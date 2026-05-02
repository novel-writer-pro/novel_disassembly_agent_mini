from pathlib import Path

from _pytest.monkeypatch import MonkeyPatch
from typer.testing import CliRunner

from novel_analyzer.cli.app import app
from tests.cli_test_support import patch_cli_sqlite_runtime

runner = CliRunner()


def test_cli_inspect_novel(tmp_path: Path) -> None:
    novel_path = tmp_path / "novel.txt"
    novel_path.write_text("第1章 一\n第1章 一\n正文\n第2章 二\n正文\n", encoding="utf-8")

    result = runner.invoke(app, ["inspect-novel", str(novel_path)])
    assert result.exit_code == 0
    assert "raw_heading_count=3" in result.stdout
    assert "normalized_chapter_count=2" in result.stdout


def test_cli_ingest_and_start_run(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    novel_path = tmp_path / "novel.txt"
    novel_path.write_text("第1章 一\n正文\n第2章 二\n正文\n", encoding="utf-8")

    _engine, _factory, db_url = patch_cli_sqlite_runtime(monkeypatch)
    init = runner.invoke(app, ["init-db", "--database-url", db_url])
    assert init.exit_code == 0

    ingest = runner.invoke(app, ["ingest", str(novel_path), "--database-url", db_url])
    assert ingest.exit_code == 0
    lines = dict(line.split("=", 1) for line in ingest.stdout.strip().splitlines())

    start = runner.invoke(
        app,
        ["start-run", lines["novel_id"], lines["manifest_id"], "--database-url", db_url],
    )
    assert start.exit_code == 0
    assert "run_id=" in start.stdout
    assert "branch_id=" in start.stdout


def test_cli_plan_next_chapter_and_imitate_chapter(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    from novel_analyzer.database.models import (
        AnalysisRun,
        ChapterArtifact,
        ChapterManifest,
        ChapterSegment,
        FactRecord,
        NovelSource,
        RunBranch,
    )
    from sqlalchemy.orm import Session

    _engine, factory, db_url = patch_cli_sqlite_runtime(monkeypatch)
    init = runner.invoke(app, ["init-db", "--database-url", db_url])
    assert init.exit_code == 0

    source_path = tmp_path / "novel.txt"
    text = (
        "第1章 大器晚成\n卫图觉醒命格并决定寻找养生功。\n"
        "第2章 二姑卫荭\n卫图拜访二姑，为资源铺垫。\n"
        "第3章 养生功法\n卫图求得龟息养气功并开始修炼。\n"
    )
    source_path.write_text(text, encoding="utf-8")

    with factory() as session:
        session = Session(bind=session.bind, future=True)
        novel = NovelSource(
            id="novel-cli-1",
            title="示例小说",
            source_path=str(source_path),
            source_hash="hash",
            metadata_json={},
        )
        manifest = ChapterManifest(
            id="manifest-cli-1",
            novel_id=novel.id,
            version=1,
            splitter_version="heuristic-v1",
            chapter_count=3,
            notes={},
        )
        run = AnalysisRun(
            id="run-cli-1",
            novel_id=novel.id,
            manifest_id=manifest.id,
            llm_base_url="https://example.invalid/v1",
            llm_model_name="gpt-5.4-mini",
            analysis_profile={},
            active_branch_id="branch-cli-1",
        )
        branch = RunBranch(
            id="branch-cli-1",
            run_id=run.id,
            name="main",
            parent_branch_id=None,
            fork_after_chapter_index=0,
            status="active",
        )
        session.add_all([novel, manifest, run, branch])
        session.flush()
        session.add_all(
            [
                ChapterSegment(
                    manifest_id=manifest.id,
                    chapter_index=1,
                    raw_heading="第1章 大器晚成",
                    normalized_chapter_no=1,
                    normalized_title="大器晚成",
                    start_offset=0,
                    end_offset=text.index("第2章"),
                    content_hash="c1",
                ),
                ChapterSegment(
                    manifest_id=manifest.id,
                    chapter_index=2,
                    raw_heading="第2章 二姑卫荭",
                    normalized_chapter_no=2,
                    normalized_title="二姑卫荭",
                    start_offset=text.index("第2章"),
                    end_offset=text.index("第3章"),
                    content_hash="c2",
                ),
                ChapterSegment(
                    manifest_id=manifest.id,
                    chapter_index=3,
                    raw_heading="第3章 养生功法",
                    normalized_chapter_no=3,
                    normalized_title="养生功法",
                    start_offset=text.index("第3章"),
                    end_offset=len(text),
                    content_hash="c3",
                ),
                ChapterArtifact(
                    branch_id=branch.id,
                    chapter_index=1,
                    artifact_type="chapter_analysis",
                    payload_json={
                        "chapter_summary": "卫图觉醒命格并决定寻找养生功。",
                        "continuity_notes": ["开篇建立命格与求生主线。"],
                    },
                    status="validated",
                    visibility="active",
                    source_kind="analysis",
                    participates_in_downstream=True,
                    inherited_from_branch_id=None,
                    is_inherited=False,
                ),
                ChapterArtifact(
                    branch_id=branch.id,
                    chapter_index=2,
                    artifact_type="chapter_analysis",
                    payload_json={
                        "chapter_summary": "卫图拜访二姑，为资源铺垫。",
                        "continuity_notes": ["求助受阻，关系推进要有中间证据。"],
                    },
                    status="validated",
                    visibility="active",
                    source_kind="analysis",
                    participates_in_downstream=True,
                    inherited_from_branch_id=None,
                    is_inherited=False,
                ),
                FactRecord(
                    branch_id=branch.id,
                    chapter_index=1,
                    fact_type="entity",
                    label="卫图",
                    evidence_list=["卫图觉醒命格"],
                    confidence=0.9,
                ),
            ]
        )
        session.commit()

    plan_result = runner.invoke(
        app,
        [
            "plan-next-chapter",
            "branch-cli-1",
            "推进卫图获取养生功的机会",
            "--emphasis",
            "主线推进,资源获取",
            "--forbidden-move",
            "不要让卫图直接获得超出铺垫的力量",
            "--database-url",
            db_url,
        ],
    )
    assert plan_result.exit_code == 0
    assert '"chapter_goal"' in plan_result.stdout
    assert '"scene_plan"' in plan_result.stdout

    imitate_result = runner.invoke(
        app,
        [
            "imitate-chapter",
            "branch-cli-1",
            "3",
            "延续主角获得功法后的行动线，并保持克制成长节奏",
            "--database-url",
            db_url,
        ],
    )
    assert imitate_result.exit_code == 0
    assert '"draft_text"' in imitate_result.stdout
    assert '"comparison_notes"' in imitate_result.stdout

    compare_result = runner.invoke(
        app,
        [
            "compare-imitation",
            "branch-cli-1",
            "3",
            "延续主角获得功法后的行动线，并保持克制成长节奏",
            "--database-url",
            db_url,
        ],
    )
    assert compare_result.exit_code == 0
    assert '"comparison"' in compare_result.stdout
    assert '"overall_verdict"' in compare_result.stdout

    review_result = runner.invoke(
        app,
        [
            "review-imitation",
            "branch-cli-1",
            "3",
            "延续主角获得功法后的行动线，并保持克制成长节奏",
            "--database-url",
            db_url,
        ],
    )
    assert review_result.exit_code == 0
    assert '"review"' in review_result.stdout
    assert '"gate"' in review_result.stdout
    assert '"risk"' in review_result.stdout
    assert '"revised_draft"' in review_result.stdout

    iterate_result = runner.invoke(
        app,
        [
            "iterate-imitation",
            "branch-cli-1",
            "3",
            "延续主角获得功法后的行动线，并保持克制成长节奏",
            "--max-rounds",
            "2",
            "--database-url",
            db_url,
        ],
    )
    assert iterate_result.exit_code == 0
    assert '"rounds"' in iterate_result.stdout
    assert '"overall_score"' in iterate_result.stdout
    assert '"final_draft"' in iterate_result.stdout

    multi_result = runner.invoke(
        app,
        [
            "multi-chapter-imitation-consistency",
            "branch-cli-1",
            "2:延续资源铺垫",
            "3:延续主角获得功法后的行动线，并保持克制成长节奏",
            "--max-rounds",
            "1",
            "--database-url",
            db_url,
        ],
    )
    assert multi_result.exit_code == 0
    assert '"steps"' in multi_result.stdout
    assert '"overall_verdict"' in multi_result.stdout

    whole_result = runner.invoke(
        app,
        [
            "plan-whole-book-imitation",
            "branch-cli-1",
            "测试项目",
            "示例小说",
            "新世界版示例小说",
            "2:延续资源铺垫",
            "3:延续主角获得功法后的行动线",
            "--world-map",
            "郑国=星际联邦",
            "--character-map",
            "卫图=魏拓",
            "--database-url",
            db_url,
        ],
    )
    assert whole_result.exit_code == 0
    assert '"mapping_pack"' in whole_result.stdout
    assert '"chapter_goals"' in whole_result.stdout

    run_result = runner.invoke(
        app,
        [
            "run-whole-book-imitation",
            "branch-cli-1",
            "测试项目",
            "示例小说",
            "新世界版示例小说",
            "2:延续资源铺垫",
            "3:延续主角获得功法后的行动线",
            "--world-map",
            "郑国=星际联邦",
            "--character-map",
            "卫图=魏拓",
            "--database-url",
            db_url,
        ],
    )
    assert run_result.exit_code == 0
    assert '"queue"' in run_result.stdout
    assert '"expected_outputs"' in run_result.stdout
    assert '"carry_over_inputs"' in run_result.stdout

    sandbox_result = runner.invoke(
        app,
        [
            "run-whole-book-imitation",
            "branch-cli-1",
            "测试项目",
            "示例小说",
            "新世界版示例小说",
            "2:延续资源铺垫",
            "3:延续主角获得功法后的行动线",
            "--world-map",
            "郑国=星际联邦",
            "--character-map",
            "卫图=魏拓",
            "--execute",
            "--max-rounds",
            "1",
            "--database-url",
            db_url,
        ],
    )
    assert sandbox_result.exit_code == 0
    assert '"execution_mode": "sandbox_execute"' in sandbox_result.stdout
    assert '"executed_steps"' in sandbox_result.stdout
    assert '"final_carry_over_state"' in sandbox_result.stdout
