"""Loom memory assembler: build carry_over_state from three memory layers.

Working Memory  – recent window summaries + active threads (~2000 tokens)
Episodic Memory – top-K important facts (sorted by importance_score * decay_factor)
Semantic Memory – active GraphNodes (characters, rules, world elements)

Output is a dict compatible with the existing carry_over_state format
(via _legacy_compat) so 0509 session_state can consume it unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from novel_analyzer.database.models import (
    ChapterArtifact,
    FactRecord,
    GraphEdge,
    GraphNode,
    WindowArtifact,
)

# Rough token budget for Working Memory (characters, not tokens, but close enough)
_WORKING_MEMORY_CHAR_BUDGET: int = 4000   # ~2000 tokens at ~2 chars/token


@dataclass
class AssembledMemory:
    """Three-layer memory output."""

    branch_id: str
    assembled_at_chapter: int
    loom_version: str = "1.0"

    # Layer 1 – Working Memory
    active_characters: list[dict[str, Any]] = field(default_factory=list)
    active_threads: list[dict[str, Any]] = field(default_factory=list)
    recent_summary: str = ""

    # Layer 2 – Episodic Memory
    episodic_anchors: list[dict[str, Any]] = field(default_factory=list)

    # Layer 3 – Semantic Memory (counts only; full data in DB)
    character_count: int = 0
    active_rule_labels: list[str] = field(default_factory=list)
    key_relationship_labels: list[str] = field(default_factory=list)

    def to_carry_over_state(self) -> dict[str, Any]:
        """Return dict compatible with existing carry_over_state format."""
        return {
            "loom_version": self.loom_version,
            "assembled_at_chapter": self.assembled_at_chapter,
            "working_memory": {
                "active_characters": self.active_characters,
                "active_threads": self.active_threads,
                "recent_summary": self.recent_summary,
            },
            "episodic_anchors": self.episodic_anchors,
            "semantic_snapshot": {
                "character_count": self.character_count,
                "active_rules": self.active_rule_labels,
                "key_relationships": self.key_relationship_labels,
            },
            # Legacy-compat: flat lists for 0509 / existing consumers
            "_legacy_compat": {
                "characters": [c["label"] for c in self.active_characters],
                "rules": self.active_rule_labels,
                "unresolved_threads": [t["label"] for t in self.active_threads],
                "previous_chapter_summary": self.recent_summary,
            },
        }


class MemoryAssemblerService:
    """Assemble carry_over_state from three memory layers."""

    def __init__(self, session: Session) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def assemble(
        self,
        branch_id: str,
        target_chapter_index: int,
        episodic_top_k: int = 20,
    ) -> AssembledMemory:
        """Build AssembledMemory for the chapter about to be written."""
        mem = AssembledMemory(
            branch_id=branch_id,
            assembled_at_chapter=target_chapter_index,
        )

        # Layer 1 – Working Memory
        mem.active_characters = self._get_active_characters(branch_id, target_chapter_index)
        mem.active_threads = self._get_active_threads(branch_id, target_chapter_index)
        mem.recent_summary = self._get_recent_summary(branch_id, target_chapter_index)

        # Layer 2 – Episodic Memory
        mem.episodic_anchors = self._get_important_events(
            branch_id, target_chapter_index, top_k=episodic_top_k
        )

        # Layer 3 – Semantic Memory
        mem.character_count = self._count_active_characters(branch_id)
        mem.active_rule_labels = self._get_active_rule_labels(branch_id)
        mem.key_relationship_labels = self._get_key_relationship_labels(
            branch_id, target_chapter_index
        )

        return mem

    # ------------------------------------------------------------------
    # Layer 1 helpers
    # ------------------------------------------------------------------

    def _get_active_characters(
        self, branch_id: str, chapter_index: int
    ) -> list[dict[str, Any]]:
        """Characters seen in the last 5 chapters with no contradiction."""
        lookback = max(1, chapter_index - 5)
        nodes = list(
            self.session.scalars(
                select(GraphNode)
                .where(GraphNode.branch_id == branch_id)
                .where(GraphNode.node_type == "character")
                .where(GraphNode.chapter_last_seen >= lookback)
                .where(GraphNode.conflict_status != "contradiction")
                .where(GraphNode.deleted_at.is_(None))
                .order_by(GraphNode.importance_score.desc())
                .limit(15)
            ).all()
        )
        return [
            {
                "label": n.label,
                "chapter_last_seen": n.chapter_last_seen,
                "importance_score": n.importance_score,
                "conflict_status": n.conflict_status,
                "status": (n.metadata_json or {}).get("status", ""),
            }
            for n in nodes
        ]

    def _get_active_threads(
        self, branch_id: str, chapter_index: int
    ) -> list[dict[str, Any]]:
        """Unresolved threads (foreshadow / conflict nodes) from last 10 chapters."""
        lookback = max(1, chapter_index - 10)
        nodes = list(
            self.session.scalars(
                select(GraphNode)
                .where(GraphNode.branch_id == branch_id)
                .where(GraphNode.node_type.in_(["foreshadow", "conflict", "thread"]))
                .where(GraphNode.chapter_last_seen >= lookback)
                .where(GraphNode.conflict_status.notin_(["resolved"]))
                .where(GraphNode.deleted_at.is_(None))
                .order_by(GraphNode.importance_score.desc())
                .limit(10)
            ).all()
        )
        return [
            {
                "label": n.label,
                "node_type": n.node_type,
                "chapter_first_seen": n.chapter_first_seen,
                "chapter_last_seen": n.chapter_last_seen,
                "importance_score": n.importance_score,
            }
            for n in nodes
        ]

    def _get_recent_summary(self, branch_id: str, chapter_index: int) -> str:
        """Concatenate summaries from the last 3 window artifacts."""
        windows = list(
            self.session.scalars(
                select(WindowArtifact)
                .where(WindowArtifact.branch_id == branch_id)
                .where(WindowArtifact.window_end_chapter < chapter_index)
                .where(WindowArtifact.deleted_at.is_(None))
                .order_by(WindowArtifact.window_end_chapter.desc())
                .limit(3)
            ).all()
        )
        if not windows:
            # Fall back to last chapter artifact summary
            artifact = self.session.scalar(
                select(ChapterArtifact)
                .where(ChapterArtifact.branch_id == branch_id)
                .where(ChapterArtifact.chapter_index == chapter_index - 1)
                .where(ChapterArtifact.deleted_at.is_(None))
            )
            if artifact:
                return str(artifact.payload_json.get("chapter_summary", ""))
            return ""

        parts: list[str] = []
        for w in reversed(windows):
            summary = str((w.payload_json or {}).get("summary", ""))
            if summary:
                parts.append(
                    f"第{w.window_start_chapter}-{w.window_end_chapter}章：{summary}"
                )
        combined = " ".join(parts)
        # Trim to budget
        return combined[:_WORKING_MEMORY_CHAR_BUDGET]

    # ------------------------------------------------------------------
    # Layer 2 helpers
    # ------------------------------------------------------------------

    def _get_important_events(
        self, branch_id: str, chapter_index: int, top_k: int
    ) -> list[dict[str, Any]]:
        """Top-K facts by effective importance (importance_score * decay_factor)."""
        facts = list(
            self.session.scalars(
                select(FactRecord)
                .where(FactRecord.branch_id == branch_id)
                .where(FactRecord.chapter_index < chapter_index)
                .where(FactRecord.episodic_status == "active")
                .where(FactRecord.deleted_at.is_(None))
                .order_by(FactRecord.importance_score.desc())
                .limit(top_k * 3)   # over-fetch, then re-rank by effective score
            ).all()
        )
        # Re-rank by effective importance
        ranked = sorted(
            facts,
            key=lambda f: f.importance_score * f.decay_factor,
            reverse=True,
        )[:top_k]
        return [
            {
                "label": f.label,
                "fact_type": f.fact_type,
                "chapter_index": f.chapter_index,
                "importance_score": f.importance_score,
                "decay_factor": f.decay_factor,
                "effective_score": round(f.importance_score * f.decay_factor, 4),
            }
            for f in ranked
        ]

    # ------------------------------------------------------------------
    # Layer 3 helpers
    # ------------------------------------------------------------------

    def _count_active_characters(self, branch_id: str) -> int:
        nodes = self.session.scalars(
            select(GraphNode)
            .where(GraphNode.branch_id == branch_id)
            .where(GraphNode.node_type == "character")
            .where(GraphNode.conflict_status != "contradiction")
            .where(GraphNode.deleted_at.is_(None))
        ).all()
        return len(list(nodes))

    def _get_active_rule_labels(self, branch_id: str) -> list[str]:
        nodes = list(
            self.session.scalars(
                select(GraphNode)
                .where(GraphNode.branch_id == branch_id)
                .where(GraphNode.node_type == "rule")
                .where(GraphNode.conflict_status.notin_(["contradiction", "evolution"]))
                .where(GraphNode.deleted_at.is_(None))
                .order_by(GraphNode.importance_score.desc())
                .limit(10)
            ).all()
        )
        return [n.label for n in nodes]

    def _get_key_relationship_labels(
        self, branch_id: str, chapter_index: int
    ) -> list[str]:
        """Active relationship edges seen in last 10 chapters."""
        lookback = max(1, chapter_index - 10)
        edges = list(
            self.session.scalars(
                select(GraphEdge)
                .where(GraphEdge.branch_id == branch_id)
                .where(GraphEdge.edge_type == "relationship")
                .where(GraphEdge.chapter_last_seen >= lookback)
                .where(GraphEdge.is_active.is_(True))
                .where(GraphEdge.deleted_at.is_(None))
                .order_by(GraphEdge.weight.desc())
                .limit(10)
            ).all()
        )
        labels: list[str] = []
        for e in edges:
            src = self.session.get(GraphNode, e.source_node_id)
            tgt = self.session.get(GraphNode, e.target_node_id)
            if src and tgt:
                labels.append(f"{src.label} → {tgt.label}")
        return labels
