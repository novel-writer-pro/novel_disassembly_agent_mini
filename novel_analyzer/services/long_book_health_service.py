"""Loom Phase 5: Long-book health monitoring service.

Detects quality degradation over a sliding window of chapters and
suggests carry_over recomposition when quality drops consistently.

All data comes from existing writer-imitate artifacts – no new LLM calls.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from novel_analyzer.database.models import ChapterArtifact

_DECLINE_WINDOW = 3
_HEALTH_WARN_THRESHOLD = 0.50
_HEALTH_CRITICAL_THRESHOLD = 0.35


@dataclass
class LongBookHealthReport:
    branch_id: str
    as_of_chapter: int
    health_score: float
    alert_level: str  # "none" | "warn" | "critical"
    quality_trend: str  # "stable" | "declining" | "recovering"
    recent_quality_scores: list[float] = field(default_factory=list)
    suggestion: str = ""

    def to_health_signal(self) -> dict[str, object]:
        return {
            "branch_id": self.branch_id,
            "as_of_chapter": self.as_of_chapter,
            "chapter_index": self.as_of_chapter,
            "health_score": self.health_score,
            "alert_level": self.alert_level,
            "quality_trend": self.quality_trend,
            "recent_quality_scores": self.recent_quality_scores,
            "suggestion": self.suggestion,
        }


class LongBookHealthService:
    """Monitor long-book quality health from chapter artifact data."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def compute_health(
        self,
        branch_id: str,
        as_of_chapter: int,
        lookback_n: int = 10,
    ) -> LongBookHealthReport:
        quality_scores = self._get_recent_quality_scores(
            branch_id, as_of_chapter, lookback_n
        )

        if not quality_scores:
            quality_scores = self._get_reader_sim_scores(branch_id, as_of_chapter, lookback_n)

        if not quality_scores:
            return LongBookHealthReport(
                branch_id=branch_id,
                as_of_chapter=as_of_chapter,
                health_score=1.0,
                alert_level="none",
                quality_trend="stable",
            )

        health_score = round(sum(quality_scores) / len(quality_scores), 4)
        trend = self._classify_trend(quality_scores)
        alert = self._classify_alert(health_score, trend)
        suggestion = self._build_suggestion(health_score, trend, alert)

        return LongBookHealthReport(
            branch_id=branch_id,
            as_of_chapter=as_of_chapter,
            health_score=health_score,
            alert_level=alert,
            quality_trend=trend,
            recent_quality_scores=quality_scores,
            suggestion=suggestion,
        )

    def detect_quality_decline(
        self,
        branch_id: str,
        as_of_chapter: int,
    ) -> bool:
        scores = self._get_recent_quality_scores(branch_id, as_of_chapter, _DECLINE_WINDOW)
        if len(scores) < _DECLINE_WINDOW:
            return False
        return all(scores[i] < scores[i - 1] for i in range(1, len(scores)))

    def _get_recent_quality_scores(
        self,
        branch_id: str,
        as_of_chapter: int,
        lookback_n: int,
    ) -> list[float]:
        artifacts = self.session.execute(
            select(ChapterArtifact.chapter_index, ChapterArtifact.payload_json)
            .where(ChapterArtifact.branch_id == branch_id)
            .where(ChapterArtifact.chapter_index <= as_of_chapter)
            .where(ChapterArtifact.chapter_index > as_of_chapter - lookback_n)
            .where(ChapterArtifact.deleted_at.is_(None))
            .order_by(ChapterArtifact.chapter_index)
        ).all()

        scores: list[float] = []
        for row in artifacts:
            payload = row.payload_json or {}
            score = payload.get("chapter_quality_score")
            if isinstance(score, (int, float)):
                scores.append(float(score))
        return scores

    def _get_reader_sim_scores(
        self, branch_id: str, as_of_chapter: int, lookback_n: int
    ) -> list[float]:
        try:
            from novel_analyzer.database.models import FactRecord as _FR
            has_data = self.session.scalar(
                select(func.count(_FR.id))
                .where(_FR.branch_id == branch_id)
                .where(_FR.chapter_index <= as_of_chapter)
                .where(_FR.deleted_at.is_(None))
            ) or 0
            if has_data == 0:
                return []
            from novel_analyzer.services.reader_simulation_service import ReaderSimulationService
            reader_svc = ReaderSimulationService(self.session)
            scores: list[float] = []
            for ch in range(max(1, as_of_chapter - lookback_n + 1), as_of_chapter + 1):
                result = reader_svc.simulate_all_panels(branch_id, ch)
                scores.append(result.overall_score)
            return scores
        except Exception:  # noqa: BLE001
            return []

    def _classify_trend(self, scores: list[float]) -> str:
        if len(scores) < 2:
            return "stable"
        recent = scores[-_DECLINE_WINDOW:] if len(scores) >= _DECLINE_WINDOW else scores
        if all(recent[i] < recent[i - 1] for i in range(1, len(recent))):
            return "declining"
        if all(recent[i] > recent[i - 1] for i in range(1, len(recent))):
            return "recovering"
        return "stable"

    def _classify_alert(self, health_score: float, trend: str) -> str:
        if health_score < _HEALTH_CRITICAL_THRESHOLD:
            return "critical"
        if health_score < _HEALTH_WARN_THRESHOLD or trend == "declining":
            return "warn"
        return "none"

    def _build_suggestion(self, health_score: float, trend: str, alert: str) -> str:
        if alert == "none":
            return ""
        parts: list[str] = []
        if trend == "declining":
            parts.append(f"质量连续下滑（近期均值 {health_score:.2f}），建议重组 carry_over 记忆")
        elif health_score < _HEALTH_WARN_THRESHOLD:
            parts.append(f"整体质量偏低（{health_score:.2f}），建议检查 steering pack 是否需要更新")
        return "；".join(parts) if parts else f"长书健康度偏低（{health_score:.2f}）"
