from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Query
from pydantic import BaseModel

from apps.api.app.routers import get_db_session, resolve_settings

router = APIRouter(prefix="/api", tags=["risk-review"])


@router.get("/review-clusters")
def review_clusters(
    run_id: str = Query(...),
    branch_id: str = Query(...),
    severity: str | None = Query(None),
    status: str | None = Query(None),
    database_url: str | None = Query(None),
) -> dict:
    from novel_analyzer.services.export_service import ExportService

    with get_db_session(database_url) as session:
        bundle = ExportService(session).export_branch_bundle(run_id, branch_id)
        candidate_clusters = cast(
            list[dict[str, object]],
            bundle.get("risk_summary", {}).get("review_candidate_clusters", []),
        )
        items = _filter_clusters(candidate_clusters, severity, status)
        return {
            "review_storage_mode": bundle.get("review_storage_mode"),
            "total": len(candidate_clusters),
            "filtered": len(items),
            "items": items,
        }


@router.get("/review-cluster-summary")
def review_cluster_summary(
    run_id: str = Query(...),
    branch_id: str = Query(...),
    database_url: str | None = Query(None),
) -> dict:
    from novel_analyzer.services.export_service import ExportService

    with get_db_session(database_url) as session:
        bundle = ExportService(session).export_branch_bundle(run_id, branch_id)
        candidate_clusters = cast(
            list[dict[str, object]],
            bundle.get("risk_summary", {}).get("review_candidate_clusters", []),
        )
        severity_counts: dict[str, int] = {}
        status_counts: dict[str, int] = {}
        for cluster in candidate_clusters:
            sev = str(cluster.get("severity", "unknown"))
            st = str(cluster.get("status", "pending"))
            severity_counts[sev] = severity_counts.get(sev, 0) + 1
            status_counts[st] = status_counts.get(st, 0) + 1

        return {
            "total_clusters": len(candidate_clusters),
            "severity_distribution": severity_counts,
            "status_distribution": status_counts,
            "risk_level": bundle.get("risk_summary", {}).get("overall_risk_level", "unknown"),
        }


class ReviewUpdateRequest(BaseModel):
    run_id: str
    branch_id: str
    cluster_key: str
    action: str
    notes: str = ""
    database_url: str | None = None


@router.post("/review-cluster-update")
def review_cluster_update(req: ReviewUpdateRequest) -> dict:
    from novel_analyzer.services.cluster_review_service import ClusterReviewService

    with get_db_session(req.database_url) as session:
        svc = ClusterReviewService(session)
        try:
            svc.update_cluster_status(
                branch_id=req.branch_id,
                cluster_key=req.cluster_key,
                action=req.action,
                notes=req.notes,
            )
            session.commit()
            return {"status": "ok", "cluster_key": req.cluster_key, "action": req.action}
        except Exception as e:
            return {"error": str(e)}


@router.get("/risk-audit")
def risk_audit(
    branch_id: str = Query(...),
    chapter_index: int = Query(...),
    database_url: str | None = Query(None),
) -> dict:
    from novel_analyzer.services.risk_audit_service import RiskAuditService

    settings = resolve_settings(database_url)
    with get_db_session(database_url) as session:
        svc = RiskAuditService(session, settings)
        try:
            report = svc.audit_chapter(branch_id, chapter_index)
            return report
        except Exception as e:
            return {"error": str(e)}


@router.get("/risk-signals")
def risk_signals(
    branch_id: str = Query(...),
    chapter_index: int = Query(...),
    limit: int = Query(50),
    database_url: str | None = Query(None),
) -> dict:
    from sqlalchemy import select
    from novel_analyzer.database.models import RiskSemanticSignalRecord

    with get_db_session(database_url) as session:
        signals = session.scalars(
            select(RiskSemanticSignalRecord)
            .where(RiskSemanticSignalRecord.branch_id == branch_id)
            .where(RiskSemanticSignalRecord.chapter_index == chapter_index)
            .where(RiskSemanticSignalRecord.deleted_at.is_(None))
            .order_by(RiskSemanticSignalRecord.confidence.desc())
            .limit(limit)
        ).all()
        items = [
            {
                "id": s.id,
                "signal_type": s.signal_type,
                "raw_text": s.raw_text[:200],
                "canonical_label": s.canonical_label,
                "canonical_group": s.canonical_group,
                "confidence": s.confidence,
                "status": s.status,
            }
            for s in signals
        ]
        return {"items": items, "total": len(items)}


def _filter_clusters(
    clusters: list[dict[str, object]],
    severity: str | None,
    status: str | None,
) -> list[dict[str, object]]:
    result = clusters
    if severity:
        result = [c for c in result if str(c.get("severity", "")) == severity]
    if status:
        result = [c for c in result if str(c.get("status", "")) == status]
    return result
