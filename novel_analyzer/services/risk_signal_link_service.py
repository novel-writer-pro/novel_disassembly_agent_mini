"""Link proposal helpers for semantic risk signals."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from novel_analyzer.database.models import RiskSignalLinkRecord


@dataclass(frozen=True, slots=True)
class StoredRiskSignalLink:
    id: str
    link_type: str
    score: float
    chapter_index: int
    from_signal_id: str
    to_signal_id: str


class RiskSignalLinkService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def replace_branch_links(
        self,
        *,
        branch_id: str,
        chapter_index: int | None = None,
        items: list[dict[str, object]],
    ) -> list[StoredRiskSignalLink]:
        stmt = delete(RiskSignalLinkRecord).where(RiskSignalLinkRecord.branch_id == branch_id)
        if chapter_index is not None:
            stmt = stmt.where(RiskSignalLinkRecord.chapter_index == chapter_index)
        self.session.execute(stmt)
        records: list[RiskSignalLinkRecord] = []
        for item in items:
            record = RiskSignalLinkRecord(
                branch_id=branch_id,
                chapter_index=int(item.get('chapter_index') or chapter_index or 0),
                from_signal_id=str(item.get('from_signal_id') or ''),
                to_signal_id=str(item.get('to_signal_id') or ''),
                link_type=str(item.get('link_type') or ''),
                score=float(item.get('score') or 0.0),
                evidence_json=dict(item.get('evidence_json') or {}),
            )
            self.session.add(record)
            records.append(record)
        self.session.flush()
        return [
            StoredRiskSignalLink(
                id=row.id,
                link_type=row.link_type,
                score=row.score,
                chapter_index=row.chapter_index,
                from_signal_id=row.from_signal_id,
                to_signal_id=row.to_signal_id,
            )
            for row in records
        ]

    def list_branch_links(self, branch_id: str, chapter_index: int | None = None) -> list[StoredRiskSignalLink]:
        stmt = select(RiskSignalLinkRecord).where(RiskSignalLinkRecord.branch_id == branch_id)
        if chapter_index is not None:
            stmt = stmt.where(RiskSignalLinkRecord.chapter_index == chapter_index)
        rows = self.session.scalars(
            stmt.order_by(RiskSignalLinkRecord.link_type, RiskSignalLinkRecord.score.desc())
        ).all()
        return [
            StoredRiskSignalLink(
                id=row.id,
                link_type=row.link_type,
                score=row.score,
                chapter_index=row.chapter_index,
                from_signal_id=row.from_signal_id,
                to_signal_id=row.to_signal_id,
            )
            for row in rows
        ]


    def build_minimal_link_proposals(
        self,
        *,
        branch_id: str,
        chapter_index: int,
        signals: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        by_type: dict[str, list[dict[str, object]]] = {}
        for item in signals:
            signal_type = str(item.get('signal_type') or '')
            if not signal_type:
                continue
            by_type.setdefault(signal_type, []).append(item)

        proposals: list[dict[str, object]] = []

        def _pair(left_type: str, right_type: str, link_type: str, score: float) -> None:
            for left in by_type.get(left_type, [])[:3]:
                for right in by_type.get(right_type, [])[:3]:
                    proposals.append(
                        {
                            'chapter_index': chapter_index,
                            'from_signal_id': str(left.get('id') or ''),
                            'to_signal_id': str(right.get('id') or ''),
                            'link_type': link_type,
                            'score': score,
                            'evidence_json': {
                                'left_signal_type': left_type,
                                'right_signal_type': right_type,
                                'left_text': str(left.get('raw_text') or ''),
                                'right_text': str(right.get('raw_text') or ''),
                            },
                        }
                    )

        _pair('foreshadow', 'checker:foreshadow_payoff_consistency', 'payoff_of', 0.75)
        _pair('relationship', 'checker:relationship_consistency', 'relationship_variant_of', 0.7)
        _pair('rule_scope', 'checker:setting_scope_consistency', 'rule_variant_of', 0.68)
        _pair('conflict_thread', 'checker:thread_closure_consistency', 'thread_continuation', 0.72)
        return proposals
