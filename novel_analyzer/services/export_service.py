"""Export helpers for directly usable branch and chapter bundles."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from novel_analyzer.database.models import (
    ChapterArtifact,
    FactRecord,
    GraphEdge,
    GraphNode,
    RetrievalDocument,
    WindowArtifact,
)
from novel_analyzer.services.chapter_index_service import ChapterIndexService
from novel_analyzer.services.status_service import StatusService


class ExportService:
    """Build directly consumable JSON bundles for branches and chapters."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.status_service = StatusService(session)
        self.chapter_index_service = ChapterIndexService(session)

    def export_branch_bundle(self, run_id: str, branch_id: str) -> dict[str, object]:
        """Return a JSON-serializable bundle for one branch."""

        status = self.status_service.get_run_status(run_id, branch_id)
        windows = self.session.scalars(
            select(WindowArtifact)
            .where(WindowArtifact.branch_id == branch_id)
            .order_by(WindowArtifact.window_start_chapter)
        ).all()
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
        return {
            'status': {
                key: getattr(status, key) for key in status.__dataclass_fields__
            },
            'chapter_index': [
                {key: getattr(row, key) for key in row.__dataclass_fields__}
                for row in self.chapter_index_service.list_rows(branch_id)
            ],
            'windows': [window.payload_json for window in windows],
            'graph_nodes': [
                {
                    'node_type': node.node_type,
                    'label': node.label,
                    'chapter_first_seen': node.chapter_first_seen,
                    'chapter_last_seen': node.chapter_last_seen,
                    'occurrence_count': node.occurrence_count,
                }
                for node in nodes
            ],
            'graph_edges': [
                {
                    'edge_type': edge.edge_type,
                    'source_node_id': edge.source_node_id,
                    'target_node_id': edge.target_node_id,
                    'weight': edge.weight,
                    'chapter_first_seen': edge.chapter_first_seen,
                    'chapter_last_seen': edge.chapter_last_seen,
                }
                for edge in edges
            ],
        }

    def export_chapter_bundle(self, branch_id: str, chapter_index: int) -> dict[str, object]:
        """Return a chapter-level bundle with artifact, facts, retrieval, and graph slices."""

        artifact = self.session.scalar(
            select(ChapterArtifact)
            .where(ChapterArtifact.branch_id == branch_id)
            .where(ChapterArtifact.chapter_index == chapter_index)
            .where(ChapterArtifact.visibility == 'active')
            .order_by(ChapterArtifact.created_at.desc())
        )
        if artifact is None:
            raise ValueError('chapter artifact not found')

        facts = self.session.scalars(
            select(FactRecord)
            .where(FactRecord.branch_id == branch_id)
            .where(FactRecord.chapter_index == chapter_index)
            .order_by(FactRecord.fact_type, FactRecord.label)
        ).all()
        retrieval = self.session.scalar(
            select(RetrievalDocument)
            .where(RetrievalDocument.branch_id == branch_id)
            .where(RetrievalDocument.chapter_index == chapter_index)
        )
        nodes = self.session.scalars(
            select(GraphNode)
            .where(GraphNode.branch_id == branch_id)
            .where(GraphNode.chapter_first_seen <= chapter_index)
            .where(GraphNode.chapter_last_seen >= chapter_index)
            .order_by(GraphNode.node_type, GraphNode.label)
        ).all()
        edges = self.session.scalars(
            select(GraphEdge)
            .where(GraphEdge.branch_id == branch_id)
            .where(GraphEdge.chapter_first_seen <= chapter_index)
            .where(GraphEdge.chapter_last_seen >= chapter_index)
            .order_by(GraphEdge.edge_type)
        ).all()

        return {
            'chapter_index': chapter_index,
            'artifact': artifact.payload_json,
            'facts': [
                {
                    'fact_type': fact.fact_type,
                    'label': fact.label,
                    'confidence': fact.confidence,
                    'evidence_list': fact.evidence_list,
                }
                for fact in facts
            ],
            'retrieval': {
                'title': retrieval.title if retrieval else None,
                'summary_text': retrieval.summary_text if retrieval else None,
                'keyword_list': retrieval.keyword_list if retrieval else [],
                'query_hints': retrieval.query_hints if retrieval else [],
            },
            'graph_nodes': [
                {
                    'node_type': node.node_type,
                    'label': node.label,
                    'occurrence_count': node.occurrence_count,
                }
                for node in nodes
            ],
            'graph_edges': [
                {
                    'edge_type': edge.edge_type,
                    'source_node_id': edge.source_node_id,
                    'target_node_id': edge.target_node_id,
                    'weight': edge.weight,
                }
                for edge in edges
            ],
        }
