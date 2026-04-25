"""Inspection/export helpers for raw LLM outputs."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from novel_analyzer.database.models import ChapterRawOutput


class RawOutputService:
    """Retrieve raw output records for debugging and audit."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def latest_for_chapter(self, branch_id: str, chapter_index: int) -> ChapterRawOutput | None:
        """Return the latest raw output record for a branch/chapter."""

        return self.session.scalar(
            select(ChapterRawOutput)
            .where(ChapterRawOutput.branch_id == branch_id)
            .where(ChapterRawOutput.chapter_index == chapter_index)
            .order_by(ChapterRawOutput.job_attempt.desc(), ChapterRawOutput.created_at.desc())
        )
