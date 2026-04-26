"""Stable application-layer read models."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from novel_analyzer.application.dto import (
    ApplicationChapterRow,
    BranchSnapshot,
    RunSnapshot,
)
from novel_analyzer.config.settings import Settings, get_settings
from novel_analyzer.database.models import AnalysisRun, NovelSource, RunBranch
from novel_analyzer.database.session import create_session_factory
from novel_analyzer.services.chapter_index_service import ChapterIndexService
from novel_analyzer.services.run_service import RunService
from novel_analyzer.services.status_service import StatusService


def _allowed_actions(state: str) -> list[str]:
    if state == "needs_recovery":
        return ["retry-failed", "retry-chapter", "clear-running", "repair"]
    if state == "ready":
        return ["start", "refresh", "export-basic"]
    if state == "completed":
        return ["export", "ask", "branch-view"]
    if state == "paused":
        return ["resume", "export", "read"]
    if state == "failed_terminal":
        return ["inspect", "retry-from-fixed-config"]
    return ["refresh"]


def _setup_status(session: Session, run_id: str) -> str:
    run = session.scalar(select(RunBranch).where(RunBranch.run_id == run_id).limit(1))
    if run is None:
        return "ok"
    novel = session.scalar(select(NovelSource).where(NovelSource.id == run.run.novel_id))
    if novel is None:
        return "ok"
    value = novel.metadata_json.get("setup_status")
    return str(value) if value else "ok"


def _pipeline_state_hint(session: Session, run_id: str) -> str | None:
    run = session.scalar(select(AnalysisRun).where(AnalysisRun.id == run_id))
    if run is None:
        return None
    hint = run.analysis_profile.get("pipeline_state_hint")
    return str(hint) if hint else None


def _derive_pipeline_state(
    session: Session,
    run_id: str,
    branch_id: str,
    next_chapter: int | None = None,
) -> str:
    setup_status = _setup_status(session, run_id)
    if setup_status == "setup_incomplete":
        return "failed_terminal"
    hint = _pipeline_state_hint(session, run_id)
    if hint:
        return hint

    status = StatusService(session).get_run_status(run_id, branch_id)
    branch = session.scalar(select(RunBranch).where(RunBranch.id == branch_id))
    if status.failed_jobs > 0:
        return "needs_recovery"
    if status.running_jobs > 0:
        return "auto_running"
    if branch is not None and branch.status == "paused":
        return "paused"
    if next_chapter is None:
        next_chapter = status.next_chapter
    if next_chapter is None and status.completed_chapters >= status.manifest_chapter_count:
        return "completed"
    return "ready"


def get_run_snapshot(
    *,
    run_id: str,
    branch_id: str,
    database_url: str | None = None,
    settings: Settings | None = None,
) -> RunSnapshot:
    """Return a stable run-level snapshot."""

    runtime = (settings or get_settings()).model_copy(deep=True)
    if database_url:
        runtime.database_url = database_url
    factory = create_session_factory(runtime)
    with factory() as session:
        status = StatusService(session).get_run_status(run_id, branch_id)
        pipeline_state = _derive_pipeline_state(session, run_id, branch_id, status.next_chapter)
        return RunSnapshot(
            run_id=status.run_id,
            branch_id=status.branch_id,
            branch_name=status.branch_name,
            pipeline_state=pipeline_state,
            manifest_chapter_count=status.manifest_chapter_count,
            completed_chapters=status.completed_chapters,
            failed_jobs=status.failed_jobs,
            running_jobs=status.running_jobs,
            next_chapter=status.next_chapter,
            allowed_actions=_allowed_actions(pipeline_state),
            setup_status=_setup_status(session, run_id),
        )


def get_branch_snapshot(
    *,
    run_id: str,
    branch_id: str,
    database_url: str | None = None,
    settings: Settings | None = None,
) -> BranchSnapshot:
    """Return a stable branch-level snapshot."""

    runtime = (settings or get_settings()).model_copy(deep=True)
    if database_url:
        runtime.database_url = database_url
    factory = create_session_factory(runtime)
    with factory() as session:
        run_service = RunService(session, runtime)
        status = StatusService(session).get_run_status(run_id, branch_id)
        rows = [
            ApplicationChapterRow(
                chapter_index=row.chapter_index,
                title=row.title,
                job_status=row.job_status,
                has_artifact=row.has_artifact,
                has_retrieval=row.has_retrieval,
                hook_score=row.hook_score,
                needs_human_review=row.needs_human_review,
                summary=row.summary,
            )
            for row in ChapterIndexService(session).list_rows(branch_id)
        ]
        pipeline_state = _derive_pipeline_state(session, run_id, branch_id, status.next_chapter)
        failed = run_service.list_failed_jobs(branch_id)
        return BranchSnapshot(
            branch_id=branch_id,
            pipeline_state=pipeline_state,
            allowed_actions=_allowed_actions(pipeline_state),
            chapter_rows=rows,
            failed_summary=[
                {"chapter_index": item.chapter_index, "error": item.last_error}
                for item in failed
            ],
        )
