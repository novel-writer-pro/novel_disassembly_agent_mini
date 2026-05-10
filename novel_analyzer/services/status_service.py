"""Operational status summaries for runs and branches."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from novel_analyzer.database.models import (
    ChapterArtifact,
    ChapterJob,
    ChapterManifest,
    FactRecord,
    GraphEdge,
    GraphNode,
    WindowArtifact,
)
from novel_analyzer.services.run_service import RunService, default_readable_artifact_clause


@dataclass(frozen=True, slots=True)
class RunStatus:
    """Compact operational status for one run/branch."""

    run_id: str
    branch_id: str
    branch_name: str
    branch_status: str
    manifest_chapter_count: int
    completed_chapters: int
    failed_jobs: int
    running_jobs: int
    next_chapter: int | None
    fact_count: int
    window_count: int
    graph_node_count: int
    graph_edge_count: int


class StatusService:
    """Build operational summaries for the current branch/run."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.run_service = RunService(session)

    def get_run_status(self, run_id: str, branch_id: str) -> RunStatus:
        """Return a compact run/branch status snapshot."""

        run, branch = self.run_service.get_run_and_branch(run_id, branch_id)
        self.run_service.fail_stalled_jobs(branch.id)
        manifest = self.session.scalar(
            select(ChapterManifest).where(ChapterManifest.id == run.manifest_id)
        )
        if manifest is None:
            raise ValueError('run is missing manifest')

        completed_chapters = self.session.scalar(
            select(func.count())
            .select_from(ChapterArtifact)
            .where(ChapterArtifact.branch_id == branch.id)
            .where(default_readable_artifact_clause())
        ) or 0
        failed_jobs = self.session.scalar(
            select(func.count())
            .select_from(ChapterJob)
            .where(ChapterJob.branch_id == branch.id)
            .where(ChapterJob.status == 'failed')
        ) or 0
        running_jobs = self.session.scalar(
            select(func.count())
            .select_from(ChapterJob)
            .where(ChapterJob.branch_id == branch.id)
            .where(ChapterJob.status == 'running')
        ) or 0
        fact_count = self.session.scalar(
            select(func.count()).select_from(FactRecord).where(FactRecord.branch_id == branch.id)
        ) or 0
        window_count = self.session.scalar(
            select(func.count())
            .select_from(WindowArtifact)
            .where(WindowArtifact.branch_id == branch.id)
        ) or 0
        graph_node_count = self.session.scalar(
            select(func.count()).select_from(GraphNode).where(GraphNode.branch_id == branch.id)
        ) or 0
        graph_edge_count = self.session.scalar(
            select(func.count()).select_from(GraphEdge).where(GraphEdge.branch_id == branch.id)
        ) or 0

        return RunStatus(
            run_id=run.id,
            branch_id=branch.id,
            branch_name=branch.name,
            branch_status=branch.status,
            manifest_chapter_count=manifest.chapter_count,
            completed_chapters=int(completed_chapters),
            failed_jobs=int(failed_jobs),
            running_jobs=int(running_jobs),
            next_chapter=self.run_service.next_chapter_index(run.id, branch.id),
            fact_count=int(fact_count),
            window_count=int(window_count),
            graph_node_count=int(graph_node_count),
            graph_edge_count=int(graph_edge_count),
        )
