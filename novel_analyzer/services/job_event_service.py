"""Job event recording and retrieval."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from novel_analyzer.database.models import ChapterJobEvent


@dataclass(frozen=True, slots=True)
class JobEventInfo:
    id: str
    run_id: str
    branch_id: str
    chapter_index: int
    event_type: str
    stage: str | None
    level: str
    message: str
    payload_json: dict[str, object]
    created_at: object


class JobEventService:
    """Read/write operational events for chapter jobs."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def record(
        self,
        *,
        run_id: str,
        branch_id: str,
        chapter_index: int,
        event_type: str,
        message: str,
        job_id: str | None = None,
        stage: str | None = None,
        level: str = "info",
        payload_json: dict[str, object] | None = None,
        commit: bool = True,
    ) -> ChapterJobEvent:
        event = ChapterJobEvent(
            run_id=run_id,
            branch_id=branch_id,
            chapter_index=chapter_index,
            job_id=job_id,
            event_type=event_type,
            stage=stage,
            level=level,
            message=message,
            payload_json=payload_json or {},
        )
        self.session.add(event)
        if commit:
            self.session.commit()
            self.session.refresh(event)
        return event

    def list_for_branch(self, branch_id: str, limit: int = 100) -> list[JobEventInfo]:
        rows = self.session.scalars(
            select(ChapterJobEvent)
            .where(ChapterJobEvent.branch_id == branch_id)
            .where(ChapterJobEvent.deleted_at.is_(None))
            .order_by(ChapterJobEvent.created_at.desc())
            .limit(limit)
        ).all()
        return [
            JobEventInfo(
                id=row.id,
                run_id=row.run_id,
                branch_id=row.branch_id,
                chapter_index=row.chapter_index,
                event_type=row.event_type,
                stage=row.stage,
                level=row.level,
                message=row.message,
                payload_json=row.payload_json,
                created_at=row.created_at,
            )
            for row in rows
        ]

    def list_for_chapter(self, branch_id: str, chapter_index: int, limit: int = 100) -> list[JobEventInfo]:
        rows = self.session.scalars(
            select(ChapterJobEvent)
            .where(ChapterJobEvent.branch_id == branch_id)
            .where(ChapterJobEvent.chapter_index == chapter_index)
            .where(ChapterJobEvent.deleted_at.is_(None))
            .order_by(ChapterJobEvent.created_at.desc())
            .limit(limit)
        ).all()
        return [
            JobEventInfo(
                id=row.id,
                run_id=row.run_id,
                branch_id=row.branch_id,
                chapter_index=row.chapter_index,
                event_type=row.event_type,
                stage=row.stage,
                level=row.level,
                message=row.message,
                payload_json=row.payload_json,
                created_at=row.created_at,
            )
            for row in rows
        ]
