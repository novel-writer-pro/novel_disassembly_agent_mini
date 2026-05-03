from pathlib import Path
import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from novel_analyzer.database.models import (
    AnalysisRun,
    ChapterArtifact,
    ChapterManifest,
    ChapterSegment,
    FactRecord,
    NovelSource,
    RunBranch,
)
from novel_analyzer.database.session import create_schema
from novel_analyzer.domain.schemas import StoryMappingPack
from novel_analyzer.services.whole_book_imitation_service import WholeBookImitationService


def _seed_branch(session, source_path: Path) -> str:
    text = (
        "第1章 大器晚成\n卫图觉醒命格并决定寻找养生功。\n"
        "第2章 二姑卫荭\n卫图拜访二姑，为资源铺垫。\n"
        "第3章 养生功法\n卫图求得龟息养气功并开始修炼。\n"
    )
    source_path.write_text(text, encoding="utf-8")

    novel = NovelSource(
        id="novel-whole-1",
        title="示例小说",
        source_path=str(source_path),
        source_hash="hash",
        metadata_json={},
    )
    manifest = ChapterManifest(
        id="manifest-whole-1",
        novel_id=novel.id,
        version=1,
        splitter_version="heuristic-v1",
        chapter_count=3,
        notes={},
    )
    run = AnalysisRun(
        id="run-whole-1",
        novel_id=novel.id,
        manifest_id=manifest.id,
        llm_base_url="https://example.invalid/v1",
        llm_model_name="gpt-5.4-mini",
        analysis_profile={},
        active_branch_id="branch-whole-1",
    )
    branch = RunBranch(
        id="branch-whole-1",
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
                payload_json={"chapter_summary": "卫图觉醒命格并决定寻找养生功。"},
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
    return branch.id


def test_whole_book_imitation_service_builds_plan(tmp_path: Path) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    create_schema(engine)
    factory = sessionmaker(bind=engine, future=True)
    with factory() as session:
        branch_id = _seed_branch(session, tmp_path / "sample.txt")
        service = WholeBookImitationService(session)
        pack = StoryMappingPack(
            project_title="测试项目",
            source_work_name="示例小说",
            target_work_name="新世界版示例小说",
            world_mapping={"郑国": "星际联邦"},
            character_mapping={"卫图": "魏拓"},
        )
        plan = service.build_plan(
            branch_id,
            mapping_pack=pack,
            chapter_goals=[
                (2, "延续资源铺垫"),
                (3, "延续主角获得功法后的行动线"),
            ],
        )
        assert plan.project_title == "测试项目"
        assert plan.source_chapter_range == [2, 3]
        assert plan.continuity_focus


def test_whole_book_imitation_service_builds_run_queue(tmp_path: Path) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    create_schema(engine)
    factory = sessionmaker(bind=engine, future=True)
    with factory() as session:
        branch_id = _seed_branch(session, tmp_path / "sample.txt")
        service = WholeBookImitationService(session)
        pack = StoryMappingPack(
            project_title="测试项目",
            source_work_name="示例小说",
            target_work_name="新世界版示例小说",
            world_mapping={"郑国": "星际联邦"},
            character_mapping={"卫图": "魏拓"},
        )
        report = service.build_run_queue(
            branch_id,
            mapping_pack=pack,
            chapter_goals=[
                (2, "延续资源铺垫"),
                (3, "延续主角获得功法后的行动线"),
            ],
        )
        assert report.queue
        assert report.queue[0].expected_outputs
        assert report.queue[1].carry_over_inputs
        assert report.queue[1].scheduling_priority <= report.queue[0].scheduling_priority
        assert report.queue[1].scheduling_reason
        assert report.policy_summary["queue_length"] == 2
        assert report.contract_version == "whole-book-imitation.v1"
        assert report.stable_contract_version == "whole-book-imitation-pre-v1"
        assert "priority_reason_histogram" in report.policy_summary
        assert "queue_priority_preview" in report.dashboard_summary
        assert "top_queue_priority_chapters" in report.dashboard_summary
        assert "queue_next_actions" in report.dashboard_summary
        assert report.run_notes


def test_whole_book_imitation_service_runs_in_sandbox(tmp_path: Path) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    create_schema(engine)
    factory = sessionmaker(bind=engine, future=True)
    with factory() as session:
        branch_id = _seed_branch(session, tmp_path / "sample.txt")
        service = WholeBookImitationService(session)
        pack = StoryMappingPack(
            project_title="测试项目",
            source_work_name="示例小说",
            target_work_name="新世界版示例小说",
            world_mapping={"郑国": "星际联邦"},
            character_mapping={"卫图": "魏拓"},
        )
        report = service.run_in_sandbox(
            branch_id,
            mapping_pack=pack,
            chapter_goals=[
                (2, "延续资源铺垫"),
                (3, "延续主角获得功法后的行动线"),
            ],
            max_rounds=1,
            use_llm=False,
        )
        assert report.execution_mode == "sandbox_execute"
        assert report.contract_version == "whole-book-imitation.v1"
        assert report.stable_contract_version == "whole-book-imitation-pre-v1"
        assert len(report.executed_steps) == 2
        assert report.final_carry_over_state is not None
        assert report.executed_steps[0].carry_over_state.generated_summary
        assert report.executed_steps[0].action_queue
        assert report.executed_steps[0].revise_payload
        assert "strategy_input" in report.executed_steps[1].model_dump()
        assert report.executed_steps[1].scheduling_priority >= 1
        assert report.executed_steps[1].scheduling_reason
        assert report.executed_steps[0].policy_summary
        assert report.policy_summary["executed_step_count"] == 2
        assert "min_overall_score" in report.policy_summary
        assert "max_action_count" in report.policy_summary
        assert "verdicts" in report.policy_summary
        assert "chapter_ranking" in report.policy_summary
        assert "severity_histogram" in report.policy_summary
        assert "book_priority_ranking" in report.policy_summary
        assert "risk_bucket_histogram" in report.policy_summary
        ordered = report.executed_steps[0].revise_payload.get("ordered_actions", [])
        assert isinstance(ordered, list)
        assert ordered
        assert report.executed_steps[1].strategy_input.get("prioritized_targets", [])
        assert report.executed_steps[1].strategy_input.get("prioritized_families", [])
        assert report.executed_steps[1].strategy_input.get("top_priority_families", []) is not None
        assert report.executed_steps[1].strategy_input.get("high_risk_families", []) is not None
        assert report.executed_steps[1].strategy_input.get("recommended_actions", [])
        assert report.dashboard_summary["chapter_count"] == 2
        assert "highest_priority_chapters" in report.dashboard_summary
        assert "strategy_targets" in report.dashboard_summary
        assert "top_priority_families" in report.dashboard_summary["strategy_targets"][0] or report.dashboard_summary["strategy_targets"][1]["top_priority_families"] is not None
        assert "issue_family_histogram" in report.dashboard_summary
        assert "cluster_buckets" in report.dashboard_summary
        assert "issue_family_ranking" in report.dashboard_summary
        assert "dialogue" in report.dashboard_summary["issue_family_histogram"]
        assert "research" in report.dashboard_summary["issue_family_histogram"]
        assert "weak_lane_priority_ranking" in report.dashboard_summary
        assert "top_weak_lane_chapters" in report.dashboard_summary
        assert "family_priority_ranking" in report.dashboard_summary
        assert "weak_lane_histogram" in report.dashboard_summary
        assert "weak_lane_top_actions" in report.dashboard_summary
        assert "top_priority_summary" in report.dashboard_summary
        assert "top_risk_summary" in report.dashboard_summary
        assert "weak_lane_dominance" in report.dashboard_summary
        assert "chapter_flags" in report.dashboard_summary
        assert "next_stage_focus" in report.policy_summary
        assert "book_handoff_summary" in report.dashboard_summary
        assert "top_repair_recommendations" in report.dashboard_summary["book_handoff_summary"]
        assert "weak_lane_action_count" in report.dashboard_summary["top_priority_summary"]
        assert "weak_lane_families" in report.dashboard_summary["top_risk_summary"]
        assert "top_priority_families" in report.dashboard_summary["top_priority_summary"]
        assert "high_risk_families" in report.dashboard_summary["top_risk_summary"]
        assert "reason" in report.policy_summary["book_priority_ranking"][0]
        assert "scheduling_priority" in report.dashboard_summary["chapter_flags"][0]


def test_whole_book_imitation_contract_docs_and_sample_are_synced() -> None:
    manifest = Path("docs/interface-manifest.md").read_text(encoding="utf-8")
    docs_index = Path("docs/README.md").read_text(encoding="utf-8")
    track_readme = Path("docs/tracks/imitation/README.md").read_text(encoding="utf-8")
    role_readme = Path("docs/roles/imitation/README.md").read_text(encoding="utf-8")
    integrator_readme = Path("docs/roles/integrator/README.md").read_text(encoding="utf-8")
    stability_doc = Path("docs/whole-book-imitation-api-stability-summary.md").read_text(encoding="utf-8")
    versioning_doc = Path("docs/whole-book-imitation-api-versioning.md").read_text(encoding="utf-8")
    freeze_doc = Path("docs/whole-book-imitation-api-freeze-readiness.md").read_text(encoding="utf-8")
    freeze_evidence_doc = Path("docs/whole-book-imitation-freeze-evidence-20260503.md").read_text(encoding="utf-8")
    sample = json.loads(Path("docs/examples/whole-book-imitation-run.sample.json").read_text(encoding="utf-8"))

    assert "## 10. Whole-Book Imitation Run Report" in manifest
    assert "book_handoff_summary" in manifest
    assert "contract_version" in manifest
    assert "stable_contract_version" in manifest
    assert "queue_next_actions" in manifest
    assert "./examples/whole-book-imitation-run.sample.json" in docs_index
    assert "./whole-book-imitation-api-stability-summary.md" in docs_index
    assert "./whole-book-imitation-api-versioning.md" in docs_index
    assert "./whole-book-imitation-api-freeze-readiness.md" in docs_index
    assert "./whole-book-imitation-freeze-evidence-20260503.md" in docs_index
    assert "whole-book-imitation-run.sample.json" in track_readme
    assert "whole-book-imitation-api-stability-summary.md" in track_readme
    assert "whole-book-imitation-api-versioning.md" in track_readme
    assert "whole-book-imitation-api-freeze-readiness.md" in track_readme
    assert "whole-book-imitation-freeze-evidence-20260503.md" in track_readme
    assert "whole-book-imitation-run.sample.json" in role_readme
    assert "whole-book-imitation-api-stability-summary.md" in integrator_readme
    assert "whole-book-imitation-api-versioning.md" in integrator_readme
    assert "whole-book-imitation-api-freeze-readiness.md" in integrator_readme
    assert "whole-book-imitation-freeze-evidence-20260503.md" in integrator_readme
    assert "pre-v1 / system-contract-ready" in stability_doc
    assert "POST /api/whole-book-imitation-run" in stability_doc
    assert "stable_contract_version = whole-book-imitation-pre-v1" in versioning_doc
    assert "pre-v1，已具备 system-contract-ready 能力" in freeze_doc
    assert "daily usage limit exceeded" in freeze_evidence_doc
    assert "billing_error" in freeze_evidence_doc

    assert sample["execution_mode"] == "sandbox_execute"
    assert sample["contract_version"] == "whole-book-imitation.v1"
    assert sample["stable_contract_version"] == "whole-book-imitation-pre-v1"
    assert "policy_summary" in sample
    assert "dashboard_summary" in sample
    assert "next_stage_focus" in sample["policy_summary"]
    assert "book_handoff_summary" in sample["dashboard_summary"]
    assert "top_repair_recommendations" in sample["dashboard_summary"]["book_handoff_summary"]
