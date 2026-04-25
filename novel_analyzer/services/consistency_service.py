"""Consistency checks across branch artifacts, retrieval, facts, windows, and graph layers."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from novel_analyzer.database.models import (
    ChapterArtifact,
    ChapterJob,
    FactRecord,
    GraphEdge,
    GraphNode,
    RetrievalDocument,
    RunBranch,
    WindowArtifact,
)
from novel_analyzer.services.graph_service import GraphService


@dataclass(frozen=True, slots=True)
class ConsistencyIssue:
    """One consistency issue found in a branch."""

    severity: str
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class BranchConsistencyReport:
    """Summary of branch consistency checks."""

    branch_id: str
    issue_count: int
    issues: list[ConsistencyIssue]


class ConsistencyService:
    """Run lightweight integrity checks on a branch."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.graph_service = GraphService(session)

    def validate_branch(self, branch_id: str) -> BranchConsistencyReport:
        """Validate materialization consistency for one branch."""

        branch = self.session.scalar(select(RunBranch).where(RunBranch.id == branch_id))
        if branch is None:
            raise ValueError(f'Unknown branch_id: {branch_id}')

        issues: list[ConsistencyIssue] = []
        artifacts = self.session.scalars(
            select(ChapterArtifact)
            .where(ChapterArtifact.branch_id == branch_id)
            .where(ChapterArtifact.visibility == 'active')
            .order_by(ChapterArtifact.chapter_index)
        ).all()
        jobs = {
            job.chapter_index: job
            for job in self.session.scalars(
                select(ChapterJob).where(ChapterJob.branch_id == branch_id)
            ).all()
        }
        retrieval_docs = {
            doc.chapter_index: doc
            for doc in self.session.scalars(
                select(RetrievalDocument).where(RetrievalDocument.branch_id == branch_id)
            ).all()
        }
        fact_counts: dict[int, int] = {}
        for row in self.session.scalars(
            select(FactRecord).where(FactRecord.branch_id == branch_id)
        ).all():
            fact_counts[row.chapter_index] = fact_counts.get(row.chapter_index, 0) + 1

        node_count = len(
            self.session.scalars(select(GraphNode).where(GraphNode.branch_id == branch_id)).all()
        )
        edge_count = len(
            self.session.scalars(select(GraphEdge).where(GraphEdge.branch_id == branch_id)).all()
        )
        windows = self.session.scalars(
            select(WindowArtifact).where(WindowArtifact.branch_id == branch_id)
        ).all()

        for artifact in artifacts:
            chapter_index = artifact.chapter_index
            job = jobs.get(chapter_index)
            if job is None:
                issues.append(
                    ConsistencyIssue(
                        'warning',
                        'missing_job',
                        f'第{chapter_index}章缺少 chapter_job',
                    )
                )
            elif job.status != 'validated':
                issues.append(
                    ConsistencyIssue(
                        'warning',
                        'job_not_validated',
                        f'第{chapter_index}章 artifact 已存在，但 job 状态为 {job.status}',
                    )
                )
            if chapter_index not in retrieval_docs:
                issues.append(
                    ConsistencyIssue(
                        'error',
                        'missing_retrieval',
                        f'第{chapter_index}章缺少 retrieval_document',
                    )
                )
            if artifact.source_kind != 'demo' and fact_counts.get(chapter_index, 0) == 0:
                issues.append(
                    ConsistencyIssue(
                        'warning',
                        'missing_facts',
                        f'第{chapter_index}章缺少 fact_records',
                    )
                )

        completed = len(artifacts)
        expected_windows = completed // 5
        if len(windows) < expected_windows:
            issues.append(
                ConsistencyIssue(
                    'warning',
                    'missing_windows',
                    (
                        f'已完成 {completed} 章，理论应有 {expected_windows} 个窗口，'
                        f'当前仅 {len(windows)} 个'
                    ),
                )
            )
        has_non_demo_artifacts = any(artifact.source_kind != 'demo' for artifact in artifacts)
        if has_non_demo_artifacts and not node_count:
            issues.append(
                ConsistencyIssue('warning', 'missing_graph_nodes', '当前 branch 缺少 graph nodes')
            )
        if has_non_demo_artifacts and not edge_count:
            issues.append(
                ConsistencyIssue('warning', 'missing_graph_edges', '当前 branch 缺少 graph edges')
            )
        if has_non_demo_artifacts and node_count and edge_count:
            snapshot = self.graph_service.reasoning_snapshot(branch_id)
            overview = snapshot.get('overview', {})
            node_type_counts = (
                overview.get('node_type_counts', {})
                if isinstance(overview, dict)
                else {}
            )
            has_stateful_nodes = any(
                int(node_type_counts.get(key, 0)) > 0
                for key in ['foreshadow', 'conflict', 'relation', 'world_rule']
            )
            if has_stateful_nodes:
                state_summary = self.graph_service.state_summary_from_snapshot(snapshot)
                summary_has_signal = any(
                    isinstance(value, list) and value
                    for value in state_summary.values()
                )
                if not summary_has_signal:
                    issues.append(
                        ConsistencyIssue(
                            'warning',
                            'missing_state_summary_signals',
                            '图谱已存在，但未形成可用的状态摘要信号',
                        )
                    )

        return BranchConsistencyReport(branch_id=branch_id, issue_count=len(issues), issues=issues)
