"""Foreshadowing lifecycle management: planted -> reinforced -> paid_off.

Tracks narrative foreshadowing through its lifecycle to ensure open threads
are always visible in subsequent chapter context, preventing lost plot threads
in long novels (100+ chapters).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from novel_analyzer.database.models import GraphNode


FORESHADOW_NODE_TYPE = 'foreshadow'

LIFECYCLE_STATES = ('planted', 'reinforced', 'paid_off', 'abandoned')


@dataclass(frozen=True, slots=True)
class ForeshadowThread:
    node_id: str
    label: str
    status: str
    chapter_planted: int
    chapter_last_seen: int
    reinforcement_count: int
    evidence: list[str]


class ForeshadowingService:
    """Manages foreshadowing lifecycle across chapters."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_open_threads(
        self,
        branch_id: str,
        before_chapter: int,
        limit: int = 20,
    ) -> list[ForeshadowThread]:
        """Return all foreshadowing threads that are still open (planted or reinforced)."""
        nodes = self.session.scalars(
            select(GraphNode)
            .where(GraphNode.branch_id == branch_id)
            .where(GraphNode.node_type == FORESHADOW_NODE_TYPE)
            .where(GraphNode.chapter_first_seen < before_chapter)
            .order_by(GraphNode.importance_score.desc(), GraphNode.chapter_first_seen.asc())
            .limit(limit * 2)
        ).all()

        threads: list[ForeshadowThread] = []
        for node in nodes:
            meta = node.metadata_json or {}
            status = str(meta.get('lifecycle_status', 'planted'))
            if status in ('paid_off', 'abandoned'):
                continue
            threads.append(ForeshadowThread(
                node_id=node.id,
                label=node.label,
                status=status,
                chapter_planted=node.chapter_first_seen,
                chapter_last_seen=node.chapter_last_seen,
                reinforcement_count=int(meta.get('reinforcement_count', 0)),
                evidence=meta.get('evidence', []) if isinstance(meta.get('evidence'), list) else [],
            ))
            if len(threads) >= limit:
                break
        return threads

    def mark_planted(
        self,
        branch_id: str,
        chapter_index: int,
        label: str,
        evidence: list[str] | None = None,
    ) -> GraphNode:
        """Register a new foreshadowing thread as planted."""
        existing = self.session.scalar(
            select(GraphNode)
            .where(GraphNode.branch_id == branch_id)
            .where(GraphNode.node_type == FORESHADOW_NODE_TYPE)
            .where(GraphNode.label == label)
        )
        if existing is not None:
            return self._reinforce(existing, chapter_index, evidence)

        node = GraphNode(
            branch_id=branch_id,
            node_type=FORESHADOW_NODE_TYPE,
            label=label,
            chapter_first_seen=chapter_index,
            chapter_last_seen=chapter_index,
            occurrence_count=1,
            metadata_json={
                'lifecycle_status': 'planted',
                'reinforcement_count': 0,
                'evidence': evidence or [],
                'history': [{'chapter': chapter_index, 'action': 'planted'}],
            },
        )
        self.session.add(node)
        self.session.flush([node])
        return node

    def mark_reinforced(
        self,
        branch_id: str,
        chapter_index: int,
        label: str,
        evidence: list[str] | None = None,
    ) -> GraphNode | None:
        """Mark an existing foreshadowing thread as reinforced in this chapter."""
        node = self.session.scalar(
            select(GraphNode)
            .where(GraphNode.branch_id == branch_id)
            .where(GraphNode.node_type == FORESHADOW_NODE_TYPE)
            .where(GraphNode.label == label)
        )
        if node is None:
            return self.mark_planted(branch_id, chapter_index, label, evidence)
        return self._reinforce(node, chapter_index, evidence)

    def mark_paid_off(
        self,
        branch_id: str,
        chapter_index: int,
        label: str,
        evidence: list[str] | None = None,
    ) -> GraphNode | None:
        """Mark a foreshadowing thread as paid off (resolved)."""
        node = self.session.scalar(
            select(GraphNode)
            .where(GraphNode.branch_id == branch_id)
            .where(GraphNode.node_type == FORESHADOW_NODE_TYPE)
            .where(GraphNode.label == label)
        )
        if node is None:
            return None
        meta = dict(node.metadata_json or {})
        meta['lifecycle_status'] = 'paid_off'
        meta['paid_off_chapter'] = chapter_index
        if evidence:
            existing_evidence = meta.get('evidence', [])
            if isinstance(existing_evidence, list):
                meta['evidence'] = existing_evidence + evidence
        history = meta.get('history', [])
        if isinstance(history, list):
            history.append({'chapter': chapter_index, 'action': 'paid_off'})
            meta['history'] = history
        node.metadata_json = meta
        node.chapter_last_seen = chapter_index
        return node

    def update_from_facts(
        self,
        branch_id: str,
        chapter_index: int,
        foreshadowing_facts: list[dict[str, object]],
        state_summary: dict[str, object],
    ) -> list[ForeshadowThread]:
        """Update foreshadowing lifecycle from chapter fact extraction results.

        Called after each chapter analysis to maintain lifecycle state.
        """
        paid_off_labels = set()
        paid_off_raw = state_summary.get('paid_off_foreshadowing', [])
        if isinstance(paid_off_raw, list):
            for item in paid_off_raw:
                text = str(item).strip()
                if text:
                    paid_off_labels.add(text.lower())

        for fact in foreshadowing_facts:
            if not isinstance(fact, dict):
                continue
            label = str(fact.get('label', '')).strip()
            if not label:
                continue
            evidence = fact.get('evidence', [])
            if not isinstance(evidence, list):
                evidence = [str(evidence)] if evidence else []

            if label.lower() in paid_off_labels:
                self.mark_paid_off(branch_id, chapter_index, label, evidence)
            else:
                self.mark_reinforced(branch_id, chapter_index, label, evidence)

        return self.get_open_threads(branch_id, before_chapter=chapter_index + 1)

    def open_threads_context_json(
        self,
        branch_id: str,
        chapter_index: int,
        limit: int = 10,
    ) -> list[dict[str, object]]:
        """Return open threads formatted for injection into chapter context."""
        threads = self.get_open_threads(branch_id, before_chapter=chapter_index, limit=limit)
        return [
            {
                'label': t.label,
                'status': t.status,
                'planted_chapter': t.chapter_planted,
                'last_seen_chapter': t.chapter_last_seen,
                'age': chapter_index - t.chapter_planted,
                'reinforcements': t.reinforcement_count,
            }
            for t in threads
        ]

    def _reinforce(
        self,
        node: GraphNode,
        chapter_index: int,
        evidence: list[str] | None = None,
    ) -> GraphNode:
        meta = dict(node.metadata_json or {})
        current_status = meta.get('lifecycle_status', 'planted')
        if current_status in ('paid_off', 'abandoned'):
            return node
        meta['lifecycle_status'] = 'reinforced'
        meta['reinforcement_count'] = int(meta.get('reinforcement_count', 0)) + 1
        if evidence:
            existing_evidence = meta.get('evidence', [])
            if isinstance(existing_evidence, list):
                meta['evidence'] = existing_evidence + evidence
        history = meta.get('history', [])
        if isinstance(history, list):
            history.append({'chapter': chapter_index, 'action': 'reinforced'})
            meta['history'] = history
        node.metadata_json = meta
        node.chapter_last_seen = chapter_index
        node.occurrence_count += 1
        return node
