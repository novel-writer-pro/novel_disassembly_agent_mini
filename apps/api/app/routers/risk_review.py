from __future__ import annotations

import json
from typing import cast

from fastapi import APIRouter, Body, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel

from apps.api.app.routers import get_db_session, resolve_settings

router = APIRouter(prefix="/api", tags=["risk-review"])


def _wsgi_json_response(payload: dict, *, status_code: int = 200) -> Response:
    """JSON response with `, ` + `: ` separators to match WSGI canonical output.

    Several test assertions are byte-substring matches like
    `b'"contract_version": "review-workflow.v1"'` (note the space after colon).
    FastAPI's default JSONResponse emits compact `, ` and `:` separators which
    lose those spaces. Mirroring the WSGI `json.dumps(..., indent=2)` keeps the
    canonical bytes contract.
    """
    body = json.dumps(payload, ensure_ascii=False, indent=2)
    return Response(content=body, status_code=status_code, media_type="application/json")


@router.get("/review-clusters")
def review_clusters(
    request: Request,
    run_id: str = Query(...),
    branch_id: str = Query(...),
    database_url: str | None = Query(None),
) -> dict:
    from apps.api.app.main import get_settings
    from novel_analyzer.services.export_service import ExportService
    from apps.api.app.main import (
        _apply_review_filters,
        _review_contract,
        _review_filters,
        create_session_factory,
    )

    raw_params = {key: str(value) for key, value in request.query_params.items()}
    filters = _review_filters(raw_params)

    runtime = get_settings().model_copy(deep=True)
    if database_url:
        runtime.database_url = database_url

    factory = create_session_factory(runtime)
    with factory() as session:
        bundle = ExportService(session).export_branch_bundle(run_id, branch_id)
        candidate_clusters = cast(
            list[dict[str, object]],
            bundle.get("risk_summary", {}).get("review_candidate_clusters", []),
        )
        items = _apply_review_filters(candidate_clusters, filters)
        return _wsgi_json_response({
            **_review_contract(),
            "review_storage_mode": bundle.get("review_storage_mode"),
            "filters": filters,
            "items": items,
        })


@router.get("/review-cluster-summary")
def review_cluster_summary(
    request: Request,
    run_id: str = Query(...),
    branch_id: str = Query(...),
    database_url: str | None = Query(None),
) -> dict:
    from apps.api.app.main import get_settings
    from novel_analyzer.services.export_service import ExportService
    from apps.api.app.main import (
        _apply_review_filters,
        _review_contract,
        _review_filters,
        _review_summary_payload,
        create_session_factory,
    )

    raw_params = {key: str(value) for key, value in request.query_params.items()}
    filters = _review_filters(raw_params)

    runtime = get_settings().model_copy(deep=True)
    if database_url:
        runtime.database_url = database_url

    factory = create_session_factory(runtime)
    with factory() as session:
        bundle = ExportService(session).export_branch_bundle(run_id, branch_id)
        candidate_clusters = cast(
            list[dict[str, object]],
            bundle.get("risk_summary", {}).get("review_candidate_clusters", []),
        )
        items = _apply_review_filters(candidate_clusters, filters)
        payload = _review_summary_payload(
            items=items,
            review_storage_mode=bundle.get("review_storage_mode"),
            filters=filters,
        )
        return _wsgi_json_response({**_review_contract(), **payload})


class ReviewUpdateRequest(BaseModel):
    branch_id: str = ""
    cluster_key: str = ""
    cluster_status: str = ""
    review_notes: str = ""
    review_owner: str = ""
    review_actor: str = ""
    review_result: str = ""
    resolved_at: str = ""
    database_url: str | None = None


@router.post("/review-cluster-update")
def review_cluster_update(req: ReviewUpdateRequest):
    from dataclasses import asdict
    from fastapi.responses import JSONResponse
    from apps.api.app.main import get_settings
    from novel_analyzer.runtime.cluster_review_state import write_cluster_review_state
    from novel_analyzer.services.cluster_review_service import (
        ClusterReviewService,
        ClusterReviewStorageUnavailable,
    )
    from apps.api.app.main import _review_contract, create_session_factory

    if not req.branch_id or not req.cluster_key or not req.cluster_status:
        return _wsgi_json_response(
            {"error": "branch_id, cluster_key and cluster_status are required"},
            status_code=400,
        )

    runtime = get_settings().model_copy(deep=True)
    if req.database_url:
        runtime.database_url = req.database_url

    review_payload = {
        "review_notes": req.review_notes,
        "review_owner": req.review_owner,
        "review_actor": req.review_actor,
        "resolved_at": req.resolved_at,
        "review_result": req.review_result,
    }

    try:
        factory = create_session_factory(runtime)
        with factory() as session:
            state = ClusterReviewService(session).write(
                branch_id=req.branch_id,
                cluster_key=req.cluster_key,
                cluster_status=req.cluster_status,
                **review_payload,
            )
            return _wsgi_json_response(
                {**_review_contract(), **asdict(state), "review_storage_mode": "db"}
            )
    except ValueError as exc:
        return _wsgi_json_response({"error": str(exc)}, status_code=400)
    except ClusterReviewStorageUnavailable:
        state = write_cluster_review_state(
            branch_id=req.branch_id,
            cluster_key=req.cluster_key,
            cluster_status=req.cluster_status,
            settings=runtime,
            **review_payload,
        )
        return _wsgi_json_response(
            {**_review_contract(), **asdict(state), "review_storage_mode": "file-fallback"}
        )
    except Exception as exc:  # noqa: BLE001
        if not ClusterReviewService._is_missing_relation_error(exc):
            return _wsgi_json_response({"error": str(exc)}, status_code=500)
        state = write_cluster_review_state(
            branch_id=req.branch_id,
            cluster_key=req.cluster_key,
            cluster_status=req.cluster_status,
            settings=runtime,
            **review_payload,
        )
        return _wsgi_json_response(
            {**_review_contract(), **asdict(state), "review_storage_mode": "file-fallback"}
        )


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


@router.get("/review-cluster-history")
def review_cluster_history(
    branch_id: str = Query(...),
    cluster_key: str = Query(...),
    database_url: str | None = Query(None),
    event_type: str = Query(""),
    review_owner: str = Query(""),
    review_result: str = Query(""),
    limit: int = Query(0),
):
    from fastapi.responses import JSONResponse
    from apps.api.app.main import get_settings
    from novel_analyzer.runtime.cluster_review_state import read_cluster_review_history
    from novel_analyzer.services.cluster_review_service import (
        ClusterReviewService,
        ClusterReviewStorageUnavailable,
    )
    from apps.api.app.main import (
        _apply_history_filters,
        _review_contract,
        create_session_factory,
    )

    runtime = get_settings().model_copy(deep=True)
    if database_url:
        runtime.database_url = database_url

    filters = {
        key: value
        for key, value in {
            "event_type": event_type,
            "review_owner": review_owner,
            "review_result": review_result,
        }.items()
        if value
    }

    def _build_payload(items_list, *, mode: str):
        return _wsgi_json_response({
            **_review_contract(),
            "review_storage_mode": mode,
            "filters": filters,
            "items": _apply_history_filters(
                items_list,
                event_type_filter=event_type,
                owner_filter=review_owner,
                result_filter=review_result,
                limit=limit,
            ),
        })

    try:
        factory = create_session_factory(runtime)
        with factory() as session:
            try:
                items = ClusterReviewService(session).read_history(branch_id, cluster_key)
                return _build_payload(items, mode="db")
            except ClusterReviewStorageUnavailable:
                items = read_cluster_review_history(branch_id, cluster_key, runtime)
                return _build_payload(items, mode="file-fallback")
    except Exception as exc:  # noqa: BLE001
        if not ClusterReviewService._is_missing_relation_error(exc):
            return _wsgi_json_response({"error": str(exc)}, status_code=500)
        items = read_cluster_review_history(branch_id, cluster_key, runtime)
        return _build_payload(items, mode="file-fallback")


@router.get("/review-batch-history")
def review_batch_history(
    branch_id: str = Query(...),
    database_url: str | None = Query(None),
    limit: int = Query(0),
):
    from apps.api.app.main import get_settings
    from novel_analyzer.runtime.review_batch_execution import read_batch_execution_history
    runtime = get_settings().model_copy(deep=True)
    if database_url:
        runtime.database_url = database_url
    items = read_batch_execution_history(branch_id, runtime)
    if limit > 0:
        items = items[-limit:]
    return {"branch_id": branch_id, "items": items}



@router.post("/review-batch-execute")
def review_batch_execute(body: dict = Body(...)):
    """Inlined v5.1: was delegating to main.py:application() during v5 T10
    soft-cutover. Now implemented directly here so WSGI dispatch can be
    fully retired.
    """
    from typing import cast
    from fastapi.responses import JSONResponse
    from apps.api.app.main import get_settings
    from apps.api.app.main import create_session_factory
    from novel_analyzer.runtime.review_batch_execution import write_batch_execution_entry
    from novel_analyzer.services.cluster_review_service import ClusterReviewService
    from novel_analyzer.services.export_service import ExportService
    from apps.api.app.main import (
        _BATCH_ACTION_CONFIG,
        _find_batch_suggestion,
        _review_contract,
    )

    run_id = str(body.get("run_id") or "")
    branch_id = str(body.get("branch_id") or "")
    action = str(body.get("action") or "")
    hint_code = str(body.get("hint_code") or "")
    group_strategy = str(body.get("group_strategy") or "")
    group_key = str(body.get("group_key") or "")
    cluster_keys = body.get("cluster_keys") or []
    if not run_id or not branch_id or not action or not hint_code or not group_strategy or not group_key:
        return JSONResponse(
            status_code=400,
            content={"error": "run_id, branch_id, action, hint_code, group_strategy and group_key are required"},
        )
    action_config = _BATCH_ACTION_CONFIG.get(action)
    if action_config is None:
        return JSONResponse(status_code=400, content={"error": "unsupported batch action"})
    if not isinstance(cluster_keys, list) or not all(isinstance(item, str) for item in cluster_keys):
        return JSONResponse(status_code=400, content={"error": "cluster_keys must be a list[str]"})

    dry_run = bool(body.get("dry_run"))
    runtime = get_settings().model_copy(deep=True)
    database_url = str(body.get("database_url") or "") or None
    if database_url:
        runtime.database_url = database_url
    review_owner = str(body.get("review_owner") or "")
    review_actor = str(body.get("review_actor") or "")
    review_notes = str(body.get("review_notes") or "")
    review_result = str(body.get("review_result") or "")
    resolved_at = str(body.get("resolved_at") or "")

    try:
        factory = create_session_factory(runtime)
        with factory() as session:
            bundle = ExportService(session).export_branch_bundle(run_id, branch_id)
            batch_suggestions = cast(
                list[dict[str, object]],
                bundle.get("review_summary", {}).get("batch_suggestions", []),
            )
            suggestion = _find_batch_suggestion(
                batch_suggestions,
                hint_code=hint_code,
                group_strategy=group_strategy,
                group_key=group_key,
            )
            if suggestion is None:
                return JSONResponse(status_code=404, content={"error": "batch suggestion not found"})

            allowed_hints = cast(set[str], action_config["allowed_hints"])
            if hint_code not in allowed_hints:
                return JSONResponse(
                    status_code=400,
                    content={"error": f"hint_code {hint_code} is not valid for action {action}"},
                )

            allowed_cluster_keys = {
                str(item) for item in cast(list[object], suggestion.get("cluster_keys", [])) if str(item)
            }
            target_cluster_keys = [
                cluster_key for cluster_key in cluster_keys if cluster_key in allowed_cluster_keys
            ]
            skipped_results: list[dict[str, str]] = [
                {"cluster_key": cluster_key, "reason": "not_in_batch_suggestion"}
                for cluster_key in cluster_keys
                if cluster_key not in allowed_cluster_keys
            ]
            if not target_cluster_keys:
                target_cluster_keys = sorted(allowed_cluster_keys)
            target_clusters = [
                item
                for item in cast(
                    list[dict[str, object]],
                    bundle.get("risk_summary", {}).get("review_candidate_clusters", []),
                )
                if str(item.get("cluster_key") or "") in target_cluster_keys
            ]
            target_cluster_map = {
                str(item.get("cluster_key") or ""): item for item in target_clusters
            }
            preview = [
                {
                    "cluster_key": str(item.get("cluster_key") or ""),
                    "cluster_title": str(item.get("cluster_title") or ""),
                    "workflow_lane": str(item.get("workflow_lane") or ""),
                    "queue_priority": str(item.get("queue_priority") or ""),
                    "close_ready_gate": bool(item.get("close_ready_gate")),
                }
                for item in target_clusters
            ]
            if action == "batch_close":
                invalid_targets = [
                    str(item.get("cluster_key") or "")
                    for item in target_clusters
                    if not bool(item.get("close_ready_gate"))
                ]
                if invalid_targets:
                    return JSONResponse(
                        status_code=400,
                        content={
                            "error": "batch_close requires close_ready_gate=true for every target",
                            "invalid_cluster_keys": invalid_targets,
                        },
                    )

            if dry_run:
                audit_entry = write_batch_execution_entry(
                    branch_id=branch_id,
                    action=action,
                    hint_code=hint_code,
                    group_strategy=group_strategy,
                    group_key=group_key,
                    dry_run=True,
                    target_count=len(target_cluster_keys),
                    success_count=0,
                    failed_count=0,
                    skipped_count=len(skipped_results),
                    preview=preview,
                    successes=[],
                    failed=[],
                    skipped=skipped_results,
                    settings=runtime,
                )
                return {
                    **_review_contract(),
                    "action": action,
                    "branch_id": branch_id,
                    "hint_code": hint_code,
                    "group_strategy": group_strategy,
                    "group_key": group_key,
                    "dry_run": True,
                    "target_count": len(target_cluster_keys),
                    "skipped_count": len(skipped_results),
                    "execution_id": audit_entry["execution_id"],
                    "preview": preview,
                    "skipped": skipped_results,
                }

            success_results: list[dict[str, str]] = []
            failed_results: list[dict[str, str]] = []
            target_cluster_status = cast(str, action_config["cluster_status"])
            preserve_existing_state = bool(action_config.get("preserve_existing_state"))
            for cluster_key in target_cluster_keys:
                try:
                    cluster_snapshot = target_cluster_map.get(cluster_key, {})
                    effective_cluster_status = target_cluster_status
                    effective_review_result = review_result or cast(
                        str, action_config["default_review_result"]
                    )
                    if preserve_existing_state and isinstance(cluster_snapshot, dict):
                        effective_cluster_status = str(
                            cluster_snapshot.get("cluster_status") or target_cluster_status
                        )
                        effective_review_result = str(
                            review_result
                            or cluster_snapshot.get("review_result")
                            or action_config["default_review_result"]
                        )
                    ClusterReviewService(session).write(
                        branch_id=branch_id,
                        cluster_key=cluster_key,
                        cluster_status=effective_cluster_status,
                        review_owner=review_owner,
                        review_actor=review_actor,
                        review_notes=review_notes,
                        review_result=effective_review_result,
                        resolved_at=resolved_at,
                    )
                    success_results.append(
                        {
                            "cluster_key": cluster_key,
                            "status": "ok",
                            "cluster_status": effective_cluster_status,
                            "review_result": effective_review_result,
                        }
                    )
                except Exception as exc:  # noqa: BLE001
                    session.rollback()
                    failed_results.append(
                        {"cluster_key": cluster_key, "status": "failed", "error": str(exc)}
                    )

            audit_entry = write_batch_execution_entry(
                branch_id=branch_id,
                action=action,
                hint_code=hint_code,
                group_strategy=group_strategy,
                group_key=group_key,
                dry_run=False,
                target_count=len(target_cluster_keys),
                success_count=len(success_results),
                failed_count=len(failed_results),
                skipped_count=len(skipped_results),
                preview=preview,
                successes=success_results,
                failed=failed_results,
                skipped=skipped_results,
                settings=runtime,
            )
            return {
                **_review_contract(),
                "action": action,
                "branch_id": branch_id,
                "hint_code": hint_code,
                "group_strategy": group_strategy,
                "group_key": group_key,
                "dry_run": False,
                "target_count": len(target_cluster_keys),
                "success_count": len(success_results),
                "failed_count": len(failed_results),
                "skipped_count": len(skipped_results),
                "execution_id": audit_entry["execution_id"],
                "preview": preview,
                "successes": success_results,
                "failed": failed_results,
                "skipped": skipped_results,
            }
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})
