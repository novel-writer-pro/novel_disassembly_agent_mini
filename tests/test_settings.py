from novel_analyzer.config.settings import Settings


def test_postgres_url_is_built_from_components() -> None:
    settings = Settings(
        db_host="127.0.0.1",
        db_port=5432,
        db_user="d2",
        db_password="d2pass",
        db_name="novel_analyzer",
    )
    assert settings.resolved_database_url == (
        "postgresql+psycopg://d2:d2pass@127.0.0.1:5432/novel_analyzer"
    )
    assert settings.masked_database_url == (
        "postgresql+psycopg://d2:***@127.0.0.1:5432/novel_analyzer"
    )


def test_explicit_database_url_takes_precedence() -> None:
    settings = Settings(database_url="postgresql+psycopg://u:p@127.0.0.1:5432/custom")
    assert settings.resolved_database_url == "postgresql+psycopg://u:p@127.0.0.1:5432/custom"


def test_explicit_database_url_is_masked_safely() -> None:
    settings = Settings(database_url="postgresql+psycopg://novel:secret@127.0.0.1:5432/custom")
    assert settings.masked_database_url == "postgresql+psycopg://novel:***@127.0.0.1:5432/custom"


def test_explicit_database_url_drives_effective_db_name_and_admin_url() -> None:
    settings = Settings(
        database_url="postgresql+psycopg://novel:secret@127.0.0.1:5433/custom_db",
        db_admin_name="postgres",
    )
    assert settings.effective_db_name == "custom_db"
    assert settings.admin_database_url == "postgresql+psycopg://novel:secret@127.0.0.1:5433/postgres"


def test_explicit_ipv6_database_url_preserves_brackets_when_rewritten() -> None:
    settings = Settings(
        database_url="postgresql+psycopg://novel:secret@[::1]:5433/custom_db",
        db_admin_name="postgres",
    )
    assert settings.admin_database_url == "postgresql+psycopg://novel:secret@[::1]:5433/postgres"
    assert settings.masked_database_url == "postgresql+psycopg://novel:***@[::1]:5433/custom_db"
