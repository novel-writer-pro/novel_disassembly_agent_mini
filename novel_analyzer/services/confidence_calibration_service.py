"""Confidence calibration: cross-chapter evidence-based scoring.

Adjusts fact confidence scores based on:
- Evidence quantity and quality (more evidence = higher confidence)
- Cross-chapter corroboration (fact mentioned in multiple chapters = boost)
- Recency decay (very old uncorroborated facts decay slightly)
- Contradiction penalty (facts with known conflicts get penalized)
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from novel_analyzer.database.models import FactRecord, GraphNode


@dataclass(frozen=True, slots=True)
class CalibrationResult:
    original_confidence: float
    calibrated_confidence: float
    factors: dict[str, float]


class ConfidenceCalibrationService:
    """Calibrates fact confidence using cross-chapter signals."""

    EVIDENCE_WEIGHT = 0.25
    CORROBORATION_WEIGHT = 0.30
    RECENCY_WEIGHT = 0.20
    CONTRADICTION_PENALTY = 0.25

    def __init__(self, session: Session) -> None:
        self.session = session

    def calibrate_chapter_facts(
        self,
        branch_id: str,
        chapter_index: int,
    ) -> dict[str, CalibrationResult]:
        facts = self.session.scalars(
            select(FactRecord)
            .where(FactRecord.branch_id == branch_id)
            .where(FactRecord.chapter_index == chapter_index)
        ).all()

        if not facts:
            return {}

        corroboration_map = self._batch_corroboration(branch_id, facts)
        contradiction_map = self._batch_contradiction(branch_id, facts)

        results: dict[str, CalibrationResult] = {}
        for fact in facts:
            calibrated = self._calibrate_single(
                chapter_index, fact, corroboration_map, contradiction_map,
            )
            results[fact.label] = calibrated
            fact.confidence = calibrated.calibrated_confidence

        self.session.flush()
        return results

    def calibrate_branch_facts(
        self,
        branch_id: str,
        up_to_chapter: int,
    ) -> int:
        facts = self.session.scalars(
            select(FactRecord)
            .where(FactRecord.branch_id == branch_id)
            .where(FactRecord.chapter_index <= up_to_chapter)
        ).all()

        if not facts:
            return 0

        corroboration_map = self._batch_corroboration(branch_id, facts)
        contradiction_map = self._batch_contradiction(branch_id, facts)

        updated = 0
        for fact in facts:
            result = self._calibrate_single(
                up_to_chapter, fact, corroboration_map, contradiction_map,
            )
            if abs(result.calibrated_confidence - result.original_confidence) > 0.01:
                fact.confidence = result.calibrated_confidence
                updated += 1

        self.session.flush()
        return updated

    def _batch_corroboration(
        self,
        branch_id: str,
        facts: list[FactRecord],
    ) -> dict[str, int]:
        labels = list({f.label for f in facts})
        if not labels:
            return {}
        rows = self.session.execute(
            select(FactRecord.label, func.count(FactRecord.id))
            .where(FactRecord.branch_id == branch_id)
            .where(FactRecord.label.in_(labels))
            .group_by(FactRecord.label)
        ).all()
        return {str(row[0]): int(row[1]) for row in rows}

    def _batch_contradiction(
        self,
        branch_id: str,
        facts: list[FactRecord],
    ) -> dict[str, str]:
        labels = list({f.label for f in facts})
        if not labels:
            return {}
        nodes = self.session.scalars(
            select(GraphNode)
            .where(GraphNode.branch_id == branch_id)
            .where(GraphNode.label.in_(labels))
        ).all()
        return {node.label: node.conflict_status for node in nodes}

    def _calibrate_single(
        self,
        current_chapter: int,
        fact: FactRecord,
        corroboration_map: dict[str, int],
        contradiction_map: dict[str, str],
    ) -> CalibrationResult:
        original = fact.confidence
        factors: dict[str, float] = {}

        evidence_score = self._evidence_factor(fact)
        factors['evidence'] = evidence_score

        corroboration_score = self._corroboration_factor_from_map(
            corroboration_map, fact.label,
        )
        factors['corroboration'] = corroboration_score

        recency_score = self._recency_factor(fact.chapter_index, current_chapter)
        factors['recency'] = recency_score

        contradiction_score = self._contradiction_factor_from_map(
            contradiction_map, fact.label,
        )
        factors['contradiction'] = contradiction_score

        calibrated = (
            self.EVIDENCE_WEIGHT * evidence_score
            + self.CORROBORATION_WEIGHT * corroboration_score
            + self.RECENCY_WEIGHT * recency_score
            - self.CONTRADICTION_PENALTY * (1.0 - contradiction_score)
        )
        calibrated = max(0.05, min(0.99, calibrated))

        return CalibrationResult(
            original_confidence=original,
            calibrated_confidence=calibrated,
            factors=factors,
        )

    @staticmethod
    def _evidence_factor(fact: FactRecord) -> float:
        evidence_list = fact.evidence_list or []
        count = len(evidence_list)
        if count == 0:
            return 0.2
        if count == 1:
            return 0.5
        if count == 2:
            return 0.7
        return min(0.9, 0.7 + 0.05 * (count - 2))

    @staticmethod
    def _corroboration_factor_from_map(corroboration_map: dict[str, int], label: str) -> float:
        mention_count = corroboration_map.get(label, 0)
        if mention_count <= 1:
            return 0.3
        if mention_count == 2:
            return 0.6
        if mention_count <= 4:
            return 0.8
        return 0.95

    @staticmethod
    def _recency_factor(fact_chapter: int, current_chapter: int) -> float:
        age = current_chapter - fact_chapter
        if age <= 3:
            return 0.9
        if age <= 10:
            return 0.7
        if age <= 30:
            return 0.5
        return 0.3

    @staticmethod
    def _contradiction_factor_from_map(contradiction_map: dict[str, str], label: str) -> float:
        status = contradiction_map.get(label)
        if status is None or status == 'clean':
            return 1.0
        if status == 'evolution':
            return 0.7
        if status == 'ambiguity':
            return 0.5
        if status == 'contradiction':
            return 0.2
        return 0.8
