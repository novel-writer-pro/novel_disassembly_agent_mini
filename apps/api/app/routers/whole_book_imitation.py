"""WSGI-canonical /api/whole-book-imitation-* endpoints.

These mirror the WSGI surface (with hyphens). The existing
whole_book.py router exposes a parallel /api/whole-book/* namespace
that v5 keeps for now but is not what current clients target.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Query, Request

router = APIRouter(tags=["whole-book-imitation"])


@router.get("/api/whole-book-imitation-readiness")
def readiness(
    branch_id: str | None = Query(None),
    database_url: str | None = Query(None),
):
    from fastapi.responses import JSONResponse
    from apps.api.app.main import _whole_book_readiness_payload

    try:
        payload = _whole_book_readiness_payload(branch_id, database_url)
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})
    return payload


@router.post("/api/whole-book-imitation-run")
def run(request: Request, body: dict[str, Any] = Body(...)):
    from fastapi.responses import JSONResponse
    from novel_analyzer.config.settings import get_settings
    from novel_analyzer.database.session import create_session_factory
    from novel_analyzer.services.whole_book_imitation_service import WholeBookImitationService
    from apps.api.app.main import (
        _whole_book_mapping_pack,
        _whole_book_chapter_goals,
        _whole_book_run_error_payload,
    )

    required = ["branch_id", "project_title", "source_work_name", "target_work_name", "chapter_specs"]
    missing_key = next((key for key in required if not body.get(key)), None)
    if missing_key is not None:
        return JSONResponse(status_code=400, content={"error": f"missing required field: {missing_key}"})

    runtime = get_settings().model_copy(deep=True)
    database_url = str(body.get("database_url") or "").strip()
    if database_url:
        runtime.database_url = database_url

    try:
        mapping_pack = _whole_book_mapping_pack(body)
        chapter_goals = _whole_book_chapter_goals(body)
        execute = bool(body.get("execute"))
        max_rounds = int(body.get("max_rounds") or 1)
        use_llm = bool(body.get("use_llm"))
        model_name = str(body.get("model_name") or "").strip() or None
        factory = create_session_factory(runtime)
        with factory() as session:
            service = WholeBookImitationService(session)
            report = (
                service.run_in_sandbox(
                    str(body["branch_id"]),
                    mapping_pack=mapping_pack,
                    chapter_goals=chapter_goals,
                    max_rounds=max_rounds,
                    use_llm=use_llm,
                    model_name=model_name,
                )
                if execute
                else service.build_run_queue(
                    str(body["branch_id"]),
                    mapping_pack=mapping_pack,
                    chapter_goals=chapter_goals,
                )
            )
    except Exception as exc:  # noqa: BLE001
        status_str, payload = _whole_book_run_error_payload(exc)
        status_code = int(status_str.split()[0])
        return JSONResponse(status_code=status_code, content=payload)

    return report.model_dump(mode="json")
