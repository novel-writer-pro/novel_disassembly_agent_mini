"""Context assembly for chapter-by-chapter deconstruction."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from novel_analyzer.database.models import (
    ChapterArtifact,
    FactRecord,
    GraphEdge,
    GraphNode,
    WindowArtifact,
)


class ContextService:
    """Build prior context payloads for later chapter analysis."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def previous_summary(self, branch_id: str, chapter_index: int) -> str:
        """Return the latest prior chapter summary, if any."""

        if chapter_index <= 1:
            return ''
        artifact = self.session.scalar(
            select(ChapterArtifact)
            .where(ChapterArtifact.branch_id == branch_id)
            .where(ChapterArtifact.chapter_index == chapter_index - 1)
            .where(ChapterArtifact.visibility == 'active')
        )
        if artifact is None:
            return ''
        return str(artifact.payload_json.get('chapter_summary', ''))

    def fact_context_json(
        self,
        branch_id: str,
        chapter_index: int,
        limit: int = 20,
    ) -> dict[str, object]:
        """Return a compact fact context snapshot from earlier chapters."""

        rows = self.session.scalars(
            select(FactRecord)
            .where(FactRecord.branch_id == branch_id)
            .where(FactRecord.chapter_index < chapter_index)
            .order_by(FactRecord.chapter_index.desc(), FactRecord.created_at.desc())
            .limit(limit)
        ).all()
        facts = [
            {
                'chapter_index': row.chapter_index,
                'fact_type': row.fact_type,
                'label': row.label,
                'confidence': row.confidence,
            }
            for row in reversed(rows)
        ]
        return {'facts': facts}


    def graph_context_json(
        self,
        branch_id: str,
        chapter_index: int,
        node_limit: int = 12,
        edge_limit: int = 12,
    ) -> dict[str, object]:
        """Return a compact graph snapshot from earlier chapters."""

        if chapter_index <= 1:
            return {'nodes': [], 'edges': []}
        nodes = self.session.scalars(
            select(GraphNode)
            .where(GraphNode.branch_id == branch_id)
            .where(GraphNode.chapter_last_seen < chapter_index)
            .order_by(GraphNode.occurrence_count.desc(), GraphNode.label)
            .limit(node_limit)
        ).all()
        edges = self.session.scalars(
            select(GraphEdge)
            .where(GraphEdge.branch_id == branch_id)
            .where(GraphEdge.chapter_last_seen < chapter_index)
            .order_by(GraphEdge.weight.desc(), GraphEdge.edge_type)
            .limit(edge_limit)
        ).all()
        node_by_id = {node.id: node for node in nodes}
        edge_items = []
        for edge in edges:
            source = node_by_id.get(edge.source_node_id)
            target = node_by_id.get(edge.target_node_id)
            edge_items.append(
                {
                    'edge_type': edge.edge_type,
                    'weight': edge.weight,
                    'source': source.label if source else edge.source_node_id,
                    'target': target.label if target else edge.target_node_id,
                }
            )
        return {
            'nodes': [
                {
                    'node_type': node.node_type,
                    'label': node.label,
                    'occurrence_count': node.occurrence_count,
                }
                for node in nodes
            ],
            'edges': edge_items,
        }

    def window_summary(self, branch_id: str, chapter_index: int) -> str:
        """Return the latest completed window summary before this chapter."""

        if chapter_index <= 1:
            return ''
        window = self.session.scalar(
            select(WindowArtifact)
            .where(WindowArtifact.branch_id == branch_id)
            .where(WindowArtifact.window_end_chapter < chapter_index)
            .order_by(WindowArtifact.window_end_chapter.desc())
        )
        if window is None:
            return ''
        return str(window.payload_json.get('window_summary', ''))

    def context_bundle(
        self,
        branch_id: str,
        chapter_index: int,
        fact_limit: int = 20,
    ) -> dict[str, object]:
        """Return the assembled prior context that later chapters will consume."""

        return {
            'chapter_index': chapter_index,
            'previous_summary': self.previous_summary(branch_id, chapter_index),
            'fact_context': self.fact_context_json(branch_id, chapter_index, fact_limit),
            'graph_context': self.graph_context_json(branch_id, chapter_index),
            'window_summary': self.window_summary(branch_id, chapter_index),
        }
