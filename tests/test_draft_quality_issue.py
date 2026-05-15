from novel_analyzer.services.imitation_harness_service import _draft_quality_issue


def test_clean_prose_passes():
    text = "卫图站在院中，望着远处的山影。" * 60
    assert _draft_quality_issue(text, min_chars=500) is None


def test_short_draft_flagged_thin():
    assert _draft_quality_issue("卫图说了句话。", min_chars=500) == "thin"


def test_empty_draft_flagged_thin():
    assert _draft_quality_issue("", min_chars=500) == "thin"


def test_scaffold_marker_in_long_text_flagged():
    body = "卫图缓缓抬手，掌心微温。" * 60
    contaminated = body + "\n\n【硬约束】不得违背世界规则"
    assert _draft_quality_issue(contaminated, min_chars=500) == "scaffold_only"


def test_chapter_goal_marker_flagged():
    body = "卫图盯着炉中的丹火。" * 60
    contaminated = "【章节目标】突破筑基\n" + body
    assert _draft_quality_issue(contaminated, min_chars=500) == "scaffold_only"


def test_action_queue_tail_flagged():
    body = "卫图缓缓抬手，掌心微温。" * 60
    bleed = body + "\n[P1|high]修正风格\n[P2|medium]补充细节\n[P3|low]检查逻辑"
    assert _draft_quality_issue(bleed, min_chars=500) == "action_queue_bleed"


def test_harness_action_queue_block_flagged():
    body = "卫图缓缓抬手，掌心微温。" * 60
    bleed = body + "\n\n【Harness Action Queue】\nrevise_dialogue"
    assert _draft_quality_issue(bleed, min_chars=500) == "scaffold_only"


def test_scaffold_marker_takes_priority_over_short():
    short_with_marker = "短文。\n【修订提示】重写"
    assert _draft_quality_issue(short_with_marker, min_chars=500) == "scaffold_only"
