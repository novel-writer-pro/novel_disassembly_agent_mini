"""Graph materialization from chapter artifacts and fact records."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from novel_analyzer.database.models import ChapterArtifact, GraphEdge, GraphNode


@dataclass(frozen=True, slots=True)
class GraphSummary:
    """Human-usable summary of a branch graph."""

    branch_id: str
    node_count: int
    edge_count: int
    top_entities: list[tuple[str, int]]
    top_events: list[tuple[str, int]]
    progression_edges: list[str]


class GraphService:
    """Build a lightweight narrative graph for one branch."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def _upsert_node(
        self,
        branch_id: str,
        node_type: str,
        label: str,
        chapter_index: int,
        metadata_json: dict[str, object] | None = None,
    ) -> GraphNode:
        node = self.session.scalar(
            select(GraphNode)
            .where(GraphNode.branch_id == branch_id)
            .where(GraphNode.node_type == node_type)
            .where(GraphNode.label == label)
        )
        if node is None:
            node = GraphNode(
                branch_id=branch_id,
                node_type=node_type,
                label=label,
                chapter_first_seen=chapter_index,
                chapter_last_seen=chapter_index,
                occurrence_count=1,
                metadata_json=metadata_json or {},
            )
            self.session.add(node)
            self.session.flush()
            return node
        node.chapter_last_seen = chapter_index
        node.occurrence_count += 1
        if metadata_json:
            node.metadata_json = {**node.metadata_json, **metadata_json}
        self.session.flush()
        return node

    def _upsert_edge(
        self,
        branch_id: str,
        source_node_id: str,
        target_node_id: str,
        edge_type: str,
        chapter_index: int,
    ) -> None:
        edge = self.session.scalar(
            select(GraphEdge)
            .where(GraphEdge.branch_id == branch_id)
            .where(GraphEdge.source_node_id == source_node_id)
            .where(GraphEdge.target_node_id == target_node_id)
            .where(GraphEdge.edge_type == edge_type)
        )
        if edge is None:
            edge = GraphEdge(
                branch_id=branch_id,
                source_node_id=source_node_id,
                target_node_id=target_node_id,
                edge_type=edge_type,
                weight=1.0,
                chapter_first_seen=chapter_index,
                chapter_last_seen=chapter_index,
                metadata_json={},
            )
            self.session.add(edge)
            self.session.flush()
            return
        edge.chapter_last_seen = chapter_index
        edge.weight += 1.0
        self.session.flush()

    def _latest_event_node(self, branch_id: str, before_chapter: int) -> GraphNode | None:
        return self.session.scalar(
            select(GraphNode)
            .where(GraphNode.branch_id == branch_id)
            .where(GraphNode.node_type == 'event')
            .where(GraphNode.chapter_last_seen < before_chapter)
            .order_by(GraphNode.chapter_last_seen.desc(), GraphNode.occurrence_count.desc())
        )

    def materialize_for_artifact(self, artifact_id: str) -> tuple[list[GraphNode], list[GraphEdge]]:
        """Materialize graph nodes and edges for one chapter artifact."""

        artifact = self.session.scalar(
            select(ChapterArtifact).where(ChapterArtifact.id == artifact_id)
        )
        if artifact is None:
            raise ValueError(f"Unknown artifact_id: {artifact_id}")

        payload = artifact.payload_json
        branch_id = artifact.branch_id
        chapter_index = artifact.chapter_index
        nodes: list[GraphNode] = []

        key_entities = cast(list[object], payload.get('key_entities', []))
        key_events = cast(list[object], payload.get('key_events', []))
        entity_labels = [
            item.strip()
            for item in key_entities
            if isinstance(item, str) and item.strip()
        ]
        event_labels = [
            item.strip()
            for item in key_events
            if isinstance(item, str) and item.strip()
        ]

        entity_nodes = [
            self._upsert_node(branch_id, 'entity', label, chapter_index)
            for label in entity_labels
        ]
        event_nodes = [
            self._upsert_node(branch_id, 'event', label, chapter_index)
            for label in event_labels
        ]
        nodes.extend(entity_nodes)
        nodes.extend(event_nodes)

        for left, right in combinations(entity_nodes, 2):
            self._upsert_edge(branch_id, left.id, right.id, 'co_occurs', chapter_index)
        for event_node in event_nodes:
            previous_event = self._latest_event_node(branch_id, chapter_index)
            if previous_event is not None:
                self._upsert_edge(
                    branch_id,
                    previous_event.id,
                    event_node.id,
                    'follows',
                    chapter_index,
                )
            for entity_node in entity_nodes:
                self._upsert_edge(
                    branch_id,
                    entity_node.id,
                    event_node.id,
                    'participates_in',
                    chapter_index,
                )
                if entity_node.chapter_first_seen < chapter_index:
                    self._upsert_edge(
                        branch_id,
                        entity_node.id,
                        event_node.id,
                        'persists_into',
                        chapter_index,
                    )

        self.session.commit()
        edge_rows = list(
            self.session.scalars(select(GraphEdge).where(GraphEdge.branch_id == branch_id)).all()
        )
        return nodes, edge_rows

    def summarize_branch(self, branch_id: str) -> GraphSummary:
        """Return a compact graph summary that is easier to inspect than raw nodes/edges."""

        nodes = self.session.scalars(
            select(GraphNode)
            .where(GraphNode.branch_id == branch_id)
            .order_by(GraphNode.node_type, GraphNode.label)
        ).all()
        edges = self.session.scalars(
            select(GraphEdge)
            .where(GraphEdge.branch_id == branch_id)
            .order_by(GraphEdge.edge_type)
        ).all()
        top_entities = sorted(
            [(node.label, node.occurrence_count) for node in nodes if node.node_type == 'entity'],
            key=lambda item: (-item[1], item[0]),
        )[:10]
        top_events = sorted(
            [(node.label, node.occurrence_count) for node in nodes if node.node_type == 'event'],
            key=lambda item: (-item[1], item[0]),
        )[:10]
        node_by_id = {node.id: node for node in nodes}
        progression_edges = []
        for edge in edges:
            if edge.edge_type != 'follows':
                continue
            source = node_by_id.get(edge.source_node_id)
            target = node_by_id.get(edge.target_node_id)
            if source is None or target is None:
                continue
            progression_edges.append(f"{source.label} -> {target.label}")
        return GraphSummary(
            branch_id=branch_id,
            node_count=len(nodes),
            edge_count=len(edges),
            top_entities=top_entities,
            top_events=top_events,
            progression_edges=progression_edges[:20],
        )
