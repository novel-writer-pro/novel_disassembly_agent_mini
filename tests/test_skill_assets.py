from novel_analyzer.skills.assets import (
    CORE_SMALL_MODEL_SKILLS,
    ChapterSkillContext,
    build_small_model_skill_prompts,
    load_skill_bundle,
)


def test_load_skill_bundle_reads_schema_and_prompt() -> None:
    bundle = load_skill_bundle('chapter-intake')
    assert (
        '章节 intake' in bundle.prompt_text
        or '章节 intake' in bundle.prompt_text.lower()
        or '章节整理' in bundle.prompt_text
    )
    assert bundle.output_schema['title'] == 'ChapterIntakeOutput'


def test_build_small_model_skill_prompts_renders_all_core_skills() -> None:
    prompts = build_small_model_skill_prompts(
        ChapterSkillContext(
            chapter_index=1,
            normalized_title='大器晚成',
            chapter_content='卫图在李宅做马倌。',
            previous_summary='上一章无。',
        )
    )
    assert set(CORE_SMALL_MODEL_SKILLS).issubset(prompts.keys())
    assert '大器晚成' in prompts['chapter-intake']
    assert '卫图在李宅做马倌' in prompts['chapter-intake']
    assert (
        'fact extraction JSON' in prompts['evidence-binder']
        or '事实提取结果' in prompts['evidence-binder']
    )
