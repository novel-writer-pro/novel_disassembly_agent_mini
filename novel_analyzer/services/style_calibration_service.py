"""Loom Phase 4: Style calibration service.

Detects style drift by comparing the current chapter's embedding vector
against a reference window of previous chapters.

All metrics use existing ChunkEmbedding data – no new LLM calls required.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from novel_analyzer.database.models import (
    ChunkEmbedding,
    RetrievalChunk,
    RetrievalDocument,
)


@dataclass
class StyleDriftResult:
    branch_id: str
    chapter_index: int
    style_drift_score: float
    alert_level: str  # "none" | "warn" | "critical"
    reference_chapter_range: tuple[int, int] | None = None
    suggestion: str = ""

    def to_style_signal(self) -> dict[str, object]:
        return {
            "chapter_index": self.chapter_index,
            "branch_id": self.branch_id,
            "style_drift_score": self.style_drift_score,
            "alert_level": self.alert_level,
            "reference_chapter_range": (
                list(self.reference_chapter_range)
                if self.reference_chapter_range
                else None
            ),
            "suggestion": self.suggestion,
        }


class StyleCalibrationService:
    """Compute style drift for a chapter relative to a reference window."""

    WARN_THRESHOLD: float = 0.15
    CRITICAL_THRESHOLD: float = 0.30

    def __init__(self, session: Session) -> None:
        self.session = session

    def compute_style_drift(
        self,
        branch_id: str,
        chapter_index: int,
        reference_window: int = 5,
    ) -> StyleDriftResult:
        current_vec = self._get_chapter_vector(branch_id, chapter_index)
        if current_vec is None:
            return StyleDriftResult(
                branch_id=branch_id,
                chapter_index=chapter_index,
                style_drift_score=0.0,
                alert_level="none",
            )

        ref_start = max(1, chapter_index - reference_window)
        ref_end = chapter_index - 1
        ref_vecs: list[list[float]] = []
        for idx in range(ref_start, ref_end + 1):
            v = self._get_chapter_vector(branch_id, idx)
            if v is not None:
                ref_vecs.append(v)

        if not ref_vecs:
            return StyleDriftResult(
                branch_id=branch_id,
                chapter_index=chapter_index,
                style_drift_score=0.0,
                alert_level="none",
                reference_chapter_range=None,
            )

        ref_mean = _mean_vector(ref_vecs)
        drift = round(_cosine_distance(current_vec, ref_mean), 4)
        alert = self._classify_drift(drift)
        suggestion = self._build_suggestion(drift, alert, ref_start, ref_end)

        return StyleDriftResult(
            branch_id=branch_id,
            chapter_index=chapter_index,
            style_drift_score=drift,
            alert_level=alert,
            reference_chapter_range=(ref_start, ref_end),
            suggestion=suggestion,
        )

    def _get_chapter_vector(
        self, branch_id: str, chapter_index: int
    ) -> list[float] | None:
        row = self.session.scalar(
            select(ChunkEmbedding)
            .join(RetrievalChunk, ChunkEmbedding.chunk_id == RetrievalChunk.id)
            .join(RetrievalDocument, RetrievalChunk.document_id == RetrievalDocument.id)
            .where(RetrievalDocument.branch_id == branch_id)
            .where(RetrievalDocument.chapter_index == chapter_index)
            .where(RetrievalChunk.chunk_order == 0)
            .where(ChunkEmbedding.deleted_at.is_(None))
        )
        if row is None or not row.vector_payload:
            return None
        return list(row.vector_payload)

    def _classify_drift(self, drift: float) -> str:
        if drift >= self.CRITICAL_THRESHOLD:
            return "critical"
        if drift >= self.WARN_THRESHOLD:
            return "warn"
        return "none"

    def _build_suggestion(
        self, drift: float, alert: str, ref_start: int, ref_end: int
    ) -> str:
        if alert == "none":
            return ""
        if alert == "warn":
            return (
                f"风格轻微漂移（score={drift}），"
                f"建议参考第{ref_start}-{ref_end}章的语言风格"
            )
        return (
            f"风格明显漂移（score={drift}），"
            f"建议重新校准，参考第{ref_start}-{ref_end}章"
        )


def _mean_vector(vecs: list[list[float]]) -> list[float]:
    if not vecs:
        return []
    dim = len(vecs[0])
    result = [0.0] * dim
    for v in vecs:
        for i, x in enumerate(v):
            result[i] += x
    n = len(vecs)
    return [x / n for x in result]


def _cosine_distance(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return round(1.0 - dot / (norm_a * norm_b), 6)
