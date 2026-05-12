"""Causal graph: typed directional cause-effect edges for logic-break detection.

Extends the existing graph with explicit causal relationships (X causes Y,
X enables Y, X prevents Y) and provides logic-break detection when later
chapters contradict established causal chains.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from novel_analyzer.database.models import GraphEdge, GraphNode


CAUSAL_EDGE_TYPES = frozenset({'causes', 'enables', 'prevents', 'triggers', 'blocks'})


@dataclass(frozen=True, slots=True)
class CausalLink:
    source_label: str
    target_label: str
    edge_type: str
    chapter_index: int
    confidence: float
    evidence: list[str]


@dataclass(frozen=True, slots=True)
class LogicBreak:
    description: str
    conflicting_chapter: int
    original_chapter: int
    causal_chain: list[str]
    severity: str


class CausalGraphService:
    """Manages causal edges and detects logic breaks in narrative chains."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def extract_causal_links(
        self,
        chapter_index: int,
        facts_data: dict[str, object],
        state_summary: dict[str, object],
    ) -> list[CausalLink]:
        """Extract causal relationships from chapter facts.

        Looks for cause-effect patterns in events, conflicts, and continuity.
        """
        links: list[CausalLink] = []

        events = facts_data.get('events', [])
        if not isinstance(events, list):
            events = []
        conflicts = facts_data.get('conflicts', [])
        if not isinstance(conflicts, list):
            conflicts = []

        for i, event in enumerate(events):
            if not isinstance(event, dict):
                continue
            label = str(event.get('label', ''))
            evidence = event.get('evidence', [])
            if not isinstance(evidence, list):
                evidence = []

            for next_event in events[i+1:]:
                if not isinstance(next_event, dict):
                    continue
                next_label = str(next_event.get('label', ''))
                if not next_label or not label:
                    continue
                if self._implies_causation(label, next_label, evidence):
                    links.append(CausalLink(
                        source_label=label,
                        target_label=next_label,
                        edge_type='causes',
                        chapter_index=chapter_index,
                        confidence=0.6,
                        evidence=evidence[:2],
                    ))

        for conflict in conflicts:
            if not isinstance(conflict, dict):
                continue
            conflict_label = str(conflict.get('label', ''))
            if not conflict_label:
                continue
            for event in events:
                if not isinstance(event, dict):
                    continue
                event_label = str(event.get('label', ''))
                if not event_label:
                    continue
                if self._conflict_triggers_event(conflict_label, event_label):
                    links.append(CausalLink(
                        source_label=conflict_label,
                        target_label=event_label,
                        edge_type='triggers',
                        chapter_index=chapter_index,
                        confidence=0.5,
                        evidence=conflict.get('evidence', [])[:2],
                    ))

        return links

    def detect_logic_breaks(
        self,
        branch_id: str,
        chapter_index: int,
        facts_data: dict[str, object],
    ) -> list[LogicBreak]:
        """Detect contradictions between current chapter facts and established causal chains."""
        breaks: list[LogicBreak] = []

        causal_edges = self.session.scalars(
            select(GraphEdge)
            .where(GraphEdge.branch_id == branch_id)
            .where(GraphEdge.edge_type.in_(list(CAUSAL_EDGE_TYPES)))
            .where(GraphEdge.chapter_first_seen < chapter_index)
            .order_by(GraphEdge.chapter_first_seen.desc())
            .limit(50)
        ).all()

        if not causal_edges:
            return breaks

        events = facts_data.get('events', [])
        if not isinstance(events, list):
            return breaks

        current_event_labels = set()
        for event in events:
            if isinstance(event, dict):
                label = str(event.get('label', '')).strip().lower()
                if label:
                    current_event_labels.add(label)

        for edge in causal_edges:
            if edge.edge_type == 'prevents':
                target_node = self.session.scalar(
                    select(GraphNode).where(GraphNode.id == edge.target_node_id)
                )
                if target_node is None:
                    continue
                prevented_label = target_node.label.lower()
                for current_label in current_event_labels:
                    if self._labels_overlap(prevented_label, current_label):
                        source_node = self.session.scalar(
                            select(GraphNode).where(GraphNode.id == edge.source_node_id)
                        )
                        source_label = source_node.label if source_node else '?'
                        breaks.append(LogicBreak(
                            description=(
                                f'第{chapter_index}章出现了"{current_label}"，'
                                f'但第{edge.chapter_first_seen}章已建立'
                                f'"{source_label}"阻止此事发生'
                            ),
                            conflicting_chapter=chapter_index,
                            original_chapter=edge.chapter_first_seen,
                            causal_chain=[source_label, 'prevents', target_node.label],
                            severity='warning',
                        ))

        return breaks

    def materialize_causal_edges(
        self,
        branch_id: str,
        chapter_index: int,
        links: list[CausalLink],
        node_cache: dict[str, GraphNode] | None = None,
    ) -> list[GraphEdge]:
        """Persist extracted causal links as graph edges."""
        edges: list[GraphEdge] = []

        for link in links:
            source_node = self._find_or_skip_node(branch_id, link.source_label)
            target_node = self._find_or_skip_node(branch_id, link.target_label)
            if source_node is None or target_node is None:
                continue

            existing = self.session.scalar(
                select(GraphEdge)
                .where(GraphEdge.branch_id == branch_id)
                .where(GraphEdge.source_node_id == source_node.id)
                .where(GraphEdge.target_node_id == target_node.id)
                .where(GraphEdge.edge_type == link.edge_type)
            )
            if existing is not None:
                existing.chapter_last_seen = chapter_index
                existing.weight += 0.5
                meta = dict(existing.metadata_json or {})
                meta['confidence'] = max(
                    float(meta.get('confidence', 0)), link.confidence
                )
                existing.metadata_json = meta
                edges.append(existing)
            else:
                edge = GraphEdge(
                    branch_id=branch_id,
                    source_node_id=source_node.id,
                    target_node_id=target_node.id,
                    edge_type=link.edge_type,
                    weight=1.0,
                    chapter_first_seen=chapter_index,
                    chapter_last_seen=chapter_index,
                    metadata_json={
                        'confidence': link.confidence,
                        'evidence': link.evidence,
                        'provenance': 'causal-extraction',
                    },
                )
                self.session.add(edge)
                edges.append(edge)

        if edges:
            self.session.flush()
        return edges

    def _find_or_skip_node(self, branch_id: str, label: str) -> GraphNode | None:
        return self.session.scalar(
            select(GraphNode)
            .where(GraphNode.branch_id == branch_id)
            .where(GraphNode.label == label)
        )

    @staticmethod
    def _implies_causation(source: str, target: str, evidence: list[str]) -> bool:
        causal_markers = ('导致', '因此', '所以', '于是', '使得', '引发', '触发', '迫使', '逼得')
        combined = source + target + ' '.join(str(e) for e in evidence)
        return any(marker in combined for marker in causal_markers)

    @staticmethod
    def _conflict_triggers_event(conflict: str, event: str) -> bool:
        trigger_markers = ('爆发', '激化', '升级', '反击', '报复', '觉醒', '突破')
        return any(marker in event for marker in trigger_markers)

    @staticmethod
    def _labels_overlap(a: str, b: str) -> bool:
        if not a or not b:
            return False
        if a in b or b in a:
            return True
        set_a = set(a)
        set_b = set(b)
        overlap = len(set_a & set_b)
        return overlap >= min(len(set_a), len(set_b)) * 0.6
