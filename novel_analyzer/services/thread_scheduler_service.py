"""Loom Phase 5: Thread scheduler service.

Classifies narrative threads (foreshadow/conflict/thread nodes) into
active / dormant / overdue buckets and suggests which thread to activate.

All data comes from existing GraphNode table – no new LLM calls required.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from novel_analyzer.database.models import GraphNode

THREAD_NODE_TYPES: frozenset[str] = frozenset({"foreshadow", "conflict", "thread"})

_DORMANT_THRESHOLD = 5
_OVERDUE_THRESHOLD = 15


@dataclass
class ThreadStatusReport:
    branch_id: str
    as_of_chapter: int
    active_threads: list[dict[str, object]] = field(default_factory=list)
    dormant_threads: list[dict[str, object]] = field(default_factory=list)
    overdue_threads: list[dict[str, object]] = field(default_factory=list)

    @property
    def overdue_ratio(self) -> float:
        total = len(self.active_threads) + len(self.dormant_threads) + len(self.overdue_threads)
        if total == 0:
            return 0.0
        return round(len(self.overdue_threads) / total, 4)

    def to_thread_status(self) -> dict[str, object]:
        return {
            "branch_id": self.branch_id,
            "as_of_chapter": self.as_of_chapter,
            "active_count": len(self.active_threads),
            "dormant_count": len(self.dormant_threads),
            "overdue_count": len(self.overdue_threads),
            "overdue_ratio": self.overdue_ratio,
            "active_threads": self.active_threads,
            "dormant_threads": self.dormant_threads,
            "overdue_threads": self.overdue_threads,
        }


@dataclass
class ThreadActivationSignal:
    branch_id: str
    chapter_index: int
    suggested_thread: str | None
    suggested_thread_type: str | None
    chapters_dormant: int
    suggestion: str

    def to_activation_signal(self) -> dict[str, object]:
        return {
            "branch_id": self.branch_id,
            "chapter_index": self.chapter_index,
            "suggested_thread": self.suggested_thread,
            "suggested_thread_type": self.suggested_thread_type,
            "chapters_dormant": self.chapters_dormant,
            "suggestion": self.suggestion,
        }


class ThreadSchedulerService:
    """Classify narrative threads and suggest activation for overdue ones."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def analyze_thread_status(
        self,
        branch_id: str,
        as_of_chapter: int,
    ) -> ThreadStatusReport:
        nodes = self.session.scalars(
            select(GraphNode)
            .where(GraphNode.branch_id == branch_id)
            .where(GraphNode.node_type.in_(list(THREAD_NODE_TYPES)))
            .where(GraphNode.conflict_status.notin_(["resolved"]))
            .where(GraphNode.deleted_at.is_(None))
            .order_by(GraphNode.importance_score.desc())
        ).all()

        active: list[dict[str, object]] = []
        dormant: list[dict[str, object]] = []
        overdue: list[dict[str, object]] = []

        for node in nodes:
            chapters_since = as_of_chapter - node.chapter_last_seen
            entry = {
                "label": node.label,
                "node_type": node.node_type,
                "chapter_first_seen": node.chapter_first_seen,
                "chapter_last_seen": node.chapter_last_seen,
                "chapters_since_last_seen": chapters_since,
                "importance_score": node.importance_score,
            }
            if chapters_since <= _DORMANT_THRESHOLD:
                active.append(entry)
            elif chapters_since <= _OVERDUE_THRESHOLD:
                dormant.append(entry)
            else:
                overdue.append(entry)

        return ThreadStatusReport(
            branch_id=branch_id,
            as_of_chapter=as_of_chapter,
            active_threads=active,
            dormant_threads=dormant,
            overdue_threads=overdue,
        )

    def suggest_thread_activation(
        self,
        branch_id: str,
        chapter_index: int,
    ) -> ThreadActivationSignal:
        report = self.analyze_thread_status(branch_id, chapter_index)

        if not report.overdue_threads and not report.dormant_threads:
            return ThreadActivationSignal(
                branch_id=branch_id,
                chapter_index=chapter_index,
                suggested_thread=None,
                suggested_thread_type=None,
                chapters_dormant=0,
                suggestion="当前无需激活线索，所有线索均在活跃状态",
            )

        candidates = report.overdue_threads or report.dormant_threads
        best = max(candidates, key=lambda t: float(t.get("importance_score", 0)))

        return ThreadActivationSignal(
            branch_id=branch_id,
            chapter_index=chapter_index,
            suggested_thread=str(best["label"]),
            suggested_thread_type=str(best["node_type"]),
            chapters_dormant=int(best["chapters_since_last_seen"]),
            suggestion=(
                f"建议本章激活线索「{best['label']}」"
                f"（已沉寂 {best['chapters_since_last_seen']} 章，"
                f"重要度 {best['importance_score']:.2f}）"
            ),
        )

    def get_total_thread_count(self, branch_id: str) -> int:
        return self.session.scalar(
            select(func.count(GraphNode.id))
            .where(GraphNode.branch_id == branch_id)
            .where(GraphNode.node_type.in_(list(THREAD_NODE_TYPES)))
            .where(GraphNode.conflict_status.notin_(["resolved"]))
            .where(GraphNode.deleted_at.is_(None))
        ) or 0
