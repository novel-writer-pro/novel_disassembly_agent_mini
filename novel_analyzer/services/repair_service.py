"""Repair/backfill helpers for existing branch artifacts."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from novel_analyzer.database.models import ChapterArtifact, ChapterJob
from novel_analyzer.services.fact_service import FactService
from novel_analyzer.services.graph_service import GraphService
from novel_analyzer.services.retrieval_service import RetrievalService
from novel_analyzer.services.run_service import RunService


@dataclass(frozen=True, slots=True)
class RepairReport:
    """Summary of repair actions taken."""

    branch_id: str
    ensured_jobs: int
    retrieval_docs: int
    fact_batches: int
    graph_batches: int
    window_updates: int


class RepairService:
    """Backfill materialized layers for an already populated branch."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.run_service = RunService(session)
        self.retrieval_service = RetrievalService(session)
        self.fact_service = FactService(session)
        self.graph_service = GraphService(session)

    def repair_branch(self, branch_id: str) -> RepairReport:
        """Ensure jobs and derived materializations exist for active artifacts."""

        artifacts = self.session.scalars(
            select(ChapterArtifact)
            .where(ChapterArtifact.branch_id == branch_id)
            .where(ChapterArtifact.visibility == 'active')
            .order_by(ChapterArtifact.chapter_index)
        ).all()
        ensured_jobs = 0
        retrieval_docs = 0
        fact_batches = 0
        graph_batches = 0
        window_updates = 0
        for artifact in artifacts:
            job = self.session.scalar(
                select(ChapterJob)
                .where(ChapterJob.branch_id == branch_id)
                .where(ChapterJob.chapter_index == artifact.chapter_index)
            )
            if job is None:
                self.run_service.start_chapter_job(branch_id, artifact.chapter_index)
                self.run_service.complete_chapter_job(branch_id, artifact.chapter_index)
                ensured_jobs += 1
            elif job.status != 'validated':
                self.run_service.complete_chapter_job(branch_id, artifact.chapter_index)
                ensured_jobs += 1
            self.retrieval_service.materialize_for_artifact(artifact.id)
            retrieval_docs += 1
            self.fact_service.materialize_for_artifact(artifact.id)
            fact_batches += 1
            self.graph_service.materialize_for_artifact(artifact.id)
            graph_batches += 1
            if self.fact_service.materialize_window_if_ready(branch_id, artifact.chapter_index, 5):
                window_updates += 1
        return RepairReport(
            branch_id=branch_id,
            ensured_jobs=ensured_jobs,
            retrieval_docs=retrieval_docs,
            fact_batches=fact_batches,
            graph_batches=graph_batches,
            window_updates=window_updates,
        )
