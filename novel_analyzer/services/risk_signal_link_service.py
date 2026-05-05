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
    evidence_reasons: list[str]


class RiskSignalLinkService:
    def __init__(self, session: Session) -> None:
        self.session = session

    @staticmethod
    def _coerce_int(value: object, default: int = 0) -> int:
        if isinstance(value, int):
            return value
        if isinstance(value, float | str) and str(value).strip():
            return int(value)
        return default

    @staticmethod
    def _coerce_float(value: object, default: float = 0.0) -> float:
        if isinstance(value, int | float):
            return float(value)
        if isinstance(value, str) and value.strip():
            return float(value)
        return default

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
            raw_chapter_index = item.get("chapter_index")
            raw_score = item.get("score")
            raw_evidence = item.get("evidence_json")
            evidence_json = raw_evidence if isinstance(raw_evidence, dict) else {}
            record = RiskSignalLinkRecord(
                branch_id=branch_id,
                chapter_index=self._coerce_int(raw_chapter_index, chapter_index or 0),
                from_signal_id=str(item.get("from_signal_id") or ""),
                to_signal_id=str(item.get("to_signal_id") or ""),
                link_type=str(item.get("link_type") or ""),
                score=self._coerce_float(raw_score),
                evidence_json=dict(evidence_json),
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
                evidence_reasons=[
                    str(item) for item in row.evidence_json.get("evidence_reasons", [])
                ],
            )
            for row in records
        ]

    def list_branch_links(
        self, branch_id: str, chapter_index: int | None = None
    ) -> list[StoredRiskSignalLink]:
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
                evidence_reasons=[
                    str(item) for item in row.evidence_json.get("evidence_reasons", [])
                ],
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
            signal_type = str(item.get("signal_type") or "")
            if not signal_type:
                continue
            by_type.setdefault(signal_type, []).append(item)

        proposals: list[dict[str, object]] = []

        def _canonical_key(item: dict[str, object]) -> str:
            metadata = item.get("metadata_json")
            if isinstance(metadata, dict):
                return str(metadata.get("canonical_key") or "")
            return ""

        def _pair(left_type: str, right_type: str, link_type: str, score: float) -> None:
            for left in by_type.get(left_type, [])[:3]:
                for right in by_type.get(right_type, [])[:3]:
                    proposals.append(
                        {
                            "chapter_index": chapter_index,
                            "from_signal_id": str(left.get("id") or ""),
                            "to_signal_id": str(right.get("id") or ""),
                            "link_type": link_type,
                            "score": score,
                            "evidence_json": {
                                "left_signal_type": left_type,
                                "right_signal_type": right_type,
                                "left_text": str(left.get("raw_text") or ""),
                                "right_text": str(right.get("raw_text") or ""),
                                "candidate_reason": (
                                    f"{link_type}:{left_type}->{right_type}:chapter-{chapter_index}"
                                ),
                                "canonical_keys": [
                                    _canonical_key(left),
                                    _canonical_key(right),
                                ],
                            },
                        }
                    )

        _pair("foreshadow", "checker:foreshadow_payoff_consistency", "payoff_of", 0.75)
        _pair("relationship", "checker:relationship_consistency", "relationship_variant_of", 0.7)
        _pair("rule_scope", "checker:setting_scope_consistency", "rule_variant_of", 0.68)
        _pair("conflict_thread", "checker:thread_closure_consistency", "thread_continuation", 0.72)
        return proposals
