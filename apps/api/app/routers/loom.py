from __future__ import annotations

from fastapi import APIRouter, Query
from pydantic import BaseModel

from apps.api.app.routers import get_db_session, resolve_settings

router = APIRouter(prefix="/api/loom", tags=["loom"])


class LoomStatusResponse(BaseModel):
    branch_id: str
    total_facts: int
    active_facts: int
    total_graph_nodes: int
    contradiction_nodes: int
    evolution_nodes: int
    loom_memory_mode: str
    tension: dict | None = None
    style: dict | None = None
    reader_sim: dict | None = None
    long_book_health: dict | None = None


@router.get("/status")
def loom_status(
    branch_id: str = Query(...),
    database_url: str | None = Query(None),
) -> LoomStatusResponse:
    from sqlalchemy import func, select
    from novel_analyzer.database.models import FactRecord, GraphNode
    from novel_analyzer.services.tension_service import TensionService

    settings = resolve_settings(database_url)
    with get_db_session(database_url) as session:
        total_facts = session.scalar(
            select(func.count(FactRecord.id))
            .where(FactRecord.branch_id == branch_id)
            .where(FactRecord.deleted_at.is_(None))
        ) or 0
        active_facts = session.scalar(
            select(func.count(FactRecord.id))
            .where(FactRecord.branch_id == branch_id)
            .where(FactRecord.episodic_status == "active")
            .where(FactRecord.deleted_at.is_(None))
        ) or 0
        total_nodes = session.scalar(
            select(func.count(GraphNode.id))
            .where(GraphNode.branch_id == branch_id)
            .where(GraphNode.deleted_at.is_(None))
        ) or 0
        contradiction_nodes = session.scalar(
            select(func.count(GraphNode.id))
            .where(GraphNode.branch_id == branch_id)
            .where(GraphNode.conflict_status == "contradiction")
            .where(GraphNode.deleted_at.is_(None))
        ) or 0
        evolution_nodes = session.scalar(
            select(func.count(GraphNode.id))
            .where(GraphNode.branch_id == branch_id)
            .where(GraphNode.conflict_status == "evolution")
            .where(GraphNode.deleted_at.is_(None))
        ) or 0

        latest_chapter = session.scalar(
            select(func.max(FactRecord.chapter_index))
            .where(FactRecord.branch_id == branch_id)
            .where(FactRecord.deleted_at.is_(None))
        )

        tension_data = None
        style_data = None
        reader_sim_data = None
        health_data = None

        if latest_chapter:
            try:
                tension_svc = TensionService(session)
                score = tension_svc.compute(branch_id, chapter_index=latest_chapter)
                tension_data = score.to_operator_signal()
            except Exception:
                pass

            if settings.loom_style_enabled:
                try:
                    from novel_analyzer.services.style_calibration_service import StyleCalibrationService
                    from novel_analyzer.services.rhythm_analysis_service import RhythmAnalysisService
                    from novel_analyzer.services.reader_simulation_service import ReaderSimulationService

                    style_svc = StyleCalibrationService(session)
                    style_result = style_svc.compute_style_drift(branch_id, latest_chapter)
                    style_data = style_result.to_style_signal()

                    reader_svc = ReaderSimulationService(session)
                    reader_result = reader_svc.simulate_all_panels(branch_id, latest_chapter)
                    reader_sim_data = reader_result.to_reader_satisfaction()
                except Exception:
                    pass

            if settings.loom_character_enabled:
                try:
                    from novel_analyzer.services.long_book_health_service import LongBookHealthService
                    health_svc = LongBookHealthService(session)
                    health = health_svc.compute_health(branch_id, latest_chapter)
                    health_data = health.to_health_signal()
                except Exception:
                    pass

        return LoomStatusResponse(
            branch_id=branch_id,
            total_facts=total_facts,
            active_facts=active_facts,
            total_graph_nodes=total_nodes,
            contradiction_nodes=contradiction_nodes,
            evolution_nodes=evolution_nodes,
            loom_memory_mode=settings.loom_memory_mode,
            tension=tension_data,
            style=style_data,
            reader_sim=reader_sim_data,
            long_book_health=health_data,
        )


@router.get("/assemble")
def loom_assemble(
    branch_id: str = Query(...),
    target_chapter: int = Query(...),
    database_url: str | None = Query(None),
) -> dict:
    from novel_analyzer.services.memory_assembler_service import MemoryAssemblerService

    settings = resolve_settings(database_url)
    with get_db_session(database_url) as session:
        svc = MemoryAssemblerService(session)
        mem = svc.assemble(branch_id, target_chapter_index=target_chapter)
        return mem.to_carry_over_state()


@router.get("/reference-eval")
def loom_reference_eval(
    branch_id: str = Query(...),
    chapter_index: int = Query(...),
    draft_dir: str = Query(...),
    database_url: str | None = Query(None),
) -> dict:
    import json
    from pathlib import Path
    from novel_analyzer.services.chapter_imitation_service import ChapterImitationService
    from novel_analyzer.services.reference_eval_service import ReferenceEvalService
    from novel_analyzer.llm.client import build_chat_model
    from langchain_core.messages import HumanMessage

    settings = resolve_settings(database_url)
    with get_db_session(database_url) as session:
        cis = ChapterImitationService(session, settings)
        title, original_text = cis._source_chapter_text(branch_id, chapter_index)

        artifact_path = Path(draft_dir) / f"writer-imitate-ch{chapter_index}.json"
        if not artifact_path.exists():
            return {"error": f"artifact not found: {artifact_path}"}

        payload = json.loads(artifact_path.read_text(encoding="utf-8"))
        fd = payload.get("final_draft", {})
        draft_text = str(fd.get("draft_text", "")).strip() if isinstance(fd, dict) else ""
        if not draft_text:
            return {"error": "draft_text is empty"}

        class _Adapter:
            def __init__(self, model):
                self._model = model
            def chat(self, prompt: str) -> str:
                return str(self._model.invoke([HumanMessage(content=prompt)]).content)

        try:
            llm_client = _Adapter(build_chat_model(settings))
        except Exception:
            llm_client = None

        ref_svc = ReferenceEvalService(llm_client=llm_client)
        result = ref_svc.evaluate(
            branch_id=branch_id,
            chapter_index=chapter_index,
            original_text=original_text,
            draft_text=draft_text,
            chapter_goal=str(payload.get("target_goal", "")),
        )
        return result.to_signal()


@router.get("/signals")
def loom_signals(
    branch_id: str = Query(...),
    chapter_index: int = Query(...),
    database_url: str | None = Query(None),
) -> dict:
    from novel_analyzer.services.tension_service import TensionService
    from novel_analyzer.services.dialogue_signal_service import DialogueSignalService

    settings = resolve_settings(database_url)
    with get_db_session(database_url) as session:
        result: dict = {}

        try:
            tension_svc = TensionService(session)
            score = tension_svc.compute(branch_id, chapter_index)
            result["tension"] = score.to_operator_signal()
        except Exception:
            result["tension"] = None

        if settings.loom_style_enabled:
            try:
                from novel_analyzer.services.style_calibration_service import StyleCalibrationService
                from novel_analyzer.services.rhythm_analysis_service import RhythmAnalysisService
                style_svc = StyleCalibrationService(session)
                rhythm_svc = RhythmAnalysisService(session)
                result["style"] = style_svc.compute_style_drift(branch_id, chapter_index).to_style_signal()
                result["rhythm"] = rhythm_svc.compute(branch_id, chapter_index).to_rhythm_signal()
            except Exception:
                pass

        if settings.loom_pairwise_enabled:
            try:
                dialogue_svc = DialogueSignalService(session)
                result["dialogue"] = dialogue_svc.compute(branch_id, chapter_index).to_dialogue_signal()
            except Exception:
                pass

        return result
