from pathlib import Path

from _pytest.capture import CaptureFixture
from _pytest.monkeypatch import MonkeyPatch

from novel_analyzer.config.settings import Settings
from novel_analyzer.database.postgres_checks import PostgresCheckReport
from scripts.check_sample_branch import main


def test_check_sample_branch_script_exports_report(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        "scripts.check_sample_branch.postgres_capability_report",
        lambda settings=None: PostgresCheckReport(
            database_exists=True,
            can_connect=True,
            initialized_schema=True,
            server_version="17.0",
            installed_extensions=["pg_trgm", "vector"],
            available_text_search_configs=["simple"],
            missing_tables=[],
            missing_extensions=[],
            missing_cluster_review_columns={},
        ),
    )
    monkeypatch.setattr(
        "scripts.check_sample_branch.export_branch_report_markdown",
        lambda run_id, branch_id, output_path, settings: output_path.write_text(
            f"run_id={run_id}\nbranch_id={branch_id}\n", encoding="utf-8"
        ),
    )
    monkeypatch.setattr(
        "scripts.check_sample_branch.get_settings",
        lambda: Settings(database_url="postgresql+psycopg://user:pass@127.0.0.1:5432/db"),
    )

    out = tmp_path / "branch.md"
    code = main(["run-1", "branch-1", str(out)])
    stdout = capsys.readouterr().out

    assert code == 0
    assert "ok=true" in stdout
    assert f"report_path={out}" in stdout
    assert out.read_text(encoding="utf-8") == "run_id=run-1\nbranch_id=branch-1\n"


def test_check_sample_branch_script_rejects_non_postgresql_url(
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        "scripts.check_sample_branch.get_settings",
        lambda: Settings(database_url="sqlite:///tmp/test.db"),
    )

    code = main(["run-1", "branch-1", "/tmp/branch.md"])
    stdout = capsys.readouterr().out

    assert code == 1
    assert "Only PostgreSQL database URLs are supported" in stdout
