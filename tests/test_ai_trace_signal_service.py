from __future__ import annotations

from novel_analyzer.services.ai_trace_signal_service import (
    AITraceSignal,
    score_ai_trace,
)


def test_empty_text_returns_zero_signal() -> None:
    sig = score_ai_trace("")
    assert isinstance(sig, AITraceSignal)
    assert sig.overall_ai_trace_score == 0.0
    assert sig.ngram_repetition_score == 0.0
    assert sig.sentence_uniformity_score == 0.0
    assert sig.hedge_word_density == 0.0
    assert sig.top_repeated_ngrams == []
    assert sig.flagged_hedges == []


def test_short_text_does_not_crash() -> None:
    sig = score_ai_trace("好。")
    assert sig.overall_ai_trace_score >= 0.0
    assert sig.sentence_count <= 1


def test_high_ngram_repetition_is_flagged() -> None:
    text = "卫图缓缓站起身。卫图缓缓站起身。卫图缓缓站起身。卫图缓缓站起身。"
    sig = score_ai_trace(text)
    assert sig.ngram_repetition_score > 0.3
    assert any("卫图" in gram for gram, _ in sig.top_repeated_ngrams)


def test_clean_diverse_prose_scores_low() -> None:
    text = (
        "黄昏的风掠过山顶，松针轻响。卫图坐下，望着远处的雪线。"
        "他记得师父说过的那句话，但今天还不打算照做。"
        "脚步声从背后传来，很慢，像是怕惊动什么。"
        "他没回头，只把刀握紧了半寸。"
    )
    sig = score_ai_trace(text)
    assert sig.overall_ai_trace_score < 0.55, f"clean text scored {sig.overall_ai_trace_score}"
    assert sig.sentence_count >= 4


def test_uniform_sentence_lengths_raise_uniformity_score() -> None:
    chunk = "他走过来对我说话。"
    text = "".join([chunk] * 10)
    sig = score_ai_trace(text)
    assert sig.sentence_uniformity_score >= 0.85
    assert sig.sentence_length_stats.get("cv", 1.0) < 0.15


def test_hedge_word_density_caught() -> None:
    text = (
        "他渐渐走近，缓缓抬起头，似乎想说什么，"
        "仿佛有些犹豫。然而他终究没有开口，"
        "其实他想说的话很多。"
    )
    sig = score_ai_trace(text)
    assert sig.hedge_word_density > 0.2
    flagged_words = {tell for tell, _ in sig.flagged_hedges}
    assert {"渐渐", "缓缓", "似乎", "仿佛", "然而", "其实"} & flagged_words


def test_overall_score_in_unit_interval() -> None:
    pathological = "渐渐渐渐渐渐渐渐渐渐渐渐渐渐渐渐渐渐渐渐"
    sig = score_ai_trace(pathological)
    assert 0.0 <= sig.overall_ai_trace_score <= 1.0
    assert 0.0 <= sig.ngram_repetition_score <= 1.0
    assert 0.0 <= sig.sentence_uniformity_score <= 1.0
    assert 0.0 <= sig.hedge_word_density <= 1.0


def test_signal_is_immutable_dataclass() -> None:
    sig = score_ai_trace("正常的一句话。")
    try:
        sig.overall_ai_trace_score = 999.0  # type: ignore[misc]
    except Exception as exc:
        assert "frozen" in str(exc).lower() or "cannot" in str(exc).lower()
        return
    raise AssertionError("AITraceSignal should be frozen")
