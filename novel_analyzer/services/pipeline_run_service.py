"""Persistence helpers for background pipeline runs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from novel_analyzer.database.models import PipelineRun


@dataclass(frozen=True, slots=True)
class PipelineRunInfo:
    id: str
    run_id: str
    branch_id: str
    mode: str
    status: str
    target_from_chapter: int | None
    target_to_chapter: int | None
    concurrency: int
    provider_profile: str | None
    created_by: str | None
    started_at: object | None
    finished_at: object | None
    paused_at: object | None
    cancelled_at: object | None
    summary_json: dict[str, object]


class PipelineRunService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        *,
        run_id: str,
        branch_id: str,
        target_from_chapter: int | None,
        target_to_chapter: int | None,
        concurrency: int = 1,
        provider_profile: str | None = None,
        created_by: str | None = None,
    ) -> PipelineRun:
        item = PipelineRun(
            run_id=run_id,
            branch_id=branch_id,
            mode="range",
            status="pending",
            target_from_chapter=target_from_chapter,
            target_to_chapter=target_to_chapter,
            concurrency=concurrency,
            provider_profile=provider_profile,
            created_by=created_by,
            summary_json={},
        )
        self.session.add(item)
        self.session.commit()
        self.session.refresh(item)
        return item

    def get(self, pipeline_run_id: str) -> PipelineRun:
        item = self.session.scalar(select(PipelineRun).where(PipelineRun.id == pipeline_run_id))
        if item is None:
            raise ValueError(f"Unknown pipeline_run_id: {pipeline_run_id}")
        return item

    def list_for_branch(self, branch_id: str, limit: int = 20) -> list[PipelineRunInfo]:
        rows = self.session.scalars(
            select(PipelineRun)
            .where(PipelineRun.branch_id == branch_id)
            .where(PipelineRun.deleted_at.is_(None))
            .order_by(PipelineRun.created_at.desc())
            .limit(limit)
        ).all()
        return [self._to_info(row) for row in rows]

    def set_status(self, pipeline_run_id: str, status: str, **times: object) -> PipelineRun:
        item = self.get(pipeline_run_id)
        item.status = status
        for key, value in times.items():
            setattr(item, key, value)
        self.session.commit()
        self.session.refresh(item)
        return item

    def patch_summary(self, pipeline_run_id: str, patch: dict[str, object]) -> PipelineRun:
        item = self.get(pipeline_run_id)
        summary = dict(item.summary_json or {})
        summary.update(patch)
        item.summary_json = summary
        self.session.commit()
        self.session.refresh(item)
        return item

    def mark_started(self, pipeline_run_id: str) -> PipelineRun:
        now = datetime.now(UTC)
        return self.set_status(pipeline_run_id, "running", started_at=now, paused_at=None, cancelled_at=None, finished_at=None)

    def mark_paused(self, pipeline_run_id: str) -> PipelineRun:
        return self.set_status(pipeline_run_id, "paused", paused_at=datetime.now(UTC))

    def mark_cancelled(self, pipeline_run_id: str) -> PipelineRun:
        now = datetime.now(UTC)
        return self.set_status(pipeline_run_id, "cancelled", cancelled_at=now, finished_at=now)

    def mark_completed(self, pipeline_run_id: str) -> PipelineRun:
        return self.set_status(pipeline_run_id, "completed", finished_at=datetime.now(UTC))

    def mark_failed(self, pipeline_run_id: str, error_message: str) -> PipelineRun:
        item = self.patch_summary(pipeline_run_id, {"last_error": error_message})
        item.status = "failed"
        item.finished_at = datetime.now(UTC)
        self.session.commit()
        self.session.refresh(item)
        return item

    def _to_info(self, row: PipelineRun) -> PipelineRunInfo:
        return PipelineRunInfo(
            id=row.id,
            run_id=row.run_id,
            branch_id=row.branch_id,
            mode=row.mode,
            status=row.status,
            target_from_chapter=row.target_from_chapter,
            target_to_chapter=row.target_to_chapter,
            concurrency=row.concurrency,
            provider_profile=row.provider_profile,
            created_by=row.created_by,
            started_at=row.started_at,
            finished_at=row.finished_at,
            paused_at=row.paused_at,
            cancelled_at=row.cancelled_at,
            summary_json=row.summary_json,
        )
