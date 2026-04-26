"""Application-layer DTOs."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ApplicationChapterRow:
    """Application-owned branch row DTO."""

    chapter_index: int
    title: str
    job_status: str
    has_artifact: bool
    has_retrieval: bool
    hook_score: float | None
    needs_human_review: bool
    summary: str


@dataclass(frozen=True, slots=True)
class AutoRunResult:
    """Result for a high-level ingest/start/advance orchestration."""

    novel_id: str
    manifest_id: str
    run_id: str | None
    branch_id: str | None
    chapter_count: int
    processed_chapters: int
    next_chapter: int | None
    pipeline_profile: str
    pipeline_state: str
    existing: bool = False
    setup_status: str = "ok"


@dataclass(frozen=True, slots=True)
class RunSnapshot:
    """Stable run-level snapshot for CLI/Web callers."""

    run_id: str
    branch_id: str
    branch_name: str
    pipeline_state: str
    manifest_chapter_count: int
    completed_chapters: int
    failed_jobs: int
    running_jobs: int
    next_chapter: int | None
    allowed_actions: list[str]
    warnings: list[str] = field(default_factory=list)
    setup_status: str = "ok"


@dataclass(frozen=True, slots=True)
class BranchSnapshot:
    """Stable branch-level snapshot for CLI/Web callers."""

    branch_id: str
    pipeline_state: str
    allowed_actions: list[str]
    chapter_rows: list[ApplicationChapterRow]
    failed_summary: list[dict[str, str | int]]


@dataclass(frozen=True, slots=True)
class RecoveryResult:
    """Result from a recovery action."""

    branch_id: str
    accepted_action: str
    pipeline_state: str
    message: str


@dataclass(frozen=True, slots=True)
class ExportRefs:
    """Filesystem-backed export references for downstream surfaces."""

    branch_bundle_path: str
    branch_qa_context_path: str
    branch_report_path: str
