"""Typer CLI entrypoint."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from typer import echo

from novel_analyzer.config.settings import Settings, get_settings
from novel_analyzer.database.migrations import upgrade_database
from novel_analyzer.database.models import ChapterManifest, WindowArtifact
from novel_analyzer.database.postgres_checks import postgres_capability_report
from novel_analyzer.database.session import (
    create_session_factory,
    database_healthcheck,
    ensure_database_exists,
)
from novel_analyzer.runtime.storage import describe_runtime_storage, migrate_legacy_runtime_dirs
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
