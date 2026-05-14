from __future__ import annotations

from fastapi import APIRouter, Query

from apps.api.app.routers import get_db_session, resolve_settings

router = APIRouter(prefix="/api", tags=["chapters"])


@router.get("/chapter-bundle")
def chapter_bundle(
    branch_id: str = Query(...),
    chapter_index: int = Query(...),
    database_url: str | None = Query(None),
) -> dict:
    from novel_analyzer.services.export_service import ExportService

    with get_db_session(database_url) as session:
        return ExportService(session).export_chapter_bundle(branch_id, chapter_index)


@router.get("/chapter-source")
def chapter_source(
    branch_id: str = Query(...),
    chapter_index: int = Query(...),
    database_url: str | None = Query(None),
) -> dict:
    from sqlalchemy import select
    from novel_analyzer.database.models import RunBranch, NovelSource, ChapterSegment
    from pathlib import Path

    with get_db_session(database_url) as session:
        branch = session.scalar(select(RunBranch).where(RunBranch.id == branch_id))
        if not branch:
            return {"error": "branch not found"}
        run = branch.run
        novel = session.scalar(select(NovelSource).where(NovelSource.id == run.novel_id))
        if not novel:
            return {"error": "novel not found"}
        manifest = run.manifest
        segment = session.scalar(
            select(ChapterSegment)
            .where(ChapterSegment.manifest_id == manifest.id)
            .where(ChapterSegment.chapter_index == chapter_index)
        )
        if not segment:
            return {"error": f"chapter {chapter_index} not found"}
        full_text = Path(novel.source_path).read_text(encoding="utf-8", errors="ignore")
        chapter_text = full_text[segment.start_offset:segment.end_offset].strip()
        return {
            "branch_id": branch_id,
            "chapter_index": chapter_index,
            "title": segment.normalized_title,
            "text": chapter_text,
            "char_count": len(chapter_text),
        }


@router.get("/chapter-qa-context")
def chapter_qa_context(
    branch_id: str = Query(...),
    chapter_index: int = Query(...),
    database_url: str | None = Query(None),
) -> dict:
    from novel_analyzer.services.export_service import ExportService

    with get_db_session(database_url) as session:
        return ExportService(session).export_chapter_qa_context(branch_id, chapter_index)


@router.get("/chapter-jobs")
def chapter_jobs(
    branch_id: str = Query(...),
    limit: int = Query(200),
    database_url: str | None = Query(None),
) -> dict:
    from sqlalchemy import select
    from novel_analyzer.database.models import ChapterJob

    with get_db_session(database_url) as session:
        jobs = session.scalars(
            select(ChapterJob)
            .where(ChapterJob.branch_id == branch_id)
            .where(ChapterJob.deleted_at.is_(None))
            .order_by(ChapterJob.chapter_index)
            .limit(limit)
        ).all()
        items = [
            {
                "id": j.id,
                "chapter_index": j.chapter_index,
                "status": j.status,
                "created_at": j.created_at.isoformat() if j.created_at else None,
            }
            for j in jobs
        ]
        return {"items": items, "total": len(items)}


@router.get("/branch-snapshot")
def branch_snapshot(
    run_id: str = Query(...),
    branch_id: str = Query(...),
    database_url: str | None = Query(None),
) -> dict:
    from novel_analyzer.services.export_service import ExportService

    with get_db_session(database_url) as session:
        return ExportService(session).export_branch_bundle(run_id, branch_id)



@router.get("/job-events")
def job_events(
    branch_id: str = Query(...),
    database_url: str | None = Query(None),
    limit: int = Query(100),
):
    from fastapi.responses import JSONResponse
    from apps.api.app.main import _job_events_payload
    try:
        return _job_events_payload(branch_id, database_url, limit)
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})


@router.get("/chapter-job-events")
def chapter_job_events(
    branch_id: str = Query(...),
    chapter_index: int = Query(...),
    database_url: str | None = Query(None),
    limit: int = Query(100),
):
    from fastapi.responses import JSONResponse
    from apps.api.app.main import _chapter_job_events_payload
    try:
        return _chapter_job_events_payload(branch_id, chapter_index, database_url, limit)
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})
