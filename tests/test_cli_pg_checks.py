from _pytest.monkeypatch import MonkeyPatch
from typer.testing import CliRunner

from novel_analyzer.cli.app import app
from novel_analyzer.config.settings import Settings
from novel_analyzer.database.postgres_checks import PostgresCheckReport

runner = CliRunner()


def test_db_capabilities_cli_outputs_expected_fields(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(
        "novel_analyzer.cli.app.postgres_capability_report",
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

    result = runner.invoke(app, ["db-capabilities"])

    assert result.exit_code == 0
    assert "database_exists=true" in result.stdout
    assert "can_connect=true" in result.stdout
    assert "initialized_schema=true" in result.stdout
    assert "installed_extensions=pg_trgm,vector" in result.stdout
    assert "ok=true" in result.stdout


def test_init_db_masks_explicit_database_url(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr("novel_analyzer.cli.app.ensure_database_exists", lambda settings=None: None)
    monkeypatch.setattr("novel_analyzer.cli.app.upgrade_database", lambda settings=None: None)

    result = runner.invoke(
        app,
        [
            "init-db",
            "--database-url",
            "postgresql+psycopg://novel:secret@127.0.0.1:5432/custom",
        ],
    )

    assert result.exit_code == 0
    assert "postgresql+psycopg://novel:***@127.0.0.1:5432/custom" in result.stdout


def test_db_capabilities_uses_effective_database_name_from_explicit_url(
    monkeypatch: MonkeyPatch,
) -> None:
    seen: dict[str, str] = {}

    def fake_report(settings: Settings | None = None) -> PostgresCheckReport:
        assert settings is not None
        seen["db_name"] = settings.effective_db_name
        seen["admin_url"] = settings.admin_database_url
        return PostgresCheckReport(
            database_exists=True,
            can_connect=True,
            initialized_schema=True,
            server_version="16.0",
            installed_extensions=["pg_trgm", "vector"],
            available_text_search_configs=["simple"],
            missing_tables=[],
            missing_extensions=[],
        )

    monkeypatch.setattr("novel_analyzer.cli.app.postgres_capability_report", fake_report)

    result = runner.invoke(
        app,
        [
            "db-capabilities",
            "--database-url",
            "postgresql+psycopg://novel:secret@127.0.0.1:5433/custom_db",
        ],
    )

    assert result.exit_code == 0
    assert seen["db_name"] == "custom_db"
    assert seen["admin_url"] == "postgresql+psycopg://novel:secret@127.0.0.1:5433/postgres"


def test_db_capabilities_rejects_non_postgresql_database_url() -> None:
    result = runner.invoke(
        app,
        [
            "db-capabilities",
            "--database-url",
            "sqlite:///tmp/test.db",
        ],
    )
    assert result.exit_code != 0
    assert "Only PostgreSQL database URLs are supported" in result.stdout


def test_init_db_rejects_non_postgresql_database_url() -> None:
    result = runner.invoke(
        app,
        [
            "init-db",
            "--database-url",
            "sqlite:///tmp/test.db",
        ],
    )
    assert result.exit_code != 0
    assert "Only PostgreSQL database URLs are supported" in result.stdout


def test_show_branch_rejects_non_postgresql_database_url() -> None:
    result = runner.invoke(
        app,
        [
            "show-branch",
            "dummy-branch",
            "--database-url",
            "sqlite:///tmp/test.db",
        ],
    )
    assert result.exit_code != 0
    assert "Only PostgreSQL database URLs are supported" in result.stdout
