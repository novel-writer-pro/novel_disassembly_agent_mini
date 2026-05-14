"""Loom memory consolidation: conflict detection and episodic decay.

Runs after each chapter analysis completes (feature-flag controlled).
Reads newly materialised GraphNodes / FactRecords and classifies them
against existing history:

  clean        – brand-new node, no conflict
  evolution    – state changed with narrative support
  contradiction – direct conflict, no narrative bridge
  ambiguity    – semantically similar but uncertain
  resolved     – previously flagged, now confirmed OK
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from novel_analyzer.database.models import ChapterArtifact, FactRecord, GraphEdge, GraphNode


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------

@dataclass
class ConflictItem:
    entity_label: str
    conflict_type: str          # contradiction | evolution | ambiguity
    chapter_new: int
    chapter_old: int
    description: str
    requires_human_review: bool = False


@dataclass
class ConsolidationResult:
    branch_id: str
    chapter_index: int
    contradictions: list[ConflictItem] = field(default_factory=list)
    evolutions: list[ConflictItem] = field(default_factory=list)
    ambiguities: list[ConflictItem] = field(default_factory=list)

    @property
    def human_review_required(self) -> bool:
        return any(c.requires_human_review for c in self.contradictions)

    @property
    def total_conflicts(self) -> int:
        return len(self.contradictions) + len(self.evolutions) + len(self.ambiguities)

    def to_operator_signal(self) -> dict[str, object]:
        """Compact dict suitable for 0509 operator_surface consumption."""
        return {
            "chapter_index": self.chapter_index,
            "contradictions_found": len(self.contradictions),
            "evolutions_recorded": len(self.evolutions),
            "ambiguities_pending": len(self.ambiguities),
            "human_review_required": self.human_review_required,
            "conflict_summary": [
                {
                    "type": c.conflict_type,
                    "entity": c.entity_label,
                    "description": c.description,
                    "requires_action": c.requires_human_review,
                }
                for c in self.contradictions + self.ambiguities
            ],
        }


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

# Edge types that count as "conflict" for conflict_density metric
# Aligned to actual graph_service production edge types + legacy forward-compat
CONFLICT_EDGE_TYPES: frozenset[str] = frozenset(
    {
        # Actual conflict edge types produced by graph_service
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

# Decay rates per chapter
_DECAY_NORMAL: float = 0.95
_DECAY_IMPORTANT: float = 0.99   # importance_score > 0.8
_DECAY_RESOLVED: float = 0.80    # already-resolved threads


class MemoryConsolidationService:
    """Detect conflicts and decay episodic importance after each chapter."""

    def __init__(self, session: Session) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def consolidate(self, branch_id: str, chapter_index: int) -> ConsolidationResult:
        """Run full consolidation for one chapter.

        1. Load new GraphNodes for this chapter.
        2. Compare against history → classify conflicts.
        3. Update conflict_status / loom_version on affected nodes.
        4. Decay episodic importance on FactRecords.
        5. Return ConsolidationResult for operator surface.
        """
        result = ConsolidationResult(branch_id=branch_id, chapter_index=chapter_index)

        new_nodes = self._load_new_nodes(branch_id, chapter_index)
        artifact_payload = self._load_artifact_payload(branch_id, chapter_index)

        for node in new_nodes:
            history = self._load_history_nodes(branch_id, node.node_type, node.label, chapter_index)
            if not history:
                # Genuinely new – mark clean (already default)
                continue

            conflict_type = self._classify(node, history, artifact_payload)

            if conflict_type == "evolution":
                item = ConflictItem(
                    entity_label=node.label,
                    conflict_type="evolution",
                    chapter_new=chapter_index,
                    chapter_old=history[0].chapter_last_seen,
                    description=f"'{node.label}' 状态在第{chapter_index}章发生演进",
                )
                result.evolutions.append(item)
                self._mark_evolution(node, history[0])

            elif conflict_type == "contradiction":
                item = ConflictItem(
                    entity_label=node.label,
                    conflict_type="contradiction",
                    chapter_new=chapter_index,
                    chapter_old=history[0].chapter_last_seen,
                    description=(
                        f"'{node.label}' 在第{chapter_index}章与第"
                        f"{history[0].chapter_last_seen}章存在直接矛盾"
                    ),
                    requires_human_review=True,
                )
                result.contradictions.append(item)
                node.conflict_status = "contradiction"
                self.session.flush()

            elif conflict_type == "ambiguity":
                item = ConflictItem(
                    entity_label=node.label,
                    conflict_type="ambiguity",
                    chapter_new=chapter_index,
                    chapter_old=history[0].chapter_last_seen,
                    description=f"'{node.label}' 与历史记录语义相似，待确认",
                )
                result.ambiguities.append(item)
                node.conflict_status = "ambiguity"
                self.session.flush()

        self._update_node_importance(branch_id, chapter_index)
        self._update_fact_importance(branch_id, chapter_index)
        self._decay_episodic_importance(branch_id, chapter_index)
        self.session.flush()
        return result

    # ------------------------------------------------------------------
    # Classification helpers
    # ------------------------------------------------------------------

    def _classify(
        self,
        node: GraphNode,
        history: Sequence[GraphNode],
        artifact_payload: dict[str, object],
    ) -> str:
        """Return 'evolution' | 'contradiction' | 'ambiguity' | 'clean'."""
        latest = history[0]

        # Same node_type + label already exists → check metadata for state change
        old_meta: dict[str, object] = latest.metadata_json or {}
        new_meta: dict[str, object] = node.metadata_json or {}

        old_status = str(old_meta.get("status", "")).strip().lower()
        new_status = str(new_meta.get("status", "")).strip().lower()

        # If statuses are identical → clean update (occurrence bump)
        if old_status == new_status or not old_status or not new_status:
            return "clean"

        # Check whether the artifact has a state_transition_notes entry
        # that mentions this entity → evolution
        transition_notes: list[str] = []
        for key in ("state_transition_notes", "state_summary"):
            val = artifact_payload.get(key)
            if isinstance(val, list):
                transition_notes.extend(str(v) for v in val)
            elif isinstance(val, dict):
                transition_notes.extend(str(v) for v in val.values())
            elif isinstance(val, str):
                transition_notes.append(val)

        label_lower = node.label.lower()
        has_transition_support = any(
            label_lower in note.lower() for note in transition_notes
        )

        # Contradictory statuses (alive/dead, ally/enemy, etc.)
        _CONTRADICTORY_PAIRS: list[tuple[str, str]] = [
            ("alive", "dead"), ("生", "死"), ("存活", "死亡"),
            ("ally", "enemy"), ("盟友", "敌人"), ("友好", "敌对"),
            ("active", "inactive"), ("启用", "废除"),
        ]
        is_contradictory = any(
            (old_status in a and new_status in b) or (old_status in b and new_status in a)
            for a, b in _CONTRADICTORY_PAIRS
        )

        if is_contradictory and not has_transition_support:
            return "contradiction"
        if has_transition_support:
            return "evolution"
        # Statuses differ but no clear bridge → ambiguity
        return "ambiguity"

    # ------------------------------------------------------------------
    # DB helpers
    # ------------------------------------------------------------------

    def _load_new_nodes(self, branch_id: str, chapter_index: int) -> list[GraphNode]:
        return list(
            self.session.scalars(
                select(GraphNode)
                .where(GraphNode.branch_id == branch_id)
                .where(GraphNode.chapter_last_seen == chapter_index)
                .where(GraphNode.deleted_at.is_(None))
            ).all()
        )

    def _load_history_nodes(
        self,
        branch_id: str,
        node_type: str,
        label: str,
        before_chapter: int,
    ) -> list[GraphNode]:
        """Return prior nodes with same type+label, ordered by chapter_last_seen desc."""
        return list(
            self.session.scalars(
                select(GraphNode)
                .where(GraphNode.branch_id == branch_id)
                .where(GraphNode.node_type == node_type)
                .where(GraphNode.label == label)
                .where(GraphNode.chapter_last_seen < before_chapter)
                .where(GraphNode.deleted_at.is_(None))
                .order_by(GraphNode.chapter_last_seen.desc())
            ).all()
        )

    def _load_artifact_payload(
        self, branch_id: str, chapter_index: int
    ) -> dict[str, object]:
        artifact = self.session.scalar(
            select(ChapterArtifact)
            .where(ChapterArtifact.branch_id == branch_id)
            .where(ChapterArtifact.chapter_index == chapter_index)
            .where(ChapterArtifact.deleted_at.is_(None))
            .order_by(ChapterArtifact.created_at.desc())
        )
        if artifact is None:
            return {}
        return artifact.payload_json or {}

    def _mark_evolution(self, new_node: GraphNode, old_node: GraphNode) -> None:
        """Mark old node as superseded, bump version on new node."""
        old_node.conflict_status = "evolution"
        # GraphNode has no is_active column; edge-level is_active lives on GraphEdge
        old_node.superseded_by_node_id = new_node.id
        new_node.loom_version = old_node.loom_version + 1
        new_node.conflict_status = "evolution"
        self.session.flush()

    def _update_node_importance(self, branch_id: str, chapter_index: int) -> None:
        from sqlalchemy import union_all, literal_column

        src = (
            select(GraphEdge.source_node_id.label("node_id"))
            .where(GraphEdge.branch_id == branch_id)
            .where(GraphEdge.deleted_at.is_(None))
        )
        tgt = (
            select(GraphEdge.target_node_id.label("node_id"))
            .where(GraphEdge.branch_id == branch_id)
            .where(GraphEdge.deleted_at.is_(None))
        )
        edge_counts_sq = union_all(src, tgt).subquery()
        rows = self.session.execute(
            select(
                edge_counts_sq.c.node_id,
                func.count(literal_column("1")).label("edge_count"),
            )
            .group_by(edge_counts_sq.c.node_id)
        ).all()

        if not rows:
            return

        max_edges = max(r.edge_count for r in rows) or 1
        id_to_score = {
            r.node_id: round(0.3 + 0.7 * (r.edge_count / max_edges), 4)
            for r in rows
        }

        nodes = self.session.scalars(
            select(GraphNode)
            .where(GraphNode.branch_id == branch_id)
            .where(GraphNode.chapter_first_seen <= chapter_index)
            .where(GraphNode.id.in_(list(id_to_score)))
            .where(GraphNode.deleted_at.is_(None))
        ).all()
        for node in nodes:
            node.importance_score = id_to_score[node.id]

    def _update_fact_importance(self, branch_id: str, chapter_index: int) -> None:
        from sqlalchemy import union_all, literal_column

        rows = self.session.execute(
            select(FactRecord.label, func.count(FactRecord.id).label("cnt"))
            .where(FactRecord.branch_id == branch_id)
            .where(FactRecord.fact_type == "entity")
            .where(FactRecord.deleted_at.is_(None))
            .group_by(FactRecord.label)
        ).all()

        if not rows:
            return

        max_cnt = max(r.cnt for r in rows) or 1
        label_to_score = {
            r.label: round(0.3 + 0.7 * (r.cnt / max_cnt), 4)
            for r in rows
        }

        facts = self.session.scalars(
            select(FactRecord)
            .where(FactRecord.branch_id == branch_id)
            .where(FactRecord.chapter_index <= chapter_index)
            .where(FactRecord.fact_type == "entity")
            .where(FactRecord.deleted_at.is_(None))
        ).all()
        for fact in facts:
            if fact.label in label_to_score:
                fact.importance_score = label_to_score[fact.label]

    def _decay_episodic_importance(
        self, branch_id: str, current_chapter: int
    ) -> None:
        """Apply per-chapter decay to FactRecord.importance_score."""
        facts = list(
            self.session.scalars(
                select(FactRecord)
                .where(FactRecord.branch_id == branch_id)
                .where(FactRecord.chapter_index < current_chapter)
                .where(FactRecord.episodic_status == "active")
                .where(FactRecord.deleted_at.is_(None))
            ).all()
        )
        for fact in facts:
            rate = (
                _DECAY_IMPORTANT if fact.importance_score > 0.8 else _DECAY_NORMAL
            )
            fact.decay_factor = round(fact.decay_factor * rate, 6)
            # Mark as decayed when effective importance drops below threshold
            if fact.importance_score * fact.decay_factor < 0.05:
                fact.episodic_status = "decayed"
