from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from novel_analyzer.config.settings import Settings
from novel_analyzer.database.models import AnalysisRun, ChapterArtifact, ChapterJob
from novel_analyzer.database.session import create_schema
from novel_analyzer.services.ingest_service import IngestService
from novel_analyzer.services.run_service import RunService


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    create_schema(engine)
    return Session(engine)


def test_fork_branch_hides_later_progress_and_copies_prefix(tmp_path) -> None:
    novel_path = tmp_path / "novel.txt"
    novel_path.write_text(
        "第1章 一\nA\n第2章 二\nB\n第3章 三\nC\n第4章 四\nD\n第5章 五\nE\n",
        encoding="utf-8",
    )

    settings = Settings(database_url="sqlite+pysqlite:///:memory:")
    with _session() as session:
        novel, manifest = IngestService(session, settings).ingest_text_file(str(novel_path), "样例")
        service = RunService(session, settings)
        run, branch = service.create_run(novel.id, manifest.id)
        for chapter_index in range(1, 6):
            service.record_chapter_artifact(
                branch.id,
                chapter_index,
                {"chapter_index": chapter_index},
            )

        child = service.fork_branch(branch.id, keep_through=3)
        run_after = session.scalar(select(AnalysisRun).where(AnalysisRun.id == run.id))
        assert run_after is not None
        assert run_after.active_branch_id == child.id

        source_artifacts = session.scalars(
            select(ChapterArtifact).where(ChapterArtifact.branch_id == branch.id)
        ).all()
        hidden_superseded = [
            artifact.chapter_index
            for artifact in source_artifacts
            if artifact.visibility == "hidden"
        ]
        assert hidden_superseded == [4, 5]

        child_artifacts = session.scalars(
            select(ChapterArtifact)
            .where(ChapterArtifact.branch_id == child.id)
            .where(ChapterArtifact.visibility == "active")
            .order_by(ChapterArtifact.chapter_index)
        ).all()
        assert [artifact.chapter_index for artifact in child_artifacts] == [1, 2, 3]
        assert all(artifact.is_inherited for artifact in child_artifacts)


def test_manual_artifact_defaults_out_of_downstream(tmp_path) -> None:
    novel_path = tmp_path / "novel.txt"
    novel_path.write_text("第1章 一\nA\n", encoding="utf-8")

    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), "样例")
        service = RunService(session)
        _, branch = service.create_run(novel.id, manifest.id)
        artifact = service.add_manual_artifact(branch.id, 1, {"note": "manual"})
        assert artifact.source_kind == "manual"
        assert artifact.participates_in_downstream is False
        snapshot = service.branch_snapshot(branch.id)
        assert snapshot["manual_excluded_chapters"] == [1]


def test_chapter_job_lifecycle(tmp_path) -> None:
    novel_path = tmp_path / 'novel.txt'
    novel_path.write_text('第1章 一\nA\n', encoding='utf-8')

    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), '样例')
        service = RunService(session)
        _, branch = service.create_run(novel.id, manifest.id)
        job = service.start_chapter_job(branch.id, 1)
        assert job.status == 'running'
        service.complete_chapter_job(branch.id, 1)
        finished = session.scalar(select(ChapterJob).where(ChapterJob.id == job.id))
        assert finished is not None
        assert finished.status == 'validated'


def test_next_chapter_index_tracks_progress(tmp_path) -> None:
    novel_path = tmp_path / 'novel.txt'
    novel_path.write_text('第1章 一\nA\n第2章 二\nB\n第3章 三\nC\n', encoding='utf-8')

    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), '样例')
        service = RunService(session)
        run, branch = service.create_run(novel.id, manifest.id)
        assert service.next_chapter_index(run.id, branch.id) == 1
        service.record_chapter_artifact(branch.id, 1, {'chapter_index': 1})
        assert service.next_chapter_index(run.id, branch.id) == 2
        service.record_chapter_artifact(branch.id, 2, {'chapter_index': 2})
        assert service.next_chapter_index(run.id, branch.id) == 3
