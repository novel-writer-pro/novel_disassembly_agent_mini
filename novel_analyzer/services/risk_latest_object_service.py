"""Object-level latest state snapshots for risk evidence packs."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from novel_analyzer.database.models import ChapterArtifact
from novel_analyzer.services.graph_service import GraphService


@dataclass(frozen=True, slots=True)
class LatestObjectSnapshot:
    object_type: str
    label: str
    source: str


class RiskLatestObjectService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.graph_service = GraphService(session)

    def latest_snapshots(self, *, branch_id: str, chapter_index: int) -> list[LatestObjectSnapshot]:
        snapshot = self.graph_service.reasoning_snapshot(branch_id, upto_chapter=max(chapter_index - 1, 0), node_limit=10, edge_limit=12)
        state_summary = self.graph_service.state_summary_from_snapshot(snapshot)
        items: list[LatestObjectSnapshot] = []
        for label in state_summary.get('evolved_relations', [])[:3]:
            items.append(LatestObjectSnapshot(object_type='relationship', label=str(label), source='state_summary.evolved_relations'))
        for label in state_summary.get('constraining_world_rules', [])[:3]:
            items.append(LatestObjectSnapshot(object_type='rule_scope', label=str(label), source='state_summary.constraining_world_rules'))
        for label in state_summary.get('escalated_conflicts', [])[:3]:
            items.append(LatestObjectSnapshot(object_type='conflict_thread', label=str(label), source='state_summary.escalated_conflicts'))
        if items:
            return items

        latest_artifact = self.session.scalar(
            select(ChapterArtifact)
            .where(ChapterArtifact.branch_id == branch_id)
            .where(ChapterArtifact.chapter_index < chapter_index)
            .where(ChapterArtifact.visibility == 'active')
            .order_by(ChapterArtifact.chapter_index.desc())
        )
        if latest_artifact is None:
            return items
        state_summary = latest_artifact.payload_json.get('state_summary', {})
        if isinstance(state_summary, dict):
            for label in state_summary.get('evolved_relations', [])[:3]:
                items.append(LatestObjectSnapshot(object_type='relationship', label=str(label), source='artifact.state_summary.evolved_relations'))
            for label in state_summary.get('constraining_world_rules', [])[:3]:
                items.append(LatestObjectSnapshot(object_type='rule_scope', label=str(label), source='artifact.state_summary.constraining_world_rules'))
            for label in state_summary.get('escalated_conflicts', [])[:3]:
                items.append(LatestObjectSnapshot(object_type='conflict_thread', label=str(label), source='artifact.state_summary.escalated_conflicts'))
        return items
