from novel_analyzer.config.settings import Settings


def test_postgres_url_is_built_from_components() -> None:
    settings = Settings(
        db_dialect="postgresql",
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
    settings = Settings(database_url="sqlite:///./custom.db", db_dialect="postgresql")
    assert settings.resolved_database_url == "sqlite:///./custom.db"
