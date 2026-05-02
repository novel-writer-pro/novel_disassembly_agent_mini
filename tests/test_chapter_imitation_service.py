from pathlib import Path

from langchain_core.messages import AIMessage
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
from novel_analyzer.services.chapter_imitation_service import ChapterImitationService


def _seed_branch(session, source_path: Path) -> str:
    text = (
        "第1章 大器晚成\n"
        "卫图觉醒命格并决定寻找养生功。\n"
        "第2章 二姑卫荭\n"
        "卫图拜访二姑，为资源铺垫。\n"
        "第3章 养生功法\n"
        "卫图求得龟息养气功并开始修炼。\n"
    )
    source_path.write_text(text, encoding="utf-8")

    novel = NovelSource(
        id="novel-imit-1",
        title="示例小说",
        source_path=str(source_path),
        source_hash="hash",
        metadata_json={},
    )
    manifest = ChapterManifest(
        id="manifest-imit-1",
        novel_id=novel.id,
        version=1,
        splitter_version="heuristic-v1",
        chapter_count=3,
        notes={},
    )
    run = AnalysisRun(
        id="run-imit-1",
        novel_id=novel.id,
        manifest_id=manifest.id,
        llm_base_url="https://example.invalid/v1",
        llm_model_name="gpt-5.4-mini",
        analysis_profile={},
        active_branch_id="branch-imit-1",
    )
    branch = RunBranch(
        id="branch-imit-1",
        run_id=run.id,
        name="main",
        parent_branch_id=None,
        fork_after_chapter_index=0,
        status="active",
    )
    segments = [
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
    ]
    session.add_all([novel, manifest, run, branch, *segments])
    session.flush()
    session.add_all(
        [
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


def test_chapter_imitation_service_builds_plan_and_skeleton(tmp_path: Path) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    create_schema(engine)
    factory = sessionmaker(bind=engine, future=True)
    with factory() as session:
        branch_id = _seed_branch(session, tmp_path / "sample.txt")
        service = ChapterImitationService(session)
        plan = service.build_imitation_plan(
            branch_id,
            source_chapter_index=3,
            target_goal="延续主角获得功法后的行动线，并保持克制成长节奏",
        )
        assert plan.source_chapter_index == 3
        assert plan.scene_beats
        draft = service.build_skeleton_draft(
            branch_id,
            source_chapter_index=3,
            target_goal="延续主角获得功法后的行动线，并保持克制成长节奏",
        )
        assert draft.original_title == "养生功法"
        assert "【章节目标】" in draft.draft_text
        assert draft.comparison_notes


def test_chapter_imitation_service_builds_llm_draft(monkeypatch, tmp_path: Path) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    create_schema(engine)
    factory = sessionmaker(bind=engine, future=True)
    with factory() as session:
        branch_id = _seed_branch(session, tmp_path / "sample.txt")
        service = ChapterImitationService(session)

        class _DummyModel:
            def invoke(self, _prompt: str):
                return AIMessage(
                    content="""
{
  "draft_title": "养生功法",
  "draft_text": "卫图在受挫后保持克制，转而将注意力放在功法修炼上。",
  "method_notes": ["保持原章克制推进节奏"],
  "comparison_notes": ["仍保留受挫后转修炼的骨架"],
  "risk_gate_notes": ["重点检查 OOC 与剧情推进支撑缺口"]
}
""".strip()
                )

        monkeypatch.setattr(
            "novel_analyzer.services.chapter_imitation_service.build_chat_model",
            lambda *args, **kwargs: _DummyModel(),
        )

        draft = service.build_llm_draft(
            branch_id,
            source_chapter_index=3,
            target_goal="延续主角获得功法后的行动线，并保持克制成长节奏",
        )
        assert draft.original_title == "养生功法"
        assert "受挫后保持克制" in draft.draft_text
        assert draft.comparison_notes


def test_chapter_imitation_service_compare_with_source(tmp_path: Path) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    create_schema(engine)
    factory = sessionmaker(bind=engine, future=True)
    with factory() as session:
        branch_id = _seed_branch(session, tmp_path / "sample.txt")
        service = ChapterImitationService(session)
        draft = service.build_skeleton_draft(
            branch_id,
            source_chapter_index=3,
            target_goal="延续主角获得功法后的行动线，并保持克制成长节奏",
        )
        report = service.compare_with_source(
            branch_id,
            source_chapter_index=3,
            draft=draft,
        )
        assert report.original_title == "养生功法"
        assert report.source_length > 0
        assert report.draft_length > 0
        assert report.structure_overlap_notes


def test_chapter_imitation_service_review_and_revise(tmp_path: Path) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    create_schema(engine)
    factory = sessionmaker(bind=engine, future=True)
    with factory() as session:
        branch_id = _seed_branch(session, tmp_path / "sample.txt")
        service = ChapterImitationService(session)
        draft = service.build_skeleton_draft(
            branch_id,
            source_chapter_index=3,
            target_goal="延续主角获得功法后的行动线，并保持克制成长节奏",
        )
        review = service.review_draft(
            branch_id,
            source_chapter_index=3,
            draft=draft,
        )
        revised = service.revise_draft(draft, review=review)
        assert review.overall_verdict
        assert review.revision_directions
        assert revised.method_notes


def test_chapter_imitation_service_gate_draft(tmp_path: Path) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    create_schema(engine)
    factory = sessionmaker(bind=engine, future=True)
    with factory() as session:
        branch_id = _seed_branch(session, tmp_path / "sample.txt")
        service = ChapterImitationService(session)
        draft = service.build_skeleton_draft(
            branch_id,
            source_chapter_index=3,
            target_goal="延续主角获得功法后的行动线，并保持克制成长节奏",
        )
        gate = service.gate_draft(
            branch_id,
            source_chapter_index=3,
            draft=draft,
        )
        assert gate.draft_title == "养生功法"
        assert gate.hook_score is not None
        assert gate.overall_verdict
