"""Context assembly for chapter-by-chapter deconstruction."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from novel_analyzer.database.models import ChapterArtifact, FactRecord, WindowArtifact
from novel_analyzer.services.graph_service import GraphService


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
        """Return a reasoning-oriented graph snapshot from earlier chapters."""

        if chapter_index <= 1:
            return {
                'overview': {
                    'node_count': 0,
                    'edge_count': 0,
                    'node_type_counts': {},
                    'edge_type_counts': {},
                },
                'central_nodes': [],
                'recent_timeline': [],
                'reasoning_paths': [],
                'active_conflicts': [],
                'open_foreshadowing': [],
                'world_rules': [],
                'nodes': [],
                'edges': [],
            }
        return GraphService(self.session).reasoning_snapshot(
            branch_id,
            upto_chapter=chapter_index - 1,
            node_limit=node_limit,
            edge_limit=edge_limit,
        )

    def state_summary_json(self, branch_id: str, chapter_index: int) -> dict[str, object]:
        """Return prior state-summary context from the reasoning graph."""

        if chapter_index <= 1:
            return {
                'new_foreshadowing': [],
                'paid_off_foreshadowing': [],
                'new_conflicts': [],
                'escalated_conflicts': [],
                'stable_relations': [],
                'evolved_relations': [],
                'observed_world_rules': [],
                'constraining_world_rules': [],
            }
        snapshot = GraphService(self.session).reasoning_snapshot(
            branch_id,
            upto_chapter=chapter_index - 1,
            node_limit=12,
            edge_limit=12,
        )
        return GraphService.state_summary_from_snapshot(
            snapshot,
            chapter_index=chapter_index - 1,
        )

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
            'state_summary': self.state_summary_json(branch_id, chapter_index),
            'window_summary': self.window_summary(branch_id, chapter_index),
        }
