"""Tests for Loom Phase 4: StyleCalibrationService, RhythmAnalysisService, and DialogueSignalService.

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
    GraphEdge,
    GraphNode,
    RetrievalChunk,
    RetrievalDocument,
)
from novel_analyzer.database.session import create_schema
from novel_analyzer.services.dialogue_signal_service import DialogueSignalService
from novel_analyzer.services.rhythm_analysis_service import (
    PACING_ACTION_HEAVY,
    PACING_BALANCED,
    PACING_SLOW_BURN,
    RhythmAnalysisService,
)
from novel_analyzer.services.style_calibration_service import StyleCalibrationService


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    create_schema(engine)
    return Session(engine)


def _branch_id() -> str:
    return str(uuid.uuid4())


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


def _add_chapter_artifact(
    session: Session,
    branch_id: str,
    chapter_index: int,
    summary: str = "",
) -> None:
    session.add(ChapterArtifact(
        branch_id=branch_id,
        chapter_index=chapter_index,
        artifact_type="chapter_analysis",
        payload_json={
            "chapter_summary": summary or f"第{chapter_index}章摘要内容" * 10,
            "key_entities": ["张三"],
            "key_events": [f"事件{chapter_index}"],
        },
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
# StyleCalibrationService tests
# ===========================================================================

def test_style_drift_no_embeddings() -> None:
    with _session() as session:
        svc = StyleCalibrationService(session)
        result = svc.compute_style_drift(_branch_id(), 5)
        assert result.style_drift_score == 0.0
        assert result.alert_level == "none"


def test_style_drift_no_reference_chapters() -> None:
    with _session() as session:
        bid = _branch_id()
        _add_chapter_embedding(session, bid, 1, [1.0, 0.0])
        session.commit()
        svc = StyleCalibrationService(session)
        result = svc.compute_style_drift(bid, 1, reference_window=5)
        assert result.style_drift_score == 0.0
        assert result.alert_level == "none"
        assert result.reference_chapter_range is None


def test_style_drift_identical_vectors() -> None:
    with _session() as session:
        bid = _branch_id()
        vec = [1.0, 0.0, 0.0]
        for i in range(1, 5):
            _add_chapter_embedding(session, bid, i, vec)
        session.commit()
        svc = StyleCalibrationService(session)
        result = svc.compute_style_drift(bid, 4, reference_window=3)
        assert result.style_drift_score == 0.0
        assert result.alert_level == "none"


def test_style_drift_orthogonal_vectors() -> None:
    with _session() as session:
        bid = _branch_id()
        for i in range(1, 4):
            _add_chapter_embedding(session, bid, i, [1.0, 0.0])
        _add_chapter_embedding(session, bid, 4, [0.0, 1.0])
        session.commit()
        svc = StyleCalibrationService(session)
        result = svc.compute_style_drift(bid, 4, reference_window=3)
        assert result.style_drift_score > 0.5
        assert result.alert_level in ("warn", "critical")
        assert result.reference_chapter_range == (1, 3)


def test_style_drift_warn_threshold() -> None:
    with _session() as session:
        bid = _branch_id()
        import math
        angle = 0.20
        for i in range(1, 4):
            _add_chapter_embedding(session, bid, i, [1.0, 0.0])
        _add_chapter_embedding(session, bid, 4, [math.cos(angle), math.sin(angle)])
        session.commit()
        svc = StyleCalibrationService(session)
        result = svc.compute_style_drift(bid, 4, reference_window=3)
        assert result.alert_level in ("warn", "critical", "none")


def test_style_drift_to_signal_dict() -> None:
    with _session() as session:
        bid = _branch_id()
        _add_chapter_embedding(session, bid, 1, [1.0, 0.0])
        _add_chapter_embedding(session, bid, 2, [0.0, 1.0])
        session.commit()
        svc = StyleCalibrationService(session)
        result = svc.compute_style_drift(bid, 2, reference_window=1)
        signal = result.to_style_signal()
        assert "style_drift_score" in signal
        assert "alert_level" in signal
        assert "chapter_index" in signal
        assert signal["chapter_index"] == 2


def test_style_drift_critical_suggestion_not_empty() -> None:
    with _session() as session:
        bid = _branch_id()
        for i in range(1, 4):
            _add_chapter_embedding(session, bid, i, [1.0, 0.0])
        _add_chapter_embedding(session, bid, 4, [0.0, 1.0])
        session.commit()
        svc = StyleCalibrationService(session)
        result = svc.compute_style_drift(bid, 4, reference_window=3)
        if result.alert_level != "none":
            assert result.suggestion != ""


# ===========================================================================
# RhythmAnalysisService tests
# ===========================================================================

def test_rhythm_no_data() -> None:
    with _session() as session:
        svc = RhythmAnalysisService(session)
        result = svc.compute(_branch_id(), 1)
        assert result.hook_density == 0.0
        assert result.climax_score == 0.0
        assert result.alert_level == "warn"


def test_rhythm_hook_density_with_facts() -> None:
    with _session() as session:
        bid = _branch_id()
        _add_chapter_artifact(session, bid, 1, summary="摘要" * 50)
        for _ in range(3):
            _add_fact(session, bid, 1, "hook", "钩子事件")
        _add_fact(session, bid, 1, "character", "角色事件")
        session.commit()
        svc = RhythmAnalysisService(session)
        result = svc.compute(bid, 1)
        assert result.hook_density > 0.0
        assert result.climax_score > 0.0


def test_rhythm_no_hooks_triggers_warn() -> None:
    with _session() as session:
        bid = _branch_id()
        _add_chapter_artifact(session, bid, 1, summary="摘要" * 50)
        _add_fact(session, bid, 1, "character", "角色")
        _add_fact(session, bid, 1, "world_rule", "规则")
        session.commit()
        svc = RhythmAnalysisService(session)
        result = svc.compute(bid, 1)
        assert result.hook_density == 0.0
        assert result.alert_level == "warn"
        assert result.suggestion != ""


def test_rhythm_high_hook_density_no_warn() -> None:
    with _session() as session:
        bid = _branch_id()
        _add_chapter_artifact(session, bid, 1, summary="摘要" * 10)
        for _ in range(5):
            _add_fact(session, bid, 1, "climax", "高潮")
        session.commit()
        svc = RhythmAnalysisService(session)
        result = svc.compute(bid, 1)
        assert result.hook_density > 1.0
        assert result.alert_level == "none"


def test_rhythm_pacing_slow_burn() -> None:
    with _session() as session:
        bid = _branch_id()
        for i in range(1, 7):
            _add_chapter_artifact(session, bid, i, summary="摘要" * 50)
            _add_fact(session, bid, i, "character", "角色")
        session.commit()
        svc = RhythmAnalysisService(session)
        result = svc.compute(bid, 6, lookback_n=5)
        assert result.pacing_type == PACING_SLOW_BURN


def test_rhythm_pacing_action_heavy() -> None:
    with _session() as session:
        bid = _branch_id()
        for i in range(1, 7):
            _add_chapter_artifact(session, bid, i, summary="摘要" * 5)
            for _ in range(10):
                _add_fact(session, bid, i, "climax", f"高潮{i}")
        session.commit()
        svc = RhythmAnalysisService(session)
        result = svc.compute(bid, 6, lookback_n=5)
        assert result.pacing_type == PACING_ACTION_HEAVY


def test_rhythm_to_signal_dict() -> None:
    with _session() as session:
        bid = _branch_id()
        _add_chapter_artifact(session, bid, 1)
        session.commit()
        svc = RhythmAnalysisService(session)
        result = svc.compute(bid, 1)
        signal = result.to_rhythm_signal()
        assert "hook_density" in signal
        assert "pacing_type" in signal
        assert "climax_score" in signal
        assert "alert_level" in signal
        assert signal["chapter_index"] == 1


def _add_graph_node(
    session: Session,
    branch_id: str,
    chapter_index: int,
    node_type: str,
    label: str,
) -> GraphNode:
    node = GraphNode(
        branch_id=branch_id,
        node_type=node_type,
        label=label,
        chapter_first_seen=chapter_index,
        chapter_last_seen=chapter_index,
    )
    session.add(node)
    session.flush()
    return node


def _add_graph_edge(
    session: Session,
    branch_id: str,
    chapter_index: int,
    source_node: GraphNode,
    target_node: GraphNode,
    edge_type: str,
) -> None:
    session.add(GraphEdge(
        branch_id=branch_id,
        source_node_id=source_node.id,
        target_node_id=target_node.id,
        edge_type=edge_type,
        chapter_first_seen=chapter_index,
        chapter_last_seen=chapter_index,
    ))
    session.flush()


# ===========================================================================
# DialogueSignalService tests
# ===========================================================================

def test_dialogue_signal_no_data() -> None:
    with _session() as session:
        svc = DialogueSignalService(session)
        result = svc.compute(_branch_id(), 1)
        assert result.character_voice_consistency == 1.0
        assert result.dialogue_efficiency == 0.0
        assert result.conflict_dialogue_density == 0.0
        assert result.alert_level in ("none", "warn")


def test_dialogue_signal_no_entities() -> None:
    with _session() as session:
        bid = _branch_id()
        _add_chapter_artifact(session, bid, 1)
        session.commit()
        svc = DialogueSignalService(session)
        result = svc.compute(bid, 1)
        assert result.character_voice_consistency == 1.0


def test_dialogue_efficiency_with_edges() -> None:
    with _session() as session:
        bid = _branch_id()
        entity = _add_graph_node(session, bid, 1, "entity", "张三")
        event = _add_graph_node(session, bid, 1, "event", "战斗")
        _add_graph_edge(session, bid, 1, entity, event, "participates_in")
        _add_fact(session, bid, 1, "event", "战斗")
        session.commit()
        svc = DialogueSignalService(session)
        result = svc.compute(bid, 1)
        assert result.dialogue_efficiency > 0.0


def test_dialogue_conflict_density_with_conflict_edges() -> None:
    with _session() as session:
        bid = _branch_id()
        entity_a = _add_graph_node(session, bid, 1, "entity", "张三")
        entity_b = _add_graph_node(session, bid, 1, "entity", "李四")
        conflict = _add_graph_node(session, bid, 1, "conflict", "冲突")
        _add_graph_edge(session, bid, 1, entity_a, conflict, "conflict_involves")
        _add_graph_edge(session, bid, 1, entity_a, entity_b, "co_occurs")
        session.commit()
        svc = DialogueSignalService(session)
        result = svc.compute(bid, 1)
        assert result.conflict_dialogue_density > 0.0
        assert result.conflict_dialogue_density < 1.0


def test_dialogue_voice_consistency_with_embeddings() -> None:
    with _session() as session:
        bid = _branch_id()
        vec = [1.0, 0.0, 0.0]
        for i in range(1, 4):
            _add_chapter_embedding(session, bid, i, vec)
            _add_fact(session, bid, i, "entity", "张三")
        session.commit()
        svc = DialogueSignalService(session)
        result = svc.compute(bid, 3, lookback_n=2)
        assert result.character_voice_consistency >= 0.9


def test_dialogue_voice_drift_triggers_warn() -> None:
    with _session() as session:
        bid = _branch_id()
        for i in range(1, 4):
            _add_chapter_embedding(session, bid, i, [1.0, 0.0])
            _add_fact(session, bid, i, "entity", "张三")
        _add_chapter_embedding(session, bid, 4, [0.0, 1.0])
        _add_fact(session, bid, 4, "entity", "张三")
        session.commit()
        svc = DialogueSignalService(session)
        result = svc.compute(bid, 4, lookback_n=3)
        assert result.alert_level == "warn"
        assert result.suggestion != ""


def test_dialogue_signal_to_dict() -> None:
    with _session() as session:
        bid = _branch_id()
        _add_chapter_artifact(session, bid, 1)
        session.commit()
        svc = DialogueSignalService(session)
        result = svc.compute(bid, 1)
        signal = result.to_dialogue_signal()
        assert "character_voice_consistency" in signal
        assert "dialogue_efficiency" in signal
        assert "conflict_dialogue_density" in signal
        assert "alert_level" in signal
        assert signal["chapter_index"] == 1
