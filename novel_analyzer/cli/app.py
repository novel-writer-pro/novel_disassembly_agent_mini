"""Typer CLI entrypoint."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from sqlalchemy import select, text
from typer import echo

from novel_analyzer.config.settings import Settings, get_settings
from novel_analyzer.database.migrations import upgrade_database
from novel_analyzer.database.models import ChapterManifest, GraphEdge, GraphNode, WindowArtifact
from novel_analyzer.database.session import (
    create_session_factory,
    database_healthcheck,
    ensure_database_exists,
)
from novel_analyzer.embedding.service import get_embedding_provider
from novel_analyzer.preprocessing.chapter_splitter import inspect_text
from novel_analyzer.reporting.branch_report import render_branch_report
from novel_analyzer.services.analysis_service import AnalysisService
from novel_analyzer.services.chapter_index_service import ChapterIndexService
from novel_analyzer.services.consistency_service import ConsistencyService
from novel_analyzer.services.context_service import ContextService
from novel_analyzer.services.export_service import ExportService
from novel_analyzer.services.fact_service import FactService
from novel_analyzer.services.graph_service import GraphService
from novel_analyzer.services.ingest_service import IngestService
from novel_analyzer.services.package_service import PackageService
from novel_analyzer.services.qa_service import BranchQAService
from novel_analyzer.services.raw_output_service import RawOutputService
from novel_analyzer.services.repair_service import RepairService
from novel_analyzer.services.retrieval_service import RetrievalService
from novel_analyzer.services.run_service import RunService
from novel_analyzer.services.status_service import StatusService
from novel_analyzer.skills.loader import list_skill_names

app = typer.Typer(add_completion=False, no_args_is_help=True)


def _settings(database_url: str | None = None) -> Settings:
    current = get_settings().model_copy(deep=True)
    if database_url:
        current.database_url = database_url
    return current


@app.command()
def init_db(
    database_url: str | None = None,
    ensure_db: bool = typer.Option(True, help="Create PostgreSQL database first when needed."),
) -> None:
    """Create or upgrade the database schema via Alembic."""

    settings = _settings(database_url)
    if ensure_db:
        ensure_database_exists(settings)
    upgrade_database(settings)
    echo(f"initialized database: {settings.masked_database_url}")


@app.command()
def db_health(database_url: str | None = None) -> None:
    """Run a simple database connectivity check."""

    settings = _settings(database_url)
    report = database_healthcheck(settings)
    for key, value in report.items():
        echo(f"{key}={value}")


@app.command()
def list_skills(database_url: str | None = None) -> None:
    """List project-local skills discovered from skills_dir/."""

    settings = _settings(database_url)
    for name in list_skill_names(settings):
        echo(name)



@app.command()
def test_embedding(
    text_input: str = '卫图觉醒命格。',
    database_url: str | None = None,
) -> None:
    """Run a smoke test for the configured embedding backend."""

    settings = _settings(database_url)
    provider = get_embedding_provider(settings)
    vectors = provider.embed_texts([text_input])
    echo(f"provider={type(provider).__name__}")
    echo(f"vector_dim={len(vectors[0])}")
    echo(f"vector_preview={vectors[0][:8]}")


@app.command()
def inspect_novel(path: Path) -> None:
    """Inspect a novel file without persisting anything."""

    text = path.read_text(encoding="utf-8")
    preview = inspect_text(text)
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

    settings = _settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        novel, manifest = IngestService(session, settings).ingest_text_file(str(path), title)
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

    settings = _settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        run, branch = RunService(session, settings).create_run(
            novel_id,
            manifest_id,
            branch_name,
        )
        echo(f"run_id={run.id}")
        echo(f"branch_id={branch.id}")
        echo(f"active_branch_id={run.active_branch_id}")






@app.command()
def clear_running_jobs(
    branch_id: str,
    reason: str = typer.Option('manual cleanup of stale running jobs', '--reason'),
    database_url: str | None = None,
) -> None:
    """Mark stale running jobs as failed so the branch can continue."""

    settings = _settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        count = RunService(session, settings).clear_running_jobs(branch_id, reason)
        echo(f"cleared_running_jobs={count}")


@app.command()
def retry_failed_jobs(
    run_id: str,
    branch_id: str,
    max_chapters: int = typer.Option(5, '--max-chapters'),
    database_url: str | None = None,
) -> None:
    """Retry failed jobs serially for up to N chapters."""

    settings = _settings(database_url)
    factory = create_session_factory(settings)
    retried = 0
    with factory() as session:
        run_service = RunService(session, settings)
        failed = run_service.list_failed_jobs(branch_id, max_chapters)
        for job in failed:
            run_service.reset_failed_job(branch_id, job.chapter_index)
            artifact_ids = AnalysisService(session, settings).analyze_range(
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

    settings = _settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        jobs = RunService(session, settings).list_failed_jobs(branch_id, limit)
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

    settings = _settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        run_service = RunService(session, settings)
        run_service.reset_failed_job(branch_id, chapter_index)
        artifact_ids = AnalysisService(session, settings).analyze_range(
            run_id,
            branch_id,
            chapter_index,
            chapter_index,
        )
        echo(f"retried_chapter={chapter_index}")
        for artifact_id in artifact_ids:
            echo(f"artifact_id={artifact_id}")



@app.command()
def list_chapters(
    branch_id: str,
    limit: int = typer.Option(200, '--limit'),
    database_url: str | None = None,
) -> None:
    """List per-chapter progress rows for one branch."""

    settings = _settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        rows = ChapterIndexService(session).list_rows(branch_id, limit)
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

    settings = _settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        status = StatusService(session).get_run_status(run_id, branch_id)
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

    settings = _settings(database_url)
    factory = create_session_factory(settings)
    processed = 0
    with factory() as session:
        run_service = RunService(session, settings)
        while processed < max_chapters:
            next_index = run_service.next_chapter_index(run_id, branch_id)
            if next_index is None:
                break
            artifact_ids = AnalysisService(session, settings).analyze_range(
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

    settings = _settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        run_service = RunService(session, settings)
        next_index = run_service.next_chapter_index(run_id, branch_id)
        if next_index is None:
            echo('next_chapter=None')
            return
        artifact_ids = AnalysisService(session, settings).analyze_range(
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

    settings = _settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        artifact_ids = AnalysisService(session, settings).analyze_range(
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

    settings = _settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        document = RetrievalService(session, settings).materialize_for_artifact(artifact_id)
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

    settings = _settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        hits = RetrievalService(session, settings).search_branch(branch_id, query, limit)
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

    settings = _settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        result = BranchQAService(session, settings).answer_question(branch_id, question, limit)
        echo(f"answer={result.answer}")
        echo(f"used_chapters={result.used_chapters}")
        echo(f"confidence={result.confidence}")
        echo(f"insufficient_context={result.insufficient_context}")
        for item in result.evidence:
            echo(f"evidence={item}")







@app.command()
def show_raw_output(
    branch_id: str,
    chapter_index: int,
    database_url: str | None = None,
) -> None:
    """Show the latest raw LLM output record for one chapter."""

    settings = _settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        record = RawOutputService(session).latest_for_chapter(branch_id, chapter_index)
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

    settings = _settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        record = RawOutputService(session).latest_for_chapter(branch_id, chapter_index)
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

    settings = _settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        bundle = ContextService(session).context_bundle(branch_id, chapter_index)
        echo(json.dumps(bundle, ensure_ascii=False, indent=2))


@app.command()
def export_context(
    branch_id: str,
    chapter_index: int,
    output_path: Path,
    database_url: str | None = None,
) -> None:
    """Export the assembled prior context for a chapter to JSON."""

    settings = _settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        bundle = ContextService(session).context_bundle(branch_id, chapter_index)
        output_path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding='utf-8')
        echo(f"context_path={output_path}")


@app.command()
def show_chapter(
    branch_id: str,
    chapter_index: int,
    database_url: str | None = None,
) -> None:
    """Show a compact chapter bundle for one branch/chapter."""

    settings = _settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        bundle = ExportService(session).export_chapter_bundle(branch_id, chapter_index)
        echo(json.dumps(bundle, ensure_ascii=False, indent=2))


@app.command()
def export_chapter_bundle(
    branch_id: str,
    chapter_index: int,
    output_path: Path,
    database_url: str | None = None,
) -> None:
    """Export one chapter bundle JSON for external consumption."""

    settings = _settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        bundle = ExportService(session).export_chapter_bundle(branch_id, chapter_index)
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

    settings = _settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        bundle = ExportService(session).export_branch_bundle(run_id, branch_id)
        output_path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding='utf-8')
        echo(f"bundle_path={output_path}")


@app.command()
def export_markdown(
    branch_id: str,
    chapter_index: int,
    output_path: Path,
    database_url: str | None = None,
) -> None:
    """Export one chapter artifact to Markdown."""

    settings = _settings(database_url)
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

    settings = _settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        artifact = RunService(session, settings).record_chapter_artifact(
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

    settings = _settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        artifact = RunService(session, settings).add_manual_artifact(
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

    settings = _settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        branch = RunService(session, settings).fork_branch(branch_id, keep_through, name)
        echo(f"new_branch_id={branch.id}")
        echo(f"fork_after_chapter_index={branch.fork_after_chapter_index}")


@app.command()
def show_branch(branch_id: str, database_url: str | None = None) -> None:
    """Print a compact branch snapshot."""

    settings = _settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        snapshot = RunService(session, settings).branch_snapshot(branch_id)
        for key, value in snapshot.items():
            echo(f"{key}={value}")







@app.command()
def repair_branch(
    branch_id: str,
    database_url: str | None = None,
) -> None:
    """Backfill jobs and materialized layers for an existing branch."""

    settings = _settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        report = RepairService(session).repair_branch(branch_id)
        for key in report.__dataclass_fields__:
            echo(f"{key}={getattr(report, key)}")


@app.command()
def validate_branch(
    branch_id: str,
    database_url: str | None = None,
) -> None:
    """Run consistency checks for one branch."""

    settings = _settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        report = ConsistencyService(session).validate_branch(branch_id)
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

    settings = _settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        facts = FactService(session).search_facts(branch_id, query, limit)
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

    settings = _settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        facts = FactService(session).list_facts(branch_id, chapter_index, limit)
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

    settings = _settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        path = PackageService(session).export_branch_package(run_id, branch_id, output_dir)
        echo(f"package_path={path}")


@app.command()
def export_branch_report(
    run_id: str,
    branch_id: str,
    output_path: Path,
    database_url: str | None = None,
) -> None:
    """Export a branch-level Markdown report."""

    settings = _settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        bundle = ExportService(session).export_branch_bundle(run_id, branch_id)
        output_path.write_text(render_branch_report(bundle), encoding='utf-8')
        echo(f"report_path={output_path}")



@app.command()
def summarize_graph(
    branch_id: str,
    database_url: str | None = None,
) -> None:
    """Show a compact reasoning-oriented graph summary."""

    settings = _settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        summary = GraphService(session).summarize_branch(branch_id)
        echo(f"branch_id={summary.branch_id}")
        echo(f"node_count={summary.node_count}")
        echo(f"edge_count={summary.edge_count}")
        for label, count in summary.top_entities:
            echo(f"top_entity={label}:{count}")
        for label, count in summary.top_events:
            echo(f"top_event={label}:{count}")
        for edge in summary.progression_edges:
            echo(f"progression={edge}")


@app.command()
def show_graph(
    branch_id: str,
    database_url: str | None = None,
) -> None:
    """Show a compact graph snapshot for a branch."""

    settings = _settings(database_url)
    factory = create_session_factory(settings)
    with factory() as session:
        nodes = session.scalars(
            select(GraphNode)
            .where(GraphNode.branch_id == branch_id)
            .order_by(GraphNode.node_type, GraphNode.label)
        ).all()
        edges = session.scalars(
            select(GraphEdge).where(GraphEdge.branch_id == branch_id).order_by(GraphEdge.edge_type)
        ).all()
        echo(f"node_count={len(nodes)}")
        for node in nodes[:20]:
            echo(f"node={node.node_type}:{node.label}:{node.occurrence_count}")
        echo(f"edge_count={len(edges)}")
        for edge in edges[:20]:
            echo(f"edge={edge.edge_type}:{edge.source_node_id}->{edge.target_node_id}:w={edge.weight}")


@app.command()
def show_window(
    branch_id: str,
    start_chapter: int,
    end_chapter: int,
    database_url: str | None = None,
) -> None:
    """Show one materialized fixed-size window artifact."""

    settings = _settings(database_url)
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

    settings = _settings(database_url)
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
