from pathlib import Path

from typer.testing import CliRunner

from novel_analyzer.cli.app import app

runner = CliRunner()


def test_export_markdown_cli(tmp_path: Path) -> None:
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
    runner.invoke(app, ['commit-demo', run_lines['branch_id'], '1', '--database-url', db_url])
    out = tmp_path / 'chapter1.md'
    result = runner.invoke(
        app,
        ['export-markdown', run_lines['branch_id'], '1', str(out), '--database-url', db_url],
    )
    assert result.exit_code == 0
    assert out.exists()
