from pathlib import Path

from _pytest.monkeypatch import MonkeyPatch
from typer.testing import CliRunner

from novel_analyzer.cli.app import app
from tests.cli_test_support import patch_cli_sqlite_runtime

runner = CliRunner()


def test_clear_running_jobs_cli_on_clean_branch(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    _engine, _factory, db_url = patch_cli_sqlite_runtime(monkeypatch)
    novel_path = tmp_path / 'novel.txt'
    novel_path.write_text('第1章 一\n正文\n', encoding='utf-8')

    runner.invoke(app, ['init-db', '--database-url', db_url])
    ingest = runner.invoke(app, ['ingest', str(novel_path), '--database-url', db_url])
    lines = dict(line.split('=', 1) for line in ingest.stdout.strip().splitlines())
    start = runner.invoke(
        app,
        ['start-run', lines['novel_id'], lines['manifest_id'], '--database-url', db_url],
    )
    run_lines = dict(line.split('=', 1) for line in start.stdout.strip().splitlines())
    result = runner.invoke(
        app,
        ['clear-running-jobs', run_lines['branch_id'], '--database-url', db_url],
    )
    assert result.exit_code == 0
    assert 'cleared_running_jobs=0' in result.stdout


def test_retry_failed_jobs_cli_on_clean_branch(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    _engine, _factory, db_url = patch_cli_sqlite_runtime(monkeypatch)
    novel_path = tmp_path / 'novel.txt'
    novel_path.write_text('第1章 一\n正文\n', encoding='utf-8')

    runner.invoke(app, ['init-db', '--database-url', db_url])
    ingest = runner.invoke(app, ['ingest', str(novel_path), '--database-url', db_url])
    lines = dict(line.split('=', 1) for line in ingest.stdout.strip().splitlines())
    start = runner.invoke(
        app,
        ['start-run', lines['novel_id'], lines['manifest_id'], '--database-url', db_url],
    )
    run_lines = dict(line.split('=', 1) for line in start.stdout.strip().splitlines())
    result = runner.invoke(
        app,
        [
            'retry-failed-jobs',
            run_lines['run_id'],
            run_lines['branch_id'],
            '--database-url',
            db_url,
        ],
    )
    assert result.exit_code == 0
    assert 'retried_failed_jobs=0' in result.stdout


def test_retry_failed_jobs_cli_skips_completed_chapters_with_artifacts(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    from sqlalchemy.orm import Session
    from sqlalchemy import create_engine, select
    from novel_analyzer.database.session import create_schema
    from novel_analyzer.services.ingest_service import IngestService
    from novel_analyzer.services.run_service import RunService
    from novel_analyzer.database.models import ChapterJob

    engine, _factory, db_url = patch_cli_sqlite_runtime(monkeypatch)
    create_schema(engine)
    novel_path = tmp_path / 'novel.txt'
    novel_path.write_text('第1章 一\n正文\n', encoding='utf-8')

    with Session(engine) as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), '样例')
        run, branch = RunService(session).create_run(novel.id, manifest.id)
        RunService(session).record_chapter_artifact(branch.id, 1, {'chapter_index': 1, 'chapter_summary': 'done'})
        job = session.scalar(select(ChapterJob).where(ChapterJob.branch_id == branch.id).where(ChapterJob.chapter_index == 1))
        if job is None:
            job = ChapterJob(branch_id=branch.id, chapter_index=1, status='failed', attempts=1)
            session.add(job)
        else:
            job.status = 'failed'
            job.attempts = 1
        session.commit()
        run_id = run.id
        branch_id = branch.id

    result = runner.invoke(
        app,
        ['retry-failed-jobs', run_id, branch_id, '--database-url', db_url],
    )
    assert result.exit_code == 0
    assert 'retried_failed_jobs=0' in result.stdout
    assert 'skipped_completed_chapters=1' in result.stdout
