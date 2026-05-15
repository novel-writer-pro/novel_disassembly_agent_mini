from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Query, UploadFile, File, Form, Request
from pydantic import BaseModel

from apps.api.app.routers import get_db_session, resolve_settings

router = APIRouter(prefix="/api", tags=["import-recovery"])


@router.post("/import")
async def import_novel(request: Request):
    """Match WSGI canonical: accept multipart file OR JSON {"chapters": [...]}.

    Returns the WSGI-equivalent envelope:
    {"import_result": {...}, "run_snapshot": {...} | null, "branch_snapshot": {...} | null}
    """
    from dataclasses import asdict
    from fastapi.responses import JSONResponse
    # Import via apps.api.app.main re-exports so existing monkeypatch.setattr(
    # api_main, "...", ...) test fixtures continue to work.
    from apps.api.app.main import (  # type: ignore[attr-defined]
        IngestService,
        create_session_factory,
        get_branch_snapshot,
        get_run_snapshot,
        ingest_and_start_pipeline,
    )
    from novel_analyzer.config.settings import get_settings

    content_type = (request.headers.get("content-type") or "").lower()

    title = ""
    pipeline_profile = "auto-lite"
    max_chapters: int | None = None
    database_url: str | None = None
    file_bytes: bytes | None = None
    file_name: str | None = None
    chapters: list[dict] | None = None

    if content_type.startswith("application/json"):
        body = await request.json() or {}
        title = str(body.get("title") or "")
        pipeline_profile = str(body.get("pipeline_profile") or "auto-lite")
        database_url = str(body.get("database_url") or "") or None
        mc_raw = str(body.get("max_chapters") or "").strip()
        max_chapters = int(mc_raw) if mc_raw else None
        chapters_raw = body.get("chapters")
        if isinstance(chapters_raw, list):
            chapters = [item for item in chapters_raw if isinstance(item, dict)]
    else:
        form = await request.form()
        title = str(form.get("title") or "")
        pipeline_profile = str(form.get("pipeline_profile") or "auto-lite")
        database_url = str(form.get("database_url") or "") or None
        mc_raw = str(form.get("max_chapters") or "").strip()
        max_chapters = int(mc_raw) if mc_raw else None
        upload = form.get("file")
        if upload is not None and hasattr(upload, "read"):
            file_bytes = await upload.read()
            file_name = getattr(upload, "filename", None) or "uploaded.txt"

    if file_bytes is None and not chapters:
        return JSONResponse(
            status_code=400,
            content={"error": "missing uploaded file or `chapters` list"},
        )

    runtime = get_settings().model_copy(deep=True)
    if database_url:
        runtime.database_url = database_url

    if file_bytes is not None:
        from novel_analyzer.runtime.storage import runtime_cache_root
        runtime_dir = runtime_cache_root(runtime) / "uploads"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        source_path = runtime_dir / file_name
        source_path.write_bytes(file_bytes)
        path_on_disk = str(source_path)
    else:
        factory = create_session_factory(runtime)
        with factory() as session:
            path_on_disk = IngestService(session, runtime).persist_chapter_list_file(
                chapters or [],
                source_name="api-chapter-list-import",
            )

    try:
        result = ingest_and_start_pipeline(
            path=path_on_disk,
            title=title or None,
            pipeline_profile=pipeline_profile,
            max_chapters=max_chapters,
            database_url=database_url,
        )
        run_snapshot = None
        branch_snapshot = None
        if result.run_id and result.branch_id:
            run_snapshot = get_run_snapshot(
                run_id=result.run_id,
                branch_id=result.branch_id,
                database_url=database_url,
            )
            branch_snapshot = get_branch_snapshot(
                run_id=result.run_id,
                branch_id=result.branch_id,
                database_url=database_url,
            )
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})

    return {
        "import_result": asdict(result),
        "run_snapshot": asdict(run_snapshot) if run_snapshot else None,
        "branch_snapshot": asdict(branch_snapshot) if branch_snapshot else None,
    }


@router.post("/recovery")
async def recovery(request: Request):
    from fastapi.responses import JSONResponse
    from novel_analyzer.application.recovery import recover_branch

    try:
        body = await request.json()
    except Exception:
        body = {}
    if not isinstance(body, dict):
        body = {}

    run_id = str(body.get("run_id") or "")
    branch_id = str(body.get("branch_id") or "")
    action = str(body.get("action") or "")
    if not run_id or not branch_id or not action:
        return JSONResponse(
            status_code=400,
            content={"error": "run_id, branch_id and action are required"},
        )

    chapter_index_raw = str(body.get("chapter_index") or "").strip()
    chapter_index = int(chapter_index_raw) if chapter_index_raw else None
    database_url = str(body.get("database_url") or "") or None

    try:
        return recover_branch(
            action=action,
            run_id=run_id,
            branch_id=branch_id,
            chapter_index=chapter_index,
            database_url=database_url,
        )
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})


@router.get("/branch-exports")
def branch_exports(
    run_id: str = Query(...),
    branch_id: str = Query(...),
    database_url: str | None = Query(None),
):
    from fastapi.responses import JSONResponse
    from novel_analyzer.services.export_service import ExportService

    with get_db_session(database_url) as session:
        try:
            bundle = ExportService(session).export_branch_bundle(run_id, branch_id)
        except Exception as e:
            return JSONResponse(status_code=500, content={"error": str(e)})
        return {
            "run_id": run_id,
            "branch_id": branch_id,
            "has_risk_summary": "risk_summary" in bundle,
            "chapter_count": bundle.get("chapter_count", 0),
            "export_keys": list(bundle.keys()),
        }


class StartRequest(BaseModel):
    run_id: str
    branch_id: str
    pipeline_profile: str = "auto-lite"
    max_chapters: int | None = None
    database_url: str | None = None


@router.post("/start")
def start_pipeline_route(req: StartRequest):
    from fastapi.responses import JSONResponse
    from novel_analyzer.application import start_pipeline as _start_pipeline

    try:
        processed_chapters, next_chapter, pipeline_state = _start_pipeline(
            run_id=req.run_id,
            branch_id=req.branch_id,
            pipeline_profile=req.pipeline_profile,
            max_chapters=req.max_chapters,
            database_url=req.database_url,
        )
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})
    return {
        "processed_chapters": processed_chapters,
        "next_chapter": next_chapter,
        "pipeline_state": pipeline_state,
    }
