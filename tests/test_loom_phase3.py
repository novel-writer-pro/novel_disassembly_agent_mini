from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from novel_analyzer.cli.app import app

runner = CliRunner()

_LONG_TEXT_A = "这是第一轮草案的正文内容，用于测试。" * 10
_LONG_TEXT_B = "这是最终草案的正文内容，经过修改。" * 10
_LONG_TEXT_C = "这是对照目录的最终草案内容。" * 10


def _make_artifact(
    tmp_dir: Path,
    chapter_index: int,
    *,
    branch_id: str = "test-branch",
    target_goal: str = "测试目标",
    round0_text: str = _LONG_TEXT_A,
    final_text: str = _LONG_TEXT_B,
    num_rounds: int = 2,
) -> Path:
    rounds = []
    for i in range(num_rounds):
        text = round0_text if i == 0 else final_text
        rounds.append({
            "round_index": i + 1,
            "draft": {"draft_text": text, "draft_title": f"草案{i+1}", "source_chapter_index": chapter_index, "original_title": "原章", "method_notes": [], "comparison_notes": [], "risk_gate_notes": []},
            "skill_outputs": {},
        })
    payload = {
        "source_chapter_index": chapter_index,
        "branch_id": branch_id,
        "target_goal": target_goal,
        "rounds": rounds,
        "final_draft": {
            "draft_text": final_text,
            "draft_title": "最终草案",
            "source_chapter_index": chapter_index,
            "original_title": "原章",
            "method_notes": [],
            "comparison_notes": [],
            "risk_gate_notes": [],
        },
        "final_verdict": "pass",
    }
    path = tmp_dir / f"writer-imitate-ch{chapter_index}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def test_collect_pairs_empty_dir(tmp_path: Path) -> None:
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    pairs_file = tmp_path / "pairs.jsonl"
    result = runner.invoke(app, [
        "loom-collect-pairs",
        "--output-dir", str(output_dir),
        "--pairs-file", str(pairs_file),
    ])
    assert result.exit_code == 0
    assert "no eligible pairs found" in result.output
    assert not pairs_file.exists()


def test_collect_pairs_single_round_skipped(tmp_path: Path) -> None:
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    _make_artifact(output_dir, 1, num_rounds=1)
    pairs_file = tmp_path / "pairs.jsonl"
    result = runner.invoke(app, [
        "loom-collect-pairs",
        "--output-dir", str(output_dir),
        "--pairs-file", str(pairs_file),
    ])
    assert result.exit_code == 0
    assert "no eligible pairs found" in result.output


def test_collect_pairs_single_dir_two_rounds(tmp_path: Path) -> None:
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    _make_artifact(output_dir, 1, num_rounds=2)
    pairs_file = tmp_path / "pairs.jsonl"
    result = runner.invoke(app, [
        "loom-collect-pairs",
        "--output-dir", str(output_dir),
        "--pairs-file", str(pairs_file),
    ])
    assert result.exit_code == 0, result.output
    assert "collected 1 pair" in result.output
    assert pairs_file.exists()
    lines = pairs_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["chapter_index"] == 1
    assert record["pair_source"] == "single_dir_rounds"
    assert "quality_score" in record
    assert "overall_preference" in record
    assert "pair_id" in record
    assert "collected_at" in record
    assert record["loom_collect_version"] == "1.0"


def test_collect_pairs_multiple_chapters(tmp_path: Path) -> None:
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    for ch in [1, 2, 3]:
        _make_artifact(output_dir, ch, num_rounds=2)
    pairs_file = tmp_path / "pairs.jsonl"
    result = runner.invoke(app, [
        "loom-collect-pairs",
        "--output-dir", str(output_dir),
        "--pairs-file", str(pairs_file),
    ])
    assert result.exit_code == 0, result.output
    assert "collected 3 pair" in result.output
    lines = pairs_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 3
    chapter_indices = sorted(json.loads(l)["chapter_index"] for l in lines)
    assert chapter_indices == [1, 2, 3]


def test_collect_pairs_cross_dir(tmp_path: Path) -> None:
    baseline_dir = tmp_path / "baseline"
    steering_dir = tmp_path / "steering"
    baseline_dir.mkdir()
    steering_dir.mkdir()
    _make_artifact(baseline_dir, 1, final_text=_LONG_TEXT_A)
    _make_artifact(steering_dir, 1, final_text=_LONG_TEXT_C)
    pairs_file = tmp_path / "pairs.jsonl"
    result = runner.invoke(app, [
        "loom-collect-pairs",
        "--output-dir", str(baseline_dir),
        "--compare-dir", str(steering_dir),
        "--pairs-file", str(pairs_file),
    ])
    assert result.exit_code == 0, result.output
    assert "collected 1 pair" in result.output
    assert "cross_dir" in result.output
    lines = pairs_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["pair_source"] == "cross_dir"
    assert record["chapter_index"] == 1


def test_collect_pairs_cross_dir_no_overlap(tmp_path: Path) -> None:
    baseline_dir = tmp_path / "baseline"
    steering_dir = tmp_path / "steering"
    baseline_dir.mkdir()
    steering_dir.mkdir()
    _make_artifact(baseline_dir, 1)
    _make_artifact(steering_dir, 2)
    pairs_file = tmp_path / "pairs.jsonl"
    result = runner.invoke(app, [
        "loom-collect-pairs",
        "--output-dir", str(baseline_dir),
        "--compare-dir", str(steering_dir),
        "--pairs-file", str(pairs_file),
    ])
    assert result.exit_code == 0
    assert "no eligible pairs found" in result.output


def test_collect_pairs_min_draft_length_filter(tmp_path: Path) -> None:
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    _make_artifact(output_dir, 1, round0_text="短文本", final_text="也很短", num_rounds=2)
    pairs_file = tmp_path / "pairs.jsonl"
    result = runner.invoke(app, [
        "loom-collect-pairs",
        "--output-dir", str(output_dir),
        "--pairs-file", str(pairs_file),
        "--min-draft-length", "50",
    ])
    assert result.exit_code == 0
    assert "no eligible pairs found" in result.output


def test_collect_pairs_appends_to_existing(tmp_path: Path) -> None:
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    _make_artifact(output_dir, 1, num_rounds=2)
    pairs_file = tmp_path / "pairs.jsonl"
    for _ in range(2):
        result = runner.invoke(app, [
            "loom-collect-pairs",
            "--output-dir", str(output_dir),
            "--pairs-file", str(pairs_file),
        ])
        assert result.exit_code == 0, result.output
    lines = pairs_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert "total_pairs_in_file=2" in result.output


def test_collect_pairs_identical_drafts_skipped(tmp_path: Path) -> None:
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    _make_artifact(output_dir, 1, round0_text=_LONG_TEXT_A, final_text=_LONG_TEXT_A, num_rounds=2)
    pairs_file = tmp_path / "pairs.jsonl"
    result = runner.invoke(app, [
        "loom-collect-pairs",
        "--output-dir", str(output_dir),
        "--pairs-file", str(pairs_file),
    ])
    assert result.exit_code == 0
    assert "no eligible pairs found" in result.output


def test_pairs_stats_no_file(tmp_path: Path) -> None:
    pairs_file = tmp_path / "nonexistent.jsonl"
    result = runner.invoke(app, ["loom-pairs-stats", "--pairs-file", str(pairs_file)])
    assert result.exit_code == 0
    assert "total_pairs=0" in result.output
    assert "target=500" in result.output
    assert "progress=0.0%" in result.output


def test_pairs_stats_with_data(tmp_path: Path) -> None:
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    for ch in [1, 2, 3]:
        _make_artifact(output_dir, ch, num_rounds=2)
    pairs_file = tmp_path / "pairs.jsonl"
    collect_result = runner.invoke(app, [
        "loom-collect-pairs",
        "--output-dir", str(output_dir),
        "--pairs-file", str(pairs_file),
    ])
    assert collect_result.exit_code == 0

    result = runner.invoke(app, ["loom-pairs-stats", "--pairs-file", str(pairs_file)])
    assert result.exit_code == 0, result.output
    assert "total_pairs:       3" in result.output
    assert "target:            500" in result.output
    assert "unique_chapters:   3" in result.output
    assert "remaining_to_target: 497" in result.output
    assert "single_dir_rounds" in result.output
    assert "heuristic" in result.output


def test_pairs_stats_progress_percentage(tmp_path: Path) -> None:
    pairs_file = tmp_path / "pairs.jsonl"
    record = {
        "chapter_index": 1,
        "branch_id": "b",
        "quality_score": 0.75,
        "confidence": 0.8,
        "overall_preference": "B",
        "dimensions": {},
        "evaluation_method": "heuristic",
        "loom_version": "1.0",
        "pair_id": "abc",
        "pair_source": "single_dir_rounds",
        "dir_a": "output",
        "dir_b": "output",
        "chapter_goal": "目标",
        "collected_at": "2026-05-10T00:00:00+00:00",
        "loom_collect_version": "1.0",
    }
    pairs_file.write_text(json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8")
    result = runner.invoke(app, ["loom-pairs-stats", "--pairs-file", str(pairs_file)])
    assert result.exit_code == 0
    assert "total_pairs:       1" in result.output
    assert "progress:          0.2%" in result.output
    assert "avg_quality_score: 0.75" in result.output


def _make_ab_artifact(
    tmp_dir: Path,
    chapter_index: int,
    *,
    branch_id: str = "test-branch",
    target_goal: str = "测试目标",
    final_text: str = _LONG_TEXT_B,
    ooc_triggered: bool = False,
    risk_level: str = "low",
    final_verdict: str = "pass",
) -> Path:
    checker_statuses = {"character_ooc": "warn"} if ooc_triggered else {"character_ooc": "pass"}
    top_risk_types = ["character_ooc"] if ooc_triggered else []
    rounds = [
        {
            "round_index": 1,
            "draft": {
                "draft_text": final_text,
                "draft_title": "草案1",
                "source_chapter_index": chapter_index,
                "original_title": "原章",
                "method_notes": [],
                "comparison_notes": [],
                "risk_gate_notes": [],
            },
            "risk": {
                "source_chapter_index": chapter_index,
                "draft_title": "草案1",
                "overall_risk_level": risk_level,
                "checker_statuses": checker_statuses,
                "top_risk_types": top_risk_types,
                "top_risk_summaries": [],
                "coverage_gaps": [],
            },
            "skill_outputs": {},
        }
    ]
    payload = {
        "source_chapter_index": chapter_index,
        "branch_id": branch_id,
        "target_goal": target_goal,
        "rounds": rounds,
        "final_draft": {
            "draft_text": final_text,
            "draft_title": "最终草案",
            "source_chapter_index": chapter_index,
            "original_title": "原章",
            "method_notes": [],
            "comparison_notes": [],
            "risk_gate_notes": [],
        },
        "final_verdict": final_verdict,
        "policy_summary": {
            "risk_overall_level": risk_level,
            "gate_verdict": "aligned",
            "overall_score": 80,
        },
    }
    path = tmp_dir / f"writer-imitate-ch{chapter_index}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def test_ab_compare_no_overlap(tmp_path: Path) -> None:
    baseline_dir = tmp_path / "baseline"
    loom_dir = tmp_path / "loom"
    baseline_dir.mkdir()
    loom_dir.mkdir()
    _make_ab_artifact(baseline_dir, 1)
    _make_ab_artifact(loom_dir, 2)
    result = runner.invoke(app, ["loom-ab-compare", str(baseline_dir), str(loom_dir)])
    assert result.exit_code == 1
    assert "no matching chapters" in result.output


def test_ab_compare_loom_reduces_ooc(tmp_path: Path) -> None:
    baseline_dir = tmp_path / "baseline"
    loom_dir = tmp_path / "loom"
    baseline_dir.mkdir()
    loom_dir.mkdir()
    for ch in [1, 2, 3, 4, 5]:
        _make_ab_artifact(baseline_dir, ch, ooc_triggered=True, risk_level="medium")
    for ch in [1, 2, 3, 4, 5]:
        ooc = ch in [1]
        _make_ab_artifact(loom_dir, ch, ooc_triggered=ooc, risk_level="low" if not ooc else "medium")
    result = runner.invoke(app, ["loom-ab-compare", str(baseline_dir), str(loom_dir)])
    assert result.exit_code == 0, result.output
    assert "total_chapters:      5" in result.output
    assert "baseline:" in result.output
    assert "loom:" in result.output
    assert "reduction:" in result.output
    assert "MET" in result.output


def test_ab_compare_loom_no_improvement(tmp_path: Path) -> None:
    baseline_dir = tmp_path / "baseline"
    loom_dir = tmp_path / "loom"
    baseline_dir.mkdir()
    loom_dir.mkdir()
    for ch in [1, 2, 3]:
        _make_ab_artifact(baseline_dir, ch, ooc_triggered=True)
        _make_ab_artifact(loom_dir, ch, ooc_triggered=True)
    result = runner.invoke(app, ["loom-ab-compare", str(baseline_dir), str(loom_dir)])
    assert result.exit_code == 0, result.output
    assert "NOT MET" in result.output
    assert "0.0%" in result.output


def test_ab_compare_output_file(tmp_path: Path) -> None:
    baseline_dir = tmp_path / "baseline"
    loom_dir = tmp_path / "loom"
    baseline_dir.mkdir()
    loom_dir.mkdir()
    _make_ab_artifact(baseline_dir, 1, ooc_triggered=True)
    _make_ab_artifact(loom_dir, 1, ooc_triggered=False)
    output_file = tmp_path / "report.json"
    result = runner.invoke(app, [
        "loom-ab-compare", str(baseline_dir), str(loom_dir),
        "--output-file", str(output_file),
    ])
    assert result.exit_code == 0, result.output
    assert output_file.exists()
    report = json.loads(output_file.read_text(encoding="utf-8"))
    assert report["contract_version"] == "loom-ab-compare.v1"
    assert report["total_chapters"] == 1
    assert report["baseline_ooc_count"] == 1
    assert report["loom_ooc_count"] == 0
    assert report["target_met"] is True
    assert len(report["improved_chapters"]) == 1
    assert len(report["regressed_chapters"]) == 0


def test_ab_compare_no_ooc_in_either(tmp_path: Path) -> None:
    baseline_dir = tmp_path / "baseline"
    loom_dir = tmp_path / "loom"
    baseline_dir.mkdir()
    loom_dir.mkdir()
    for ch in [1, 2]:
        _make_ab_artifact(baseline_dir, ch, ooc_triggered=False)
        _make_ab_artifact(loom_dir, ch, ooc_triggered=False)
    result = runner.invoke(app, ["loom-ab-compare", str(baseline_dir), str(loom_dir)])
    assert result.exit_code == 0, result.output
    assert "0/2 (0.0%)" in result.output


def test_collect_pairs_from_db_no_overlap(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.cli_test_support import patch_cli_sqlite_runtime
    from novel_analyzer.services.ingest_service import IngestService
    from novel_analyzer.services.run_service import RunService

    engine, factory, db_url = patch_cli_sqlite_runtime(monkeypatch)
    novel_path = tmp_path / "novel.txt"
    novel_path.write_text("第1章 一\n正文\n第2章 二\n正文2\n", encoding="utf-8")
    with factory() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), "测试")
        run, branch_a = RunService(session).create_run(novel.id, manifest.id)
        run2, branch_b = RunService(session).create_run(novel.id, manifest.id)
        branch_a_id = branch_a.id
        branch_b_id = branch_b.id
        RunService(session).record_chapter_artifact(branch_a_id, 1, {"chapter_summary": "摘要A章1", "normalized_title": "第1章"})
        RunService(session).record_chapter_artifact(branch_b_id, 2, {"chapter_summary": "摘要B章2", "normalized_title": "第2章"})
        session.commit()

    pairs_file = tmp_path / "pairs.jsonl"
    result = runner.invoke(app, [
        "loom-collect-pairs-from-db", branch_a_id, branch_b_id,
        "--pairs-file", str(pairs_file),
        "--database-url", db_url,
    ])
    assert result.exit_code == 0
    assert "no matching chapters" in result.output


def test_collect_pairs_from_db_matching_chapters(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.cli_test_support import patch_cli_sqlite_runtime
    from novel_analyzer.services.ingest_service import IngestService
    from novel_analyzer.services.run_service import RunService

    engine, factory, db_url = patch_cli_sqlite_runtime(monkeypatch)
    novel_path = tmp_path / "novel.txt"
    novel_path.write_text("第1章 一\n正文\n第2章 二\n正文2\n", encoding="utf-8")
    with factory() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), "测试")
        run, branch_a = RunService(session).create_run(novel.id, manifest.id)
        run2, branch_b = RunService(session).create_run(novel.id, manifest.id)
        branch_a_id = branch_a.id
        branch_b_id = branch_b.id
        for ch in [1, 2]:
            RunService(session).record_chapter_artifact(
                branch_a_id, ch,
                {"chapter_summary": f"分支A第{ch}章摘要内容，用于测试对比。", "normalized_title": f"第{ch}章", "key_events": [f"事件{ch}A"]},
            )
            RunService(session).record_chapter_artifact(
                branch_b_id, ch,
                {"chapter_summary": f"分支B第{ch}章摘要内容，与A不同。", "normalized_title": f"第{ch}章", "key_events": [f"事件{ch}B"]},
            )
        session.commit()

    pairs_file = tmp_path / "pairs.jsonl"
    result = runner.invoke(app, [
        "loom-collect-pairs-from-db", branch_a_id, branch_b_id,
        "--pairs-file", str(pairs_file),
        "--database-url", db_url,
    ])
    assert result.exit_code == 0, result.output
    assert "collected 2 pair" in result.output
    assert pairs_file.exists()
    lines = pairs_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    record = json.loads(lines[0])
    assert record["pair_source"] == "db_branch_compare"
    assert "quality_score" in record
    assert record["loom_collect_version"] == "1.0"


def test_collect_pairs_from_db_identical_summaries_skipped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.cli_test_support import patch_cli_sqlite_runtime
    from novel_analyzer.services.ingest_service import IngestService
    from novel_analyzer.services.run_service import RunService

    engine, factory, db_url = patch_cli_sqlite_runtime(monkeypatch)
    novel_path = tmp_path / "novel.txt"
    novel_path.write_text("第1章 一\n正文\n", encoding="utf-8")
    with factory() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), "测试")
        run, branch_a = RunService(session).create_run(novel.id, manifest.id)
        run2, branch_b = RunService(session).create_run(novel.id, manifest.id)
        branch_a_id = branch_a.id
        branch_b_id = branch_b.id
        same_summary = "完全相同的摘要内容，两个分支一模一样。"
        RunService(session).record_chapter_artifact(branch_a_id, 1, {"chapter_summary": same_summary, "normalized_title": "第1章"})
        RunService(session).record_chapter_artifact(branch_b_id, 1, {"chapter_summary": same_summary, "normalized_title": "第1章"})
        session.commit()

    pairs_file = tmp_path / "pairs.jsonl"
    result = runner.invoke(app, [
        "loom-collect-pairs-from-db", branch_a_id, branch_b_id,
        "--pairs-file", str(pairs_file),
        "--database-url", db_url,
    ])
    assert result.exit_code == 0
    assert "no eligible pairs found" in result.output
