"""Run, branch, checkpoint, and artifact orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from novel_analyzer.config.settings import Settings, get_settings
from novel_analyzer.database.models import (
    AnalysisRun,
    ChapterArtifact,
    ChapterJob,
    ChapterManifest,
    ChapterRawOutput,
    NovelSource,
    RunBranch,
    RunCheckpoint,
)


@dataclass(frozen=True, slots=True)
class FailedJobInfo:
    """Compact failed-job summary."""

    chapter_index: int
    attempts: int
    last_error: str


class RunService:
    """Handles analysis run lifecycle."""

    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()

    def create_run(
        self,
        novel_id: str,
        manifest_id: str,
        branch_name: str = "main",
        analysis_profile: dict[str, Any] | None = None,
    ) -> tuple[AnalysisRun, RunBranch]:
        """Create a new run with an active root branch."""

        self.session.scalar(select(NovelSource).where(NovelSource.id == novel_id))
        self.session.scalar(select(ChapterManifest).where(ChapterManifest.id == manifest_id))

        run = AnalysisRun(
            novel_id=novel_id,
            manifest_id=manifest_id,
            llm_base_url=self.settings.llm_base_url,
            llm_model_name=self.settings.llm_model_name,
            analysis_profile=analysis_profile or {},
        )
        self.session.add(run)
        self.session.flush()

        branch = RunBranch(
            run_id=run.id,
            name=branch_name,
            fork_after_chapter_index=0,
            status="active",
        )
        self.session.add(branch)
        self.session.flush()

        run.active_branch_id = branch.id
        self.session.commit()
        self.session.refresh(run)
        self.session.refresh(branch)
        return run, branch

    def get_run_and_branch(self, run_id: str, branch_id: str) -> tuple[AnalysisRun, RunBranch]:
        """Load a run/branch pair and validate ownership."""

        run = self.session.scalar(select(AnalysisRun).where(AnalysisRun.id == run_id))
        branch = self.session.scalar(select(RunBranch).where(RunBranch.id == branch_id))
        if run is None or branch is None:
            raise ValueError("Unknown run_id or branch_id")
        if branch.run_id != run.id:
            raise ValueError("branch does not belong to run")
        return run, branch

    def next_chapter_index(self, run_id: str, branch_id: str) -> int | None:
        """Return the next chapter index that should be analyzed for a branch."""

        run, branch = self.get_run_and_branch(run_id, branch_id)
        manifest = self.session.scalar(
            select(ChapterManifest).where(ChapterManifest.id == run.manifest_id)
        )
        if manifest is None:
            raise ValueError("run is missing manifest")

        completed = self.session.scalars(
            select(ChapterArtifact.chapter_index)
            .where(ChapterArtifact.branch_id == branch.id)
            .where(ChapterArtifact.visibility == "active")
            .order_by(ChapterArtifact.chapter_index)
        ).all()
        done = set(completed)
        for chapter_index in range(1, manifest.chapter_count + 1):
            if chapter_index not in done:
                return chapter_index
        return None

    def list_failed_jobs(self, branch_id: str, limit: int = 20) -> list[FailedJobInfo]:
        """Return failed jobs for one branch."""

        jobs = self.session.scalars(
            select(ChapterJob)
            .where(ChapterJob.branch_id == branch_id)
            .where(ChapterJob.status == "failed")
            .order_by(ChapterJob.chapter_index)
            .limit(limit)
        ).all()
        return [
            FailedJobInfo(
                chapter_index=job.chapter_index,
                attempts=job.attempts,
                last_error=job.last_error or '',
            )
            for job in jobs
        ]

    def reset_failed_job(self, branch_id: str, chapter_index: int) -> None:
        """Reset a failed chapter job back to pending-like state for retry."""

        job = self.session.scalar(
            select(ChapterJob)
            .where(ChapterJob.branch_id == branch_id)
            .where(ChapterJob.chapter_index == chapter_index)
        )
        if job is None:
            raise ValueError("chapter job missing")
        job.status = "pending"
        job.last_error = None
        job.finished_at = None
        self.session.commit()


    def clear_running_jobs(self, branch_id: str, reason: str) -> int:
        """Mark stale running jobs as failed with a cleanup reason."""

        jobs = self.session.scalars(
            select(ChapterJob)
            .where(ChapterJob.branch_id == branch_id)
            .where(ChapterJob.status == "running")
            .order_by(ChapterJob.chapter_index)
        ).all()
        for job in jobs:
            job.status = "failed"
            job.last_error = reason
            job.finished_at = datetime.now(UTC)  # type: ignore[assignment]
        self.session.commit()
        return len(jobs)

    def start_chapter_job(self, branch_id: str, chapter_index: int) -> ChapterJob:
        """Mark a chapter job as running and increment attempts."""

        job = self.session.scalar(
            select(ChapterJob)
            .where(ChapterJob.branch_id == branch_id)
            .where(ChapterJob.chapter_index == chapter_index)
        )
        now = datetime.now(UTC)
        if job is None:
            job = ChapterJob(
                branch_id=branch_id,
                chapter_index=chapter_index,
                status="running",
                attempts=1,
                started_at=now,
            )
            self.session.add(job)
        else:
            job.status = "running"
            job.attempts += 1
            job.started_at = now  # type: ignore[assignment]
            job.finished_at = None
            job.last_error = None
        self.session.commit()
        self.session.refresh(job)
        return job

    def complete_chapter_job(self, branch_id: str, chapter_index: int) -> None:
        """Mark a chapter job as validated."""

        job = self.session.scalar(
            select(ChapterJob)
            .where(ChapterJob.branch_id == branch_id)
            .where(ChapterJob.chapter_index == chapter_index)
        )
        if job is None:
            raise ValueError("chapter job missing")
        job.status = "validated"
        job.finished_at = datetime.now(UTC)  # type: ignore[assignment]
        self.session.commit()

    def fail_chapter_job(self, branch_id: str, chapter_index: int, error: str) -> None:
        """Mark a chapter job as failed."""

        job = self.session.scalar(
            select(ChapterJob)
            .where(ChapterJob.branch_id == branch_id)
            .where(ChapterJob.chapter_index == chapter_index)
        )
        if job is None:
            raise ValueError("chapter job missing")
        job.status = "failed"
        job.last_error = error
        job.finished_at = datetime.now(UTC)  # type: ignore[assignment]
        self.session.commit()

    def record_raw_output(
        self,
        run_id: str,
        branch_id: str,
        chapter_index: int,
        job_attempt: int,
        raw_response_text: str,
        *,
        parsed_json: dict[str, object] | None,
        parse_status: str,
        parse_error: str | None,
        invocation_metadata: dict[str, object] | None = None,
    ) -> ChapterRawOutput:
        """Persist the raw model response and parse metadata."""

        raw_output = ChapterRawOutput(
            run_id=run_id,
            branch_id=branch_id,
            chapter_index=chapter_index,
            job_attempt=job_attempt,
            raw_response_text=raw_response_text,
            parsed_json=parsed_json,
            parse_status=parse_status,
            parse_error=parse_error,
            invocation_metadata=invocation_metadata or {},
        )
        self.session.add(raw_output)
        self.session.commit()
        self.session.refresh(raw_output)
        return raw_output

    def record_chapter_artifact(
        self,
        branch_id: str,
        chapter_index: int,
        payload: dict[str, Any],
        *,
        langgraph_thread_id: str | None = None,
        langgraph_checkpoint_id: str | None = None,
        source_kind: str = "model",
        participates_in_downstream: bool = True,
    ) -> ChapterArtifact:
        """Commit one chapter as the smallest durable unit."""

        branch = self.session.scalar(select(RunBranch).where(RunBranch.id == branch_id))
        if branch is None:
            raise ValueError(f"Unknown branch_id: {branch_id}")

        self.session.execute(
            update(ChapterArtifact)
            .where(ChapterArtifact.branch_id == branch_id)
            .where(ChapterArtifact.chapter_index == chapter_index)
            .where(ChapterArtifact.visibility == "active")
            .values(visibility="hidden")
        )

        self.session.execute(
            update(RunCheckpoint)
            .where(RunCheckpoint.branch_id == branch_id)
            .where(RunCheckpoint.chapter_index == chapter_index)
            .where(RunCheckpoint.visibility == "active")
            .values(visibility="hidden")
        )

        checkpoint = RunCheckpoint(
            branch_id=branch_id,
            chapter_index=chapter_index,
            langgraph_thread_id=langgraph_thread_id,
            langgraph_checkpoint_id=langgraph_checkpoint_id,
            state_summary={"committed": True, "chapter_index": chapter_index},
        )
        artifact = ChapterArtifact(
            branch_id=branch_id,
            chapter_index=chapter_index,
            payload_json=payload,
            source_kind=source_kind,
            participates_in_downstream=participates_in_downstream,
        )
        self.session.add_all([checkpoint, artifact])
        self.session.commit()
        self.session.refresh(artifact)
        return artifact

    def add_manual_artifact(
        self,
        branch_id: str,
        chapter_index: int,
        payload: dict[str, Any],
    ) -> ChapterArtifact:
        """Persist a manual patch that is retained but excluded by default downstream."""

        return self.record_chapter_artifact(
            branch_id,
            chapter_index,
            payload,
            source_kind="manual",
            participates_in_downstream=False,
        )

    def fork_branch(
        self,
        source_branch_id: str,
        keep_through: int,
        new_name: str | None = None,
    ) -> RunBranch:
        """Create a child branch and logically hide superseded downstream artifacts."""

        source_branch = self.session.scalar(
            select(RunBranch).where(RunBranch.id == source_branch_id)
        )
        if source_branch is None:
            raise ValueError(f"Unknown source_branch_id: {source_branch_id}")

        child = RunBranch(
            run_id=source_branch.run_id,
            name=new_name or f"{source_branch.name}-fork-{keep_through}",
            parent_branch_id=source_branch.id,
            fork_after_chapter_index=keep_through,
            status="active",
        )
        self.session.add(child)
        self.session.flush()

        checkpoints = self.session.scalars(
            select(RunCheckpoint)
            .where(RunCheckpoint.branch_id == source_branch.id)
            .where(RunCheckpoint.chapter_index <= keep_through)
            .where(RunCheckpoint.visibility == "active")
            .order_by(RunCheckpoint.chapter_index)
        ).all()
        for checkpoint in checkpoints:
            self.session.add(
                RunCheckpoint(
                    branch_id=child.id,
                    chapter_index=checkpoint.chapter_index,
                    langgraph_thread_id=checkpoint.langgraph_thread_id,
                    langgraph_checkpoint_id=checkpoint.langgraph_checkpoint_id,
                    state_summary=checkpoint.state_summary,
                    inherited_from_branch_id=source_branch.id,
                    is_inherited=True,
                )
            )

        artifacts = self.session.scalars(
            select(ChapterArtifact)
            .where(ChapterArtifact.branch_id == source_branch.id)
            .where(ChapterArtifact.chapter_index <= keep_through)
            .where(ChapterArtifact.visibility == "active")
            .order_by(ChapterArtifact.chapter_index)
        ).all()
        for artifact in artifacts:
            self.session.add(
                ChapterArtifact(
                    branch_id=child.id,
                    chapter_index=artifact.chapter_index,
                    artifact_type=artifact.artifact_type,
                    payload_json=artifact.payload_json,
                    status=artifact.status,
                    visibility="active",
                    source_kind=artifact.source_kind,
                    participates_in_downstream=artifact.participates_in_downstream,
                    inherited_from_branch_id=source_branch.id,
                    is_inherited=True,
                )
            )

        self.session.execute(
            update(ChapterArtifact)
            .where(ChapterArtifact.branch_id == source_branch.id)
            .where(ChapterArtifact.chapter_index > keep_through)
            .where(ChapterArtifact.visibility == "active")
            .values(visibility="hidden", status="superseded")
        )
        self.session.execute(
            update(RunCheckpoint)
            .where(RunCheckpoint.branch_id == source_branch.id)
            .where(RunCheckpoint.chapter_index > keep_through)
            .where(RunCheckpoint.visibility == "active")
            .values(visibility="hidden")
        )
        self.session.execute(
            update(RunBranch)
            .where(RunBranch.id == source_branch.id)
            .values(status="superseded")
        )
        self.session.execute(
            update(AnalysisRun)
            .where(AnalysisRun.id == source_branch.run_id)
            .values(active_branch_id=child.id)
        )
        self.session.commit()
        self.session.refresh(child)
        return child

    def branch_snapshot(self, branch_id: str) -> dict[str, Any]:
        """Return a compact branch summary for CLI inspection."""

        branch = self.session.scalar(select(RunBranch).where(RunBranch.id == branch_id))
        if branch is None:
            raise ValueError(f"Unknown branch_id: {branch_id}")

        artifacts = self.session.scalars(
            select(ChapterArtifact)
            .where(ChapterArtifact.branch_id == branch_id)
            .where(ChapterArtifact.visibility == "active")
            .order_by(ChapterArtifact.chapter_index)
        ).all()
        jobs = self.session.scalars(
            select(ChapterJob)
            .where(ChapterJob.branch_id == branch_id)
            .order_by(ChapterJob.chapter_index)
        ).all()
        return {
            "branch_id": branch.id,
            "name": branch.name,
            "status": branch.status,
            "fork_after_chapter_index": branch.fork_after_chapter_index,
            "visible_chapters": [artifact.chapter_index for artifact in artifacts],
            "job_statuses": {job.chapter_index: job.status for job in jobs},
            "manual_excluded_chapters": [
                artifact.chapter_index
                for artifact in artifacts
                if artifact.source_kind == "manual" and not artifact.participates_in_downstream
            ],
        }
