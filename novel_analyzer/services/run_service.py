"""Run, branch, checkpoint, and artifact orchestration."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import and_, select, update
from sqlalchemy.orm import Session

from novel_analyzer.config.settings import Settings, get_settings
from novel_analyzer.database.models import (
    AnalysisRun,
    ChapterArtifact,
    ChapterJob,
    ChapterJobEvent,
    ChapterManifest,
    ChapterRawOutput,
    NovelSource,
    RunBranch,
    RunCheckpoint,
)
from novel_analyzer.services.job_event_service import JobEventService


def default_readable_artifact_clause() -> object:
    """Return the canonical active-artifact filter used by default readers."""

    return and_(
        ChapterArtifact.visibility == "active",
        ChapterArtifact.participates_in_downstream.is_(True),
    )


@dataclass(frozen=True, slots=True)
class FailedJobInfo:
    """Compact failed-job summary."""

    chapter_index: int
    attempts: int
    last_error: str
    failure_class: str | None = None
    failure_code: str | None = None


class RunService:
    """Handles analysis run lifecycle."""

    @staticmethod
    def _chapter_payload_with_profile_metadata(
        payload: dict[str, Any],
        *,
        branch_id: str,
        chapter_index: int,
        artifact_id: str,
        source_kind: str,
    ) -> dict[str, Any]:
        enriched = dict(payload)
        profile = dict(enriched.get('_deconstruction_profile') or {})
        if not profile:
            return enriched
        profile['canonical_artifact_id'] = artifact_id
        if not profile.get('idempotency_key'):
            profile_name = str(profile.get('profile') or 'quick')
            content_hash = str(profile.get('content_hash') or '')
            seed = json.dumps(
                {
                    'branch_id': branch_id,
                    'chapter_index': chapter_index,
                    'artifact_id': artifact_id,
                    'profile': profile_name,
                    'content_hash': content_hash,
                    'source_kind': source_kind,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
            profile['idempotency_key'] = hashlib.sha256(seed.encode('utf-8')).hexdigest()
        enriched['_deconstruction_profile'] = profile
        return enriched

    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.job_events = JobEventService(session)

    def _classify_failure(self, error: str) -> tuple[str, str]:
        lowered = error.lower()
        if '503' in lowered or 'service temporarily unavailable' in lowered:
            return 'provider_503', 'http_503'
        if '429' in lowered or 'rate limit' in lowered:
            return 'rate_limit', 'http_429'
        if '402' in lowered or 'insufficient balance' in lowered or 'billing_error' in lowered:
            return 'provider_balance', 'http_402'
        if 'timeout' in lowered:
            return 'timeout', 'timeout'
        if 'connection error' in lowered or 'remote end closed connection' in lowered:
            return 'provider_connection', 'provider_connection'
        if 'json' in lowered:
            return 'invalid_json', 'json_parse'
        if 'sparse result' in lowered:
            return 'sparse_result', 'sparse_result'
        if 'sql' in lowered or 'database' in lowered:
            return 'db_error', 'db_error'
        return 'unknown', 'unknown'

    def _run_id_for_branch(self, branch_id: str) -> str:
        branch = self.session.scalar(select(RunBranch).where(RunBranch.id == branch_id))
        if branch is None:
            raise ValueError(f"Unknown branch_id: {branch_id}")
        return branch.run_id

    def record_job_event(
        self,
        *,
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
        return self.job_events.record(
            run_id=self._run_id_for_branch(branch_id),
            branch_id=branch_id,
            chapter_index=chapter_index,
            event_type=event_type,
            message=message,
            job_id=job_id,
            stage=stage,
            level=level,
            payload_json=payload_json,
            commit=commit,
        )

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
            .where(default_readable_artifact_clause())
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
                failure_class=job.failure_class,
                failure_code=job.failure_code,
            )
            for job in jobs
        ]

    def list_retryable_failed_jobs(self, branch_id: str, limit: int = 20) -> list[FailedJobInfo]:
        """Return failed jobs that are still below the manual-recovery threshold."""

        return [
            item
            for item in self.list_failed_jobs(branch_id, limit)
            if item.attempts < self.settings.chapter_failure_retry_limit
        ]

    def list_terminal_failed_jobs(self, branch_id: str, limit: int = 20) -> list[FailedJobInfo]:
        """Return failed jobs that exhausted automatic retry budget."""

        return [
            item
            for item in self.list_failed_jobs(branch_id, limit)
            if item.attempts >= self.settings.chapter_failure_retry_limit
        ]

    def fail_stalled_jobs(self, branch_id: str, *, timeout_seconds: int | None = None) -> int:
        """Fail running jobs that have not heartbeated within the configured timeout."""

        timeout = timeout_seconds or self.settings.chapter_job_stall_timeout_seconds
        cutoff = datetime.now(UTC) - timedelta(seconds=timeout)
        jobs = self.session.scalars(
            select(ChapterJob)
            .where(ChapterJob.branch_id == branch_id)
            .where(ChapterJob.status == "running")
            .where(
                (
                    ChapterJob.heartbeat_at.is_(None)
                    & ChapterJob.started_at.is_not(None)
                    & (ChapterJob.started_at < cutoff)
                )
                | (
                    ChapterJob.heartbeat_at.is_not(None)
                    & (ChapterJob.heartbeat_at < cutoff)
                )
            )
            .order_by(ChapterJob.chapter_index)
        ).all()
        if not jobs:
            return 0

        for job in jobs:
            job.status = "failed"
            job.last_error = f"job stalled for more than {timeout} seconds"
            job.failure_class = "stalled"
            job.failure_code = "heartbeat_timeout"
            job.finished_at = datetime.now(UTC)  # type: ignore[assignment]
        self.session.commit()
        for job in jobs:
            self.record_job_event(
                branch_id=branch_id,
                chapter_index=job.chapter_index,
                job_id=job.id,
                event_type="job_stalled",
                stage=job.current_stage,
                level="warning",
                message=job.last_error or "job stalled",
                payload_json={
                    "failure_class": "stalled",
                    "failure_code": "heartbeat_timeout",
                    "timeout_seconds": timeout,
                },
            )
        return len(jobs)

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
        job.current_stage = None
        job.progress_percent = 0
        job.heartbeat_at = None
        job.next_retry_at = None
        job.failure_class = None
        job.failure_code = None
        job.finished_at = None
        self.session.commit()
        self.record_job_event(
            branch_id=branch_id,
            chapter_index=chapter_index,
            job_id=job.id,
            event_type="job_reset",
            message=f"chapter {chapter_index} reset for retry",
        )


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
            job.failure_class = "manual_cleanup"
            job.failure_code = "manual_cleanup"
            job.finished_at = datetime.now(UTC)  # type: ignore[assignment]
        self.session.commit()
        for job in jobs:
            self.record_job_event(
                branch_id=branch_id,
                chapter_index=job.chapter_index,
                job_id=job.id,
                event_type="job_force_failed",
                stage=job.current_stage,
                level="warning",
                message=reason,
                payload_json={"status": "failed"},
            )
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
                progress_percent=1,
                current_stage="queued",
                provider_name=self.settings.llm_provider_name,
                model_name=self.settings.llm_model_name,
                started_at=now,
                heartbeat_at=now,
            )
            self.session.add(job)
        else:
            job.status = "running"
            job.attempts += 1
            job.progress_percent = 1
            job.current_stage = "queued"
            job.started_at = now  # type: ignore[assignment]
            job.heartbeat_at = now  # type: ignore[assignment]
            job.finished_at = None
            job.last_error = None
            job.failure_class = None
            job.failure_code = None
        self.session.commit()
        self.session.refresh(job)
        self.record_job_event(
            branch_id=branch_id,
            chapter_index=chapter_index,
            job_id=job.id,
            event_type="job_started",
            stage=job.current_stage,
            message=f"chapter {chapter_index} started",
            payload_json={"attempts": job.attempts, "model_name": job.model_name or ""},
        )
        return job

    def update_job_progress(
        self,
        branch_id: str,
        chapter_index: int,
        *,
        current_stage: str,
        progress_percent: int,
        message: str | None = None,
        emit_event: bool = False,
    ) -> ChapterJob:
        job = self.session.scalar(
            select(ChapterJob)
            .where(ChapterJob.branch_id == branch_id)
            .where(ChapterJob.chapter_index == chapter_index)
        )
        if job is None:
            raise ValueError("chapter job missing")
        job.current_stage = current_stage
        job.progress_percent = progress_percent
        job.heartbeat_at = datetime.now(UTC)  # type: ignore[assignment]
        self.session.commit()
        self.session.refresh(job)
        if emit_event:
            self.record_job_event(
                branch_id=branch_id,
                chapter_index=chapter_index,
                job_id=job.id,
                event_type="stage_started",
                stage=current_stage,
                message=message or f"chapter {chapter_index} entered {current_stage}",
                payload_json={"progress_percent": progress_percent},
            )
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
        job.current_stage = "completed"
        job.progress_percent = 100
        job.heartbeat_at = datetime.now(UTC)  # type: ignore[assignment]
        job.finished_at = datetime.now(UTC)  # type: ignore[assignment]
        self.session.commit()
        self.record_job_event(
            branch_id=branch_id,
            chapter_index=chapter_index,
            job_id=job.id,
            event_type="job_completed",
            stage="completed",
            message=f"chapter {chapter_index} completed",
            payload_json={"attempts": job.attempts},
        )

    def fail_chapter_job(self, branch_id: str, chapter_index: int, error: str) -> None:
        """Mark a chapter job as failed."""

        job = self.session.scalar(
            select(ChapterJob)
            .where(ChapterJob.branch_id == branch_id)
            .where(ChapterJob.chapter_index == chapter_index)
        )
        if job is None:
            raise ValueError("chapter job missing")
        failure_class, failure_code = self._classify_failure(error)
        job.status = "failed"
        job.last_error = error
        job.failure_class = failure_class
        job.failure_code = failure_code
        job.finished_at = datetime.now(UTC)  # type: ignore[assignment]
        self.session.commit()
        self.record_job_event(
            branch_id=branch_id,
            chapter_index=chapter_index,
            job_id=job.id,
            event_type="job_failed",
            stage=job.current_stage,
            level="error",
            message=error,
            payload_json={
                "failure_class": failure_class,
                "failure_code": failure_code,
                "attempts": job.attempts,
            },
        )

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

        if participates_in_downstream:
            self.session.execute(
                update(ChapterArtifact)
                .where(ChapterArtifact.branch_id == branch_id)
                .where(ChapterArtifact.chapter_index == chapter_index)
                .where(ChapterArtifact.visibility == "active")
                .where(ChapterArtifact.participates_in_downstream.is_(True))
                .values(visibility="hidden")
            )

        checkpoint = self.session.scalar(
            select(RunCheckpoint)
            .where(RunCheckpoint.branch_id == branch_id)
            .where(RunCheckpoint.chapter_index == chapter_index)
        )
        if checkpoint is None:
            checkpoint = RunCheckpoint(
                branch_id=branch_id,
                chapter_index=chapter_index,
                langgraph_thread_id=langgraph_thread_id,
                langgraph_checkpoint_id=langgraph_checkpoint_id,
                state_summary={"committed": True, "chapter_index": chapter_index},
            )
            self.session.add(checkpoint)
        else:
            checkpoint.langgraph_thread_id = langgraph_thread_id
            checkpoint.langgraph_checkpoint_id = langgraph_checkpoint_id
            checkpoint.state_summary = {"committed": True, "chapter_index": chapter_index}
            checkpoint.visibility = "active"
            checkpoint.inherited_from_branch_id = None
            checkpoint.is_inherited = False

        artifact = ChapterArtifact(
            branch_id=branch_id,
            chapter_index=chapter_index,
            payload_json=payload,
            source_kind=source_kind,
            participates_in_downstream=participates_in_downstream,
        )
        self.session.add(artifact)
        self.session.flush()
        artifact.payload_json = self._chapter_payload_with_profile_metadata(
            payload,
            branch_id=branch_id,
            chapter_index=chapter_index,
            artifact_id=artifact.id,
            source_kind=source_kind,
        )
        self.session.commit()
        self.session.refresh(artifact)
        self.record_job_event(
            branch_id=branch_id,
            chapter_index=chapter_index,
            event_type="artifact_saved",
            message=f"chapter {chapter_index} artifact persisted",
            payload_json={"artifact_id": artifact.id, "source_kind": source_kind},
        )
        return artifact

    def restore_previous_active_artifact(
        self,
        branch_id: str,
        chapter_index: int,
        artifact_id: str,
    ) -> None:
        """Rollback a just-persisted artifact so failed downstream materialization stays blocking."""

        self.session.execute(
            update(ChapterArtifact)
            .where(ChapterArtifact.id == artifact_id)
            .values(visibility="hidden")
        )
        previous_artifact = self.session.scalar(
            select(ChapterArtifact)
            .where(ChapterArtifact.branch_id == branch_id)
            .where(ChapterArtifact.chapter_index == chapter_index)
            .where(ChapterArtifact.id != artifact_id)
            .order_by(ChapterArtifact.created_at.desc())
        )
        if previous_artifact is not None:
            previous_artifact.visibility = "active"
        self.session.commit()

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
            .where(default_readable_artifact_clause())
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
