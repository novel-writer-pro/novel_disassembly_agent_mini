"""Shared recovery wrappers."""

from __future__ import annotations

from novel_analyzer.application.dto import RecoveryResult
from novel_analyzer.application.queries import get_run_snapshot
from novel_analyzer.config.settings import Settings, get_settings
from novel_analyzer.database.session import create_session_factory
from novel_analyzer.services.repair_service import RepairService
from novel_analyzer.services.run_service import RunService


def recover_branch(
    *,
    action: str,
    run_id: str,
    branch_id: str,
    chapter_index: int | None = None,
    database_url: str | None = None,
    settings: Settings | None = None,
) -> RecoveryResult:
    """Run a supported recovery action and report the resulting state."""

    runtime = (settings or get_settings()).model_copy(deep=True)
    if database_url:
        runtime.database_url = database_url
    factory = create_session_factory(runtime)
    with factory() as session:
        run_service = RunService(session, runtime)
        if action == "retry-chapter":
            if chapter_index is None:
                raise ValueError("chapter_index is required for retry-chapter")
            run_service.ensure_chapter_retryable(branch_id, chapter_index)
            run_service.reset_failed_job(branch_id, chapter_index)
            message = f"retried chapter {chapter_index}"
        elif action == "retry-failed":
            failed = run_service.list_failed_jobs(branch_id)
            for item in failed:
                run_service.reset_failed_job(branch_id, item.chapter_index)
            message = f"reset {len(failed)} failed jobs"
        elif action == "clear-running":
            cleared = run_service.clear_running_jobs(
                branch_id,
                "application recovery clear-running",
            )
            message = f"cleared {cleared} running jobs"
        elif action == "repair":
            report = RepairService(session).repair_branch(branch_id)
            message = (
                "repair ensured "
                f"{report.ensured_jobs} jobs, {report.retrieval_docs} retrieval docs"
            )
        else:
            raise ValueError(f"Unsupported recovery action: {action}")

    snapshot = get_run_snapshot(
        run_id=run_id,
        branch_id=branch_id,
        database_url=database_url,
        settings=runtime,
    )
    return RecoveryResult(
        branch_id=branch_id,
        accepted_action=action,
        pipeline_state=snapshot.pipeline_state,
        message=message,
    )
