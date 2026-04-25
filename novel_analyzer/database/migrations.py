"""Helpers for running Alembic migrations programmatically."""

from __future__ import annotations

from pathlib import Path

from alembic.config import Config

from alembic import command
from novel_analyzer.config.settings import Settings, get_settings


def get_alembic_config(settings: Settings | None = None) -> Config:
    """Build an Alembic config bound to the runtime database URL."""

    runtime = settings or get_settings()
    config = Config(str(Path("alembic.ini")))
    config.set_main_option("sqlalchemy.url", runtime.resolved_database_url)
    return config


def upgrade_database(settings: Settings | None = None, revision: str = "head") -> None:
    """Upgrade the database to the requested Alembic revision."""

    command.upgrade(get_alembic_config(settings), revision)
