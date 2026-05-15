"""Pure helper functions for the imitation harness controller.

Extracted from imitation_harness_service.py during the T4 split. These
functions are stateless decision logic — severity/priority classification,
issue-family routing, action sorting, stop-reason aggregation, and revise
payload assembly — separated from the orchestrator class so they can be
unit-tested directly and reused without instantiating the service.

The class still exposes them as @staticmethod aliases for backward
compatibility with tests that monkeypatch or call
``HarnessControllerService._aggregate_stop_reason(...)`` directly.
"""

from __future__ import annotations

import json

from novel_analyzer.domain.schemas import (
    ChapterImitationDraft,
    ChapterImitationGateReport,
    ChapterImitationHarnessAction,
    ChapterImitationPreflightReport,
    ChapterImitationReviewReport,
    ChapterImitationRiskReport,
    ChapterImitationScoreReport,
)


def severity_priority(status: str, *, risk_level: str | None = None) -> tuple[str, int]:
    if status == "block":
        return ("high", 1)
    if risk_level == "high":
        return ("high", 1)
    if risk_level == "medium":
        return ("medium", 2)
    if status == "warn":
        return ("medium", 2)
    return ("low", 4)


def issue_family_for_action(action_type: str) -> str:
    lowered = action_type.lower()
    if "constraint" in lowered:
        return "constraint"
    if "relationship" in lowered or "relation" in lowered:
        return "relationship"
    if "rule" in lowered:
        return "rule"
    if "motivation" in lowered:
        return "motivation"
    if "hook" in lowered:
        return "hook"
    if "style" in lowered or "prose" in lowered:
        return "style"
    if "rhythm" in lowered:
        return "rhythm"
    if "reader" in lowered:
        return "reader_sim"
    if "dialogue" in lowered:
        return "dialogue"
    if "research" in lowered:
        return "research"
    return "general"


def family_sort_rank(action_type: str) -> int:
    family = issue_family_for_action(action_type)
    if family in {"style", "rhythm", "reader_sim", "dialogue"}:
        return 0
    return 1


def sorted_actions(
    actions: list[ChapterImitationHarnessAction],
) -> list[ChapterImitationHarnessAction]:
    severity_rank = {"high": 0, "medium": 1, "low": 2}
    return sorted(
        actions,
        key=lambda item: (
            item.priority,
            family_sort_rank(item.action_type),
            severity_rank.get(item.severity, 3),
            item.action_type,
            item.target,
        ),
    )


def aggregate_stop_reason(
    *,
    preflight: ChapterImitationPreflightReport,
    gate: ChapterImitationGateReport,
    risk: ChapterImitationRiskReport,
    score: ChapterImitationScoreReport,
    actions: list[ChapterImitationHarnessAction],
) -> tuple[str, str]:
    critical_actions = [
        item for item in actions
        if item.priority == 1 and item.severity in {"high", "critical"}
    ]
    gate_aligned = gate.overall_verdict != "needs_revision"
    risk_low = risk.overall_risk_level == "low"
    no_blocking = len(preflight.blocking_issues) == 0

    if (
        preflight.overall_verdict == "pass"
        and gate_aligned
        and risk_low
        and score.overall_score >= 80
        and not critical_actions
    ):
        return ("pass", "harness_quality_threshold_reached")
    if (
        gate_aligned
        and risk_low
        and no_blocking
        and score.overall_score >= 75
        and not critical_actions
    ):
        return ("pass", "harness_soft_pass")
    if critical_actions:
        return ("needs_revision", "critical_action_required")
    if risk.overall_risk_level != "low":
        return ("needs_revision", "risk_revision_required")
    if gate.overall_verdict == "needs_revision":
        return ("needs_revision", "gate_revision_required")
    return ("needs_revision", "quality_iteration_required")


def build_revise_payload(
    *,
    actions: list[ChapterImitationHarnessAction],
    preflight: ChapterImitationPreflightReport,
    gate: ChapterImitationGateReport,
    risk: ChapterImitationRiskReport,
) -> dict[str, object]:
    return {
        "ordered_actions": [
            {
                "action_type": item.action_type,
                "issue_family": issue_family_for_action(item.action_type),
                "target": item.target,
                "severity": item.severity,
                "priority": item.priority,
                "instructions": item.instructions,
            }
            for item in actions
        ],
        "blocking_issues": preflight.blocking_issues,
        "recommended_actions": preflight.recommended_actions,
        "gate_verdict": gate.overall_verdict,
        "risk_overall_level": risk.overall_risk_level,
        "issue_families": [
            issue_family_for_action(item.action_type) for item in actions
        ],
    }


def apply_actions_to_draft(
    draft: ChapterImitationDraft,
    *,
    review: ChapterImitationReviewReport,
    preflight: ChapterImitationPreflightReport,
    actions: list[ChapterImitationHarnessAction],
    base_reviser,
) -> ChapterImitationDraft:
    revised = base_reviser(draft, review=review)
    revise_payload = build_revise_payload(
        actions=actions,
        preflight=preflight,
        gate=ChapterImitationGateReport(
            source_chapter_index=draft.source_chapter_index,
            draft_title=draft.draft_title,
        ),
        risk=ChapterImitationRiskReport(
            source_chapter_index=draft.source_chapter_index,
            draft_title=draft.draft_title,
        ),
    )
    return revised.model_copy(
        update={
            "risk_gate_notes": revised.risk_gate_notes + preflight.recommended_actions[:3],
            "comparison_notes": revised.comparison_notes
            + [f"ACTION:{item.action_type}:{item.target}" for item in actions[:4]]
            + [json.dumps(revise_payload, ensure_ascii=False)[:300]],
            "action_queue": list(actions[:6]),
            "is_scaffold_only": draft.is_scaffold_only,
        }
    )


def policy_summary(
    *,
    preflight: ChapterImitationPreflightReport,
    gate: ChapterImitationGateReport,
    risk: ChapterImitationRiskReport,
    score: ChapterImitationScoreReport,
    actions: list[ChapterImitationHarnessAction],
    final_verdict: str,
    stop_reason: str,
) -> dict[str, object]:
    highest_priority = min((item.priority for item in actions), default=4)
    highest_severity = "low"
    for item in actions:
        if item.severity == "high":
            highest_severity = "high"
            break
        if item.severity == "medium":
            highest_severity = "medium"
    issue_families = [issue_family_for_action(item.action_type) for item in actions]
    return {
        "final_verdict": final_verdict,
        "stop_reason": stop_reason,
        "highest_action_priority": highest_priority,
        "highest_action_severity": highest_severity,
        "action_count": len(actions),
        "weak_lane_action_count": sum(
            1 for item in actions if family_sort_rank(item.action_type) == 0
        ),
        "blocking_issue_count": len(preflight.blocking_issues),
        "recommended_action_count": len(preflight.recommended_actions),
        "gate_verdict": gate.overall_verdict,
        "risk_overall_level": risk.overall_risk_level,
        "overall_score": score.overall_score,
        "issue_families": issue_families,
    }


__all__ = [
    "aggregate_stop_reason",
    "apply_actions_to_draft",
    "build_revise_payload",
    "family_sort_rank",
    "issue_family_for_action",
    "policy_summary",
    "severity_priority",
    "sorted_actions",
]
