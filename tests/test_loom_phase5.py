"""Tests for Loom Phase 5: ThreadSchedulerService, ReaderSimulationService, LongBookHealthService.

All tests use SQLite in-memory so no PostgreSQL is required.
"""

from __future__ import annotations

import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from novel_analyzer.database.models import (
    ChapterArtifact,
    ChunkEmbedding,
    FactRecord,
    GraphNode,
    RetrievalChunk,
    RetrievalDocument,
)
from novel_analyzer.database.session import create_schema
from novel_analyzer.services.long_book_health_service import LongBookHealthService
from novel_analyzer.services.reader_simulation_service import ReaderSimulationService
from novel_analyzer.services.thread_scheduler_service import ThreadSchedulerService


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    create_schema(engine)
    return Session(engine)


def _branch_id() -> str:
    return str(uuid.uuid4())


def _add_thread_node(
    session: Session,
    branch_id: str,
    chapter_first: int,
    chapter_last: int,
    node_type: str = "foreshadow",
    label: str = "伏笔",
    importance: float = 0.7,
) -> GraphNode:
    node = GraphNode(
        branch_id=branch_id,
        node_type=node_type,
        label=label,
        chapter_first_seen=chapter_first,
        chapter_last_seen=chapter_last,
        importance_score=importance,
    )
    session.add(node)
    session.flush()
    return node


def _add_chapter_artifact(
    session: Session,
    branch_id: str,
    chapter_index: int,
    quality_score: float | None = None,
    summary: str = "",
) -> None:
    payload: dict = {
        "chapter_summary": summary or f"第{chapter_index}章摘要",
        "key_entities": ["张三"],
        "key_events": [f"事件{chapter_index}"],
    }
    if quality_score is not None:
        payload["chapter_quality_score"] = quality_score
    session.add(ChapterArtifact(
        branch_id=branch_id,
        chapter_index=chapter_index,
        artifact_type="chapter_analysis",
        payload_json=payload,
    ))
    session.flush()


def _add_chapter_embedding(
    session: Session,
    branch_id: str,
    chapter_index: int,
    vector: list[float],
) -> None:
    doc = RetrievalDocument(
        branch_id=branch_id,
        chapter_index=chapter_index,
        title=f"第{chapter_index}章",
        summary_text=f"第{chapter_index}章摘要",
        bm25_text=f"第{chapter_index}章",
        keyword_list=[],
        query_hints=[],
        materialization_status="ready",
    )
    session.add(doc)
    session.flush()
    chunk = RetrievalChunk(
        document_id=doc.id,
        chunk_order=0,
        text=f"第{chapter_index}章正文",
        start_offset=0,
        end_offset=10,
        embedding_status="ready",
        keyword_list=[],
    )
    session.add(chunk)
    session.flush()
    session.add(ChunkEmbedding(
        chunk_id=chunk.id,
        model_name="stub",
        vector_dim=len(vector),
        vector_payload=vector,
        l2_norm=1.0,
        status="ready",
    ))
    session.flush()


def _add_fact(
    session: Session,
    branch_id: str,
    chapter_index: int,
    fact_type: str,
    label: str = "事件",
) -> None:
    session.add(FactRecord(
        branch_id=branch_id,
        chapter_index=chapter_index,
        fact_type=fact_type,
        label=label,
        evidence_list=[],
        confidence=0.9,
    ))
    session.flush()


# ===========================================================================
# ThreadSchedulerService tests
# ===========================================================================

def test_thread_scheduler_no_threads() -> None:
    with _session() as session:
        svc = ThreadSchedulerService(session)
        report = svc.analyze_thread_status(_branch_id(), 10)
        assert report.active_threads == []
        assert report.dormant_threads == []
        assert report.overdue_threads == []
        assert report.overdue_ratio == 0.0


def test_thread_scheduler_active_thread() -> None:
    with _session() as session:
        bid = _branch_id()
        _add_thread_node(session, bid, 1, 8, label="近期伏笔")
        session.commit()
        svc = ThreadSchedulerService(session)
        report = svc.analyze_thread_status(bid, 10)
        assert len(report.active_threads) == 1
        assert report.dormant_threads == []
        assert report.overdue_threads == []


def test_thread_scheduler_dormant_thread() -> None:
    with _session() as session:
        bid = _branch_id()
        _add_thread_node(session, bid, 1, 3, label="沉寂伏笔")
        session.commit()
        svc = ThreadSchedulerService(session)
        report = svc.analyze_thread_status(bid, 10)
        assert len(report.dormant_threads) == 1
        assert report.active_threads == []


def test_thread_scheduler_overdue_thread() -> None:
    with _session() as session:
        bid = _branch_id()
        _add_thread_node(session, bid, 1, 1, label="过期伏笔")
        session.commit()
        svc = ThreadSchedulerService(session)
        report = svc.analyze_thread_status(bid, 20)
        assert len(report.overdue_threads) == 1
        assert report.overdue_ratio > 0.0


def test_thread_scheduler_suggest_activation() -> None:
    with _session() as session:
        bid = _branch_id()
        _add_thread_node(session, bid, 1, 1, label="重要伏笔", importance=0.9)
        session.commit()
        svc = ThreadSchedulerService(session)
        signal = svc.suggest_thread_activation(bid, 20)
        assert signal.suggested_thread == "重要伏笔"
        assert signal.chapters_dormant == 19
        assert signal.suggestion != ""


def test_thread_scheduler_no_suggestion_when_all_active() -> None:
    with _session() as session:
        bid = _branch_id()
        _add_thread_node(session, bid, 1, 9, label="活跃伏笔")
        session.commit()
        svc = ThreadSchedulerService(session)
        signal = svc.suggest_thread_activation(bid, 10)
        assert signal.suggested_thread is None


def test_thread_scheduler_to_dict() -> None:
    with _session() as session:
        bid = _branch_id()
        _add_thread_node(session, bid, 1, 1, label="伏笔A")
        session.commit()
        svc = ThreadSchedulerService(session)
        report = svc.analyze_thread_status(bid, 20)
        d = report.to_thread_status()
        assert "overdue_count" in d
        assert "overdue_ratio" in d
        assert "active_threads" in d


def test_thread_scheduler_total_count() -> None:
    with _session() as session:
        bid = _branch_id()
        _add_thread_node(session, bid, 1, 5, label="伏笔A")
        _add_thread_node(session, bid, 2, 8, label="伏笔B", node_type="conflict")
        session.commit()
        svc = ThreadSchedulerService(session)
        assert svc.get_total_thread_count(bid) == 2


# ===========================================================================
# ReaderSimulationService tests
# ===========================================================================

def test_reader_sim_no_data() -> None:
    with _session() as session:
        svc = ReaderSimulationService(session)
        result = svc.simulate_all_panels(_branch_id(), 1)
        assert 0.0 <= result.overall_score <= 1.0
        assert len(result.panels) == 4
        assert result.alert_level in ("none", "warn", "critical")


def test_reader_sim_panel_types() -> None:
    with _session() as session:
        svc = ReaderSimulationService(session)
        result = svc.simulate_all_panels(_branch_id(), 1)
        panel_types = {p.panel_type for p in result.panels}
        assert panel_types == {"casual", "veteran", "satisfaction", "editor"}


def test_reader_sim_to_dict() -> None:
    with _session() as session:
        svc = ReaderSimulationService(session)
        result = svc.simulate_all_panels(_branch_id(), 1)
        d = result.to_reader_satisfaction()
        assert "overall_score" in d
        assert "panels" in d
        assert len(d["panels"]) == 4
        assert d["chapter_index"] == 1


def test_reader_sim_with_data() -> None:
    with _session() as session:
        bid = _branch_id()
        _add_chapter_artifact(session, bid, 1, summary="摘要" * 20)
        for _ in range(3):
            _add_fact(session, bid, 1, "climax", "高潮")
        _add_chapter_embedding(session, bid, 1, [1.0, 0.0])
        session.commit()
        svc = ReaderSimulationService(session)
        result = svc.simulate_all_panels(bid, 1)
        assert 0.0 <= result.overall_score <= 1.0


def test_reader_sim_warn_when_low_scores() -> None:
    with _session() as session:
        svc = ReaderSimulationService(session)
        result = svc.simulate_all_panels(_branch_id(), 1)
        if result.alert_level != "none":
            assert result.suggestion != ""


# ===========================================================================
# LongBookHealthService tests
# ===========================================================================

def test_long_book_health_no_data() -> None:
    with _session() as session:
        svc = LongBookHealthService(session)
        report = svc.compute_health(_branch_id(), 10)
        assert report.health_score == 1.0
        assert report.alert_level == "none"
        assert report.quality_trend == "stable"


def test_long_book_health_stable() -> None:
    with _session() as session:
        bid = _branch_id()
        for i in range(1, 6):
            _add_chapter_artifact(session, bid, i, quality_score=0.75)
        session.commit()
        svc = LongBookHealthService(session)
        report = svc.compute_health(bid, 5)
        assert report.health_score == 0.75
        assert report.quality_trend == "stable"
        assert report.alert_level == "none"


def test_long_book_health_declining() -> None:
    with _session() as session:
        bid = _branch_id()
        for i, score in enumerate([0.8, 0.7, 0.6], start=1):
            _add_chapter_artifact(session, bid, i, quality_score=score)
        session.commit()
        svc = LongBookHealthService(session)
        report = svc.compute_health(bid, 3)
        assert report.quality_trend == "declining"
        assert report.alert_level in ("warn", "critical")


def test_long_book_health_recovering() -> None:
    with _session() as session:
        bid = _branch_id()
        for i, score in enumerate([0.5, 0.6, 0.7], start=1):
            _add_chapter_artifact(session, bid, i, quality_score=score)
        session.commit()
        svc = LongBookHealthService(session)
        report = svc.compute_health(bid, 3)
        assert report.quality_trend == "recovering"


def test_long_book_health_detect_decline() -> None:
    with _session() as session:
        bid = _branch_id()
        for i, score in enumerate([0.8, 0.7, 0.6], start=1):
            _add_chapter_artifact(session, bid, i, quality_score=score)
        session.commit()
        svc = LongBookHealthService(session)
        assert svc.detect_quality_decline(bid, 3) is True


def test_long_book_health_no_decline_when_stable() -> None:
    with _session() as session:
        bid = _branch_id()
        for i in range(1, 4):
            _add_chapter_artifact(session, bid, i, quality_score=0.75)
        session.commit()
        svc = LongBookHealthService(session)
        assert svc.detect_quality_decline(bid, 3) is False


def test_long_book_health_to_dict() -> None:
    with _session() as session:
        bid = _branch_id()
        _add_chapter_artifact(session, bid, 1, quality_score=0.6)
        session.commit()
        svc = LongBookHealthService(session)
        report = svc.compute_health(bid, 1)
        d = report.to_health_signal()
        assert "health_score" in d
        assert "quality_trend" in d
        assert "alert_level" in d
        assert d["chapter_index"] == 1
