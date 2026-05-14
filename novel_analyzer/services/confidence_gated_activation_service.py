"""Confidence-gated checker activation: dynamic checker thresholds.

Adjusts which risk checkers run and their severity thresholds based on
the calibrated confidence of facts in the current chapter. Low-confidence
chapters get stricter checking; high-confidence chapters skip redundant checks.
"""

from __future__ import annotations

from dataclasses import dataclass

from novel_analyzer.database.models import FactRecord


@dataclass(frozen=True, slots=True)
class CheckerGateDecision:
    checker_name: str
    should_run: bool
    severity_boost: float
    reason: str


class ConfidenceGatedActivationService:
    """Decides which checkers to activate based on chapter fact confidence profile."""

    HIGH_CONFIDENCE_THRESHOLD = 0.75
    LOW_CONFIDENCE_THRESHOLD = 0.4
    SKIP_THRESHOLD = 0.85

    @classmethod
    def gate_checkers(
        cls,
        facts: list[FactRecord],
        checker_names: list[str],
    ) -> dict[str, CheckerGateDecision]:
        """Determine activation and severity boost for each checker."""
        if not facts:
            return {
                name: CheckerGateDecision(
                    checker_name=name, should_run=True,
                    severity_boost=0.2, reason='no facts available, run all checkers strictly',
                )
                for name in checker_names
            }

        avg_confidence = sum(f.confidence for f in facts) / len(facts)
        low_confidence_ratio = sum(
            1 for f in facts if f.confidence < cls.LOW_CONFIDENCE_THRESHOLD
        ) / len(facts)

        decisions: dict[str, CheckerGateDecision] = {}
        for name in checker_names:
            if avg_confidence >= cls.SKIP_THRESHOLD and low_confidence_ratio < 0.1:
                if name in ('power_scaling_consistency', 'setting_scope_consistency'):
                    decisions[name] = CheckerGateDecision(
                        checker_name=name, should_run=False,
                        severity_boost=0.0,
                        reason=f'avg confidence {avg_confidence:.2f} above skip threshold',
                    )
                    continue

            severity_boost = 0.0
            if avg_confidence < cls.LOW_CONFIDENCE_THRESHOLD:
                severity_boost = 0.3
            elif low_confidence_ratio > 0.5:
                severity_boost = 0.2
            elif avg_confidence < cls.HIGH_CONFIDENCE_THRESHOLD:
                severity_boost = 0.1

            decisions[name] = CheckerGateDecision(
                checker_name=name, should_run=True,
                severity_boost=severity_boost,
                reason=f'avg_conf={avg_confidence:.2f}, low_ratio={low_confidence_ratio:.2f}',
            )

        return decisions

    @classmethod
    def should_escalate_to_human(
        cls,
        facts: list[FactRecord],
        risk_count: int,
    ) -> bool:
        """Determine if the chapter should be escalated based on confidence + risk density."""
        if not facts:
            return risk_count > 0

        avg_confidence = sum(f.confidence for f in facts) / len(facts)
        if avg_confidence < cls.LOW_CONFIDENCE_THRESHOLD and risk_count >= 2:
            return True
        if risk_count >= 5:
            return True
        return False
