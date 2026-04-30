from novel_analyzer.database.postgres_checks import PostgresCheckReport


def test_postgres_check_report_ok_requires_extensions_and_schema() -> None:
    report = PostgresCheckReport(
        database_exists=True,
        can_connect=True,
        initialized_schema=True,
        server_version="16.0",
        installed_extensions=["pg_trgm", "vector"],
        available_text_search_configs=["simple"],
        missing_tables=[],
        missing_extensions=[],
    )
    assert report.ok is True


def test_postgres_check_report_fails_when_extensions_are_missing() -> None:
    report = PostgresCheckReport(
        database_exists=True,
        can_connect=True,
        initialized_schema=True,
        server_version="16.0",
        installed_extensions=["pg_trgm"],
        available_text_search_configs=["simple"],
        missing_tables=[],
        missing_extensions=["vector"],
    )
    assert report.ok is False
