"""Helpers for loading and rendering project-local skill assets."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from string import Template
from typing import Any

from novel_analyzer.config.settings import Settings, get_settings

CORE_SMALL_MODEL_SKILLS = [
    'chapter-intake',
    'chapter-fact-extractor',
    'evidence-binder',
    'chapter-analysis-generator',
    'writer-learning-lens',
    'anti-fabrication-guard',
]


@dataclass(frozen=True, slots=True)
class SkillAssetBundle:
    """A loaded prompt/schema asset pair for one skill."""

    skill_name: str
    prompt_text: str
    output_schema: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ChapterSkillContext:
    """Minimal prompt-rendering context for chapter-oriented skills."""

    chapter_index: int
    normalized_title: str
    chapter_content: str
    previous_summary: str = ''
    intake_json: str = '{}'
    prior_context_json: str = '{}'
    graph_context_json: str = '{}'
    state_summary_json: str = '{}'
    cleaned_text: str = ''
    fact_json: str = '{}'
    evidence_bound_json: str = '{}'
    window_summary: str = ''
    chapter_json: str = '{}'
    prior_writer_notes: str = ''
    analysis_json: str = '{}'
    writer_json: str = '{}'


def _skills_root(settings: Settings | None = None) -> Path:
    runtime = settings or get_settings()
    return Path(runtime.skills_dir)


def load_skill_bundle(skill_name: str, settings: Settings | None = None) -> SkillAssetBundle:
    """Load prompt and schema assets for a project-local skill."""

    root = _skills_root(settings) / skill_name
    prompt_path = root / 'prompts' / 'main.md'
    schema_path = root / 'schemas' / 'output.schema.json'
    prompt_text = prompt_path.read_text(encoding='utf-8') if prompt_path.exists() else ''
    if schema_path.exists():
        output_schema = json.loads(schema_path.read_text(encoding='utf-8'))
    else:
        output_schema = {}
    return SkillAssetBundle(
        skill_name=skill_name,
        prompt_text=prompt_text,
        output_schema=output_schema,
    )


def render_skill_prompt(
    skill_name: str,
    variables: dict[str, str],
    settings: Settings | None = None,
) -> str:
    """Render a skill prompt using lightweight template substitution."""

    bundle = load_skill_bundle(skill_name, settings)
    normalized = {key: value for key, value in variables.items()}
    template = Template(bundle.prompt_text.replace('{{', '${').replace('}}', '}'))
    return template.safe_substitute(normalized)


def build_small_model_skill_prompts(
    context: ChapterSkillContext,
    settings: Settings | None = None,
) -> dict[str, str]:
    """Build prompt payloads for the default small-model skill pipeline."""

    payload = {
        'chapter_index': str(context.chapter_index),
        'normalized_title': context.normalized_title,
        'chapter_content': context.chapter_content,
        'previous_summary': context.previous_summary,
        'intake_json': context.intake_json,
        'prior_context_json': context.prior_context_json,
        'graph_context_json': context.graph_context_json,
        'state_summary_json': context.state_summary_json,
        'cleaned_text': context.cleaned_text,
        'fact_json': context.fact_json,
        'evidence_bound_json': context.evidence_bound_json,
        'window_summary': context.window_summary,
        'chapter_json': context.chapter_json,
        'prior_writer_notes': context.prior_writer_notes,
        'analysis_json': context.analysis_json,
        'writer_json': context.writer_json,
    }
    return {
        skill_name: render_skill_prompt(skill_name, payload, settings)
        for skill_name in CORE_SMALL_MODEL_SKILLS
    }
