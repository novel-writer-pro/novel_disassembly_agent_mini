from novel_analyzer.agent.pipeline import (
    DEFAULT_SMALL_MODEL_STAGES,
    STAGE_TO_SKILL,
    ChapterAgentContext,
    build_agent_stage_prompts,
)


def test_build_agent_stage_prompts_renders_core_pipeline() -> None:
    prompts = build_agent_stage_prompts(
        ChapterAgentContext(
            chapter_index=1,
            normalized_title='大器晚成',
            chapter_content='卫图在李宅做马倌。',
            previous_summary='上一章无。',
            state_summary_json='{"paid_off_foreshadowing":["旧伏笔"]}',
        )
    )
    assert set(DEFAULT_SMALL_MODEL_STAGES).issubset(prompts.keys())
    assert '大器晚成' in prompts['chapter_intake']
    assert '卫图在李宅做马倌' in prompts['chapter_intake']
    assert '作者学习视角' in prompts['writer_learning_lens']
    assert '旧伏笔' in prompts['analysis_generator']


def test_internal_stages_are_backed_by_repo_local_skill_assets() -> None:
    assert STAGE_TO_SKILL['chapter_intake'] == 'chapter-intake'
    assert STAGE_TO_SKILL['anti_fabrication_guard'] == 'anti-fabrication-guard'
