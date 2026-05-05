"""Exact latest context lookup for risk-audit evidence packs."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from novel_analyzer.database.models import FactRecord


@dataclass(frozen=True, slots=True)
class ExactContextHit:
    fact_type: str
    label: str
    chapter_index: int


class RiskExactContextService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def latest_fact_hits(
        self,
        *,
        branch_id: str,
        query_text: str,
        before_chapter_index: int,
        fact_types: tuple[str, ...] = (),
        limit: int = 5,
    ) -> list[ExactContextHit]:
        query = query_text.strip()
        if not query:
            return []
        stmt = (
            select(FactRecord)
            .where(FactRecord.branch_id == branch_id)
            .where(FactRecord.chapter_index < before_chapter_index)
            .where(FactRecord.label.like(f"%{query}%"))
        )
        if fact_types:
            stmt = stmt.where(FactRecord.fact_type.in_(fact_types))
        rows = self.session.scalars(
            stmt.order_by(FactRecord.chapter_index.desc(), FactRecord.label).limit(limit)
        ).all()
        return [
            ExactContextHit(
                fact_type=row.fact_type,
                label=row.label,
                chapter_index=row.chapter_index,
            )
            for row in rows
        ]
