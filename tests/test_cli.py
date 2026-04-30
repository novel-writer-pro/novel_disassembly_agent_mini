from pathlib import Path

from _pytest.monkeypatch import MonkeyPatch
from typer.testing import CliRunner

from novel_analyzer.cli.app import app
from tests.cli_test_support import patch_cli_sqlite_runtime

runner = CliRunner()


def test_cli_inspect_novel(tmp_path: Path) -> None:
    novel_path = tmp_path / "novel.txt"
    novel_path.write_text("第1章 一\n第1章 一\n正文\n第2章 二\n正文\n", encoding="utf-8")

    result = runner.invoke(app, ["inspect-novel", str(novel_path)])
    assert result.exit_code == 0
    assert "raw_heading_count=3" in result.stdout
    assert "normalized_chapter_count=2" in result.stdout


def test_cli_ingest_and_start_run(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    novel_path = tmp_path / "novel.txt"
    novel_path.write_text("第1章 一\n正文\n第2章 二\n正文\n", encoding="utf-8")

    _engine, _factory, db_url = patch_cli_sqlite_runtime(monkeypatch)
    init = runner.invoke(app, ["init-db", "--database-url", db_url])
    assert init.exit_code == 0

    ingest = runner.invoke(app, ["ingest", str(novel_path), "--database-url", db_url])
    assert ingest.exit_code == 0
    lines = dict(line.split("=", 1) for line in ingest.stdout.strip().splitlines())

    start = runner.invoke(
        app,
        ["start-run", lines["novel_id"], lines["manifest_id"], "--database-url", db_url],
    )
    assert start.exit_code == 0
    assert "run_id=" in start.stdout
    assert "branch_id=" in start.stdout
