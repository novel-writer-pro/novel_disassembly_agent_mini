"""Loom Phase 4: Dialogue quality signal service.

Computes three dialogue quality proxies using existing DB data:
  character_voice_consistency – entity overlap × chapter embedding similarity
  dialogue_efficiency         – participates_in edges / total event count
  conflict_dialogue_density   – conflict-type edges / total edge count

No new LLM calls required.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from novel_analyzer.database.models import (
    ChunkEmbedding,
    FactRecord,
    GraphEdge,
    GraphNode,
    RetrievalChunk,
    RetrievalDocument,
)

CONFLICT_EDGE_TYPES: frozenset[str] = frozenset(
    {
        "conflict_centers_on",
        "conflict_involves",
        "pressured_by",
        "conflict",
        "confrontation",
        "opposition",
    }
)

INTERACTION_EDGE_TYPES: frozenset[str] = frozenset(
    {
        "participates_in",
        "co_occurs",
        "relates_to",
        "contextualizes",
    }
)


@dataclass
class DialogueSignal:
    branch_id: str
    chapter_index: int
    character_voice_consistency: float
    dialogue_efficiency: float
    conflict_dialogue_density: float
    alert_level: str  # "none" | "warn" | "critical"
    suggestion: str = ""
    character_details: dict[str, float] = field(default_factory=dict)

    def to_dialogue_signal(self) -> dict[str, object]:
        return {
            "chapter_index": self.chapter_index,
            "branch_id": self.branch_id,
            "character_voice_consistency": self.character_voice_consistency,
            "dialogue_efficiency": self.dialogue_efficiency,
            "conflict_dialogue_density": self.conflict_dialogue_density,
            "alert_level": self.alert_level,
            "suggestion": self.suggestion,
            "character_details": self.character_details,
        }


class DialogueSignalService:
    """Compute dialogue quality signals for a chapter."""

    VOICE_WARN_THRESHOLD: float = 0.60
    EFFICIENCY_WARN_THRESHOLD: float = 0.20

    def __init__(self, session: Session) -> None:
        self.session = session

    def compute(
        self,
        branch_id: str,
        chapter_index: int,
        lookback_n: int = 5,
    ) -> DialogueSignal:
        voice_consistency, char_details = self._character_voice_consistency(
            branch_id, chapter_index, lookback_n
        )
        efficiency = self._dialogue_efficiency(branch_id, chapter_index)
        conflict_density = self._conflict_dialogue_density(branch_id, chapter_index)
        alert = self._classify_alert(voice_consistency, efficiency)
        suggestion = self._build_suggestion(voice_consistency, efficiency, alert)

        return DialogueSignal(
            branch_id=branch_id,
            chapter_index=chapter_index,
            character_voice_consistency=voice_consistency,
            dialogue_efficiency=efficiency,
            conflict_dialogue_density=conflict_density,
            alert_level=alert,
            suggestion=suggestion,
            character_details=char_details,
        )

    def _character_voice_consistency(
        self,
        branch_id: str,
        chapter_index: int,
        lookback_n: int,
    ) -> tuple[float, dict[str, float]]:
        current_entities = self._get_chapter_entities(branch_id, chapter_index)
        if not current_entities:
            return 1.0, {}

        current_vec = self._get_chapter_vector(branch_id, chapter_index)
        if current_vec is None:
            return 1.0, {}

        char_scores: dict[str, float] = {}
        for entity_label in current_entities:
            prev_chapters = self._get_entity_chapters(
                branch_id, entity_label, chapter_index, lookback_n
            )
            if not prev_chapters:
                char_scores[entity_label] = 1.0
                continue
            similarities: list[float] = []
            for prev_idx in prev_chapters:
                prev_vec = self._get_chapter_vector(branch_id, prev_idx)
                if prev_vec is not None:
                    similarities.append(1.0 - _cosine_distance(current_vec, prev_vec))
            if similarities:
                char_scores[entity_label] = round(
                    sum(similarities) / len(similarities), 4
                )
            else:
                char_scores[entity_label] = 1.0

        if not char_scores:
            return 1.0, {}
        overall = round(sum(char_scores.values()) / len(char_scores), 4)
        return overall, char_scores

    def _dialogue_efficiency(self, branch_id: str, chapter_index: int) -> float:
        interaction_count = self.session.scalar(
            select(func.count(GraphEdge.id))
            .where(GraphEdge.branch_id == branch_id)
            .where(GraphEdge.chapter_last_seen == chapter_index)
            .where(GraphEdge.edge_type.in_(list(INTERACTION_EDGE_TYPES)))
            .where(GraphEdge.deleted_at.is_(None))
        ) or 0

        total_events = self.session.scalar(
            select(func.count(FactRecord.id))
            .where(FactRecord.branch_id == branch_id)
            .where(FactRecord.chapter_index == chapter_index)
            .where(FactRecord.fact_type == "event")
            .where(FactRecord.deleted_at.is_(None))
        ) or 0

        if total_events == 0:
            return 0.0
        return round(min(1.0, interaction_count / max(total_events, 1)), 4)

    def _conflict_dialogue_density(
        self, branch_id: str, chapter_index: int
    ) -> float:
        conflict_count = self.session.scalar(
            select(func.count(GraphEdge.id))
            .where(GraphEdge.branch_id == branch_id)
            .where(GraphEdge.chapter_last_seen == chapter_index)
            .where(GraphEdge.edge_type.in_(list(CONFLICT_EDGE_TYPES)))
            .where(GraphEdge.deleted_at.is_(None))
        ) or 0

        total_edges = self.session.scalar(
            select(func.count(GraphEdge.id))
            .where(GraphEdge.branch_id == branch_id)
            .where(GraphEdge.chapter_last_seen == chapter_index)
            .where(GraphEdge.deleted_at.is_(None))
        ) or 0

        if total_edges == 0:
            return 0.0
        return round(conflict_count / total_edges, 4)

    def _get_chapter_entities(
        self, branch_id: str, chapter_index: int
    ) -> list[str]:
        rows = self.session.scalars(
            select(FactRecord.label)
            .where(FactRecord.branch_id == branch_id)
            .where(FactRecord.chapter_index == chapter_index)
            .where(FactRecord.fact_type == "entity")
            .where(FactRecord.deleted_at.is_(None))
            .limit(10)
        ).all()
        return list(rows)

    def _get_entity_chapters(
        self,
        branch_id: str,
        entity_label: str,
        before_chapter: int,
        lookback_n: int,
    ) -> list[int]:
        rows = self.session.scalars(
            select(FactRecord.chapter_index)
            .where(FactRecord.branch_id == branch_id)
            .where(FactRecord.label == entity_label)
            .where(FactRecord.fact_type == "entity")
            .where(FactRecord.chapter_index < before_chapter)
            .where(
                FactRecord.chapter_index >= before_chapter - lookback_n
            )
            .where(FactRecord.deleted_at.is_(None))
            .order_by(FactRecord.chapter_index.desc())
            .limit(lookback_n)
        ).all()
        return list(rows)

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

    def _classify_alert(
        self, voice_consistency: float, efficiency: float
    ) -> str:
        if voice_consistency < self.VOICE_WARN_THRESHOLD:
            return "warn"
        if efficiency < self.EFFICIENCY_WARN_THRESHOLD:
            return "warn"
        return "none"

    def _build_suggestion(
        self, voice_consistency: float, efficiency: float, alert: str
    ) -> str:
        if alert == "none":
            return ""
        parts: list[str] = []
        if voice_consistency < self.VOICE_WARN_THRESHOLD:
            parts.append(
                f"角色声音一致性偏低（{voice_consistency:.2f}），建议检查角色说话风格"
            )
        if efficiency < self.EFFICIENCY_WARN_THRESHOLD:
            parts.append(
                f"对话推进情节效率偏低（{efficiency:.2f}），建议精简填充性对话"
            )
        return "；".join(parts)


def _cosine_distance(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return round(1.0 - dot / (norm_a * norm_b), 6)
