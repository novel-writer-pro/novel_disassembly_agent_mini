from pathlib import Path

from _pytest.monkeypatch import MonkeyPatch
from typer.testing import CliRunner

from novel_analyzer.cli.app import app
from novel_analyzer.config.settings import Settings
from novel_analyzer.services.run_service import RunService
from tests.cli_test_support import patch_cli_sqlite_runtime

runner = CliRunner()


def test_export_raw_output_cli(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    _engine, factory, db_url = patch_cli_sqlite_runtime(monkeypatch)
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
    _ = Settings
    with factory() as session:
        RunService(session).record_raw_output(
            run_lines['run_id'],
            run_lines['branch_id'],
            1,
            1,
            'demo raw',
            parsed_json={'ok': True},
            parse_status='parsed',
            parse_error=None,
            invocation_metadata={'model': 'demo'},
        )
    out = tmp_path / 'raw.json'
    result = runner.invoke(
        app,
        ['export-raw-output', run_lines['branch_id'], '1', str(out), '--database-url', db_url],
    )
    assert result.exit_code == 0
    assert out.exists()
