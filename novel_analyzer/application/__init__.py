"""Shared application-layer orchestration façades."""

from novel_analyzer.application.bootstrap import ingest_and_start_pipeline
from novel_analyzer.application.dto import (
    ApplicationChapterRow,
    AutoRunResult,
    BranchSnapshot,
    ExportRefs,
    RecoveryResult,
    RunSnapshot,
)
from novel_analyzer.application.exports import export_branch_refs
from novel_analyzer.application.pipeline import advance_pipeline, start_pipeline
from novel_analyzer.application.queries import get_branch_snapshot, get_run_snapshot
from novel_analyzer.application.recovery import recover_branch

__all__ = [
    "ApplicationChapterRow",
    "AutoRunResult",
    "BranchSnapshot",
    "ExportRefs",
    "RecoveryResult",
    "RunSnapshot",
    "advance_pipeline",
    "export_branch_refs",
    "get_branch_snapshot",
    "get_run_snapshot",
    "ingest_and_start_pipeline",
    "recover_branch",
    "start_pipeline",
]
