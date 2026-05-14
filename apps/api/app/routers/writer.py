from __future__ import annotations

import json

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from apps.api.app.routers import get_db_session, resolve_settings

router = APIRouter(prefix="/api/writer", tags=["writer"])


class WriterImitateRequest(BaseModel):
    branch_id: str
    chapter_index: int
    target_goal: str
    use_llm: bool = False
    model_name: str | None = None
    loom_memory_mode: str | None = None
    loom_pairwise_enabled: bool = False
    loom_style_enabled: bool = False
    loom_character_enabled: bool = False
    database_url: str | None = None


@router.post("/imitate")
def writer_imitate(req: WriterImitateRequest) -> dict:
    from novel_analyzer.services.imitation_harness_service import ImitationHarnessService

    settings = resolve_settings(req.database_url)
    if req.loom_memory_mode:
        settings = settings.model_copy(update={"loom_memory_mode": req.loom_memory_mode})
    if req.loom_pairwise_enabled:
        settings = settings.model_copy(update={"loom_pairwise_enabled": True})
    if req.loom_style_enabled:
        settings = settings.model_copy(update={"loom_style_enabled": True})
    if req.loom_character_enabled:
        settings = settings.model_copy(update={"loom_character_enabled": True})

    with get_db_session(req.database_url) as session:
        harness = ImitationHarnessService(session, settings)
        report = harness.run_harness(
            req.branch_id,
            source_chapter_index=req.chapter_index,
            target_goal=req.target_goal,
            use_llm=req.use_llm,
            model_name=req.model_name,
        )
        return {
            "source_chapter_index": report.source_chapter_index,
            "target_goal": report.target_goal,
            "final_verdict": report.final_verdict,
            "stop_reason": report.stop_reason,
            "final_draft": {
                "draft_title": report.final_draft.draft_title,
                "draft_text": report.final_draft.draft_text,
            },
            "chapter_quality_signal": report.chapter_quality_signal,
            "dialogue_signal": report.dialogue_signal,
            "rounds_count": len(report.rounds),
            "action_queue_count": len(report.action_queue),
        }


@router.get("/imitate/signals")
def writer_imitate_signals(
    branch_id: str = Query(...),
    chapter_index: int = Query(...),
    database_url: str | None = Query(None),
) -> dict:
    from novel_analyzer.services.imitation_harness_service import ImitationHarnessService

    settings = resolve_settings(database_url)
    settings = settings.model_copy(update={
        "loom_style_enabled": True,
        "loom_pairwise_enabled": True,
        "loom_character_enabled": True,
    })

    with get_db_session(database_url) as session:
        harness = ImitationHarnessService(session, settings)
        report = harness.run_harness(
            branch_id,
            source_chapter_index=chapter_index,
            target_goal="",
            use_llm=False,
        )
        last_round = report.rounds[-1] if report.rounds else None
        skill_outputs = last_round.skill_outputs if last_round else {}
        return {
            "tension": skill_outputs.get("_loom_tension", {}),
            "style": skill_outputs.get("_loom_style", {}),
            "rhythm": skill_outputs.get("_loom_rhythm", {}),
            "character": skill_outputs.get("_loom_character_consistency", {}),
            "reader_sim": skill_outputs.get("_loom_reader_sim", {}),
            "thread_activation": skill_outputs.get("_loom_thread_activation", {}),
            "reference_fidelity": skill_outputs.get("_loom_reference_fidelity", {}),
            "dialogue": report.dialogue_signal,
            "chapter_quality": report.chapter_quality_signal,
        }


@router.post("/imitate-stream")
def writer_imitate_stream(req: WriterImitateRequest):
    from novel_analyzer.services.chapter_imitation_service import ChapterImitationService
    from novel_analyzer.llm.client import build_chat_model
    from novel_analyzer.llm.prompts import build_chapter_imitation_prompt
    from langchain_core.messages import HumanMessage

    settings = resolve_settings(req.database_url)
    if req.loom_memory_mode:
        settings = settings.model_copy(update={"loom_memory_mode": req.loom_memory_mode})

    def generate():
        with get_db_session(req.database_url) as session:
            try:
                cis = ChapterImitationService(session, settings)
                plan = cis.build_imitation_plan(
                    req.branch_id,
                    source_chapter_index=req.chapter_index,
                    target_goal=req.target_goal,
                )
                title, source_text = cis._source_chapter_text(req.branch_id, req.chapter_index)

                previous_summary = ""
                if settings.loom_memory_mode in ("enabled", "ab") and req.chapter_index >= 10:
                    try:
                        from novel_analyzer.services.memory_assembler_service import MemoryAssemblerService
                        mem_svc = MemoryAssemblerService(session)
                        mem = mem_svc.assemble(req.branch_id, target_chapter_index=req.chapter_index + 1)
                        previous_summary = mem.recent_summary
                    except Exception:
                        pass

                prompt = build_chapter_imitation_prompt(
                    source_chapter_index=req.chapter_index,
                    source_title=title,
                    source_excerpt=source_text[:2500],
                    target_goal=req.target_goal,
                    style_axes=plan.style_axes,
                    scene_beats=plan.scene_beats,
                    hard_constraints=plan.hard_constraints,
                    soft_constraints=plan.soft_constraints,
                    previous_summary=previous_summary,
                )

                model = build_chat_model(settings, model_name=req.model_name)
                for chunk in model.stream([HumanMessage(content=prompt)]):
                    content = chunk.content if hasattr(chunk, "content") else str(chunk)
                    if content:
                        event = json.dumps({"type": "chunk", "content": content}, ensure_ascii=False)
                        yield f"data: {event}\n\n"

                yield f"data: {json.dumps({'type': 'done'})}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
