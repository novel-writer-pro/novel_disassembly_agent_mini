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
            state = ClusterReviewService(session).write(
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


@app.command()
def preflight_imitation(
    branch_id: str,
    source_chapter_index: int,
    target_goal: str,
    use_llm: bool = typer.Option(False, "--use-llm"),
    model_name: str = typer.Option("", "--model-name"),
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
            )
            if use_llm
            else chapter_service.build_skeleton_draft(
                branch_id,
                source_chapter_index=source_chapter_index,
                target_goal=target_goal,
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
    database_url: str | None = None,
) -> None:
    """Run the first controlled imitation harness with skill contracts and preflight routing."""

    settings = _safe_settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        report = _imitation_harness_service(session, settings).run_harness(
            branch_id,
            source_chapter_index=source_chapter_index,
            target_goal=target_goal,
            max_rounds=max_rounds,
            use_llm=use_llm,
            model_name=model_name or None,
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
