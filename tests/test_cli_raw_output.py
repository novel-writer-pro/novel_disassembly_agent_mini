from pathlib import Path

from typer.testing import CliRunner

from novel_analyzer.cli.app import app
from novel_analyzer.config.settings import Settings
from novel_analyzer.database.session import create_session_factory
from novel_analyzer.services.run_service import RunService

runner = CliRunner()


def test_export_raw_output_cli(tmp_path: Path) -> None:
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
    with create_session_factory(Settings(database_url=db_url))() as session:
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
