from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from novel_analyzer.database.models import (
    AnalysisRun,
    ChapterArtifact,
    ChapterManifest,
    FactRecord,
    NovelSource,
    RunBranch,
)
from novel_analyzer.database.session import create_schema
from novel_analyzer.domain.schemas import ChapterPlanningIntent
from novel_analyzer.services.next_chapter_planner_service import NextChapterPlannerService


def _seed_branch(session) -> str:
    novel = NovelSource(
        id="novel-1",
        title="示例小说",
        source_path="/tmp/sample.txt",
        source_hash="hash",
        metadata_json={},
    )
    manifest = ChapterManifest(
        id="manifest-1",
        novel_id=novel.id,
        version=1,
        splitter_version="heuristic-v1",
        chapter_count=100,
        notes={},
    )
    run = AnalysisRun(
        id="run-1",
        novel_id=novel.id,
        manifest_id=manifest.id,
        llm_base_url="https://example.invalid/v1",
        llm_model_name="gpt-5.4-mini",
        analysis_profile={},
        active_branch_id="branch-1",
    )
    branch = RunBranch(
        id="branch-1",
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
            ChapterArtifact(
                branch_id=branch.id,
                chapter_index=1,
                artifact_type="chapter_analysis",
                payload_json={
                    "chapter_summary": "卫图觉醒命格并决定求取养生功。",
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
                    "chapter_summary": "卫图拜访二姑，为接触功法资源做铺垫。",
                    "continuity_notes": ["关系推进存在轻度支撑缺口。"],
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
            FactRecord(
                branch_id=branch.id,
                chapter_index=2,
                fact_type="entity",
                label="卫荭",
                evidence_list=["卫图拜访二姑卫荭"],
                confidence=0.8,
            ),
        ]
    )
    session.commit()
    return branch.id


def test_next_chapter_planner_builds_context_and_plan() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    create_schema(engine)
    factory = sessionmaker(bind=engine, future=True)
    with factory() as session:
        branch_id = _seed_branch(session)
        service = NextChapterPlannerService(session)
        intent = ChapterPlanningIntent(
            primary_goal="推进卫图获取养生功的机会",
            emphasis=["主线推进", "资源获取"],
            forbidden_moves=["不要让卫图直接获得超出铺垫的力量"],
            preferred_tone="克制务实",
            pace="steady",
        )

        context = service.build_context(branch_id, intent=intent)
        assert context.branch_id == branch_id
        assert context.current_chapter_index == 2
        assert context.next_chapter_index == 3
        assert context.recent_chapter_summaries
        assert "卫图" in context.active_characters

        plan = service.build_plan(branch_id, intent=intent)
        assert plan.branch_id == branch_id
        assert plan.next_chapter_index == 3
        assert any(key in plan.chapter_goal for key in ["身份", "赎身", "养生功", "资源积累"])
        assert len(plan.scene_plan) == 3
        assert any("禁止：" in item for item in plan.risk_notes)
        assert any("长线兑现：" in item for item in plan.risk_notes)
        assert plan.foreshadow_to_touch
        assert any("volume_goal=" in item for item in context.planning_notes)
