from pathlib import Path

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
        assert report.run_notes
