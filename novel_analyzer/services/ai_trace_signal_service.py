"""AI-trace detection: pure heuristic scoring for "AI-flavored" prose.

Inspired by the 33-dimension audit pattern from the inkos project. Three
deterministic signals, no LLM calls, no DB dependency:

  ngram_repetition_score    — fraction of bigrams/trigrams that recur,
                               weighted by length. High = LLM-typical
                               vocabulary loops.
  sentence_uniformity_score — coefficient of variation of sentence
                               lengths inverted. High = uniform = LLM-typical
                               (real prose has bursty short/long mix).
  hedge_word_density        — frequency of common Chinese AI tells:
                               hedge adverbs (渐渐/缓缓/似乎), excessive
                               similes (仿佛/宛如/犹如), and contrastive
                               connectors (然而/不过/但是).

The composite ``overall_ai_trace_score`` is a 0-1 number. Calibrated
against 507 real production imitation drafts (2026-05-15):

  median = 0.19   p90 = 0.24   p95 = 0.25   p99 = 0.27   max = 0.57

Thresholds derived from real-data calibration (NOT from theoretical
"feels right" levels):

  >= 0.24 — warn, deserves reviewer attention
  >= 0.30 — alert, almost certainly a vocabulary-loop draft

Run ``scripts/dev/heuristic-scorer-benchmark.py`` to refresh the
distribution after material changes to LLM provider or prompt set.

Boundary contract:
- Pure functions; safe to call from any layer (service, CLI, test).
- Input is plain str (chapter draft text). No FactRecord / artifact dep.
- Output is a frozen dataclass; callers serialize as needed.
- Never raises on empty/odd input — returns zeroed scores.
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field

_SENTENCE_TERMINATORS = "。！？；!?;"
_HEDGE_TELLS: tuple[str, ...] = (
    "渐渐", "缓缓", "悄悄", "默默", "微微", "轻轻", "淡淡",
    "似乎", "仿佛", "宛如", "犹如", "好像", "如同",
    "然而", "不过", "但是", "可是", "只是",
    "其实", "事实上", "毫无疑问", "无可置疑",
    "深邃", "深刻", "复杂",
)

_NGRAM_MIN_LEN = 2
_NGRAM_MAX_LEN = 4
_REPETITION_MIN_COUNT = 3


@dataclass(frozen=True, slots=True)
class AITraceSignal:
    """Output of :func:`score_ai_trace`. Lower is better (less AI-flavored)."""

    overall_ai_trace_score: float
    ngram_repetition_score: float
    sentence_uniformity_score: float
    hedge_word_density: float
    top_repeated_ngrams: list[tuple[str, int]] = field(default_factory=list)
    sentence_length_stats: dict[str, float] = field(default_factory=dict)
    flagged_hedges: list[tuple[str, int]] = field(default_factory=list)
    sentence_count: int = 0
    char_count: int = 0


def _split_sentences(text: str) -> list[str]:
    pattern = f"[{re.escape(_SENTENCE_TERMINATORS)}]+"
    parts = [seg.strip() for seg in re.split(pattern, text) if seg.strip()]
    return parts


def _chinese_chars(text: str) -> str:
    return "".join(ch for ch in text if "\u4e00" <= ch <= "\u9fff")


def _ngram_counts(text: str, *, n: int) -> dict[str, int]:
    chars = _chinese_chars(text)
    if len(chars) < n:
        return {}
    counts: dict[str, int] = {}
    for i in range(len(chars) - n + 1):
        gram = chars[i:i + n]
        counts[gram] = counts.get(gram, 0) + 1
    return counts


def _ngram_repetition_score(text: str) -> tuple[float, list[tuple[str, int]]]:
    chars_total = len(_chinese_chars(text))
    if chars_total < _NGRAM_MIN_LEN:
        return 0.0, []

    repeated: dict[str, int] = {}
    weighted_sum = 0.0
    coverage_total = 0.0

    for n in range(_NGRAM_MIN_LEN, _NGRAM_MAX_LEN + 1):
        counts = _ngram_counts(text, n=n)
        for gram, count in counts.items():
            if count >= _REPETITION_MIN_COUNT:
                if count > repeated.get(gram, 0):
                    repeated[gram] = count
                weighted_sum += (count - 1) * n
        coverage_total += max(0, chars_total - n + 1)

    if coverage_total == 0:
        return 0.0, []

    score = min(1.0, weighted_sum / coverage_total)
    top = sorted(repeated.items(), key=lambda item: (-item[1], -len(item[0]), item[0]))[:10]
    return score, top


def _sentence_uniformity_score(text: str) -> tuple[float, dict[str, float], int]:
    sentences = _split_sentences(text)
    if len(sentences) < 3:
        return 0.0, {}, len(sentences)

    lengths = [len(_chinese_chars(s)) for s in sentences if _chinese_chars(s)]
    if len(lengths) < 3:
        return 0.0, {}, len(sentences)

    mean_len = statistics.mean(lengths)
    if mean_len <= 0:
        return 0.0, {}, len(sentences)

    stdev = statistics.pstdev(lengths)
    cv = stdev / mean_len if mean_len else 0.0
    uniformity = max(0.0, min(1.0, 1.0 - cv))
    stats = {
        "mean": round(mean_len, 2),
        "stdev": round(stdev, 2),
        "min": float(min(lengths)),
        "max": float(max(lengths)),
        "cv": round(cv, 3),
    }
    return uniformity, stats, len(sentences)


def _hedge_word_density(text: str) -> tuple[float, list[tuple[str, int]]]:
    chinese_total = len(_chinese_chars(text))
    if chinese_total == 0:
        return 0.0, []

    hits: list[tuple[str, int]] = []
    char_hits = 0
    for tell in _HEDGE_TELLS:
        count = text.count(tell)
        if count > 0:
            hits.append((tell, count))
            char_hits += count * len(tell)

    density = min(1.0, char_hits * 8.0 / chinese_total)
    hits.sort(key=lambda item: (-item[1], item[0]))
    return density, hits[:10]


def score_ai_trace(text: str) -> AITraceSignal:
    if not text or not text.strip():
        return AITraceSignal(
            overall_ai_trace_score=0.0,
            ngram_repetition_score=0.0,
            sentence_uniformity_score=0.0,
            hedge_word_density=0.0,
        )

    rep_score, top_ngrams = _ngram_repetition_score(text)
    uniformity, sent_stats, sent_count = _sentence_uniformity_score(text)
    hedge, hedge_hits = _hedge_word_density(text)

    overall = round(0.45 * rep_score + 0.30 * uniformity + 0.25 * hedge, 4)

    return AITraceSignal(
        overall_ai_trace_score=overall,
        ngram_repetition_score=round(rep_score, 4),
        sentence_uniformity_score=round(uniformity, 4),
        hedge_word_density=round(hedge, 4),
        top_repeated_ngrams=top_ngrams,
        sentence_length_stats=sent_stats,
        flagged_hedges=hedge_hits,
        sentence_count=sent_count,
        char_count=len(_chinese_chars(text)),
    )
