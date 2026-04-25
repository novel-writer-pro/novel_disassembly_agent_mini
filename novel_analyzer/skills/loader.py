"""Local wrapper around SkillKit using project-root skills_dir."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from skillkit import SkillManager
from skillkit.core.models import SkillMetadata
from skillkit.integrations.langchain import create_langchain_tools

from novel_analyzer.config.settings import Settings, get_settings


def create_skill_manager(settings: Settings | None = None) -> SkillManager:
    """Create a SkillManager constrained to the project's skills_dir."""

    runtime = settings or get_settings()
    return SkillManager(
        project_skill_dir=Path(runtime.skills_dir),
        anthropic_config_dir="",
        plugin_dirs=[],
        additional_search_paths=[],
        default_script_timeout=runtime.skill_default_timeout,
    )


def discover_skills(settings: Settings | None = None) -> SkillManager:
    """Create and discover project-local skills."""

    manager = create_skill_manager(settings)
    manager.discover()
    return manager


def list_skill_names(settings: Settings | None = None) -> list[str]:
    """Return discovered skill names."""

    manager = discover_skills(settings)
    names: list[str] = []
    for item in manager.list_skills(include_qualified=False):
        if isinstance(item, str):
            names.append(item)
        else:
            metadata: SkillMetadata = item
            names.append(metadata.name)
    return sorted(names)


def create_skill_tools(settings: Settings | None = None) -> list[Any]:
    """Return LangChain tools created from discovered skills."""

    manager = discover_skills(settings)
    return create_langchain_tools(manager)
