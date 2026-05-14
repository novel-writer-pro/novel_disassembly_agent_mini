from __future__ import annotations

import json
from typing import AsyncGenerator

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from apps.api.app.routers import get_db_session, resolve_settings

router = APIRouter(prefix="/api", tags=["pipeline"])


class PipelineStartRequest(BaseModel):
    branch_id: str
    start_chapter: int
    end_chapter: int
    database_url: str | None = None


@router.post("/pipeline/start-range")
def pipeline_start_range(req: PipelineStartRequest) -> dict:
    from novel_analyzer.services.analysis_service import AnalysisService

    settings = resolve_settings(req.database_url)
    with get_db_session(req.database_url) as session:
        svc = AnalysisService(session, settings)
        try:
            result = svc.analyze_range(
                req.branch_id,
                start_chapter=req.start_chapter,
                end_chapter=req.end_chapter,
            )
            return {
                "status": "completed",
                "branch_id": req.branch_id,
                "start_chapter": req.start_chapter,
                "end_chapter": req.end_chapter,
                "chapters_processed": result.get("chapters_processed", 0) if isinstance(result, dict) else 0,
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}


@router.get("/pipeline/runs")
def pipeline_runs(
    branch_id: str = Query(...),
    limit: int = Query(10),
    database_url: str | None = Query(None),
) -> dict:
    from sqlalchemy import select
    from novel_analyzer.database.models import ChapterJob

    with get_db_session(database_url) as session:
        jobs = session.scalars(
            select(ChapterJob)
            .where(ChapterJob.branch_id == branch_id)
            .where(ChapterJob.deleted_at.is_(None))
            .order_by(ChapterJob.created_at.desc())
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
        return {"items": items}


class AskBranchRequest(BaseModel):
    branch_id: str
    question: str
    database_url: str | None = None


@router.post("/ask-branch")
def ask_branch(req: AskBranchRequest) -> dict:
    from novel_analyzer.services.branch_qa_service import BranchQaService

    settings = resolve_settings(req.database_url)
    with get_db_session(req.database_url) as session:
        svc = BranchQaService(session, settings)
        try:
            result = svc.ask(req.branch_id, req.question)
            return {"answer": result.answer, "sources": result.sources}
        except Exception as e:
            return {"error": str(e)}


@router.post("/ask-branch-stream")
def ask_branch_stream(req: AskBranchRequest):
    from novel_analyzer.services.branch_qa_service import BranchQaService

    settings = resolve_settings(req.database_url)

    def generate():
        with get_db_session(req.database_url) as session:
            svc = BranchQaService(session, settings)
            try:
                for chunk in svc.ask_stream(req.branch_id, req.question):
                    event = json.dumps({"type": "chunk", "content": chunk}, ensure_ascii=False)
                    yield f"data: {event}\n\n"
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.get("/search-branch")
@router.post("/search-branch")
def search_branch(
    branch_id: str = Query(...),
    q: str = Query(..., alias="q"),
    limit: int = Query(10),
    database_url: str | None = Query(None),
) -> dict:
    query = q  # WSGI canonical names this 'q'
    from novel_analyzer.services.retrieval_service import RetrievalService

    settings = resolve_settings(database_url)
    with get_db_session(database_url) as session:
        svc = RetrievalService(session, settings)
        try:
            hits = svc.search(branch_id, query, top_k=limit)
            return {
                "query": query,
                "hits": [
                    {
                        "chunk_text": h.chunk_text[:300],
                        "chapter_index": h.chapter_index,
                        "score": h.score,
                    }
                    for h in hits
                ],
            }
        except Exception as e:
            return {"error": str(e)}
