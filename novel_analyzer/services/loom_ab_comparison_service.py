"""Loom carry-over A/B comparison: shadow vs enabled mode metric deltas.

T5 from kernel-sota-gap-assessment §10. The Loom carry-over experiment
runs the same chapter set twice — once with loom_memory_mode=shadow
(default, pre-Loom legacy carry-over) and once with loom_memory_mode=enabled
(Phase 1 layered memory) — then compares quality metrics across the two.

This module is the pure-function COMPARISON HALF. The operator runs both
A and B sides via writer-imitate-range with the appropriate env, collects
the resulting writer-imitate-ch*.json artifacts, and feeds them in here.
The expected metrics from kernel-sota §4.3 P0-1 are:

  character_ooc_trigger_rate  — flagged actions of type character_ooc
                                 across the chapter range; lower = better
  avg_overall_score          — mean policy_summary.overall_score; higher = better
  avg_blocking_issues        — mean policy_summary.blocking_issue_count; lower = better
  high_risk_chapter_rate     — fraction of chapters with risk_overall_level=high
  pass_verdict_rate          — fraction of chapters with final_verdict=pass

Boundary contract (matches B1/B4/B5/factscore/persona):
- Pure function; no DB, no LLM, no I/O beyond the caller's reads.
- Caller passes two lists of already-loaded payload dicts.
- Output is a frozen dataclass of metric deltas + per-side aggregates.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean
from typing import Any


@dataclass(frozen=True, slots=True)
class LoomCarryOverMetrics:
    label: str
    chapter_count: int
    character_ooc_trigger_rate: float
    avg_overall_score: float
    avg_blocking_issues: float
    high_risk_chapter_rate: float
    pass_verdict_rate: float


@dataclass(frozen=True, slots=True)
class LoomCarryOverComparison:
    side_a: LoomCarryOverMetrics
    side_b: LoomCarryOverMetrics
    delta: dict[str, float] = field(default_factory=dict)
    interpretation: list[str] = field(default_factory=list)


def _payload_metrics(payloads: list[dict[str, Any]], *, label: str) -> LoomCarryOverMetrics:
    if not payloads:
        return LoomCarryOverMetrics(
            label=label,
            chapter_count=0,
            character_ooc_trigger_rate=0.0,
            avg_overall_score=0.0,
            avg_blocking_issues=0.0,
            high_risk_chapter_rate=0.0,
            pass_verdict_rate=0.0,
        )

    n = len(payloads)
    ooc_chapters = 0
    overall_scores: list[float] = []
    blocking_counts: list[int] = []
    high_risk_count = 0
    pass_count = 0

    for payload in payloads:
        policy_obj = payload.get("policy_summary")
        policy = policy_obj if isinstance(policy_obj, dict) else {}
        issue_families = policy.get("issue_families") or []
        if isinstance(issue_families, list) and any(
            "character" in str(item).lower() or "ooc" in str(item).lower()
            for item in issue_families
        ):
            ooc_chapters += 1

        score = policy.get("overall_score")
        if isinstance(score, (int, float)):
            overall_scores.append(float(score))

        blocking = policy.get("blocking_issue_count")
        if isinstance(blocking, int):
            blocking_counts.append(blocking)

        risk_level = str(policy.get("risk_overall_level") or "").lower()
        if risk_level == "high":
            high_risk_count += 1

        verdict = str(payload.get("final_verdict") or "").lower()
        if verdict == "pass":
            pass_count += 1

    return LoomCarryOverMetrics(
        label=label,
        chapter_count=n,
        character_ooc_trigger_rate=round(ooc_chapters / n, 4),
        avg_overall_score=round(mean(overall_scores), 2) if overall_scores else 0.0,
        avg_blocking_issues=round(mean(blocking_counts), 2) if blocking_counts else 0.0,
        high_risk_chapter_rate=round(high_risk_count / n, 4),
        pass_verdict_rate=round(pass_count / n, 4),
    )


def compare_carry_over_modes(
    side_a_payloads: list[dict[str, Any]],
    side_b_payloads: list[dict[str, Any]],
    *,
    side_a_label: str = "shadow",
    side_b_label: str = "enabled",
) -> LoomCarryOverComparison:
    a = _payload_metrics(side_a_payloads, label=side_a_label)
    b = _payload_metrics(side_b_payloads, label=side_b_label)

    delta = {
        "character_ooc_trigger_rate": round(
            b.character_ooc_trigger_rate - a.character_ooc_trigger_rate, 4
        ),
        "avg_overall_score": round(b.avg_overall_score - a.avg_overall_score, 2),
        "avg_blocking_issues": round(b.avg_blocking_issues - a.avg_blocking_issues, 2),
        "high_risk_chapter_rate": round(
            b.high_risk_chapter_rate - a.high_risk_chapter_rate, 4
        ),
        "pass_verdict_rate": round(b.pass_verdict_rate - a.pass_verdict_rate, 4),
    }

    interpretation: list[str] = []
    if delta["character_ooc_trigger_rate"] < -0.05:
        interpretation.append(
            f"{side_b_label} reduces character_ooc trigger rate by "
            f"{abs(delta['character_ooc_trigger_rate'] * 100):.1f}pp"
        )
    elif delta["character_ooc_trigger_rate"] > 0.05:
        interpretation.append(
            f"WARNING: {side_b_label} INCREASES character_ooc rate by "
            f"{delta['character_ooc_trigger_rate'] * 100:.1f}pp"
        )

    if delta["avg_overall_score"] > 2.0:
        interpretation.append(
            f"{side_b_label} raises avg overall_score by {delta['avg_overall_score']:.1f}"
        )
    elif delta["avg_overall_score"] < -2.0:
        interpretation.append(
            f"WARNING: {side_b_label} LOWERS avg overall_score by "
            f"{abs(delta['avg_overall_score']):.1f}"
        )

    if delta["pass_verdict_rate"] > 0.05:
        interpretation.append(
            f"{side_b_label} improves pass_verdict_rate by "
            f"{delta['pass_verdict_rate'] * 100:.1f}pp"
        )
    elif delta["pass_verdict_rate"] < -0.05:
        interpretation.append(
            f"WARNING: {side_b_label} REDUCES pass_verdict_rate by "
            f"{abs(delta['pass_verdict_rate'] * 100):.1f}pp"
        )

    if not interpretation:
        interpretation.append(
            f"No statistically meaningful delta between {side_a_label} and {side_b_label}"
        )

    return LoomCarryOverComparison(
        side_a=a,
        side_b=b,
        delta=delta,
        interpretation=interpretation,
    )
