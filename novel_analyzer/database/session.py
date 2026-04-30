"""Session helpers."""

from __future__ import annotations

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from novel_analyzer.config.settings import Settings, get_settings
from novel_analyzer.database.base import Base


def create_engine_from_settings(settings: Settings | None = None) -> Engine:
    """Create a SQLAlchemy engine."""

    runtime = settings or get_settings()
    return create_engine(runtime.resolved_database_url, echo=runtime.db_echo, future=True)


def create_session_factory(settings: Settings | None = None) -> sessionmaker[Session]:
    """Create a sessionmaker bound to the configured engine."""

    engine = create_engine_from_settings(settings)
    return sessionmaker(bind=engine, future=True)


def create_schema(engine: Engine) -> None:
    """Create all tables."""

    Base.metadata.create_all(engine)


def ensure_database_exists(settings: Settings | None = None) -> None:
    """Create the target PostgreSQL database when absent."""

    runtime = settings or get_settings()

    admin_engine = create_engine(
        runtime.admin_database_url,
        future=True,
        isolation_level="AUTOCOMMIT",
    )
    query = text("SELECT 1 FROM pg_database WHERE datname = :db_name")
    create_sql = text(f'CREATE DATABASE "{runtime.effective_db_name}"')
    with admin_engine.connect() as connection:
        exists = connection.execute(
            query,
            {"db_name": runtime.effective_db_name},
        ).scalar_one_or_none()
        if exists is None:
            connection.execute(create_sql)


def database_healthcheck(settings: Settings | None = None) -> dict[str, str]:
    """Return a compact DB health summary."""

    runtime = settings or get_settings()
    engine = create_engine_from_settings(runtime)
    with engine.connect() as connection:
        scalar = connection.execute(text("SELECT 1")).scalar_one()
    return {
        "database_url": runtime.masked_database_url,
        "dialect": engine.dialect.name,
        "select_1": str(scalar),
    }
