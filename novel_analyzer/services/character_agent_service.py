"""Loom Phase 4: Character agent service.

Builds a CharacterPersona from existing DB data and checks whether
a draft text is consistent with that persona.

All data comes from existing tables (FactRecord, GraphNode, GraphEdge,
ChunkEmbedding) – no new LLM calls required for the heuristic path.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from novel_analyzer.database.models import (
    ChunkEmbedding,
    FactRecord,
    GraphEdge,
    GraphNode,
    RetrievalChunk,
    RetrievalDocument,
)


@dataclass
class CharacterPersona:
    character_id: str
    branch_id: str
    built_at_chapter: int
    behavior_labels: list[str] = field(default_factory=list)
    episodic_anchors: list[dict[str, object]] = field(default_factory=list)
    relationship_network: dict[str, str] = field(default_factory=dict)
    speech_style_vector: list[float] = field(default_factory=list)
    chapter_appearances: list[int] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "character_id": self.character_id,
            "branch_id": self.branch_id,
            "built_at_chapter": self.built_at_chapter,
            "behavior_labels": self.behavior_labels,
            "episodic_anchor_count": len(self.episodic_anchors),
            "relationship_count": len(self.relationship_network),
            "has_speech_vector": bool(self.speech_style_vector),
            "chapter_appearances": self.chapter_appearances,
        }


@dataclass
class CharacterConsistencySignal:
    character_id: str
    overall_consistency_score: float
    speech_consistency: float
    behavior_consistency: float
    relationship_consistency: float
    alert_level: str  # "none" | "warn" | "critical"
    suggestion: str = ""

    def to_consistency_signal(self) -> dict[str, object]:
        return {
            "character_id": self.character_id,
            "overall_consistency_score": self.overall_consistency_score,
            "speech_consistency": self.speech_consistency,
            "behavior_consistency": self.behavior_consistency,
            "relationship_consistency": self.relationship_consistency,
            "alert_level": self.alert_level,
            "suggestion": self.suggestion,
        }


class CharacterAgentService:
    """Build CharacterPersona and check draft consistency."""

    WARN_THRESHOLD: float = 0.60
    CRITICAL_THRESHOLD: float = 0.40

    def __init__(self, session: Session) -> None:
        self.session = session

    def build_character_persona(
        self,
        branch_id: str,
        character_name: str,
        as_of_chapter: int,
        top_k: int = 20,
    ) -> CharacterPersona:
        behavior_labels = self._get_behavior_labels(
            branch_id, character_name, as_of_chapter, top_k
        )
        episodic_anchors = self._get_episodic_anchors(
            branch_id, character_name, as_of_chapter
        )
        relationship_network = self._get_relationship_network(
            branch_id, character_name
        )
        speech_vector = self._get_speech_vector(
            branch_id, character_name, as_of_chapter
        )
        chapter_appearances = self._get_chapter_appearances(
            branch_id, character_name, as_of_chapter
        )

        return CharacterPersona(
            character_id=character_name,
            branch_id=branch_id,
            built_at_chapter=as_of_chapter,
            behavior_labels=behavior_labels,
            episodic_anchors=episodic_anchors,
            relationship_network=relationship_network,
            speech_style_vector=speech_vector,
            chapter_appearances=chapter_appearances,
        )

    def check_character_consistency(
        self,
        persona: CharacterPersona,
        draft_text: str,
        chapter_index: int,
    ) -> CharacterConsistencySignal:
        speech_consistency = self._check_speech_consistency(
            persona, chapter_index
        )
        behavior_consistency = self._check_behavior_consistency(
            persona, draft_text
        )
        relationship_consistency = self._check_relationship_consistency(
            persona, draft_text
        )

        overall = round(
            speech_consistency * 0.40
            + behavior_consistency * 0.35
            + relationship_consistency * 0.25,
            4,
        )
        alert = self._classify_alert(overall)
        suggestion = self._build_suggestion(
            overall, speech_consistency, behavior_consistency, alert
        )

        return CharacterConsistencySignal(
            character_id=persona.character_id,
            overall_consistency_score=overall,
            speech_consistency=round(speech_consistency, 4),
            behavior_consistency=round(behavior_consistency, 4),
            relationship_consistency=round(relationship_consistency, 4),
            alert_level=alert,
            suggestion=suggestion,
        )

    def _get_behavior_labels(
        self,
        branch_id: str,
        character_name: str,
        as_of_chapter: int,
        top_k: int,
    ) -> list[str]:
        rows = self.session.scalars(
            select(FactRecord.label)
            .where(FactRecord.branch_id == branch_id)
            .where(FactRecord.label == character_name)
            .where(FactRecord.fact_type == "entity")
            .where(FactRecord.chapter_index <= as_of_chapter)
            .where(FactRecord.episodic_status == "active")
            .where(FactRecord.deleted_at.is_(None))
            .order_by(FactRecord.importance_score.desc())
            .limit(top_k)
        ).all()
        return list(rows)

    def _get_episodic_anchors(
        self,
        branch_id: str,
        character_name: str,
        as_of_chapter: int,
    ) -> list[dict[str, object]]:
        rows = self.session.execute(
            select(FactRecord.chapter_index, FactRecord.label, FactRecord.importance_score)
            .where(FactRecord.branch_id == branch_id)
            .where(FactRecord.label == character_name)
            .where(FactRecord.fact_type == "entity")
            .where(FactRecord.chapter_index <= as_of_chapter)
            .where(FactRecord.importance_score >= 0.7)
            .where(FactRecord.deleted_at.is_(None))
            .order_by(FactRecord.importance_score.desc())
            .limit(10)
        ).all()
        return [
            {
                "chapter": row.chapter_index,
                "label": row.label,
                "importance": row.importance_score,
            }
            for row in rows
        ]

    def _get_relationship_network(
        self, branch_id: str, character_name: str
    ) -> dict[str, str]:
        node = self.session.scalar(
            select(GraphNode)
            .where(GraphNode.branch_id == branch_id)
            .where(GraphNode.label == character_name)
            .where(GraphNode.node_type == "entity")
            .where(GraphNode.deleted_at.is_(None))
        )
        if node is None:
            return {}

        edges = self.session.scalars(
            select(GraphEdge)
            .where(GraphEdge.branch_id == branch_id)
            .where(
                (GraphEdge.source_node_id == node.id)
                | (GraphEdge.target_node_id == node.id)
            )
            .where(GraphEdge.is_active.is_(True))
            .where(GraphEdge.deleted_at.is_(None))
            .limit(20)
        ).all()

        network: dict[str, str] = {}
        for edge in edges:
            if edge.source_node_id == node.id:
                other = self.session.scalar(
                    select(GraphNode.label)
                    .where(GraphNode.id == edge.target_node_id)
                )
            else:
                other = self.session.scalar(
                    select(GraphNode.label)
                    .where(GraphNode.id == edge.source_node_id)
                )
            if other:
                network[other] = edge.edge_type
        return network

    def _get_speech_vector(
        self,
        branch_id: str,
        character_name: str,
        as_of_chapter: int,
    ) -> list[float]:
        chapter_appearances = self._get_chapter_appearances(
            branch_id, character_name, as_of_chapter
        )
        if not chapter_appearances:
            return []

        vecs: list[list[float]] = []
        for ch_idx in chapter_appearances[-5:]:
            row = self.session.scalar(
                select(ChunkEmbedding)
                .join(RetrievalChunk, ChunkEmbedding.chunk_id == RetrievalChunk.id)
                .join(
                    RetrievalDocument,
                    RetrievalChunk.document_id == RetrievalDocument.id,
                )
                .where(RetrievalDocument.branch_id == branch_id)
                .where(RetrievalDocument.chapter_index == ch_idx)
                .where(RetrievalChunk.chunk_order == 0)
                .where(ChunkEmbedding.deleted_at.is_(None))
            )
            if row is not None and row.vector_payload:
                vecs.append(list(row.vector_payload))

        if not vecs:
            return []
        return _mean_vector(vecs)

    def _get_chapter_appearances(
        self,
        branch_id: str,
        character_name: str,
        as_of_chapter: int,
    ) -> list[int]:
        rows = self.session.scalars(
            select(FactRecord.chapter_index)
            .where(FactRecord.branch_id == branch_id)
            .where(FactRecord.label == character_name)
            .where(FactRecord.fact_type == "entity")
            .where(FactRecord.chapter_index <= as_of_chapter)
            .where(FactRecord.deleted_at.is_(None))
            .order_by(FactRecord.chapter_index)
        ).all()
        return sorted(set(rows))

    def _check_speech_consistency(
        self, persona: CharacterPersona, chapter_index: int
    ) -> float:
        if not persona.speech_style_vector:
            return 1.0
        current_vec = self._get_speech_vector(
            persona.branch_id, persona.character_id, chapter_index
        )
        if not current_vec:
            return 1.0
        return round(
            1.0 - _cosine_distance(current_vec, persona.speech_style_vector), 4
        )

    def _check_behavior_consistency(
        self, persona: CharacterPersona, draft_text: str
    ) -> float:
        if not persona.behavior_labels:
            return 1.0
        name = persona.character_id
        if name not in draft_text:
            return 1.0
        return 0.8

    def _check_relationship_consistency(
        self, persona: CharacterPersona, draft_text: str
    ) -> float:
        if not persona.relationship_network:
            return 1.0
        mentioned = sum(
            1 for other in persona.relationship_network if other in draft_text
        )
        if mentioned == 0:
            return 1.0
        return 0.85

    def _classify_alert(self, score: float) -> str:
        if score < self.CRITICAL_THRESHOLD:
            return "critical"
        if score < self.WARN_THRESHOLD:
            return "warn"
        return "none"

    def _build_suggestion(
        self,
        overall: float,
        speech: float,
        behavior: float,
        alert: str,
    ) -> str:
        if alert == "none":
            return ""
        parts: list[str] = []
        if speech < self.WARN_THRESHOLD:
            parts.append("说话风格与历史章节差异较大")
        if behavior < self.WARN_THRESHOLD:
            parts.append("行为模式与角色认知基不符")
        if not parts:
            parts.append(f"角色一致性偏低（{overall:.2f}）")
        return f"{parts[0]}，建议检查角色设定"


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
