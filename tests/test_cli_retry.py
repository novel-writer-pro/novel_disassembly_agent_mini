from pathlib import Path

from _pytest.monkeypatch import MonkeyPatch
from typer.testing import CliRunner

from novel_analyzer.cli.app import app
from tests.cli_test_support import patch_cli_sqlite_runtime

runner = CliRunner()


def test_list_failed_jobs_empty_on_clean_branch(
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
        ['list-failed-jobs', run_lines['branch_id'], '--database-url', db_url],
    )
    assert result.exit_code == 0
    assert 'failed_job_count=0' in result.stdout
