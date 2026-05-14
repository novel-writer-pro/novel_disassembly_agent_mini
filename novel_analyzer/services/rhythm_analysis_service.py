"""Loom Phase 4: Rhythm analysis service.

Computes narrative pacing signals for a chapter:
  hook_density     – hook/climax events per 1000 characters
  pacing_type      – slow_burn | action_heavy | balanced | episodic
  climax_score     – composite high-tension score (reuses TensionService data)

All metrics use existing DB data – no new LLM calls required.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from novel_analyzer.database.models import (
    ChapterArtifact,
    FactRecord,
)

HOOK_FACT_TYPES: frozenset[str] = frozenset(
    {
        "hook",
        "climax",
        "reversal",
        "revelation",
        "confrontation",
        "turning_point",
    }
)

HOOK_CONTINUITY_KEYWORDS: frozenset[str] = frozenset(
    {"钩子", "高潮", "反转", "揭示", "悬念", "冲突升级", "转折", "危机", "爆发",
     "伏笔", "后续", "下一章", "将会", "暗示", "预示", "留下", "埋下", "引出"}
)

PACING_SLOW_BURN = "slow_burn"
PACING_ACTION_HEAVY = "action_heavy"
PACING_BALANCED = "balanced"
PACING_EPISODIC = "episodic"


@dataclass
class RhythmSignal:
    branch_id: str
    chapter_index: int
    hook_density: float
    pacing_type: str
    climax_score: float
    alert_level: str  # "none" | "warn" | "critical"
    suggestion: str = ""

    def to_rhythm_signal(self) -> dict[str, object]:
        return {
            "chapter_index": self.chapter_index,
            "branch_id": self.branch_id,
            "hook_density": self.hook_density,
            "pacing_type": self.pacing_type,
            "climax_score": self.climax_score,
            "alert_level": self.alert_level,
            "suggestion": self.suggestion,
        }


class RhythmAnalysisService:
    """Compute narrative rhythm and pacing signals for a chapter."""

    HOOK_DENSITY_LOW = 1.0
    HOOK_DENSITY_HIGH = 4.0
    LOOKBACK_N = 5

    def __init__(self, session: Session) -> None:
        self.session = session

    def compute(
        self,
        branch_id: str,
        chapter_index: int,
        lookback_n: int = LOOKBACK_N,
    ) -> RhythmSignal:
        hook_density = self._compute_hook_density(branch_id, chapter_index)
        climax_score = self._compute_climax_score(branch_id, chapter_index)
        pacing_type = self._classify_pacing(branch_id, chapter_index, lookback_n)
        alert = self._classify_alert(hook_density)
        suggestion = self._build_suggestion(hook_density, alert)

        return RhythmSignal(
            branch_id=branch_id,
            chapter_index=chapter_index,
            hook_density=hook_density,
            pacing_type=pacing_type,
            climax_score=climax_score,
            alert_level=alert,
            suggestion=suggestion,
        )

    def _compute_hook_density(self, branch_id: str, chapter_index: int) -> float:
        hook_count = self.session.scalar(
            select(func.count(FactRecord.id))
            .where(FactRecord.branch_id == branch_id)
            .where(FactRecord.chapter_index == chapter_index)
            .where(FactRecord.fact_type.in_(list(HOOK_FACT_TYPES)))
            .where(FactRecord.deleted_at.is_(None))
        ) or 0

        from sqlalchemy import or_
        continuity_labels = self.session.scalars(
            select(FactRecord.label)
            .where(FactRecord.branch_id == branch_id)
            .where(FactRecord.chapter_index == chapter_index)
            .where(FactRecord.fact_type == "continuity")
            .where(FactRecord.deleted_at.is_(None))
        ).all()
        continuity_hook_count = sum(
            1 for label in continuity_labels
            if any(kw in label for kw in HOOK_CONTINUITY_KEYWORDS)
        )

        word_count = self._get_chapter_word_count(branch_id, chapter_index)
        if word_count == 0:
            return 0.0
        return round((hook_count + continuity_hook_count) / (word_count / 1000), 4)

    def _compute_climax_score(self, branch_id: str, chapter_index: int) -> float:
        hook_count = self.session.scalar(
            select(func.count(FactRecord.id))
            .where(FactRecord.branch_id == branch_id)
            .where(FactRecord.chapter_index == chapter_index)
            .where(FactRecord.fact_type.in_(list(HOOK_FACT_TYPES)))
            .where(FactRecord.deleted_at.is_(None))
        ) or 0

        continuity_labels = self.session.scalars(
            select(FactRecord.label)
            .where(FactRecord.branch_id == branch_id)
            .where(FactRecord.chapter_index == chapter_index)
            .where(FactRecord.fact_type == "continuity")
            .where(FactRecord.deleted_at.is_(None))
        ).all()
        continuity_hook_count = sum(
            1 for label in continuity_labels
            if any(kw in label for kw in HOOK_CONTINUITY_KEYWORDS)
        )

        total_count = self.session.scalar(
            select(func.count(FactRecord.id))
            .where(FactRecord.branch_id == branch_id)
            .where(FactRecord.chapter_index == chapter_index)
            .where(FactRecord.deleted_at.is_(None))
        ) or 0

        if total_count == 0:
            return 0.0
        return round((hook_count + continuity_hook_count) / total_count, 4)

    def _classify_pacing(
        self, branch_id: str, chapter_index: int, lookback_n: int
    ) -> str:
        densities: list[float] = []
        for idx in range(max(1, chapter_index - lookback_n), chapter_index + 1):
            densities.append(self._compute_hook_density(branch_id, idx))

        if not densities:
            return PACING_BALANCED

        avg = sum(densities) / len(densities)
        variance = sum((d - avg) ** 2 for d in densities) / len(densities)

        if avg < 0.5 and variance < 0.1:
            return PACING_SLOW_BURN
        if avg > 2.5:
            return PACING_ACTION_HEAVY
        if variance > 0.5:
            return PACING_BALANCED
        return PACING_EPISODIC

    def _get_chapter_word_count(self, branch_id: str, chapter_index: int) -> int:
        from novel_analyzer.database.models import RetrievalChunk as _RC
        from novel_analyzer.database.models import RetrievalDocument as _RD

        texts = self.session.scalars(
            select(_RC.text)
            .join(_RD, _RC.document_id == _RD.id)
            .where(_RD.branch_id == branch_id)
            .where(_RD.chapter_index == chapter_index)
            .where(_RC.deleted_at.is_(None))
        ).all()
        total = sum(len(t) for t in texts)
        if total > 0:
            return total

        artifact = self.session.scalar(
            select(ChapterArtifact)
            .where(ChapterArtifact.branch_id == branch_id)
            .where(ChapterArtifact.chapter_index == chapter_index)
            .where(ChapterArtifact.deleted_at.is_(None))
        )
        if artifact is None:
            return 0
        payload = artifact.payload_json or {}
        summary = str(payload.get("chapter_summary", ""))
        return max(len(summary) * 10, 500)

    def _classify_alert(self, hook_density: float) -> str:
        if hook_density < self.HOOK_DENSITY_LOW:
            return "warn"
        return "none"

    def _build_suggestion(self, hook_density: float, alert: str) -> str:
        if alert == "none":
            return ""
        return (
            f"爽点密度偏低（{hook_density}/千字），"
            "建议在本章增加情绪高点或意外反转"
        )
