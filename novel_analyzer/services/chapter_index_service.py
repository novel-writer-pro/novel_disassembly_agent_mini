"""Per-chapter operational index for one branch."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from novel_analyzer.database.models import (
    ChapterArtifact,
    ChapterJob,
    ChapterManifest,
    ChapterSegment,
    RetrievalDocument,
    RunBranch,
)


@dataclass(frozen=True, slots=True)
class ChapterIndexRow:
    """Compact per-chapter status row."""

    chapter_index: int
    title: str
    job_status: str
    has_artifact: bool
    has_retrieval: bool
    hook_score: float | None
    needs_human_review: bool
    summary: str


class ChapterIndexService:
    """Build a branch-wide chapter index view."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def list_rows(self, branch_id: str, limit: int = 200) -> list[ChapterIndexRow]:
        """Return per-chapter rows for one branch, including not-yet-processed chapters."""

        branch = self.session.scalar(select(RunBranch).where(RunBranch.id == branch_id))
        if branch is None:
            raise ValueError(f'Unknown branch_id: {branch_id}')
        manifest = self.session.scalar(
            select(ChapterManifest)
            .where(ChapterManifest.id == branch.run.manifest_id)
        )
        if manifest is None:
            raise ValueError('branch is missing manifest')
        segments = {
            seg.chapter_index: seg
            for seg in self.session.scalars(
                select(ChapterSegment)
                .where(ChapterSegment.manifest_id == manifest.id)
                .order_by(ChapterSegment.chapter_index)
                .limit(limit)
            ).all()
        }
        jobs = {
            job.chapter_index: job
            for job in self.session.scalars(
                select(ChapterJob)
                .where(ChapterJob.branch_id == branch_id)
                .order_by(ChapterJob.chapter_index)
                .limit(limit)
            ).all()
        }
        artifacts = {
            artifact.chapter_index: artifact
            for artifact in self.session.scalars(
                select(ChapterArtifact)
                .where(ChapterArtifact.branch_id == branch_id)
                .where(ChapterArtifact.visibility == 'active')
                .order_by(ChapterArtifact.chapter_index)
                .limit(limit)
            ).all()
        }
        retrieval_docs = {
            doc.chapter_index: doc
            for doc in self.session.scalars(
                select(RetrievalDocument)
                .where(RetrievalDocument.branch_id == branch_id)
                .order_by(RetrievalDocument.chapter_index)
                .limit(limit)
            ).all()
        }

        all_indexes = sorted(
            set(segments) | set(jobs) | set(artifacts) | set(retrieval_docs)
        )[:limit]
        rows: list[ChapterIndexRow] = []
        for chapter_index in all_indexes:
            artifact = artifacts.get(chapter_index)
            payload: dict[str, Any] = artifact.payload_json if artifact is not None else {}
            job = jobs.get(chapter_index)
            retrieval = retrieval_docs.get(chapter_index)
            segment = segments.get(chapter_index)
            title = str(
                payload.get('normalized_title')
                or (retrieval.title if retrieval else '')
                or (segment.normalized_title if segment else '')
            )
            summary = str(payload.get('chapter_summary') or payload.get('summary') or '')
            rows.append(
                ChapterIndexRow(
                    chapter_index=chapter_index,
                    title=title,
                    job_status=job.status if job is not None else 'pending',
                    has_artifact=artifact is not None,
                    has_retrieval=retrieval is not None,
                    hook_score=payload.get('hook_score'),
                    needs_human_review=bool(payload.get('needs_human_review', False)),
                    summary=summary,
                )
            )
        return rows
