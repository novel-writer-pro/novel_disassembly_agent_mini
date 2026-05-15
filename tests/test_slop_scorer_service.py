from __future__ import annotations

from novel_analyzer.services.slop_scorer_service import SlopSignal, score_slop


def test_empty_returns_zero() -> None:
    sig = score_slop("")
    assert isinstance(sig, SlopSignal)
    assert sig.overall_slop_score == 0.0
    assert sig.flagged_cliches == []
    assert sig.flagged_tellings == []


def test_clean_prose_scores_low() -> None:
    text = (
        "黄昏的风掠过山顶，松针轻响。卫图坐下，望着远处的雪线。"
        "他记得师父说过的那句话，但今天还不打算照做。"
        "脚步声从背后传来，很慢，像是怕惊动什么。"
        "他没回头，只把刀握紧了半寸。"
    )
    sig = score_slop(text)
    assert sig.overall_slop_score < 0.30, f"clean prose scored {sig.overall_slop_score}"


def test_cliche_phrases_caught() -> None:
    text = (
        "他抬起头，深邃的眼眸望向远方，嘴角勾起一抹冷笑。"
        "她神色复杂地看着他，心中一凛。"
        "两人不动声色，气场全开。"
    )
    sig = score_slop(text)
    assert sig.cliche_phrase_score > 0.4
    flagged = {phrase for phrase, _ in sig.flagged_cliches}
    assert "深邃的眼眸" in flagged
    assert "嘴角勾起" in flagged
    assert "不动声色" in flagged


def test_telling_violations_caught() -> None:
    text = (
        "他感到愤怒。她感到悲伤。他很开心。她很难过。"
        "他非常震惊，她十分尴尬。"
    )
    sig = score_slop(text)
    assert sig.telling_violation_score > 0.4
    flagged = {phrase for phrase, _ in sig.flagged_tellings}
    assert "感到愤怒" in flagged
    assert "他很开心" in flagged


def test_adverb_stacking_caught() -> None:
    text = "他非常非常累，特别特别困，十分十分饿，相当相当无奈。"
    sig = score_slop(text)
    assert sig.adverb_stacking_score > 0.5
    flagged = {adv for adv, _ in sig.flagged_adverbs}
    assert "非常" in flagged
    assert "特别" in flagged


def test_overall_score_bounded() -> None:
    saturated = "深邃的眼眸" * 50 + "嘴角勾起" * 50 + "他感到愤怒" * 50
    sig = score_slop(saturated)
    assert 0.0 <= sig.overall_slop_score <= 1.0
    assert sig.cliche_phrase_score <= 1.0
    assert sig.telling_violation_score <= 1.0
    assert sig.adverb_stacking_score <= 1.0


def test_no_double_counting_with_ai_trace() -> None:
    from novel_analyzer.services.ai_trace_signal_service import score_ai_trace
    text = (
        "他感到愤怒，深邃的眼眸盯着对方。"
        "嘴角勾起一抹冷笑。气场全开。"
        "她非常震惊。"
    )
    slop = score_slop(text)
    ai_trace = score_ai_trace(text)
    slop_flagged = {phrase for phrase, _ in slop.flagged_cliches + slop.flagged_tellings}
    ai_flagged = {phrase for phrase, _ in ai_trace.flagged_hedges}
    assert not (slop_flagged & ai_flagged), (
        f"slop and ai_trace overlap: {slop_flagged & ai_flagged}"
    )


def test_signal_immutable() -> None:
    sig = score_slop("正常一句话。")
    try:
        sig.overall_slop_score = 999.0  # type: ignore[misc]
    except Exception as exc:
        assert "frozen" in str(exc).lower() or "cannot" in str(exc).lower()
        return
    raise AssertionError("SlopSignal should be frozen")
