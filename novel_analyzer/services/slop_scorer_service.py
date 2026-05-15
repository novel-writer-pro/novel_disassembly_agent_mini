"""Mechanical slop scoring — DIAGNOSTIC ONLY, weak signal in current corpus.

⚠️  Validation result (2026-05-15, n=507 production drafts):
   B4 effect size is below noise floor. needs_revision mean = 0.006,
   pass mean = 0.002. Median is 0.000 across both groups. The
   imitation harness already scrubs the obvious slop upstream via
   stage-merged prompts, so this scorer rarely fires on harness
   output. Wiring as a GateChecker would add no signal.
   May still be useful on RAW LLM output or user-pasted drafts.
   See: docs/research/heuristic-scorer-validation-findings-20260515.md

Inspired by autonovel/evaluate.py mechanical-layer slop detection. Three
signals orthogonal to ai_trace_signal_service:

  cliche_phrase_score      — density of well-known Chinese web-novel
                              cliché phrases (深邃的眼眸 / 嘴角勾起 /
                              不动声色 / 妖孽般的容颜 / ...). Curated
                              list, not exhaustive — catches the loudest
                              tells without false-positiving on legit prose.
  telling_violation_score  — frequency of "show-don't-tell" violations:
                              direct emotion declarations like "他很愤怒"
                              "她非常开心" instead of showing through
                              actions. Heuristic but high-signal.
  adverb_stacking_score    — degree-adverb pile-up (非常/极其/十分/
                              特别 within short windows). High = lazy
                              intensification.

Calibrated distribution against 507 real drafts (does NOT imply quality):

  median = 0.00   p90 = 0.018   p95 = 0.028   p99 = 0.049   max = 0.10

Run ``scripts/dev/heuristic-scorer-benchmark.py`` to refresh the
distribution after material changes to LLM provider or prompt set.

Boundary contract (same as ai_trace_signal_service):
- Pure functions; no DB, no LLM, no I/O.
- Input: plain str chapter text. Output: frozen dataclass.
- Never raises; returns zeroed scores on empty input.
- Cheap: O(n × |patterns|) where n = char count, patterns ~= 80.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_CLICHE_PHRASES: tuple[str, ...] = (
    "深邃的眼眸", "深邃的眸子", "深邃的目光", "深邃的眼神",
    "完美的身材", "魔鬼般的身材", "妖孽般的容颜", "倾国倾城",
    "嘴角勾起", "嘴角微扬", "嘴角扯出", "嘴角浮现",
    "不动声色", "面无表情", "神色复杂", "眼神复杂",
    "心头一紧", "心中一凛", "心中一震", "心中一惊",
    "鬼魅般", "幽灵般", "如同鬼魅",
    "毫不犹豫", "毫不留情", "毫无征兆",
    "突如其来", "猝不及防", "措手不及",
    "波澜不惊", "云淡风轻", "风轻云淡",
    "气场全开", "气势汹汹",
    "霸道总裁", "高冷男神",
)

_TELLING_PATTERNS: tuple[str, ...] = (
    "感到", "感受到", "觉得自己",
    "他很", "她很", "他非常", "她非常",
    "他十分", "她十分", "他相当", "她相当",
)

_TELLING_EMOTIONS: tuple[str, ...] = (
    "愤怒", "生气", "开心", "高兴", "快乐", "悲伤", "难过",
    "害怕", "恐惧", "紧张", "兴奋", "激动", "失望", "痛苦",
    "震惊", "惊讶", "无奈", "尴尬", "羞愧", "得意",
)

_DEGREE_ADVERBS: tuple[str, ...] = (
    "非常", "极其", "十分", "特别", "相当",
    "格外", "异常", "无比", "极度", "极为",
)

_ADVERB_WINDOW = 80


def _chinese_chars(text: str) -> str:
    return "".join(ch for ch in text if "\u4e00" <= ch <= "\u9fff")


@dataclass(frozen=True, slots=True)
class SlopSignal:
    overall_slop_score: float
    cliche_phrase_score: float
    telling_violation_score: float
    adverb_stacking_score: float
    flagged_cliches: list[tuple[str, int]] = field(default_factory=list)
    flagged_tellings: list[tuple[str, int]] = field(default_factory=list)
    flagged_adverbs: list[tuple[str, int]] = field(default_factory=list)
    char_count: int = 0


def _cliche_phrase_score(text: str) -> tuple[float, list[tuple[str, int]]]:
    chinese_total = len(_chinese_chars(text))
    if chinese_total == 0:
        return 0.0, []
    hits: list[tuple[str, int]] = []
    char_hits = 0
    for phrase in _CLICHE_PHRASES:
        count = text.count(phrase)
        if count > 0:
            hits.append((phrase, count))
            char_hits += count * len(phrase)
    score = min(1.0, char_hits * 12.0 / chinese_total)
    hits.sort(key=lambda item: (-item[1], -len(item[0]), item[0]))
    return score, hits[:10]


def _telling_violation_score(text: str) -> tuple[float, list[tuple[str, int]]]:
    chinese_total = len(_chinese_chars(text))
    if chinese_total == 0:
        return 0.0, []
    hits_counter: dict[str, int] = {}
    total = 0
    for prefix in _TELLING_PATTERNS:
        for emotion in _TELLING_EMOTIONS:
            phrase = prefix + emotion
            count = text.count(phrase)
            if count > 0:
                hits_counter[phrase] = count
                total += count
    score = min(1.0, total * 60.0 / chinese_total)
    hits = sorted(hits_counter.items(), key=lambda item: (-item[1], item[0]))[:10]
    return score, hits


def _adverb_stacking_score(text: str) -> tuple[float, list[tuple[str, int]]]:
    chinese_total = len(_chinese_chars(text))
    if chinese_total == 0:
        return 0.0, []
    pattern = "|".join(re.escape(adv) for adv in _DEGREE_ADVERBS)
    matches = list(re.finditer(pattern, text))
    if not matches:
        return 0.0, []
    counter: dict[str, int] = {}
    for match in matches:
        word = match.group(0)
        counter[word] = counter.get(word, 0) + 1
    stacking_pairs = 0
    for i in range(1, len(matches)):
        if matches[i].start() - matches[i - 1].end() <= _ADVERB_WINDOW:
            stacking_pairs += 1
    base_density = sum(counter.values()) * 12.0 / chinese_total
    stacking_bonus = stacking_pairs * 24.0 / chinese_total
    score = min(1.0, base_density + stacking_bonus)
    hits = sorted(counter.items(), key=lambda item: (-item[1], item[0]))[:10]
    return score, hits


def score_slop(text: str) -> SlopSignal:
    if not text or not text.strip():
        return SlopSignal(
            overall_slop_score=0.0,
            cliche_phrase_score=0.0,
            telling_violation_score=0.0,
            adverb_stacking_score=0.0,
        )
    cliche, cliche_hits = _cliche_phrase_score(text)
    telling, telling_hits = _telling_violation_score(text)
    adverb, adverb_hits = _adverb_stacking_score(text)
    overall = round(0.45 * cliche + 0.35 * telling + 0.20 * adverb, 4)
    return SlopSignal(
        overall_slop_score=overall,
        cliche_phrase_score=round(cliche, 4),
        telling_violation_score=round(telling, 4),
        adverb_stacking_score=round(adverb, 4),
        flagged_cliches=cliche_hits,
        flagged_tellings=telling_hits,
        flagged_adverbs=adverb_hits,
        char_count=len(_chinese_chars(text)),
    )
