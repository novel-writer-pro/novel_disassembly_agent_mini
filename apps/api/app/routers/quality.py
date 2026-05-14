from __future__ import annotations

from fastapi import APIRouter, Query

from apps.api.app.routers import get_db_session, resolve_settings

router = APIRouter(prefix="/api/quality", tags=["quality"])


@router.get("/health")
def quality_health(
    branch_id: str = Query(...),
    database_url: str | None = Query(None),
) -> dict:
    from sqlalchemy import func, select
    from novel_analyzer.database.models import FactRecord
    from novel_analyzer.services.long_book_health_service import LongBookHealthService

    settings = resolve_settings(database_url)
    with get_db_session(database_url) as session:
        latest_chapter = session.scalar(
            select(func.max(FactRecord.chapter_index))
            .where(FactRecord.branch_id == branch_id)
            .where(FactRecord.deleted_at.is_(None))
        )
        if not latest_chapter:
            return {"error": "no data for branch"}

        svc = LongBookHealthService(session)
        report = svc.compute_health(branch_id, latest_chapter)
        return report.to_health_signal()


@router.get("/trend")
def quality_trend(
    branch_id: str = Query(...),
    database_url: str | None = Query(None),
) -> dict:
    from sqlalchemy import func, select
    from novel_analyzer.database.models import FactRecord
    from novel_analyzer.services.long_book_health_service import LongBookHealthService

    settings = resolve_settings(database_url)
    with get_db_session(database_url) as session:
        latest_chapter = session.scalar(
            select(func.max(FactRecord.chapter_index))
            .where(FactRecord.branch_id == branch_id)
            .where(FactRecord.deleted_at.is_(None))
        )
        if not latest_chapter:
            return {"error": "no data for branch"}

        svc = LongBookHealthService(session)
        report = svc.compute_health(branch_id, latest_chapter, lookback_n=20)
        return {
            "branch_id": branch_id,
            "as_of_chapter": latest_chapter,
            "health_score": report.health_score,
            "quality_trend": report.quality_trend,
            "recent_quality_scores": report.recent_quality_scores,
            "is_declining": svc.detect_quality_decline(branch_id, latest_chapter),
        }


@router.get("/gate-summary")
def quality_gate_summary(
    branch_id: str = Query(...),
    database_url: str | None = Query(None),
) -> dict:
    from pathlib import Path
    from novel_analyzer.cli.app import (
        _collect_writer_output_loom_signals,
        _build_session_loom_gate_summary,
    )

    settings = resolve_settings(database_url)
    return {
        "branch_id": branch_id,
        "gate_summary": {
            "contract_version": "loom-gate-summary.v2",
            "note": "use loom-status CLI or whole-book export for full gate summary",
        },
    }


@router.get("/pairs-stats")
def quality_pairs_stats(
    pairs_file: str = Query("output/loom-pairs.jsonl"),
) -> dict:
    import json
    from pathlib import Path

    path = Path(pairs_file)
    if not path.exists():
        return {"error": f"pairs file not found: {pairs_file}", "total_pairs": 0}

    pairs = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            try:
                pairs.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    if not pairs:
        return {"total_pairs": 0, "target": 500, "progress_pct": 0.0}

    quality_scores = [p.get("quality_score", 0.5) for p in pairs if isinstance(p.get("quality_score"), (int, float))]
    preferences = {}
    methods = {}
    for p in pairs:
        pref = str(p.get("overall_preference", "unknown"))
        preferences[pref] = preferences.get(pref, 0) + 1
        method = str(p.get("evaluation_method", "unknown"))
        methods[method] = methods.get(method, 0) + 1

    chapters = sorted(set(p.get("chapter_index", 0) for p in pairs if isinstance(p.get("chapter_index"), int)))

    return {
        "total_pairs": len(pairs),
        "target": 500,
        "progress_pct": round(len(pairs) / 500 * 100, 1),
        "avg_quality_score": round(sum(quality_scores) / len(quality_scores), 4) if quality_scores else None,
        "unique_chapters": len(chapters),
        "chapter_range": f"{min(chapters)}-{max(chapters)}" if chapters else "",
        "preference_distribution": preferences,
        "evaluation_method_distribution": methods,
    }

