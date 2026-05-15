from novel_analyzer.llm.prompts import build_chapter_imitation_prompt


def _base_kwargs() -> dict:
    return {
        "source_chapter_index": 2,
        "source_title": "二姑卫荭",
        "source_excerpt": "卫图前往黄宅拜见二姑卫荭。",
        "target_goal": "延续资源铺垫",
        "style_axes": ["第三人称有限视角"],
        "scene_beats": ["拜访黄宅"],
        "hard_constraints": ["不得违背奴籍设定"],
        "soft_constraints": ["保持人物动机连贯"],
    }


def test_prompt_omits_mapping_block_when_pack_is_none():
    prompt = build_chapter_imitation_prompt(**_base_kwargs(), mapping_pack=None)
    assert "人物名替换（必须执行）" not in prompt
    assert "世界设定替换（必须执行）" not in prompt


def test_baseline_prompt_includes_self_check_section():
    prompt = build_chapter_imitation_prompt(**_base_kwargs(), mapping_pack=None)
    assert "已通过自检" in prompt
    assert "节奏检查" in prompt
    assert "对话检查" in prompt
    assert "动机检查" in prompt
    assert "关系检查" in prompt
    assert "营销冗余检查" in prompt


def test_mapped_prompt_keeps_baseline_self_check():
    pack = {"character_mapping": {"卫图": "魏拓"}}
    prompt = build_chapter_imitation_prompt(**_base_kwargs(), mapping_pack=pack)
    assert "已通过自检" in prompt
    assert "节奏检查" in prompt
    assert "二次检查：在生成完 draft_text 后" in prompt


def test_prompt_omits_mapping_block_when_pack_is_empty_dict():
    prompt = build_chapter_imitation_prompt(**_base_kwargs(), mapping_pack={})
    assert "人物名替换（必须执行）" not in prompt
    assert "世界设定替换（必须执行）" not in prompt


def test_prompt_includes_character_mapping():
    pack = {"character_mapping": {"卫图": "魏拓", "卫荭": "魏蓁"}}
    prompt = build_chapter_imitation_prompt(**_base_kwargs(), mapping_pack=pack)
    assert "人物名替换（必须执行）" in prompt
    assert "卫图→魏拓" in prompt
    assert "卫荭→魏蓁" in prompt


def test_prompt_includes_world_and_power_mapping():
    pack = {
        "world_mapping": {"郑国": "星际联邦"},
        "power_mapping": {"养生功": "星能调息术"},
    }
    prompt = build_chapter_imitation_prompt(**_base_kwargs(), mapping_pack=pack)
    assert "世界设定替换（必须执行）" in prompt
    assert "郑国→星际联邦" in prompt
    assert "力量体系替换（必须执行）" in prompt
    assert "养生功→星能调息术" in prompt


def test_prompt_includes_rule_overrides_and_forbidden_transformations():
    pack = {
        "rule_overrides": ["奴籍替换为合同制度"],
        "forbidden_transformations": ["不得引入魔法元素"],
    }
    prompt = build_chapter_imitation_prompt(**_base_kwargs(), mapping_pack=pack)
    assert "规则覆盖" in prompt
    assert "奴籍替换为合同制度" in prompt
    assert "禁止转化" in prompt
    assert "不得引入魔法元素" in prompt


def test_prompt_handles_partial_mapping_pack():
    pack = {"character_mapping": {"卫图": "魏拓"}, "world_mapping": {}, "rule_overrides": []}
    prompt = build_chapter_imitation_prompt(**_base_kwargs(), mapping_pack=pack)
    assert "卫图→魏拓" in prompt
    assert "世界设定替换（必须执行）" not in prompt
    assert "规则覆盖" not in prompt


def test_prompt_truncates_long_rule_lists():
    pack = {"rule_overrides": [f"rule_{i}" for i in range(10)]}
    prompt = build_chapter_imitation_prompt(**_base_kwargs(), mapping_pack=pack)
    assert "rule_0" in prompt
    assert "rule_4" in prompt
    assert "rule_5" not in prompt


def test_prompt_keeps_existing_blocks_alongside_mapping():
    pack = {"character_mapping": {"卫图": "魏拓"}}
    prompt = build_chapter_imitation_prompt(
        **_base_kwargs(),
        previous_summary="第一章卫图觉醒命格。",
        active_characters=["卫图", "卫荭"],
        mapping_pack=pack,
    )
    assert "前情摘要" in prompt
    assert "当前活跃角色" in prompt
    assert "卫图→魏拓" in prompt


def test_prompt_imperative_appears_in_rules_section_unconditionally():
    no_pack = build_chapter_imitation_prompt(**_base_kwargs(), mapping_pack=None)
    with_pack = build_chapter_imitation_prompt(
        **_base_kwargs(),
        mapping_pack={"character_mapping": {"卫图": "魏拓"}},
    )
    assert "draft_text 中必须使用映射后的名称" in no_pack
    assert "draft_text 中必须使用映射后的名称" in with_pack
    assert "人物名替换（必须执行）" not in no_pack
    assert "人物名替换（必须执行）" in with_pack


def test_prompt_explicitly_forbids_method_label_bleed_in_draft_text():
    """Cross-book manual review surfaced LLM writing planning vocabulary into prose:
    xuezhong ch4 dumped '目标明确：/阻力浮现：/主角回应：/章尾钩子：' into draft_text;
    weitu ch4-5 dumped '（章末钩子：...）' and '（本章完）'. Prompt must explicitly
    forbid these so the model knows draft_text is reader-facing prose, not a report.
    """
    prompt = build_chapter_imitation_prompt(**_base_kwargs(), mapping_pack=None)
    # Explicit method-label bans
    for label in ("目标明确：", "阻力浮现：", "主角回应：", "章尾钩子："):
        assert label in prompt, f"expected prompt to mention forbidden label {label!r}"
    # Scaffold marker bans
    for marker in ("（本章完）", "【硬约束】", "【说明】", "【修订提示】"):
        assert marker in prompt, f"expected prompt to mention forbidden marker {marker!r}"
    # The clause must explicitly say these belong elsewhere
    assert "method_notes" in prompt
    assert "comparison_notes" in prompt
