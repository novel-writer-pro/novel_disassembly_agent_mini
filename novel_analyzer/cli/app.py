"""Typer CLI entrypoint."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session
from typer import echo

from novel_analyzer.config.settings import Settings, get_settings
from novel_analyzer.database.migrations import upgrade_database
from novel_analyzer.database.models import (
    AnalysisRun,
    ChapterArtifact,
    FactRecord,
    NovelSource,
    RunBranch,
    ChapterManifest,
    WindowArtifact,
)
from novel_analyzer.database.postgres_checks import postgres_capability_report
from novel_analyzer.database.session import (
    create_session_factory,
    database_healthcheck,
    ensure_database_exists,
)
from novel_analyzer.runtime.storage import describe_runtime_storage, migrate_legacy_runtime_dirs
from novel_analyzer.runtime.provider_health import read_provider_health
from novel_analyzer.runtime.cluster_review_state import (
    read_cluster_review_history,
    read_cluster_review_state,
    write_cluster_review_state,
)
from novel_analyzer.services.steering_library_service import (
    SteeringLibraryService,
    SteeringPack,
    SteeringRetrievalMeta,
)

app = typer.Typer(add_completion=False, no_args_is_help=True)


def _settings(database_url: str | None = None) -> Settings:
    current = get_settings().model_copy(deep=True)
    if database_url:
        current.database_url = database_url
    return current


def _safe_settings(database_url: str | None = None, *, require_admin: bool = False) -> Settings:
    try:
        current = _settings(database_url)
        _ = current.admin_database_url if require_admin else current.resolved_database_url
        return current
    except ValueError as exc:
        echo(str(exc))
        raise typer.Exit(code=1) from exc


def _list_skill_names(settings: Settings) -> list[str]:
    from novel_analyzer.skills.loader import list_skill_names

    return list_skill_names(settings)


def _get_embedding_provider(settings: Settings) -> Any:
    from novel_analyzer.embedding.service import get_embedding_provider

    return get_embedding_provider(settings)


def _inspect_text(text: str) -> Any:
    from novel_analyzer.preprocessing.chapter_splitter import inspect_text

    return inspect_text(text)


def _render_branch_report(bundle: dict[str, object]) -> str:
    from novel_analyzer.reporting.branch_report import render_branch_report

    return render_branch_report(bundle)


def _mapping_pairs(items: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in items:
        left, _, right = item.partition("=")
        if left and right:
            result[left] = right
    return result


def _parse_chapter_goal_spec(chapter_spec: list[str]) -> list[tuple[int, str]]:
    chapter_goals: list[tuple[int, str]] = []
    for item in chapter_spec:
        chapter_text, _, goal = item.partition(":")
        if not chapter_text or not goal:
            raise typer.Exit(code=1)
        chapter_goals.append((int(chapter_text), goal))
    return chapter_goals


def _steering_pack(
    worldview_note: list[str],
    trope_axis: list[str],
    innovation_directive: list[str],
    taboo_innovation: list[str],
    knowledge_ref: list[str],
    trope_doc: list[str] | None = None,
    worldview_doc: list[str] | None = None,
    audience_doc: list[str] | None = None,
) -> tuple[SteeringPack, SteeringRetrievalMeta]:
    retrieval_query = " ".join(
        worldview_note
        + trope_axis
        + innovation_directive
        + taboo_innovation
        + knowledge_ref
        + (trope_doc or [])
        + (worldview_doc or [])
        + (audience_doc or [])
    )
    retrieval = SteeringLibraryService().retrieve_pack(
        query_text=retrieval_query,
        trope_docs=trope_doc or [],
        worldview_docs=worldview_doc or [],
        audience_docs=audience_doc or [],
    )
    pack = retrieval["steering_pack"]
    pack["worldview_capsule"].extend(item for item in worldview_note if item.strip())
    pack["trope_axes"].extend(item for item in trope_axis if item.strip())
    pack["innovation_directives"].extend(item for item in innovation_directive if item.strip())
    pack["taboo_innovations"].extend(item for item in taboo_innovation if item.strip())
    pack["external_knowledge_refs"].extend(item for item in knowledge_ref if item.strip())
    return pack, retrieval["retrieval_meta"]


def _build_story_mapping_pack(
    project_title: str,
    source_work_name: str,
    target_work_name: str,
    *,
    world_map: list[str],
    character_map: list[str],
    faction_map: list[str],
    power_map: list[str],
    rule_override: list[str],
    forbidden_transformation: list[str],
) -> Any:
    from novel_analyzer.domain.schemas import StoryMappingPack

    return StoryMappingPack(
        project_title=project_title,
        source_work_name=source_work_name,
        target_work_name=target_work_name,
        world_mapping=_mapping_pairs(world_map),
        character_mapping=_mapping_pairs(character_map),
        faction_mapping=_mapping_pairs(faction_map),
        power_mapping=_mapping_pairs(power_map),
        rule_overrides=rule_override,
        forbidden_transformations=forbidden_transformation,
    )


def _whole_book_readiness_payload(
    session: Session,
    settings: Settings,
    *,
    branch_id: str | None = None,
) -> dict[str, object]:
    target_branch_id = branch_id
    if not target_branch_id:
        target_branch_id = session.scalar(
            select(ChapterArtifact.branch_id)
            .where(ChapterArtifact.artifact_type == "chapter_analysis")
            .group_by(ChapterArtifact.branch_id)
            .order_by(func.count(ChapterArtifact.id).desc())
            .limit(1)
        )

    branch_summary: dict[str, object] = {
        "branch_id": target_branch_id or "",
        "exists": False,
        "chapter_analysis_count": 0,
        "fact_record_count": 0,
        "chapter_span": {"min": None, "max": None},
        "run_id": "",
        "branch_name": "",
        "status": "",
        "novel_title": "",
    }
    if target_branch_id:
        branch = session.get(RunBranch, target_branch_id)
        if branch is not None:
            analysis_count = session.scalar(
                select(func.count())
                .select_from(ChapterArtifact)
                .where(
                    ChapterArtifact.branch_id == target_branch_id,
                    ChapterArtifact.artifact_type == "chapter_analysis",
                )
            ) or 0
            fact_count = session.scalar(
                select(func.count())
                .select_from(FactRecord)
                .where(FactRecord.branch_id == target_branch_id)
            ) or 0
            chapter_min, chapter_max = session.execute(
                select(
                    func.min(ChapterArtifact.chapter_index),
                    func.max(ChapterArtifact.chapter_index),
                ).where(
                    ChapterArtifact.branch_id == target_branch_id,
                    ChapterArtifact.artifact_type == "chapter_analysis",
                )
            ).one()
            novel_title = session.scalar(
                select(NovelSource.title)
                .join(AnalysisRun, AnalysisRun.novel_id == NovelSource.id)
                .where(AnalysisRun.id == branch.run_id)
            ) or ""
            branch_summary = {
                "branch_id": target_branch_id,
                "exists": True,
                "chapter_analysis_count": int(analysis_count),
                "fact_record_count": int(fact_count),
                "chapter_span": {"min": chapter_min, "max": chapter_max},
                "run_id": branch.run_id,
                "branch_name": branch.name,
                "status": branch.status,
                "novel_title": novel_title,
            }

    provider_health = read_provider_health(settings)
    return {
        "contract_version": "whole-book-imitation-readiness.v1",
        "stable_contract_version": "whole-book-imitation-readiness-pre-v1",
        "whole_book_contract_version": "whole-book-imitation.v1",
        "whole_book_stable_contract_version": "whole-book-imitation-pre-v1",
        "database": {
            "masked_database_url": settings.masked_database_url,
            "effective_db_name": settings.effective_db_name,
        },
        "provider": {
            "provider_name": settings.llm_provider_name,
            "base_url": settings.resolved_llm_base_url,
            "api_key_present": bool(settings.resolved_llm_api_key),
            "model_name": settings.llm_model_name,
            "stage_model_name": settings.llm_stage_model_name,
            "qa_model_name": settings.llm_qa_model_name,
            "provider_health": {
                "provider_name": provider_health.provider_name,
                "model_name": provider_health.model_name,
                "last_status": provider_health.last_status,
                "degraded_events": provider_health.degraded_events,
                "success_events": provider_health.success_events,
                "last_error": provider_health.last_error,
                "last_updated_at": provider_health.last_updated_at,
            },
        },
        "branch_candidate": branch_summary,
        "readiness_notes": [
            "如果 api_key_present=false，则不能做真实 provider-backed whole-book execute。",
            "如果 provider_health.last_status=degraded，应先确认上游 provider 是否恢复。",
            "如果 branch_candidate.chapter_analysis_count < 2，则不适合做 whole-book imitation freeze evidence。",
        ],
    }


def _ingest_and_start_pipeline(**kwargs: Any) -> Any:
    from novel_analyzer.application import ingest_and_start_pipeline

    return ingest_and_start_pipeline(**kwargs)


def _ingest_service(session: Session, settings: Settings) -> Any:
    from novel_analyzer.services.ingest_service import IngestService

    return IngestService(session, settings)


def _run_service(session: Session, settings: Settings) -> Any:
    from novel_analyzer.services.run_service import RunService

    return RunService(session, settings)


def _analysis_service(session: Session, settings: Settings) -> Any:
    from novel_analyzer.services.analysis_service import AnalysisService

    return AnalysisService(session, settings)


def _chapter_index_service(session: Session) -> Any:
    from novel_analyzer.services.chapter_index_service import ChapterIndexService

    return ChapterIndexService(session)


def _status_service(session: Session) -> Any:
    from novel_analyzer.services.status_service import StatusService

    return StatusService(session)


def _retrieval_service(session: Session, settings: Settings) -> Any:
    from novel_analyzer.services.retrieval_service import RetrievalService

    return RetrievalService(session, settings)


def _qa_service(session: Session, settings: Settings) -> Any:
    from novel_analyzer.services.qa_service import BranchQAService

    return BranchQAService(session, settings)


def _raw_output_service(session: Session) -> Any:
    from novel_analyzer.services.raw_output_service import RawOutputService

    return RawOutputService(session)


def _context_service(session: Session) -> Any:
    from novel_analyzer.services.context_service import ContextService

    return ContextService(session)


def _export_service(session: Session) -> Any:
    from novel_analyzer.services.export_service import ExportService

    return ExportService(session)


def _repair_service(session: Session) -> Any:
    from novel_analyzer.services.repair_service import RepairService

    return RepairService(session)


def _consistency_service(session: Session) -> Any:
    from novel_analyzer.services.consistency_service import ConsistencyService

    return ConsistencyService(session)


def _fact_service(session: Session) -> Any:
    from novel_analyzer.services.fact_service import FactService

    return FactService(session)


def _package_service(session: Session) -> Any:
    from novel_analyzer.services.package_service import PackageService

    return PackageService(session)


def _graph_service(session: Session) -> Any:
    from novel_analyzer.services.graph_service import GraphService

    return GraphService(session)


def _next_chapter_planner_service(session: Session) -> Any:
    from novel_analyzer.services.next_chapter_planner_service import NextChapterPlannerService

    return NextChapterPlannerService(session)


def _chapter_imitation_service(session: Session) -> Any:
    from novel_analyzer.services.chapter_imitation_service import ChapterImitationService

    return ChapterImitationService(session)


def _whole_book_imitation_service(session: Session) -> Any:
    from novel_analyzer.services.whole_book_imitation_service import WholeBookImitationService

    return WholeBookImitationService(session)


def _imitation_harness_service(session: Session, settings: Settings) -> Any:
    from novel_analyzer.services.imitation_harness_service import HarnessControllerService

    return HarnessControllerService(session, settings)


def _author_knowledge_service(session: Session) -> Any:
    from novel_analyzer.services.author_knowledge_service import AuthorKnowledgeService

    return AuthorKnowledgeService(session)


def _novel_assistant_service(session: Session, settings: Settings) -> Any:
    from novel_analyzer.services.novel_assistant_service import NovelAssistantService

    return NovelAssistantService(session, settings)


def _reader_feedback_service(session: Session) -> Any:
    from novel_analyzer.services.reader_feedback_service import ReaderFeedbackService

    return ReaderFeedbackService(session)


@app.command()
def init_db(
    database_url: str | None = None,
    ensure_db: bool = typer.Option(True, help="Create PostgreSQL database first when needed."),
) -> None:
    """Create or upgrade the database schema via Alembic."""

    settings = _safe_settings(database_url, require_admin=True)
    if ensure_db:
        ensure_database_exists(settings)
    upgrade_database(settings)
    echo(f"initialized database: {settings.masked_database_url}")


@app.command()
def db_health(database_url: str | None = None) -> None:
    """Run a simple database connectivity check."""

    settings = _safe_settings(database_url)
    report = database_healthcheck(settings)
    for key, value in report.items():
        echo(f"{key}={value}")


@app.command()
def db_capabilities(database_url: str | None = None) -> None:
    """Check PostgreSQL database existence, schema initialization, and extensions."""

    settings = _safe_settings(database_url, require_admin=True)
    report = postgres_capability_report(settings)
    echo(f"database_exists={str(report.database_exists).lower()}")
    echo(f"can_connect={str(report.can_connect).lower()}")
    echo(f"initialized_schema={str(report.initialized_schema).lower()}")
    echo(f"server_version={report.server_version}")
    echo(f"installed_extensions={','.join(report.installed_extensions)}")
    echo(f"available_text_search_configs={','.join(report.available_text_search_configs)}")
    echo(f"missing_tables={','.join(report.missing_tables)}")
    echo(f"missing_extensions={','.join(report.missing_extensions)}")
    if report.missing_cluster_review_columns:
        items = [
            f"{table}:{','.join(columns)}"
            for table, columns in sorted(report.missing_cluster_review_columns.items())
        ]
        echo(f"missing_cluster_review_columns={';'.join(items)}")
    else:
        echo("missing_cluster_review_columns=")
    echo(f"ok={str(report.ok).lower()}")
    if not report.ok:
        raise typer.Exit(code=1)


@app.command()
def runtime_storage(migrate: bool = typer.Option(False, "--migrate")) -> None:
    """Inspect managed runtime storage roots and optionally migrate legacy .omx files."""

    report = migrate_legacy_runtime_dirs(get_settings()) if migrate else describe_runtime_storage(get_settings())
    echo(f"cache_root={report.cache_root}")
    echo(f"legacy_root={report.legacy_root}")
    echo(f"cache_upload_files={report.cache_upload_files}")
    echo(f"cache_export_files={report.cache_export_files}")
    echo(f"legacy_upload_files={report.legacy_upload_files}")
    echo(f"legacy_export_files={report.legacy_export_files}")
    echo(f"missing_from_cache={report.missing_from_cache}")
    echo(f"migrated_this_run={report.migrated_this_run}")


@app.command()
def list_skills(database_url: str | None = None) -> None:
    """List project-local skills discovered from skills_dir/."""

    settings = _safe_settings(database_url)
    for name in _list_skill_names(settings):
        echo(name)



@app.command()
def test_embedding(
    text_input: str = '卫图觉醒命格。',
    database_url: str | None = None,
) -> None:
    """Run a smoke test for the configured embedding backend."""

    settings = _safe_settings(database_url)
    provider = _get_embedding_provider(settings)
    vectors = provider.embed_texts([text_input])
    echo(f"provider={type(provider).__name__}")
    echo(f"vector_dim={len(vectors[0])}")
    echo(f"vector_preview={vectors[0][:8]}")


@app.command()
def inspect_novel(path: Path) -> None:
    """Inspect a novel file without persisting anything."""

    text = path.read_text(encoding="utf-8")
    preview = _inspect_text(text)
    echo(f"raw_heading_count={preview.raw_heading_count}")
    echo(f"normalized_chapter_count={preview.normalized_chapter_count}")
    echo(f"duplicate_heading_count={preview.duplicate_heading_count}")
    for heading in preview.first_headings:
        echo(f"- {heading}")


@app.command()
def ingest(
    path: Path,
    title: str | None = None,
    database_url: str | None = None,
) -> None:
    """Persist a novel and its chapter manifest."""

    settings = _safe_settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        novel, manifest = _ingest_service(session, settings).ingest_text_file(str(path), title)
        echo(f"novel_id={novel.id}")
        echo(f"manifest_id={manifest.id}")
        echo(f"chapter_count={manifest.chapter_count}")


@app.command()
def ingest_chapter_list(
    input_path: Path,
    title: str | None = None,
    source_name: str = typer.Option("chapter-list-import", "--source-name"),
    database_url: str | None = None,
) -> None:
    """Persist a novel from a JSON chapter list and derive a chapter manifest."""

    payload = json.loads(input_path.read_text(encoding="utf-8"))
    chapters = payload.get("chapters", []) if isinstance(payload, dict) else payload
    if not isinstance(chapters, list):
        echo("chapter list payload must be a JSON list or an object with `chapters`")
        raise typer.Exit(code=1)

    settings = _safe_settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        novel, manifest = _ingest_service(session, settings).ingest_chapter_list(
            [item for item in chapters if isinstance(item, dict)],
            title=title,
            source_name=source_name,
        )
        echo(f"novel_id={novel.id}")
        echo(f"manifest_id={manifest.id}")
        echo(f"chapter_count={manifest.chapter_count}")
        echo(f"source_path={novel.source_path}")


@app.command()
def start_run(
    novel_id: str,
    manifest_id: str,
    branch_name: str = "main",
    database_url: str | None = None,
) -> None:
    """Create a new analysis run with a root branch."""

    settings = _safe_settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        run, branch = _run_service(session, settings).create_run(
            novel_id,
            manifest_id,
            branch_name,
        )
        echo(f"run_id={run.id}")
        echo(f"branch_id={branch.id}")
        echo(f"active_branch_id={run.active_branch_id}")


@app.command()
def auto_run(
    path: Path,
    title: str | None = None,
    branch_name: str = "main",
    max_chapters: int | None = typer.Option(None, "--max-chapters"),
    pipeline_profile: str = typer.Option("auto-lite", "--pipeline-profile"),
    database_url: str | None = None,
) -> None:
    """Ingest, create a run, and optionally auto-advance in one command."""

    try:
        result = _ingest_and_start_pipeline(
            path=str(path),
            title=title,
            branch_name=branch_name,
            pipeline_profile=pipeline_profile,
            max_chapters=max_chapters,
            database_url=database_url,
        )
    except ValueError as exc:
        echo(str(exc))
        raise typer.Exit(code=1) from exc
    echo(f"novel_id={result.novel_id}")
    echo(f"manifest_id={result.manifest_id}")
    echo(f"chapter_count={result.chapter_count}")
    echo(f"run_id={result.run_id}")
    echo(f"branch_id={result.branch_id}")
    echo(f"processed_chapters={result.processed_chapters}")
    echo(f"next_chapter={result.next_chapter}")
    echo(f"pipeline_profile={result.pipeline_profile}")
    echo(f"pipeline_state={result.pipeline_state}")
    echo(f"setup_status={result.setup_status}")
    echo(f"existing={str(result.existing).lower()}")






@app.command()
def clear_running_jobs(
    branch_id: str,
    reason: str = typer.Option('manual cleanup of stale running jobs', '--reason'),
    database_url: str | None = None,
) -> None:
    """Mark stale running jobs as failed so the branch can continue."""

    settings = _safe_settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        count = _run_service(session, settings).clear_running_jobs(branch_id, reason)
        echo(f"cleared_running_jobs={count}")


@app.command()
def retry_failed_jobs(
    run_id: str,
    branch_id: str,
    max_chapters: int = typer.Option(5, '--max-chapters'),
    database_url: str | None = None,
) -> None:
    """Retry failed jobs serially for up to N chapters."""

    settings = _safe_settings(database_url)
    factory = create_session_factory(settings)
    retried = 0
    with factory() as session:
        run_service = _run_service(session, settings)
        failed = run_service.list_failed_jobs(branch_id, max_chapters)
        for job in failed:
            run_service.reset_failed_job(branch_id, job.chapter_index)
            artifact_ids = _analysis_service(session, settings).analyze_range(
                run_id,
                branch_id,
                job.chapter_index,
                job.chapter_index,
            )
            retried += len(artifact_ids)
        echo(f"retried_failed_jobs={retried}")


@app.command()
def list_failed_jobs(
    branch_id: str,
    limit: int = typer.Option(20, '--limit'),
    database_url: str | None = None,
) -> None:
    """List failed jobs for one branch."""

    settings = _safe_settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        jobs = _run_service(session, settings).list_failed_jobs(branch_id, limit)
        echo(f"failed_job_count={len(jobs)}")
        for job in jobs:
            echo(
                f"failed=chapter:{job.chapter_index}|attempts:{job.attempts}|error:{job.last_error}"
            )


@app.command()
def retry_chapter(
    run_id: str,
    branch_id: str,
    chapter_index: int,
    database_url: str | None = None,
) -> None:
    """Reset one failed chapter and retry it immediately."""

    settings = _safe_settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        run_service = _run_service(session, settings)
        run_service.reset_failed_job(branch_id, chapter_index)
        artifact_ids = _analysis_service(session, settings).analyze_range(
            run_id,
            branch_id,
            chapter_index,
            chapter_index,
        )
        echo(f"retried_chapter={chapter_index}")
        for artifact_id in artifact_ids:
            echo(f"artifact_id={artifact_id}")


@app.command()
def list_job_events(
    branch_id: str,
    limit: int = typer.Option(50, '--limit'),
    database_url: str | None = None,
) -> None:
    """List recent job events for one branch."""

    settings = _safe_settings(database_url)
    factory = create_session_factory(settings)
    from novel_analyzer.services.job_event_service import JobEventService

    with factory() as session:
        rows = JobEventService(session).list_for_branch(branch_id, limit)
        echo(f"job_event_count={len(rows)}")
        for item in rows:
            echo(
                f"event=chapter:{item.chapter_index}|type:{item.event_type}|stage:{item.stage or '-'}|"
                f"level:{item.level}|message:{item.message}"
            )



@app.command()
def list_chapters(
    branch_id: str,
    limit: int = typer.Option(200, '--limit'),
    database_url: str | None = None,
) -> None:
    """List per-chapter progress rows for one branch."""

    settings = _safe_settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        rows = _chapter_index_service(session).list_rows(branch_id, limit)
        echo(f"chapter_row_count={len(rows)}")
        for row in rows:
            echo(
                f"chapter={row.chapter_index}|title={row.title}|job={row.job_status}|"
                f"artifact={row.has_artifact}|retrieval={row.has_retrieval}|"
                f"hook={row.hook_score}|review={row.needs_human_review}"
            )


@app.command()
def show_run_status(
    run_id: str,
    branch_id: str,
    database_url: str | None = None,
) -> None:
    """Show an operational status snapshot for one run/branch."""

    settings = _safe_settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        status = _status_service(session).get_run_status(run_id, branch_id)
        for key in status.__dataclass_fields__:
            echo(f"{key}={getattr(status, key)}")



@app.command()
def resume_run(
    run_id: str,
    branch_id: str,
    max_chapters: int = typer.Option(1, '--max-chapters'),
    database_url: str | None = None,
) -> None:
    """Advance the run serially for up to N chapters, stopping on first failure."""

    settings = _safe_settings(database_url)
    factory = create_session_factory(settings)
    processed = 0
    with factory() as session:
        run_service = _run_service(session, settings)
        while processed < max_chapters:
            next_index = run_service.next_chapter_index(run_id, branch_id)
            if next_index is None:
                break
            artifact_ids = _analysis_service(session, settings).analyze_range(
                run_id,
                branch_id,
                next_index,
                next_index,
            )
            processed += len(artifact_ids)
            if not artifact_ids:
                break
        echo(f"processed_chapters={processed}")
        echo(f"next_chapter={run_service.next_chapter_index(run_id, branch_id)}")


@app.command()
def analyze_next(
    run_id: str,
    branch_id: str,
    database_url: str | None = None,
) -> None:
    """Analyze the next pending chapter for a branch."""

    settings = _safe_settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        run_service = _run_service(session, settings)
        next_index = run_service.next_chapter_index(run_id, branch_id)
        if next_index is None:
            echo('next_chapter=None')
            return
        artifact_ids = _analysis_service(session, settings).analyze_range(
            run_id,
            branch_id,
            next_index,
            next_index,
        )
        echo(f"next_chapter={next_index}")
        for artifact_id in artifact_ids:
            echo(f"artifact_id={artifact_id}")


@app.command()
def analyze_range(
    run_id: str,
    branch_id: str,
    start_chapter: int,
    end_chapter: int,
    database_url: str | None = None,
) -> None:
    """Analyze and persist a chapter range using the configured LLM."""

    settings = _safe_settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        artifact_ids = _analysis_service(session, settings).analyze_range(
            run_id,
            branch_id,
            start_chapter,
            end_chapter,
        )
        echo(f"artifact_count={len(artifact_ids)}")
        for artifact_id in artifact_ids:
            echo(f"artifact_id={artifact_id}")


@app.command()
def materialize_retrieval(artifact_id: str, database_url: str | None = None) -> None:
    """Materialize retrieval rows for an existing chapter artifact."""

    settings = _safe_settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        document = _retrieval_service(session, settings).materialize_for_artifact(artifact_id)
        echo(f"document_id={document.id}")
        echo(f"chapter_index={document.chapter_index}")


@app.command()
def search_branch(
    branch_id: str,
    query: str,
    limit: int = 5,
    database_url: str | None = None,
) -> None:
    """Run retrieval search over a branch's materialized documents."""

    settings = _safe_settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        hits = _retrieval_service(session, settings).search_branch(branch_id, query, limit)
        echo(f"hit_count={len(hits)}")
        for hit in hits:
            echo(
                f"chapter_index={hit.chapter_index} | score={hit.score:.4f} | "
                f"title={hit.title} | keywords={hit.keyword_list}"
            )


@app.command()
def search_branch_diagnostics(
    branch_id: str,
    query: str,
    limit: int = 5,
    database_url: str | None = None,
) -> None:
    """Show retrieval raw/rerank diagnostics for a branch query."""

    settings = _safe_settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        payload = _retrieval_service(session, settings).search_branch_with_diagnostics(
            branch_id, query, limit
        )
        echo(f"query={payload.query}")
        echo(f"raw_hit_count={len(payload.raw_hits)}")
        echo(f"reranked_hit_count={len(payload.reranked_hits)}")
        echo(f"fusion_applied={payload.fusion_applied}")
        echo(f"rerank_applied={payload.rerank_applied}")
        echo(f"raw_latency_ms={payload.raw_latency_ms:.2f}")
        echo(f"rerank_latency_ms={payload.rerank_latency_ms:.2f}")
        echo(f"route_counts={payload.route_counts or {}}")
        for route in payload.route_diagnostics or []:
            echo(
                f"route={route.route} | hit_count={route.hit_count} | latency_ms={route.latency_ms:.2f}"
            )
        for hit in payload.raw_hits[:limit]:
            echo(
                f"raw_hit=chapter_index={hit.chapter_index} | score={hit.score:.4f} | title={hit.title}"
            )
        for hit in payload.reranked_hits[:limit]:
            echo(
                f"reranked_hit=chapter_index={hit.chapter_index} | score={hit.score:.4f} | title={hit.title}"
            )


@app.command()
def export_search_branch_diagnostics(
    branch_id: str,
    query: str,
    output_path: Path,
    limit: int = 5,
    database_url: str | None = None,
) -> None:
    """Export retrieval raw/rerank diagnostics for a branch query to JSON."""

    settings = _safe_settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        payload = _retrieval_service(session, settings).search_branch_with_diagnostics(
            branch_id, query, limit
        )
        def _hit_json(hit: Any) -> dict[str, object]:
            return {
                "chapter_index": hit.chapter_index,
                "title": hit.title,
                "summary_text": hit.summary_text,
                "score": hit.score,
                "keyword_list": hit.keyword_list,
            }
        output = {
            "query": payload.query,
            "raw_hits": [_hit_json(hit) for hit in payload.raw_hits],
            "reranked_hits": [_hit_json(hit) for hit in payload.reranked_hits],
            "rerank_applied": payload.rerank_applied,
            "fusion_applied": payload.fusion_applied,
            "route_counts": payload.route_counts or {},
            "route_diagnostics": [
                {
                    "route": route.route,
                    "hit_count": route.hit_count,
                    "latency_ms": route.latency_ms,
                }
                for route in payload.route_diagnostics or []
            ],
            "raw_latency_ms": payload.raw_latency_ms,
            "rerank_latency_ms": payload.rerank_latency_ms,
        }
        output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
        echo(f"search_branch_diagnostics_path={output_path}")



@app.command()
def export_retrieval_benchmark(
    branch_id: str,
    output_path: Path,
    query: list[str] = typer.Option([], "--query"),
    limit: int = 5,
    database_url: str | None = None,
) -> None:
    """Export a multi-query retrieval benchmark bundle for one branch."""

    settings = _safe_settings(database_url)
    factory = create_session_factory(settings)
    queries = query or ["卫图 命格", "二姑 养生功", "资源 婚事"]
    with factory() as session:
        service = _retrieval_service(session, settings)
        results = []
        for item in queries:
            payload = service.search_branch_with_diagnostics(branch_id, item, limit)
            results.append({
                "query": payload.query,
                "fusion_applied": payload.fusion_applied,
                "rerank_applied": payload.rerank_applied,
                "route_counts": payload.route_counts or {},
                "raw_latency_ms": payload.raw_latency_ms,
                "rerank_latency_ms": payload.rerank_latency_ms,
                "top_raw_chapters": [hit.chapter_index for hit in payload.raw_hits[:limit]],
                "top_reranked_chapters": [hit.chapter_index for hit in payload.reranked_hits[:limit]],
            })
        output = {
            "contract_version": "retrieval-benchmark.v1",
            "branch_id": branch_id,
            "queries": results,
        }
        output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
        echo(f"retrieval_benchmark_path={output_path}")


@app.command()
def ask_branch(
    branch_id: str,
    question: str,
    limit: int = 5,
    database_url: str | None = None,
) -> None:
    """Answer a question about the novel using branch retrieval context."""

    settings = _safe_settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        result = _qa_service(session, settings).answer_question(branch_id, question, limit)
        echo(f"answer={result.answer}")
        echo(f"used_chapters={result.used_chapters}")
        echo(f"confidence={result.confidence}")
        echo(f"insufficient_context={result.insufficient_context}")
        for item in result.evidence:
            echo(f"evidence={item}")
        for item in result.reasoning_paths:
            echo(f"reasoning_path={item}")
        for item in result.graph_signals:
            echo(f"graph_signal={item}")









@app.command()
def show_novel_assistant(
    branch_id: str,
    query: str = "",
    question: str = "",
    from_chapter_index: int | None = None,
    upto_chapter_index: int | None = None,
    focus_label: str = "",
    limit: int = 5,
    database_url: str | None = None,
) -> None:
    """Show the unified novel assistant capability pack."""

    settings = _safe_settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        payload = _novel_assistant_service(session, settings).build_branch_assistant_pack(
            branch_id,
            query=query,
            question=question,
            from_chapter_index=from_chapter_index,
            upto_chapter_index=upto_chapter_index,
            focus_label=focus_label,
            limit=limit,
        )
        echo(json.dumps(payload, ensure_ascii=False, indent=2))


@app.command()
def export_novel_assistant(
    branch_id: str,
    output_path: Path,
    query: str = "",
    question: str = "",
    from_chapter_index: int | None = None,
    upto_chapter_index: int | None = None,
    focus_label: str = "",
    limit: int = 5,
    database_url: str | None = None,
) -> None:
    """Export the unified novel assistant capability pack to JSON."""

    settings = _safe_settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        payload = _novel_assistant_service(session, settings).build_branch_assistant_pack(
            branch_id,
            query=query,
            question=question,
            from_chapter_index=from_chapter_index,
            upto_chapter_index=upto_chapter_index,
            focus_label=focus_label,
            limit=limit,
        )
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
        echo(f"novel_assistant_path={output_path}")



@app.command()
def show_governance_dashboard(
    branch_id: str,
    query: str = "",
    question: str = "",
    from_chapter_index: int | None = None,
    upto_chapter_index: int | None = None,
    focus_label: str = "",
    limit: int = 5,
    database_url: str | None = None,
) -> None:
    """Show the governance dashboard slice from the unified novel assistant pack."""

    settings = _safe_settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        payload = _novel_assistant_service(session, settings).build_branch_assistant_pack(
            branch_id,
            query=query,
            question=question,
            from_chapter_index=from_chapter_index,
            upto_chapter_index=upto_chapter_index,
            focus_label=focus_label,
            limit=limit,
        )
        echo(json.dumps(payload.get("governance_dashboard_pack", {}), ensure_ascii=False, indent=2))


@app.command()
def export_governance_dashboard(
    branch_id: str,
    output_path: Path,
    query: str = "",
    question: str = "",
    from_chapter_index: int | None = None,
    upto_chapter_index: int | None = None,
    focus_label: str = "",
    limit: int = 5,
    database_url: str | None = None,
) -> None:
    """Export the governance dashboard slice to JSON."""

    settings = _safe_settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        payload = _novel_assistant_service(session, settings).build_branch_assistant_pack(
            branch_id,
            query=query,
            question=question,
            from_chapter_index=from_chapter_index,
            upto_chapter_index=upto_chapter_index,
            focus_label=focus_label,
            limit=limit,
        )
        output_path.write_text(json.dumps(payload.get("governance_dashboard_pack", {}), ensure_ascii=False, indent=2), encoding='utf-8')
        echo(f"governance_dashboard_path={output_path}")


@app.command()
def export_governance_report_brief(
    branch_id: str,
    output_path: Path,
    query: str = "",
    question: str = "",
    from_chapter_index: int | None = None,
    upto_chapter_index: int | None = None,
    focus_label: str = "",
    limit: int = 5,
    database_url: str | None = None,
) -> None:
    """Export the governance report brief to Markdown."""

    settings = _safe_settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        payload = _novel_assistant_service(session, settings).build_branch_assistant_pack(
            branch_id,
            query=query,
            question=question,
            from_chapter_index=from_chapter_index,
            upto_chapter_index=upto_chapter_index,
            focus_label=focus_label,
            limit=limit,
        )
        brief = payload.get("governance_report_brief_pack", {})
        output_path.write_text(str(brief.get("brief_text", "")), encoding='utf-8')
        echo(f"governance_report_brief_path={output_path}")


@app.command()
def export_release_review_note(
    branch_id: str,
    output_path: Path,
    query: str = "",
    question: str = "",
    from_chapter_index: int | None = None,
    upto_chapter_index: int | None = None,
    focus_label: str = "",
    limit: int = 5,
    database_url: str | None = None,
) -> None:
    """Export the release review note to Markdown."""

    settings = _safe_settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        payload = _novel_assistant_service(session, settings).build_branch_assistant_pack(
            branch_id,
            query=query,
            question=question,
            from_chapter_index=from_chapter_index,
            upto_chapter_index=upto_chapter_index,
            focus_label=focus_label,
            limit=limit,
        )
        note = payload.get("release_review_note_pack", {})
        output_path.write_text(str(note.get("note_text", "")), encoding='utf-8')
        echo(f"release_review_note_path={output_path}")


@app.command()
def export_approval_decision_memo(
    branch_id: str,
    output_path: Path,
    query: str = "",
    question: str = "",
    from_chapter_index: int | None = None,
    upto_chapter_index: int | None = None,
    focus_label: str = "",
    limit: int = 5,
    database_url: str | None = None,
) -> None:
    """Export the approval decision memo to Markdown."""

    settings = _safe_settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        payload = _novel_assistant_service(session, settings).build_branch_assistant_pack(
            branch_id,
            query=query,
            question=question,
            from_chapter_index=from_chapter_index,
            upto_chapter_index=upto_chapter_index,
            focus_label=focus_label,
            limit=limit,
        )
        memo = payload.get("approval_decision_memo_pack", {})
        output_path.write_text(str(memo.get("memo_text", "")), encoding='utf-8')
        echo(f"approval_decision_memo_path={output_path}")


@app.command()
def export_external_report_bundle(
    branch_id: str,
    output_path: Path,
    query: str = "",
    question: str = "",
    from_chapter_index: int | None = None,
    upto_chapter_index: int | None = None,
    focus_label: str = "",
    limit: int = 5,
    database_url: str | None = None,
) -> None:
    """Export the external report bundle to JSON."""

    settings = _safe_settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        payload = _novel_assistant_service(session, settings).build_branch_assistant_pack(
            branch_id,
            query=query,
            question=question,
            from_chapter_index=from_chapter_index,
            upto_chapter_index=upto_chapter_index,
            focus_label=focus_label,
            limit=limit,
        )
        bundle = payload.get("external_report_bundle_pack", {})
        output_path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding='utf-8')
        echo(f"external_report_bundle_path={output_path}")


@app.command()
def export_external_report_markdown(
    branch_id: str,
    output_path: Path,
    query: str = "",
    question: str = "",
    from_chapter_index: int | None = None,
    upto_chapter_index: int | None = None,
    focus_label: str = "",
    limit: int = 5,
    database_url: str | None = None,
) -> None:
    """Export the external report bundle as Markdown."""

    settings = _safe_settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        payload = _novel_assistant_service(session, settings).build_branch_assistant_pack(
            branch_id,
            query=query,
            question=question,
            from_chapter_index=from_chapter_index,
            upto_chapter_index=upto_chapter_index,
            focus_label=focus_label,
            limit=limit,
        )
        report = payload.get("external_report_markdown_pack", {})
        output_path.write_text(str(report.get("markdown_text", "")), encoding='utf-8')
        echo(f"external_report_markdown_path={output_path}")


@app.command()
def export_final_release_archive(
    branch_id: str,
    output_path: Path,
    query: str = "",
    question: str = "",
    from_chapter_index: int | None = None,
    upto_chapter_index: int | None = None,
    focus_label: str = "",
    limit: int = 5,
    database_url: str | None = None,
) -> None:
    """Export the final release archive bundle to JSON."""

    settings = _safe_settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        payload = _novel_assistant_service(session, settings).build_branch_assistant_pack(
            branch_id,
            query=query,
            question=question,
            from_chapter_index=from_chapter_index,
            upto_chapter_index=upto_chapter_index,
            focus_label=focus_label,
            limit=limit,
        )
        archive = payload.get("final_release_archive_pack", {})
        output_path.write_text(json.dumps(archive, ensure_ascii=False, indent=2), encoding='utf-8')
        echo(f"final_release_archive_path={output_path}")

@app.command()
def show_raw_output(
    branch_id: str,
    chapter_index: int,
    database_url: str | None = None,
) -> None:
    """Show the latest raw LLM output record for one chapter."""

    settings = _safe_settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        record = _raw_output_service(session).latest_for_chapter(branch_id, chapter_index)
        if record is None:
            raise typer.Exit(code=1)
        echo(f"chapter_index={record.chapter_index}")
        echo(f"job_attempt={record.job_attempt}")
        echo(f"parse_status={record.parse_status}")
        echo(f"parse_error={record.parse_error}")
        echo(f"invocation_metadata={record.invocation_metadata}")
        echo(record.raw_response_text)


@app.command()
def export_raw_output(
    branch_id: str,
    chapter_index: int,
    output_path: Path,
    database_url: str | None = None,
) -> None:
    """Export the latest raw output JSON/text bundle for one chapter."""

    settings = _safe_settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        record = _raw_output_service(session).latest_for_chapter(branch_id, chapter_index)
        if record is None:
            raise typer.Exit(code=1)
        payload = {
            'chapter_index': record.chapter_index,
            'job_attempt': record.job_attempt,
            'parse_status': record.parse_status,
            'parse_error': record.parse_error,
            'invocation_metadata': record.invocation_metadata,
            'parsed_json': record.parsed_json,
            'raw_response_text': record.raw_response_text,
        }
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
        echo(f"raw_output_path={output_path}")


@app.command()
def show_context(
    branch_id: str,
    chapter_index: int,
    database_url: str | None = None,
) -> None:
    """Show the assembled prior context that will feed a chapter."""

    settings = _safe_settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        bundle = _context_service(session).context_bundle(branch_id, chapter_index)
        echo(json.dumps(bundle, ensure_ascii=False, indent=2))


@app.command()
def export_context(
    branch_id: str,
    chapter_index: int,
    output_path: Path,
    database_url: str | None = None,
) -> None:
    """Export the assembled prior context for a chapter to JSON."""

    settings = _safe_settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        bundle = _context_service(session).context_bundle(branch_id, chapter_index)
        output_path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding='utf-8')
        echo(f"context_path={output_path}")


@app.command()
def show_chapter(
    branch_id: str,
    chapter_index: int,
    database_url: str | None = None,
) -> None:
    """Show a compact chapter bundle for one branch/chapter."""

    settings = _safe_settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        bundle = _export_service(session).export_chapter_bundle(branch_id, chapter_index)
        echo(json.dumps(bundle, ensure_ascii=False, indent=2))


@app.command()
def export_chapter_bundle(
    branch_id: str,
    chapter_index: int,
    output_path: Path,
    database_url: str | None = None,
) -> None:
    """Export one chapter bundle JSON for external consumption."""

    settings = _safe_settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        bundle = _export_service(session).export_chapter_bundle(branch_id, chapter_index)
        output_path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding='utf-8')
        echo(f"chapter_bundle_path={output_path}")


@app.command()
def export_branch_bundle(
    run_id: str,
    branch_id: str,
    output_path: Path,
    database_url: str | None = None,
) -> None:
    """Export one branch bundle JSON for external consumption."""

    settings = _safe_settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        bundle = _export_service(session).export_branch_bundle(run_id, branch_id)
        output_path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding='utf-8')
        echo(f"bundle_path={output_path}")


@app.command()
def export_chapter_qa_context(
    branch_id: str,
    chapter_index: int,
    output_path: Path,
    database_url: str | None = None,
) -> None:
    """Export one chapter QA context JSON for downstream tools."""

    settings = _safe_settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        payload = _export_service(session).export_chapter_qa_context(branch_id, chapter_index)
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
        echo(f"chapter_qa_context_path={output_path}")


@app.command()
def export_branch_qa_context(
    run_id: str,
    branch_id: str,
    output_path: Path,
    database_url: str | None = None,
) -> None:
    """Export one branch QA context JSON for downstream tools."""

    settings = _safe_settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        payload = _export_service(session).export_branch_qa_context(run_id, branch_id)
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
        echo(f"branch_qa_context_path={output_path}")


@app.command()
def import_reader_feedback(
    branch_id: str,
    input_path: Path,
    database_url: str | None = None,
) -> None:
    """Import reader comments from JSON list."""

    settings = _safe_settings(database_url)
    factory = create_session_factory(settings)
    comments = json.loads(input_path.read_text(encoding='utf-8'))
    with factory() as session:
        payload = _reader_feedback_service(session).import_comments(branch_id, comments)
        echo(json.dumps(payload, ensure_ascii=False, indent=2))


@app.command()
def export_reader_feedback_summary(
    branch_id: str,
    output_path: Path,
    database_url: str | None = None,
) -> None:
    """Export reader feedback summary to JSON."""

    settings = _safe_settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        payload = _reader_feedback_service(session).summarize_branch_feedback(branch_id)
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
        echo(f"reader_feedback_summary_path={output_path}")


@app.command()
def show_author_knowledge(
    branch_id: str,
    from_chapter_index: int | None = None,
    upto_chapter_index: int | None = None,
    focus_label: str = "",
    database_url: str | None = None,
) -> None:
    """Show the author-facing branch knowledge pack."""

    settings = _safe_settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        payload = _author_knowledge_service(session).build_branch_knowledge_pack(
            branch_id,
            from_chapter_index=from_chapter_index,
            upto_chapter_index=upto_chapter_index,
            focus_label=focus_label,
        )
        echo(json.dumps(payload, ensure_ascii=False, indent=2))


@app.command()
def export_author_knowledge(
    branch_id: str,
    output_path: Path,
    from_chapter_index: int | None = None,
    upto_chapter_index: int | None = None,
    focus_label: str = "",
    database_url: str | None = None,
) -> None:
    """Export the author-facing branch knowledge pack to JSON."""

    settings = _safe_settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        payload = _author_knowledge_service(session).build_branch_knowledge_pack(
            branch_id,
            from_chapter_index=from_chapter_index,
            upto_chapter_index=upto_chapter_index,
            focus_label=focus_label,
        )
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        echo(f"author_knowledge_path={output_path}")


@app.command()
def export_markdown(
    branch_id: str,
    chapter_index: int,
    output_path: Path,
    database_url: str | None = None,
) -> None:
    """Export one chapter artifact to Markdown."""

    settings = _safe_settings(database_url)
    factory = create_session_factory(settings)
    from novel_analyzer.reporting.markdown import render_chapter_markdown
    with factory() as session:
        payload = session.execute(
            text(
                "SELECT payload_json FROM chapter_artifacts "
                "WHERE branch_id=:branch_id AND chapter_index=:chapter_index "
                "AND visibility='active' ORDER BY created_at DESC LIMIT 1"
            ),
            {"branch_id": branch_id, "chapter_index": chapter_index},
        ).scalar_one_or_none()
        if payload is None:
            raise typer.Exit(code=1)
        if isinstance(payload, str):
            payload = json.loads(payload)
        output_path.write_text(render_chapter_markdown(payload), encoding='utf-8')
        echo(f"markdown_path={output_path}")


@app.command()
def commit_demo(
    branch_id: str,
    chapter_index: int,
    database_url: str | None = None,
) -> None:
    """Commit a demo artifact for a chapter."""

    settings = _safe_settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        artifact = _run_service(session, settings).record_chapter_artifact(
            branch_id,
            chapter_index,
            payload={"chapter_index": chapter_index, "summary": f"chapter {chapter_index}"},
            source_kind='demo',
        )
        echo(f"artifact_id={artifact.id}")


@app.command()
def add_manual(
    branch_id: str,
    chapter_index: int,
    database_url: str | None = None,
) -> None:
    """Persist a manual artifact excluded from downstream by default."""

    settings = _safe_settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        artifact = _run_service(session, settings).add_manual_artifact(
            branch_id,
            chapter_index,
            payload={"note": "manual patch"},
        )
        echo(f"artifact_id={artifact.id}")
        echo(f"participates_in_downstream={artifact.participates_in_downstream}")


@app.command()
def fork_branch(
    branch_id: str,
    keep_through: int,
    name: str | None = None,
    database_url: str | None = None,
) -> None:
    """Fork a branch, preserving chapters <= keep_through and hiding later progress."""

    settings = _safe_settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        branch = _run_service(session, settings).fork_branch(branch_id, keep_through, name)
        echo(f"new_branch_id={branch.id}")
        echo(f"fork_after_chapter_index={branch.fork_after_chapter_index}")


@app.command()
def show_branch(branch_id: str, database_url: str | None = None) -> None:
    """Print a compact branch snapshot."""

    settings = _safe_settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        snapshot = _run_service(session, settings).branch_snapshot(branch_id)
        for key, value in snapshot.items():
            echo(f"{key}={value}")







@app.command()
def repair_branch(
    branch_id: str,
    database_url: str | None = None,
) -> None:
    """Backfill jobs and materialized layers for an existing branch."""

    settings = _safe_settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        report = _repair_service(session).repair_branch(branch_id)
        for key in report.__dataclass_fields__:
            echo(f"{key}={getattr(report, key)}")


@app.command()
def validate_branch(
    branch_id: str,
    database_url: str | None = None,
) -> None:
    """Run consistency checks for one branch."""

    settings = _safe_settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        report = _consistency_service(session).validate_branch(branch_id)
        echo(f"issue_count={report.issue_count}")
        for issue in report.issues:
            echo(f"issue={issue.severity}|{issue.code}|{issue.message}")


@app.command()
def search_facts(
    branch_id: str,
    query: str,
    limit: int = typer.Option(20, '--limit'),
    database_url: str | None = None,
) -> None:
    """Search extracted facts inside one branch."""

    settings = _safe_settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        facts = _fact_service(session).search_facts(branch_id, query, limit)
        echo(f"fact_hit_count={len(facts)}")
        for fact in facts:
            echo(
                f"fact=chapter:{fact.chapter_index}|type:{fact.fact_type}|label:{fact.label}|confidence:{fact.confidence}"
            )


@app.command()
def show_facts(
    branch_id: str,
    chapter_index: int | None = typer.Option(None, '--chapter-index'),
    limit: int = typer.Option(50, '--limit'),
    database_url: str | None = None,
) -> None:
    """Show fact rows for a branch (optionally one chapter)."""

    settings = _safe_settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        facts = _fact_service(session).list_facts(branch_id, chapter_index, limit)
        echo(f"fact_count={len(facts)}")
        for fact in facts:
            echo(
                f"fact=chapter:{fact.chapter_index}|type:{fact.fact_type}|label:{fact.label}|confidence:{fact.confidence}"
            )


@app.command()
def export_branch_package(
    run_id: str,
    branch_id: str,
    output_dir: Path,
    database_url: str | None = None,
) -> None:
    """Export a complete branch package directory."""

    settings = _safe_settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        path = _package_service(session).export_branch_package(run_id, branch_id, output_dir)
        echo(f"package_path={path}")


@app.command()
def export_branch_report(
    run_id: str,
    branch_id: str,
    output_path: Path,
    database_url: str | None = None,
) -> None:
    """Export a branch-level Markdown report."""

    settings = _safe_settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        bundle = _export_service(session).export_branch_bundle(run_id, branch_id)
        output_path.write_text(_render_branch_report(bundle), encoding='utf-8')
        echo(f"report_path={output_path}")


@app.command()
def set_cluster_status(
    branch_id: str,
    cluster_key: str,
    cluster_status: str,
    review_notes: str = typer.Option('', '--review-notes'),
    review_owner: str = typer.Option('', '--review-owner'),
    review_actor: str = typer.Option('', '--review-actor'),
    resolved_at: str = typer.Option('', '--resolved-at'),
    review_result: str = typer.Option('', '--review-result'),
    database_url: str | None = None,
) -> None:
    """Persist a minimal manual status override for one risk cluster."""
    settings = _safe_settings(database_url)
    factory = create_session_factory(settings)
    try:
        with factory() as session:
            from novel_analyzer.services.cluster_review_service import ClusterReviewService
            state: Any = ClusterReviewService(session).write(
                branch_id=branch_id,
                cluster_key=cluster_key,
                cluster_status=cluster_status,
                review_notes=review_notes,
                review_owner=review_owner,
                review_actor=review_actor,
                resolved_at=resolved_at,
                review_result=review_result,
            )
    except Exception:
        state = write_cluster_review_state(
            branch_id=branch_id,
            cluster_key=cluster_key,
            cluster_status=cluster_status,
            review_notes=review_notes,
            review_owner=review_owner,
            review_actor=review_actor,
            resolved_at=resolved_at,
            review_result=review_result,
            settings=settings,
        )
    echo(f"branch_id={state.branch_id}")
    echo(f"cluster_key={state.cluster_key}")
    echo(f"cluster_status={state.cluster_status}")
    echo(f"review_notes={state.review_notes}")
    echo(f"review_owner={state.review_owner}")
    echo(f"review_actor={state.review_actor}")
    echo(f"resolved_at={state.resolved_at}")
    echo(f"review_result={state.review_result}")


@app.command()
def show_cluster_status(branch_id: str, database_url: str | None = None) -> None:
    """Show persisted manual status overrides for one branch's risk clusters."""
    settings = _safe_settings(database_url)
    factory = create_session_factory(settings)
    try:
        with factory() as session:
            from novel_analyzer.services.cluster_review_service import ClusterReviewService
            payload = ClusterReviewService(session).read_branch(branch_id)
    except Exception:
        payload = read_cluster_review_state(branch_id, settings)
    echo(json.dumps(payload, ensure_ascii=False, indent=2))


@app.command()
def show_cluster_history(
    branch_id: str,
    cluster_key: str,
    event_type: str = typer.Option('', '--event-type'),
    review_owner: str = typer.Option('', '--review-owner'),
    review_result: str = typer.Option('', '--review-result'),
    limit: int = typer.Option(0, '--limit'),
    database_url: str | None = None,
) -> None:
    """Show review history for one cluster."""

    settings = _safe_settings(database_url)
    factory = create_session_factory(settings)
    try:
        with factory() as session:
            from novel_analyzer.services.cluster_review_service import ClusterReviewService
            payload = ClusterReviewService(session).read_history(branch_id, cluster_key)
    except Exception:
        payload = read_cluster_review_history(branch_id, cluster_key, settings)
    if event_type:
        payload = [item for item in payload if str(item.get('event_type') or '') == event_type]
    if review_owner:
        payload = [item for item in payload if str(item.get('review_owner') or '') == review_owner]
    if review_result:
        payload = [item for item in payload if str(item.get('review_result') or '') == review_result]
    if limit > 0:
        payload = payload[-limit:]
    echo(json.dumps(payload, ensure_ascii=False, indent=2))



@app.command()
def summarize_graph(
    branch_id: str,
    database_url: str | None = None,
) -> None:
    """Show a compact reasoning-oriented graph summary."""

    settings = _safe_settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        summary = _graph_service(session).summarize_branch(branch_id)
        echo(f"branch_id={summary.branch_id}")
        echo(f"node_count={summary.node_count}")
        echo(f"edge_count={summary.edge_count}")
        echo(f"node_types={json.dumps(summary.node_type_counts, ensure_ascii=False)}")
        echo(f"edge_types={json.dumps(summary.edge_type_counts, ensure_ascii=False)}")
        for label, count in summary.top_entities:
            echo(f"top_entity={label}:{count}")
        for label, count in summary.top_events:
            echo(f"top_event={label}:{count}")
        for label, count in summary.top_conflicts:
            echo(f"top_conflict={label}:{count}")
        for edge in summary.progression_edges:
            echo(f"progression={edge}")
        for path in summary.reasoning_paths:
            echo(f"reasoning_path={path}")
        for label in summary.open_foreshadowing:
            echo(f"open_foreshadowing={label}")
        for label in summary.active_conflicts:
            echo(f"active_conflict={label}")
        for label in summary.world_rules:
            echo(f"world_rule={label}")


@app.command()
def show_graph(
    branch_id: str,
    upto_chapter: int | None = None,
    database_url: str | None = None,
) -> None:
    """Show a compact graph snapshot for a branch."""

    settings = _safe_settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        snapshot = _graph_service(session).reasoning_snapshot(
            branch_id,
            upto_chapter=upto_chapter,
        )
        echo(json.dumps(snapshot, ensure_ascii=False, indent=2))


@app.command()
def show_reasoning_graph(
    branch_id: str,
    upto_chapter: int | None = None,
    database_url: str | None = None,
) -> None:
    """Show the full reasoning-graph JSON for a branch."""

    settings = _safe_settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        snapshot = _graph_service(session).reasoning_snapshot(
            branch_id,
            upto_chapter=upto_chapter,
            node_limit=50,
            edge_limit=80,
        )
        echo(json.dumps(snapshot, ensure_ascii=False, indent=2))


@app.command()
def plan_next_chapter(
    branch_id: str,
    primary_goal: str,
    emphasis: str = typer.Option("", "--emphasis"),
    forbidden_move: list[str] = typer.Option([], "--forbidden-move"),
    preferred_tone: str = typer.Option("", "--preferred-tone"),
    pace: str = typer.Option("", "--pace"),
    target_word_count: int | None = typer.Option(None, "--target-word-count"),
    database_url: str | None = None,
) -> None:
    """Build a visible next-chapter planning card for one branch."""

    from novel_analyzer.domain.schemas import ChapterPlanningIntent

    settings = _safe_settings(database_url)
    factory = create_session_factory(settings)
    emphasis_items = [item.strip() for item in emphasis.split(",") if item.strip()]
    intent = ChapterPlanningIntent(
        primary_goal=primary_goal,
        emphasis=emphasis_items,
        forbidden_moves=forbidden_move,
        preferred_tone=preferred_tone or None,
        pace=pace or None,
        target_word_count=target_word_count,
    )
    with factory() as session:
        payload = _next_chapter_planner_service(session).build_plan(branch_id, intent=intent)
        echo(payload.model_dump_json(indent=2, ensure_ascii=False))


@app.command()
def imitate_chapter(
    branch_id: str,
    source_chapter_index: int,
    target_goal: str,
    use_llm: bool = typer.Option(False, "--use-llm"),
    model_name: str = typer.Option("", "--model-name"),
    database_url: str | None = None,
) -> None:
    """Build a visible imitation plan + skeleton draft for one source chapter."""

    settings = _safe_settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        service = _chapter_imitation_service(session)
        payload = (
            service.build_llm_draft(
                branch_id,
                source_chapter_index=source_chapter_index,
                target_goal=target_goal,
                model_name=model_name or None,
            )
            if use_llm
            else service.build_skeleton_draft(
                branch_id,
                source_chapter_index=source_chapter_index,
                target_goal=target_goal,
            )
        )
        echo(payload.model_dump_json(indent=2, ensure_ascii=False))


@app.command()
def compare_imitation(
    branch_id: str,
    source_chapter_index: int,
    target_goal: str,
    use_llm: bool = typer.Option(False, "--use-llm"),
    model_name: str = typer.Option("", "--model-name"),
    database_url: str | None = None,
) -> None:
    """Build an imitation draft and a structured comparison report."""

    settings = _safe_settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        service = _chapter_imitation_service(session)
        draft = (
            service.build_llm_draft(
                branch_id,
                source_chapter_index=source_chapter_index,
                target_goal=target_goal,
                model_name=model_name or None,
            )
            if use_llm
            else service.build_skeleton_draft(
                branch_id,
                source_chapter_index=source_chapter_index,
                target_goal=target_goal,
            )
        )
        report = service.compare_with_source(
            branch_id,
            source_chapter_index=source_chapter_index,
            draft=draft,
        )
        echo(
            json.dumps(
                {
                    "draft": draft.model_dump(mode="json"),
                    "comparison": report.model_dump(mode="json"),
                },
                ensure_ascii=False,
                indent=2,
            )
        )


@app.command()
def review_imitation(
    branch_id: str,
    source_chapter_index: int,
    target_goal: str,
    use_llm: bool = typer.Option(False, "--use-llm"),
    model_name: str = typer.Option("", "--model-name"),
    database_url: str | None = None,
) -> None:
    """Build draft + comparison + review + revised draft for one imitation experiment."""

    settings = _safe_settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        service = _chapter_imitation_service(session)
        draft = (
            service.build_llm_draft(
                branch_id,
                source_chapter_index=source_chapter_index,
                target_goal=target_goal,
                model_name=model_name or None,
            )
            if use_llm
            else service.build_skeleton_draft(
                branch_id,
                source_chapter_index=source_chapter_index,
                target_goal=target_goal,
            )
        )
        comparison = service.compare_with_source(
            branch_id,
            source_chapter_index=source_chapter_index,
            draft=draft,
        )
        review = service.review_draft(
            branch_id,
            source_chapter_index=source_chapter_index,
            draft=draft,
        )
        gate = service.gate_draft(
            branch_id,
            source_chapter_index=source_chapter_index,
            draft=draft,
        )
        risk = service.risk_review_draft(
            branch_id,
            source_chapter_index=source_chapter_index,
            draft=draft,
        )
        revised = service.revise_draft(draft, review=review)
        echo(
            json.dumps(
                {
                    "draft": draft.model_dump(mode="json"),
                    "comparison": comparison.model_dump(mode="json"),
                    "review": review.model_dump(mode="json"),
                    "gate": gate.model_dump(mode="json"),
                    "risk": risk.model_dump(mode="json"),
                    "revised_draft": revised.model_dump(mode="json"),
                },
                ensure_ascii=False,
                indent=2,
            )
        )


@app.command()
def iterate_imitation(
    branch_id: str,
    source_chapter_index: int,
    target_goal: str,
    max_rounds: int = typer.Option(2, "--max-rounds"),
    use_llm: bool = typer.Option(False, "--use-llm"),
    model_name: str = typer.Option("", "--model-name"),
    database_url: str | None = None,
) -> None:
    """Run a multi-round imitation optimization loop and emit all rounds."""

    settings = _safe_settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        report = _chapter_imitation_service(session).iterate_draft(
            branch_id,
            source_chapter_index=source_chapter_index,
            target_goal=target_goal,
            max_rounds=max_rounds,
            use_llm=use_llm,
            model_name=model_name or None,
        )
        echo(report.model_dump_json(indent=2, ensure_ascii=False))


@app.command()
def multi_chapter_imitation_consistency(
    branch_id: str,
    chapter_spec: list[str] = typer.Argument(..., help="Pairs like 3:目标A 4:目标B"),
    max_rounds: int = typer.Option(1, "--max-rounds"),
    use_llm: bool = typer.Option(False, "--use-llm"),
    model_name: str = typer.Option("", "--model-name"),
    database_url: str | None = None,
) -> None:
    """Run a lightweight multi-chapter consistency pass across several imitation steps."""

    parsed: list[tuple[int, str]] = []
    for item in chapter_spec:
        chapter_text, _, goal = item.partition(":")
        if not chapter_text or not goal:
            raise typer.Exit(code=1)
        parsed.append((int(chapter_text), goal))

    settings = _safe_settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        report = _chapter_imitation_service(session).build_multi_chapter_consistency(
            branch_id,
            chapter_goals=parsed,
            max_rounds=max_rounds,
            use_llm=use_llm,
            model_name=model_name or None,
        )
        echo(report.model_dump_json(indent=2, ensure_ascii=False))


@app.command()
def plan_whole_book_imitation(
    branch_id: str,
    project_title: str,
    source_work_name: str,
    target_work_name: str,
    chapter_spec: list[str] = typer.Argument(..., help="Pairs like 3:目标A 4:目标B"),
    world_map: list[str] = typer.Option([], "--world-map"),
    character_map: list[str] = typer.Option([], "--character-map"),
    faction_map: list[str] = typer.Option([], "--faction-map"),
    power_map: list[str] = typer.Option([], "--power-map"),
    rule_override: list[str] = typer.Option([], "--rule-override"),
    forbidden_transformation: list[str] = typer.Option([], "--forbidden-transformation"),
    database_url: str | None = None,
) -> None:
    """Build a whole-book imitation orchestration skeleton."""
    chapter_goals = _parse_chapter_goal_spec(chapter_spec)
    mapping_pack = _build_story_mapping_pack(
        project_title,
        source_work_name,
        target_work_name,
        world_map=world_map,
        character_map=character_map,
        faction_map=faction_map,
        power_map=power_map,
        rule_override=rule_override,
        forbidden_transformation=forbidden_transformation,
    )
    settings = _safe_settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        report = _whole_book_imitation_service(session).build_plan(
            branch_id,
            mapping_pack=mapping_pack,
            chapter_goals=chapter_goals,
        )
        echo(report.model_dump_json(indent=2, ensure_ascii=False))


@app.command()
def run_whole_book_imitation(
    branch_id: str,
    project_title: str,
    source_work_name: str,
    target_work_name: str,
    chapter_spec: list[str] = typer.Argument(..., help="Pairs like 3:目标A 4:目标B"),
    world_map: list[str] = typer.Option([], "--world-map"),
    character_map: list[str] = typer.Option([], "--character-map"),
    faction_map: list[str] = typer.Option([], "--faction-map"),
    power_map: list[str] = typer.Option([], "--power-map"),
    rule_override: list[str] = typer.Option([], "--rule-override"),
    forbidden_transformation: list[str] = typer.Option([], "--forbidden-transformation"),
    execute: bool = typer.Option(False, "--execute", help="Run sandbox iteration instead of dry-run queue only."),
    max_rounds: int = typer.Option(1, "--max-rounds"),
    use_llm: bool = typer.Option(False, "--use-llm"),
    model_name: str = typer.Option("", "--model-name"),
    database_url: str | None = None,
) -> None:
    """Build a dry-run queue or execute a sandbox whole-book imitation run."""
    chapter_goals = _parse_chapter_goal_spec(chapter_spec)
    mapping_pack = _build_story_mapping_pack(
        project_title,
        source_work_name,
        target_work_name,
        world_map=world_map,
        character_map=character_map,
        faction_map=faction_map,
        power_map=power_map,
        rule_override=rule_override,
        forbidden_transformation=forbidden_transformation,
    )
    settings = _safe_settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        service = _whole_book_imitation_service(session)
        report = (
            service.run_in_sandbox(
                branch_id,
                mapping_pack=mapping_pack,
                chapter_goals=chapter_goals,
                max_rounds=max_rounds,
                use_llm=use_llm,
                model_name=model_name or None,
            )
            if execute
            else service.build_run_queue(
                branch_id,
                mapping_pack=mapping_pack,
                chapter_goals=chapter_goals,
            )
        )
        echo(report.model_dump_json(indent=2, ensure_ascii=False))


@app.command()
def export_whole_book_imitation_run(
    branch_id: str,
    project_title: str,
    source_work_name: str,
    target_work_name: str,
    output_path: Path,
    chapter_spec: list[str] = typer.Argument(..., help="Pairs like 3:目标A 4:目标B"),
    world_map: list[str] = typer.Option([], "--world-map"),
    character_map: list[str] = typer.Option([], "--character-map"),
    faction_map: list[str] = typer.Option([], "--faction-map"),
    power_map: list[str] = typer.Option([], "--power-map"),
    rule_override: list[str] = typer.Option([], "--rule-override"),
    forbidden_transformation: list[str] = typer.Option([], "--forbidden-transformation"),
    execute: bool = typer.Option(False, "--execute", help="Run sandbox iteration instead of dry-run queue only."),
    max_rounds: int = typer.Option(1, "--max-rounds"),
    use_llm: bool = typer.Option(False, "--use-llm"),
    model_name: str = typer.Option("", "--model-name"),
    database_url: str | None = None,
) -> None:
    """Export a whole-book imitation run report JSON for downstream systems."""

    chapter_goals = _parse_chapter_goal_spec(chapter_spec)
    mapping_pack = _build_story_mapping_pack(
        project_title,
        source_work_name,
        target_work_name,
        world_map=world_map,
        character_map=character_map,
        faction_map=faction_map,
        power_map=power_map,
        rule_override=rule_override,
        forbidden_transformation=forbidden_transformation,
    )
    settings = _safe_settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        service = _whole_book_imitation_service(session)
        report = (
            service.run_in_sandbox(
                branch_id,
                mapping_pack=mapping_pack,
                chapter_goals=chapter_goals,
                max_rounds=max_rounds,
                use_llm=use_llm,
                model_name=model_name or None,
            )
            if execute
            else service.build_run_queue(
                branch_id,
                mapping_pack=mapping_pack,
                chapter_goals=chapter_goals,
            )
        )
        output_path.write_text(report.model_dump_json(indent=2, ensure_ascii=False), encoding="utf-8")
        echo(f"whole_book_imitation_run_path={output_path}")


@app.command()
def show_imitation_skill_contracts(database_url: str | None = None) -> None:
    """Show the local imitation skill contracts expected by the harness controller."""

    settings = _safe_settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        payload = _imitation_harness_service(session, settings).list_skill_contracts()
        echo(json.dumps([item.model_dump(mode="json") for item in payload], ensure_ascii=False, indent=2))


@app.command()
def show_whole_book_imitation_readiness(
    branch_id: str = typer.Option("", "--branch-id"),
    database_url: str | None = None,
) -> None:
    """Show provider/database/branch readiness evidence for whole-book imitation freeze checks."""

    settings = _safe_settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        payload = _whole_book_readiness_payload(
            session,
            settings,
            branch_id=branch_id or None,
        )
        echo(json.dumps(payload, ensure_ascii=False, indent=2))


def _coerce_chapter_index(value: object) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


def _build_baseline_vs_steering_report(
    baseline_items: list[dict[str, object]],
    steering_items: list[dict[str, object]],
) -> dict[str, object]:
    baseline_by_chapter: dict[int, dict[str, object]] = {}
    for item in baseline_items:
        chapter_index = _coerce_chapter_index(item.get("source_chapter_index"))
        if chapter_index is None:
            continue
        baseline_by_chapter[chapter_index] = item
    steering_by_chapter: dict[int, dict[str, object]] = {}
    for item in steering_items:
        chapter_index = _coerce_chapter_index(item.get("source_chapter_index"))
        if chapter_index is None:
            continue
        steering_by_chapter[chapter_index] = item
    compared_chapters = sorted(set(baseline_by_chapter) & set(steering_by_chapter))
    comparisons: list[dict[str, object]] = []
    steering_changed_count = 0
    verdict_shift_count = 0
    for chapter_index in compared_chapters:
        baseline_item = baseline_by_chapter[chapter_index]
        steering_item = steering_by_chapter[chapter_index]
        baseline_verdict = str(baseline_item.get("final_verdict", "")).strip()
        steering_verdict = str(steering_item.get("final_verdict", "")).strip()
        baseline_stop_reason = str(baseline_item.get("stop_reason", "")).strip()
        steering_stop_reason = str(steering_item.get("stop_reason", "")).strip()
        baseline_draft = baseline_item.get("final_draft", {})
        steering_draft = steering_item.get("final_draft", {})
        baseline_title = ""
        steering_title = ""
        if isinstance(baseline_draft, dict):
            baseline_title = str(baseline_draft.get("draft_title", "")).strip()
        if isinstance(steering_draft, dict):
            steering_title = str(steering_draft.get("draft_title", "")).strip()
        title_changed = baseline_title != steering_title
        verdict_changed = baseline_verdict != steering_verdict or baseline_stop_reason != steering_stop_reason
        if title_changed:
            steering_changed_count += 1
        if verdict_changed:
            verdict_shift_count += 1
        comparisons.append(
            {
                "source_chapter_index": chapter_index,
                "baseline_final_verdict": baseline_verdict,
                "steering_final_verdict": steering_verdict,
                "baseline_stop_reason": baseline_stop_reason,
                "steering_stop_reason": steering_stop_reason,
                "baseline_draft_title": baseline_title,
                "steering_draft_title": steering_title,
                "title_changed": title_changed,
                "verdict_changed": verdict_changed,
            }
        )
    summary_lines = [
        f"对照章节数={len(compared_chapters)}",
        f"标题变化章节数={steering_changed_count}",
        f"verdict/stop_reason 变化章节数={verdict_shift_count}",
    ]
    return {
        "chapter_count": len(compared_chapters),
        "title_changed_count": steering_changed_count,
        "verdict_shift_count": verdict_shift_count,
        "summary": "；".join(summary_lines),
        "items": comparisons,
    }


def _extract_reader_sim_snapshot(payload: dict[str, object]) -> dict[str, object]:
    rounds = payload.get("rounds", [])
    if not isinstance(rounds, list) or not rounds:
        return {
            "engagement_score": 0,
            "concerns": [],
            "recommended_actions": [],
            "reader_profile": "",
        }
    last_round = rounds[-1]
    if not isinstance(last_round, dict):
        return {
            "engagement_score": 0,
            "concerns": [],
            "recommended_actions": [],
            "reader_profile": "",
        }
    skill_outputs = last_round.get("skill_outputs", {})
    if not isinstance(skill_outputs, dict):
        return {
            "engagement_score": 0,
            "concerns": [],
            "recommended_actions": [],
            "reader_profile": "",
        }
    reader_output = skill_outputs.get("reader-sim-review", {})
    if not isinstance(reader_output, dict):
        return {
            "engagement_score": 0,
            "concerns": [],
            "recommended_actions": [],
            "reader_profile": "",
        }
    concerns = [str(item).strip() for item in reader_output.get("concerns", []) if str(item).strip()]
    recommended_actions = [
        str(item).strip()
        for item in reader_output.get("recommended_actions", [])
        if str(item).strip()
    ]
    score_raw = reader_output.get("engagement_score", 0)
    engagement_score = int(score_raw) if isinstance(score_raw, int) else 0
    return {
        "engagement_score": engagement_score,
        "concerns": concerns,
        "recommended_actions": recommended_actions,
        "reader_profile": str(reader_output.get("reader_profile", "")).strip(),
    }


def _build_reader_sim_acceptance_summary(
    baseline_items: list[dict[str, object]],
    steering_items: list[dict[str, object]],
) -> dict[str, object]:
    baseline_by_chapter: dict[int, dict[str, object]] = {}
    for item in baseline_items:
        chapter_index = _coerce_chapter_index(item.get("source_chapter_index"))
        if chapter_index is None:
            continue
        baseline_by_chapter[chapter_index] = item
    steering_by_chapter: dict[int, dict[str, object]] = {}
    for item in steering_items:
        chapter_index = _coerce_chapter_index(item.get("source_chapter_index"))
        if chapter_index is None:
            continue
        steering_by_chapter[chapter_index] = item
    compared_chapters = sorted(set(baseline_by_chapter) & set(steering_by_chapter))
    items: list[dict[str, object]] = []
    improved_count = 0
    for chapter_index in compared_chapters:
        baseline_snapshot = _extract_reader_sim_snapshot(baseline_by_chapter[chapter_index])
        steering_snapshot = _extract_reader_sim_snapshot(steering_by_chapter[chapter_index])
        baseline_score_raw = baseline_snapshot.get("engagement_score", 0)
        steering_score_raw = steering_snapshot.get("engagement_score", 0)
        baseline_score = baseline_score_raw if isinstance(baseline_score_raw, int) else 0
        steering_score = steering_score_raw if isinstance(steering_score_raw, int) else 0
        score_delta = steering_score - baseline_score
        baseline_concerns_raw = baseline_snapshot.get("concerns", [])
        steering_concerns_raw = steering_snapshot.get("concerns", [])
        baseline_concerns = baseline_concerns_raw if isinstance(baseline_concerns_raw, list) else []
        steering_concerns = steering_concerns_raw if isinstance(steering_concerns_raw, list) else []
        concern_delta = len(steering_concerns) - len(baseline_concerns)
        improved = score_delta > 0 or concern_delta < 0
        if improved:
            improved_count += 1
        items.append(
            {
                "source_chapter_index": chapter_index,
                "baseline_engagement_score": baseline_score,
                "steering_engagement_score": steering_score,
                "score_delta": score_delta,
                "baseline_concern_count": len(baseline_concerns),
                "steering_concern_count": len(steering_concerns),
                "concern_delta": concern_delta,
                "steering_top_concerns": steering_concerns[:3],
                "improved": improved,
            }
        )
    score_delta_total = 0
    for item in items:
        score_delta_value = item.get("score_delta")
        if isinstance(score_delta_value, int):
            score_delta_total += score_delta_value
    average_delta = round(score_delta_total / len(items), 2) if items else 0.0
    summary = (
        f"reader-sim 改善章节数={improved_count}/{len(items)}；平均 engagement delta={average_delta}"
        if items
        else "当前缺少 reader-sim round evidence。"
    )
    return {
        "chapter_count": len(items),
        "improved_count": improved_count,
        "average_score_delta": average_delta,
        "summary": summary,
        "items": items,
    }


def _build_experiment_decision_note(
    baseline_vs_steering_report: dict[str, object],
    delta_visual_summary: dict[str, object],
    reader_sim_acceptance_summary: dict[str, object],
) -> dict[str, object]:
    comparison_chapters_raw = baseline_vs_steering_report.get("chapter_count", 0)
    comparison_chapters = comparison_chapters_raw if isinstance(comparison_chapters_raw, int) else 0
    verdict_shift_raw = baseline_vs_steering_report.get("verdict_shift_count", 0)
    verdict_shift_count = verdict_shift_raw if isinstance(verdict_shift_raw, int) else 0
    innovation_card = delta_visual_summary.get("innovation_card", {})
    risk_card = delta_visual_summary.get("risk_card", {})
    innovation_level = (
        str(innovation_card.get("level", "light")).strip()
        if isinstance(innovation_card, dict)
        else "light"
    )
    risk_level = (
        str(risk_card.get("level", "low")).strip()
        if isinstance(risk_card, dict)
        else "low"
    )
    improved_count_raw = reader_sim_acceptance_summary.get("improved_count", 0)
    improved_count = improved_count_raw if isinstance(improved_count_raw, int) else 0
    acceptance_chapters_raw = reader_sim_acceptance_summary.get("chapter_count", 0)
    acceptance_chapters = (
        acceptance_chapters_raw if isinstance(acceptance_chapters_raw, int) else 0
    )
    average_score_delta_raw = reader_sim_acceptance_summary.get("average_score_delta", 0)
    average_score_delta = (
        float(average_score_delta_raw)
        if isinstance(average_score_delta_raw, (int, float))
        else 0.0
    )
    recommendation = "hold"
    reason = "当前信号不足以支持推广，先继续补实验或修正风险。"
    next_action = "补更多连续章节实验，并先消化当前风险/读者卡点。"
    if comparison_chapters > 0 and improved_count == acceptance_chapters and risk_level == "low":
        recommendation = "promote"
        reason = "reader-sim 与风险信号都支持继续放大，本轮可进入更长区间推广验证。"
        next_action = "把同主题 steering 推广到更长章节区间，并继续收集真实读者反馈。"
    elif improved_count > 0 and risk_level in {"low", "medium"}:
        recommendation = "pilot"
        reason = "已有部分正向接受度信号，但仍需更长区间与 continuity 复核。"
        next_action = "保留当前 steering 方向，先做 1 个更长批次的 pilot run。"
    elif innovation_level == "high" and risk_level in {"medium", "high"}:
        recommendation = "de-risk"
        reason = "创新强度已经上来，但风险与稳定性仍不够，先降风险再推广。"
        next_action = "收缩 directive 或 taboo 边界后重跑，再决定是否扩大。"

    pilot_scope = "2-4 章连续 pilot"
    promotion_gate = "reader_improved_count > 0 且 risk_level != high"
    rollback_trigger = "reader_acceptance 转负或 risk_level 升到 high"
    evidence_required = [
        "baseline_vs_steering_report",
        "delta_visual_summary",
        "reader_sim_acceptance_summary",
    ]
    if recommendation == "promote":
        pilot_scope = "5-8 章扩区验证"
        promotion_gate = "reader_improved_count == reader_chapter_count 且 risk_level == low"
        rollback_trigger = "连续章节出现 verdict_shift_count 上升或读者接受度回落"
        evidence_required.append("真实读者反馈")
    elif recommendation == "de-risk":
        pilot_scope = "1-2 章降风险复跑"
        promotion_gate = "先把 risk_level 压回 low/medium 再讨论扩大"
        rollback_trigger = "继续出现高风险 + 读者接受度无改善"
    elif recommendation == "hold":
        pilot_scope = "暂停扩大，仅补证据"
        promotion_gate = "至少补齐新的 pilot 证据再决定"
        rollback_trigger = "下一轮仍无正向 reader-sim 改善"

    ship_blockers: list[str] = []
    required_human_review: list[str] = []
    confidence_level = "medium"
    business_risk_label = "controlled"
    go_live_checklist = [
        "确认 baseline_vs_steering_report 已更新",
        "确认 delta_visual_summary 与 reader_sim_acceptance_summary 已复核",
        "确认最新 steering 命中文档与禁区边界仍适用",
    ]
    if risk_level == "high":
        ship_blockers.append("high_risk_level")
        required_human_review.append("风险/连续性人工复核")
        confidence_level = "low"
        business_risk_label = "high-risk"
    elif risk_level == "medium":
        required_human_review.append("中风险实验人工抽查")
        confidence_level = "medium"
        business_risk_label = "guarded"
    else:
        confidence_level = "high" if recommendation == "promote" else "medium"
        business_risk_label = "controlled"
    if improved_count <= 0:
        ship_blockers.append("reader_acceptance_not_improved")
        required_human_review.append("读者接受度无改善原因复盘")
        confidence_level = "low"
    if verdict_shift_count > max(1, comparison_chapters // 2):
        ship_blockers.append("verdict_shift_too_high")
        required_human_review.append("gate/verdict 变化过大复核")
        business_risk_label = "guarded"
    if recommendation == "promote":
        go_live_checklist.extend(
            [
                "确认真实读者反馈采集窗口已准备",
                "确认扩大批次的 rollback trigger 已预先登记",
            ]
        )
    else:
        go_live_checklist.extend(
            [
                "确认 pilot_scope 与 evidence_required 已被执行负责人接受",
                "确认下一轮复跑窗口与评审人已明确",
            ]
        )

    success_kpi_targets = [
        f"reader_improved_count >= {max(1, acceptance_chapters // 2 or 1)}",
        "business_risk_label != high-risk",
        "rollback_trigger 未被触发",
    ]
    failure_kpi_triggers = [
        "reader_acceptance_not_improved",
        "high_risk_level",
        "verdict_shift_too_high",
    ]
    observation_window = (
        "上线后连续观察 5-8 章"
        if recommendation == "promote"
        else "下一轮 pilot 观察 2-4 章"
    )
    owner_roles = [
        "writer-operator",
        "continuity-reviewer",
        "reader-feedback-owner",
    ]
    if business_risk_label in {"guarded", "high-risk"}:
        owner_roles.append("risk-approver")
    handoff_packet = [
        "writer_innovation_explanation",
        "experiment_decision_note",
        "baseline_vs_steering_report",
        "reader_sim_acceptance_summary",
    ]

    return {
        "recommendation": recommendation,
        "reason": reason,
        "next_action": next_action,
        "comparison_chapter_count": comparison_chapters,
        "verdict_shift_count": verdict_shift_count,
        "reader_improved_count": improved_count,
        "reader_chapter_count": acceptance_chapters,
        "average_score_delta": average_score_delta,
        "innovation_level": innovation_level,
        "risk_level": risk_level,
        "pilot_scope": pilot_scope,
        "promotion_gate": promotion_gate,
        "rollback_trigger": rollback_trigger,
        "evidence_required": evidence_required,
        "ship_blockers": ship_blockers,
        "required_human_review": required_human_review,
        "confidence_level": confidence_level,
        "business_risk_label": business_risk_label,
        "go_live_checklist": go_live_checklist,
        "success_kpi_targets": success_kpi_targets,
        "failure_kpi_triggers": failure_kpi_triggers,
        "observation_window": observation_window,
        "owner_roles": owner_roles,
        "handoff_packet": handoff_packet,
    }


def _build_writer_innovation_explanation(
    steering_pack: SteeringPack,
    retrieval_meta: SteeringRetrievalMeta,
    baseline_vs_steering_report: dict[str, object],
    delta_visual_summary: dict[str, object],
    reader_sim_acceptance_summary: dict[str, object],
) -> dict[str, object]:
    worldview = steering_pack.get("worldview_capsule", [])[:2]
    tropes = steering_pack.get("trope_axes", [])[:3]
    directives = steering_pack.get("innovation_directives", [])[:3]
    taboo = steering_pack.get("taboo_innovations", [])[:2]
    top_hits: list[str] = []
    selected_doc_summaries = retrieval_meta.get("selected_doc_summaries", {})
    for bucket in ["trope", "worldview", "audience"]:
        docs = selected_doc_summaries.get(bucket, [])
        for item in docs[:1]:
            slug = str(item.get("slug", "")).strip()
            summary = str(item.get("summary", "")).strip()
            if slug:
                top_hits.append(f"{bucket}:{slug}")
            if summary and len(top_hits) >= 3:
                break
    comparison_summary = str(baseline_vs_steering_report.get("summary", "")).strip()
    innovation_card = delta_visual_summary.get("innovation_card", {})
    risk_card = delta_visual_summary.get("risk_card", {})
    innovation_level = str(innovation_card.get("level", "light")).strip() if isinstance(innovation_card, dict) else "light"
    risk_level = str(risk_card.get("level", "low")).strip() if isinstance(risk_card, dict) else "low"
    reader_summary = str(reader_sim_acceptance_summary.get("summary", "")).strip()
    explanation_lines = []
    if worldview:
        explanation_lines.append(f"本轮世界观底座：{'；'.join(worldview)}")
    if tropes:
        explanation_lines.append(f"本轮套路轴：{'；'.join(tropes)}")
    if directives:
        explanation_lines.append(f"本轮创新动作：{'；'.join(directives)}")
    if top_hits:
        explanation_lines.append(f"主要参考命中：{'；'.join(top_hits[:3])}")
    if comparison_summary:
        explanation_lines.append(f"baseline 对照：{comparison_summary}")
    if reader_summary:
        explanation_lines.append(f"reader-sim：{reader_summary}")
    if taboo:
        explanation_lines.append(f"本轮禁区：{'；'.join(taboo)}")
    focus = "先保 continuity，再放大创新收益。"
    if innovation_level == "high" and risk_level in {"medium", "high"}:
        focus = "创新偏强且风险升高，优先压住越界与 continuity 破口。"
    elif innovation_level in {"medium", "high"}:
        focus = "创新已进入发力区，优先检查收益兑现是否足够具体。"
    elif risk_level in {"medium", "high"}:
        focus = "风险提示偏高，优先处理禁区与读者卡点。"
    return {
        "summary": " | ".join(explanation_lines),
        "focus": focus,
        "top_worldview": worldview,
        "top_tropes": tropes,
        "top_directives": directives,
        "top_hits": top_hits[:3],
        "taboo_reminders": taboo,
    }


def _build_delta_visual_summary(
    steering_pack: SteeringPack,
    retrieval_meta: SteeringRetrievalMeta,
) -> dict[str, object]:
    worldview_count = len(steering_pack["worldview_capsule"])
    trope_count = len(steering_pack["trope_axes"])
    innovation_count = len(steering_pack["innovation_directives"])
    taboo_count = len(steering_pack["taboo_innovations"])
    knowledge_count = len(steering_pack["external_knowledge_refs"])
    selected_doc_count = 0
    for key in ["selected_trope_docs", "selected_worldview_docs", "selected_audience_docs"]:
        value = retrieval_meta.get(key, [])
        if isinstance(value, list):
            selected_doc_count += len(value)
    innovation_pressure = innovation_count + trope_count + worldview_count
    risk_pressure = taboo_count + max(0, selected_doc_count - innovation_count)
    innovation_level = "light"
    if innovation_pressure >= 8:
        innovation_level = "high"
    elif innovation_pressure >= 4:
        innovation_level = "medium"
    risk_level = "low"
    if risk_pressure >= 6:
        risk_level = "high"
    elif risk_pressure >= 3:
        risk_level = "medium"
    return {
        "innovation_card": {
            "level": innovation_level,
            "worldview_count": worldview_count,
            "trope_count": trope_count,
            "innovation_directive_count": innovation_count,
            "summary": f"创新压力={innovation_pressure}（worldview={worldview_count}, trope={trope_count}, directive={innovation_count}）",
        },
        "risk_card": {
            "level": risk_level,
            "taboo_count": taboo_count,
            "knowledge_ref_count": knowledge_count,
            "selected_doc_count": selected_doc_count,
            "summary": f"风险压力={risk_pressure}（taboo={taboo_count}, refs={knowledge_count}, hits={selected_doc_count}）",
        },
        "operator_hint": (
            "创新已偏高，优先检查 continuity 与 reader-sim 反馈。"
            if innovation_level == "high"
            else "当前创新增量可控，可继续观察 baseline vs steering 差异。"
        ),
    }


def _write_writer_imitation_outputs(
    output_dir: Path,
    stem: str,
    payload: dict[str, object],
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{stem}.json"
    md_path = output_dir / f"{stem}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines: list[str] = [f"# {stem}"]
    steering_pack = payload.get("steering_pack", {})
    if isinstance(steering_pack, dict) and steering_pack:
        lines.append("\n## Steering Pack")
        for key, value in steering_pack.items():
            if isinstance(value, list):
                joined = "；".join(str(item) for item in value if str(item).strip())
                lines.append(f"- {key}: {joined}")
            else:
                lines.append(f"- {key}: {value}")
    steering_retrieval_meta = payload.get("steering_retrieval_meta", {})
    if isinstance(steering_retrieval_meta, dict) and steering_retrieval_meta:
        lines.append("\n## Steering Retrieval Meta")
        for key in ["selected_trope_docs", "selected_worldview_docs", "selected_audience_docs"]:
            value = steering_retrieval_meta.get(key, [])
            if isinstance(value, list) and value:
                lines.append(f"- {key}: {'；'.join(str(item) for item in value)}")
        hit_reasons = steering_retrieval_meta.get("hit_reasons", {})
        if isinstance(hit_reasons, dict) and hit_reasons:
            lines.append("\n### Hit Reasons")
            for bucket, mapping in hit_reasons.items():
                if not isinstance(mapping, dict) or not mapping:
                    continue
                lines.append(f"- {bucket}:")
                for slug, reasons in mapping.items():
                    joined = "；".join(str(item) for item in reasons if str(item).strip())
                    lines.append(f"  - {slug}: {joined}")
        selected_doc_summaries = steering_retrieval_meta.get("selected_doc_summaries", {})
        non_empty_summary_buckets = {
            bucket: docs
            for bucket, docs in selected_doc_summaries.items()
            if isinstance(docs, list) and docs
        } if isinstance(selected_doc_summaries, dict) else {}
        if non_empty_summary_buckets:
            lines.append("\n### Hit Doc Summaries")
            for bucket, docs in non_empty_summary_buckets.items():
                lines.append(f"- {bucket}:")
                for item in docs:
                    if not isinstance(item, dict):
                        continue
                    slug = str(item.get("slug", "")).strip()
                    summary = str(item.get("summary", "")).strip()
                    labels = item.get("labels", [])
                    label_text = " / ".join(
                        str(label).strip() for label in labels if str(label).strip()
                    ) if isinstance(labels, list) else ""
                    detail = summary or label_text or "(no summary)"
                    lines.append(f"  - {slug}: {detail}")
    writer_innovation_explanation = payload.get("writer_innovation_explanation", {})
    if isinstance(writer_innovation_explanation, dict) and writer_innovation_explanation:
        lines.append("\n## Writer Innovation Explanation")
        summary = str(writer_innovation_explanation.get("summary", "")).strip()
        focus = str(writer_innovation_explanation.get("focus", "")).strip()
        if summary:
            lines.append(f"- summary: {summary}")
        if focus:
            lines.append(f"- focus: {focus}")
        for key in ["top_worldview", "top_tropes", "top_directives", "top_hits", "taboo_reminders"]:
            value = writer_innovation_explanation.get(key, [])
            if isinstance(value, list) and value:
                lines.append(f"- {key}: {'；'.join(str(item) for item in value if str(item).strip())}")
    experiment_decision_note = payload.get("experiment_decision_note", {})
    if isinstance(experiment_decision_note, dict) and experiment_decision_note:
        lines.append("\n## Experiment Decision Note")
        for key in [
            "recommendation",
            "reason",
            "next_action",
            "comparison_chapter_count",
            "reader_improved_count",
            "reader_chapter_count",
            "average_score_delta",
            "innovation_level",
            "risk_level",
            "pilot_scope",
            "promotion_gate",
            "rollback_trigger",
            "confidence_level",
            "business_risk_label",
            "observation_window",
        ]:
            if key in experiment_decision_note:
                lines.append(f"- {key}: {experiment_decision_note[key]}")
        for list_key in [
            "evidence_required",
            "ship_blockers",
            "required_human_review",
            "go_live_checklist",
            "success_kpi_targets",
            "failure_kpi_triggers",
            "owner_roles",
            "handoff_packet",
        ]:
            value = experiment_decision_note.get(list_key, [])
            if isinstance(value, list) and value:
                lines.append(f"- {list_key}: {'；'.join(str(item) for item in value if str(item).strip())}")
    delta_visual_summary = payload.get("delta_visual_summary", {})
    if isinstance(delta_visual_summary, dict) and delta_visual_summary:
        lines.append("\n## Delta Visual Summary")
        for card_key in ["innovation_card", "risk_card"]:
            card = delta_visual_summary.get(card_key, {})
            if not isinstance(card, dict) or not card:
                continue
            lines.append(f"\n### {card_key}")
            for key, value in card.items():
                lines.append(f"- {key}: {value}")
        operator_hint = str(delta_visual_summary.get("operator_hint", "")).strip()
        if operator_hint:
            lines.append(f"\n### Operator Hint\n- {operator_hint}")
    reader_sim_acceptance_summary = payload.get("reader_sim_acceptance_summary", {})
    if isinstance(reader_sim_acceptance_summary, dict) and reader_sim_acceptance_summary:
        lines.append("\n## Reader Sim Acceptance Summary")
        for key in ["chapter_count", "improved_count", "average_score_delta", "summary"]:
            if key in reader_sim_acceptance_summary:
                lines.append(f"- {key}: {reader_sim_acceptance_summary[key]}")
        acceptance_items = reader_sim_acceptance_summary.get("items", [])
        if isinstance(acceptance_items, list) and acceptance_items:
            lines.append("\n### Reader Sim Acceptance")
            for item in acceptance_items:
                if not isinstance(item, dict):
                    continue
                lines.append(f"- chapter {item.get('source_chapter_index')}:")
                lines.append(
                    f"  - engagement: {item.get('baseline_engagement_score')} -> {item.get('steering_engagement_score')}"
                )
                lines.append(
                    f"  - concerns: {item.get('baseline_concern_count')} -> {item.get('steering_concern_count')}"
                )
                lines.append(f"  - improved: {item.get('improved')}")
    final_draft = payload.get("final_draft", {})
    if isinstance(final_draft, dict):
        draft_title = str(final_draft.get("draft_title", "")).strip()
        draft_text = str(final_draft.get("draft_text", "")).strip()
        visible_draft_text = draft_text.split("【Harness Action Queue】", 1)[0].rstrip()
        if draft_title:
            lines.append(f"\n## Draft Title\n{draft_title}")
        if visible_draft_text:
            lines.append(f"\n## Draft Text\n{visible_draft_text}")
        risk_gate_notes = final_draft.get("risk_gate_notes", [])
        if isinstance(risk_gate_notes, list) and risk_gate_notes:
            deduped_notes: list[str] = []
            seen_notes: set[str] = set()
            for item in risk_gate_notes:
                note = str(item).strip()
                if not note or note in seen_notes:
                    continue
                seen_notes.add(note)
                deduped_notes.append(note)
            lines.append("\n## Risk Gate Notes")
            lines.extend(f"- {item}" for item in deduped_notes[:12])
    final_verdict = str(payload.get("final_verdict", "")).strip()
    if final_verdict:
        lines.append(f"\n## Final Verdict\n- {final_verdict}")
    stop_reason = str(payload.get("stop_reason", "")).strip()
    if stop_reason:
        lines.append(f"\n## Stop Reason\n- {stop_reason}")
    policy_summary = payload.get("policy_summary", {})
    if isinstance(policy_summary, dict) and policy_summary:
        lines.append("\n## Policy Summary")
        for key, value in policy_summary.items():
            lines.append(f"- {key}: {value}")
    items = payload.get("items", [])
    if isinstance(items, list) and items:
        lines.append("\n## Range Items")
        for item in items:
            if not isinstance(item, dict):
                continue
            chapter_index = item.get("source_chapter_index")
            target_goal = item.get("target_goal")
            final_verdict = str(item.get("final_verdict", "")).strip()
            stop_reason = str(item.get("stop_reason", "")).strip()
            lines.append(f"\n### Chapter {chapter_index}")
            lines.append(f"- target_goal: {target_goal}")
            lines.append(f"- final_verdict: {final_verdict}")
            lines.append(f"- stop_reason: {stop_reason}")
            final_draft = item.get("final_draft", {})
            if isinstance(final_draft, dict):
                draft_title = str(final_draft.get("draft_title", "")).strip()
                draft_text = str(final_draft.get("draft_text", "")).strip()
                visible_draft_text = draft_text.split("【Harness Action Queue】", 1)[0].rstrip()
                if draft_title:
                    lines.append(f"- draft_title: {draft_title}")
                if visible_draft_text:
                    lines.append("")
                    lines.append(visible_draft_text)
    experiment_meta = payload.get("experiment_meta", {})
    if isinstance(experiment_meta, dict) and experiment_meta:
        lines.append("\n## Experiment Meta")
        for key, value in experiment_meta.items():
            if key == "baseline_vs_steering_report" and isinstance(value, dict):
                lines.append(f"- {key}:")
                for sub_key in ["chapter_count", "title_changed_count", "verdict_shift_count", "summary"]:
                    if sub_key in value:
                        lines.append(f"  - {sub_key}: {value[sub_key]}")
                report_items = value.get("items", [])
                if isinstance(report_items, list) and report_items:
                    lines.append("\n### Baseline vs Steering")
                    for item in report_items:
                        if not isinstance(item, dict):
                            continue
                        lines.append(f"- chapter {item.get('source_chapter_index')}:")
                        lines.append(
                            f"  - baseline: {item.get('baseline_final_verdict')} / {item.get('baseline_stop_reason')}"
                        )
                        lines.append(
                            f"  - steering: {item.get('steering_final_verdict')} / {item.get('steering_stop_reason')}"
                        )
                        lines.append(f"  - title_changed: {item.get('title_changed')}")
                continue
            if isinstance(value, dict):
                lines.append(f"- {key}:")
                for sub_key, sub_value in value.items():
                    lines.append(f"  - {sub_key}: {sub_value}")
            else:
                lines.append(f"- {key}: {value}")
    md_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    return json_path, md_path


def _writer_review_markdown(
    *,
    source_chapter_index: int,
    target_goal: str,
    report_payload: dict[str, object],
) -> str:
    lines: list[str] = [f"# writer-imitate-review-ch{source_chapter_index}"]
    lines.append(f"\n- source_chapter_index: {source_chapter_index}")
    lines.append(f"- target_goal: {target_goal}")

    final_verdict = str(report_payload.get("final_verdict", "")).strip()
    stop_reason = str(report_payload.get("stop_reason", "")).strip()
    if final_verdict:
        lines.append(f"- final_verdict: {final_verdict}")
    if stop_reason:
        lines.append(f"- stop_reason: {stop_reason}")

    rounds = report_payload.get("rounds", [])
    first_round = rounds[0] if isinstance(rounds, list) and rounds and isinstance(rounds[0], dict) else {}
    if isinstance(first_round, dict):
        comparison = first_round.get("comparison", {})
        if isinstance(comparison, dict):
            lines.append("\n## Side-by-side Review")
            lines.append(f"- source_title: {comparison.get('original_title', '')}")
            lines.append(f"- draft_title: {comparison.get('draft_title', '')}")
            lines.append(f"- source_length: {comparison.get('source_length', '')}")
            lines.append(f"- draft_length: {comparison.get('draft_length', '')}")
            structure_notes = comparison.get("structure_overlap_notes", [])
            if isinstance(structure_notes, list) and structure_notes:
                lines.append("\n### Structure Notes")
                lines.extend(f"- {str(item)}" for item in structure_notes[:8])
            style_notes = comparison.get("style_alignment_notes", [])
            if isinstance(style_notes, list) and style_notes:
                lines.append("\n### Style Notes")
                lines.extend(f"- {str(item)}" for item in style_notes[:8])
            risk_notes = comparison.get("risk_alignment_notes", [])
            if isinstance(risk_notes, list) and risk_notes:
                lines.append("\n### Risk Alignment Notes")
                lines.extend(f"- {str(item)}" for item in risk_notes[:8])

    final_draft = report_payload.get("final_draft", {})
    if isinstance(final_draft, dict):
        draft_title = str(final_draft.get("draft_title", "")).strip()
        draft_text = str(final_draft.get("draft_text", "")).strip()
        visible_draft_text = draft_text.split("【Harness Action Queue】", 1)[0].rstrip()
        if draft_title:
            lines.append(f"\n## Draft Title\n{draft_title}")
        if visible_draft_text:
            lines.append(f"\n## Draft Text\n{visible_draft_text}")
        risk_gate_notes = final_draft.get("risk_gate_notes", [])
        if isinstance(risk_gate_notes, list) and risk_gate_notes:
            lines.append("\n## Risk Gate Notes")
            seen: set[str] = set()
            for item in risk_gate_notes:
                note = str(item).strip()
                if note and note not in seen:
                    seen.add(note)
                    lines.append(f"- {note}")

    policy_summary = report_payload.get("policy_summary", {})
    if isinstance(policy_summary, dict) and policy_summary:
        lines.append("\n## Policy Summary")
        for key, value in policy_summary.items():
            lines.append(f"- {key}: {value}")

    action_queue = report_payload.get("action_queue", [])
    if isinstance(action_queue, list) and action_queue:
        lines.append("\n## Action Queue")
        for item in action_queue[:12]:
            if not isinstance(item, dict):
                continue
            lines.append(
                f"- P{item.get('priority')} | {item.get('severity')} | "
                f"{item.get('action_type')} -> {item.get('target')}"
            )
    return "\n".join(lines).strip() + "\n"


def _build_writer_output_session_state(output_dir: Path) -> dict[str, object]:
    experiment_files = sorted(output_dir.glob("writer-innovation-experiment-*.json"))
    ledger_entries: list[dict[str, object]] = []
    session_recommendations: list[str] = []
    session_risk_labels: list[str] = []
    session_next_actions: list[str] = []
    session_focuses: list[str] = []

    for path in experiment_files:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        experiment_name = str(payload.get("experiment_name", "")).strip() or path.stem
        decision_note = payload.get("experiment_decision_note", {})
        recommendation = ""
        next_action = ""
        pilot_scope = ""
        confidence_level = ""
        observation_window = ""
        business_risk_label = ""
        if isinstance(decision_note, dict):
            recommendation = str(decision_note.get("recommendation", "")).strip()
            next_action = str(decision_note.get("next_action", "")).strip()
            pilot_scope = str(decision_note.get("pilot_scope", "")).strip()
            confidence_level = str(decision_note.get("confidence_level", "")).strip()
            observation_window = str(decision_note.get("observation_window", "")).strip()
            business_risk_label = str(decision_note.get("business_risk_label", "")).strip()
        explanation = payload.get("writer_innovation_explanation", {})
        focus = str(explanation.get("focus", "")).strip() if isinstance(explanation, dict) else ""
        acceptance = payload.get("reader_sim_acceptance_summary", {})
        reader_acceptance = {}
        if isinstance(acceptance, dict):
            reader_acceptance = {
                "improved_count": int(acceptance.get("improved_count", 0) or 0),
                "chapter_count": int(acceptance.get("chapter_count", 0) or 0),
                "average_score_delta": float(acceptance.get("average_score_delta", 0) or 0),
            }
        ledger_entries.append(
            {
                "experiment_name": experiment_name,
                "artifact": path.name,
                "recommendation": recommendation,
                "next_action": next_action,
                "pilot_scope": pilot_scope,
                "confidence_level": confidence_level,
                "observation_window": observation_window,
                "business_risk_label": business_risk_label,
                "focus": focus,
                "reader_acceptance": reader_acceptance,
            }
        )
        if recommendation:
            session_recommendations.append(recommendation)
        if business_risk_label:
            session_risk_labels.append(business_risk_label)
        if next_action:
            session_next_actions.append(next_action)
        if focus:
            session_focuses.append(focus)

    if all(item == "promote" for item in session_recommendations) and session_recommendations:
        promotion_verdict = "promote"
    elif any(item == "de-risk" for item in session_recommendations):
        promotion_verdict = "de-risk"
    elif any(item == "pilot" for item in session_recommendations):
        promotion_verdict = "pilot"
    else:
        promotion_verdict = "hold"

    if any(item == "high-risk" for item in session_risk_labels):
        risk_register = "high-risk"
    elif any(item == "guarded" for item in session_risk_labels):
        risk_register = "guarded"
    else:
        risk_register = "controlled"

    session_ship_decision = (
        "ship-ready" if promotion_verdict == "promote" and risk_register == "controlled" else "needs-review"
    )
    session_ready_queue = session_next_actions[:2] if session_ship_decision == "ship-ready" else []
    session_blockers: list[str] = []
    if risk_register == "high-risk":
        session_blockers.append("high-risk experiments still present")
    if promotion_verdict == "hold":
        session_blockers.append("insufficient positive evidence across session")
    session_blocked_queue = session_blockers[:2]
    session_escalation_path = [
        "writer-operator -> continuity-reviewer",
        "continuity-reviewer -> reader-feedback-owner",
    ]
    if risk_register in {"guarded", "high-risk"}:
        session_escalation_path.append("reader-feedback-owner -> risk-approver")
    if session_ship_decision == "needs-review":
        session_escalation_path.append("risk-approver -> business-owner")
    session_recovery_plan = [
        "若 reader_acceptance 转负，回退到上一版 steering 组合",
        "若 risk_register 升级，切换到 de-risk lane 并压缩 pilot_scope",
    ]
    session_required_review = ["session operator review"]
    if risk_register in {"guarded", "high-risk"}:
        session_required_review.append("risk approver review")
    session_owner_handoff = [
        "writer-operator -> continuity-reviewer",
        "continuity-reviewer -> reader-feedback-owner",
    ]
    if risk_register in {"guarded", "high-risk"}:
        session_owner_handoff.append("reader-feedback-owner -> risk-approver")
    session_priority_queue = session_next_actions[:3] if session_next_actions else ["补更多证据后再推进。"]
    session_lane_status = (
        "expansion-lane"
        if promotion_verdict == "promote"
        else "risk-mitigation-lane"
        if promotion_verdict == "de-risk"
        else "pilot-lane"
        if promotion_verdict == "pilot"
        else "evidence-lane"
    )
    session_release_readiness = (
        "ready-for-managed-pilot"
        if session_ship_decision == "ship-ready"
        else "blocked-pending-review"
    )
    session_execution_mode = (
        "scale"
        if session_ship_decision == "ship-ready" and promotion_verdict == "promote"
        else "stabilize"
        if promotion_verdict == "de-risk"
        else "pilot"
    )
    session_action_window = "next-5-8-chapters" if session_execution_mode == "scale" else "next-2-4-chapters"
    session_recovery_owner = (
        "risk-approver"
        if risk_register in {"guarded", "high-risk"}
        else "writer-operator"
    )
    session_command_brief = [
        f"当前 lane: {session_lane_status}",
        f"当前 ship decision: {session_ship_decision}",
        f"优先动作: {session_priority_queue[0]}",
    ]
    session_governor_mode = (
        "guarded-scale"
        if session_ship_decision == "ship-ready"
        else "risk-first"
        if risk_register in {"guarded", "high-risk"}
        else "evidence-first"
    )
    session_runtime_contract = (
        f"mode={session_execution_mode} | readiness={session_release_readiness} | lane={session_lane_status}"
    )
    session_state_snapshot = [
        f"promotion_verdict={promotion_verdict}",
        f"risk_register={risk_register}",
        f"ship_decision={session_ship_decision}",
    ]
    session_control_loop = {
        "entry_criteria": [
            "至少存在 1 个 innovation experiment artifact",
            "baseline_vs_steering 与 reader_sim_acceptance evidence 已生成",
        ],
        "guard_conditions": [
            "risk_register 不能为 high-risk 才允许进入 ship-ready",
            "reader_acceptance_not_improved 时禁止进入 scale 模式",
        ],
        "state_machine": [
            "evidence-lane -> pilot-lane",
            "pilot-lane -> expansion-lane",
            "pilot-lane -> risk-mitigation-lane",
            "risk-mitigation-lane -> pilot-lane",
        ],
        "allowed_transitions": [
            "hold -> pilot",
            "pilot -> promote",
            "pilot -> de-risk",
            "de-risk -> pilot",
        ],
        "auto_actions": [
            f"根据 {promotion_verdict} 自动选择 {session_lane_status}",
            f"根据 risk_register={risk_register} 自动分配 recovery owner={session_recovery_owner}",
        ],
        "manual_overrides": [
            "允许 business-owner 人工改写 promotion_verdict",
            "允许 risk-approver 人工冻结扩区或切回 de-risk lane",
        ],
    }
    session_queue_registry = {
        "priority_queue": session_priority_queue,
        "ready_queue": session_ready_queue,
        "blocked_queue": session_blocked_queue,
        "required_review": session_required_review,
        "owner_handoff": session_owner_handoff,
        "escalation_path": session_escalation_path,
        "recovery_plan": session_recovery_plan,
    }
    session_execution_registry = {
        "lane_status": session_lane_status,
        "release_readiness": session_release_readiness,
        "execution_mode": session_execution_mode,
        "action_window": session_action_window,
        "recovery_owner": session_recovery_owner,
        "command_brief": session_command_brief,
    }
    session_governance_registry = {
        "governor_mode": session_governor_mode,
        "decision_bus": [
            "promotion_verdict -> session_ship_decision",
            "risk_register -> required_review",
            "session_blockers -> escalation_path",
        ],
        "policy_versions": ["innovation-policy.v1", "session-control.v1"],
        "review_quorum": ["writer-operator", "continuity-reviewer", "reader-feedback-owner"],
        "authority_map": session_escalation_path,
    }
    session_digest_registry = {
        "runtime_contract": session_runtime_contract,
        "state_snapshot": session_state_snapshot,
        "control_summary": [
            f"ship={session_ship_decision}",
            f"lane={session_lane_status}",
            f"risk={risk_register}",
            f"queue={len(session_priority_queue)}",
        ],
        "operating_system_verdict": [
            f"runtime={session_execution_mode}",
            f"authority={session_ship_decision}",
            f"governor={session_governor_mode}",
            f"risk={risk_register}",
        ],
        "os_control_digest": [
            f"backbone={len(session_escalation_path)}",
            f"queue={len(session_priority_queue)}",
            f"review={len(session_required_review)}",
        ],
    }
    session_live_ops_board = {
        "promotion_verdict": promotion_verdict,
        "risk_register": risk_register,
        "session_ship_decision": session_ship_decision,
        "primary_focus": session_focuses[0] if session_focuses else "",
        "focuses": session_focuses[:3],
    }
    session_action_backlog: list[dict[str, object]] = []
    for index, entry in enumerate(ledger_entries, start=1):
        recommendation = str(entry.get("recommendation", "")).strip()
        business_risk_label = str(entry.get("business_risk_label", "")).strip()
        if business_risk_label == "high-risk":
            status = "blocked"
            owner = "risk-approver"
        elif recommendation in {"de-risk", "pilot"} or business_risk_label == "guarded":
            status = "review"
            owner = "continuity-reviewer"
        else:
            status = "ready"
            owner = "writer-operator"
        target_lane = (
            "expansion-lane"
            if recommendation == "promote"
            else "risk-mitigation-lane"
            if recommendation == "de-risk"
            else "pilot-lane"
            if recommendation == "pilot"
            else "evidence-lane"
        )
        unblock_conditions: list[str] = []
        if status == "blocked":
            unblock_conditions.append("risk approver 完成高风险复核")
        elif status == "review":
            unblock_conditions.append("补齐 reader acceptance / continuity evidence")
        session_action_backlog.append(
            {
                "ticket_id": f"exp-{index:02d}",
                "experiment_name": entry.get("experiment_name", ""),
                "status": status,
                "owner": owner,
                "target_lane": target_lane,
                "next_action": entry.get("next_action", ""),
                "checkpoint": f"{entry.get('experiment_name', '')}:{recommendation or 'observe'}",
                "unblock_conditions": unblock_conditions,
            }
        )
    if promotion_verdict == "promote" and risk_register == "controlled":
        session_transition_queue = [
            {
                "from": "pilot-lane",
                "to": "expansion-lane",
                "trigger": "promotion_verdict=promote and risk_register=controlled",
                "owner": "writer-operator",
            }
        ]
    elif promotion_verdict == "de-risk":
        session_transition_queue = [
            {
                "from": "pilot-lane",
                "to": "risk-mitigation-lane",
                "trigger": "promotion_verdict=de-risk",
                "owner": "risk-approver",
            }
        ]
    else:
        session_transition_queue = [
            {
                "from": "evidence-lane",
                "to": "pilot-lane",
                "trigger": "reader acceptance improves and blockers clear",
                "owner": "continuity-reviewer",
            }
        ]
    session_checkpoint_mutations = [
        {
            "field": "promotion_verdict",
            "value": promotion_verdict,
            "reason": "聚合 experiment_decision_note.recommendation",
        },
        {
            "field": "risk_register",
            "value": risk_register,
            "reason": "聚合 business_risk_label",
        },
        {
            "field": "session_ship_decision",
            "value": session_ship_decision,
            "reason": "由 promotion_verdict + risk_register 推导",
        },
        {
            "field": "session_recovery_owner",
            "value": session_recovery_owner,
            "reason": "根据 guarded/high-risk 状态自动选择",
        },
    ]
    session_operator_contract = {
        "contract_version": "writer-imitate-operator-surface.v1",
        "status": {
            "promotion_verdict": promotion_verdict,
            "risk_register": risk_register,
            "session_ship_decision": session_ship_decision,
            "session_lane_status": session_lane_status,
            "session_execution_mode": session_execution_mode,
            "session_release_readiness": session_release_readiness,
        },
        "queues": {
            "priority_queue": session_priority_queue,
            "ready_queue": session_ready_queue,
            "blocked_queue": session_blocked_queue,
        },
        "owners": {
            "session_recovery_owner": session_recovery_owner,
            "session_required_review": session_required_review,
            "session_escalation_path": session_escalation_path,
            "session_owner_handoff": session_owner_handoff,
        },
        "actions": {
            "session_action_backlog_count": len(session_action_backlog),
            "session_transition_queue": session_transition_queue,
            "session_checkpoint_mutations": session_checkpoint_mutations,
        },
        "summary": session_live_ops_board,
    }
    session_primary_verdicts = {
        "promotion_verdict": promotion_verdict,
        "runtime_verdict": f"{session_execution_mode}:{session_ship_decision}:{risk_register}",
        "control_verdict": f"{session_governor_mode}:{session_lane_status}",
        "final_verdict": f"{session_ship_decision}:{session_release_readiness}",
    }
    session_primary_digests = {
        "runtime_contract": session_runtime_contract,
        "control_summary": f"ship={session_ship_decision};lane={session_lane_status};risk={risk_register}",
        "governance_checksum": f"checksum={len(session_escalation_path)}",
        "operating_digest": f"ready={len(session_ready_queue)};blocked={len(session_blocked_queue)}",
    }
    session_primary_contract_hints = {
        "preferred_verdict_source": "session_primary_verdicts",
        "preferred_digest_source": "session_primary_digests",
        "legacy_verdict_fields": [
            "session_control_verdict",
            "session_runtime_verdict",
            "session_final_control_verdict",
            "session_final_runtime_verdict",
            "session_operating_system_verdict",
        ],
        "legacy_digest_fields": [
            "session_governance_checksum",
            "session_governance_checksum_v2",
            "session_os_control_digest",
            "session_control_summary",
            "session_operating_checksum",
        ],
        "migration_status": "compatibility-layer-active",
    }
    session_legacy_contract_layer = {
        "contract_version": "writer-imitate-legacy-contract-layer.v1",
        "legacy_verdict_fields": session_primary_contract_hints["legacy_verdict_fields"],
        "legacy_digest_fields": session_primary_contract_hints["legacy_digest_fields"],
        "legacy_verdict_count": len(session_primary_contract_hints["legacy_verdict_fields"]),
        "legacy_digest_count": len(session_primary_contract_hints["legacy_digest_fields"]),
        "status": "compatibility-layer-active",
    }
    session_legacy_retirement_readiness = {
        "contract_version": "writer-imitate-legacy-retirement-readiness.v1",
        "status": "not-ready",
        "required_conditions": [
            "downstream consumers switched to session_primary_verdicts",
            "downstream consumers switched to session_primary_digests",
            "legacy contract surface reviewed by operators",
            "primary-first display policy validated in production-like workflow",
        ],
        "blocking_reasons": [
            "legacy verdict fields still exposed for compatibility",
            "legacy digest fields still exposed for compatibility",
        ],
    }
    session_legacy_retirement_plan = {
        "contract_version": "writer-imitate-legacy-retirement-plan.v1",
        "phase": "pre-retirement",
        "pilot_candidates": [
            "session_governance_checksum_v2",
            "session_operating_checksum",
        ],
        "second_wave_candidates": [
            "session_control_verdict",
            "session_runtime_verdict",
            "session_operating_system_verdict",
        ],
        "retirement_order": [
            "extra digest/checksum variants",
            "overlapping verdict variants",
            "deep legacy compatibility summary fields",
        ],
        "safety_rules": [
            "do not retire any legacy field before primary consumer migration is verified",
            "keep legacy-contract-surface updated while retirement is incomplete",
            "retire one family slice at a time with regression evidence",
        ],
    }
    session_legacy_retirement_pilot_wave = {
        "contract_version": "writer-imitate-legacy-retirement-pilot-wave.v1",
        "status": "planned-not-executed",
        "wave_id": "legacy-retirement-wave-01",
        "target_fields": [
            "session_governance_checksum_v2",
            "session_operating_checksum",
        ],
        "target_family": "extra digest/checksum variants",
        "rollback_rule": "restore legacy fields immediately if downstream consumer mismatch appears",
        "evidence_required": [
            "primary digest consumers confirmed",
            "legacy surface remains complete",
            "targeted regression suite passes",
        ],
    }
    session_control_surface_entrypoints = {
        "primary_operator_entrypoint_json": "writer-imitate-operator-surface.json",
        "primary_operator_entrypoint_markdown": "writer-imitate-operator-surface.md",
        "legacy_operator_entrypoint_json": "writer-imitate-legacy-contract-surface.json",
        "legacy_operator_entrypoint_markdown": "writer-imitate-legacy-contract-surface.md",
        "legacy_retirement_preview_json": "writer-imitate-legacy-retirement-preview.json",
        "legacy_retirement_preview_markdown": "writer-imitate-legacy-retirement-preview.md",
        "live_control_state_json": "writer-imitate-live-control-state.json",
        "live_control_state_markdown": "writer-imitate-live-control-state.md",
        "live_mutation_preview_json": "writer-imitate-live-mutation-preview.json",
        "live_mutation_preview_markdown": "writer-imitate-live-mutation-preview.md",
        "live_validation_state_json": "writer-imitate-live-validation-state.json",
        "live_validation_state_markdown": "writer-imitate-live-validation-state.md",
        "external_runtime_executor_readiness_json": "writer-imitate-external-runtime-executor-readiness.json",
        "external_runtime_executor_readiness_markdown": "writer-imitate-external-runtime-executor-readiness.md",
        "external_runtime_executor_preview_json": "writer-imitate-external-runtime-executor-preview.json",
        "external_runtime_executor_preview_markdown": "writer-imitate-external-runtime-executor-preview.md",
        "entrypoint_roles": {
            "primary_operator_entrypoint": "default-operator-home",
            "legacy_operator_entrypoint": "compatibility-governance-surface",
            "legacy_retirement_preview": "retirement-preview-surface",
            "live_control_state": "preview-to-live-bridge-surface",
            "live_mutation_preview": "live-mutation-review-surface",
            "live_validation_state": "local-validation-bridge-surface",
            "external_runtime_executor_readiness": "runtime-executor-gate-surface",
            "external_runtime_executor_preview": "runtime-executor-review-surface",
        },
        "preferred_first_layer_sections": [
            "session_primary_verdicts",
            "session_primary_digests",
            "session_operator_contract",
        ],
        "secondary_sections": [
            "session_primary_contract_hints",
            "session_legacy_contract_layer",
        ],
        "display_policy": "primary-first-legacy-secondary",
    }

    return {
        "contract_version": "writer-imitate-session-state.v3",
        "output_dir": str(output_dir),
        "experiment_count": len(ledger_entries),
        "promotion_verdict": promotion_verdict,
        "risk_register": risk_register,
        "session_ship_decision": session_ship_decision,
        "session_ready_queue": session_ready_queue,
        "session_blocked_queue": session_blocked_queue,
        "session_escalation_path": session_escalation_path,
        "session_recovery_plan": session_recovery_plan,
        "session_focuses": session_focuses[:3],
        "session_control_loop": session_control_loop,
        "session_queue_registry": session_queue_registry,
        "session_execution_registry": session_execution_registry,
        "session_governance_registry": session_governance_registry,
        "session_digest_registry": session_digest_registry,
        "session_live_ops_board": session_live_ops_board,
        "session_action_backlog": session_action_backlog,
        "session_transition_queue": session_transition_queue,
        "session_checkpoint_mutations": session_checkpoint_mutations,
        "session_operator_contract": session_operator_contract,
        "session_primary_verdicts": session_primary_verdicts,
        "session_primary_digests": session_primary_digests,
        "session_primary_contract_hints": session_primary_contract_hints,
        "session_legacy_contract_layer": session_legacy_contract_layer,
        "session_legacy_retirement_readiness": session_legacy_retirement_readiness,
        "session_legacy_retirement_plan": session_legacy_retirement_plan,
        "session_legacy_retirement_pilot_wave": session_legacy_retirement_pilot_wave,
        "session_control_surface_entrypoints": session_control_surface_entrypoints,
        "experiments": ledger_entries,
    }


def _build_writer_output_action_queue(output_dir: Path) -> dict[str, object]:
    session_state = _build_writer_output_session_state(output_dir)
    backlog_obj = session_state.get("session_action_backlog", [])
    backlog = backlog_obj if isinstance(backlog_obj, list) else []
    transition_queue_obj = session_state.get("session_transition_queue", [])
    transition_queue = transition_queue_obj if isinstance(transition_queue_obj, list) else []
    checkpoint_mutations_obj = session_state.get("session_checkpoint_mutations", [])
    checkpoint_mutations = checkpoint_mutations_obj if isinstance(checkpoint_mutations_obj, list) else []
    ready_items = [
        item for item in backlog if isinstance(item, dict) and str(item.get("status", "")).strip() == "ready"
    ]
    review_items = [
        item for item in backlog if isinstance(item, dict) and str(item.get("status", "")).strip() == "review"
    ]
    blocked_items = [
        item for item in backlog if isinstance(item, dict) and str(item.get("status", "")).strip() == "blocked"
    ]
    primary_verdicts = session_state.get("session_primary_verdicts", {})
    primary_digests = session_state.get("session_primary_digests", {})
    return {
        "contract_version": "writer-imitate-action-queue.v1",
        "primary_operator_entrypoint": "writer-imitate-operator-surface.json",
        "legacy_operator_entrypoint": "writer-imitate-legacy-contract-surface.json",
        "promotion_verdict": session_state.get("promotion_verdict", ""),
        "risk_register": session_state.get("risk_register", ""),
        "session_ship_decision": session_state.get("session_ship_decision", ""),
        "session_operator_contract": session_state.get("session_operator_contract", {}),
        "session_primary_verdicts": primary_verdicts if isinstance(primary_verdicts, dict) else {},
        "session_primary_digests": primary_digests if isinstance(primary_digests, dict) else {},
        "session_primary_contract_hints": session_state.get("session_primary_contract_hints", {}),
        "session_legacy_contract_layer": session_state.get("session_legacy_contract_layer", {}),
        "action_backlog": backlog,
        "ready_items": ready_items,
        "review_items": review_items,
        "blocked_items": blocked_items,
        "transition_queue": transition_queue,
        "checkpoint_mutations": checkpoint_mutations,
        "execution_registry": session_state.get("session_execution_registry", {}),
        "governance_registry": session_state.get("session_governance_registry", {}),
        "live_ops_board": session_state.get("session_live_ops_board", {}),
    }


def _build_writer_output_operator_surface(output_dir: Path) -> dict[str, object]:
    session_state = _build_writer_output_session_state(output_dir)
    operator_contract_obj = session_state.get("session_operator_contract", {})
    operator_contract = operator_contract_obj if isinstance(operator_contract_obj, dict) else {}
    primary_verdicts_obj = session_state.get("session_primary_verdicts", {})
    primary_verdicts = primary_verdicts_obj if isinstance(primary_verdicts_obj, dict) else {}
    primary_digests_obj = session_state.get("session_primary_digests", {})
    primary_digests = primary_digests_obj if isinstance(primary_digests_obj, dict) else {}
    primary_hints_obj = session_state.get("session_primary_contract_hints", {})
    primary_hints = primary_hints_obj if isinstance(primary_hints_obj, dict) else {}
    legacy_layer_obj = session_state.get("session_legacy_contract_layer", {})
    legacy_layer = legacy_layer_obj if isinstance(legacy_layer_obj, dict) else {}
    retirement_readiness_obj = session_state.get("session_legacy_retirement_readiness", {})
    retirement_readiness = retirement_readiness_obj if isinstance(retirement_readiness_obj, dict) else {}
    retirement_plan_obj = session_state.get("session_legacy_retirement_plan", {})
    retirement_plan = retirement_plan_obj if isinstance(retirement_plan_obj, dict) else {}
    retirement_pilot_wave_obj = session_state.get("session_legacy_retirement_pilot_wave", {})
    retirement_pilot_wave = retirement_pilot_wave_obj if isinstance(retirement_pilot_wave_obj, dict) else {}
    entrypoints_obj = session_state.get("session_control_surface_entrypoints", {})
    entrypoints = entrypoints_obj if isinstance(entrypoints_obj, dict) else {}
    return {
        "contract_version": "writer-imitate-operator-surface.v1",
        "primary_operator_entrypoint": "writer-imitate-operator-surface.json",
        "legacy_operator_entrypoint": "writer-imitate-legacy-contract-surface.json",
        "session_operator_contract": operator_contract,
        "session_primary_verdicts": primary_verdicts,
        "session_primary_digests": primary_digests,
        "session_primary_contract_hints": primary_hints,
        "session_legacy_contract_layer": legacy_layer,
        "session_legacy_retirement_readiness": retirement_readiness,
        "session_legacy_retirement_plan": retirement_plan,
        "session_legacy_retirement_pilot_wave": retirement_pilot_wave,
        "session_control_surface_entrypoints": entrypoints,
        "promotion_verdict": session_state.get("promotion_verdict", ""),
        "risk_register": session_state.get("risk_register", ""),
        "session_ship_decision": session_state.get("session_ship_decision", ""),
    }


def _append_operator_contract_lines(
    lines: list[str],
    operator_contract: object,
    *,
    heading: str = "## Operator-Facing Stable Contract",
    include_queues: bool = False,
    include_actions: bool = False,
    compact_mode: str = "default",
) -> None:
    if not isinstance(operator_contract, dict):
        return
    status = operator_contract.get("status", {})
    queues = operator_contract.get("queues", {})
    owners = operator_contract.get("owners", {})
    actions = operator_contract.get("actions", {})
    if not isinstance(status, dict) or not isinstance(owners, dict):
        return

    lines.append(f"\n{heading}")
    if compact_mode == "default":
        lines.append(
            f"- status: lane={status.get('session_lane_status', '')} | "
            f"mode={status.get('session_execution_mode', '')} | "
            f"ship={status.get('session_ship_decision', '')} | risk={status.get('risk_register', '')}"
        )
        lines.append(
            f"- owner: recovery={owners.get('session_recovery_owner', '')} | "
            f"readiness={status.get('session_release_readiness', '')}"
        )
    elif compact_mode == "readiness":
        lines.append(
            f"- status: lane={status.get('session_lane_status', '')} | "
            f"mode={status.get('session_execution_mode', '')} | "
            f"readiness={status.get('session_release_readiness', '')}"
        )
        lines.append(
            f"- owner: recovery={owners.get('session_recovery_owner', '')} | "
            f"ship={status.get('session_ship_decision', '')}"
        )
    if include_queues and isinstance(queues, dict):
        lines.append(
            f"- queues: priority={len(queues.get('priority_queue', [])) if isinstance(queues.get('priority_queue', []), list) else 0} | "
            f"ready={len(queues.get('ready_queue', [])) if isinstance(queues.get('ready_queue', []), list) else 0} | "
            f"blocked={len(queues.get('blocked_queue', [])) if isinstance(queues.get('blocked_queue', []), list) else 0}"
        )
    if include_actions and isinstance(actions, dict):
        lines.append(
            f"- actions: backlog={actions.get('session_action_backlog_count', 0)} | "
            f"transitions={len(actions.get('session_transition_queue', [])) if isinstance(actions.get('session_transition_queue', []), list) else 0} | "
            f"checkpoints={len(actions.get('session_checkpoint_mutations', [])) if isinstance(actions.get('session_checkpoint_mutations', []), list) else 0}"
        )


def _append_primary_surface_lines(lines: list[str], payload: dict[str, object]) -> None:
    primary_verdicts = payload.get("session_primary_verdicts", {})
    if isinstance(primary_verdicts, dict):
        lines.append("\n## Primary Verdicts")
        lines.append(f"- promotion_verdict: {primary_verdicts.get('promotion_verdict', '')}")
        lines.append(f"- runtime_verdict: {primary_verdicts.get('runtime_verdict', '')}")
        lines.append(f"- control_verdict: {primary_verdicts.get('control_verdict', '')}")
        lines.append(f"- final_verdict: {primary_verdicts.get('final_verdict', '')}")
    primary_digests = payload.get("session_primary_digests", {})
    if isinstance(primary_digests, dict):
        lines.append("\n## Primary Digests")
        lines.append(f"- runtime_contract: {primary_digests.get('runtime_contract', '')}")
        lines.append(f"- control_summary: {primary_digests.get('control_summary', '')}")
        lines.append(f"- governance_checksum: {primary_digests.get('governance_checksum', '')}")
        lines.append(f"- operating_digest: {primary_digests.get('operating_digest', '')}")
    primary_hints = payload.get("session_primary_contract_hints", {})
    if isinstance(primary_hints, dict):
        lines.append("\n## Primary Contract Migration Hints")
        lines.append(f"- preferred_verdict_source: {primary_hints.get('preferred_verdict_source', '')}")
        lines.append(f"- preferred_digest_source: {primary_hints.get('preferred_digest_source', '')}")
        lines.append(f"- migration_status: {primary_hints.get('migration_status', '')}")
        legacy_verdict_fields = primary_hints.get("legacy_verdict_fields", [])
        legacy_digest_fields = primary_hints.get("legacy_digest_fields", [])
        legacy_verdict_text = (
            "；".join(str(x) for x in legacy_verdict_fields)
            if isinstance(legacy_verdict_fields, list)
            else ""
        )
        legacy_digest_text = (
            "；".join(str(x) for x in legacy_digest_fields)
            if isinstance(legacy_digest_fields, list)
            else ""
        )
        lines.append(f"- legacy_verdict_fields: {legacy_verdict_text}")
        lines.append(f"- legacy_digest_fields: {legacy_digest_text}")
        lines.append("- compatibility_note: legacy verdict/digest fields remain available but are no longer the preferred first-layer entrypoint")
    legacy_layer = payload.get("session_legacy_contract_layer", {})
    if isinstance(legacy_layer, dict):
        lines.append("\n## Legacy Contract Layer")
        lines.append(f"- status: {legacy_layer.get('status', '')}")
        lines.append(f"- legacy_verdict_count: {legacy_layer.get('legacy_verdict_count', 0)}")
        lines.append(f"- legacy_digest_count: {legacy_layer.get('legacy_digest_count', 0)}")
    retirement_readiness = payload.get("session_legacy_retirement_readiness", {})
    if isinstance(retirement_readiness, dict):
        lines.append("\n## Legacy Retirement Readiness")
        lines.append(f"- status: {retirement_readiness.get('status', '')}")
        required_conditions = retirement_readiness.get("required_conditions", [])
        blocking_reasons = retirement_readiness.get("blocking_reasons", [])
        required_text = "；".join(str(x) for x in required_conditions) if isinstance(required_conditions, list) else ""
        blocking_text = "；".join(str(x) for x in blocking_reasons) if isinstance(blocking_reasons, list) else ""
        lines.append(f"- required_conditions: {required_text}")
        lines.append(f"- blocking_reasons: {blocking_text}")
    retirement_plan = payload.get("session_legacy_retirement_plan", {})
    if isinstance(retirement_plan, dict):
        lines.append("\n## Legacy Retirement Plan")
        lines.append(f"- phase: {retirement_plan.get('phase', '')}")
        pilot = retirement_plan.get("pilot_candidates", [])
        second_wave = retirement_plan.get("second_wave_candidates", [])
        order = retirement_plan.get("retirement_order", [])
        pilot_text = "；".join(str(x) for x in pilot) if isinstance(pilot, list) else ""
        second_wave_text = "；".join(str(x) for x in second_wave) if isinstance(second_wave, list) else ""
        order_text = "；".join(str(x) for x in order) if isinstance(order, list) else ""
        lines.append(f"- pilot_candidates: {pilot_text}")
        lines.append(f"- second_wave_candidates: {second_wave_text}")
        lines.append(f"- retirement_order: {order_text}")
    retirement_pilot_wave = payload.get("session_legacy_retirement_pilot_wave", {})
    if isinstance(retirement_pilot_wave, dict):
        lines.append("\n## Legacy Retirement Pilot Wave")
        lines.append(f"- status: {retirement_pilot_wave.get('status', '')}")
        lines.append(f"- wave_id: {retirement_pilot_wave.get('wave_id', '')}")
        lines.append(f"- target_family: {retirement_pilot_wave.get('target_family', '')}")
        targets = retirement_pilot_wave.get("target_fields", [])
        target_text = "；".join(str(x) for x in targets) if isinstance(targets, list) else ""
        lines.append(f"- target_fields: {target_text}")


def _writer_output_operator_surface_markdown(output_dir: Path) -> str:
    payload = _build_writer_output_operator_surface(output_dir)
    lines = ["# Writer Imitation Operator Surface"]
    lines.append(f"\n- contract_version: {payload.get('contract_version', '')}")
    lines.append("- legacy_operator_entrypoint: writer-imitate-legacy-contract-surface.md")
    entrypoints = payload.get("session_control_surface_entrypoints", {})
    if isinstance(entrypoints, dict):
        lines.append(f"- primary_operator_entrypoint: {entrypoints.get('primary_operator_entrypoint_markdown', '')}")
        lines.append(f"- legacy_operator_entrypoint: {entrypoints.get('legacy_operator_entrypoint_markdown', '')}")
        lines.append(f"- legacy_retirement_preview: {entrypoints.get('legacy_retirement_preview_markdown', '')}")
        lines.append(f"- live_control_state: {entrypoints.get('live_control_state_markdown', '')}")
        lines.append(f"- live_mutation_preview: {entrypoints.get('live_mutation_preview_markdown', '')}")
        lines.append(f"- live_validation_state: {entrypoints.get('live_validation_state_markdown', '')}")
        lines.append(f"- external_runtime_executor_readiness: {entrypoints.get('external_runtime_executor_readiness_markdown', '')}")
        lines.append(f"- external_runtime_executor_preview: {entrypoints.get('external_runtime_executor_preview_markdown', '')}")
        entrypoint_roles = entrypoints.get("entrypoint_roles", {})
        if isinstance(entrypoint_roles, dict):
            lines.append(f"- primary_operator_role: {entrypoint_roles.get('primary_operator_entrypoint', '')}")
            lines.append(f"- legacy_operator_role: {entrypoint_roles.get('legacy_operator_entrypoint', '')}")
            lines.append(f"- legacy_retirement_preview_role: {entrypoint_roles.get('legacy_retirement_preview', '')}")
            lines.append(f"- live_control_state_role: {entrypoint_roles.get('live_control_state', '')}")
            lines.append(f"- live_mutation_preview_role: {entrypoint_roles.get('live_mutation_preview', '')}")
            lines.append(f"- live_validation_state_role: {entrypoint_roles.get('live_validation_state', '')}")
            lines.append(f"- external_runtime_executor_readiness_role: {entrypoint_roles.get('external_runtime_executor_readiness', '')}")
            lines.append(f"- external_runtime_executor_preview_role: {entrypoint_roles.get('external_runtime_executor_preview', '')}")
        lines.append(f"- display_policy: {entrypoints.get('display_policy', '')}")
    lines.append(f"- promotion_verdict: {payload.get('promotion_verdict', '')}")
    lines.append(f"- risk_register: {payload.get('risk_register', '')}")
    lines.append(f"- session_ship_decision: {payload.get('session_ship_decision', '')}")
    _append_primary_surface_lines(lines, payload)
    _append_operator_contract_lines(
        lines,
        payload.get("session_operator_contract", {}),
        include_queues=True,
        include_actions=True,
    )
    return "\n".join(lines).strip() + "\n"


def _build_writer_output_legacy_contract_surface(output_dir: Path) -> dict[str, object]:
    session_state = _build_writer_output_session_state(output_dir)
    legacy_layer_obj = session_state.get("session_legacy_contract_layer", {})
    legacy_layer = legacy_layer_obj if isinstance(legacy_layer_obj, dict) else {}
    primary_hints_obj = session_state.get("session_primary_contract_hints", {})
    primary_hints = primary_hints_obj if isinstance(primary_hints_obj, dict) else {}
    retirement_readiness_obj = session_state.get("session_legacy_retirement_readiness", {})
    retirement_readiness = retirement_readiness_obj if isinstance(retirement_readiness_obj, dict) else {}
    retirement_plan_obj = session_state.get("session_legacy_retirement_plan", {})
    retirement_plan = retirement_plan_obj if isinstance(retirement_plan_obj, dict) else {}
    retirement_pilot_wave_obj = session_state.get("session_legacy_retirement_pilot_wave", {})
    retirement_pilot_wave = retirement_pilot_wave_obj if isinstance(retirement_pilot_wave_obj, dict) else {}
    entrypoints_obj = session_state.get("session_control_surface_entrypoints", {})
    entrypoints = entrypoints_obj if isinstance(entrypoints_obj, dict) else {}
    return {
        "contract_version": "writer-imitate-legacy-contract-surface.v1",
        "primary_operator_entrypoint": "writer-imitate-operator-surface.json",
        "legacy_operator_entrypoint": "writer-imitate-legacy-contract-surface.json",
        "session_legacy_contract_layer": legacy_layer,
        "session_primary_contract_hints": primary_hints,
        "session_legacy_retirement_readiness": retirement_readiness,
        "session_legacy_retirement_plan": retirement_plan,
        "session_legacy_retirement_pilot_wave": retirement_pilot_wave,
        "session_control_surface_entrypoints": entrypoints,
    }


def _writer_output_legacy_contract_surface_markdown(output_dir: Path) -> str:
    payload = _build_writer_output_legacy_contract_surface(output_dir)
    lines = ["# Writer Imitation Legacy Contract Surface"]
    lines.append(f"\n- contract_version: {payload.get('contract_version', '')}")
    entrypoints = payload.get("session_control_surface_entrypoints", {})
    if isinstance(entrypoints, dict):
        lines.append(f"- primary_operator_entrypoint: {entrypoints.get('primary_operator_entrypoint_markdown', '')}")
        lines.append(f"- legacy_operator_entrypoint: {entrypoints.get('legacy_operator_entrypoint_markdown', '')}")
        lines.append(f"- legacy_retirement_preview: {entrypoints.get('legacy_retirement_preview_markdown', '')}")
        lines.append(f"- live_mutation_preview: {entrypoints.get('live_mutation_preview_markdown', '')}")
        lines.append(f"- live_validation_state: {entrypoints.get('live_validation_state_markdown', '')}")
        lines.append(f"- external_runtime_executor_readiness: {entrypoints.get('external_runtime_executor_readiness_markdown', '')}")
        lines.append(f"- external_runtime_executor_preview: {entrypoints.get('external_runtime_executor_preview_markdown', '')}")
        entrypoint_roles = entrypoints.get("entrypoint_roles", {})
        if isinstance(entrypoint_roles, dict):
            lines.append(f"- primary_operator_role: {entrypoint_roles.get('primary_operator_entrypoint', '')}")
            lines.append(f"- legacy_operator_role: {entrypoint_roles.get('legacy_operator_entrypoint', '')}")
            lines.append(f"- legacy_retirement_preview_role: {entrypoint_roles.get('legacy_retirement_preview', '')}")
            lines.append(f"- live_control_state_role: {entrypoint_roles.get('live_control_state', '')}")
            lines.append(f"- live_mutation_preview_role: {entrypoint_roles.get('live_mutation_preview', '')}")
            lines.append(f"- live_validation_state_role: {entrypoint_roles.get('live_validation_state', '')}")
            lines.append(f"- external_runtime_executor_readiness_role: {entrypoint_roles.get('external_runtime_executor_readiness', '')}")
            lines.append(f"- external_runtime_executor_preview_role: {entrypoint_roles.get('external_runtime_executor_preview', '')}")
    _append_primary_surface_lines(lines, payload)
    retirement_readiness = payload.get("session_legacy_retirement_readiness", {})
    if isinstance(retirement_readiness, dict):
        lines.append("\n## Legacy Retirement Readiness")
        lines.append(f"- status: {retirement_readiness.get('status', '')}")
        required_conditions = retirement_readiness.get("required_conditions", [])
        blocking_reasons = retirement_readiness.get("blocking_reasons", [])
        required_text = "；".join(str(x) for x in required_conditions) if isinstance(required_conditions, list) else ""
        blocking_text = "；".join(str(x) for x in blocking_reasons) if isinstance(blocking_reasons, list) else ""
        lines.append(f"- required_conditions: {required_text}")
        lines.append(f"- blocking_reasons: {blocking_text}")
    retirement_plan = payload.get("session_legacy_retirement_plan", {})
    if isinstance(retirement_plan, dict):
        lines.append("\n## Legacy Retirement Plan")
        lines.append(f"- phase: {retirement_plan.get('phase', '')}")
        pilot = retirement_plan.get("pilot_candidates", [])
        second_wave = retirement_plan.get("second_wave_candidates", [])
        order = retirement_plan.get("retirement_order", [])
        pilot_text = "；".join(str(x) for x in pilot) if isinstance(pilot, list) else ""
        second_wave_text = "；".join(str(x) for x in second_wave) if isinstance(second_wave, list) else ""
        order_text = "；".join(str(x) for x in order) if isinstance(order, list) else ""
        lines.append(f"- pilot_candidates: {pilot_text}")
        lines.append(f"- second_wave_candidates: {second_wave_text}")
        lines.append(f"- retirement_order: {order_text}")
    retirement_pilot_wave = payload.get("session_legacy_retirement_pilot_wave", {})
    if isinstance(retirement_pilot_wave, dict):
        lines.append("\n## Legacy Retirement Pilot Wave")
        lines.append(f"- status: {retirement_pilot_wave.get('status', '')}")
        lines.append(f"- wave_id: {retirement_pilot_wave.get('wave_id', '')}")
        lines.append(f"- target_family: {retirement_pilot_wave.get('target_family', '')}")
        targets = retirement_pilot_wave.get("target_fields", [])
        target_text = "；".join(str(x) for x in targets) if isinstance(targets, list) else ""
        lines.append(f"- target_fields: {target_text}")
    return "\n".join(lines).strip() + "\n"


def _build_writer_output_legacy_retirement_preview(output_dir: Path) -> dict[str, object]:
    session_state = _build_writer_output_session_state(output_dir)
    pilot_wave_obj = session_state.get("session_legacy_retirement_pilot_wave", {})
    pilot_wave = pilot_wave_obj if isinstance(pilot_wave_obj, dict) else {}
    readiness_obj = session_state.get("session_legacy_retirement_readiness", {})
    readiness = readiness_obj if isinstance(readiness_obj, dict) else {}
    legacy_layer_obj = session_state.get("session_legacy_contract_layer", {})
    legacy_layer = legacy_layer_obj if isinstance(legacy_layer_obj, dict) else {}
    return {
        "contract_version": "writer-imitate-legacy-retirement-preview.v1",
        "primary_operator_entrypoint": "writer-imitate-operator-surface.json",
        "legacy_operator_entrypoint": "writer-imitate-legacy-contract-surface.json",
        "retirement_readiness": readiness,
        "retirement_pilot_wave": pilot_wave,
        "legacy_contract_layer": legacy_layer,
        "preview_status": "planned-not-executed",
        "projected_effect": {
            "legacy_verdict_count_after_wave": max(int(legacy_layer.get("legacy_verdict_count", 0) or 0), 0),
            "legacy_digest_count_after_wave": max(
                int(legacy_layer.get("legacy_digest_count", 0) or 0) - len(pilot_wave.get("target_fields", []))
                if isinstance(pilot_wave.get("target_fields", []), list)
                else int(legacy_layer.get("legacy_digest_count", 0) or 0),
                0,
            ),
            "requires_rollback_on_mismatch": True,
        },
    }


def _build_writer_output_control_surface_registry(output_dir: Path) -> dict[str, object]:
    session_state = _build_writer_output_session_state(output_dir)
    entrypoints_obj = session_state.get("session_control_surface_entrypoints", {})
    entrypoints = entrypoints_obj if isinstance(entrypoints_obj, dict) else {}
    operator_contract_obj = session_state.get("session_operator_contract", {})
    operator_contract = operator_contract_obj if isinstance(operator_contract_obj, dict) else {}
    return {
        "contract_version": "writer-imitate-control-surface-registry.v1",
        "session_control_surface_entrypoints": entrypoints,
        "session_operator_contract": operator_contract,
        "registry_status": "active",
    }


def _writer_output_control_surface_registry_markdown(output_dir: Path) -> str:
    payload = _build_writer_output_control_surface_registry(output_dir)
    lines = ["# Writer Imitation Control Surface Registry"]
    lines.append(f"\n- contract_version: {payload.get('contract_version', '')}")
    lines.append(f"- registry_status: {payload.get('registry_status', '')}")
    entrypoints = payload.get("session_control_surface_entrypoints", {})
    if isinstance(entrypoints, dict):
        lines.append("\n## EntryPoints")
        lines.append(f"- primary_operator_entrypoint: {entrypoints.get('primary_operator_entrypoint_markdown', '')}")
        lines.append(f"- legacy_operator_entrypoint: {entrypoints.get('legacy_operator_entrypoint_markdown', '')}")
        lines.append(f"- legacy_retirement_preview: {entrypoints.get('legacy_retirement_preview_markdown', '')}")
        lines.append(f"- live_control_state: {entrypoints.get('live_control_state_markdown', '')}")
        lines.append(f"- display_policy: {entrypoints.get('display_policy', '')}")
        roles = entrypoints.get("entrypoint_roles", {})
        if isinstance(roles, dict):
            lines.append("\n## EntryPoint Roles")
            lines.append(f"- primary_operator_entrypoint: {roles.get('primary_operator_entrypoint', '')}")
            lines.append(f"- legacy_operator_entrypoint: {roles.get('legacy_operator_entrypoint', '')}")
            lines.append(f"- legacy_retirement_preview: {roles.get('legacy_retirement_preview', '')}")
            lines.append(f"- live_control_state: {roles.get('live_control_state', '')}")
    operator_contract = payload.get("session_operator_contract", {})
    _append_operator_contract_lines(lines, operator_contract, include_queues=True, include_actions=True)
    return "\n".join(lines).strip() + "\n"


def _writer_output_legacy_retirement_preview_markdown(output_dir: Path) -> str:
    payload = _build_writer_output_legacy_retirement_preview(output_dir)
    lines = ["# Writer Imitation Legacy Retirement Preview"]
    lines.append(f"\n- contract_version: {payload.get('contract_version', '')}")
    lines.append("- primary_operator_entrypoint: writer-imitate-operator-surface.md")
    lines.append("- legacy_operator_entrypoint: writer-imitate-legacy-contract-surface.md")
    lines.append(f"- preview_status: {payload.get('preview_status', '')}")

    readiness = payload.get("retirement_readiness", {})
    if isinstance(readiness, dict):
        lines.append("\n## Retirement Readiness")
        lines.append(f"- status: {readiness.get('status', '')}")
        required_conditions = readiness.get("required_conditions", [])
        blocking_reasons = readiness.get("blocking_reasons", [])
        required_text = "；".join(str(x) for x in required_conditions) if isinstance(required_conditions, list) else ""
        blocking_text = "；".join(str(x) for x in blocking_reasons) if isinstance(blocking_reasons, list) else ""
        lines.append(f"- required_conditions: {required_text}")
        lines.append(f"- blocking_reasons: {blocking_text}")

    pilot_wave = payload.get("retirement_pilot_wave", {})
    if isinstance(pilot_wave, dict):
        lines.append("\n## Retirement Pilot Wave")
        lines.append(f"- wave_id: {pilot_wave.get('wave_id', '')}")
        lines.append(f"- status: {pilot_wave.get('status', '')}")
        lines.append(f"- target_family: {pilot_wave.get('target_family', '')}")
        targets = pilot_wave.get("target_fields", [])
        target_text = "；".join(str(x) for x in targets) if isinstance(targets, list) else ""
        lines.append(f"- target_fields: {target_text}")
        lines.append(f"- rollback_rule: {pilot_wave.get('rollback_rule', '')}")

    projected_effect = payload.get("projected_effect", {})
    if isinstance(projected_effect, dict):
        lines.append("\n## Projected Effect")
        lines.append(
            f"- legacy_verdict_count_after_wave: {projected_effect.get('legacy_verdict_count_after_wave', 0)}"
        )
        lines.append(
            f"- legacy_digest_count_after_wave: {projected_effect.get('legacy_digest_count_after_wave', 0)}"
        )
        lines.append(
            f"- requires_rollback_on_mismatch: {projected_effect.get('requires_rollback_on_mismatch', False)}"
        )

    return "\n".join(lines).strip() + "\n"


def _writer_output_action_queue_markdown(output_dir: Path) -> str:
    payload = _build_writer_output_action_queue(output_dir)
    lines = ["# Writer Imitation Action Queue"]
    lines.append(f"\n- contract_version: {payload.get('contract_version', '')}")
    lines.append("- primary_operator_entrypoint: writer-imitate-operator-surface.md")
    lines.append("- legacy_operator_entrypoint: writer-imitate-legacy-contract-surface.md")
    lines.append(f"- promotion_verdict: {payload.get('promotion_verdict', '')}")
    lines.append(f"- risk_register: {payload.get('risk_register', '')}")
    lines.append(f"- session_ship_decision: {payload.get('session_ship_decision', '')}")
    _append_primary_surface_lines(lines, payload)
    _append_operator_contract_lines(
        lines,
        payload.get("session_operator_contract", {}),
        include_queues=True,
        include_actions=True,
    )

    execution_registry = payload.get("execution_registry", {})
    if isinstance(execution_registry, dict):
        lines.append(
            "- execution_registry: "
            f"lane={execution_registry.get('lane_status', '')} | "
            f"mode={execution_registry.get('execution_mode', '')} | "
            f"window={execution_registry.get('action_window', '')} | "
            f"owner={execution_registry.get('recovery_owner', '')}"
        )

    lines.append("\n## Action Backlog")
    action_backlog = payload.get("action_backlog", [])
    for item in action_backlog if isinstance(action_backlog, list) else []:
        if not isinstance(item, dict):
            continue
        unblock = item.get("unblock_conditions", [])
        unblock_text = "；".join(str(x) for x in unblock) if isinstance(unblock, list) and unblock else "none"
        lines.append(
            f"- {item.get('ticket_id', '')}: status={item.get('status', '')} | owner={item.get('owner', '')} | "
            f"lane={item.get('target_lane', '')} | checkpoint={item.get('checkpoint', '')}"
        )
        lines.append(f"  - experiment_name: {item.get('experiment_name', '')}")
        lines.append(f"  - next_action: {item.get('next_action', '')}")
        lines.append(f"  - unblock_conditions: {unblock_text}")

    lines.append("\n## Transition Queue")
    transition_queue = payload.get("transition_queue", [])
    for item in transition_queue if isinstance(transition_queue, list) else []:
        if not isinstance(item, dict):
            continue
        lines.append(
            f"- {item.get('from', '')} -> {item.get('to', '')} | "
            f"trigger={item.get('trigger', '')} | owner={item.get('owner', '')}"
        )

    lines.append("\n## Checkpoint Mutations")
    checkpoint_mutations = payload.get("checkpoint_mutations", [])
    for item in checkpoint_mutations if isinstance(checkpoint_mutations, list) else []:
        if not isinstance(item, dict):
            continue
        lines.append(
            f"- {item.get('field', '')}: value={item.get('value', '')} | reason={item.get('reason', '')}"
        )

    governance_registry = payload.get("governance_registry", {})
    if isinstance(governance_registry, dict):
        review_quorum = governance_registry.get("review_quorum", [])
        quorum_text = "；".join(str(x) for x in review_quorum) if isinstance(review_quorum, list) else ""
        lines.append("\n## Governance Registry")
        lines.append(f"- governor_mode: {governance_registry.get('governor_mode', '')}")
        lines.append(f"- review_quorum: {quorum_text}")

    live_ops_board = payload.get("live_ops_board", {})
    if isinstance(live_ops_board, dict):
        focuses = live_ops_board.get("focuses", [])
        focus_text = "；".join(str(x) for x in focuses) if isinstance(focuses, list) else ""
        lines.append("\n## Live Ops Board")
        lines.append(f"- primary_focus: {live_ops_board.get('primary_focus', '')}")
        lines.append(f"- focuses: {focus_text}")

    return "\n".join(lines).strip() + "\n"


def _build_writer_output_execution_state(output_dir: Path) -> dict[str, object]:
    session_state = _build_writer_output_session_state(output_dir)
    action_queue = _build_writer_output_action_queue(output_dir)
    backlog_obj = action_queue.get("action_backlog", [])
    backlog = backlog_obj if isinstance(backlog_obj, list) else []
    transitions_obj = action_queue.get("transition_queue", [])
    transitions = transitions_obj if isinstance(transitions_obj, list) else []
    mutations_obj = action_queue.get("checkpoint_mutations", [])
    mutations = mutations_obj if isinstance(mutations_obj, list) else []

    execution_tickets: list[dict[str, object]] = []
    for item in backlog:
        if not isinstance(item, dict):
            continue
        status = str(item.get("status", "")).strip()
        phase = (
            "dispatch-ready"
            if status == "ready"
            else "review-gate"
            if status == "review"
            else "blocked-recovery"
        )
        execution_tickets.append(
            {
                "ticket_id": item.get("ticket_id", ""),
                "phase": phase,
                "status": status,
                "owner": item.get("owner", ""),
                "target_lane": item.get("target_lane", ""),
                "checkpoint": item.get("checkpoint", ""),
                "next_action": item.get("next_action", ""),
                "replayable": status != "blocked",
            }
        )

    ready_count = sum(1 for item in execution_tickets if str(item.get("status", "")).strip() == "ready")
    blocked_count = sum(1 for item in execution_tickets if str(item.get("status", "")).strip() == "blocked")
    review_count = sum(1 for item in execution_tickets if str(item.get("status", "")).strip() == "review")
    run_status = "blocked" if blocked_count else "active" if ready_count else "reviewing"
    replay_plan = [
        "读取 execution_tickets，优先挑选 replayable=true 且 status=ready 的 ticket",
        "按 transition_queue 的首项决定 lane 迁移方向",
        "按 checkpoint_mutations 顺序回写 promotion/risk/ship/recovery owner",
    ]
    execution_registry_obj = session_state.get("session_execution_registry", {})
    execution_registry = execution_registry_obj if isinstance(execution_registry_obj, dict) else {}
    recovery_cursor = {
        "blocked_ticket_ids": [
            str(item.get("ticket_id", ""))
            for item in execution_tickets
            if str(item.get("status", "")).strip() == "blocked"
        ],
        "review_ticket_ids": [
            str(item.get("ticket_id", ""))
            for item in execution_tickets
            if str(item.get("status", "")).strip() == "review"
        ],
        "recovery_owner": execution_registry.get("recovery_owner", ""),
    }
    checkpoint_log = [
        {
            "field": item.get("field", ""),
            "pending_value": item.get("value", ""),
            "applied": False,
            "reason": item.get("reason", ""),
        }
        for item in mutations
        if isinstance(item, dict)
    ]
    transition_history = [
        {
            "from": item.get("from", ""),
            "to": item.get("to", ""),
            "trigger": item.get("trigger", ""),
            "applied": False,
            "owner": item.get("owner", ""),
        }
        for item in transitions
        if isinstance(item, dict)
    ]
    return {
        "contract_version": "writer-imitate-execution-state.v1",
        "primary_operator_entrypoint": "writer-imitate-operator-surface.json",
        "legacy_operator_entrypoint": "writer-imitate-legacy-contract-surface.json",
        "run_status": run_status,
        "promotion_verdict": session_state.get("promotion_verdict", ""),
        "risk_register": session_state.get("risk_register", ""),
        "session_ship_decision": session_state.get("session_ship_decision", ""),
        "session_operator_contract": session_state.get("session_operator_contract", {}),
        "session_primary_verdicts": session_state.get("session_primary_verdicts", {}),
        "session_primary_digests": session_state.get("session_primary_digests", {}),
        "session_primary_contract_hints": session_state.get("session_primary_contract_hints", {}),
        "session_legacy_contract_layer": session_state.get("session_legacy_contract_layer", {}),
        "execution_ticket_count": len(execution_tickets),
        "ready_count": ready_count,
        "review_count": review_count,
        "blocked_count": blocked_count,
        "execution_tickets": execution_tickets,
        "transition_history": transition_history,
        "checkpoint_log": checkpoint_log,
        "replay_plan": replay_plan,
        "recovery_cursor": recovery_cursor,
        "live_ops_board": action_queue.get("live_ops_board", {}),
    }


def _writer_output_execution_state_markdown(output_dir: Path) -> str:
    payload = _build_writer_output_execution_state(output_dir)
    lines = ["# Writer Imitation Execution State"]
    lines.append(f"\n- contract_version: {payload.get('contract_version', '')}")
    lines.append("- primary_operator_entrypoint: writer-imitate-operator-surface.md")
    lines.append("- legacy_operator_entrypoint: writer-imitate-legacy-contract-surface.md")
    lines.append(f"- run_status: {payload.get('run_status', '')}")
    lines.append(f"- promotion_verdict: {payload.get('promotion_verdict', '')}")
    lines.append(f"- risk_register: {payload.get('risk_register', '')}")
    lines.append(f"- session_ship_decision: {payload.get('session_ship_decision', '')}")
    lines.append(
        f"- counts: ready={payload.get('ready_count', 0)} | review={payload.get('review_count', 0)} | blocked={payload.get('blocked_count', 0)}"
    )
    _append_primary_surface_lines(lines, payload)
    _append_operator_contract_lines(
        lines,
        payload.get("session_operator_contract", {}),
        compact_mode="readiness",
    )

    lines.append("\n## Execution Tickets")
    execution_tickets = payload.get("execution_tickets", [])
    for item in execution_tickets if isinstance(execution_tickets, list) else []:
        if not isinstance(item, dict):
            continue
        lines.append(
            f"- {item.get('ticket_id', '')}: phase={item.get('phase', '')} | status={item.get('status', '')} | "
            f"owner={item.get('owner', '')} | replayable={item.get('replayable', False)}"
        )
        lines.append(f"  - target_lane: {item.get('target_lane', '')}")
        lines.append(f"  - checkpoint: {item.get('checkpoint', '')}")
        lines.append(f"  - next_action: {item.get('next_action', '')}")

    lines.append("\n## Transition History")
    transition_history = payload.get("transition_history", [])
    for item in transition_history if isinstance(transition_history, list) else []:
        if not isinstance(item, dict):
            continue
        lines.append(
            f"- {item.get('from', '')} -> {item.get('to', '')} | trigger={item.get('trigger', '')} | "
            f"applied={item.get('applied', False)} | owner={item.get('owner', '')}"
        )

    lines.append("\n## Checkpoint Log")
    checkpoint_log = payload.get("checkpoint_log", [])
    for item in checkpoint_log if isinstance(checkpoint_log, list) else []:
        if not isinstance(item, dict):
            continue
        lines.append(
            f"- {item.get('field', '')}: pending_value={item.get('pending_value', '')} | "
            f"applied={item.get('applied', False)} | reason={item.get('reason', '')}"
        )

    lines.append("\n## Replay Plan")
    replay_plan = payload.get("replay_plan", [])
    for item in replay_plan if isinstance(replay_plan, list) else []:
        lines.append(f"- {item}")

    recovery_cursor = payload.get("recovery_cursor", {})
    if isinstance(recovery_cursor, dict):
        blocked_ids = recovery_cursor.get("blocked_ticket_ids", [])
        review_ids = recovery_cursor.get("review_ticket_ids", [])
        blocked_text = "；".join(str(x) for x in blocked_ids) if isinstance(blocked_ids, list) else ""
        review_text = "；".join(str(x) for x in review_ids) if isinstance(review_ids, list) else ""
        lines.append("\n## Recovery Cursor")
        lines.append(f"- recovery_owner: {recovery_cursor.get('recovery_owner', '')}")
        lines.append(f"- blocked_ticket_ids: {blocked_text}")
        lines.append(f"- review_ticket_ids: {review_text}")

    return "\n".join(lines).strip() + "\n"


def _build_writer_output_execution_replay(output_dir: Path) -> dict[str, object]:
    execution_state = _build_writer_output_execution_state(output_dir)
    tickets_obj = execution_state.get("execution_tickets", [])
    tickets = tickets_obj if isinstance(tickets_obj, list) else []
    transition_history_obj = execution_state.get("transition_history", [])
    transition_history = transition_history_obj if isinstance(transition_history_obj, list) else []
    checkpoint_log_obj = execution_state.get("checkpoint_log", [])
    checkpoint_log = checkpoint_log_obj if isinstance(checkpoint_log_obj, list) else []

    applied_ticket_ids: list[str] = []
    deferred_ticket_ids: list[str] = []
    blocked_ticket_ids: list[str] = []
    replay_results: list[dict[str, object]] = []
    for item in tickets:
        if not isinstance(item, dict):
            continue
        ticket_id = str(item.get("ticket_id", "")).strip()
        status = str(item.get("status", "")).strip()
        if status == "ready":
            applied_ticket_ids.append(ticket_id)
            replay_results.append(
                {
                    "ticket_id": ticket_id,
                    "result": "applied-preview",
                    "phase_after": "checkpoint-pending",
                    "owner": item.get("owner", ""),
                }
            )
        elif status == "review":
            deferred_ticket_ids.append(ticket_id)
            replay_results.append(
                {
                    "ticket_id": ticket_id,
                    "result": "deferred-review",
                    "phase_after": "review-gate",
                    "owner": item.get("owner", ""),
                }
            )
        else:
            blocked_ticket_ids.append(ticket_id)
            replay_results.append(
                {
                    "ticket_id": ticket_id,
                    "result": "blocked-recovery",
                    "phase_after": "blocked-recovery",
                    "owner": item.get("owner", ""),
                }
            )

    transition_preview = []
    for item in transition_history:
        if not isinstance(item, dict):
            continue
        transition_preview.append(
            {
                "from": item.get("from", ""),
                "to": item.get("to", ""),
                "trigger": item.get("trigger", ""),
                "owner": item.get("owner", ""),
                "would_apply": bool(applied_ticket_ids),
            }
        )

    checkpoint_preview = []
    applied_checkpoint_fields: list[str] = []
    for item in checkpoint_log:
        if not isinstance(item, dict):
            continue
        field = str(item.get("field", "")).strip()
        would_apply = bool(applied_ticket_ids)
        if would_apply and field:
            applied_checkpoint_fields.append(field)
        checkpoint_preview.append(
            {
                "field": field,
                "pending_value": item.get("pending_value", ""),
                "would_apply": would_apply,
                "reason": item.get("reason", ""),
            }
        )

    next_run_status = (
        "checkpoint-pending"
        if applied_ticket_ids
        else "reviewing"
        if deferred_ticket_ids
        else "blocked"
    )
    recovery_cursor_obj = execution_state.get("recovery_cursor", {})
    recovery_cursor = recovery_cursor_obj if isinstance(recovery_cursor_obj, dict) else {}
    next_recovery_cursor = {
        "blocked_ticket_ids": blocked_ticket_ids,
        "review_ticket_ids": deferred_ticket_ids,
        "replay_ready_ticket_ids": applied_ticket_ids,
        "recovery_owner": recovery_cursor.get("recovery_owner", ""),
    }
    return {
        "contract_version": "writer-imitate-execution-replay.v1",
        "primary_operator_entrypoint": "writer-imitate-operator-surface.json",
        "legacy_operator_entrypoint": "writer-imitate-legacy-contract-surface.json",
        "source_contract_version": execution_state.get("contract_version", ""),
        "session_operator_contract": execution_state.get("session_operator_contract", {}),
        "session_primary_verdicts": execution_state.get("session_primary_verdicts", {}),
        "session_primary_digests": execution_state.get("session_primary_digests", {}),
        "session_primary_contract_hints": execution_state.get("session_primary_contract_hints", {}),
        "session_legacy_contract_layer": execution_state.get("session_legacy_contract_layer", {}),
        "current_run_status": execution_state.get("run_status", ""),
        "next_run_status": next_run_status,
        "applied_ticket_ids": applied_ticket_ids,
        "deferred_ticket_ids": deferred_ticket_ids,
        "blocked_ticket_ids": blocked_ticket_ids,
        "replay_results": replay_results,
        "transition_preview": transition_preview,
        "checkpoint_preview": checkpoint_preview,
        "applied_checkpoint_fields": applied_checkpoint_fields,
        "next_recovery_cursor": next_recovery_cursor,
    }


def _writer_output_execution_replay_markdown(output_dir: Path) -> str:
    payload = _build_writer_output_execution_replay(output_dir)
    lines = ["# Writer Imitation Execution Replay Preview"]
    lines.append(f"\n- contract_version: {payload.get('contract_version', '')}")
    lines.append("- primary_operator_entrypoint: writer-imitate-operator-surface.md")
    lines.append("- legacy_operator_entrypoint: writer-imitate-legacy-contract-surface.md")
    lines.append(f"- source_contract_version: {payload.get('source_contract_version', '')}")
    lines.append(f"- current_run_status: {payload.get('current_run_status', '')}")
    lines.append(f"- next_run_status: {payload.get('next_run_status', '')}")
    _append_primary_surface_lines(lines, payload)
    _append_operator_contract_lines(lines, payload.get("session_operator_contract", {}))

    lines.append("\n## Replay Results")
    replay_results = payload.get("replay_results", [])
    for item in replay_results if isinstance(replay_results, list) else []:
        if not isinstance(item, dict):
            continue
        lines.append(
            f"- {item.get('ticket_id', '')}: result={item.get('result', '')} | "
            f"phase_after={item.get('phase_after', '')} | owner={item.get('owner', '')}"
        )

    lines.append("\n## Transition Preview")
    transition_preview = payload.get("transition_preview", [])
    for item in transition_preview if isinstance(transition_preview, list) else []:
        if not isinstance(item, dict):
            continue
        lines.append(
            f"- {item.get('from', '')} -> {item.get('to', '')} | trigger={item.get('trigger', '')} | "
            f"would_apply={item.get('would_apply', False)} | owner={item.get('owner', '')}"
        )

    lines.append("\n## Checkpoint Preview")
    checkpoint_preview = payload.get("checkpoint_preview", [])
    for item in checkpoint_preview if isinstance(checkpoint_preview, list) else []:
        if not isinstance(item, dict):
            continue
        lines.append(
            f"- {item.get('field', '')}: pending_value={item.get('pending_value', '')} | "
            f"would_apply={item.get('would_apply', False)} | reason={item.get('reason', '')}"
        )

    recovery_cursor = payload.get("next_recovery_cursor", {})
    if isinstance(recovery_cursor, dict):
        blocked_ids = recovery_cursor.get("blocked_ticket_ids", [])
        review_ids = recovery_cursor.get("review_ticket_ids", [])
        replay_ready_ids = recovery_cursor.get("replay_ready_ticket_ids", [])
        blocked_text = "；".join(str(x) for x in blocked_ids) if isinstance(blocked_ids, list) else ""
        review_text = "；".join(str(x) for x in review_ids) if isinstance(review_ids, list) else ""
        replay_ready_text = "；".join(str(x) for x in replay_ready_ids) if isinstance(replay_ready_ids, list) else ""
        lines.append("\n## Next Recovery Cursor")
        lines.append(f"- recovery_owner: {recovery_cursor.get('recovery_owner', '')}")
        lines.append(f"- replay_ready_ticket_ids: {replay_ready_text}")
        lines.append(f"- blocked_ticket_ids: {blocked_text}")
        lines.append(f"- review_ticket_ids: {review_text}")

    return "\n".join(lines).strip() + "\n"


def _build_writer_output_execution_apply(output_dir: Path) -> dict[str, object]:
    replay = _build_writer_output_execution_replay(output_dir)
    replay_results_obj = replay.get("replay_results", [])
    replay_results = replay_results_obj if isinstance(replay_results_obj, list) else []
    transition_preview_obj = replay.get("transition_preview", [])
    transition_preview = transition_preview_obj if isinstance(transition_preview_obj, list) else []
    checkpoint_preview_obj = replay.get("checkpoint_preview", [])
    checkpoint_preview = checkpoint_preview_obj if isinstance(checkpoint_preview_obj, list) else []

    applied_tickets: list[dict[str, object]] = []
    deferred_tickets: list[dict[str, object]] = []
    blocked_tickets: list[dict[str, object]] = []
    for item in replay_results:
        if not isinstance(item, dict):
            continue
        result = str(item.get("result", "")).strip()
        normalized = {
            "ticket_id": item.get("ticket_id", ""),
            "result": result,
            "phase_after": item.get("phase_after", ""),
            "owner": item.get("owner", ""),
        }
        if result == "applied-preview":
            applied_tickets.append(normalized)
        elif result == "deferred-review":
            deferred_tickets.append(normalized)
        else:
            blocked_tickets.append(normalized)

    applied_transitions = [
        {
            "from": item.get("from", ""),
            "to": item.get("to", ""),
            "owner": item.get("owner", ""),
        }
        for item in transition_preview
        if isinstance(item, dict) and bool(item.get("would_apply", False))
    ]
    applied_checkpoints = [
        {
            "field": item.get("field", ""),
            "value": item.get("pending_value", ""),
            "reason": item.get("reason", ""),
        }
        for item in checkpoint_preview
        if isinstance(item, dict) and bool(item.get("would_apply", False))
    ]
    apply_status = (
        "applied-preview"
        if applied_tickets
        else "deferred-review"
        if deferred_tickets
        else "blocked-recovery"
    )
    next_resume_hint = (
        "apply-ready-checkpoints"
        if applied_tickets
        else "resolve-review-gate"
        if deferred_tickets
        else "run-recovery-lane"
    )
    return {
        "contract_version": "writer-imitate-execution-apply.v1",
        "primary_operator_entrypoint": "writer-imitate-operator-surface.json",
        "legacy_operator_entrypoint": "writer-imitate-legacy-contract-surface.json",
        "source_contract_version": replay.get("contract_version", ""),
        "session_operator_contract": replay.get("session_operator_contract", {}),
        "session_primary_verdicts": replay.get("session_primary_verdicts", {}),
        "session_primary_digests": replay.get("session_primary_digests", {}),
        "session_primary_contract_hints": replay.get("session_primary_contract_hints", {}),
        "session_legacy_contract_layer": replay.get("session_legacy_contract_layer", {}),
        "apply_status": apply_status,
        "applied_tickets": applied_tickets,
        "deferred_tickets": deferred_tickets,
        "blocked_tickets": blocked_tickets,
        "applied_transitions": applied_transitions,
        "applied_checkpoints": applied_checkpoints,
        "next_resume_hint": next_resume_hint,
    }


def _writer_output_execution_apply_markdown(output_dir: Path) -> str:
    payload = _build_writer_output_execution_apply(output_dir)
    lines = ["# Writer Imitation Execution Apply Preview"]
    lines.append(f"\n- contract_version: {payload.get('contract_version', '')}")
    lines.append("- primary_operator_entrypoint: writer-imitate-operator-surface.md")
    lines.append("- legacy_operator_entrypoint: writer-imitate-legacy-contract-surface.md")
    lines.append(f"- source_contract_version: {payload.get('source_contract_version', '')}")
    lines.append(f"- apply_status: {payload.get('apply_status', '')}")
    lines.append(f"- next_resume_hint: {payload.get('next_resume_hint', '')}")
    _append_primary_surface_lines(lines, payload)
    _append_operator_contract_lines(lines, payload.get("session_operator_contract", {}))
    applied_tickets = payload.get("applied_tickets", [])
    deferred_tickets = payload.get("deferred_tickets", [])
    blocked_tickets = payload.get("blocked_tickets", [])
    applied_transitions = payload.get("applied_transitions", [])
    applied_checkpoints = payload.get("applied_checkpoints", [])
    lines.append("\n## Applied Tickets")
    for item in applied_tickets if isinstance(applied_tickets, list) else []:
        if isinstance(item, dict):
            lines.append(
                f"- {item.get('ticket_id', '')}: result={item.get('result', '')} | phase_after={item.get('phase_after', '')} | owner={item.get('owner', '')}"
            )
    lines.append("\n## Deferred Tickets")
    for item in deferred_tickets if isinstance(deferred_tickets, list) else []:
        if isinstance(item, dict):
            lines.append(
                f"- {item.get('ticket_id', '')}: result={item.get('result', '')} | phase_after={item.get('phase_after', '')} | owner={item.get('owner', '')}"
            )
    lines.append("\n## Blocked Tickets")
    for item in blocked_tickets if isinstance(blocked_tickets, list) else []:
        if isinstance(item, dict):
            lines.append(
                f"- {item.get('ticket_id', '')}: result={item.get('result', '')} | phase_after={item.get('phase_after', '')} | owner={item.get('owner', '')}"
            )
    lines.append("\n## Applied Transitions")
    for item in applied_transitions if isinstance(applied_transitions, list) else []:
        if isinstance(item, dict):
            lines.append(f"- {item.get('from', '')} -> {item.get('to', '')} | owner={item.get('owner', '')}")
    lines.append("\n## Applied Checkpoints")
    for item in applied_checkpoints if isinstance(applied_checkpoints, list) else []:
        if isinstance(item, dict):
            lines.append(
                f"- {item.get('field', '')}: value={item.get('value', '')} | reason={item.get('reason', '')}"
            )
    return "\n".join(lines).strip() + "\n"


def _build_writer_output_live_control_state(output_dir: Path) -> dict[str, object]:
    apply_preview = _build_writer_output_execution_apply(output_dir)
    operator_contract_obj = apply_preview.get("session_operator_contract", {})
    operator_contract = operator_contract_obj if isinstance(operator_contract_obj, dict) else {}
    primary_verdicts_obj = apply_preview.get("session_primary_verdicts", {})
    primary_verdicts = primary_verdicts_obj if isinstance(primary_verdicts_obj, dict) else {}
    primary_digests_obj = apply_preview.get("session_primary_digests", {})
    primary_digests = primary_digests_obj if isinstance(primary_digests_obj, dict) else {}
    applied_checkpoints_obj = apply_preview.get("applied_checkpoints", [])
    applied_checkpoints = applied_checkpoints_obj if isinstance(applied_checkpoints_obj, list) else []
    applied_transitions_obj = apply_preview.get("applied_transitions", [])
    applied_transitions = applied_transitions_obj if isinstance(applied_transitions_obj, list) else []
    live_mutation_readiness = {
        "status": "not-ready",
        "required_conditions": [
            "checkpoint writeback executor implemented",
            "transition apply executor implemented",
            "rollback path verified against live mutation",
        ],
        "blocking_reasons": [
            "apply preview is still non-mutating",
            "live checkpoint writeback has not been wired",
        ],
        "next_action": "implement checkpoint writeback executor",
    }
    live_mutation_plan = {
        "phase": "pre-live-mutation",
        "execution_order": [
            "checkpoint-writeback",
            "transition-apply",
            "post-apply-validation",
        ],
        "checkpoint_writeback_targets": [
            item.get("field", "")
            for item in applied_checkpoints
            if isinstance(item, dict)
        ],
        "transition_apply_targets": [
            f"{item.get('from', '')}->{item.get('to', '')}"
            for item in applied_transitions
            if isinstance(item, dict)
        ],
        "rollback_strategy": [
            "restore previous checkpoint snapshot",
            "restore previous transition status",
            "revert live mutation if downstream mismatch appears",
        ],
    }
    live_mutation_pilot_wave = {
        "wave_id": "live-mutation-wave-01",
        "status": "planned-not-executed",
        "target_scope": [
            "checkpoint-writeback",
            "transition-apply",
        ],
        "pilot_targets": {
            "checkpoint_writeback_targets": live_mutation_plan["checkpoint_writeback_targets"],
            "transition_apply_targets": live_mutation_plan["transition_apply_targets"],
        },
        "rollback_rule": "if writeback/apply mismatch appears, restore previous checkpoint snapshot and transition status immediately",
    }

    return {
        "contract_version": "writer-imitate-live-control-state.v1",
        "primary_operator_entrypoint": "writer-imitate-operator-surface.json",
        "legacy_operator_entrypoint": "writer-imitate-legacy-contract-surface.json",
        "source_apply_contract_version": apply_preview.get("contract_version", ""),
        "live_state_status": "preview-backed-pending-live-mutation",
        "session_operator_contract": operator_contract,
        "session_primary_verdicts": primary_verdicts,
        "session_primary_digests": primary_digests,
        "pending_checkpoint_writeback": applied_checkpoints,
        "pending_transition_apply": applied_transitions,
        "next_live_mutation_step": "checkpoint-writeback",
        "live_mutation_readiness": live_mutation_readiness,
        "live_mutation_plan": live_mutation_plan,
        "live_mutation_pilot_wave": live_mutation_pilot_wave,
    }


def _writer_output_live_control_state_markdown(output_dir: Path) -> str:
    payload = _build_writer_output_live_control_state(output_dir)
    lines = ["# Writer Imitation Live Control State"]
    lines.append(f"\n- contract_version: {payload.get('contract_version', '')}")
    lines.append("- primary_operator_entrypoint: writer-imitate-operator-surface.md")
    lines.append("- legacy_operator_entrypoint: writer-imitate-legacy-contract-surface.md")
    lines.append(f"- source_apply_contract_version: {payload.get('source_apply_contract_version', '')}")
    lines.append(f"- live_state_status: {payload.get('live_state_status', '')}")
    lines.append(f"- next_live_mutation_step: {payload.get('next_live_mutation_step', '')}")
    _append_primary_surface_lines(lines, payload)
    _append_operator_contract_lines(lines, payload.get("session_operator_contract", {}))
    readiness = payload.get("live_mutation_readiness", {})
    if isinstance(readiness, dict):
        lines.append("\n## Live Mutation Readiness")
        lines.append(f"- status: {readiness.get('status', '')}")
        required_conditions = readiness.get("required_conditions", [])
        blocking_reasons = readiness.get("blocking_reasons", [])
        required_text = "；".join(str(x) for x in required_conditions) if isinstance(required_conditions, list) else ""
        blocking_text = "；".join(str(x) for x in blocking_reasons) if isinstance(blocking_reasons, list) else ""
        lines.append(f"- required_conditions: {required_text}")
        lines.append(f"- blocking_reasons: {blocking_text}")
        lines.append(f"- next_action: {readiness.get('next_action', '')}")
    plan = payload.get("live_mutation_plan", {})
    if isinstance(plan, dict):
        lines.append("\n## Live Mutation Plan")
        lines.append(f"- phase: {plan.get('phase', '')}")
        execution_order = plan.get("execution_order", [])
        checkpoints = plan.get("checkpoint_writeback_targets", [])
        transitions = plan.get("transition_apply_targets", [])
        rollback = plan.get("rollback_strategy", [])
        order_text = "；".join(str(x) for x in execution_order) if isinstance(execution_order, list) else ""
        checkpoint_text = "；".join(str(x) for x in checkpoints) if isinstance(checkpoints, list) else ""
        transition_text = "；".join(str(x) for x in transitions) if isinstance(transitions, list) else ""
        rollback_text = "；".join(str(x) for x in rollback) if isinstance(rollback, list) else ""
        lines.append(f"- execution_order: {order_text}")
        lines.append(f"- checkpoint_writeback_targets: {checkpoint_text}")
        lines.append(f"- transition_apply_targets: {transition_text}")
        lines.append(f"- rollback_strategy: {rollback_text}")
    pilot_wave = payload.get("live_mutation_pilot_wave", {})
    if isinstance(pilot_wave, dict):
        lines.append("\n## Live Mutation Pilot Wave")
        lines.append(f"- wave_id: {pilot_wave.get('wave_id', '')}")
        lines.append(f"- status: {pilot_wave.get('status', '')}")
        target_scope = pilot_wave.get("target_scope", [])
        scope_text = "；".join(str(x) for x in target_scope) if isinstance(target_scope, list) else ""
        lines.append(f"- target_scope: {scope_text}")
        lines.append(f"- rollback_rule: {pilot_wave.get('rollback_rule', '')}")

    lines.append("\n## Pending Checkpoint Writeback")
    checkpoints = payload.get("pending_checkpoint_writeback", [])
    for item in checkpoints if isinstance(checkpoints, list) else []:
        if isinstance(item, dict):
            lines.append(
                f"- {item.get('field', '')}: value={item.get('value', '')} | reason={item.get('reason', '')}"
            )

    lines.append("\n## Pending Transition Apply")
    transitions = payload.get("pending_transition_apply", [])
    for item in transitions if isinstance(transitions, list) else []:
        if isinstance(item, dict):
            lines.append(
                f"- {item.get('from', '')} -> {item.get('to', '')} | owner={item.get('owner', '')}"
            )
    return "\n".join(lines).strip() + "\n"


def _build_writer_output_live_mutation_preview(output_dir: Path) -> dict[str, object]:
    live_control_state = _build_writer_output_live_control_state(output_dir)
    readiness_obj = live_control_state.get("live_mutation_readiness", {})
    readiness = readiness_obj if isinstance(readiness_obj, dict) else {}
    plan_obj = live_control_state.get("live_mutation_plan", {})
    plan = plan_obj if isinstance(plan_obj, dict) else {}
    pilot_wave_obj = live_control_state.get("live_mutation_pilot_wave", {})
    pilot_wave = pilot_wave_obj if isinstance(pilot_wave_obj, dict) else {}
    checkpoints_obj = live_control_state.get("pending_checkpoint_writeback", [])
    checkpoints = checkpoints_obj if isinstance(checkpoints_obj, list) else []
    transitions_obj = live_control_state.get("pending_transition_apply", [])
    transitions = transitions_obj if isinstance(transitions_obj, list) else []

    return {
        "contract_version": "writer-imitate-live-mutation-preview.v1",
        "primary_operator_entrypoint": "writer-imitate-operator-surface.json",
        "live_control_state_entrypoint": "writer-imitate-live-control-state.json",
        "preview_status": "planned-not-executed",
        "live_mutation_readiness": readiness,
        "live_mutation_plan": plan,
        "live_mutation_pilot_wave": pilot_wave,
        "checkpoint_writeback_preview": checkpoints,
        "transition_apply_preview": transitions,
    }


def _writer_output_live_mutation_preview_markdown(output_dir: Path) -> str:
    payload = _build_writer_output_live_mutation_preview(output_dir)
    lines = ["# Writer Imitation Live Mutation Preview"]
    lines.append(f"\n- contract_version: {payload.get('contract_version', '')}")
    lines.append("- primary_operator_entrypoint: writer-imitate-operator-surface.md")
    lines.append("- live_control_state_entrypoint: writer-imitate-live-control-state.md")
    lines.append(f"- preview_status: {payload.get('preview_status', '')}")

    readiness = payload.get("live_mutation_readiness", {})
    if isinstance(readiness, dict):
        lines.append("\n## Live Mutation Readiness")
        lines.append(f"- status: {readiness.get('status', '')}")
        lines.append(f"- next_action: {readiness.get('next_action', '')}")

    plan = payload.get("live_mutation_plan", {})
    if isinstance(plan, dict):
        lines.append("\n## Live Mutation Plan")
        execution_order = plan.get("execution_order", [])
        order_text = "；".join(str(x) for x in execution_order) if isinstance(execution_order, list) else ""
        lines.append(f"- execution_order: {order_text}")

    pilot_wave = payload.get("live_mutation_pilot_wave", {})
    if isinstance(pilot_wave, dict):
        lines.append("\n## Live Mutation Pilot Wave")
        lines.append(f"- wave_id: {pilot_wave.get('wave_id', '')}")
        lines.append(f"- status: {pilot_wave.get('status', '')}")
        lines.append(f"- rollback_rule: {pilot_wave.get('rollback_rule', '')}")

    lines.append("\n## Checkpoint Writeback Preview")
    checkpoints = payload.get("checkpoint_writeback_preview", [])
    for item in checkpoints if isinstance(checkpoints, list) else []:
        if isinstance(item, dict):
            lines.append(f"- {item.get('field', '')}: value={item.get('value', '')} | reason={item.get('reason', '')}")

    lines.append("\n## Transition Apply Preview")
    transitions = payload.get("transition_apply_preview", [])
    for item in transitions if isinstance(transitions, list) else []:
        if isinstance(item, dict):
            lines.append(f"- {item.get('from', '')} -> {item.get('to', '')} | owner={item.get('owner', '')}")

    return "\n".join(lines).strip() + "\n"


def _build_writer_output_live_checkpoint_state(output_dir: Path) -> dict[str, object]:
    live_control_state = _build_writer_output_live_control_state(output_dir)
    checkpoints_obj = live_control_state.get("pending_checkpoint_writeback", [])
    checkpoints = checkpoints_obj if isinstance(checkpoints_obj, list) else []
    applied_checkpoints: list[dict[str, object]] = []
    for item in checkpoints:
        if not isinstance(item, dict):
            continue
        applied_checkpoints.append(
            {
                "field": item.get("field", ""),
                "value": item.get("value", ""),
                "reason": item.get("reason", ""),
                "applied": True,
            }
        )
    operator_contract_obj = live_control_state.get("session_operator_contract", {})
    operator_contract = operator_contract_obj if isinstance(operator_contract_obj, dict) else {}
    primary_verdicts_obj = live_control_state.get("session_primary_verdicts", {})
    primary_verdicts = primary_verdicts_obj if isinstance(primary_verdicts_obj, dict) else {}
    primary_digests_obj = live_control_state.get("session_primary_digests", {})
    primary_digests = primary_digests_obj if isinstance(primary_digests_obj, dict) else {}
    return {
        "contract_version": "writer-imitate-live-checkpoint-state.v1",
        "primary_operator_entrypoint": "writer-imitate-operator-surface.json",
        "live_control_state_entrypoint": "writer-imitate-live-control-state.json",
        "live_checkpoint_status": "checkpoint-writeback-applied-local",
        "next_live_mutation_step": "transition-apply",
        "session_operator_contract": operator_contract,
        "session_primary_verdicts": primary_verdicts,
        "session_primary_digests": primary_digests,
        "applied_checkpoints": applied_checkpoints,
    }


def _writer_output_live_checkpoint_state_markdown(output_dir: Path) -> str:
    payload = _build_writer_output_live_checkpoint_state(output_dir)
    lines = ["# Writer Imitation Live Checkpoint State"]
    lines.append(f"\n- contract_version: {payload.get('contract_version', '')}")
    lines.append("- primary_operator_entrypoint: writer-imitate-operator-surface.md")
    lines.append("- live_control_state_entrypoint: writer-imitate-live-control-state.md")
    lines.append(f"- live_checkpoint_status: {payload.get('live_checkpoint_status', '')}")
    lines.append(f"- next_live_mutation_step: {payload.get('next_live_mutation_step', '')}")
    _append_primary_surface_lines(lines, payload)
    _append_operator_contract_lines(lines, payload.get("session_operator_contract", {}))
    lines.append("\n## Applied Checkpoints")
    checkpoints = payload.get("applied_checkpoints", [])
    for item in checkpoints if isinstance(checkpoints, list) else []:
        if isinstance(item, dict):
            lines.append(
                f"- {item.get('field', '')}: value={item.get('value', '')} | applied={item.get('applied', False)} | reason={item.get('reason', '')}"
            )
    return "\n".join(lines).strip() + "\n"


def _build_writer_output_live_transition_state(output_dir: Path) -> dict[str, object]:
    live_control_state = _build_writer_output_live_control_state(output_dir)
    transitions_obj = live_control_state.get("pending_transition_apply", [])
    transitions = transitions_obj if isinstance(transitions_obj, list) else []
    applied_transitions: list[dict[str, object]] = []
    for item in transitions:
        if not isinstance(item, dict):
            continue
        applied_transitions.append(
            {
                "from": item.get("from", ""),
                "to": item.get("to", ""),
                "owner": item.get("owner", ""),
                "applied": True,
            }
        )
    operator_contract_obj = live_control_state.get("session_operator_contract", {})
    operator_contract = operator_contract_obj if isinstance(operator_contract_obj, dict) else {}
    primary_verdicts_obj = live_control_state.get("session_primary_verdicts", {})
    primary_verdicts = primary_verdicts_obj if isinstance(primary_verdicts_obj, dict) else {}
    primary_digests_obj = live_control_state.get("session_primary_digests", {})
    primary_digests = primary_digests_obj if isinstance(primary_digests_obj, dict) else {}
    return {
        "contract_version": "writer-imitate-live-transition-state.v1",
        "primary_operator_entrypoint": "writer-imitate-operator-surface.json",
        "live_control_state_entrypoint": "writer-imitate-live-control-state.json",
        "live_transition_status": "transition-apply-applied-local",
        "next_live_mutation_step": "post-apply-validation",
        "session_operator_contract": operator_contract,
        "session_primary_verdicts": primary_verdicts,
        "session_primary_digests": primary_digests,
        "applied_transitions": applied_transitions,
    }


def _writer_output_live_transition_state_markdown(output_dir: Path) -> str:
    payload = _build_writer_output_live_transition_state(output_dir)
    lines = ["# Writer Imitation Live Transition State"]
    lines.append(f"\n- contract_version: {payload.get('contract_version', '')}")
    lines.append("- primary_operator_entrypoint: writer-imitate-operator-surface.md")
    lines.append("- live_control_state_entrypoint: writer-imitate-live-control-state.md")
    lines.append(f"- live_transition_status: {payload.get('live_transition_status', '')}")
    lines.append(f"- next_live_mutation_step: {payload.get('next_live_mutation_step', '')}")
    _append_primary_surface_lines(lines, payload)
    _append_operator_contract_lines(lines, payload.get("session_operator_contract", {}))
    lines.append("\n## Applied Transitions")
    transitions = payload.get("applied_transitions", [])
    for item in transitions if isinstance(transitions, list) else []:
        if isinstance(item, dict):
            lines.append(
                f"- {item.get('from', '')} -> {item.get('to', '')} | owner={item.get('owner', '')} | applied={item.get('applied', False)}"
            )
    return "\n".join(lines).strip() + "\n"


def _build_writer_output_live_validation_state(output_dir: Path) -> dict[str, object]:
    live_checkpoint_state = _build_writer_output_live_checkpoint_state(output_dir)
    live_transition_state = _build_writer_output_live_transition_state(output_dir)
    checkpoints_obj = live_checkpoint_state.get("applied_checkpoints", [])
    checkpoints = checkpoints_obj if isinstance(checkpoints_obj, list) else []
    transitions_obj = live_transition_state.get("applied_transitions", [])
    transitions = transitions_obj if isinstance(transitions_obj, list) else []
    operator_contract_obj = live_transition_state.get("session_operator_contract", {})
    operator_contract = operator_contract_obj if isinstance(operator_contract_obj, dict) else {}
    primary_verdicts_obj = live_transition_state.get("session_primary_verdicts", {})
    primary_verdicts = primary_verdicts_obj if isinstance(primary_verdicts_obj, dict) else {}
    primary_digests_obj = live_transition_state.get("session_primary_digests", {})
    primary_digests = primary_digests_obj if isinstance(primary_digests_obj, dict) else {}

    validation_checks = [
        {"check": "checkpoint_writeback_applied", "passed": bool(checkpoints)},
        {"check": "transition_apply_applied", "passed": bool(transitions)},
        {"check": "operator_contract_preserved", "passed": bool(operator_contract)},
    ]

    validation_status = "validated-local" if all(bool(item.get("passed", False)) for item in validation_checks) else "validation-failed"

    return {
        "contract_version": "writer-imitate-live-validation-state.v1",
        "primary_operator_entrypoint": "writer-imitate-operator-surface.json",
        "live_control_state_entrypoint": "writer-imitate-live-control-state.json",
        "live_validation_status": validation_status,
        "session_operator_contract": operator_contract,
        "session_primary_verdicts": primary_verdicts,
        "session_primary_digests": primary_digests,
        "validation_checks": validation_checks,
        "next_live_mutation_step": "external-runtime-executor",
    }


def _writer_output_live_validation_state_markdown(output_dir: Path) -> str:
    payload = _build_writer_output_live_validation_state(output_dir)
    lines = ["# Writer Imitation Live Validation State"]
    lines.append(f"\n- contract_version: {payload.get('contract_version', '')}")
    lines.append("- primary_operator_entrypoint: writer-imitate-operator-surface.md")
    lines.append("- live_control_state_entrypoint: writer-imitate-live-control-state.md")
    lines.append(f"- live_validation_status: {payload.get('live_validation_status', '')}")
    lines.append(f"- next_live_mutation_step: {payload.get('next_live_mutation_step', '')}")
    _append_primary_surface_lines(lines, payload)
    _append_operator_contract_lines(lines, payload.get("session_operator_contract", {}))
    lines.append("\n## Validation Checks")
    checks = payload.get("validation_checks", [])
    for item in checks if isinstance(checks, list) else []:
        if isinstance(item, dict):
            lines.append(f"- {item.get('check', '')}: passed={item.get('passed', False)}")
    return "\n".join(lines).strip() + "\n"


def _build_writer_output_external_runtime_executor_readiness(output_dir: Path) -> dict[str, object]:
    live_validation_state = _build_writer_output_live_validation_state(output_dir)
    validation_status = str(live_validation_state.get("live_validation_status", "")).strip()
    readiness = {
        "status": "not-ready" if validation_status != "validated-local" else "bridge-ready-runtime-not-wired",
        "required_conditions": [
            "external runtime checkpoint executor implemented",
            "external runtime transition executor implemented",
            "runtime-side rollback path verified",
            "consumer migration telemetry connected",
        ],
        "blocking_reasons": [
            "local bridge stops at output artifacts only",
            "external runtime mutation path not wired yet",
        ],
        "next_action": "implement external runtime checkpoint executor",
    }
    runtime_executor_plan = {
        "phase": "pre-runtime-executor",
        "execution_order": [
            "external-checkpoint-writeback",
            "external-transition-apply",
            "post-runtime-validation",
        ],
        "pilot_scope": [
            "checkpoint-writeback-only on controlled output-backed branch",
            "single transition apply after checkpoint success",
        ],
        "rollback_strategy": [
            "restore previous runtime checkpoint snapshot",
            "restore previous runtime transition state",
            "disable runtime executor if downstream mismatch appears",
        ],
    }
    runtime_executor_pilot_wave = {
        "wave_id": "external-runtime-wave-01",
        "status": "planned-not-executed",
        "target_scope": [
            "external-checkpoint-writeback",
            "external-transition-apply",
        ],
        "pilot_targets": [
            "single runtime checkpoint writeback after local validation success",
            "single runtime transition apply after checkpoint writeback success",
        ],
        "rollback_rule": "disable runtime executor and restore previous runtime checkpoint/transition state if mismatch appears",
    }
    return {
        "contract_version": "writer-imitate-external-runtime-executor-readiness.v1",
        "primary_operator_entrypoint": "writer-imitate-operator-surface.json",
        "live_validation_state_entrypoint": "writer-imitate-live-validation-state.json",
        "readiness": readiness,
        "external_runtime_executor_plan": runtime_executor_plan,
        "external_runtime_executor_pilot_wave": runtime_executor_pilot_wave,
    }


def _writer_output_external_runtime_executor_readiness_markdown(output_dir: Path) -> str:
    payload = _build_writer_output_external_runtime_executor_readiness(output_dir)
    lines = ["# Writer Imitation External Runtime Executor Readiness"]
    lines.append(f"\n- contract_version: {payload.get('contract_version', '')}")
    lines.append("- primary_operator_entrypoint: writer-imitate-operator-surface.md")
    lines.append("- live_validation_state_entrypoint: writer-imitate-live-validation-state.md")
    readiness = payload.get("readiness", {})
    if isinstance(readiness, dict):
        lines.append("\n## Readiness")
        lines.append(f"- status: {readiness.get('status', '')}")
        required_conditions = readiness.get("required_conditions", [])
        blocking_reasons = readiness.get("blocking_reasons", [])
        required_text = "；".join(str(x) for x in required_conditions) if isinstance(required_conditions, list) else ""
        blocking_text = "；".join(str(x) for x in blocking_reasons) if isinstance(blocking_reasons, list) else ""
        lines.append(f"- required_conditions: {required_text}")
        lines.append(f"- blocking_reasons: {blocking_text}")
        lines.append(f"- next_action: {readiness.get('next_action', '')}")
    plan = payload.get("external_runtime_executor_plan", {})
    if isinstance(plan, dict):
        lines.append("\n## External Runtime Executor Plan")
        lines.append(f"- phase: {plan.get('phase', '')}")
        execution_order = plan.get("execution_order", [])
        pilot_scope = plan.get("pilot_scope", [])
        rollback = plan.get("rollback_strategy", [])
        execution_text = "；".join(str(x) for x in execution_order) if isinstance(execution_order, list) else ""
        pilot_text = "；".join(str(x) for x in pilot_scope) if isinstance(pilot_scope, list) else ""
        rollback_text = "；".join(str(x) for x in rollback) if isinstance(rollback, list) else ""
        lines.append(f"- execution_order: {execution_text}")
        lines.append(f"- pilot_scope: {pilot_text}")
        lines.append(f"- rollback_strategy: {rollback_text}")
    pilot_wave = payload.get("external_runtime_executor_pilot_wave", {})
    if isinstance(pilot_wave, dict):
        lines.append("\n## External Runtime Executor Pilot Wave")
        lines.append(f"- wave_id: {pilot_wave.get('wave_id', '')}")
        lines.append(f"- status: {pilot_wave.get('status', '')}")
        target_scope = pilot_wave.get("target_scope", [])
        target_text = "；".join(str(x) for x in target_scope) if isinstance(target_scope, list) else ""
        lines.append(f"- target_scope: {target_text}")
        lines.append(f"- rollback_rule: {pilot_wave.get('rollback_rule', '')}")
    return "\n".join(lines).strip() + "\n"


def _build_writer_output_external_runtime_executor_preview(output_dir: Path) -> dict[str, object]:
    readiness = _build_writer_output_external_runtime_executor_readiness(output_dir)
    readiness_obj = readiness.get("readiness", {})
    readiness_payload = readiness_obj if isinstance(readiness_obj, dict) else {}
    plan_obj = readiness.get("external_runtime_executor_plan", {})
    plan = plan_obj if isinstance(plan_obj, dict) else {}
    pilot_wave_obj = readiness.get("external_runtime_executor_pilot_wave", {})
    pilot_wave = pilot_wave_obj if isinstance(pilot_wave_obj, dict) else {}
    return {
        "contract_version": "writer-imitate-external-runtime-executor-preview.v1",
        "primary_operator_entrypoint": "writer-imitate-operator-surface.json",
        "external_runtime_executor_readiness_entrypoint": "writer-imitate-external-runtime-executor-readiness.json",
        "preview_status": "planned-not-executed",
        "readiness": readiness_payload,
        "external_runtime_executor_plan": plan,
        "external_runtime_executor_pilot_wave": pilot_wave,
    }


def _writer_output_external_runtime_executor_preview_markdown(output_dir: Path) -> str:
    payload = _build_writer_output_external_runtime_executor_preview(output_dir)
    lines = ["# Writer Imitation External Runtime Executor Preview"]
    lines.append(f"\n- contract_version: {payload.get('contract_version', '')}")
    lines.append("- primary_operator_entrypoint: writer-imitate-operator-surface.md")
    lines.append("- external_runtime_executor_readiness_entrypoint: writer-imitate-external-runtime-executor-readiness.md")
    lines.append(f"- preview_status: {payload.get('preview_status', '')}")
    readiness = payload.get("readiness", {})
    if isinstance(readiness, dict):
        lines.append("\n## Readiness")
        lines.append(f"- status: {readiness.get('status', '')}")
        lines.append(f"- next_action: {readiness.get('next_action', '')}")
    plan = payload.get("external_runtime_executor_plan", {})
    if isinstance(plan, dict):
        lines.append("\n## External Runtime Executor Plan")
        execution_order = plan.get("execution_order", [])
        pilot_scope = plan.get("pilot_scope", [])
        execution_text = "；".join(str(x) for x in execution_order) if isinstance(execution_order, list) else ""
        pilot_text = "；".join(str(x) for x in pilot_scope) if isinstance(pilot_scope, list) else ""
        lines.append(f"- execution_order: {execution_text}")
        lines.append(f"- pilot_scope: {pilot_text}")
    pilot_wave = payload.get("external_runtime_executor_pilot_wave", {})
    if isinstance(pilot_wave, dict):
        lines.append("\n## External Runtime Executor Pilot Wave")
        lines.append(f"- wave_id: {pilot_wave.get('wave_id', '')}")
        lines.append(f"- status: {pilot_wave.get('status', '')}")
        lines.append(f"- rollback_rule: {pilot_wave.get('rollback_rule', '')}")
    return "\n".join(lines).strip() + "\n"


def _build_writer_output_external_runtime_checkpoint_state(output_dir: Path) -> dict[str, object]:
    preview = _build_writer_output_external_runtime_executor_preview(output_dir)
    readiness_obj = preview.get("readiness", {})
    readiness = readiness_obj if isinstance(readiness_obj, dict) else {}
    pilot_wave_obj = preview.get("external_runtime_executor_pilot_wave", {})
    pilot_wave = pilot_wave_obj if isinstance(pilot_wave_obj, dict) else {}
    live_checkpoint_state = _build_writer_output_live_checkpoint_state(output_dir)
    applied_checkpoints_obj = live_checkpoint_state.get("applied_checkpoints", [])
    applied_checkpoints = applied_checkpoints_obj if isinstance(applied_checkpoints_obj, list) else []

    simulated_runtime_checkpoints: list[dict[str, object]] = []
    for item in applied_checkpoints:
        if not isinstance(item, dict):
            continue
        simulated_runtime_checkpoints.append(
            {
                "field": item.get("field", ""),
                "value": item.get("value", ""),
                "reason": item.get("reason", ""),
                "applied": True,
                "mode": "external-runtime-simulated-local",
            }
        )

    return {
        "contract_version": "writer-imitate-external-runtime-checkpoint-state.v1",
        "primary_operator_entrypoint": "writer-imitate-operator-surface.json",
        "external_runtime_executor_preview_entrypoint": "writer-imitate-external-runtime-executor-preview.json",
        "checkpoint_state_status": "external-runtime-checkpoint-simulated-local",
        "readiness": readiness,
        "pilot_wave": pilot_wave,
        "applied_runtime_checkpoints": simulated_runtime_checkpoints,
        "next_runtime_step": "external-transition-apply",
    }


def _writer_output_external_runtime_checkpoint_state_markdown(output_dir: Path) -> str:
    payload = _build_writer_output_external_runtime_checkpoint_state(output_dir)
    lines = ["# Writer Imitation External Runtime Checkpoint State"]
    lines.append(f"\n- contract_version: {payload.get('contract_version', '')}")
    lines.append("- primary_operator_entrypoint: writer-imitate-operator-surface.md")
    lines.append("- external_runtime_executor_preview_entrypoint: writer-imitate-external-runtime-executor-preview.md")
    lines.append(f"- checkpoint_state_status: {payload.get('checkpoint_state_status', '')}")
    lines.append(f"- next_runtime_step: {payload.get('next_runtime_step', '')}")
    readiness = payload.get("readiness", {})
    if isinstance(readiness, dict):
        lines.append("\n## Readiness")
        lines.append(f"- status: {readiness.get('status', '')}")
        lines.append(f"- next_action: {readiness.get('next_action', '')}")
    pilot_wave = payload.get("pilot_wave", {})
    if isinstance(pilot_wave, dict):
        lines.append("\n## Pilot Wave")
        lines.append(f"- wave_id: {pilot_wave.get('wave_id', '')}")
        lines.append(f"- status: {pilot_wave.get('status', '')}")
    lines.append("\n## Applied Runtime Checkpoints")
    items = payload.get("applied_runtime_checkpoints", [])
    for item in items if isinstance(items, list) else []:
        if isinstance(item, dict):
            lines.append(
                f"- {item.get('field', '')}: value={item.get('value', '')} | applied={item.get('applied', False)} | mode={item.get('mode', '')}"
            )
    return "\n".join(lines).strip() + "\n"


def _build_writer_output_external_runtime_transition_state(output_dir: Path) -> dict[str, object]:
    preview = _build_writer_output_external_runtime_executor_preview(output_dir)
    readiness_obj = preview.get("readiness", {})
    readiness = readiness_obj if isinstance(readiness_obj, dict) else {}
    pilot_wave_obj = preview.get("external_runtime_executor_pilot_wave", {})
    pilot_wave = pilot_wave_obj if isinstance(pilot_wave_obj, dict) else {}
    live_transition_state = _build_writer_output_live_transition_state(output_dir)
    applied_transitions_obj = live_transition_state.get("applied_transitions", [])
    applied_transitions = applied_transitions_obj if isinstance(applied_transitions_obj, list) else []

    simulated_runtime_transitions: list[dict[str, object]] = []
    for item in applied_transitions:
        if not isinstance(item, dict):
            continue
        simulated_runtime_transitions.append(
            {
                "from": item.get("from", ""),
                "to": item.get("to", ""),
                "owner": item.get("owner", ""),
                "applied": True,
                "mode": "external-runtime-simulated-local",
            }
        )

    return {
        "contract_version": "writer-imitate-external-runtime-transition-state.v1",
        "primary_operator_entrypoint": "writer-imitate-operator-surface.json",
        "external_runtime_executor_preview_entrypoint": "writer-imitate-external-runtime-executor-preview.json",
        "transition_state_status": "external-runtime-transition-simulated-local",
        "readiness": readiness,
        "pilot_wave": pilot_wave,
        "applied_runtime_transitions": simulated_runtime_transitions,
        "next_runtime_step": "post-runtime-validation",
    }


def _writer_output_external_runtime_transition_state_markdown(output_dir: Path) -> str:
    payload = _build_writer_output_external_runtime_transition_state(output_dir)
    lines = ["# Writer Imitation External Runtime Transition State"]
    lines.append(f"\n- contract_version: {payload.get('contract_version', '')}")
    lines.append("- primary_operator_entrypoint: writer-imitate-operator-surface.md")
    lines.append("- external_runtime_executor_preview_entrypoint: writer-imitate-external-runtime-executor-preview.md")
    lines.append(f"- transition_state_status: {payload.get('transition_state_status', '')}")
    lines.append(f"- next_runtime_step: {payload.get('next_runtime_step', '')}")
    readiness = payload.get("readiness", {})
    if isinstance(readiness, dict):
        lines.append("\n## Readiness")
        lines.append(f"- status: {readiness.get('status', '')}")
        lines.append(f"- next_action: {readiness.get('next_action', '')}")
    pilot_wave = payload.get("pilot_wave", {})
    if isinstance(pilot_wave, dict):
        lines.append("\n## Pilot Wave")
        lines.append(f"- wave_id: {pilot_wave.get('wave_id', '')}")
        lines.append(f"- status: {pilot_wave.get('status', '')}")
    lines.append("\n## Applied Runtime Transitions")
    items = payload.get("applied_runtime_transitions", [])
    for item in items if isinstance(items, list) else []:
        if isinstance(item, dict):
            lines.append(
                f"- {item.get('from', '')} -> {item.get('to', '')} | applied={item.get('applied', False)} | mode={item.get('mode', '')}"
            )
    return "\n".join(lines).strip() + "\n"


def _build_writer_output_execution_resume(output_dir: Path) -> dict[str, object]:
    apply_preview = _build_writer_output_execution_apply(output_dir)
    deferred_obj = apply_preview.get("deferred_tickets", [])
    deferred_tickets = deferred_obj if isinstance(deferred_obj, list) else []
    blocked_obj = apply_preview.get("blocked_tickets", [])
    blocked_tickets = blocked_obj if isinstance(blocked_obj, list) else []
    resume_targets = [
        {
            "ticket_id": item.get("ticket_id", ""),
            "resume_mode": "review-resume",
            "owner": item.get("owner", ""),
        }
        for item in deferred_tickets
        if isinstance(item, dict)
    ] + [
        {
            "ticket_id": item.get("ticket_id", ""),
            "resume_mode": "recovery-resume",
            "owner": item.get("owner", ""),
        }
        for item in blocked_tickets
        if isinstance(item, dict)
    ]
    resume_steps = [
        "若存在 applied_checkpoints，先确认 checkpoint writeback 顺序",
        "对 deferred tickets 走 review-resume",
        "对 blocked tickets 走 recovery-resume",
    ]
    resume_status = "resume-ready" if resume_targets else "no-resume-needed"
    return {
        "contract_version": "writer-imitate-execution-resume.v1",
        "primary_operator_entrypoint": "writer-imitate-operator-surface.json",
        "legacy_operator_entrypoint": "writer-imitate-legacy-contract-surface.json",
        "source_contract_version": apply_preview.get("contract_version", ""),
        "session_operator_contract": apply_preview.get("session_operator_contract", {}),
        "session_primary_verdicts": apply_preview.get("session_primary_verdicts", {}),
        "session_primary_digests": apply_preview.get("session_primary_digests", {}),
        "session_primary_contract_hints": apply_preview.get("session_primary_contract_hints", {}),
        "session_legacy_contract_layer": apply_preview.get("session_legacy_contract_layer", {}),
        "resume_status": resume_status,
        "resume_targets": resume_targets,
        "resume_steps": resume_steps,
        "resume_hint": apply_preview.get("next_resume_hint", ""),
    }


def _writer_output_execution_resume_markdown(output_dir: Path) -> str:
    payload = _build_writer_output_execution_resume(output_dir)
    lines = ["# Writer Imitation Execution Resume Plan"]
    lines.append(f"\n- contract_version: {payload.get('contract_version', '')}")
    lines.append("- primary_operator_entrypoint: writer-imitate-operator-surface.md")
    lines.append("- legacy_operator_entrypoint: writer-imitate-legacy-contract-surface.md")
    lines.append(f"- source_contract_version: {payload.get('source_contract_version', '')}")
    lines.append(f"- resume_status: {payload.get('resume_status', '')}")
    lines.append(f"- resume_hint: {payload.get('resume_hint', '')}")
    _append_primary_surface_lines(lines, payload)
    _append_operator_contract_lines(lines, payload.get("session_operator_contract", {}))
    resume_targets = payload.get("resume_targets", [])
    resume_steps = payload.get("resume_steps", [])
    lines.append("\n## Resume Targets")
    for item in resume_targets if isinstance(resume_targets, list) else []:
        if isinstance(item, dict):
            lines.append(
                f"- {item.get('ticket_id', '')}: resume_mode={item.get('resume_mode', '')} | owner={item.get('owner', '')}"
            )
    lines.append("\n## Resume Steps")
    for item in resume_steps if isinstance(resume_steps, list) else []:
        lines.append(f"- {item}")
    return "\n".join(lines).strip() + "\n"


def _writer_output_index_markdown(output_dir: Path) -> str:
    lines: list[str] = ["# Writer Imitation Output Index"]
    range_files = sorted(output_dir.glob("writer-imitate-range-*.json"))
    experiment_files = sorted(output_dir.glob("writer-innovation-experiment-*.json"))
    if not range_files and not experiment_files:
        return "# Writer Imitation Output Index\n\n- no writer imitation json files found\n"

    if range_files:
        lines.append("\n## Range Runs")
    for path in range_files:
        lines.append(f"\n### {path.name}")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            lines.append(f"- parse_error: {exc}")
            continue
        items = payload.get("items", [])
        if not isinstance(items, list):
            lines.append("- items: unavailable")
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            chapter_index = item.get("source_chapter_index")
            target_goal = item.get("target_goal")
            final_verdict = str(item.get("final_verdict", "")).strip()
            stop_reason = str(item.get("stop_reason", "")).strip()
            final_draft = item.get("final_draft", {})
            draft_title = ""
            draft_len = 0
            if isinstance(final_draft, dict):
                draft_title = str(final_draft.get("draft_title", "")).strip()
                draft_len = len(str(final_draft.get("draft_text", "")))
            lines.append(
                f"- chapter {chapter_index}: verdict={final_verdict} | stop={stop_reason} | "
                f"title={draft_title} | draft_len={draft_len}"
            )
            if target_goal:
                lines.append(f"  - target_goal: {target_goal}")

    ledger_entries: list[dict[str, str]] = []
    session_recommendations: list[str] = []
    session_risk_labels: list[str] = []
    session_focuses: list[str] = []
    session_next_actions: list[str] = []
    if experiment_files:
        lines.append("\n## Innovation Experiments")
    for path in experiment_files:
        lines.append(f"\n### {path.name}")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            lines.append(f"- parse_error: {exc}")
            continue
        experiment_name = str(payload.get("experiment_name", "")).strip()
        if experiment_name:
            lines.append(f"- experiment_name: {experiment_name}")
        delta_visual_summary = payload.get("delta_visual_summary", {})
        innovation_level = ""
        risk_level = ""
        if isinstance(delta_visual_summary, dict):
            innovation_card = delta_visual_summary.get("innovation_card", {})
            risk_card = delta_visual_summary.get("risk_card", {})
            if isinstance(innovation_card, dict):
                innovation_level = str(innovation_card.get("level", "")).strip()
                lines.append(
                    f"- innovation_level: {innovation_level} | summary={innovation_card.get('summary', '')}"
                )
            if isinstance(risk_card, dict):
                risk_level = str(risk_card.get("level", "")).strip()
                lines.append(
                    f"- risk_level: {risk_level} | summary={risk_card.get('summary', '')}"
                )
        explanation = payload.get("writer_innovation_explanation", {})
        explanation_focus = ""
        if isinstance(explanation, dict):
            summary = str(explanation.get("summary", "")).strip()
            explanation_focus = str(explanation.get("focus", "")).strip()
            if summary:
                lines.append(f"- explanation_summary: {summary}")
            if explanation_focus:
                lines.append(f"- explanation_focus: {explanation_focus}")
        decision_note = payload.get("experiment_decision_note", {})
        decision_recommendation = ""
        decision_next_action = ""
        decision_pilot_scope = ""
        decision_confidence = ""
        decision_observation_window = ""
        decision_business_risk = ""
        if isinstance(decision_note, dict):
            decision_recommendation = str(decision_note.get("recommendation", "")).strip()
            decision_next_action = str(decision_note.get("next_action", "")).strip()
            decision_pilot_scope = str(decision_note.get("pilot_scope", "")).strip()
            decision_confidence = str(decision_note.get("confidence_level", "")).strip()
            decision_observation_window = str(decision_note.get("observation_window", "")).strip()
            decision_business_risk = str(decision_note.get("business_risk_label", "")).strip()
            if decision_recommendation:
                lines.append(f"- recommendation: {decision_recommendation}")
            if decision_next_action:
                lines.append(f"- next_action: {decision_next_action}")
            if decision_pilot_scope:
                lines.append(f"- pilot_scope: {decision_pilot_scope}")
            if decision_confidence:
                lines.append(f"- confidence_level: {decision_confidence}")
            if decision_observation_window:
                lines.append(f"- observation_window: {decision_observation_window}")
        acceptance = payload.get("reader_sim_acceptance_summary", {})
        reader_acceptance = ""
        if isinstance(acceptance, dict):
            reader_acceptance = (
                f"improved={acceptance.get('improved_count', 0)}/{acceptance.get('chapter_count', 0)} | "
                f"avg_delta={acceptance.get('average_score_delta', 0)}"
            )
            lines.append(f"- reader_acceptance: {reader_acceptance}")
        experiment_meta = payload.get("experiment_meta", {})
        baseline_summary = ""
        if isinstance(experiment_meta, dict):
            comparison = experiment_meta.get("baseline_vs_steering_report", {})
            if isinstance(comparison, dict):
                baseline_summary = str(comparison.get("summary", "")).strip()
                lines.append(f"- baseline_vs_steering: {baseline_summary}")
        ledger_entries.append(
            {
                "experiment_name": experiment_name or path.stem,
                "artifact": path.name,
                "innovation_level": innovation_level,
                "risk_level": risk_level,
                "reader_acceptance": reader_acceptance,
                "focus": explanation_focus,
                "recommendation": decision_recommendation,
                "next_action": decision_next_action,
                "pilot_scope": decision_pilot_scope,
                "confidence_level": decision_confidence,
                "observation_window": decision_observation_window,
                "business_risk_label": decision_business_risk,
                "baseline": baseline_summary,
            }
        )
        if decision_recommendation:
            session_recommendations.append(decision_recommendation)
        if decision_business_risk:
            session_risk_labels.append(decision_business_risk)
        if explanation_focus:
            session_focuses.append(explanation_focus)
        if decision_next_action:
            session_next_actions.append(decision_next_action)

    if ledger_entries:
        lines.append("\n## Experiment Session Control Plane")
        if all(item == "promote" for item in session_recommendations):
            promotion_verdict = "promote"
        elif any(item == "de-risk" for item in session_recommendations):
            promotion_verdict = "de-risk"
        elif any(item == "pilot" for item in session_recommendations):
            promotion_verdict = "pilot"
        else:
            promotion_verdict = "hold"
        if any(item == "high-risk" for item in session_risk_labels):
            risk_register = "high-risk"
        elif any(item == "guarded" for item in session_risk_labels):
            risk_register = "guarded"
        else:
            risk_register = "controlled"
        handoff_summary = "；".join(session_next_actions[:3]) if session_next_actions else "补更多证据后再推进。"
        session_ship_decision = (
            "ship-ready"
            if promotion_verdict == "promote" and risk_register == "controlled"
            else "needs-review"
        )
        session_blockers: list[str] = []
        if risk_register == "high-risk":
            session_blockers.append("high-risk experiments still present")
        if promotion_verdict == "hold":
            session_blockers.append("insufficient positive evidence across session")
        session_required_review = ["session operator review"]
        if risk_register in {"guarded", "high-risk"}:
            session_required_review.append("risk approver review")
        session_owner_handoff = [
            "writer-operator -> continuity-reviewer",
            "continuity-reviewer -> reader-feedback-owner",
        ]
        if risk_register in {"guarded", "high-risk"}:
            session_owner_handoff.append("reader-feedback-owner -> risk-approver")
        session_priority_queue = session_next_actions[:3] if session_next_actions else ["补更多证据后再推进。"]
        session_lane_status = (
            "expansion-lane"
            if promotion_verdict == "promote"
            else "risk-mitigation-lane" if promotion_verdict == "de-risk" else "pilot-lane" if promotion_verdict == "pilot" else "evidence-lane"
        )
        session_escalation_path = [
            "writer-operator -> continuity-reviewer",
            "continuity-reviewer -> reader-feedback-owner",
        ]
        if risk_register in {"guarded", "high-risk"}:
            session_escalation_path.append("reader-feedback-owner -> risk-approver")
        if session_ship_decision == "needs-review":
            session_escalation_path.append("risk-approver -> business-owner")
        session_release_readiness = (
            "ready-for-managed-pilot"
            if session_ship_decision == "ship-ready"
            else "blocked-pending-review"
        )
        session_recovery_plan = [
            "若 reader_acceptance 转负，回退到上一版 steering 组合",
            "若 risk_register 升级，切换到 de-risk lane 并压缩 pilot_scope",
        ]
        session_execution_mode = (
            "scale"
            if session_ship_decision == "ship-ready" and promotion_verdict == "promote"
            else "stabilize" if promotion_verdict == "de-risk" else "pilot"
        )
        session_action_window = (
            "next-5-8-chapters"
            if session_execution_mode == "scale"
            else "next-2-4-chapters"
        )
        session_ready_queue = session_priority_queue[:2] if session_ship_decision == "ship-ready" else []
        session_blocked_queue = session_blockers[:2] if session_blockers else []
        session_recovery_owner = (
            "risk-approver"
            if risk_register in {"guarded", "high-risk"}
            else "writer-operator"
        )
        session_command_brief = [
            f"当前 lane: {session_lane_status}",
            f"当前 ship decision: {session_ship_decision}",
            f"优先动作: {session_priority_queue[0]}",
        ]
        session_runtime_contract = (
            f"mode={session_execution_mode} | readiness={session_release_readiness} | lane={session_lane_status}"
        )
        session_state_snapshot = [
            f"promotion_verdict={promotion_verdict}",
            f"risk_register={risk_register}",
            f"ship_decision={session_ship_decision}",
        ]
        session_transition_rules = [
            "promote + controlled -> scale",
            "de-risk -> stabilize",
            "hold/blocked -> evidence-lane",
        ]
        session_auto_actions = [
            f"根据 {promotion_verdict} 自动选择 {session_lane_status}",
            f"根据 risk_register={risk_register} 自动分配 recovery owner={session_recovery_owner}",
        ]
        session_manual_overrides = [
            "允许 business-owner 人工改写 promotion_verdict",
            "允许 risk-approver 人工冻结扩区或切回 de-risk lane",
        ]
        session_guard_conditions = [
            "risk_register 不能为 high-risk 才允许进入 ship-ready",
            "reader_acceptance_not_improved 时禁止进入 scale 模式",
        ]
        session_entry_criteria = [
            "至少存在 1 个 innovation experiment artifact",
            "baseline_vs_steering 与 reader_sim_acceptance evidence 已生成",
        ]
        session_exit_criteria = [
            "session_priority_queue 已执行完或被重新分派",
            "session_required_review 已完成或升级路径已确认",
        ]
        session_auto_escalations = [
            "high-risk -> risk approver",
            "needs-review + blocked -> business owner",
        ]
        session_override_audit = [
            "记录 promotion_verdict 的人工覆盖原因",
            "记录 lane/queue 人工改写的责任人与时间",
        ]
        session_state_machine = [
            "evidence-lane -> pilot-lane",
            "pilot-lane -> expansion-lane",
            "pilot-lane -> risk-mitigation-lane",
            "risk-mitigation-lane -> pilot-lane",
        ]
        session_allowed_transitions = [
            "hold -> pilot",
            "pilot -> promote",
            "pilot -> de-risk",
            "de-risk -> pilot",
        ]
        session_trigger_matrix = [
            "reader_improved_count 上升 -> 扩大 pilot_scope",
            "risk_register 升级 -> 触发 risk approver escalation",
            "session_blockers 非空 -> 阻断 ship-ready",
        ]
        session_reconciliation_steps = [
            "比对 baseline_vs_steering 与 reader_acceptance 是否一致",
            "比对 risk_register 与 ship_blockers 是否一致",
            "比对 next_action 与 session_priority_queue 是否一致",
        ]
        session_operator_commands = [
            "review ledger",
            "promote lane",
            "switch to de-risk",
            "freeze rollout",
        ]
        session_policy_pack = [
            "优先保证 continuity 与 risk_register 对齐",
            "promotion_verdict 只能在 evidence 完整时进入 promote",
            "高风险 lane 必须经过 risk approver 才能放量",
        ]
        session_slo_contract = [
            "关键 artifact 生成成功率 >= 95%",
            "session_priority_queue 的首项必须可执行",
            "需要 review 的 lane 必须在当前窗口内指派 owner",
        ]
        session_failure_domains = [
            "reader-acceptance-domain",
            "continuity-risk-domain",
            "operator-handoff-domain",
        ]
        session_intervention_matrix = [
            "reader_acceptance 下降 -> 切到 de-risk lane",
            "risk_register 升级 -> 触发 risk approver + freeze rollout",
            "handoff_summary 不清晰 -> 强制补 operator note",
        ]
        session_audit_digest = [
            f"promotion={promotion_verdict}",
            f"risk={risk_register}",
            f"ship={session_ship_decision}",
            f"lane={session_lane_status}",
        ]
        session_governor_mode = (
            "autonomous-scale"
            if session_ship_decision == "ship-ready" and promotion_verdict == "promote"
            else "guarded-operations" if risk_register in {"guarded", "high-risk"} else "supervised-pilot"
        )
        session_decision_bus = [
            f"promotion_verdict -> {promotion_verdict}",
            f"risk_register -> {risk_register}",
            f"ship_decision -> {session_ship_decision}",
        ]
        session_watchdog_rules = [
            "risk_register 升到 high-risk 时自动阻断 ship-ready",
            "reader_acceptance 连续转负时自动推入 blocked_queue",
            "required_review 未完成时禁止切到 scale 模式",
        ]
        session_contingency_routes = [
            "scale 失败 -> de-risk lane",
            "pilot 无改善 -> evidence-lane",
            "blocked-pending-review -> business-owner escalation",
        ]
        session_operating_envelope = [
            f"mode={session_execution_mode}",
            f"window={session_action_window}",
            f"governor={session_governor_mode}",
        ]
        session_control_objectives = [
            "最大化 reader acceptance 的正向变化",
            "最小化 risk_register 与 ship_blockers 的暴露",
            "保证 session_priority_queue 在当前窗口内可执行",
        ]
        session_enforcement_rules = [
            "risk_register=high-risk 时禁止 promote",
            "required_review 未完成时禁止 ship-ready",
            "session_blocked_queue 非空时禁止进入 scale",
        ]
        session_decision_priorities = [
            "1. continuity / risk",
            "2. reader acceptance",
            "3. rollout velocity",
        ]
        session_supervision_hooks = [
            "review gate hook",
            "risk escalation hook",
            "reader-acceptance regression hook",
        ]
        session_telemetry_digest = [
            f"recommendations={len(session_recommendations)}",
            f"risk_labels={len(session_risk_labels)}",
            f"queue_size={len(session_priority_queue)}",
        ]
        session_policy_versions = [
            "control-plane.v1",
            "decision-contract.v1",
            "session-governor.v1",
        ]
        session_safety_budget = [
            "允许 0 个未解释的 high-risk blocker",
            "允许 1 次以内人工 override 未闭环",
        ]
        session_latency_budget = [
            "当前 action window 内优先处理前 2 项 ready queue",
            "需要 review 的 lane 应在本轮 session 内完成指派",
        ]
        session_review_quorum = [
            "writer-operator",
            "continuity-reviewer",
            "reader-feedback-owner",
        ]
        if risk_register in {"guarded", "high-risk"}:
            session_review_quorum.append("risk-approver")
        session_contract_digest = [
            f"governor={session_governor_mode}",
            f"readiness={session_release_readiness}",
            f"quorum={len(session_review_quorum)}",
        ]
        session_compliance_pack = [
            "review quorum 满足后才允许进入 promote/ship-ready",
            "所有 override 必须落入 override audit",
            "高风险 lane 必须存在 risk-approver 责任链",
        ]
        session_failure_budget = [
            "允许 0 个 unresolved high-risk blocker",
            "允许 1 次以内 reader_acceptance 明显回落后立即回滚",
        ]
        session_override_budget = [
            "允许 1 次 business-owner promotion override",
            "允许 1 次 risk-approver lane freeze override",
        ]
        session_reliability_digest = [
            f"ship_decision={session_ship_decision}",
            f"blocked_queue={len(session_blocked_queue)}",
            f"ready_queue={len(session_ready_queue)}",
        ]
        session_governance_checksum = [
            f"policy_versions={len(session_policy_versions)}",
            f"quorum={len(session_review_quorum)}",
            f"audit_items={len(session_override_audit)}",
        ]
        session_authority_map = [
            "writer-operator=lane owner",
            "continuity-reviewer=continuity gate",
            "reader-feedback-owner=acceptance gate",
            "risk-approver=high-risk override",
            "business-owner=final escalation",
        ]
        session_escalation_budget = [
            "允许 1 次 risk-approver escalation",
            "允许 1 次 business-owner final escalation",
        ]
        session_remediation_contract = [
            "reader_acceptance 转负 -> 立即切回 de-risk lane",
            "high-risk blocker 出现 -> freeze rollout + 指派 remediation owner",
        ]
        session_consensus_rules = [
            "promote 需要 review quorum 无阻断",
            "ship-ready 需要 risk_register != high-risk",
            "override 必须记录到 override audit",
        ]
        session_integrity_digest = [
            f"blockers={len(session_blockers)}",
            f"ready={len(session_ready_queue)}",
            f"blocked={len(session_blocked_queue)}",
            f"quorum={len(session_review_quorum)}",
        ]
        session_control_kernel = [
            f"governor={session_governor_mode}",
            f"runtime={session_execution_mode}",
            f"lane={session_lane_status}",
        ]
        session_safety_circuit_breakers = [
            "high-risk blocker -> stop scale",
            "reader_acceptance 连续转负 -> force de-risk",
            "required_review 缺失 -> block ship-ready",
        ]
        session_override_channels = [
            "business-owner override channel",
            "risk-approver freeze channel",
            "writer-operator remediation channel",
        ]
        session_repair_loops = [
            "reader regression -> de-risk -> pilot",
            "risk escalation -> freeze -> remediation -> pilot",
        ]
        session_control_memory = [
            f"last_promotion_verdict={promotion_verdict}",
            f"last_risk_register={risk_register}",
            f"last_ship_decision={session_ship_decision}",
        ]
        session_constraint_register = [
            "ship-ready 受 risk_register 和 required_review 约束",
            "scale 受 reader_acceptance 与 blocked_queue 约束",
            "override 受 override_budget 与 override_audit 约束",
        ]
        session_safety_invariants = [
            "high-risk 与 ship-ready 不可同时成立",
            "session_blocked_queue 非空时不可直接 promote",
            "required_review 未清零前不可进入 autonomous-scale",
        ]
        session_repair_budget = [
            "允许 1 次 lane freeze 后重试",
            "允许 1 次 reader_acceptance 修复回路后再评估 promote",
        ]
        session_runtime_digest = [
            f"mode={session_execution_mode}",
            f"lane={session_lane_status}",
            f"ready={len(session_ready_queue)}",
            f"blocked={len(session_blocked_queue)}",
        ]
        session_control_fabric = [
            f"governor={session_governor_mode}",
            f"contract={len(session_contract_digest)}-signals",
            f"kernel={len(session_control_kernel)}-signals",
        ]
        session_guardrail_matrix = [
            "risk_register=high-risk -> block promote",
            "blocked_queue>0 -> block scale",
            "required_review pending -> block ship-ready",
        ]
        session_override_protocol = [
            "business-owner override 必须进入 override_audit",
            "risk-approver freeze 后必须登记 remediation_contract",
        ]
        session_failure_isolation = [
            "reader acceptance failure 限制在 pilot lane",
            "risk escalation failure 限制在 remediation lane",
            "operator handoff failure 限制在 review queue",
        ]
        session_runtime_manifest = [
            f"execution_mode={session_execution_mode}",
            f"release_readiness={session_release_readiness}",
            f"governor_mode={session_governor_mode}",
        ]
        session_control_bus = [
            f"promotion={promotion_verdict}",
            f"risk={risk_register}",
            f"ship={session_ship_decision}",
            f"lane={session_lane_status}",
        ]
        session_event_channels = [
            "reader-acceptance-events",
            "risk-escalation-events",
            "review-completion-events",
        ]
        session_runtime_priorities = [
            "P0: ship blockers",
            "P1: required review",
            "P2: ready queue rollout",
        ]
        session_alert_routes = [
            "high-risk -> risk-approver",
            "blocked ship -> business-owner",
            "reader regression -> writer-operator",
        ]
        session_state_checkpoint = [
            f"promotion_verdict={promotion_verdict}",
            f"risk_register={risk_register}",
            f"ship_decision={session_ship_decision}",
            f"execution_mode={session_execution_mode}",
        ]
        session_execution_graph = [
            "evidence -> pilot -> review -> promote",
            "pilot -> de-risk -> remediation -> pilot",
            "blocked -> escalation -> review",
        ]
        session_signal_registry = [
            "promotion_verdict",
            "risk_register",
            "session_ship_decision",
            "reader_acceptance",
            "session_ready_queue",
        ]
        session_action_contract = [
            "ready_queue 首项必须对应 next_action",
            "blocked_queue 非空时必须存在 escalation_path 或 remediation_contract",
            "promotion_verdict 变化时必须更新 state_checkpoint",
        ]
        session_backpressure_rules = [
            "blocked_queue>0 时压缩 ready_queue 执行窗口",
            "required_review 未完成时暂停 scale lane",
            "risk_register 升级时优先处理 remediation_contract",
        ]
        session_runtime_proof = [
            f"graph_edges={len(session_execution_graph)}",
            f"signals={len(session_signal_registry)}",
            f"contracts={len(session_action_contract)}",
        ]
        session_supervisory_contract = [
            "每轮 session 必须产生 promotion/risk/handoff 三类摘要",
            "每轮 blocked_queue 变化必须可追踪到 escalation_path 或 remediation_contract",
        ]
        session_recovery_matrix = [
            "reader regression -> de-risk -> pilot",
            "high-risk blocker -> freeze -> remediation -> review",
            "ship not ready -> escalation -> re-evaluate readiness",
        ]
        session_signal_budget = [
            "允许 5 类核心信号参与 governor 决策",
            "允许 3 条以内关键优先级信号进入 command brief",
        ]
        session_checkpoint_policy = [
            "每轮 session 至少写入一次 state checkpoint",
            "promotion/risk/ship 任一变化都必须刷新 checkpoint",
        ]
        session_operating_ledger = [
            f"artifacts={len(ledger_entries)}",
            f"ready_queue={len(session_ready_queue)}",
            f"blocked_queue={len(session_blocked_queue)}",
            f"escalations={len(session_escalation_path)}",
        ]
        session_governance_fabric = [
            f"governor={session_governor_mode}",
            f"quorum={len(session_review_quorum)}",
            f"authority={len(session_authority_map)}",
        ]
        session_checkpoint_contract = [
            "promotion/risk/ship 变化必须刷新 state checkpoint",
            "blocked_queue 变化必须刷新 session-state artifact",
            "ship-ready 前必须重新核验 checkpoint contract",
        ]
        session_supervision_priorities = [
            "P0: ship blockers / risk",
            "P1: required review / escalation",
            "P2: rollout readiness / queue execution",
        ]
        session_ledger_consistency_rules = [
            "ledger 与 session-state 必须共享同一 promotion_verdict",
            "ledger 与 decision note 必须共享同一 next_action",
            "ledger 与 risk register 必须共享同一 business_risk_label",
        ]
        session_runtime_attestation = [
            f"state_artifacts={len(ledger_entries)}",
            f"checkpoints={len(session_state_checkpoint)}",
            f"contracts={len(session_contract_digest)}",
        ]
        session_runtime_mesh = [
            f"governor={session_governor_mode}",
            f"bus={len(session_control_bus)}-signals",
            f"fabric={len(session_governance_fabric)}-signals",
        ]
        session_policy_router = [
            "risk_register -> compliance_pack",
            "promotion_verdict -> rollout/ship lane",
            "blocked_queue -> remediation/escalation lane",
        ]
        session_checkpoint_ring = [
            "state_checkpoint",
            "runtime_manifest",
            "contract_digest",
            "runtime_attestation",
        ]
        session_audit_stream = [
            "override_audit",
            "audit_digest",
            "governance_checksum",
        ]
        session_operating_signature = [
            f"mesh={len(session_runtime_mesh)}",
            f"router={len(session_policy_router)}",
            f"ring={len(session_checkpoint_ring)}",
        ]
        session_policy_mesh = [
            f"policy_versions={len(session_policy_versions)}",
            f"compliance_pack={len(session_compliance_pack)}",
            f"governance_fabric={len(session_governance_fabric)}",
        ]
        session_enforcement_bus = [
            "guard_conditions -> enforcement_rules",
            "watchdog_rules -> alert_routes",
            "compliance_pack -> review_quorum",
        ]
        session_runtime_sentry = [
            "watch blocked_queue",
            "watch risk_register",
            "watch reader_acceptance deltas",
        ]
        session_checkpoint_audit_chain = [
            "state_checkpoint -> checkpoint_contract",
            "checkpoint_contract -> runtime_attestation",
            "runtime_attestation -> audit_stream",
        ]
        session_operating_posture = [
            f"governor={session_governor_mode}",
            f"execution={session_execution_mode}",
            f"readiness={session_release_readiness}",
        ]
        session_attestation_chain = [
            "state_checkpoint -> runtime_attestation",
            "runtime_attestation -> checkpoint_audit_chain",
            "checkpoint_audit_chain -> control_verdict",
        ]
        session_trust_zones = [
            "operator-zone",
            "review-zone",
            "risk-zone",
            "business-zone",
        ]
        session_policy_attestors = [
            "writer-operator",
            "continuity-reviewer",
            "risk-approver",
        ]
        session_recovery_posture = [
            "风险升高时进入 guarded recovery",
            "reader regression 时进入 de-risk recovery",
            "blocked ship 时进入 escalation recovery",
        ]
        session_control_verdict = [
            f"ship={session_ship_decision}",
            f"risk={risk_register}",
            f"governor={session_governor_mode}",
        ]
        session_protocol_stack = [
            "policy-kernel",
            "governance-fabric",
            "runtime-mesh",
            "execution-kernel",
        ]
        session_trust_contract = [
            "attestation chain 必须闭合",
            "policy attestors 必须覆盖关键 review 角色",
            "control verdict 必须可回溯到 runtime attestation",
        ]
        session_recovery_authority = [
            "writer-operator 负责普通 remediation",
            "risk-approver 负责 high-risk recovery",
            "business-owner 负责 blocked ship 的最终决断",
        ]
        session_audit_checkpoint_map = [
            "state_checkpoint -> checkpoint_ring",
            "checkpoint_ring -> audit_stream",
            "audit_stream -> governance_checksum",
        ]
        session_runtime_certificate = [
            f"governor={session_governor_mode}",
            f"mesh={len(session_runtime_mesh)}",
            f"contracts={len(session_contract_digest)}",
        ]
        session_governance_topology = [
            "operator -> review -> risk -> business",
            "policy kernel -> checkpoint contract -> audit stream",
            "runtime mesh -> control bus -> execution kernel",
        ]
        session_protocol_budget = [
            "允许 3 条核心协议路径并行",
            "禁止未经 attestation 的 ship-ready 路径绕过 review quorum",
        ]
        session_certificate_chain = [
            "runtime_certificate -> control_verdict",
            "control_verdict -> governance_checksum",
            "governance_checksum -> audit_digest",
        ]
        session_recovery_authorizations = [
            "writer-operator 可执行普通 remediation",
            "risk-approver 可执行 guarded recovery",
            "business-owner 可批准 blocked ship 的最终恢复路径",
        ]
        session_control_attestation = [
            f"attestors={len(session_policy_attestors)}",
            f"trust_zones={len(session_trust_zones)}",
            f"certificate_chain={len(session_certificate_chain)}",
        ]
        session_assurance_contract = [
            "control verdict 必须与 governance checksum 对齐",
            "runtime certificate 必须可追溯到 attestation chain",
            "recovery posture 必须与 recovery authority 一致",
        ]
        session_policy_checksum = [
            f"policy_mesh={len(session_policy_mesh)}",
            f"policy_versions={len(session_policy_versions)}",
            f"compliance_pack={len(session_compliance_pack)}",
        ]
        session_runtime_alignment = [
            f"lane={session_lane_status} 与 mode={session_execution_mode} 对齐",
            f"governor={session_governor_mode} 与 readiness={session_release_readiness} 对齐",
            f"ship={session_ship_decision} 与 risk={risk_register} 对齐",
        ]
        session_recovery_certainty = [
            f"recovery_owner={session_recovery_owner}",
            f"recovery_routes={len(session_recovery_plan)}",
            f"remediation_contracts={len(session_remediation_contract)}",
        ]
        session_operator_assurance = [
            "operator 可以从 index 读取 promotion/risk/queue/checkpoint 全量信号",
            "operator 可以从 session-state.json 读取机读状态快照",
            "operator 可依据 control verdict 与 runtime certificate 执行推广或冻结",
        ]
        session_meta_governor = [
            f"governor_mode={session_governor_mode}",
            f"control_verdict={session_ship_decision}",
            f"risk_register={risk_register}",
        ]
        session_policy_integrity = [
            f"policy_versions={len(session_policy_versions)}",
            f"checksum={len(session_policy_checksum)}",
            f"attestors={len(session_policy_attestors)}",
        ]
        session_runtime_consistency = [
            f"execution_mode={session_execution_mode} 与 lane={session_lane_status} 对齐",
            f"release_readiness={session_release_readiness} 与 ship={session_ship_decision} 对齐",
        ]
        session_override_accountability = [
            "所有 override 必须进入 override_audit",
            "override channel 必须可追溯到 authority_map",
        ]
        session_control_confidence = [
            f"confidence_level={decision_confidence or 'unknown'}",
            f"quorum={len(session_review_quorum)}",
            f"attestation={len(session_control_attestation)}",
        ]
        session_executive_contract = [
            "promote 必须满足 review quorum + control verdict + runtime certificate",
            "blocked ship 必须进入 executive review",
            "override 必须绑定 accountable authority",
        ]
        session_supervision_certificate = [
            f"supervision_hooks={len(session_supervision_hooks)}",
            f"review_quorum={len(session_review_quorum)}",
            f"audit_stream={len(session_audit_stream)}",
        ]
        session_override_liability = [
            "business-owner override 对最终 ship 结果负责",
            "risk-approver freeze override 对风险控制负责",
        ]
        session_operating_authority = [
            "lane_owner=writer-operator",
            f"risk_owner={session_recovery_owner}",
            f"ship_authority={session_ship_decision}",
        ]
        session_authority_certificate = [
            "lane_owner=writer-operator",
            f"risk_owner={session_recovery_owner}",
            f"quorum={len(session_review_quorum)}",
        ]
        session_policy_envelope = [
            f"policy_versions={len(session_policy_versions)}",
            f"compliance={len(session_compliance_pack)}",
            f"slo={len(session_slo_contract)}",
        ]
        session_escalation_authority = [
            "risk-approver 可升级 high-risk lane",
            "business-owner 可裁决 blocked ship",
            "writer-operator 可发起普通 remediation escalation",
        ]
        session_assurance_digest = [
            f"assurance={len(session_assurance_contract)}",
            f"attestation={len(session_control_attestation)}",
            f"integrity={len(session_policy_integrity)}",
        ]
        session_governance_verdict = [
            f"ship={session_ship_decision}",
            f"risk={risk_register}",
            f"confidence={decision_confidence or 'unknown'}",
        ]
        session_governance_mesh = [
            f"authority={len(session_authority_map)}",
            f"attestors={len(session_policy_attestors)}",
            f"quorum={len(session_review_quorum)}",
        ]
        session_attestation_budget = [
            "允许 1 次附加 attestation 复核",
            "允许 1 次 checkpoint 证书补签",
        ]
        session_policy_fallbacks = [
            "promote 失败 -> 回退到 pilot policy",
            "high-risk -> 回退到 guarded policy",
            "blocked ship -> 回退到 evidence policy",
        ]
        session_recovery_routing = [
            "reader regression -> writer-operator",
            "high-risk -> risk-approver",
            "blocked ship -> business-owner",
        ]
        session_runtime_verdict = [
            f"execution={session_execution_mode}",
            f"ship={session_ship_decision}",
            f"confidence={decision_confidence or 'unknown'}",
        ]
        session_control_plane_closure = [
            "control bus 与 runtime manifest 必须闭合",
            "governance verdict 与 ship decision 必须一致",
            "session-state artifact 与 index 必须共享同一 promotion/risk 结论",
        ]
        session_exec_fabric = [
            f"lane={session_lane_status}",
            f"governor={session_governor_mode}",
            f"mesh={len(session_governance_mesh)}",
        ]
        session_authority_routes = [
            "writer-operator -> continuity-reviewer -> reader-feedback-owner",
            "reader-feedback-owner -> risk-approver -> business-owner",
        ]
        session_assurance_chain = [
            "policy_checksum -> runtime_alignment -> control_confidence",
            "control_confidence -> governance_verdict -> runtime_certificate",
        ]
        session_runtime_seal = [
            f"governor={session_governor_mode}",
            f"ship={session_ship_decision}",
            f"risk={risk_register}",
        ]
        session_authority_fabric = [
            f"authority_map={len(session_authority_map)}",
            f"authority_certificate={len(session_authority_certificate)}",
            f"escalation_authority={len(session_escalation_authority)}",
        ]
        session_override_chain = [
            "business-owner override -> override_audit",
            "risk-approver freeze -> remediation_contract",
            "writer-operator remediation -> session_repair_loops",
        ]
        session_control_closure_audit = [
            "promotion/risk/ship 三元状态与 session-state 一致",
            "authority routes 与 escalation path 一致",
            "runtime seal 与 governance verdict 一致",
        ]
        session_runtime_witness = [
            f"mesh={len(session_governance_mesh)}",
            f"attestors={len(session_policy_attestors)}",
            f"contracts={len(session_contract_digest)}",
        ]
        session_governance_posture = [
            f"governor={session_governor_mode}",
            f"readiness={session_release_readiness}",
            f"authority={session_ship_decision}",
        ]
        session_operating_charter = [
            "当前 session 必须保持 promotion/risk/ship 三元结论可追踪",
            "当前 session 必须保证 ready/blocked queue 与 remediation 合同一致",
        ]
        session_control_charter = [
            "control plane 负责收束 decision/bus/checkpoint/runtime 结论",
            "session-state 与 index 必须共享同一控制结论",
        ]
        session_governance_charter = [
            "governance verdict 必须通过 attestation 与 checksum 双重校验",
            "executive-governance 负责最终 ship authority 约束",
        ]
        session_runtime_authority_digest = [
            "lane_owner=writer-operator",
            f"risk_owner={session_recovery_owner}",
            f"ship_authority={session_ship_decision}",
        ]
        session_final_control_verdict = [
            f"promotion={promotion_verdict}",
            f"risk={risk_register}",
            f"ship={session_ship_decision}",
            f"governor={session_governor_mode}",
        ]
        session_governance_closure = [
            "promotion/risk/ship 三元结论已闭合",
            "authority / assurance / runtime 结论已闭合",
            "index 与 session-state 可共享统一控制结论",
        ]
        session_authority_verdict = [
            "lane_owner=writer-operator",
            f"risk_owner={session_recovery_owner}",
            f"ship_authority={session_ship_decision}",
        ]
        session_runtime_horizon = [
            f"action_window={session_action_window}",
            f"queue={len(session_priority_queue)}",
            f"release_readiness={session_release_readiness}",
        ]
        session_supervision_digest = [
            f"hooks={len(session_supervision_hooks)}",
            f"quorum={len(session_review_quorum)}",
            f"audit={len(session_override_audit)}",
        ]
        session_control_summary = [
            f"governor={session_governor_mode}",
            f"verdict={session_ship_decision}",
            f"confidence={decision_confidence or 'unknown'}",
        ]
        session_operating_system_contract = [
            "session-state / index / decision artifact 必须共享同一控制结论",
            "authority, governance, runtime 三层字段必须可互相校验",
            "任何 promote/ship-ready 必须可回溯到 attestation + runtime proof",
        ]
        session_control_checkpoint_digest = [
            f"state={len(session_state_checkpoint)}",
            f"contract={len(session_checkpoint_contract)}",
            f"ring={len(session_checkpoint_ring)}",
        ]
        session_authority_signature = [
            "lane_owner=writer-operator",
            f"risk_owner={session_recovery_owner}",
            f"business_route={len(session_escalation_path)}",
        ]
        session_recovery_escalation_mesh = [
            "reader regression -> de-risk -> remediation -> pilot",
            "high-risk -> risk-approver -> business-owner",
            "blocked ship -> executive review -> closure",
        ]
        session_final_operating_posture = [
            f"governor={session_governor_mode}",
            f"runtime={session_execution_mode}",
            f"verdict={session_ship_decision}",
            f"risk={risk_register}",
        ]
        session_command_mesh = [
            "review ledger -> decide lane",
            "decide lane -> assign next action",
            "assign next action -> refresh state checkpoint",
        ]
        session_authority_fabric_v2 = [
            f"authority_map={len(session_authority_map)}",
            f"authority_certificate={len(session_authority_certificate)}",
            f"authority_routes={len(session_authority_routes)}",
        ]
        session_closure_attestation = [
            f"closure={len(session_control_plane_closure)}",
            f"attestation={len(session_control_attestation)}",
            f"governance={len(session_governance_closure)}",
        ]
        session_operating_charter_mesh = [
            f"operating_charter={len(session_operating_charter)}",
            f"control_charter={len(session_control_charter)}",
            f"governance_charter={len(session_governance_charter)}",
        ]
        session_final_runtime_verdict = [
            f"mode={session_execution_mode}",
            f"ship={session_ship_decision}",
            f"governor={session_governor_mode}",
            f"confidence={decision_confidence or 'unknown'}",
        ]
        session_executive_command_mesh = [
            "review ledger -> executive lane selection",
            "executive lane selection -> authority dispatch",
            "authority dispatch -> final runtime verdict",
        ]
        session_authority_control_matrix = [
            "writer-operator controls lane execution",
            "risk-approver controls guarded / high-risk lanes",
            "business-owner controls blocked-ship final escalation",
        ]
        session_runtime_closure_proof = [
            f"closure={len(session_control_plane_closure)}",
            f"checkpoint={len(session_control_checkpoint_digest)}",
            f"verdict={len(session_final_control_verdict)}",
        ]
        session_governance_signal_chain = [
            "promotion_verdict -> governance_verdict -> final_runtime_verdict",
            "risk_register -> authority_verdict -> operating_posture",
        ]
        session_operating_system_verdict = [
            f"runtime={session_execution_mode}",
            f"authority={session_ship_decision}",
            f"governor={session_governor_mode}",
            f"risk={risk_register}",
        ]
        session_governance_backbone = [
            f"governor={session_governor_mode}",
            f"mesh={len(session_governance_mesh)}",
            f"quorum={len(session_review_quorum)}",
        ]
        session_control_lattice = [
            "decision -> governance -> runtime -> recovery",
            "authority -> attestation -> verdict",
            "policy -> checksum -> enforcement",
        ]
        session_authority_bus = [
            "writer-operator -> continuity-reviewer",
            "reader-feedback-owner -> risk-approver",
            "risk-approver -> business-owner",
        ]
        session_runtime_witness_chain = [
            "state_checkpoint -> runtime_witness",
            "runtime_witness -> runtime_certificate",
            "runtime_certificate -> final_runtime_verdict",
        ]
        session_os_control_digest = [
            f"backbone={len(session_governance_backbone)}",
            f"lattice={len(session_control_lattice)}",
            f"authority_bus={len(session_authority_bus)}",
        ]
        session_transition_preview = (
            "pilot-lane -> expansion-lane"
            if promotion_verdict == "promote" and risk_register == "controlled"
            else "pilot-lane -> risk-mitigation-lane"
            if promotion_verdict == "de-risk"
            else "evidence-lane -> pilot-lane"
        )
        session_checkpoint_preview = [
            "promotion_verdict",
            "risk_register",
            "session_ship_decision",
            "session_recovery_owner",
        ]
        lines.append("\n### Control Surface EntryPoints")
        lines.append("- primary_operator_entrypoint: writer-imitate-operator-surface.md")
        lines.append("- legacy_operator_entrypoint: writer-imitate-legacy-contract-surface.md")
        lines.append("- legacy_retirement_preview: writer-imitate-legacy-retirement-preview.md")
        lines.append("- live_control_state: writer-imitate-live-control-state.md")
        lines.append("- live_mutation_preview: writer-imitate-live-mutation-preview.md")
        lines.append("- live_validation_state: writer-imitate-live-validation-state.md")
        lines.append("- external_runtime_executor_readiness: writer-imitate-external-runtime-executor-readiness.md")
        lines.append("- external_runtime_executor_preview: writer-imitate-external-runtime-executor-preview.md")
        lines.append("- primary_operator_role: default-operator-home")
        lines.append("- legacy_operator_role: compatibility-governance-surface")
        lines.append("- legacy_retirement_preview_role: retirement-preview-surface")
        lines.append("- live_control_state_role: preview-to-live-bridge-surface")
        lines.append("- live_mutation_preview_role: live-mutation-review-surface")
        lines.append("- live_validation_state_role: local-validation-bridge-surface")
        lines.append("- external_runtime_executor_readiness_role: runtime-executor-gate-surface")
        lines.append("- external_runtime_executor_preview_role: runtime-executor-review-surface")
        lines.append("- display_policy: primary-first-legacy-secondary")
        lines.append("\n### Operator-Facing Stable Contract")
        lines.append(f"- promotion_verdict: {promotion_verdict}")
        lines.append(f"- risk_register: {risk_register}")
        lines.append(f"- session_ship_decision: {session_ship_decision}")
        lines.append(f"- session_lane_status: {session_lane_status}")
        lines.append(f"- session_execution_mode: {session_execution_mode}")
        lines.append(f"- session_release_readiness: {session_release_readiness}")
        lines.append(f"- session_priority_queue: {'；'.join(session_priority_queue)}")
        lines.append(
            f"- session_ready_queue: {'；'.join(session_ready_queue) if session_ready_queue else 'none'}"
        )
        lines.append(
            f"- session_blocked_queue: {'；'.join(session_blocked_queue) if session_blocked_queue else 'none'}"
        )
        lines.append(f"- session_recovery_owner: {session_recovery_owner}")
        lines.append(f"- session_required_review: {'；'.join(session_required_review)}")
        lines.append(f"- session_escalation_path: {'；'.join(session_escalation_path)}")
        lines.append(f"- session_owner_handoff: {'；'.join(session_owner_handoff)}")
        lines.append(f"- session_transition_queue: next={session_transition_preview}")
        lines.append(
            f"- session_checkpoint_mutations: fields={len(session_checkpoint_preview)} | first={session_checkpoint_preview[0]}"
        )
        lines.append(
            f"- session_live_ops_board: ship={session_ship_decision}；promotion={promotion_verdict}；risk={risk_register}"
        )
        lines.append(
            f"- session_digest_registry: runtime={session_runtime_contract}；summary={session_control_summary[0]}"
        )

        lines.append("\n### Full Session Field Surface")
        lines.append(f"- promotion_verdict: {promotion_verdict}")
        lines.append(f"- risk_register: {risk_register}")
        lines.append(f"- handoff_summary: {handoff_summary}")
        lines.append(f"- session_ship_decision: {session_ship_decision}")
        lines.append(f"- session_lane_status: {session_lane_status}")
        lines.append(f"- session_release_readiness: {session_release_readiness}")
        lines.append(f"- session_execution_mode: {session_execution_mode}")
        lines.append(f"- session_action_window: {session_action_window}")
        lines.append(f"- session_runtime_contract: {session_runtime_contract}")
        lines.append(f"- session_state_snapshot: {'；'.join(session_state_snapshot)}")
        lines.append(f"- session_transition_rules: {'；'.join(session_transition_rules)}")
        lines.append(f"- session_auto_actions: {'；'.join(session_auto_actions)}")
        lines.append(f"- session_manual_overrides: {'；'.join(session_manual_overrides)}")
        lines.append(f"- session_guard_conditions: {'；'.join(session_guard_conditions)}")
        lines.append(f"- session_entry_criteria: {'；'.join(session_entry_criteria)}")
        lines.append(f"- session_exit_criteria: {'；'.join(session_exit_criteria)}")
        lines.append(f"- session_auto_escalations: {'；'.join(session_auto_escalations)}")
        lines.append(f"- session_override_audit: {'；'.join(session_override_audit)}")
        lines.append(f"- session_state_machine: {'；'.join(session_state_machine)}")
        lines.append(f"- session_allowed_transitions: {'；'.join(session_allowed_transitions)}")
        lines.append(f"- session_trigger_matrix: {'；'.join(session_trigger_matrix)}")
        lines.append(f"- session_reconciliation_steps: {'；'.join(session_reconciliation_steps)}")
        lines.append(f"- session_operator_commands: {'；'.join(session_operator_commands)}")
        lines.append(f"- session_policy_pack: {'；'.join(session_policy_pack)}")
        lines.append(f"- session_slo_contract: {'；'.join(session_slo_contract)}")
        lines.append(f"- session_failure_domains: {'；'.join(session_failure_domains)}")
        lines.append(f"- session_intervention_matrix: {'；'.join(session_intervention_matrix)}")
        lines.append(f"- session_audit_digest: {'；'.join(session_audit_digest)}")
        lines.append(f"- session_governor_mode: {session_governor_mode}")
        lines.append(f"- session_decision_bus: {'；'.join(session_decision_bus)}")
        lines.append(f"- session_watchdog_rules: {'；'.join(session_watchdog_rules)}")
        lines.append(f"- session_contingency_routes: {'；'.join(session_contingency_routes)}")
        lines.append(f"- session_operating_envelope: {'；'.join(session_operating_envelope)}")
        lines.append(f"- session_control_objectives: {'；'.join(session_control_objectives)}")
        lines.append(f"- session_enforcement_rules: {'；'.join(session_enforcement_rules)}")
        lines.append(f"- session_decision_priorities: {'；'.join(session_decision_priorities)}")
        lines.append(f"- session_supervision_hooks: {'；'.join(session_supervision_hooks)}")
        lines.append(f"- session_telemetry_digest: {'；'.join(session_telemetry_digest)}")
        lines.append(f"- session_policy_versions: {'；'.join(session_policy_versions)}")
        lines.append(f"- session_safety_budget: {'；'.join(session_safety_budget)}")
        lines.append(f"- session_latency_budget: {'；'.join(session_latency_budget)}")
        lines.append(f"- session_review_quorum: {'；'.join(session_review_quorum)}")
        lines.append(f"- session_contract_digest: {'；'.join(session_contract_digest)}")
        lines.append(f"- session_compliance_pack: {'；'.join(session_compliance_pack)}")
        lines.append(f"- session_failure_budget: {'；'.join(session_failure_budget)}")
        lines.append(f"- session_override_budget: {'；'.join(session_override_budget)}")
        lines.append(f"- session_reliability_digest: {'；'.join(session_reliability_digest)}")
        lines.append(f"- session_governance_checksum: {'；'.join(session_governance_checksum)}")
        lines.append(f"- session_authority_map: {'；'.join(session_authority_map)}")
        lines.append(f"- session_escalation_budget: {'；'.join(session_escalation_budget)}")
        lines.append(f"- session_remediation_contract: {'；'.join(session_remediation_contract)}")
        lines.append(f"- session_consensus_rules: {'；'.join(session_consensus_rules)}")
        lines.append(f"- session_integrity_digest: {'；'.join(session_integrity_digest)}")
        lines.append(f"- session_control_memory: {'；'.join(session_control_memory)}")
        lines.append(f"- session_constraint_register: {'；'.join(session_constraint_register)}")
        lines.append(f"- session_safety_invariants: {'；'.join(session_safety_invariants)}")
        lines.append(f"- session_repair_budget: {'；'.join(session_repair_budget)}")
        lines.append(f"- session_runtime_digest: {'；'.join(session_runtime_digest)}")
        lines.append(f"- session_control_fabric: {'；'.join(session_control_fabric)}")
        lines.append(f"- session_guardrail_matrix: {'；'.join(session_guardrail_matrix)}")
        lines.append(f"- session_override_protocol: {'；'.join(session_override_protocol)}")
        lines.append(f"- session_failure_isolation: {'；'.join(session_failure_isolation)}")
        lines.append(f"- session_runtime_manifest: {'；'.join(session_runtime_manifest)}")
        lines.append(f"- session_control_bus: {'；'.join(session_control_bus)}")
        lines.append(f"- session_event_channels: {'；'.join(session_event_channels)}")
        lines.append(f"- session_runtime_priorities: {'；'.join(session_runtime_priorities)}")
        lines.append(f"- session_alert_routes: {'；'.join(session_alert_routes)}")
        lines.append(f"- session_state_checkpoint: {'；'.join(session_state_checkpoint)}")
        lines.append(f"- session_execution_graph: {'；'.join(session_execution_graph)}")
        lines.append(f"- session_signal_registry: {'；'.join(session_signal_registry)}")
        lines.append(f"- session_action_contract: {'；'.join(session_action_contract)}")
        lines.append(f"- session_backpressure_rules: {'；'.join(session_backpressure_rules)}")
        lines.append(f"- session_runtime_proof: {'；'.join(session_runtime_proof)}")
        lines.append(f"- session_supervisory_contract: {'；'.join(session_supervisory_contract)}")
        lines.append(f"- session_recovery_matrix: {'；'.join(session_recovery_matrix)}")
        lines.append(f"- session_signal_budget: {'；'.join(session_signal_budget)}")
        lines.append(f"- session_checkpoint_policy: {'；'.join(session_checkpoint_policy)}")
        lines.append(f"- session_operating_ledger: {'；'.join(session_operating_ledger)}")
        lines.append(f"- session_governance_fabric: {'；'.join(session_governance_fabric)}")
        lines.append(f"- session_checkpoint_contract: {'；'.join(session_checkpoint_contract)}")
        lines.append(f"- session_supervision_priorities: {'；'.join(session_supervision_priorities)}")
        lines.append(f"- session_ledger_consistency_rules: {'；'.join(session_ledger_consistency_rules)}")
        lines.append(f"- session_runtime_attestation: {'；'.join(session_runtime_attestation)}")
        lines.append(f"- session_runtime_mesh: {'；'.join(session_runtime_mesh)}")
        lines.append(f"- session_policy_router: {'；'.join(session_policy_router)}")
        lines.append(f"- session_checkpoint_ring: {'；'.join(session_checkpoint_ring)}")
        lines.append(f"- session_audit_stream: {'；'.join(session_audit_stream)}")
        lines.append(f"- session_operating_signature: {'；'.join(session_operating_signature)}")
        lines.append(f"- session_policy_mesh: {'；'.join(session_policy_mesh)}")
        lines.append(f"- session_enforcement_bus: {'；'.join(session_enforcement_bus)}")
        lines.append(f"- session_runtime_sentry: {'；'.join(session_runtime_sentry)}")
        lines.append(f"- session_checkpoint_audit_chain: {'；'.join(session_checkpoint_audit_chain)}")
        lines.append(f"- session_operating_posture: {'；'.join(session_operating_posture)}")
        lines.append(f"- session_attestation_chain: {'；'.join(session_attestation_chain)}")
        lines.append(f"- session_trust_zones: {'；'.join(session_trust_zones)}")
        lines.append(f"- session_policy_attestors: {'；'.join(session_policy_attestors)}")
        lines.append(f"- session_recovery_posture: {'；'.join(session_recovery_posture)}")
        lines.append("\n#### Legacy Verdict/Digest Compatibility Layer")
        lines.append(f"- session_control_verdict: {'；'.join(session_control_verdict)}")
        lines.append(f"- session_protocol_stack: {'；'.join(session_protocol_stack)}")
        lines.append(f"- session_trust_contract: {'；'.join(session_trust_contract)}")
        lines.append(f"- session_recovery_authority: {'；'.join(session_recovery_authority)}")
        lines.append(f"- session_audit_checkpoint_map: {'；'.join(session_audit_checkpoint_map)}")
        lines.append(f"- session_runtime_certificate: {'；'.join(session_runtime_certificate)}")
        lines.append(f"- session_governance_topology: {'；'.join(session_governance_topology)}")
        lines.append(f"- session_protocol_budget: {'；'.join(session_protocol_budget)}")
        lines.append(f"- session_certificate_chain: {'；'.join(session_certificate_chain)}")
        lines.append(f"- session_recovery_authorizations: {'；'.join(session_recovery_authorizations)}")
        lines.append(f"- session_control_attestation: {'；'.join(session_control_attestation)}")
        lines.append(f"- session_assurance_contract: {'；'.join(session_assurance_contract)}")
        lines.append(f"- session_policy_checksum: {'；'.join(session_policy_checksum)}")
        lines.append(f"- session_runtime_alignment: {'；'.join(session_runtime_alignment)}")
        lines.append(f"- session_recovery_certainty: {'；'.join(session_recovery_certainty)}")
        lines.append(f"- session_operator_assurance: {'；'.join(session_operator_assurance)}")
        lines.append(f"- session_meta_governor: {'；'.join(session_meta_governor)}")
        lines.append(f"- session_policy_integrity: {'；'.join(session_policy_integrity)}")
        lines.append(f"- session_runtime_consistency: {'；'.join(session_runtime_consistency)}")
        lines.append(f"- session_override_accountability: {'；'.join(session_override_accountability)}")
        lines.append(f"- session_control_confidence: {'；'.join(session_control_confidence)}")
        lines.append(f"- session_executive_contract: {'；'.join(session_executive_contract)}")
        lines.append(f"- session_supervision_certificate: {'；'.join(session_supervision_certificate)}")
        lines.append(f"- session_override_liability: {'；'.join(session_override_liability)}")
        lines.append(f"- session_operating_authority: {'；'.join(session_operating_authority)}")
        lines.append(f"- session_authority_certificate: {'；'.join(session_authority_certificate)}")
        lines.append(f"- session_policy_envelope: {'；'.join(session_policy_envelope)}")
        lines.append(f"- session_escalation_authority: {'；'.join(session_escalation_authority)}")
        lines.append(f"- session_assurance_digest: {'；'.join(session_assurance_digest)}")
        lines.append(f"- session_governance_verdict: {'；'.join(session_governance_verdict)}")
        lines.append(f"- session_governance_mesh: {'；'.join(session_governance_mesh)}")
        lines.append(f"- session_attestation_budget: {'；'.join(session_attestation_budget)}")
        lines.append(f"- session_policy_fallbacks: {'；'.join(session_policy_fallbacks)}")
        lines.append(f"- session_recovery_routing: {'；'.join(session_recovery_routing)}")
        lines.append(f"- session_runtime_verdict: {'；'.join(session_runtime_verdict)}")
        lines.append(f"- session_control_plane_closure: {'；'.join(session_control_plane_closure)}")
        lines.append(f"- session_exec_fabric: {'；'.join(session_exec_fabric)}")
        lines.append(f"- session_authority_routes: {'；'.join(session_authority_routes)}")
        lines.append(f"- session_assurance_chain: {'；'.join(session_assurance_chain)}")
        lines.append(f"- session_runtime_seal: {'；'.join(session_runtime_seal)}")
        lines.append(f"- session_authority_fabric: {'；'.join(session_authority_fabric)}")
        lines.append(f"- session_override_chain: {'；'.join(session_override_chain)}")
        lines.append(f"- session_control_closure_audit: {'；'.join(session_control_closure_audit)}")
        lines.append(f"- session_runtime_witness: {'；'.join(session_runtime_witness)}")
        lines.append(f"- session_governance_posture: {'；'.join(session_governance_posture)}")
        lines.append(f"- session_operating_charter: {'；'.join(session_operating_charter)}")
        lines.append(f"- session_control_charter: {'；'.join(session_control_charter)}")
        lines.append(f"- session_governance_charter: {'；'.join(session_governance_charter)}")
        lines.append(f"- session_runtime_authority_digest: {'；'.join(session_runtime_authority_digest)}")
        lines.append(f"- session_final_control_verdict: {'；'.join(session_final_control_verdict)}")
        lines.append(f"- session_command_mesh: {'；'.join(session_command_mesh)}")
        lines.append(f"- session_authority_fabric_v2: {'；'.join(session_authority_fabric_v2)}")
        lines.append(f"- session_closure_attestation: {'；'.join(session_closure_attestation)}")
        lines.append(f"- session_operating_charter_mesh: {'；'.join(session_operating_charter_mesh)}")
        lines.append(f"- session_final_runtime_verdict: {'；'.join(session_final_runtime_verdict)}")
        lines.append(f"- session_executive_command_mesh: {'；'.join(session_executive_command_mesh)}")
        lines.append(f"- session_authority_control_matrix: {'；'.join(session_authority_control_matrix)}")
        lines.append(f"- session_runtime_closure_proof: {'；'.join(session_runtime_closure_proof)}")
        lines.append(f"- session_governance_signal_chain: {'；'.join(session_governance_signal_chain)}")
        lines.append(f"- session_operating_system_verdict: {'；'.join(session_operating_system_verdict)}")
        lines.append(f"- session_governance_backbone: {'；'.join(session_governance_backbone)}")
        lines.append(f"- session_control_lattice: {'；'.join(session_control_lattice)}")
        lines.append(f"- session_authority_bus: {'；'.join(session_authority_bus)}")
        lines.append(f"- session_runtime_witness_chain: {'；'.join(session_runtime_witness_chain)}")
        lines.append(f"- session_os_control_digest: {'；'.join(session_os_control_digest)}")
        lines.append(f"- session_governance_closure: {'；'.join(session_governance_closure)}")
        lines.append(f"- session_authority_verdict: {'；'.join(session_authority_verdict)}")
        lines.append(f"- session_runtime_horizon: {'；'.join(session_runtime_horizon)}")
        lines.append(f"- session_supervision_digest: {'；'.join(session_supervision_digest)}")
        lines.append(f"- session_control_summary: {'；'.join(session_control_summary)}")
        lines.append(f"- session_operating_system_contract: {'；'.join(session_operating_system_contract)}")
        lines.append(f"- session_control_checkpoint_digest: {'；'.join(session_control_checkpoint_digest)}")
        lines.append(f"- session_authority_signature: {'；'.join(session_authority_signature)}")
        lines.append(f"- session_recovery_escalation_mesh: {'；'.join(session_recovery_escalation_mesh)}")
        lines.append(f"- session_final_operating_posture: {'；'.join(session_final_operating_posture)}")
        lines.append(f"- session_control_kernel: {'；'.join(session_control_kernel)}")
        lines.append(f"- session_safety_circuit_breakers: {'；'.join(session_safety_circuit_breakers)}")
        lines.append(f"- session_override_channels: {'；'.join(session_override_channels)}")
        lines.append(f"- session_repair_loops: {'；'.join(session_repair_loops)}")
        lines.append(
            "- session_control_loop: "
            f"entry={len(session_entry_criteria)}；guards={len(session_guard_conditions)}；"
            f"transitions={len(session_allowed_transitions)}；auto_actions={len(session_auto_actions)}"
        )
        lines.append(
            "- session_queue_registry: "
            f"priority={len(session_priority_queue)}；ready={len(session_ready_queue)}；"
            f"blocked={len(session_blocked_queue)}；review={len(session_required_review)}"
        )
        lines.append(
            "- session_execution_registry: "
            f"lane={session_lane_status}；mode={session_execution_mode}；"
            f"window={session_action_window}；owner={session_recovery_owner}"
        )
        lines.append(
            "- session_governance_registry: "
            f"governor={session_governor_mode}；authority_routes={len(session_escalation_path)}；"
            f"quorum={len(session_review_quorum)}"
        )
        lines.append(
            "- session_digest_registry: "
            f"runtime={session_runtime_contract}；control_summary={session_control_summary[0]}；"
            f"os_digest={session_os_control_digest[0]}"
        )
        lines.append(
            "- session_live_ops_board: "
            f"ship={session_ship_decision}；promotion={promotion_verdict}；"
            f"risk={risk_register}；focuses={len(session_focuses[:3])}"
        )
        ready_ticket_count = sum(
            1
            for entry in ledger_entries
            if entry.get("recommendation") == "promote" and entry.get("business_risk_label") != "high-risk"
        )
        blocked_ticket_count = sum(1 for item in session_blockers) or sum(1 for entry in ledger_entries if entry.get("business_risk_label") == "high-risk")
        review_ticket_count = max(len(ledger_entries) - ready_ticket_count - blocked_ticket_count, 0)
        next_transition = (
            "pilot-lane -> expansion-lane"
            if promotion_verdict == "promote" and risk_register == "controlled"
            else "pilot-lane -> risk-mitigation-lane"
            if promotion_verdict == "de-risk"
            else "evidence-lane -> pilot-lane"
        )
        lines.append(
            "- session_action_backlog: "
            f"tickets={len(ledger_entries)}；ready={ready_ticket_count}；"
            f"review={review_ticket_count}；blocked={blocked_ticket_count}"
        )
        lines.append(
            "- session_transition_queue: "
            f"transitions=1；next={next_transition}；owner={session_recovery_owner}"
        )
        lines.append(
            "- session_checkpoint_mutations: "
            f"mutations=4；primary=promotion_verdict->{promotion_verdict}；"
            f"risk_register->{risk_register}"
        )
        lines.append(
            "- legacy_retirement_wave_01: retired_from_full_surface=session_governance_checksum_v2；session_operating_checksum"
        )
        if session_blockers:
            lines.append(f"- session_blockers: {'；'.join(session_blockers)}")
        if session_ready_queue:
            lines.append(f"- session_ready_queue: {'；'.join(session_ready_queue)}")
        if session_blocked_queue:
            lines.append(f"- session_blocked_queue: {'；'.join(session_blocked_queue)}")
        lines.append(f"- session_required_review: {'；'.join(session_required_review)}")
        lines.append(f"- session_owner_handoff: {'；'.join(session_owner_handoff)}")
        lines.append(f"- session_escalation_path: {'；'.join(session_escalation_path)}")
        lines.append(f"- session_priority_queue: {'；'.join(session_priority_queue)}")
        lines.append(f"- session_recovery_plan: {'；'.join(session_recovery_plan)}")
        lines.append(f"- session_recovery_owner: {session_recovery_owner}")
        lines.append(f"- session_command_brief: {'；'.join(session_command_brief)}")
        if session_focuses:
            lines.append(f"- session_focuses: {'；'.join(session_focuses[:3])}")

        lines.append("\n## Experiment Ledger")
        for entry in ledger_entries:
            lines.append(f"\n### {entry['experiment_name']}")
            lines.append(f"- artifact: {entry['artifact']}")
            lines.append(f"- innovation_level: {entry['innovation_level']}")
            lines.append(f"- risk_level: {entry['risk_level']}")
            lines.append(f"- business_risk_label: {entry['business_risk_label']}")
            lines.append(f"- reader_acceptance: {entry['reader_acceptance']}")
            lines.append(f"- focus: {entry['focus']}")
            lines.append(f"- recommendation: {entry['recommendation']}")
            lines.append(f"- next_action: {entry['next_action']}")
            lines.append(f"- pilot_scope: {entry['pilot_scope']}")
            lines.append(f"- confidence_level: {entry['confidence_level']}")
            lines.append(f"- observation_window: {entry['observation_window']}")
            lines.append(f"- baseline_vs_steering: {entry['baseline']}")
    return "\n".join(lines).strip() + "\n"


@app.command()
def writer_imitate(
    branch_id: str,
    source_chapter_index: int,
    target_goal: str,
    output_dir: Path = typer.Option(Path("output"), "--output-dir"),
    use_llm: bool = typer.Option(False, "--use-llm"),
    model_name: str = typer.Option("", "--model-name"),
    max_rounds: int = typer.Option(2, "--max-rounds"),
    worldview_note: list[str] = typer.Option([], "--worldview-note"),
    trope_axis: list[str] = typer.Option([], "--trope-axis"),
    innovation_directive: list[str] = typer.Option([], "--innovation-directive"),
    taboo_innovation: list[str] = typer.Option([], "--taboo-innovation"),
    knowledge_ref: list[str] = typer.Option([], "--knowledge-ref"),
    trope_doc: list[str] = typer.Option([], "--trope-doc"),
    worldview_doc: list[str] = typer.Option([], "--worldview-doc"),
    audience_doc: list[str] = typer.Option([], "--audience-doc"),
    database_url: str | None = None,
) -> None:
    """Writer-facing imitation entrypoint that writes artifacts into output/."""

    settings = _safe_settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        steering, retrieval_meta = _steering_pack(
            worldview_note,
            trope_axis,
            innovation_directive,
            taboo_innovation,
            knowledge_ref,
            trope_doc,
            worldview_doc,
            audience_doc,
        )
        report = _imitation_harness_service(session, settings).run_harness(
            branch_id,
            source_chapter_index=source_chapter_index,
            target_goal=target_goal,
            max_rounds=max_rounds,
            use_llm=use_llm,
            model_name=model_name or None,
            steering_pack=steering,
        )
        payload = report.model_dump(mode="json")
        payload["steering_pack"] = steering
        payload["steering_retrieval_meta"] = retrieval_meta
        stem = f"writer-imitate-ch{source_chapter_index}"
        json_path, md_path = _write_writer_imitation_outputs(output_dir, stem, payload)
        echo(f"writer_imitate_json={json_path}")
        echo(f"writer_imitate_markdown={md_path}")


@app.command()
def writer_imitate_range(
    branch_id: str,
    chapter_spec: list[str] = typer.Argument(..., help="Pairs like 3:目标A 4:目标B"),
    output_dir: Path = typer.Option(Path("output"), "--output-dir"),
    use_llm: bool = typer.Option(False, "--use-llm"),
    model_name: str = typer.Option("", "--model-name"),
    max_rounds: int = typer.Option(2, "--max-rounds"),
    worldview_note: list[str] = typer.Option([], "--worldview-note"),
    trope_axis: list[str] = typer.Option([], "--trope-axis"),
    innovation_directive: list[str] = typer.Option([], "--innovation-directive"),
    taboo_innovation: list[str] = typer.Option([], "--taboo-innovation"),
    knowledge_ref: list[str] = typer.Option([], "--knowledge-ref"),
    trope_doc: list[str] = typer.Option([], "--trope-doc"),
    worldview_doc: list[str] = typer.Option([], "--worldview-doc"),
    audience_doc: list[str] = typer.Option([], "--audience-doc"),
    database_url: str | None = None,
) -> None:
    """Batch writer-facing imitation entrypoint for multiple source chapters."""

    parsed = _parse_chapter_goal_spec(chapter_spec)
    settings = _safe_settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        service = _imitation_harness_service(session, settings)
        outputs: list[dict[str, object]] = []
        steering, retrieval_meta = _steering_pack(
            worldview_note,
            trope_axis,
            innovation_directive,
            taboo_innovation,
            knowledge_ref,
            trope_doc,
            worldview_doc,
            audience_doc,
        )
        for source_chapter_index, target_goal in parsed:
            report = service.run_harness(
                branch_id,
                source_chapter_index=source_chapter_index,
                target_goal=target_goal,
                max_rounds=max_rounds,
                use_llm=use_llm,
                model_name=model_name or None,
                steering_pack=steering,
            )
            payload = report.model_dump(mode="json")
            outputs.append(
                {
                    "source_chapter_index": source_chapter_index,
                    "target_goal": target_goal,
                    "final_verdict": payload.get("final_verdict"),
                    "stop_reason": payload.get("stop_reason"),
                    "final_draft": payload.get("final_draft", {}),
                    "policy_summary": payload.get("policy_summary", {}),
                }
            )
        stem = f"writer-imitate-range-{parsed[0][0]}-{parsed[-1][0]}"
        json_path, md_path = _write_writer_imitation_outputs(
            output_dir,
            stem,
            {"items": outputs, "branch_id": branch_id, "steering_pack": steering, "steering_retrieval_meta": retrieval_meta},
        )
        echo(f"writer_imitate_range_json={json_path}")
        echo(f"writer_imitate_range_markdown={md_path}")


@app.command()
def writer_imitate_review(
    branch_id: str,
    source_chapter_index: int,
    target_goal: str,
    output_dir: Path = typer.Option(Path("output"), "--output-dir"),
    use_llm: bool = typer.Option(False, "--use-llm"),
    model_name: str = typer.Option("", "--model-name"),
    max_rounds: int = typer.Option(2, "--max-rounds"),
    worldview_note: list[str] = typer.Option([], "--worldview-note"),
    trope_axis: list[str] = typer.Option([], "--trope-axis"),
    innovation_directive: list[str] = typer.Option([], "--innovation-directive"),
    taboo_innovation: list[str] = typer.Option([], "--taboo-innovation"),
    knowledge_ref: list[str] = typer.Option([], "--knowledge-ref"),
    trope_doc: list[str] = typer.Option([], "--trope-doc"),
    worldview_doc: list[str] = typer.Option([], "--worldview-doc"),
    audience_doc: list[str] = typer.Option([], "--audience-doc"),
    database_url: str | None = None,
) -> None:
    """Writer-facing single-chapter imitation review markdown export."""

    settings = _safe_settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        steering, retrieval_meta = _steering_pack(
            worldview_note,
            trope_axis,
            innovation_directive,
            taboo_innovation,
            knowledge_ref,
            trope_doc,
            worldview_doc,
            audience_doc,
        )
        report = _imitation_harness_service(session, settings).run_harness(
            branch_id,
            source_chapter_index=source_chapter_index,
            target_goal=target_goal,
            max_rounds=max_rounds,
            use_llm=use_llm,
            model_name=model_name or None,
            steering_pack=steering,
        )
        payload = report.model_dump(mode="json")
        payload["steering_pack"] = steering
        payload["steering_retrieval_meta"] = retrieval_meta
        output_dir.mkdir(parents=True, exist_ok=True)
        md_path = output_dir / f"writer-imitate-review-ch{source_chapter_index}.md"
        md_path.write_text(
            _writer_review_markdown(
                source_chapter_index=source_chapter_index,
                target_goal=target_goal,
                report_payload=payload,
            ),
            encoding="utf-8",
        )
        echo(f"writer_imitate_review_markdown={md_path}")


@app.command()
def writer_imitate_index(
    output_dir: Path = typer.Option(Path("output"), "--output-dir"),
) -> None:
    """Generate a writer-facing index page for output/ imitation artifacts."""

    output_dir.mkdir(parents=True, exist_ok=True)
    md_path = output_dir / "writer-imitate-index.md"
    state_path = output_dir / "writer-imitate-session-state.json"
    operator_surface_json_path = output_dir / "writer-imitate-operator-surface.json"
    operator_surface_md_path = output_dir / "writer-imitate-operator-surface.md"
    legacy_surface_json_path = output_dir / "writer-imitate-legacy-contract-surface.json"
    legacy_surface_md_path = output_dir / "writer-imitate-legacy-contract-surface.md"
    legacy_retirement_preview_json_path = output_dir / "writer-imitate-legacy-retirement-preview.json"
    legacy_retirement_preview_md_path = output_dir / "writer-imitate-legacy-retirement-preview.md"
    control_surface_registry_json_path = output_dir / "writer-imitate-control-surface-registry.json"
    control_surface_registry_md_path = output_dir / "writer-imitate-control-surface-registry.md"
    action_queue_json_path = output_dir / "writer-imitate-action-queue.json"
    action_queue_md_path = output_dir / "writer-imitate-action-queue.md"
    execution_state_json_path = output_dir / "writer-imitate-execution-state.json"
    execution_state_md_path = output_dir / "writer-imitate-execution-state.md"
    execution_replay_json_path = output_dir / "writer-imitate-execution-replay.json"
    execution_replay_md_path = output_dir / "writer-imitate-execution-replay.md"
    md_path.write_text(_writer_output_index_markdown(output_dir), encoding="utf-8")
    state_path.write_text(
        json.dumps(_build_writer_output_session_state(output_dir), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    operator_surface_json_path.write_text(
        json.dumps(_build_writer_output_operator_surface(output_dir), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    operator_surface_md_path.write_text(
        _writer_output_operator_surface_markdown(output_dir),
        encoding="utf-8",
    )
    legacy_surface_json_path.write_text(
        json.dumps(_build_writer_output_legacy_contract_surface(output_dir), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    legacy_surface_md_path.write_text(
        _writer_output_legacy_contract_surface_markdown(output_dir),
        encoding="utf-8",
    )
    legacy_retirement_preview_json_path.write_text(
        json.dumps(_build_writer_output_legacy_retirement_preview(output_dir), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    legacy_retirement_preview_md_path.write_text(
        _writer_output_legacy_retirement_preview_markdown(output_dir),
        encoding="utf-8",
    )
    control_surface_registry_json_path.write_text(
        json.dumps(_build_writer_output_control_surface_registry(output_dir), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    control_surface_registry_md_path.write_text(
        _writer_output_control_surface_registry_markdown(output_dir),
        encoding="utf-8",
    )
    action_queue_json_path.write_text(
        json.dumps(_build_writer_output_action_queue(output_dir), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    action_queue_md_path.write_text(
        _writer_output_action_queue_markdown(output_dir),
        encoding="utf-8",
    )
    execution_state_json_path.write_text(
        json.dumps(_build_writer_output_execution_state(output_dir), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    execution_state_md_path.write_text(
        _writer_output_execution_state_markdown(output_dir),
        encoding="utf-8",
    )
    execution_replay_json_path.write_text(
        json.dumps(_build_writer_output_execution_replay(output_dir), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    execution_replay_md_path.write_text(
        _writer_output_execution_replay_markdown(output_dir),
        encoding="utf-8",
    )
    echo(f"writer_imitate_index_markdown={md_path}")
    echo(f"writer_imitate_session_state_json={state_path}")
    echo(f"writer_imitate_operator_surface_json={operator_surface_json_path}")
    echo(f"writer_imitate_operator_surface_markdown={operator_surface_md_path}")
    echo(f"writer_imitate_legacy_contract_surface_json={legacy_surface_json_path}")
    echo(f"writer_imitate_legacy_contract_surface_markdown={legacy_surface_md_path}")
    echo(f"writer_imitate_legacy_retirement_preview_json={legacy_retirement_preview_json_path}")
    echo(f"writer_imitate_legacy_retirement_preview_markdown={legacy_retirement_preview_md_path}")
    echo(f"writer_imitate_control_surface_registry_json={control_surface_registry_json_path}")
    echo(f"writer_imitate_control_surface_registry_markdown={control_surface_registry_md_path}")
    echo(f"writer_imitate_action_queue_json={action_queue_json_path}")
    echo(f"writer_imitate_action_queue_markdown={action_queue_md_path}")
    echo(f"writer_imitate_execution_state_json={execution_state_json_path}")
    echo(f"writer_imitate_execution_state_markdown={execution_state_md_path}")
    echo(f"writer_imitate_execution_replay_json={execution_replay_json_path}")
    echo(f"writer_imitate_execution_replay_markdown={execution_replay_md_path}")


@app.command()
def writer_imitate_apply_replay(
    output_dir: Path = typer.Option(Path("output"), "--output-dir"),
) -> None:
    """Build an apply-preview artifact from writer imitation replay state."""

    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "writer-imitate-execution-apply.json"
    md_path = output_dir / "writer-imitate-execution-apply.md"
    json_path.write_text(
        json.dumps(_build_writer_output_execution_apply(output_dir), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    md_path.write_text(_writer_output_execution_apply_markdown(output_dir), encoding="utf-8")
    echo(f"writer_imitate_execution_apply_json={json_path}")
    echo(f"writer_imitate_execution_apply_markdown={md_path}")


@app.command()
def writer_imitate_live_control_state(
    output_dir: Path = typer.Option(Path("output"), "--output-dir"),
) -> None:
    """Build a persisted-style live control state artifact from apply preview."""

    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "writer-imitate-live-control-state.json"
    md_path = output_dir / "writer-imitate-live-control-state.md"
    json_path.write_text(
        json.dumps(_build_writer_output_live_control_state(output_dir), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    md_path.write_text(
        _writer_output_live_control_state_markdown(output_dir),
        encoding="utf-8",
    )
    echo(f"writer_imitate_live_control_state_json={json_path}")
    echo(f"writer_imitate_live_control_state_markdown={md_path}")


@app.command()
def writer_imitate_live_mutation_preview(
    output_dir: Path = typer.Option(Path("output"), "--output-dir"),
) -> None:
    """Build a standalone live-mutation preview artifact from the bridge state."""

    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "writer-imitate-live-mutation-preview.json"
    md_path = output_dir / "writer-imitate-live-mutation-preview.md"
    json_path.write_text(
        json.dumps(_build_writer_output_live_mutation_preview(output_dir), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    md_path.write_text(
        _writer_output_live_mutation_preview_markdown(output_dir),
        encoding="utf-8",
    )
    echo(f"writer_imitate_live_mutation_preview_json={json_path}")
    echo(f"writer_imitate_live_mutation_preview_markdown={md_path}")


@app.command()
def writer_imitate_apply_live_checkpoint(
    output_dir: Path = typer.Option(Path("output"), "--output-dir"),
) -> None:
    """Apply checkpoint writeback locally into an output artifact without touching external runtime state."""

    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "writer-imitate-live-checkpoint-state.json"
    md_path = output_dir / "writer-imitate-live-checkpoint-state.md"
    json_path.write_text(
        json.dumps(_build_writer_output_live_checkpoint_state(output_dir), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    md_path.write_text(
        _writer_output_live_checkpoint_state_markdown(output_dir),
        encoding="utf-8",
    )
    echo(f"writer_imitate_live_checkpoint_state_json={json_path}")
    echo(f"writer_imitate_live_checkpoint_state_markdown={md_path}")


@app.command()
def writer_imitate_apply_live_transition(
    output_dir: Path = typer.Option(Path("output"), "--output-dir"),
) -> None:
    """Apply transition state locally into an output artifact without touching external runtime state."""

    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "writer-imitate-live-transition-state.json"
    md_path = output_dir / "writer-imitate-live-transition-state.md"
    json_path.write_text(
        json.dumps(_build_writer_output_live_transition_state(output_dir), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    md_path.write_text(
        _writer_output_live_transition_state_markdown(output_dir),
        encoding="utf-8",
    )
    echo(f"writer_imitate_live_transition_state_json={json_path}")
    echo(f"writer_imitate_live_transition_state_markdown={md_path}")


@app.command()
def writer_imitate_validate_live_state(
    output_dir: Path = typer.Option(Path("output"), "--output-dir"),
) -> None:
    """Validate the local live bridge state into an output artifact without touching external runtime state."""

    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "writer-imitate-live-validation-state.json"
    md_path = output_dir / "writer-imitate-live-validation-state.md"
    json_path.write_text(
        json.dumps(_build_writer_output_live_validation_state(output_dir), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    md_path.write_text(
        _writer_output_live_validation_state_markdown(output_dir),
        encoding="utf-8",
    )
    echo(f"writer_imitate_live_validation_state_json={json_path}")
    echo(f"writer_imitate_live_validation_state_markdown={md_path}")


@app.command()
def writer_imitate_external_runtime_executor_readiness(
    output_dir: Path = typer.Option(Path("output"), "--output-dir"),
) -> None:
    """Build a readiness artifact for the future external runtime executors."""

    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "writer-imitate-external-runtime-executor-readiness.json"
    md_path = output_dir / "writer-imitate-external-runtime-executor-readiness.md"
    json_path.write_text(
        json.dumps(_build_writer_output_external_runtime_executor_readiness(output_dir), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    md_path.write_text(
        _writer_output_external_runtime_executor_readiness_markdown(output_dir),
        encoding="utf-8",
    )
    echo(f"writer_imitate_external_runtime_executor_readiness_json={json_path}")
    echo(f"writer_imitate_external_runtime_executor_readiness_markdown={md_path}")


@app.command()
def writer_imitate_external_runtime_executor_preview(
    output_dir: Path = typer.Option(Path("output"), "--output-dir"),
) -> None:
    """Build a standalone preview artifact for the future external runtime executors."""

    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "writer-imitate-external-runtime-executor-preview.json"
    md_path = output_dir / "writer-imitate-external-runtime-executor-preview.md"
    json_path.write_text(
        json.dumps(_build_writer_output_external_runtime_executor_preview(output_dir), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    md_path.write_text(
        _writer_output_external_runtime_executor_preview_markdown(output_dir),
        encoding="utf-8",
    )
    echo(f"writer_imitate_external_runtime_executor_preview_json={json_path}")
    echo(f"writer_imitate_external_runtime_executor_preview_markdown={md_path}")


@app.command()
def writer_imitate_apply_external_runtime_checkpoint(
    output_dir: Path = typer.Option(Path("output"), "--output-dir"),
) -> None:
    """Simulate the first external-runtime checkpoint writeback into an output artifact only."""

    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "writer-imitate-external-runtime-checkpoint-state.json"
    md_path = output_dir / "writer-imitate-external-runtime-checkpoint-state.md"
    json_path.write_text(
        json.dumps(_build_writer_output_external_runtime_checkpoint_state(output_dir), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    md_path.write_text(
        _writer_output_external_runtime_checkpoint_state_markdown(output_dir),
        encoding="utf-8",
    )
    echo(f"writer_imitate_external_runtime_checkpoint_state_json={json_path}")
    echo(f"writer_imitate_external_runtime_checkpoint_state_markdown={md_path}")


@app.command()
def writer_imitate_apply_external_runtime_transition(
    output_dir: Path = typer.Option(Path("output"), "--output-dir"),
) -> None:
    """Simulate the first external-runtime transition apply into an output artifact only."""

    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "writer-imitate-external-runtime-transition-state.json"
    md_path = output_dir / "writer-imitate-external-runtime-transition-state.md"
    json_path.write_text(
        json.dumps(_build_writer_output_external_runtime_transition_state(output_dir), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    md_path.write_text(
        _writer_output_external_runtime_transition_state_markdown(output_dir),
        encoding="utf-8",
    )
    echo(f"writer_imitate_external_runtime_transition_state_json={json_path}")
    echo(f"writer_imitate_external_runtime_transition_state_markdown={md_path}")


@app.command()
def writer_imitate_resume_replay(
    output_dir: Path = typer.Option(Path("output"), "--output-dir"),
) -> None:
    """Build a resume-plan artifact from writer imitation apply preview."""

    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "writer-imitate-execution-resume.json"
    md_path = output_dir / "writer-imitate-execution-resume.md"
    json_path.write_text(
        json.dumps(_build_writer_output_execution_resume(output_dir), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    md_path.write_text(_writer_output_execution_resume_markdown(output_dir), encoding="utf-8")
    echo(f"writer_imitate_execution_resume_json={json_path}")
    echo(f"writer_imitate_execution_resume_markdown={md_path}")


@app.command()
def writer_innovation_experiment(
    branch_id: str,
    experiment_name: str,
    chapter_spec: list[str] = typer.Argument(..., help="Pairs like 24:强化阶层冲击 25:强化回乡情绪"),
    output_dir: Path = typer.Option(Path("output"), "--output-dir"),
    use_llm: bool = typer.Option(False, "--use-llm"),
    model_name: str = typer.Option("", "--model-name"),
    max_rounds: int = typer.Option(2, "--max-rounds"),
    worldview_note: list[str] = typer.Option([], "--worldview-note"),
    trope_axis: list[str] = typer.Option([], "--trope-axis"),
    innovation_directive: list[str] = typer.Option([], "--innovation-directive"),
    taboo_innovation: list[str] = typer.Option([], "--taboo-innovation"),
    knowledge_ref: list[str] = typer.Option([], "--knowledge-ref"),
    trope_doc: list[str] = typer.Option([], "--trope-doc"),
    worldview_doc: list[str] = typer.Option([], "--worldview-doc"),
    audience_doc: list[str] = typer.Option([], "--audience-doc"),
    database_url: str | None = None,
) -> None:
    """Run a batch innovation-steered imitation experiment and persist a reusable bundle."""

    parsed = _parse_chapter_goal_spec(chapter_spec)
    settings = _safe_settings(database_url)
    factory = create_session_factory(settings)
    steering, retrieval_meta = _steering_pack(
        worldview_note,
        trope_axis,
        innovation_directive,
        taboo_innovation,
        knowledge_ref,
        trope_doc,
        worldview_doc,
        audience_doc,
    )
    with factory() as session:
        service = _imitation_harness_service(session, settings)
        baseline_outputs: list[dict[str, object]] = []
        outputs: list[dict[str, object]] = []
        for source_chapter_index, target_goal in parsed:
            baseline_report = service.run_harness(
                branch_id,
                source_chapter_index=source_chapter_index,
                target_goal=target_goal,
                max_rounds=max_rounds,
                use_llm=use_llm,
                model_name=model_name or None,
                steering_pack=None,
            )
            baseline_payload = baseline_report.model_dump(mode="json")
            baseline_outputs.append(
                {
                    "source_chapter_index": source_chapter_index,
                    "target_goal": target_goal,
                    "final_verdict": baseline_payload.get("final_verdict"),
                    "stop_reason": baseline_payload.get("stop_reason"),
                    "final_draft": baseline_payload.get("final_draft", {}),
                    "policy_summary": baseline_payload.get("policy_summary", {}),
                    "rounds": baseline_payload.get("rounds", []),
                    "steering_summary": {},
                }
            )
            report = service.run_harness(
                branch_id,
                source_chapter_index=source_chapter_index,
                target_goal=target_goal,
                max_rounds=max_rounds,
                use_llm=use_llm,
                model_name=model_name or None,
                steering_pack=steering,
            )
            payload = report.model_dump(mode="json")
            outputs.append(
                {
                    "source_chapter_index": source_chapter_index,
                    "target_goal": target_goal,
                    "final_verdict": payload.get("final_verdict"),
                    "stop_reason": payload.get("stop_reason"),
                    "final_draft": payload.get("final_draft", {}),
                    "policy_summary": payload.get("policy_summary", {}),
                    "rounds": payload.get("rounds", []),
                    "steering_summary": steering,
                }
            )
        baseline_vs_steering_report = _build_baseline_vs_steering_report(baseline_outputs, outputs)
        delta_visual_summary = _build_delta_visual_summary(steering, retrieval_meta)
        reader_sim_acceptance_summary = _build_reader_sim_acceptance_summary(baseline_outputs, outputs)
        writer_innovation_explanation = _build_writer_innovation_explanation(
            steering,
            retrieval_meta,
            baseline_vs_steering_report,
            delta_visual_summary,
            reader_sim_acceptance_summary,
        )
        experiment_decision_note = _build_experiment_decision_note(
            baseline_vs_steering_report,
            delta_visual_summary,
            reader_sim_acceptance_summary,
        )
        stem = f"writer-innovation-experiment-{experiment_name}"
        json_path, md_path = _write_writer_imitation_outputs(
            output_dir,
            stem,
            {
                "contract_version": "writer-innovation-experiment.v1",
                "experiment_name": experiment_name,
                "branch_id": branch_id,
                "steering_pack": steering,
                "steering_retrieval_meta": retrieval_meta,
                "delta_visual_summary": delta_visual_summary,
                "reader_sim_acceptance_summary": reader_sim_acceptance_summary,
                "writer_innovation_explanation": writer_innovation_explanation,
                "experiment_decision_note": experiment_decision_note,
                "baseline_items": baseline_outputs,
                "items": outputs,
                "experiment_meta": {
                    "chapter_count": len(outputs),
                    "use_llm": use_llm,
                    "max_rounds": max_rounds,
                    "model_name": model_name or settings.llm_model_name,
                    "baseline_vs_steering_report": baseline_vs_steering_report,
                    "innovation_delta_summary": {
                        "worldview_note_count": len(steering.get("worldview_capsule", [])),
                        "trope_axis_count": len(steering.get("trope_axes", [])),
                        "innovation_directive_count": len(steering.get("innovation_directives", [])),
                    },
                    "risk_delta_summary": {
                        "taboo_innovation_count": len(steering.get("taboo_innovations", [])),
                        "external_knowledge_ref_count": len(steering.get("external_knowledge_refs", [])),
                    },
                },
            },
        )
        echo(f"writer_innovation_experiment_json={json_path}")
        echo(f"writer_innovation_experiment_markdown={md_path}")


@app.command()
def preflight_imitation(
    branch_id: str,
    source_chapter_index: int,
    target_goal: str,
    use_llm: bool = typer.Option(False, "--use-llm"),
    model_name: str = typer.Option("", "--model-name"),
    worldview_note: list[str] = typer.Option([], "--worldview-note"),
    trope_axis: list[str] = typer.Option([], "--trope-axis"),
    innovation_directive: list[str] = typer.Option([], "--innovation-directive"),
    taboo_innovation: list[str] = typer.Option([], "--taboo-innovation"),
    knowledge_ref: list[str] = typer.Option([], "--knowledge-ref"),
    trope_doc: list[str] = typer.Option([], "--trope-doc"),
    worldview_doc: list[str] = typer.Option([], "--worldview-doc"),
    audience_doc: list[str] = typer.Option([], "--audience-doc"),
    database_url: str | None = None,
) -> None:
    """Run deterministic preflight checks before formal imitation gate/risk review."""

    settings = _safe_settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        chapter_service = _chapter_imitation_service(session)
        draft = (
            chapter_service.build_llm_draft(
                branch_id,
                source_chapter_index=source_chapter_index,
                target_goal=target_goal,
                model_name=model_name or None,
                steering_pack=_steering_pack(
                    worldview_note,
                    trope_axis,
                    innovation_directive,
                    taboo_innovation,
                    knowledge_ref,
                    trope_doc,
                    worldview_doc,
                    audience_doc,
                )[0],
            )
            if use_llm
            else chapter_service.build_skeleton_draft(
                branch_id,
                source_chapter_index=source_chapter_index,
                target_goal=target_goal,
                steering_pack=_steering_pack(
                    worldview_note,
                    trope_axis,
                    innovation_directive,
                    taboo_innovation,
                    knowledge_ref,
                    trope_doc,
                    worldview_doc,
                    audience_doc,
                )[0],
            )
        )
        comparison = chapter_service.compare_with_source(
            branch_id,
            source_chapter_index=source_chapter_index,
            draft=draft,
        )
        report = _imitation_harness_service(session, settings).preflight_draft(
            branch_id,
            source_chapter_index=source_chapter_index,
            draft=draft,
            comparison=comparison,
        )
        echo(
            json.dumps(
                {
                    "draft": draft.model_dump(mode="json"),
                    "comparison": comparison.model_dump(mode="json"),
                    "preflight": report.model_dump(mode="json"),
                },
                ensure_ascii=False,
                indent=2,
            )
        )


@app.command()
def harness_imitation(
    branch_id: str,
    source_chapter_index: int,
    target_goal: str,
    max_rounds: int = typer.Option(2, "--max-rounds"),
    use_llm: bool = typer.Option(False, "--use-llm"),
    model_name: str = typer.Option("", "--model-name"),
    worldview_note: list[str] = typer.Option([], "--worldview-note"),
    trope_axis: list[str] = typer.Option([], "--trope-axis"),
    innovation_directive: list[str] = typer.Option([], "--innovation-directive"),
    taboo_innovation: list[str] = typer.Option([], "--taboo-innovation"),
    knowledge_ref: list[str] = typer.Option([], "--knowledge-ref"),
    trope_doc: list[str] = typer.Option([], "--trope-doc"),
    worldview_doc: list[str] = typer.Option([], "--worldview-doc"),
    audience_doc: list[str] = typer.Option([], "--audience-doc"),
    database_url: str | None = None,
) -> None:
    """Run the first controlled imitation harness with skill contracts and preflight routing."""

    settings = _safe_settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        steering, _retrieval_meta = _steering_pack(
            worldview_note,
            trope_axis,
            innovation_directive,
            taboo_innovation,
            knowledge_ref,
            trope_doc,
            worldview_doc,
            audience_doc,
        )
        report = _imitation_harness_service(session, settings).run_harness(
            branch_id,
            source_chapter_index=source_chapter_index,
            target_goal=target_goal,
            max_rounds=max_rounds,
            use_llm=use_llm,
            model_name=model_name or None,
            steering_pack=steering,
        )
        echo(report.model_dump_json(indent=2, ensure_ascii=False))


@app.command()
def show_window(
    branch_id: str,
    start_chapter: int,
    end_chapter: int,
    database_url: str | None = None,
) -> None:
    """Show one materialized fixed-size window artifact."""

    settings = _safe_settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        artifact = session.scalar(
            select(WindowArtifact)
            .where(WindowArtifact.branch_id == branch_id)
            .where(WindowArtifact.window_start_chapter == start_chapter)
            .where(WindowArtifact.window_end_chapter == end_chapter)
        )
        if artifact is None:
            raise typer.Exit(code=1)
        echo(str(artifact.payload_json))


@app.command()
def latest_manifest(novel_id: str, database_url: str | None = None) -> None:
    """Show the latest manifest id for a novel."""

    settings = _safe_settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        manifest = session.scalar(
            select(ChapterManifest)
            .where(ChapterManifest.novel_id == novel_id)
            .order_by(ChapterManifest.version.desc())
        )
        if manifest is None:
            raise typer.Exit(code=1)
        echo(f"manifest_id={manifest.id}")
        echo(f"chapter_count={manifest.chapter_count}")


if __name__ == "__main__":
    app()
