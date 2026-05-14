from pathlib import Path

from _pytest.monkeypatch import MonkeyPatch
from sqlalchemy import create_engine, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from novel_analyzer.application import (
    export_branch_refs,
    get_branch_snapshot,
    get_run_snapshot,
    ingest_and_start_pipeline,
    recover_branch,
    start_pipeline,
)
from novel_analyzer.database.models import AnalysisRun, ChapterManifest, NovelSource, RunBranch
from novel_analyzer.database.session import create_schema
from novel_analyzer.services.analysis_service import AnalysisService
from novel_analyzer.services.run_service import RunService


def _patch_application_sqlite(monkeypatch: MonkeyPatch) -> tuple[Engine, str]:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    create_schema(engine)
    factory = sessionmaker(bind=engine, future=True)
    targets = [
        "novel_analyzer.application.bootstrap.create_session_factory",
        "novel_analyzer.application.pipeline.create_session_factory",
        "novel_analyzer.application.queries.create_session_factory",
        "novel_analyzer.application.recovery.create_session_factory",
        "novel_analyzer.application.exports.create_session_factory",
    ]
    for target in targets:
        monkeypatch.setattr(target, lambda settings=None, _factory=factory: _factory)
    monkeypatch.setattr(
        "novel_analyzer.application.bootstrap.ensure_database_exists",
        lambda settings=None: None,
    )
    monkeypatch.setattr(
        "novel_analyzer.application.bootstrap.upgrade_database",
        lambda settings=None: None,
    )
    return engine, "postgresql+psycopg://novel:novelpass@127.0.0.1:5432/test"


def test_application_bootstrap_run_creates_ids_and_initial_progress(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    engine, db_url = _patch_application_sqlite(monkeypatch)
    novel_path = tmp_path / "novel.txt"
    novel_path.write_text("第1章 一\n正文\n第2章 二\n正文\n", encoding="utf-8")

    result = ingest_and_start_pipeline(
        path=str(novel_path),
        pipeline_profile="manual",
        max_chapters=0,
        database_url=db_url,
    )

    assert result.novel_id
    assert result.manifest_id
    assert result.run_id
    assert result.branch_id
    assert result.chapter_count == 2
    assert result.processed_chapters == 0
    assert result.next_chapter == 1
    assert result.pipeline_state == "ready"

    with Session(engine) as session:
        novels = session.scalars(select(NovelSource)).all()
        manifests = session.scalars(select(ChapterManifest)).all()
        runs = session.scalars(select(AnalysisRun)).all()
        branches = session.scalars(select(RunBranch)).all()
        assert len(novels) == 1
        assert len(manifests) == 1
        assert len(runs) == 1
        assert len(branches) == 1
        assert runs[0].active_branch_id == branches[0].id


def test_application_pipeline_failure_returns_stable_needs_recovery(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    _engine, db_url = _patch_application_sqlite(monkeypatch)
    novel_path = tmp_path / "novel.txt"
    novel_path.write_text("第1章 一\n正文\n第2章 二\n正文\n", encoding="utf-8")

    def fake_analyze_range(
        self: AnalysisService,
        run_id: str,
        branch_id: str,
        start_chapter: int,
        end_chapter: int,
    ) -> list[str]:
        _ = (run_id, end_chapter)
        self.run_service.start_chapter_job(branch_id, start_chapter)
        self.run_service.fail_chapter_job(branch_id, start_chapter, "boom")
        raise RuntimeError("boom")

    monkeypatch.setattr(AnalysisService, "analyze_range", fake_analyze_range)

    result = ingest_and_start_pipeline(
        path=str(novel_path),
        pipeline_profile="auto-lite",
        max_chapters=1,
        database_url=db_url,
    )

    assert result.processed_chapters == 0
    assert result.pipeline_state == "needs_recovery"
    assert result.run_id is not None
    assert result.branch_id is not None


def test_application_pipeline_pre_job_failure_returns_failed_terminal(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    _engine, db_url = _patch_application_sqlite(monkeypatch)
    novel_path = tmp_path / "novel.txt"
    novel_path.write_text("第1章 一\n正文\n", encoding="utf-8")

    def explode(
        self: AnalysisService,
        run_id: str,
        branch_id: str,
        start_chapter: int,
        end_chapter: int,
    ) -> list[str]:
        _ = (self, run_id, branch_id, start_chapter, end_chapter)
        raise RuntimeError("pre-job failure")

    monkeypatch.setattr(AnalysisService, "analyze_range", explode)

    result = ingest_and_start_pipeline(
        path=str(novel_path),
        pipeline_profile="auto-lite",
        max_chapters=1,
        database_url=db_url,
    )

    assert result.processed_chapters == 0
    assert result.pipeline_state == "failed_terminal"


def test_application_auto_full_defaults_to_manifest_completion(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    _engine, db_url = _patch_application_sqlite(monkeypatch)
    novel_path = tmp_path / "novel.txt"
    novel_path.write_text("第1章 一\n正文\n第2章 二\n正文\n", encoding="utf-8")

    def fake_analyze_range(
        self: AnalysisService,
        run_id: str,
        branch_id: str,
        start_chapter: int,
        end_chapter: int,
    ) -> list[str]:
        _ = (run_id, end_chapter)
        job = self.run_service.start_chapter_job(branch_id, start_chapter)
        artifact = self.run_service.record_chapter_artifact(
            branch_id,
            start_chapter,
            payload={"chapter_index": start_chapter, "summary": f"chapter {start_chapter}"},
            source_kind="demo",
        )
        self.run_service.complete_chapter_job(branch_id, start_chapter)
        return [artifact.id if artifact.id else str(job.id)]

    monkeypatch.setattr(AnalysisService, "analyze_range", fake_analyze_range)

    result = ingest_and_start_pipeline(
        path=str(novel_path),
        pipeline_profile="auto-full",
        database_url=db_url,
    )

    assert result.processed_chapters == 2
    assert result.next_chapter is None
    assert result.pipeline_state == "completed"


def test_application_snapshots_recovery_and_exports_work_together(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    engine, db_url = _patch_application_sqlite(monkeypatch)
    novel_path = tmp_path / "novel.txt"
    novel_path.write_text("第1章 一\n正文\n第2章 二\n正文\n", encoding="utf-8")

    result = ingest_and_start_pipeline(
        path=str(novel_path),
        pipeline_profile="manual",
        max_chapters=0,
        database_url=db_url,
    )
    assert result.run_id is not None
    assert result.branch_id is not None

    with Session(engine) as session:
        service = RunService(session)
        service.record_chapter_artifact(
            result.branch_id,
            1,
            payload={"chapter_index": 1, "summary": "chapter 1", "normalized_title": "一"},
            source_kind="demo",
        )
        service.start_chapter_job(result.branch_id, 2)
        service.fail_chapter_job(result.branch_id, 2, "needs retry")

    run_snapshot = get_run_snapshot(
        run_id=result.run_id,
        branch_id=result.branch_id,
        database_url=db_url,
    )
    branch_snapshot = get_branch_snapshot(
        run_id=result.run_id,
        branch_id=result.branch_id,
        database_url=db_url,
    )
    recovery = recover_branch(
        action="retry-chapter",
        run_id=result.run_id,
        branch_id=result.branch_id,
        chapter_index=2,
        database_url=db_url,
    )
    exports = export_branch_refs(
        run_id=result.run_id,
        branch_id=result.branch_id,
        output_dir=str(tmp_path / "exports"),
        database_url=db_url,
    )

    assert run_snapshot.pipeline_state == "ready"
    assert branch_snapshot.failed_summary == []
    assert recovery.accepted_action == "retry-chapter"
    assert Path(exports.branch_bundle_path).exists()
    assert Path(exports.branch_qa_context_path).exists()
    assert Path(exports.branch_report_path).exists()


def test_start_pipeline_requires_ready_state(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    engine, db_url = _patch_application_sqlite(monkeypatch)
    novel_path = tmp_path / "novel.txt"
    novel_path.write_text("第1章 一\n正文\n", encoding="utf-8")

    result = ingest_and_start_pipeline(
        path=str(novel_path),
        pipeline_profile="manual",
        max_chapters=0,
        database_url=db_url,
    )
    assert result.run_id is not None
    assert result.branch_id is not None

    processed, next_chapter, pipeline_state = start_pipeline(
        run_id=result.run_id,
        branch_id=result.branch_id,
        pipeline_profile="auto-lite",
        max_chapters=0,
        database_url=db_url,
    )

    assert processed == 0
    assert next_chapter == 1
    assert pipeline_state == "ready"

    with Session(engine) as session:
        run = session.scalar(select(AnalysisRun).where(AnalysisRun.id == result.run_id))
        assert run is not None
        assert run.analysis_profile["pipeline_profile"] == "auto-lite"


def test_needs_recovery_outranks_paused(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    engine, db_url = _patch_application_sqlite(monkeypatch)
    novel_path = tmp_path / "novel.txt"
    novel_path.write_text("第1章 一\n正文\n第2章 二\n正文\n", encoding="utf-8")

    result = ingest_and_start_pipeline(
        path=str(novel_path),
        pipeline_profile="manual",
        max_chapters=0,
        database_url=db_url,
    )
    assert result.run_id is not None
    assert result.branch_id is not None

    with Session(engine) as session:
        service = RunService(session)
        service.start_chapter_job(result.branch_id, 1)
        service.fail_chapter_job(result.branch_id, 1, "paused but failed")
        branch = session.scalar(select(RunBranch).where(RunBranch.id == result.branch_id))
        assert branch is not None
        branch.status = "paused"
        session.commit()

    snapshot = get_run_snapshot(
        run_id=result.run_id,
        branch_id=result.branch_id,
        database_url=db_url,
    )
    assert snapshot.pipeline_state == "ready"


def test_application_pipeline_auto_retries_until_manual_recovery_threshold(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    _engine, db_url = _patch_application_sqlite(monkeypatch)
    novel_path = tmp_path / "novel.txt"
    novel_path.write_text("第1章 一\n正文\n第2章 二\n正文\n", encoding="utf-8")

    def fake_analyze_range(
        self: AnalysisService,
        run_id: str,
        branch_id: str,
        start_chapter: int,
        end_chapter: int,
    ) -> list[str]:
        _ = (run_id, end_chapter)
        self.run_service.start_chapter_job(branch_id, start_chapter)
        self.run_service.fail_chapter_job(branch_id, start_chapter, "boom")
        raise RuntimeError("boom")

    monkeypatch.setattr(AnalysisService, "analyze_range", fake_analyze_range)

    result = ingest_and_start_pipeline(
        path=str(novel_path),
        pipeline_profile="auto-lite",
        max_chapters=1,
        database_url=db_url,
    )

    assert result.pipeline_state == "needs_recovery"
    assert result.run_id is not None
    assert result.branch_id is not None

    run_snapshot = get_run_snapshot(
        run_id=result.run_id,
        branch_id=result.branch_id,
        database_url=db_url,
    )
    branch_snapshot = get_branch_snapshot(
        run_id=result.run_id,
        branch_id=result.branch_id,
        database_url=db_url,
    )

    assert run_snapshot.pipeline_state == "needs_recovery"
    assert branch_snapshot.failed_summary[0]["chapter_index"] == 1
    assert branch_snapshot.failed_summary[0]["failure_class"] is None



def test_retryable_failed_job_stays_ready_until_attempt_limit(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    engine, db_url = _patch_application_sqlite(monkeypatch)
    novel_path = tmp_path / "novel.txt"
    novel_path.write_text("第1章 一\n正文\n第2章 二\n正文\n", encoding="utf-8")

    result = ingest_and_start_pipeline(
        path=str(novel_path),
        pipeline_profile="manual",
        max_chapters=0,
        database_url=db_url,
    )
    assert result.run_id is not None
    assert result.branch_id is not None

    with Session(engine) as session:
        service = RunService(session)
        service.start_chapter_job(result.branch_id, 1)
        service.fail_chapter_job(result.branch_id, 1, "temporary failure")

    snapshot = get_run_snapshot(
        run_id=result.run_id,
        branch_id=result.branch_id,
        database_url=db_url,
    )
    branch_snapshot = get_branch_snapshot(
        run_id=result.run_id,
        branch_id=result.branch_id,
        database_url=db_url,
    )

    assert snapshot.pipeline_state == "ready"
    assert snapshot.failed_jobs == 0
    assert branch_snapshot.failed_summary == []


def test_failed_job_requires_manual_recovery_after_five_attempts(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    engine, db_url = _patch_application_sqlite(monkeypatch)
    novel_path = tmp_path / "novel.txt"
    novel_path.write_text("第1章 一\n正文\n第2章 二\n正文\n", encoding="utf-8")

    result = ingest_and_start_pipeline(
        path=str(novel_path),
        pipeline_profile="manual",
        max_chapters=0,
        database_url=db_url,
    )
    assert result.run_id is not None
    assert result.branch_id is not None

    with Session(engine) as session:
        service = RunService(session)
        for _ in range(5):
            service.start_chapter_job(result.branch_id, 1)
            service.fail_chapter_job(result.branch_id, 1, "still broken")

    snapshot = get_run_snapshot(
        run_id=result.run_id,
        branch_id=result.branch_id,
        database_url=db_url,
    )
    branch_snapshot = get_branch_snapshot(
        run_id=result.run_id,
        branch_id=result.branch_id,
        database_url=db_url,
    )

    assert snapshot.pipeline_state == "needs_recovery"
    assert snapshot.failed_jobs == 1
    assert branch_snapshot.failed_summary[0]["chapter_index"] == 1


def test_branch_snapshot_maps_provider_balance_failure_class(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    engine, db_url = _patch_application_sqlite(monkeypatch)
    novel_path = tmp_path / "novel.txt"
    novel_path.write_text("第1章 一\n正文\n", encoding="utf-8")

    result = ingest_and_start_pipeline(
        path=str(novel_path),
        pipeline_profile="manual",
        max_chapters=0,
        database_url=db_url,
    )
    assert result.run_id is not None
    assert result.branch_id is not None

    with Session(engine) as session:
        service = RunService(session)
        for _ in range(5):
            service.start_chapter_job(result.branch_id, 1)
            service.fail_chapter_job(
                result.branch_id,
                1,
                "Error code: 402 - {'error': {'message': 'Insufficient Balance'}}",
            )

    branch_snapshot = get_branch_snapshot(
        run_id=result.run_id,
        branch_id=result.branch_id,
        database_url=db_url,
    )
    assert branch_snapshot.failed_summary[0]["failure_class"] == "provider_balance"


def test_branch_snapshot_maps_provider_connection_failure_class(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    engine, db_url = _patch_application_sqlite(monkeypatch)
    novel_path = tmp_path / "novel.txt"
    novel_path.write_text("第1章 一\n正文\n", encoding="utf-8")

    result = ingest_and_start_pipeline(
        path=str(novel_path),
        pipeline_profile="manual",
        max_chapters=0,
        database_url=db_url,
    )
    assert result.run_id is not None
    assert result.branch_id is not None

    with Session(engine) as session:
        service = RunService(session)
        for _ in range(5):
            service.start_chapter_job(result.branch_id, 1)
            service.fail_chapter_job(
                result.branch_id,
                1,
                "Connection error.",
            )

    branch_snapshot = get_branch_snapshot(
        run_id=result.run_id,
        branch_id=result.branch_id,
        database_url=db_url,
    )
    assert branch_snapshot.failed_summary[0]["failure_class"] == "provider_connection"


