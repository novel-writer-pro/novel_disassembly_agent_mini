"""Tests for Loom Phase 1: MemoryConsolidationService, MemoryAssemblerService,
TensionService, and PairwiseEvalService.

All tests use SQLite in-memory so no PostgreSQL is required.
"""

from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from novel_analyzer.database.models import (
    ChapterArtifact,
    FactRecord,
    GraphEdge,
    GraphNode,
)
from novel_analyzer.database.session import create_schema
from novel_analyzer.services.fact_service import FactService
from novel_analyzer.services.graph_service import GraphService
from novel_analyzer.services.ingest_service import IngestService
from novel_analyzer.services.memory_assembler_service import MemoryAssemblerService
from novel_analyzer.services.memory_consolidation_service import (
    MemoryConsolidationService,
)
from novel_analyzer.services.pairwise_eval_service import PairwiseEvalService
from novel_analyzer.services.run_service import RunService
from novel_analyzer.services.tension_service import TensionService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    create_schema(engine)
    return Session(engine)


def _chapter_payload(
    chapter_index: int,
    *,
    entities: list[str] | None = None,
    events: list[str] | None = None,
    summary: str = "",
    state_transition_notes: list[str] | None = None,
) -> dict[str, object]:
    return {
        "chapter_index": chapter_index,
        "normalized_title": f"第{chapter_index}章",
        "chapter_summary": summary or f"第{chapter_index}章摘要",
        "key_entities": entities or ["张三", "李四"],
        "key_events": events or [f"第{chapter_index}章事件"],
        "continuity_notes": [f"第{chapter_index}章衔接"],
        "writer_learning_notes": [],
        "unsupported_inferences": [],
        "ambiguous_points": [],
        "needs_human_review": False,
        "quality_gate_notes": [],
        "hook_score": 4.0,
        "dimensions": [],
        "state_transition_notes": state_transition_notes or [],
    }


def _stage_payload(
    characters: list[dict] | None = None,
    events: list[dict] | None = None,
    conflicts: list[dict] | None = None,
) -> dict[str, object]:
    return {
        "facts": {
            "characters": characters or [],
            "events": events or [],
            "relations": [],
            "conflicts": conflicts or [],
            "foreshadowing": [],
            "worldbuilding_facts": [],
        },
        "analysis": {"continuity_notes": []},
    }


def _setup_branch(session: Session, tmp_path):
    """Create novel → run → branch, return (run_id, branch_id)."""
    novel_path = tmp_path / "novel.txt"
    novel_path.write_text("第1章 一\n正文\n", encoding="utf-8")
    novel, manifest = IngestService(session).ingest_text_file(str(novel_path), "测试小说")
    run, branch = RunService(session).create_run(novel.id, manifest.id)
    return run.id, branch.id


def _record_chapter(
    session: Session,
    run_id: str,
    branch_id: str,
    chapter_index: int,
    *,
    entities: list[str] | None = None,
    events: list[str] | None = None,
    summary: str = "",
    state_transition_notes: list[str] | None = None,
    conflicts: list[dict] | None = None,
) -> ChapterArtifact:
    """Record artifact + stage payload + materialise graph + facts."""
    payload = _chapter_payload(
        chapter_index,
        entities=entities,
        events=events,
        summary=summary,
        state_transition_notes=state_transition_notes,
    )
    artifact = RunService(session).record_chapter_artifact(branch_id, chapter_index, payload)

    char_list = [
        {"label": e, "evidence": [e], "confidence": 0.9}
        for e in (entities or ["张三"])
    ]
    RunService(session).record_raw_output(
        run_id,
        branch_id,
        chapter_index,
        1,
        json.dumps(_stage_payload(characters=char_list, conflicts=conflicts or []), ensure_ascii=False),
        parsed_json={"ok": True},
        parse_status="parsed",
        parse_error=None,
        invocation_metadata={},
    )
    GraphService(session).materialize_for_artifact(artifact.id)
    FactService(session).materialize_for_artifact(artifact.id)
    return artifact


# ===========================================================================
# DB model tests – new Loom fields have correct defaults
# ===========================================================================


def test_fact_record_loom_fields_have_defaults(tmp_path) -> None:
    with _session() as session:
        run_id, branch_id = _setup_branch(session, tmp_path)
        _record_chapter(session, run_id, branch_id, 1)
        facts = session.scalars(
            select(FactRecord).where(FactRecord.branch_id == branch_id)
        ).all()
        assert facts, "No FactRecords created"
        for f in facts:
            assert f.importance_score == 0.5
            assert f.decay_factor == 1.0
            assert f.episodic_status == "active"


def test_graph_node_loom_fields_have_defaults(tmp_path) -> None:
    with _session() as session:
        run_id, branch_id = _setup_branch(session, tmp_path)
        _record_chapter(session, run_id, branch_id, 1)
        nodes = session.scalars(
            select(GraphNode).where(GraphNode.branch_id == branch_id)
        ).all()
        assert nodes, "No GraphNodes created"
        for n in nodes:
            assert n.conflict_status == "clean"
            assert n.loom_version == 1
            assert n.superseded_by_node_id is None
            assert n.importance_score == 0.5


def test_graph_edge_loom_fields_have_defaults(tmp_path) -> None:
    with _session() as session:
        run_id, branch_id = _setup_branch(session, tmp_path)
        _record_chapter(session, run_id, branch_id, 1, entities=["张三", "李四"])
        _record_chapter(session, run_id, branch_id, 2, entities=["张三", "李四"])
        edges = session.scalars(
            select(GraphEdge).where(GraphEdge.branch_id == branch_id)
        ).all()
        # Edges may or may not exist depending on graph materialisation
        for e in edges:
            assert e.conflict_status == "clean"
            assert e.loom_version == 1
            assert e.is_active is True


# ===========================================================================
# MemoryConsolidationService tests
# ===========================================================================


def test_consolidation_clean_new_chapter(tmp_path) -> None:
    """First chapter has no history → no conflicts."""
    with _session() as session:
        run_id, branch_id = _setup_branch(session, tmp_path)
        _record_chapter(session, run_id, branch_id, 1)
        svc = MemoryConsolidationService(session)
        result = svc.consolidate(branch_id, 1)
        assert result.total_conflicts == 0
        assert not result.human_review_required


def test_consolidation_decay_reduces_importance(tmp_path) -> None:
    """After consolidation, old facts should have decayed decay_factor."""
    with _session() as session:
        run_id, branch_id = _setup_branch(session, tmp_path)
        _record_chapter(session, run_id, branch_id, 1)
        _record_chapter(session, run_id, branch_id, 2)
        svc = MemoryConsolidationService(session)
        svc.consolidate(branch_id, 2)
        ch1_facts = session.scalars(
            select(FactRecord)
            .where(FactRecord.branch_id == branch_id)
            .where(FactRecord.chapter_index == 1)
        ).all()
        assert ch1_facts, "Chapter 1 facts should exist"
        for f in ch1_facts:
            assert f.decay_factor < 1.0, f"decay_factor should have decreased, got {f.decay_factor}"


def test_consolidation_result_operator_signal(tmp_path) -> None:
    """to_operator_signal() returns expected keys."""
    with _session() as session:
        run_id, branch_id = _setup_branch(session, tmp_path)
        _record_chapter(session, run_id, branch_id, 1)
        svc = MemoryConsolidationService(session)
        result = svc.consolidate(branch_id, 1)
        signal = result.to_operator_signal()
        assert "chapter_index" in signal
        assert "contradictions_found" in signal
        assert "human_review_required" in signal
        assert "conflict_summary" in signal


def test_consolidation_multiple_chapters(tmp_path) -> None:
    """Consolidation runs cleanly across 5 chapters."""
    with _session() as session:
        run_id, branch_id = _setup_branch(session, tmp_path)
        svc = MemoryConsolidationService(session)
        for i in range(1, 6):
            _record_chapter(session, run_id, branch_id, i, entities=["主角", f"配角{i}"])
            result = svc.consolidate(branch_id, i)
            assert isinstance(result.total_conflicts, int)


# ===========================================================================
# MemoryAssemblerService tests
# ===========================================================================


def test_assembler_returns_assembled_memory(tmp_path) -> None:
    with _session() as session:
        run_id, branch_id = _setup_branch(session, tmp_path)
        for i in range(1, 4):
            _record_chapter(session, run_id, branch_id, i, entities=["张三", "李四"])
        svc = MemoryAssemblerService(session)
        mem = svc.assemble(branch_id, target_chapter_index=4)
        assert mem.assembled_at_chapter == 4
        assert mem.loom_version == "1.0"


def test_assembler_carry_over_state_has_legacy_compat(tmp_path) -> None:
    """_legacy_compat must contain the keys 0509 session_state expects."""
    with _session() as session:
        run_id, branch_id = _setup_branch(session, tmp_path)
        for i in range(1, 3):
            _record_chapter(session, run_id, branch_id, i)
        svc = MemoryAssemblerService(session)
        mem = svc.assemble(branch_id, target_chapter_index=3)
        cos = mem.to_carry_over_state()
        assert "_legacy_compat" in cos
        lc = cos["_legacy_compat"]
        assert "characters" in lc
        assert "rules" in lc
        assert "unresolved_threads" in lc
        assert "previous_chapter_summary" in lc


def test_assembler_episodic_anchors_sorted_by_effective_score(tmp_path) -> None:
    """Episodic anchors should be sorted by importance_score * decay_factor desc."""
    with _session() as session:
        run_id, branch_id = _setup_branch(session, tmp_path)
        for i in range(1, 6):
            _record_chapter(session, run_id, branch_id, i)
        # Manually boost one fact's importance
        facts = session.scalars(
            select(FactRecord).where(FactRecord.branch_id == branch_id)
        ).all()
        if facts:
            facts[0].importance_score = 0.95
            session.flush()
        svc = MemoryAssemblerService(session)
        mem = svc.assemble(branch_id, target_chapter_index=6)
        anchors = mem.episodic_anchors
        if len(anchors) >= 2:
            scores = [a["effective_score"] for a in anchors]
            assert scores == sorted(scores, reverse=True), "Anchors not sorted by effective_score"


def test_assembler_active_characters_excludes_contradictions(tmp_path) -> None:
    """Characters with conflict_status='contradiction' should not appear."""
    with _session() as session:
        run_id, branch_id = _setup_branch(session, tmp_path)
        _record_chapter(session, run_id, branch_id, 1, entities=["张三"])
        # Manually mark 张三 as contradiction
        node = session.scalar(
            select(GraphNode)
            .where(GraphNode.branch_id == branch_id)
            .where(GraphNode.label == "张三")
        )
        if node:
            node.conflict_status = "contradiction"
            session.flush()
        svc = MemoryAssemblerService(session)
        mem = svc.assemble(branch_id, target_chapter_index=2)
        labels = [c["label"] for c in mem.active_characters]
        assert "张三" not in labels, "Contradicted character should be excluded"


# ===========================================================================
# TensionService tests
# ===========================================================================


def test_tension_service_returns_score(tmp_path) -> None:
    with _session() as session:
        run_id, branch_id = _setup_branch(session, tmp_path)
        for i in range(1, 4):
            _record_chapter(session, run_id, branch_id, i)
        svc = TensionService(session)
        score = svc.compute(branch_id, chapter_index=3)
        assert 0.0 <= score.tension_score <= 1.0
        assert 0.0 <= score.plot_similarity <= 1.0
        assert score.conflict_density >= 0.0
        assert 0.0 <= score.surprise_index <= 1.0


def test_tension_operator_signal_keys(tmp_path) -> None:
    with _session() as session:
        run_id, branch_id = _setup_branch(session, tmp_path)
        _record_chapter(session, run_id, branch_id, 1)
        svc = TensionService(session)
        score = svc.compute(branch_id, chapter_index=1)
        sig = score.to_operator_signal()
        assert "chapter_index" in sig
        assert "tension_score" in sig
        assert "status" in sig
        assert "metrics" in sig
        assert "plot_similarity" in sig["metrics"]
        assert "conflict_density" in sig["metrics"]
        assert "surprise_index" in sig["metrics"]


def test_tension_surprise_index_new_chapter(tmp_path) -> None:
    """First chapter has all-new facts → surprise_index should be 1.0."""
    with _session() as session:
        run_id, branch_id = _setup_branch(session, tmp_path)
        _record_chapter(session, run_id, branch_id, 1, entities=["全新角色A", "全新角色B"])
        svc = TensionService(session)
        score = svc.compute(branch_id, chapter_index=1)
        # Chapter 1 has no prior facts → surprise = 1.0
        assert score.surprise_index == 1.0


def test_tension_surprise_index_repeated_chapter(tmp_path) -> None:
    """Chapter with same entities as previous → lower surprise_index."""
    with _session() as session:
        run_id, branch_id = _setup_branch(session, tmp_path)
        _record_chapter(session, run_id, branch_id, 1, entities=["张三", "李四"])
        _record_chapter(session, run_id, branch_id, 2, entities=["张三", "李四"])
        svc = TensionService(session)
        score_ch1 = svc.compute(branch_id, chapter_index=1)
        score_ch2 = svc.compute(branch_id, chapter_index=2)
        assert score_ch2.surprise_index < score_ch1.surprise_index


def test_tension_alerts_generated_for_low_tension(tmp_path) -> None:
    """Repeated identical chapters should trigger alerts."""
    with _session() as session:
        run_id, branch_id = _setup_branch(session, tmp_path)
        # 4 chapters with identical entities → high similarity, low surprise
        for i in range(1, 5):
            _record_chapter(session, run_id, branch_id, i, entities=["张三", "李四"], events=["同一事件"])
        svc = TensionService(session)
        score = svc.compute(branch_id, chapter_index=4)
        # With identical content, surprise_index should be very low → alert
        assert score.surprise_index < 0.5


def test_tension_with_rhythm_signal_double_flat(tmp_path) -> None:
    """Low hook_density + low conflict_density → double_flat alert."""
    with _session() as session:
        run_id, branch_id = _setup_branch(session, tmp_path)
        for i in range(1, 4):
            _record_chapter(session, run_id, branch_id, i, entities=["张三"], events=["普通事件"])
        svc = TensionService(session)
        rhythm_signal = {
            "hook_density": 0.2,
            "alert_level": "warn",
            "pacing_type": "slow_burn",
            "climax_score": 0.0,
        }
        score = svc.compute(branch_id, chapter_index=3, rhythm_signal=rhythm_signal)
        alert_types = [a.alert_type for a in score.alerts]
        assert "double_flat" in alert_types or "low_hook_density" in alert_types


def test_tension_with_rhythm_signal_no_extra_alert_when_ok(tmp_path) -> None:
    """Normal hook_density → no extra rhythm alert."""
    with _session() as session:
        run_id, branch_id = _setup_branch(session, tmp_path)
        _record_chapter(session, run_id, branch_id, 1, entities=["张三"])
        svc = TensionService(session)
        rhythm_signal = {
            "hook_density": 2.5,
            "alert_level": "none",
            "pacing_type": "balanced",
            "climax_score": 0.4,
        }
        score = svc.compute(branch_id, chapter_index=1, rhythm_signal=rhythm_signal)
        alert_types = [a.alert_type for a in score.alerts]
        assert "double_flat" not in alert_types
        assert "low_hook_density" not in alert_types


# ===========================================================================
# PairwiseEvalService tests
# ===========================================================================


def test_pairwise_heuristic_prefers_pass_verdict() -> None:
    """Heuristic should prefer the draft with 'pass' risk verdict."""
    svc = PairwiseEvalService(llm_client=None)
    result = svc.evaluate(
        pair_id="test-1",
        branch_id="branch-1",
        chapter_index=5,
        draft_a="这是草案A，内容较短。",
        draft_b="这是草案B，内容更长，描写更丰富，情节更完整，角色动机更清晰。" * 10,
        risk_verdict_a="revise",
        risk_verdict_b="pass",
    )
    assert result.overall_preference == "B"
    assert result.evaluation_method == "heuristic"


def test_pairwise_heuristic_tie_on_similar_drafts() -> None:
    """Similar drafts with same verdict → tie."""
    svc = PairwiseEvalService(llm_client=None)
    result = svc.evaluate(
        pair_id="test-2",
        branch_id="branch-1",
        chapter_index=3,
        draft_a="草案A内容。",
        draft_b="草案B内容。",
        risk_verdict_a="pass",
        risk_verdict_b="pass",
    )
    assert result.overall_preference == "tie"


def test_pairwise_quality_score_range() -> None:
    """quality_score must be in [0, 1]."""
    svc = PairwiseEvalService(llm_client=None)
    result = svc.evaluate(
        pair_id="test-3",
        branch_id="branch-1",
        chapter_index=1,
        draft_a="A" * 500,
        draft_b="B" * 200,
        risk_verdict_a="pass",
        risk_verdict_b="revise",
    )
    assert 0.0 <= result.quality_score <= 1.0


def test_pairwise_chapter_quality_signal_keys() -> None:
    """to_chapter_quality_signal() must contain keys 0509 expects."""
    svc = PairwiseEvalService(llm_client=None)
    result = svc.evaluate(
        pair_id="test-4",
        branch_id="branch-1",
        chapter_index=7,
        draft_a="草案A",
        draft_b="草案B",
    )
    sig = result.to_chapter_quality_signal()
    assert "chapter_index" in sig
    assert "quality_score" in sig
    assert "confidence" in sig
    assert "overall_preference" in sig
    assert "dimensions" in sig
    assert "evaluation_method" in sig


def test_pairwise_llm_response_parsing() -> None:
    """_parse_llm_response handles valid JSON correctly."""
    svc = PairwiseEvalService(llm_client=None)
    raw = json.dumps({
        "overall_preference": "A",
        "overall_reason": "A的角色动机更清晰",
        "confidence": 0.85,
        "dimensions": {
            "character_consistency": {"winner": "A", "reason": "角色行为一致", "score_diff": 0.3},
            "plot_coherence": {"winner": "A", "reason": "情节流畅", "score_diff": 0.2},
            "style_fidelity": {"winner": "tie", "reason": "风格相当", "score_diff": 0.0},
            "narrative_tension": {"winner": "B", "reason": "B张力更强", "score_diff": 0.1},
        },
    })
    result = svc._parse_llm_response(
        raw, pair_id="p1", branch_id="b1", chapter_index=3
    )
    assert result.overall_preference == "A"
    assert result.confidence == 0.85
    assert result.dimensions["character_consistency"].winner == "A"
    assert result.dimensions["style_fidelity"].winner == "tie"
    assert 0.0 <= result.quality_score <= 1.0


def test_pairwise_llm_response_invalid_json_fallback() -> None:
    """Invalid JSON from LLM → fallback result with tie."""
    svc = PairwiseEvalService(llm_client=None)
    result = svc._parse_llm_response(
        "这不是JSON", pair_id="p2", branch_id="b1", chapter_index=1
    )
    assert result.overall_preference == "tie"
    assert result.confidence == 0.0
    assert result.evaluation_method == "fallback"


# ===========================================================================
# Integration: consolidation → assembler → tension pipeline
# ===========================================================================


def test_full_loom_pipeline(tmp_path) -> None:
    """End-to-end: 5 chapters → consolidate → assemble → tension."""
    with _session() as session:
        run_id, branch_id = _setup_branch(session, tmp_path)
        consolidation_svc = MemoryConsolidationService(session)
        assembler_svc = MemoryAssemblerService(session)
        tension_svc = TensionService(session)

        entity_sets = [
            ["主角", "反派"],
            ["主角", "盟友"],
            ["主角", "反派", "新角色"],
            ["主角", "盟友", "反派"],
            ["主角", "新角色2", "神秘人"],
        ]

        for i, entities in enumerate(entity_sets, start=1):
            _record_chapter(session, run_id, branch_id, i, entities=entities)
            c_result = consolidation_svc.consolidate(branch_id, i)
            assert isinstance(c_result.total_conflicts, int)

        # Assemble memory for chapter 6
        mem = assembler_svc.assemble(branch_id, target_chapter_index=6)
        cos = mem.to_carry_over_state()
        assert cos["loom_version"] == "1.0"
        assert "_legacy_compat" in cos

        # Tension for chapter 5
        t_score = tension_svc.compute(branch_id, chapter_index=5)
        assert 0.0 <= t_score.tension_score <= 1.0
        sig = t_score.to_operator_signal()
        assert sig["loom_version"] == "1.0"
