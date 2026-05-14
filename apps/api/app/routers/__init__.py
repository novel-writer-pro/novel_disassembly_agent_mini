"""Shared utilities for API routers."""

from __future__ import annotations

import json
from typing import Any

from novel_analyzer.config.settings import Settings, get_settings
from novel_analyzer.database.session import create_session_factory


def get_db_session(database_url: str | None = None):
    settings = get_settings()
    if database_url:
        settings = settings.model_copy(update={"database_url": database_url})
    factory = create_session_factory(settings)
    return factory()


def resolve_settings(database_url: str | None = None) -> Settings:
    settings = get_settings()
    if database_url:
        settings = settings.model_copy(update={"database_url": database_url})
    return settings
