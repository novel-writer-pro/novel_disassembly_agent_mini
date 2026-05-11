"""Loom tension metrics: three quantitative narrative-tension indicators.

All three metrics use existing DB data only – no new LLM calls required.

plot_similarity_score  – cosine similarity of chapter embeddings vs prev N chapters
                         (falls back to keyword-overlap when embeddings absent)
conflict_density       – conflict-type GraphEdge count per 1000 chars
surprise_index         – fraction of new FactRecord labels not seen before
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from novel_analyzer.database.models import (
    ChapterArtifact,
    ChunkEmbedding,
    FactRecord,
    GraphEdge,
    RetrievalChunk,
    RetrievalDocument,
)

# Edge types that count as "conflict" for conflict_density
CONFLICT_EDGE_TYPES: frozenset[str] = frozenset(
    {
        # Actual edge types produced by graph_service
        "conflict_centers_on",
        "conflict_involves",
        "pressured_by",
        # Legacy / future types kept for forward-compat
        "conflict",
        "confrontation",
        "opposition",
        "betrayal",
        "threat",
        "challenge",
        "power_struggle",
        "moral_dilemma",
        "hostility",
        "rivalry",
    }
)

# Thresholds
_SIMILARITY_HIGH = 0.85   # above → high repetition warning
_SIMILARITY_MED = 0.70    # above → medium warning
_DENSITY_LOW = 0.5        # below → low conflict warning
_SURPRISE_LOW = 0.10      # below → low novelty warning
_TENSION_WARN = 0.40      # overall score below → warning


@dataclass
class TensionAlert:
    alert_type: str
    severity: str          # high | medium | low
    message: str
    suggestion: str


@dataclass
class TensionScore:
    chapter_index: int
    branch_id: str
    tension_score: float
    plot_similarity: float
    conflict_density: float
    surprise_index: float
    alerts: list[TensionAlert] = field(default_factory=list)
    loom_version: str = "1.0"

    def to_operator_signal(self) -> dict[str, object]:
        """Compact dict for 0509 operator_surface."""
        return {
            "chapter_index": self.chapter_index,
            "tension_score": round(self.tension_score, 4),
            "status": "warning" if self.alerts else "ok",
            "alerts": [
                {
                    "type": a.alert_type,
                    "severity": a.severity,
                    "message": a.message,
                    "suggestion": a.suggestion,
                }
                for a in self.alerts
            ],
            "metrics": {
                "plot_similarity": round(self.plot_similarity, 4),
                "conflict_density": round(self.conflict_density, 4),
                "surprise_index": round(self.surprise_index, 4),
            },
            "loom_version": self.loom_version,
        }


class TensionService:
    """Compute narrative tension metrics for a chapter."""

    def __init__(self, session: Session) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compute(
        self,
        branch_id: str,
        chapter_index: int,
        lookback_n: int = 3,
        rhythm_signal: dict[str, object] | None = None,
        thread_status: dict[str, object] | None = None,
    ) -> TensionScore:
        similarity = self._plot_similarity(branch_id, chapter_index, lookback_n)
        density = self._conflict_density(branch_id, chapter_index)
        surprise = self._surprise_index(branch_id, chapter_index)

        # Composite score (higher = more tension = better)
        tension = (
            (1.0 - similarity) * 0.40
            + min(density / 1.5, 1.0) * 0.35
            + surprise * 0.25
        )
        tension = round(max(0.0, min(1.0, tension)), 4)

        alerts = self._build_alerts(similarity, density, surprise, tension, rhythm_signal, thread_status)
        return TensionScore(
            chapter_index=chapter_index,
            branch_id=branch_id,
            tension_score=tension,
            plot_similarity=similarity,
            conflict_density=density,
            surprise_index=surprise,
            alerts=alerts,
        )

    # ------------------------------------------------------------------
    # Metric 1: plot_similarity_score
    # ------------------------------------------------------------------

    def _plot_similarity(
        self, branch_id: str, chapter_index: int, lookback_n: int
    ) -> float:
        """Cosine similarity between current chapter and previous N chapters.

        Uses stored vector_payload from ChunkEmbedding (first chunk of each
        RetrievalDocument).  Falls back to keyword-overlap when embeddings
        are absent.
        """
        current_vec = self._get_chapter_vector(branch_id, chapter_index)
        if current_vec is None:
            return self._keyword_similarity(branch_id, chapter_index, lookback_n)

        similarities: list[float] = []
        for prev_idx in range(max(1, chapter_index - lookback_n), chapter_index):
            prev_vec = self._get_chapter_vector(branch_id, prev_idx)
            if prev_vec is not None:
                similarities.append(_cosine(current_vec, prev_vec))

        return round(sum(similarities) / len(similarities), 4) if similarities else 0.0

    def _get_chapter_vector(
        self, branch_id: str, chapter_index: int
    ) -> list[float] | None:
        """Return the first chunk embedding for a chapter, or None."""
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

    def _keyword_similarity(
        self, branch_id: str, chapter_index: int, lookback_n: int
    ) -> float:
        """Fallback: Jaccard similarity on key_entities from chapter artifacts."""
        current_kw = self._get_chapter_keywords(branch_id, chapter_index)
        if not current_kw:
            return 0.0

        similarities: list[float] = []
        for prev_idx in range(max(1, chapter_index - lookback_n), chapter_index):
            prev_kw = self._get_chapter_keywords(branch_id, prev_idx)
            if prev_kw:
                inter = len(current_kw & prev_kw)
                union = len(current_kw | prev_kw)
                similarities.append(inter / union if union else 0.0)

        return round(sum(similarities) / len(similarities), 4) if similarities else 0.0

    def _get_chapter_keywords(self, branch_id: str, chapter_index: int) -> set[str]:
        artifact = self.session.scalar(
            select(ChapterArtifact)
            .where(ChapterArtifact.branch_id == branch_id)
            .where(ChapterArtifact.chapter_index == chapter_index)
            .where(ChapterArtifact.deleted_at.is_(None))
        )
        if artifact is None:
            return set()
        payload = artifact.payload_json or {}
        entities: list[object] = list(payload.get("key_entities", []))
        events: list[object] = list(payload.get("key_events", []))
        return {str(x).strip().lower() for x in entities + events if x}

    # ------------------------------------------------------------------
    # Metric 2: conflict_density
    # ------------------------------------------------------------------

    def _conflict_density(self, branch_id: str, chapter_index: int) -> float:
        """Conflict signals per 1000 characters: conflict-type edges + conflict nodes."""
        from novel_analyzer.database.models import GraphNode

        edge_count = self.session.scalar(
            select(func.count(GraphEdge.id))
            .where(GraphEdge.branch_id == branch_id)
            .where(GraphEdge.chapter_last_seen == chapter_index)
            .where(GraphEdge.edge_type.in_(list(CONFLICT_EDGE_TYPES)))
            .where(GraphEdge.deleted_at.is_(None))
        ) or 0

        node_count = self.session.scalar(
            select(func.count(GraphNode.id))
            .where(GraphNode.branch_id == branch_id)
            .where(GraphNode.chapter_last_seen == chapter_index)
            .where(GraphNode.node_type == "conflict")
            .where(GraphNode.deleted_at.is_(None))
        ) or 0

        conflict_count = edge_count + node_count
        word_count = self._get_chapter_word_count(branch_id, chapter_index)
        if word_count == 0:
            return 0.0
        return round(conflict_count / (word_count / 1000), 4)

    def _get_chapter_word_count(self, branch_id: str, chapter_index: int) -> int:
        """Approximate word count from chapter artifact summary length."""
        artifact = self.session.scalar(
            select(ChapterArtifact)
            .where(ChapterArtifact.branch_id == branch_id)
            .where(ChapterArtifact.chapter_index == chapter_index)
            .where(ChapterArtifact.deleted_at.is_(None))
        )
        if artifact is None:
            return 0
        payload = artifact.payload_json or {}
        # Use summary length as proxy; real text length would be better
        summary = str(payload.get("chapter_summary", ""))
        # Estimate: summary is ~10% of full chapter
        return max(len(summary) * 10, 500)

    # ------------------------------------------------------------------
    # Metric 3: surprise_index
    # ------------------------------------------------------------------

    def _surprise_index(self, branch_id: str, chapter_index: int) -> float:
        """Fraction of this chapter's fact labels not seen in prior chapters."""
        current_facts = list(
            self.session.scalars(
                select(FactRecord)
                .where(FactRecord.branch_id == branch_id)
                .where(FactRecord.chapter_index == chapter_index)
                .where(FactRecord.deleted_at.is_(None))
            ).all()
        )
        if not current_facts:
            return 0.0

        known_labels: set[str] = set(
            self.session.scalars(
                select(FactRecord.label)
                .where(FactRecord.branch_id == branch_id)
                .where(FactRecord.chapter_index < chapter_index)
                .where(FactRecord.deleted_at.is_(None))
            ).all()
        )

        new_count = sum(1 for f in current_facts if f.label not in known_labels)
        return round(new_count / len(current_facts), 4)

    # ------------------------------------------------------------------
    # Alert builder
    # ------------------------------------------------------------------

    def _build_alerts(
        self,
        similarity: float,
        density: float,
        surprise: float,
        tension: float,
        rhythm_signal: dict[str, object] | None = None,
        thread_status: dict[str, object] | None = None,
    ) -> list[TensionAlert]:
        alerts: list[TensionAlert] = []

        if similarity > _SIMILARITY_HIGH:
            alerts.append(TensionAlert(
                alert_type="high_similarity",
                severity="high",
                message=f"情节相似度 {similarity:.2f}，与前几章高度重复",
                suggestion="考虑引入新的冲突或意外转折",
            ))
        elif similarity > _SIMILARITY_MED:
            alerts.append(TensionAlert(
                alert_type="medium_similarity",
                severity="medium",
                message=f"情节相似度 {similarity:.2f}，变化较少",
                suggestion="可适当增加新元素或加快节奏",
            ))

        if density < _DENSITY_LOW:
            alerts.append(TensionAlert(
                alert_type="low_conflict_density",
                severity="medium",
                message=f"冲突密度 {density:.2f}，情节偏平淡",
                suggestion="考虑增加角色间冲突或内心矛盾",
            ))

        if surprise < _SURPRISE_LOW:
            alerts.append(TensionAlert(
                alert_type="low_surprise",
                severity="medium",
                message=f"新颖度指数 {surprise:.2f}，几乎没有新元素",
                suggestion="考虑引入新角色、新地点或新信息",
            ))

        if rhythm_signal:
            hook_density = rhythm_signal.get("hook_density")
            rhythm_alert = rhythm_signal.get("alert_level", "none")
            if rhythm_alert != "none" and isinstance(hook_density, (int, float)):
                if density < _DENSITY_LOW:
                    alerts.append(TensionAlert(
                        alert_type="double_flat",
                        severity="high",
                        message=f"冲突密度（{density:.2f}）与爽点密度（{hook_density:.2f}/千字）双低，情节严重平淡",
                        suggestion="建议同时增加冲突事件和情绪高点，或激活已有伏笔",
                    ))
                else:
                    alerts.append(TensionAlert(
                        alert_type="low_hook_density",
                        severity="medium",
                        message=f"爽点密度偏低（{hook_density:.2f}/千字），读者留存风险",
                        suggestion="建议在本章增加情绪高点或意外反转",
                    ))

        if thread_status:
            overdue = thread_status.get("overdue_threads", [])
            if isinstance(overdue, list) and overdue:
                best = max(overdue, key=lambda t: float(t.get("importance_score", 0)) if isinstance(t, dict) else 0)
                label = str(best.get("label", "")) if isinstance(best, dict) else ""
                dormant_n = int(best.get("chapters_since_last_seen", 0)) if isinstance(best, dict) else 0
                alerts.append(TensionAlert(
                    alert_type="overdue_thread",
                    severity="medium",
                    message=f"线索「{label}」已沉寂 {dormant_n} 章，建议本章激活",
                    suggestion=f"激活线索「{label}」可提升情节新颖度和读者期待感",
                ))

        return alerts


# ---------------------------------------------------------------------------
# Math helpers
# ---------------------------------------------------------------------------

def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine similarity between two vectors."""
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
