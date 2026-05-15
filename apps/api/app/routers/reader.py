from __future__ import annotations

from fastapi import APIRouter, Body, Query
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/reader", tags=["reader"])


@router.post("/feedback")
def submit_feedback(payload: dict = Body(...)):
    branch_id = str(payload.get("branch_id") or "")
    chapter_index_raw = str(payload.get("chapter_index") or "").strip()
    rating_raw = str(payload.get("rating") or "").strip()
    comment = str(payload.get("comment") or "")
    if not branch_id or not chapter_index_raw or not rating_raw:
        return JSONResponse(
            status_code=400,
            content={"error": "branch_id, chapter_index, and rating are required"},
        )
    try:
        chapter_index = int(chapter_index_raw)
        rating = int(rating_raw)
        if not (1 <= rating <= 5):
            raise ValueError("rating must be 1-5")
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})

    database_url = str(payload.get("database_url") or "") or None
    from novel_analyzer.config.settings import get_settings
    from apps.api.app.main import create_session_factory
    from novel_analyzer.services.reader_feedback_service import ReaderFeedbackService

    runtime = get_settings().model_copy(deep=True)
    if database_url:
        runtime.database_url = database_url
    try:
        factory = create_session_factory(runtime)
        with factory() as session:
            svc = ReaderFeedbackService(session)
            stars = "★" * rating
            comment_text = f"{stars} {comment}".strip() if comment else stars
            svc.record_comment(branch_id, chapter_index, comment_text)
            session.commit()
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})
    return {"ok": True}


@router.get("/feedback-summary")
def feedback_summary(
    branch_id: str = Query(...),
    database_url: str | None = Query(None),
):
    from novel_analyzer.config.settings import get_settings
    from apps.api.app.main import create_session_factory
    from novel_analyzer.services.reader_feedback_service import ReaderFeedbackService

    runtime = get_settings().model_copy(deep=True)
    if database_url:
        runtime.database_url = database_url
    try:
        factory = create_session_factory(runtime)
        with factory() as session:
            svc = ReaderFeedbackService(session)
            summary = svc.summarize_branch_feedback(branch_id)
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})
    return summary
