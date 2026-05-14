from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Query, UploadFile, File, Form
from pydantic import BaseModel

from apps.api.app.routers import get_db_session, resolve_settings

router = APIRouter(prefix="/api", tags=["import-recovery"])


@router.post("/import")
async def import_novel(
    file: UploadFile = File(None),
    title: str = Form(""),
    pipeline_profile: str = Form("auto-lite"),
    max_chapters: int | None = Form(None),
    database_url: str | None = Form(None),
) -> dict:
    from novel_analyzer.services.ingest_service import IngestService

    settings = resolve_settings(database_url)

    if file is None:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=400, content={"error": "missing uploaded file or `chapters` list"})

    content = await file.read()
    text = content.decode("utf-8", errors="ignore")

    runtime_dir = Path(".cache/runtime/uploads")
    runtime_dir.mkdir(parents=True, exist_ok=True)
    source_path = runtime_dir / (file.filename or "uploaded.txt")
    source_path.write_text(text, encoding="utf-8")

    with get_db_session(database_url) as session:
        svc = IngestService(session, settings)
        try:
            result = svc.ingest(
                source_path=str(source_path),
                title=title or file.filename or "Untitled",
                max_chapters=max_chapters,
            )
            session.commit()
            return {
                "status": "ok",
                "novel_id": result.get("novel_id"),
                "run_id": result.get("run_id"),
                "branch_id": result.get("branch_id"),
                "chapter_count": result.get("chapter_count", 0),
            }
        except Exception as e:
            return {"error": str(e)}


class RecoveryRequest(BaseModel):
    branch_id: str
    chapter_index: int | None = None
    action: str = "retry"
    database_url: str | None = None


@router.post("/recovery")
def recovery(req: RecoveryRequest) -> dict:
    from novel_analyzer.services.analysis_service import AnalysisService

    settings = resolve_settings(req.database_url)
    with get_db_session(req.database_url) as session:
        svc = AnalysisService(session, settings)
        try:
            if req.action == "retry" and req.chapter_index is not None:
                result = svc.analyze_range(
                    req.branch_id,
                    start_chapter=req.chapter_index,
                    end_chapter=req.chapter_index,
                )
                session.commit()
                return {"status": "ok", "action": "retry", "chapter_index": req.chapter_index}
            return {"error": f"unsupported action: {req.action}"}
        except Exception as e:
            return {"error": str(e)}


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
