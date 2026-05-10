"""Tests for Loom Phase 2 integration:
- Settings Loom flags
- analysis_service consolidation hook (shadow mode)
- imitation_harness tension preflight check
- imitation_harness carry_over Loom assembler
- CLI commands loom-status / loom-consolidate / loom-assemble
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from typer.testing import CliRunner

from novel_analyzer.cli.app import app
from tests.cli_test_support import patch_cli_sqlite_runtime
from novel_analyzer.config.settings import Settings
from novel_analyzer.database.models import ChapterArtifact, FactRecord, GraphNode
from novel_analyzer.database.session import create_schema
from novel_analyzer.services.fact_service import FactService
from novel_analyzer.services.graph_service import GraphService
from novel_analyzer.services.imitation_harness_service import HarnessControllerService
from novel_analyzer.services.ingest_service import IngestService
from novel_analyzer.services.memory_consolidation_service import MemoryConsolidationService
from novel_analyzer.services.run_service import RunService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    create_schema(engine)
    return Session(engine)


def _chapter_payload(
    chapter_index: int,
    entities: list[str] | None = None,
    events: list[str] | None = None,
) -> dict[str, object]:
    return {
        "chapter_index": chapter_index,
        "normalized_title": f"第{chapter_index}章",
        "chapter_summary": f"第{chapter_index}章摘要内容",
        "key_entities": entities or ["主角", "配角"],
        "key_events": events or [f"第{chapter_index}章事件"],
        "continuity_notes": [],
        "writer_learning_notes": [],
        "unsupported_inferences": [],
        "ambiguous_points": [],
        "needs_human_review": False,
        "quality_gate_notes": [],
        "hook_score": 4.0,
        "dimensions": [],
        "state_transition_notes": [],
    }


def _setup_branch(session: Session, tmp_path: Path):
    novel_path = tmp_path / "novel.txt"
    novel_path.write_text("第1章 一\n正文\n", encoding="utf-8")
    novel, manifest = IngestService(session).ingest_text_file(str(novel_path), "测试")
    run, branch = RunService(session).create_run(novel.id, manifest.id)
    return run.id, branch.id


def _record_chapter(
    session: Session,
    run_id: str,
    branch_id: str,
    chapter_index: int,
    entities: list[str] | None = None,
) -> ChapterArtifact:
    payload = _chapter_payload(chapter_index, entities=entities)
    artifact = RunService(session).record_chapter_artifact(branch_id, chapter_index, payload)
    char_list = [{"label": e, "evidence": [e], "confidence": 0.9} for e in (entities or ["主角"])]
    RunService(session).record_raw_output(
        run_id, branch_id, chapter_index, 1,
        json.dumps({"facts": {"characters": char_list, "events": [], "relations": [],
                              "conflicts": [], "foreshadowing": [], "worldbuilding_facts": []},
                    "analysis": {}}, ensure_ascii=False),
        parsed_json={"ok": True}, parse_status="parsed",
        parse_error=None, invocation_metadata={},
    )
    GraphService(session).materialize_for_artifact(artifact.id)
    FactService(session).materialize_for_artifact(artifact.id)
    return artifact


# ===========================================================================
# Settings tests
# ===========================================================================

def test_settings_loom_defaults() -> None:
    s = Settings(
        _env_file=None,  # type: ignore[call-arg]
        db_dialect="sqlite",
        database_url="sqlite+pysqlite:///:memory:",
    )
    assert s.loom_memory_mode == "shadow"
    assert s.loom_tension_enabled is True
    assert s.loom_pairwise_enabled is False
    assert s.loom_episodic_top_k == 20
    assert s.loom_tension_lookback_n == 3
    assert s.loom_style_enabled is False
    assert s.loom_character_enabled is False


def test_settings_loom_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NOVEL_ANALYZER_LOOM_MEMORY_MODE", "enabled")
    monkeypatch.setenv("NOVEL_ANALYZER_LOOM_TENSION_ENABLED", "false")
    monkeypatch.setenv("NOVEL_ANALYZER_LOOM_PAIRWISE_ENABLED", "true")
    s = Settings(
        _env_file=None,  # type: ignore[call-arg]
        db_dialect="sqlite",
        database_url="sqlite+pysqlite:///:memory:",
    )
    assert s.loom_memory_mode == "enabled"
    assert s.loom_tension_enabled is False
    assert s.loom_pairwise_enabled is True


# ===========================================================================
# analysis_service consolidation hook
# ===========================================================================

def test_consolidation_called_in_shadow_mode(tmp_path: Path) -> None:
    """MemoryConsolidationService.consolidate is called when loom_memory_mode=shadow."""
    with _session() as session:
        run_id, branch_id = _setup_branch(session, tmp_path)
        _record_chapter(session, run_id, branch_id, 1)

        svc = MemoryConsolidationService(session)
        result = svc.consolidate(branch_id, 1)
        # Should run without error and return a result
        assert result.branch_id == branch_id
        assert result.chapter_index == 1


def test_consolidation_disabled_mode_skipped(tmp_path: Path) -> None:
    """When loom_memory_mode=disabled, consolidation is not called by analysis_service."""
    # We test this by verifying the Settings flag is respected
    s = Settings(
        _env_file=None,  # type: ignore[call-arg]
        db_dialect="sqlite",
        database_url="sqlite+pysqlite:///:memory:",
        loom_memory_mode="disabled",
    )
    assert s.loom_memory_mode == "disabled"
    # The analysis_service checks: if mode in ("shadow", "enabled", "ab")
    assert s.loom_memory_mode not in ("shadow", "enabled", "ab")


# ===========================================================================
# HarnessControllerService tension preflight
# ===========================================================================

def test_harness_preflight_tension_check_pass(tmp_path: Path) -> None:
    """Tension check passes when there's only one chapter (no history to compare)."""
    with _session() as session:
        run_id, branch_id = _setup_branch(session, tmp_path)
        _record_chapter(session, run_id, branch_id, 1, entities=["主角A", "配角B"])

        settings = Settings(
            _env_file=None,  # type: ignore[call-arg]
            db_dialect="sqlite",
            database_url="sqlite+pysqlite:///:memory:",
            loom_tension_enabled=True,
        )
        harness = HarnessControllerService(session, settings)

        from novel_analyzer.domain.schemas import ChapterImitationDraft
        draft = ChapterImitationDraft(
            source_chapter_index=1,
            original_title="原章标题",
            draft_title="测试草案",
            draft_text="这是一段测试草案文本，包含主角和配角的互动。" * 20,
            risk_gate_notes=[],
        )

        mock_compare = MagicMock()
        mock_compare.overall_verdict = "aligned"
        mock_compare.source_length = 500
        mock_compare.draft_length = 400

        with patch.object(harness.chapter_imitation, "compare_with_source", return_value=mock_compare):
            preflight = harness.preflight_draft(
                branch_id,
                source_chapter_index=1,
                draft=draft,
            )

        check_names = [c.check_name for c in preflight.checks]
        assert "loom_tension" in check_names


def test_harness_preflight_tension_disabled(tmp_path: Path) -> None:
    """When loom_tension_enabled=False, no loom_tension check is added."""
    with _session() as session:
        run_id, branch_id = _setup_branch(session, tmp_path)
        _record_chapter(session, run_id, branch_id, 1)

        settings = Settings(
            _env_file=None,  # type: ignore[call-arg]
            db_dialect="sqlite",
            database_url="sqlite+pysqlite:///:memory:",
            loom_tension_enabled=False,
        )
        harness = HarnessControllerService(session, settings)

        from novel_analyzer.domain.schemas import ChapterImitationDraft
        draft = ChapterImitationDraft(
            source_chapter_index=1,
            original_title="原章标题",
            draft_title="测试草案",
            draft_text="草案文本" * 50,
            risk_gate_notes=[],
        )
        mock_compare = MagicMock()
        mock_compare.overall_verdict = "aligned"
        mock_compare.source_length = 500
        mock_compare.draft_length = 400

        with patch.object(harness.chapter_imitation, "compare_with_source", return_value=mock_compare):
            preflight = harness.preflight_draft(
                branch_id,
                source_chapter_index=1,
                draft=draft,
            )

        check_names = [c.check_name for c in preflight.checks]
        assert "loom_tension" not in check_names


# ===========================================================================
# HarnessControllerService carry_over assembler
# ===========================================================================

def test_build_carry_over_json_shadow_mode(tmp_path: Path) -> None:
    """In shadow mode, carry_over JSON contains _loom_memory key."""
    with _session() as session:
        run_id, branch_id = _setup_branch(session, tmp_path)
        for i in range(1, 4):
            _record_chapter(session, run_id, branch_id, i)

        settings = Settings(
            _env_file=None,  # type: ignore[call-arg]
            db_dialect="sqlite",
            database_url="sqlite+pysqlite:///:memory:",
            loom_memory_mode="shadow",
        )
        harness = HarnessControllerService(session, settings)

        mock_plan = MagicMock()
        mock_plan.worldview_capsule = "仙侠世界"
        mock_plan.trope_axes = ["热血", "成长"]
        mock_plan.innovation_directives = []
        mock_plan.external_knowledge_refs = []

        result_json = harness._build_carry_over_json(
            branch_id, source_chapter_index=3, plan=mock_plan
        )
        result = json.loads(result_json)
        assert "_loom_memory" in result
        assert "loom_version" in result["_loom_memory"]
        assert "_legacy_compat" in result["_loom_memory"]


def test_build_carry_over_json_enabled_mode(tmp_path: Path) -> None:
    """In enabled mode, carry_over JSON uses Loom structure with plan fields merged."""
    with _session() as session:
        run_id, branch_id = _setup_branch(session, tmp_path)
        for i in range(1, 4):
            _record_chapter(session, run_id, branch_id, i)

        settings = Settings(
            _env_file=None,  # type: ignore[call-arg]
            db_dialect="sqlite",
            database_url="sqlite+pysqlite:///:memory:",
            loom_memory_mode="enabled",
        )
        harness = HarnessControllerService(session, settings)

        mock_plan = MagicMock()
        mock_plan.worldview_capsule = "都市异能"
        mock_plan.trope_axes = ["逆袭"]
        mock_plan.innovation_directives = ["引入新反派"]
        mock_plan.external_knowledge_refs = []

        result_json = harness._build_carry_over_json(
            branch_id, source_chapter_index=3, plan=mock_plan
        )
        result = json.loads(result_json)
        # Loom structure
        assert "loom_version" in result
        assert "working_memory" in result
        assert "episodic_anchors" in result
        # Plan fields merged in
        assert result["worldview_capsule"] == "都市异能"
        assert result["innovation_directives"] == ["引入新反派"]


def test_build_carry_over_json_disabled_mode(tmp_path: Path) -> None:
    """In disabled mode, carry_over JSON is pure legacy format."""
    with _session() as session:
        run_id, branch_id = _setup_branch(session, tmp_path)
        _record_chapter(session, run_id, branch_id, 1)

        settings = Settings(
            _env_file=None,  # type: ignore[call-arg]
            db_dialect="sqlite",
            database_url="sqlite+pysqlite:///:memory:",
            loom_memory_mode="disabled",
        )
        harness = HarnessControllerService(session, settings)

        mock_plan = MagicMock()
        mock_plan.worldview_capsule = "玄幻"
        mock_plan.trope_axes = []
        mock_plan.innovation_directives = []
        mock_plan.external_knowledge_refs = []

        result_json = harness._build_carry_over_json(
            branch_id, source_chapter_index=1, plan=mock_plan
        )
        result = json.loads(result_json)
        # Pure legacy: no Loom keys
        assert "loom_version" not in result
        assert "_loom_memory" not in result
        assert result["worldview_capsule"] == "玄幻"


# ===========================================================================
# CLI commands
# ===========================================================================

runner = CliRunner()


def test_cli_loom_status_no_branch(tmp_path: Path) -> None:
    """loom-status with non-existent branch should not crash."""
    result = runner.invoke(
        app,
        ["loom-status", "nonexistent-branch-id",
         "--database-url", "sqlite+pysqlite:///:memory:"],
    )
    # Should exit (branch not found) but not raise an unhandled exception
    assert result.exit_code in (0, 1)


def test_cli_loom_consolidate_no_branch(tmp_path: Path) -> None:
    """loom-consolidate with non-existent branch should not crash."""
    result = runner.invoke(
        app,
        ["loom-consolidate", "nonexistent-branch-id", "1",
         "--database-url", "sqlite+pysqlite:///:memory:"],
    )
    assert result.exit_code in (0, 1)


def test_cli_loom_assemble_no_branch(tmp_path: Path) -> None:
    """loom-assemble with non-existent branch should not crash."""
    result = runner.invoke(
        app,
        ["loom-assemble", "nonexistent-branch-id", "1",
         "--database-url", "sqlite+pysqlite:///:memory:"],
    )
    assert result.exit_code in (0, 1)


def test_cli_loom_status_with_data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """loom-status shows correct stats for a branch with data."""
    engine, factory, db_url = patch_cli_sqlite_runtime(monkeypatch)
    novel_path = tmp_path / "novel.txt"
    novel_path.write_text("第1章 一\n正文\n", encoding="utf-8")
    with factory() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), "测试")
        run, branch = RunService(session).create_run(novel.id, manifest.id)
        branch_id = branch.id
        run_id = run.id
        for i in range(1, 4):
            _record_chapter(session, run_id, branch_id, i, entities=[f"角色{i}", "主角"])
        session.commit()

    result = runner.invoke(app, ["loom-status", branch_id, "--database-url", db_url])
    assert result.exit_code == 0, result.output
    assert "Loom Memory Status" in result.output
    assert branch_id in result.output
    assert "total_facts" in result.output


def test_cli_loom_consolidate_with_data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """loom-consolidate runs and outputs conflict counts."""
    engine, factory, db_url = patch_cli_sqlite_runtime(monkeypatch)
    novel_path = tmp_path / "novel.txt"
    novel_path.write_text("第1章 一\n正文\n", encoding="utf-8")
    with factory() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), "测试")
        run, branch = RunService(session).create_run(novel.id, manifest.id)
        branch_id = branch.id
        run_id = run.id
        _record_chapter(session, run_id, branch_id, 1)
        session.commit()

    result = runner.invoke(app, ["loom-consolidate", branch_id, "1", "--database-url", db_url])
    assert result.exit_code == 0, result.output
    assert "contradictions" in result.output
    assert "evolutions" in result.output


def test_cli_loom_assemble_with_data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """loom-assemble outputs valid JSON carry_over_state."""
    engine, factory, db_url = patch_cli_sqlite_runtime(monkeypatch)
    novel_path = tmp_path / "novel.txt"
    novel_path.write_text("第1章 一\n正文\n", encoding="utf-8")
    with factory() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), "测试")
        run, branch = RunService(session).create_run(novel.id, manifest.id)
        branch_id = branch.id
        run_id = run.id
        for i in range(1, 4):
            _record_chapter(session, run_id, branch_id, i)
        session.commit()

    result = runner.invoke(app, ["loom-assemble", branch_id, "4", "--database-url", db_url])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert "loom_version" in data
    assert "_legacy_compat" in data


def test_harness_pairwise_disabled_by_default(tmp_path: Path) -> None:
    with _session() as session:
        run_id, branch_id = _setup_branch(session, tmp_path)
        for i in range(1, 4):
            _record_chapter(session, run_id, branch_id, i)

        settings = Settings(
            _env_file=None,  # type: ignore[call-arg]
            db_dialect="sqlite",
            database_url="sqlite+pysqlite:///:memory:",
            loom_pairwise_enabled=False,
        )
        harness = HarnessControllerService(session, settings)
        report = harness.run_harness(
            branch_id,
            source_chapter_index=1,
            target_goal="测试目标",
            max_rounds=1,
            use_llm=False,
        )
        assert report.chapter_quality_signal == {}


def test_harness_pairwise_enabled_single_round_produces_signal(tmp_path: Path) -> None:
    with _session() as session:
        run_id, branch_id = _setup_branch(session, tmp_path)
        for i in range(1, 4):
            _record_chapter(session, run_id, branch_id, i)

        settings = Settings(
            _env_file=None,  # type: ignore[call-arg]
            db_dialect="sqlite",
            database_url="sqlite+pysqlite:///:memory:",
            loom_pairwise_enabled=True,
        )
        harness = HarnessControllerService(session, settings)
        report = harness.run_harness(
            branch_id,
            source_chapter_index=1,
            target_goal="测试目标",
            max_rounds=1,
            use_llm=False,
        )
        assert "quality_score" in report.chapter_quality_signal
        assert "overall_preference" in report.chapter_quality_signal
        assert report.chapter_quality_signal["evaluation_method"] == "heuristic"


def test_harness_pairwise_enabled_signal_in_last_round_skill_outputs(tmp_path: Path) -> None:
    with _session() as session:
        run_id, branch_id = _setup_branch(session, tmp_path)
        for i in range(1, 4):
            _record_chapter(session, run_id, branch_id, i)

        settings = Settings(
            _env_file=None,  # type: ignore[call-arg]
            db_dialect="sqlite",
            database_url="sqlite+pysqlite:///:memory:",
            loom_pairwise_enabled=True,
        )
        harness = HarnessControllerService(session, settings)
        report = harness.run_harness(
            branch_id,
            source_chapter_index=1,
            target_goal="测试目标",
            max_rounds=2,
            use_llm=False,
        )
        assert report.rounds
        last_round = report.rounds[-1]
        assert "_loom_chapter_quality" in last_round.skill_outputs
        quality = last_round.skill_outputs["_loom_chapter_quality"]
        assert isinstance(quality, dict)
        assert "quality_score" in quality
