from pathlib import Path

from _pytest.monkeypatch import MonkeyPatch
from typer.testing import CliRunner

from novel_analyzer.application.dto import AutoRunResult
from novel_analyzer.cli.app import app

runner = CliRunner()


def test_auto_run_cli_calls_shared_layer_and_preserves_key_value_output(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, object] = {}
    novel_path = tmp_path / "novel.txt"
    novel_path.write_text("第1章 一\n正文\n第2章 二\n正文\n", encoding="utf-8")

    def fake_ingest_and_start_pipeline(**kwargs: object) -> AutoRunResult:
        captured.update(kwargs)
        return AutoRunResult(
            novel_id="novel-1",
            manifest_id="manifest-1",
            run_id="run-1",
            branch_id="branch-1",
            chapter_count=2,
            processed_chapters=0,
            next_chapter=1,
            pipeline_profile="auto-lite",
            pipeline_state="ready",
        )

    monkeypatch.setattr(
        "novel_analyzer.cli.app._ingest_and_start_pipeline",
        fake_ingest_and_start_pipeline,
    )

    result = runner.invoke(
        app,
        [
            "auto-run",
            str(novel_path),
            "--database-url",
            "postgresql+psycopg://novel:novelpass@127.0.0.1:5432/test",
            "--max-chapters",
            "0",
        ],
    )

    assert result.exit_code == 0
    assert "novel_id=novel-1" in result.stdout
    assert "manifest_id=manifest-1" in result.stdout
    assert "run_id=run-1" in result.stdout
    assert "branch_id=branch-1" in result.stdout
    assert "processed_chapters=0" in result.stdout
    assert "next_chapter=1" in result.stdout
    assert captured["path"] == str(novel_path)
    assert captured["max_chapters"] == 0
