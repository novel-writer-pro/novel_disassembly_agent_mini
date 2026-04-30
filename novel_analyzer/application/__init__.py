"""Shared application-layer orchestration façades."""

from novel_analyzer.application.bootstrap import ingest_and_start_pipeline
from novel_analyzer.application.dto import (
    ApplicationChapterJobRow,
    ApplicationChapterRow,
    AutoRunResult,
    BranchSnapshot,
    ExportRefs,
    PipelineRunSnapshot,
    RecoveryResult,
    RunSnapshot,
)
from novel_analyzer.application.exports import export_branch_refs
from novel_analyzer.application.pipeline_async import (
    cancel_pipeline_run,
    get_pipeline_run_status,
    list_pipeline_runs,
    pause_pipeline_run,
    resume_pipeline_run,
    start_pipeline_run_async,
)
from novel_analyzer.application.pipeline import advance_pipeline, start_pipeline
from novel_analyzer.application.queries import get_branch_snapshot, get_run_snapshot
from novel_analyzer.application.queries import get_branch_job_rows
from novel_analyzer.application.recovery import recover_branch

__all__ = [
    "ApplicationChapterRow",
    "ApplicationChapterJobRow",
    "AutoRunResult",
    "BranchSnapshot",
    "ExportRefs",
    "PipelineRunSnapshot",
    "RecoveryResult",
    "RunSnapshot",
    "cancel_pipeline_run",
    "advance_pipeline",
    "export_branch_refs",
    "get_branch_snapshot",
    "get_branch_job_rows",
    "get_pipeline_run_status",
    "get_run_snapshot",
    "ingest_and_start_pipeline",
    "list_pipeline_runs",
    "pause_pipeline_run",
    "recover_branch",
    "resume_pipeline_run",
    "start_pipeline_run_async",
    "start_pipeline",
]
