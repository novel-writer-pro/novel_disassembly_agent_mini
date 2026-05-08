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


def _writer_output_index_markdown(output_dir: Path) -> str:
    lines: list[str] = ["# Writer Imitation Output Index"]
    json_files = sorted(output_dir.glob("writer-imitate-range-*.json"))
    if not json_files:
        return "# Writer Imitation Output Index\n\n- no writer-imitate-range json files found\n"

    for path in json_files:
        lines.append(f"\n## {path.name}")
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
    md_path.write_text(_writer_output_index_markdown(output_dir), encoding="utf-8")
    echo(f"writer_imitate_index_markdown={md_path}")


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
