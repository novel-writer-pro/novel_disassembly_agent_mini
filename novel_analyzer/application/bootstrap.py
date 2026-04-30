"""Bootstrap orchestration for ingest/start/advance flows."""

from __future__ import annotations

from pathlib import Path

from novel_analyzer.application.dto import AutoRunResult
from novel_analyzer.application.pipeline import advance_pipeline
from novel_analyzer.config.settings import Settings, get_settings
from novel_analyzer.database.migrations import upgrade_database
from novel_analyzer.database.models import NovelSource
from novel_analyzer.database.session import create_session_factory, ensure_database_exists
from novel_analyzer.services.ingest_service import IngestService
from novel_analyzer.services.run_service import RunService


def _setup_incomplete(novel: NovelSource, message: str) -> None:
    metadata = dict(novel.metadata_json)
    metadata["setup_status"] = "setup_incomplete"
    metadata["setup_error"] = message
    novel.metadata_json = metadata


def ingest_and_start_pipeline(
    *,
    path: str,
    title: str | None = None,
    branch_name: str = "main",
    pipeline_profile: str = "auto-lite",
    max_chapters: int | None = None,
    database_url: str | None = None,
    settings: Settings | None = None,
) -> AutoRunResult:
    """Ingest a novel, create a run, and optionally advance chapters."""

    runtime = (settings or get_settings()).model_copy(deep=True)
    if database_url:
        runtime.database_url = database_url
    ensure_database_exists(runtime)
    upgrade_database(runtime)
    factory = create_session_factory(runtime)
    with factory() as session:
        novel, manifest = IngestService(session, runtime).ingest_text_file(path, title)
        try:
            analysis_profile = {
                "pipeline_profile": pipeline_profile,
                "source_kind": "local_path",
                "source_ref": str(Path(path)),
            }
            run, branch = RunService(session, runtime).create_run(
                novel.id,
                manifest.id,
                branch_name,
                analysis_profile=analysis_profile,
            )
        except Exception as exc:
            _setup_incomplete(novel, str(exc))
            session.commit()
            return AutoRunResult(
                novel_id=novel.id,
                manifest_id=manifest.id,
                run_id=None,
                branch_id=None,
                chapter_count=manifest.chapter_count,
                processed_chapters=0,
                next_chapter=1 if manifest.chapter_count else None,
                pipeline_profile=pipeline_profile,
                pipeline_state="failed_terminal",
                setup_status="setup_incomplete",
            )
        novel_id = novel.id
        manifest_id = manifest.id
        chapter_count = manifest.chapter_count
        run_id = run.id
        branch_id = branch.id

    if pipeline_profile == "manual" or max_chapters == 0:
        return AutoRunResult(
            novel_id=novel_id,
            manifest_id=manifest_id,
            run_id=run_id,
            branch_id=branch_id,
            chapter_count=chapter_count,
            processed_chapters=0,
            next_chapter=1 if chapter_count else None,
            pipeline_profile=pipeline_profile,
            pipeline_state="ready" if chapter_count else "completed",
        )

    effective_max_chapters = (
        chapter_count if pipeline_profile == "auto-full" and max_chapters is None else max_chapters
    )
    if effective_max_chapters is None:
        effective_max_chapters = 1

    processed_chapters, next_chapter, pipeline_state = advance_pipeline(
        run_id=run_id,
        branch_id=branch_id,
        max_chapters=effective_max_chapters,
        database_url=database_url,
        settings=runtime,
    )
    return AutoRunResult(
        novel_id=novel_id,
        manifest_id=manifest_id,
        run_id=run_id,
        branch_id=branch_id,
        chapter_count=chapter_count,
        processed_chapters=processed_chapters,
        next_chapter=next_chapter,
        pipeline_profile=pipeline_profile,
        pipeline_state=pipeline_state,
    )
