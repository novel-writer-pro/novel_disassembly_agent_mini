"""Minimal async background pipeline runner for the WSGI prototype."""

from __future__ import annotations

import concurrent.futures
import threading
import time
from dataclasses import asdict, dataclass

from novel_analyzer.config.settings import Settings, get_settings
from novel_analyzer.database.session import create_session_factory
from novel_analyzer.services.job_event_service import JobEventService
from novel_analyzer.services.pipeline_run_service import PipelineRunInfo, PipelineRunService
from novel_analyzer.services.run_service import RunService
from novel_analyzer.services.analysis_service import AnalysisService

_REGISTRY_LOCK = threading.Lock()
_PIPELINE_THREADS: dict[str, threading.Thread] = {}


@dataclass(frozen=True, slots=True)
class PipelineRunSnapshot:
    id: str
    run_id: str
    branch_id: str
    status: str
    target_from_chapter: int | None
    target_to_chapter: int | None
    concurrency: int
    provider_profile: str | None
    summary_json: dict[str, object]
    started_at: object | None
    finished_at: object | None
    paused_at: object | None
    cancelled_at: object | None


def _runtime(settings: Settings | None = None, database_url: str | None = None) -> Settings:
    current = (settings or get_settings()).model_copy(deep=True)
    if database_url:
        current.database_url = database_url
    return current


def _snapshot(info: PipelineRunInfo) -> PipelineRunSnapshot:
    def iso(value: object | None) -> str | None:
        return value.isoformat() if hasattr(value, "isoformat") else (str(value) if value is not None else None)

    return PipelineRunSnapshot(
        id=info.id,
        run_id=info.run_id,
        branch_id=info.branch_id,
        status=info.status,
        target_from_chapter=info.target_from_chapter,
        target_to_chapter=info.target_to_chapter,
        concurrency=info.concurrency,
        provider_profile=info.provider_profile,
        summary_json=info.summary_json,
        started_at=iso(info.started_at),
        finished_at=iso(info.finished_at),
        paused_at=iso(info.paused_at),
        cancelled_at=iso(info.cancelled_at),
    )


def _runner_loop(pipeline_run_id: str, runtime: Settings) -> None:
    factory = create_session_factory(runtime)
    while True:
        with factory() as session:
            runs = PipelineRunService(session)
            run = runs.get(pipeline_run_id)
            RunService(session, runtime).fail_stalled_jobs(run.branch_id)
            if run.status == "cancelled":
                break
            if run.status == "paused":
                time.sleep(1.0)
                continue
            if run.status == "pending":
                runs.mark_started(pipeline_run_id)
                JobEventService(session).record(
                    run_id=run.run_id,
                    branch_id=run.branch_id,
                    chapter_index=run.target_from_chapter or 0,
                    event_type="pipeline_started",
                    message=f"pipeline {pipeline_run_id} started",
                )
                run = runs.get(pipeline_run_id)

            run_service = RunService(session, runtime)
            next_chapter = run_service.next_chapter_index(run.run_id, run.branch_id)
            if next_chapter is None:
                runs.mark_completed(pipeline_run_id)
                break
            if run.target_to_chapter is not None and next_chapter > run.target_to_chapter:
                runs.mark_completed(pipeline_run_id)
                break

            batch_size = max(1, min(run.concurrency, 3))
            end_chapter = next_chapter + batch_size - 1
            if run.target_to_chapter is not None:
                end_chapter = min(end_chapter, run.target_to_chapter)

            runs.patch_summary(
                pipeline_run_id,
                {
                    "current_chapter": next_chapter,
                    "batch_end_chapter": end_chapter,
                    "last_tick_at": time.time(),
                },
            )

        try:
            with factory() as session:
                run = PipelineRunService(session).get(pipeline_run_id)
                AnalysisService(session, runtime).analyze_range(
                    run.run_id,
                    run.branch_id,
                    next_chapter,
                    end_chapter,
                )
                PipelineRunService(session).patch_summary(
                    pipeline_run_id,
                    {"last_completed_chapter": end_chapter},
                )
        except Exception as exc:  # noqa: BLE001
            with factory() as session:
                run = PipelineRunService(session).get(pipeline_run_id)
                failed = RunService(session, runtime).list_failed_jobs(run.branch_id, 1)
                if failed and failed[0].attempts < runtime.chapter_failure_retry_limit:
                    PipelineRunService(session).patch_summary(
                        pipeline_run_id,
                        {"last_error": str(exc), "retrying_chapter": next_chapter},
                    )
                else:
                    PipelineRunService(session).mark_failed(pipeline_run_id, str(exc))
                    JobEventService(session).record(
                        run_id=run.run_id,
                        branch_id=run.branch_id,
                        chapter_index=next_chapter or 0,
                        event_type="pipeline_failed",
                        level="error",
                        message=str(exc),
                    )
                    break
        time.sleep(0.2)

    with _REGISTRY_LOCK:
        _PIPELINE_THREADS.pop(pipeline_run_id, None)


def start_pipeline_run_async(
    *,
    run_id: str,
    branch_id: str,
    target_from_chapter: int | None = None,
    target_to_chapter: int | None = None,
    concurrency: int = 1,
    provider_profile: str | None = None,
    created_by: str | None = "api",
    database_url: str | None = None,
    settings: Settings | None = None,
) -> PipelineRunSnapshot:
    runtime = _runtime(settings, database_url)
    factory = create_session_factory(runtime)
    with factory() as session:
        run_service = RunService(session, runtime)
        next_chapter = run_service.next_chapter_index(run_id, branch_id)
        effective_from = target_from_chapter or next_chapter
        if effective_from is None:
            item = PipelineRunService(session).create(
                run_id=run_id,
                branch_id=branch_id,
                target_from_chapter=target_from_chapter,
                target_to_chapter=target_to_chapter,
                concurrency=concurrency,
                provider_profile=provider_profile,
                created_by=created_by,
            )
            completed = PipelineRunService(session).mark_completed(item.id)
            return _snapshot(PipelineRunService(session)._to_info(completed))
        if next_chapter is not None and effective_from != next_chapter:
            raise ValueError(f"async start-range currently only supports current next_chapter={next_chapter}")
        item = PipelineRunService(session).create(
            run_id=run_id,
            branch_id=branch_id,
            target_from_chapter=effective_from,
            target_to_chapter=target_to_chapter,
            concurrency=concurrency,
            provider_profile=provider_profile,
            created_by=created_by,
        )
        info = PipelineRunService(session)._to_info(item)

    thread = threading.Thread(target=_runner_loop, args=(info.id, runtime), daemon=True, name=f"pipeline-{info.id[:8]}")
    with _REGISTRY_LOCK:
        _PIPELINE_THREADS[info.id] = thread
    thread.start()
    return _snapshot(info)


def get_pipeline_run_status(
    *,
    pipeline_run_id: str,
    database_url: str | None = None,
    settings: Settings | None = None,
) -> PipelineRunSnapshot:
    runtime = _runtime(settings, database_url)
    factory = create_session_factory(runtime)
    with factory() as session:
        info = PipelineRunService(session).list_for_branch(PipelineRunService(session).get(pipeline_run_id).branch_id, limit=100)
        row = next(item for item in info if item.id == pipeline_run_id)
    return _snapshot(row)


def list_pipeline_runs(
    *,
    branch_id: str,
    limit: int = 20,
    database_url: str | None = None,
    settings: Settings | None = None,
) -> list[PipelineRunSnapshot]:
    runtime = _runtime(settings, database_url)
    factory = create_session_factory(runtime)
    with factory() as session:
        rows = PipelineRunService(session).list_for_branch(branch_id, limit)
    return [_snapshot(row) for row in rows]


def pause_pipeline_run(*, pipeline_run_id: str, database_url: str | None = None, settings: Settings | None = None) -> PipelineRunSnapshot:
    runtime = _runtime(settings, database_url)
    factory = create_session_factory(runtime)
    with factory() as session:
        row = PipelineRunService(session).mark_paused(pipeline_run_id)
        info = PipelineRunService(session)._to_info(row)
    return _snapshot(info)


def resume_pipeline_run(*, pipeline_run_id: str, database_url: str | None = None, settings: Settings | None = None) -> PipelineRunSnapshot:
    runtime = _runtime(settings, database_url)
    factory = create_session_factory(runtime)
    with factory() as session:
        row = PipelineRunService(session).mark_started(pipeline_run_id)
        info = PipelineRunService(session)._to_info(row)
    with _REGISTRY_LOCK:
        thread = _PIPELINE_THREADS.get(pipeline_run_id)
        alive = thread.is_alive() if thread else False
        if not alive:
            thread = threading.Thread(target=_runner_loop, args=(pipeline_run_id, runtime), daemon=True, name=f"pipeline-{pipeline_run_id[:8]}")
            _PIPELINE_THREADS[pipeline_run_id] = thread
            thread.start()
    return _snapshot(info)


def cancel_pipeline_run(*, pipeline_run_id: str, database_url: str | None = None, settings: Settings | None = None) -> PipelineRunSnapshot:
    runtime = _runtime(settings, database_url)
    factory = create_session_factory(runtime)
    with factory() as session:
        row = PipelineRunService(session).mark_cancelled(pipeline_run_id)
        info = PipelineRunService(session)._to_info(row)
    return _snapshot(info)
