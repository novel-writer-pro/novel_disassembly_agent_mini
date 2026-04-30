"""DB-backed review state service for risk clusters."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from novel_analyzer.database.models import ClusterReviewEventRecord, ClusterReviewRecord
from novel_analyzer.runtime.cluster_review_state import (
    ALLOWED_CLUSTER_STATUSES,
    ALLOWED_REVIEW_RESULTS,
)


class ClusterReviewStorageUnavailable(RuntimeError):
    """Raised when DB-backed review storage is not migrated yet."""


@dataclass(frozen=True, slots=True)
class ClusterReviewEntry:
    branch_id: str
    cluster_key: str
    cluster_status: str
    review_result: str = ""
    review_notes: str = ""
    review_owner: str = ""
    resolved_at: str = ""


class ClusterReviewService:
    """Persist and read review state from the database."""

    def __init__(self, session: Session) -> None:
        self.session = session

    @staticmethod
    def _is_missing_relation_error(exc: Exception) -> bool:
        message = str(exc).lower()
        return ("relation" in message and "does not exist" in message) or "no such table" in message

    @staticmethod
    def _validate(cluster_status: str, review_result: str, review_notes: str) -> None:
        if cluster_status not in ALLOWED_CLUSTER_STATUSES:
            raise ValueError(
                f"Unsupported cluster_status: {cluster_status}. "
                f"Allowed: {sorted(ALLOWED_CLUSTER_STATUSES)}"
            )
        if review_result not in ALLOWED_REVIEW_RESULTS:
            raise ValueError(
                f"Unsupported review_result: {review_result}. "
                f"Allowed: {sorted(ALLOWED_REVIEW_RESULTS)}"
            )
        if cluster_status == "resolved" and not review_result:
            raise ValueError("cluster_status=resolved requires a non-empty review_result")
        if cluster_status == "escalated" and review_result != "needs-escalation":
            raise ValueError("cluster_status=escalated requires review_result=needs-escalation")
        if cluster_status == "resolved" and review_result == "needs-escalation":
            raise ValueError(
                "cluster_status=resolved cannot be paired with review_result=needs-escalation"
            )
        if review_result == "needs-escalation" and not review_notes.strip():
            raise ValueError("review_result=needs-escalation requires non-empty review_notes")

    def read_branch(self, branch_id: str) -> dict[str, dict[str, str]]:
        try:
            rows = self.session.scalars(
                select(ClusterReviewRecord)
                .where(ClusterReviewRecord.branch_id == branch_id)
                .where(ClusterReviewRecord.visibility == "active")
                .order_by(ClusterReviewRecord.cluster_key)
            ).all()
        except (OperationalError, ProgrammingError) as exc:
            if not self._is_missing_relation_error(exc):
                raise
            self.session.rollback()
            raise ClusterReviewStorageUnavailable("cluster review tables are unavailable") from exc
        return {
            row.cluster_key: {
                "cluster_status": row.cluster_status,
                "review_result": row.review_result,
                "review_notes": row.review_notes,
                "review_owner": row.review_owner,
                "resolved_at": row.resolved_at_text,
            }
            for row in rows
        }

    def read_history(self, branch_id: str, cluster_key: str) -> list[dict[str, object]]:
        try:
            rows = self.session.scalars(
                select(ClusterReviewEventRecord)
                .where(ClusterReviewEventRecord.branch_id == branch_id)
                .where(ClusterReviewEventRecord.cluster_key == cluster_key)
                .order_by(ClusterReviewEventRecord.created_at)
            ).all()
        except (OperationalError, ProgrammingError) as exc:
            if not self._is_missing_relation_error(exc):
                raise
            self.session.rollback()
            return []
        return [
            {
                "event_id": row.id,
                "previous_cluster_status": row.previous_cluster_status,
                "previous_review_result": row.previous_review_result,
                "previous_review_notes": row.previous_review_notes,
                "previous_review_owner": row.previous_review_owner,
                "previous_resolved_at": row.previous_resolved_at_text,
                "cluster_status": row.cluster_status,
                "review_result": row.review_result,
                "review_notes": row.review_notes,
                "review_owner": row.review_owner,
                "resolved_at": row.resolved_at_text,
                "event_type": row.event_type,
                "created_at": row.created_at.isoformat()
                if hasattr(row.created_at, "isoformat")
                else "",
            }
            for row in rows
        ]

    def write(
        self,
        *,
        branch_id: str,
        cluster_key: str,
        cluster_status: str,
        review_result: str = "",
        review_notes: str = "",
        review_owner: str = "",
        resolved_at: str = "",
    ) -> ClusterReviewEntry:
        self._validate(cluster_status, review_result, review_notes)
        row = self.session.scalar(
            select(ClusterReviewRecord)
            .where(ClusterReviewRecord.branch_id == branch_id)
            .where(ClusterReviewRecord.cluster_key == cluster_key)
            .where(ClusterReviewRecord.visibility == "active")
        )
        previous_cluster_status = row.cluster_status if row is not None else ""
        previous_review_result = row.review_result if row is not None else ""
        previous_review_notes = row.review_notes if row is not None else ""
        previous_review_owner = row.review_owner if row is not None else ""
        previous_resolved_at = row.resolved_at_text if row is not None else ""
        if row is None:
            row = ClusterReviewRecord(
                branch_id=branch_id,
                cluster_key=cluster_key,
                cluster_status=cluster_status,
                review_result=review_result,
                review_notes=review_notes,
                review_owner=review_owner,
                resolved_at_text=resolved_at,
            )
            self.session.add(row)
        else:
            row.cluster_status = cluster_status
            row.review_result = review_result
            row.review_notes = review_notes
            row.review_owner = review_owner
            row.resolved_at_text = resolved_at
        self.session.add(
            ClusterReviewEventRecord(
                branch_id=branch_id,
                cluster_key=cluster_key,
                previous_cluster_status=previous_cluster_status,
                previous_review_result=previous_review_result,
                previous_review_notes=previous_review_notes,
                previous_review_owner=previous_review_owner,
                previous_resolved_at_text=previous_resolved_at,
                cluster_status=cluster_status,
                review_result=review_result,
                review_notes=review_notes,
                review_owner=review_owner,
                resolved_at_text=resolved_at,
                event_type="status_update",
            )
        )
        self.session.commit()
        return ClusterReviewEntry(
            branch_id=branch_id,
            cluster_key=cluster_key,
            cluster_status=cluster_status,
            review_result=review_result,
            review_notes=review_notes,
            review_owner=review_owner,
            resolved_at=resolved_at,
        )
