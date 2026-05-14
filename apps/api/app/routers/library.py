from __future__ import annotations

from fastapi import APIRouter, Query
from pydantic import BaseModel

from apps.api.app.routers import get_db_session, resolve_settings

router = APIRouter(prefix="/api", tags=["library"])


@router.get("/library")
def library_list(
    database_url: str | None = Query(None),
    limit: int = Query(20),
) -> dict:
    from sqlalchemy import select, func
    from novel_analyzer.database.models import NovelSource, RunBranch, FactRecord

    with get_db_session(database_url) as session:
        novels = session.scalars(
            select(NovelSource)
            .where(NovelSource.deleted_at.is_(None))
            .order_by(NovelSource.created_at.desc())
            .limit(limit)
        ).all()

        items = []
        for novel in novels:
            runs = novel.runs if hasattr(novel, "runs") else []
            branch_count = 0
            chapter_count = 0
            for run in runs:
                branches = run.branches if hasattr(run, "branches") else []
                branch_count += len(branches)
                for branch in branches:
                    ch_count = session.scalar(
                        select(func.max(FactRecord.chapter_index))
                        .where(FactRecord.branch_id == branch.id)
                        .where(FactRecord.deleted_at.is_(None))
                    ) or 0
                    chapter_count = max(chapter_count, ch_count)

            items.append({
                "id": novel.id,
                "title": novel.title,
                "source_path": novel.source_path,
                "created_at": novel.created_at.isoformat() if novel.created_at else None,
                "run_count": len(runs),
                "branch_count": branch_count,
                "max_chapter_index": chapter_count,
            })

        return {"items": items, "total": len(items)}


@router.get("/run-snapshot")
def run_snapshot(
    run_id: str = Query(...),
    branch_id: str = Query(...),
    database_url: str | None = Query(None),
) -> dict:
    from sqlalchemy import select, func
    from novel_analyzer.database.models import AnalysisRun, RunBranch, FactRecord

    with get_db_session(database_url) as session:
        run = session.scalar(select(AnalysisRun).where(AnalysisRun.id == run_id))
        if not run:
            return {"error": "run not found"}

        branch = session.scalar(select(RunBranch).where(RunBranch.id == branch_id))
        if not branch:
            return {"error": "branch not found"}

        max_chapter = session.scalar(
            select(func.max(FactRecord.chapter_index))
            .where(FactRecord.branch_id == branch_id)
            .where(FactRecord.deleted_at.is_(None))
        ) or 0

        total_facts = session.scalar(
            select(func.count(FactRecord.id))
            .where(FactRecord.branch_id == branch_id)
            .where(FactRecord.deleted_at.is_(None))
        ) or 0

        return {
            "run_id": run.id,
            "novel_id": run.novel_id,
            "branch_id": branch.id,
            "branch_title": branch.title,
            "max_chapter_index": max_chapter,
            "total_facts": total_facts,
            "created_at": run.created_at.isoformat() if run.created_at else None,
        }
