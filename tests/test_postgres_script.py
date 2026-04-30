from _pytest.capture import CaptureFixture
from _pytest.monkeypatch import MonkeyPatch

from novel_analyzer.config.settings import Settings
from novel_analyzer.database.postgres_checks import PostgresCheckReport
from scripts.check_postgres import main


def test_check_postgres_script_returns_zero_when_report_is_ok(
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        "scripts.check_postgres.postgres_capability_report",
        lambda settings=None: PostgresCheckReport(
            database_exists=True,
            can_connect=True,
            initialized_schema=True,
            server_version="16.0",
            installed_extensions=["pg_trgm", "vector"],
            available_text_search_configs=["simple"],
            missing_tables=[],
            missing_extensions=[],
        ),
    )
    monkeypatch.setattr("scripts.check_postgres.get_settings", lambda: object())

    code = main()
    out = capsys.readouterr().out

    assert code == 0
    assert "ok=true" in out


def test_check_postgres_script_rejects_non_postgresql_url(
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        "scripts.check_postgres.get_settings",
        lambda: Settings(database_url="sqlite:///tmp/test.db"),
    )

    code = main()
    out = capsys.readouterr().out

    assert code == 1
    assert "Only PostgreSQL database URLs are supported" in out
