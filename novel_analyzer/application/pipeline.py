"""Shared pipeline progression helpers."""

from __future__ import annotations

from sqlalchemy import select

from novel_analyzer.application.queries import _derive_pipeline_state, get_run_snapshot
from novel_analyzer.config.settings import Settings, get_settings
from novel_analyzer.database.models import AnalysisRun
from novel_analyzer.database.session import create_session_factory
from novel_analyzer.services.analysis_service import AnalysisService
from novel_analyzer.services.run_service import RunService


def _set_pipeline_hint(
    run: AnalysisRun,
    *,
    pipeline_profile: str | None = None,
    state_hint: str | None = None,
    error_message: str | None = None,
) -> None:
    profile = dict(run.analysis_profile)
    if pipeline_profile is not None:
        profile["pipeline_profile"] = pipeline_profile
    if state_hint is None:
        profile.pop("pipeline_state_hint", None)
        profile.pop("pipeline_last_error", None)
    else:
        profile["pipeline_state_hint"] = state_hint
        profile["pipeline_last_error"] = error_message or ""
    run.analysis_profile = profile


def advance_pipeline(
    *,
    run_id: str,
    branch_id: str,
    max_chapters: int,
    database_url: str | None = None,
    settings: Settings | None = None,
) -> tuple[int, int | None, str]:
    """Advance a branch serially up to N chapters, stopping on failure."""

    runtime = (settings or get_settings()).model_copy(deep=True)
    if database_url:
        runtime.database_url = database_url
    factory = create_session_factory(runtime)
    processed = 0
    with factory() as session:
        run_service = RunService(session, runtime)
        run, _branch = run_service.get_run_and_branch(run_id, branch_id)
        _set_pipeline_hint(run, state_hint=None)
        session.commit()
        while processed < max_chapters:
            next_index = run_service.next_chapter_index(run_id, branch_id)
            if next_index is None:
                break
            try:
                artifact_ids = AnalysisService(session, runtime).analyze_range(
                    run_id,
                    branch_id,
                    next_index,
                    next_index,
                )
            except Exception as exc:
                failed_jobs = run_service.list_failed_jobs(branch_id, 1)
                if not failed_jobs:
                    _set_pipeline_hint(
                        run,
                        state_hint="failed_terminal",
                        error_message=str(exc),
                    )
                    session.commit()
                    break

                failed_job = failed_jobs[0]
                if failed_job.attempts < runtime.chapter_failure_retry_limit:
                    run_service.reset_failed_job(branch_id, failed_job.chapter_index)
                    continue

                break
            processed += len(artifact_ids)
            if not artifact_ids:
                break
        next_chapter = run_service.next_chapter_index(run_id, branch_id)
        pipeline_state = _derive_pipeline_state(session, run_id, branch_id, next_chapter)
    return processed, next_chapter, pipeline_state


def start_pipeline(
    *,
    run_id: str,
    branch_id: str,
    pipeline_profile: str,
    max_chapters: int | None,
    database_url: str | None = None,
    settings: Settings | None = None,
) -> tuple[int, int | None, str]:
    """Explicitly start a previously ready run."""

    snapshot = get_run_snapshot(
        run_id=run_id,
        branch_id=branch_id,
        database_url=database_url,
        settings=settings,
    )
    if snapshot.pipeline_state != "ready":
        raise ValueError(f"run is not ready to start: {snapshot.pipeline_state}")
    runtime = (settings or get_settings()).model_copy(deep=True)
    if database_url:
        runtime.database_url = database_url
    factory = create_session_factory(runtime)
    with factory() as session:
        run = session.scalar(select(AnalysisRun).where(AnalysisRun.id == run_id))
        if run is None:
            raise ValueError(f"Unknown run_id: {run_id}")
        _set_pipeline_hint(run, pipeline_profile=pipeline_profile, state_hint=None)
        session.commit()
    effective_max_chapters = max_chapters
    if effective_max_chapters is None:
        effective_max_chapters = 999999 if pipeline_profile == "auto-full" else 1
    return advance_pipeline(
        run_id=run_id,
        branch_id=branch_id,
        max_chapters=effective_max_chapters,
        database_url=database_url,
        settings=runtime,
    )
