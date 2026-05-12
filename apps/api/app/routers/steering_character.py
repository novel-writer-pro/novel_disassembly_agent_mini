from __future__ import annotations

from fastapi import APIRouter, Query
from pydantic import BaseModel

from apps.api.app.routers import get_db_session, resolve_settings

router = APIRouter(prefix="/api", tags=["steering-character"])


@router.get("/steering/retrieve")
def steering_retrieve(
    query: str = Query(...),
    database_url: str | None = Query(None),
) -> dict:
    from novel_analyzer.services.steering_library_service import SteeringLibraryService

    try:
        svc = SteeringLibraryService()
        result = svc.retrieve_pack(query_text=query)
        return result
    except Exception as e:
        return {"error": str(e)}


@router.get("/character/persona")
def character_persona(
    branch_id: str = Query(...),
    character_name: str = Query(...),
    as_of_chapter: int = Query(...),
    database_url: str | None = Query(None),
) -> dict:
    from novel_analyzer.services.character_agent_service import CharacterAgentService

    settings = resolve_settings(database_url)
    with get_db_session(database_url) as session:
        try:
            svc = CharacterAgentService(session)
            persona = svc.build_character_persona(branch_id, character_name, as_of_chapter)
            return persona.to_dict() if hasattr(persona, "to_dict") else {
                "character_name": character_name,
                "branch_id": branch_id,
                "as_of_chapter": as_of_chapter,
                "values": persona.values if hasattr(persona, "values") else [],
                "goals": persona.goals if hasattr(persona, "goals") else [],
                "speech_style": persona.speech_style if hasattr(persona, "speech_style") else {},
                "consistency_score": persona.consistency_score if hasattr(persona, "consistency_score") else 0.0,
            }
        except Exception as e:
            return {"error": str(e)}


@router.get("/character/consistency")
def character_consistency(
    branch_id: str = Query(...),
    character_name: str = Query(...),
    chapter_index: int = Query(...),
    draft_text: str = Query(""),
    database_url: str | None = Query(None),
) -> dict:
    from novel_analyzer.services.character_agent_service import CharacterAgentService

    settings = resolve_settings(database_url)
    with get_db_session(database_url) as session:
        try:
            svc = CharacterAgentService(session)
            persona = svc.build_character_persona(branch_id, character_name, chapter_index - 1)
            result = svc.check_character_consistency(persona, draft_text, chapter_index)
            return {
                "character_name": character_name,
                "chapter_index": chapter_index,
                "alert_level": result.alert_level,
                "overall_consistency_score": result.overall_consistency_score,
                "suggestion": result.suggestion,
            }
        except Exception as e:
            return {"error": str(e)}


@router.post("/loom/consolidate")
def loom_consolidate(
    branch_id: str = Query(...),
    chapter_index: int = Query(...),
    database_url: str | None = Query(None),
) -> dict:
    from novel_analyzer.services.memory_consolidation_service import MemoryConsolidationService

    with get_db_session(database_url) as session:
        try:
            svc = MemoryConsolidationService(session)
            result = svc.consolidate(branch_id, chapter_index)
            session.commit()
            return {
                "branch_id": branch_id,
                "chapter_index": chapter_index,
                "contradictions": len(result.contradictions),
                "evolutions": len(result.evolutions),
                "ambiguities": len(result.ambiguities),
                "human_review_required": result.human_review_required,
            }
        except Exception as e:
            return {"error": str(e)}


class AbCompareRequest(BaseModel):
    baseline_dir: str
    loom_dir: str


@router.post("/loom/ab-compare")
def loom_ab_compare(req: AbCompareRequest) -> dict:
    import json
    from pathlib import Path
    from novel_analyzer.cli.app import _loom_load_chapter_artifacts, _loom_final_draft_text, _loom_extract_signals

    baseline_artifacts = _loom_load_chapter_artifacts(Path(req.baseline_dir))
    loom_artifacts = _loom_load_chapter_artifacts(Path(req.loom_dir))
    common_chapters = sorted(set(baseline_artifacts) & set(loom_artifacts))

    if not common_chapters:
        return {"error": "no matching chapters", "total": 0}

    chapter_results = []
    for ch_idx in common_chapters:
        b_signals = _loom_extract_signals(baseline_artifacts[ch_idx])
        l_signals = _loom_extract_signals(loom_artifacts[ch_idx])
        chapter_results.append({
            "chapter_index": ch_idx,
            "baseline_tension": b_signals.get("tension", {}).get("tension_score"),
            "loom_tension": l_signals.get("tension", {}).get("tension_score"),
            "baseline_reader_sim": b_signals.get("reader_sim", {}).get("overall_score"),
            "loom_reader_sim": l_signals.get("reader_sim", {}).get("overall_score"),
            "baseline_fidelity": b_signals.get("reference_fidelity", {}).get("overall_fidelity"),
            "loom_fidelity": l_signals.get("reference_fidelity", {}).get("overall_fidelity"),
        })

    return {
        "total_chapters": len(common_chapters),
        "chapter_results": chapter_results,
    }
