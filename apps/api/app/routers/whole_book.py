from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from apps.api.app.routers import get_db_session, resolve_settings

router = APIRouter(prefix="/api/whole-book", tags=["whole-book"])


class WholeBookPlanRequest(BaseModel):
    branch_id: str
    project_title: str
    source_title: str
    target_title: str
    chapter_goals: list[dict[str, Any]]
    database_url: str | None = None


@router.post("/plan")
def whole_book_plan(req: WholeBookPlanRequest) -> dict:
    from novel_analyzer.services.whole_book_imitation_service import WholeBookImitationService

    settings = resolve_settings(req.database_url)
    with get_db_session(req.database_url) as session:
        svc = WholeBookImitationService()
        goals = [(g.get("chapter_index", 0), g.get("goal", "")) for g in req.chapter_goals]
        try:
            plan = svc.build_plan(
                branch_id=req.branch_id,
                project_title=req.project_title,
                source_title=req.source_title,
                target_title=req.target_title,
                chapter_goals=goals,
            )
            return plan.model_dump(mode="json") if hasattr(plan, "model_dump") else {"plan": str(plan)}
        except Exception as e:
            return {"error": str(e)}


class WholeBookExecuteRequest(BaseModel):
    branch_id: str
    project_title: str
    source_title: str
    target_title: str
    chapter_goals: list[dict[str, Any]]
    use_llm: bool = False
    loom_memory_mode: str = "enabled"
    database_url: str | None = None


@router.post("/execute")
def whole_book_execute(req: WholeBookExecuteRequest) -> dict:
    from novel_analyzer.services.whole_book_imitation_service import WholeBookImitationService
    from novel_analyzer.services.imitation_harness_service import ImitationHarnessService

    settings = resolve_settings(req.database_url)
    settings = settings.model_copy(update={
        "loom_memory_mode": req.loom_memory_mode,
        "loom_pairwise_enabled": True,
        "loom_style_enabled": True,
        "loom_character_enabled": True,
    })

    with get_db_session(req.database_url) as session:
        harness = ImitationHarnessService(session, settings)
        svc = WholeBookImitationService()
        goals = [(g.get("chapter_index", 0), g.get("goal", "")) for g in req.chapter_goals]
        try:
            report = svc.execute(
                branch_id=req.branch_id,
                project_title=req.project_title,
                source_title=req.source_title,
                target_title=req.target_title,
                chapter_goals=goals,
                harness=harness,
                use_llm=req.use_llm,
            )
            return report.model_dump(mode="json") if hasattr(report, "model_dump") else {"report": str(report)}
        except Exception as e:
            return {"error": str(e)}


@router.post("/execute-stream")
def whole_book_execute_stream(req: WholeBookExecuteRequest):
    from novel_analyzer.services.imitation_harness_service import ImitationHarnessService

    settings = resolve_settings(req.database_url)
    settings = settings.model_copy(update={
        "loom_memory_mode": req.loom_memory_mode,
        "loom_pairwise_enabled": True,
        "loom_style_enabled": True,
        "loom_character_enabled": True,
    })

    def generate():
        with get_db_session(req.database_url) as session:
            harness = ImitationHarnessService(session, settings)
            for goal_item in req.chapter_goals:
                ch_idx = goal_item.get("chapter_index", 0)
                goal = goal_item.get("goal", "")
                try:
                    event = json.dumps({
                        "type": "chapter_start",
                        "chapter_index": ch_idx,
                        "goal": goal,
                    }, ensure_ascii=False)
                    yield f"data: {event}\n\n"

                    report = harness.run_harness(
                        req.branch_id,
                        source_chapter_index=ch_idx,
                        target_goal=goal,
                        use_llm=req.use_llm,
                    )
                    event = json.dumps({
                        "type": "chapter_done",
                        "chapter_index": ch_idx,
                        "verdict": report.final_verdict,
                        "draft_len": len(report.final_draft.draft_text),
                    }, ensure_ascii=False)
                    yield f"data: {event}\n\n"
                except Exception as e:
                    event = json.dumps({
                        "type": "chapter_error",
                        "chapter_index": ch_idx,
                        "error": str(e),
                    }, ensure_ascii=False)
                    yield f"data: {event}\n\n"

            yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.get("/export")
def whole_book_export(
    run_id: str = Query(...),
    branch_id: str = Query(...),
    database_url: str | None = Query(None),
) -> dict:
    from novel_analyzer.services.export_service import ExportService

    with get_db_session(database_url) as session:
        try:
            bundle = ExportService(session).export_branch_bundle(run_id, branch_id)
            return bundle
        except Exception as e:
            return {"error": str(e)}
