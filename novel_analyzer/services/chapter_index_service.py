"""Per-chapter operational index for one branch."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

from novel_analyzer.database.models import (
    ChapterArtifact,
    ChapterJob,
    ChapterRiskCardRecord,
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
    risk_level: str | None
    risk_count: int


@dataclass(frozen=True, slots=True)
class ChapterJobRow:
    """Detailed per-chapter job row for pipeline console."""

    chapter_index: int
    title: str
    status: str
    current_stage: str | None
    progress_percent: int
    attempts: int
    heartbeat_at: object | None
    failure_class: str | None
    failure_code: str | None
    last_error: str | None
    has_artifact: bool


class ChapterIndexService:
    """Build a branch-wide chapter index view."""

    def __init__(self, session: Session) -> None:
        self.session = session

    @staticmethod
    def _is_missing_relation_error(exc: Exception) -> bool:
        message = str(exc).lower()
        return "relation" in message and "does not exist" in message

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
        try:
            risk_cards = {
                record.chapter_index: record
                for record in self.session.scalars(
                    select(ChapterRiskCardRecord)
                    .where(ChapterRiskCardRecord.branch_id == branch_id)
                    .where(ChapterRiskCardRecord.visibility == 'active')
                    .order_by(ChapterRiskCardRecord.chapter_index)
                    .limit(limit)
                ).all()
            }
        except ProgrammingError as exc:
            if not self._is_missing_relation_error(exc):
                raise
            self.session.rollback()
            risk_cards = {}

        all_indexes = sorted(
            set(segments) | set(jobs) | set(artifacts) | set(retrieval_docs) | set(risk_cards)
        )[:limit]
        rows: list[ChapterIndexRow] = []
        for chapter_index in all_indexes:
            artifact = artifacts.get(chapter_index)
            payload: dict[str, Any] = artifact.payload_json if artifact is not None else {}
            job = jobs.get(chapter_index)
            retrieval = retrieval_docs.get(chapter_index)
            segment = segments.get(chapter_index)
            risk_card_record = risk_cards.get(chapter_index)
            risk_payload: dict[str, Any] = (
                risk_card_record.payload_json if risk_card_record is not None else {}
            )
            top_risks = risk_payload.get('top_risks', [])
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
                    risk_level=str(risk_payload.get('overall_risk_level')) if risk_payload else None,
                    risk_count=len(top_risks) if isinstance(top_risks, list) else 0,
                )
            )
        return rows

    def list_job_rows(self, branch_id: str, limit: int = 200) -> list[ChapterJobRow]:
        """Return detailed per-chapter job rows for pipeline monitoring."""

        branch = self.session.scalar(select(RunBranch).where(RunBranch.id == branch_id))
        if branch is None:
            raise ValueError(f'Unknown branch_id: {branch_id}')
        manifest = self.session.scalar(
            select(ChapterManifest).where(ChapterManifest.id == branch.run.manifest_id)
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

        all_indexes = sorted(set(segments) | set(jobs) | set(artifacts))[:limit]
        rows: list[ChapterJobRow] = []
        for chapter_index in all_indexes:
            segment = segments.get(chapter_index)
            job = jobs.get(chapter_index)
            artifact = artifacts.get(chapter_index)
            title = str(
                (artifact.payload_json.get('normalized_title') if artifact else '')
                or (segment.normalized_title if segment else '')
            )
            rows.append(
                ChapterJobRow(
                    chapter_index=chapter_index,
                    title=title,
                    status=job.status if job is not None else 'pending',
                    current_stage=job.current_stage if job is not None else None,
                    progress_percent=job.progress_percent if job is not None else 0,
                    attempts=job.attempts if job is not None else 0,
                    heartbeat_at=job.heartbeat_at if job is not None else None,
                    failure_class=job.failure_class if job is not None else None,
                    failure_code=job.failure_code if job is not None else None,
                    last_error=job.last_error if job is not None else None,
                    has_artifact=artifact is not None,
                )
            )
        return rows
