"""Internal staged prompt orchestration for the book-deconstruction agent."""

from __future__ import annotations

from dataclasses import dataclass

from novel_analyzer.skills.assets import render_skill_prompt

DEFAULT_SMALL_MODEL_STAGES = [
    'chapter_intake',
    'fact_extractor',
    'evidence_binder',
    'analysis_generator',
    'writer_learning_lens',
    'anti_fabrication_guard',
]

STAGE_TO_SKILL = {
    'chapter_intake': 'chapter-intake',
    'fact_extractor': 'chapter-fact-extractor',
    'evidence_binder': 'evidence-binder',
    'analysis_generator': 'chapter-analysis-generator',
    'writer_learning_lens': 'writer-learning-lens',
    'anti_fabrication_guard': 'anti-fabrication-guard',
}


@dataclass(frozen=True, slots=True)
class ChapterAgentContext:
    """Minimal render context for the internal book-deconstruction agent."""

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


def build_agent_stage_prompts(context: ChapterAgentContext) -> dict[str, str]:
    """Render all internal stage prompts from repo-local skill assets."""

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
        stage_name: render_skill_prompt(skill_name, payload)
        for stage_name, skill_name in STAGE_TO_SKILL.items()
    }
