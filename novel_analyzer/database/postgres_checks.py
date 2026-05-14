"""PostgreSQL capability and initialization checks."""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from novel_analyzer.config.settings import Settings, get_settings

REQUIRED_TABLES = (
    "alembic_version",
    "novel_sources",
    "chapter_manifests",
    "chapter_segments",
    "analysis_runs",
    "run_branches",
    "chapter_artifacts",
    "chapter_jobs",
    "retrieval_documents",
    "graph_nodes",
    "graph_edges",
)

RECOMMENDED_EXTENSIONS = ("pg_trgm", "vector")
TEXT_SEARCH_CONFIGS = ("simple", "jiebacfg", "jiebaqry")
CLUSTER_REVIEW_REQUIRED_COLUMNS: dict[str, tuple[str, ...]] = {
    "cluster_review_records": ("review_actor",),
    "cluster_review_event_records": (
        "previous_cluster_status",
        "previous_review_result",
        "previous_review_actor",
        "review_actor",
    ),
}


@dataclass(frozen=True, slots=True)
class PostgresCheckReport:
    """Compact PostgreSQL environment report."""

    database_exists: bool
    can_connect: bool
    initialized_schema: bool
    server_version: str | None
    installed_extensions: list[str]
    available_text_search_configs: list[str]
    missing_tables: list[str]
    missing_extensions: list[str]
    missing_cluster_review_columns: dict[str, list[str]] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return (
            self.database_exists
            and self.can_connect
            and self.initialized_schema
            and not self.missing_extensions
        )


def postgres_capability_report(settings: Settings | None = None) -> PostgresCheckReport:
    """Inspect PostgreSQL readiness for this project."""

    runtime = settings or get_settings()
    try:
        admin_engine = create_engine(
            runtime.admin_database_url,
            future=True,
            isolation_level="AUTOCOMMIT",
        )
        with admin_engine.connect() as connection:
            database_exists = (
            connection.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :db_name"),
                    {"db_name": runtime.effective_db_name},
                ).scalar_one_or_none()
                is not None
            )
    except SQLAlchemyError:
        return PostgresCheckReport(
            database_exists=False,
            can_connect=False,
            initialized_schema=False,
            server_version=None,
            installed_extensions=[],
            available_text_search_configs=[],
            missing_tables=list(REQUIRED_TABLES),
            missing_extensions=list(RECOMMENDED_EXTENSIONS),
            missing_cluster_review_columns={},
        )

    if not database_exists:
        return PostgresCheckReport(
            database_exists=False,
            can_connect=False,
            initialized_schema=False,
            server_version=None,
            installed_extensions=[],
            available_text_search_configs=[],
            missing_tables=list(REQUIRED_TABLES),
            missing_extensions=list(RECOMMENDED_EXTENSIONS),
            missing_cluster_review_columns={},
        )

    try:
        engine = create_engine(runtime.resolved_database_url, future=True)
        with engine.connect() as connection:
            server_version = cast_scalar_string(
                connection.execute(text("SHOW server_version")).scalar_one_or_none()
            )
            installed_extensions = [
                str(row[0])
                for row in connection.execute(
                    text(
                        "SELECT extname FROM pg_extension "
                        "WHERE extname = ANY(:extensions) ORDER BY extname"
                    ),
                    {"extensions": list(RECOMMENDED_EXTENSIONS)},
                ).all()
            ]
            available_text_search_configs = [
                str(row[0])
                for row in connection.execute(
                    text(
                        "SELECT cfgname FROM pg_ts_config "
                        "WHERE cfgname = ANY(:configs) ORDER BY cfgname"
                    ),
                    {"configs": list(TEXT_SEARCH_CONFIGS)},
                ).all()
            ]
            existing_tables = {
                str(row[0])
                for row in connection.execute(
                    text(
                        "SELECT tablename FROM pg_tables "
                        "WHERE schemaname = 'public' AND tablename = ANY(:tables)"
                    ),
                    {"tables": list(REQUIRED_TABLES)},
                ).all()
            }
            missing_cluster_review_columns: dict[str, list[str]] = {}
            for table_name, required_columns in CLUSTER_REVIEW_REQUIRED_COLUMNS.items():
                if table_name not in existing_tables:
                    continue
                existing_columns = {
                    str(row[0])
                    for row in connection.execute(
                        text(
                            """
                            SELECT column_name
                            FROM information_schema.columns
                            WHERE table_schema = 'public' AND table_name = :table_name
                            """
                        ),
                        {"table_name": table_name},
                    ).all()
                }
                missing = [name for name in required_columns if name not in existing_columns]
                if missing:
                    missing_cluster_review_columns[table_name] = missing
    except SQLAlchemyError:
        return PostgresCheckReport(
            database_exists=True,
            can_connect=False,
            initialized_schema=False,
            server_version=None,
            installed_extensions=[],
            available_text_search_configs=[],
            missing_tables=list(REQUIRED_TABLES),
            missing_extensions=list(RECOMMENDED_EXTENSIONS),
            missing_cluster_review_columns={},
        )

    missing_tables = [name for name in REQUIRED_TABLES if name not in existing_tables]
    missing_extensions = [
        name for name in RECOMMENDED_EXTENSIONS if name not in installed_extensions
    ]
    return PostgresCheckReport(
        database_exists=True,
        can_connect=True,
        initialized_schema=not missing_tables,
        server_version=server_version,
        installed_extensions=installed_extensions,
        available_text_search_configs=available_text_search_configs,
        missing_tables=missing_tables,
        missing_extensions=missing_extensions,
        missing_cluster_review_columns=missing_cluster_review_columns,
    )


def cast_scalar_string(value: object | None) -> str | None:
    """Normalize scalar values to optional strings."""

    if value is None:
        return None
    return str(value)
