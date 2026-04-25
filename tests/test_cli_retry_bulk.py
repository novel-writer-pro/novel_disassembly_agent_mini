from pathlib import Path

from typer.testing import CliRunner

from novel_analyzer.cli.app import app

runner = CliRunner()


def test_clear_running_jobs_cli_on_clean_branch(tmp_path: Path) -> None:
    db_path = tmp_path / 'test.db'
    db_url = f'sqlite:///{db_path}'
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


def test_retry_failed_jobs_cli_on_clean_branch(tmp_path: Path) -> None:
    db_path = tmp_path / 'test.db'
    db_url = f'sqlite:///{db_path}'
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
