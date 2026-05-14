"""Lightweight WSGI backend for the workbench prototype."""

from __future__ import annotations

import io
import json
import shutil
from dataclasses import asdict
from email.parser import BytesParser
from email.policy import default
from datetime import datetime
from pathlib import Path
from socketserver import ThreadingMixIn
from typing import Any, cast
from urllib.parse import parse_qs
from uuid import uuid4
from wsgiref.simple_server import WSGIServer, make_server
from wsgiref.types import StartResponse
from sqlalchemy import func, select

from novel_analyzer.application import (
    cancel_pipeline_run,
    export_branch_refs,
    get_branch_job_rows,
    get_branch_snapshot,
    get_pipeline_run_status,
    get_run_snapshot,
    ingest_and_start_pipeline,
    list_pipeline_runs,
    pause_pipeline_run,
    recover_branch,
    resume_pipeline_run,
    start_pipeline,
    start_pipeline_run_async,
)
from novel_analyzer.application.queries import _derive_pipeline_state, _setup_status
from novel_analyzer.config.settings import get_settings
from novel_analyzer.runtime.cluster_review_state import (
    ALLOWED_CLUSTER_STATUSES,
    ALLOWED_REVIEW_RESULTS,
    read_cluster_review_history,
    write_cluster_review_state,
)
from novel_analyzer.runtime.review_batch_execution import (
    read_batch_execution_history,
    write_batch_execution_entry,
)
from novel_analyzer.database.models import (
    AnalysisRun,
    ChapterArtifact,
    ChapterManifest,
    ChapterSegment,
    FactRecord,
    NovelSource,
    RunBranch,
)
from novel_analyzer.database.session import create_session_factory
from novel_analyzer.runtime.provider_health import read_provider_health
from novel_analyzer.runtime.storage import (
    describe_runtime_storage,
    migrate_legacy_runtime_dirs,
    runtime_cache_root,
)
from novel_analyzer.services.cluster_review_service import (
    ClusterReviewService,
    ClusterReviewStorageUnavailable,
)
from novel_analyzer.services.export_service import ExportService
from novel_analyzer.services.ingest_service import IngestService
from novel_analyzer.services.job_event_service import JobEventService
from novel_analyzer.services.qa_service import BranchQAService
from novel_analyzer.services.retrieval_service import RetrievalService
from novel_analyzer.services.status_service import StatusService
from novel_analyzer.services.whole_book_imitation_service import WholeBookImitationService


class ThreadingWSGIServer(ThreadingMixIn, WSGIServer):
    """Serve concurrent WSGI requests so long operations don't block the whole API."""

    daemon_threads = True


_RUNTIME_MIGRATED = False

def _quality_dashboard_payload(branch_id: str, database_url: str | None = None) -> dict[str, Any]:
    """Compute /api/quality-dashboard payload for a branch (T7 v5 helper)."""
    from novel_analyzer.services.foreshadowing_service import ForeshadowingService
    from novel_analyzer.database.models import ChapterArtifact as CA

    runtime = get_settings().model_copy(deep=True)
    if database_url:
        runtime.database_url = database_url
    factory = create_session_factory(runtime)
    with factory() as session:
        artifacts = session.scalars(
            select(CA)
            .where(CA.branch_id == branch_id)
            .where(CA.visibility == "active")
            .order_by(CA.chapter_index)
        ).all()
        facts_all = session.scalars(
            select(FactRecord)
            .where(FactRecord.branch_id == branch_id)
            .order_by(FactRecord.chapter_index)
        ).all()

        chapter_count = len(artifacts)
        total_facts = len(facts_all)
        avg_confidence = (
            sum(f.confidence for f in facts_all) / total_facts if total_facts else 0.0
        )
        low_confidence_count = sum(1 for f in facts_all if f.confidence < 0.4)

        fs = ForeshadowingService(session)
        open_threads = fs.get_open_threads(branch_id, before_chapter=9999, limit=50)

        chapter_summaries = []
        for art in artifacts[:50]:
            payload_data = art.payload_json or {}
            profile = payload_data.get("_deconstruction_profile", {})
            chapter_summaries.append({
                "chapter_index": art.chapter_index,
                "has_summary": bool(str(payload_data.get("chapter_summary", "")).strip()),
                "entity_count": len(payload_data.get("key_entities", [])),
                "event_count": len(payload_data.get("key_events", [])),
                "needs_human_review": payload_data.get("needs_human_review", False),
                "profile": profile.get("profile", "unknown"),
                "writer_lens_status": profile.get("writer_lens_status", "unknown"),
            })

        return {
            "branch_id": branch_id,
            "chapter_count": chapter_count,
            "total_facts": total_facts,
            "avg_confidence": round(avg_confidence, 3),
            "low_confidence_facts": low_confidence_count,
            "low_confidence_ratio": round(low_confidence_count / total_facts, 3) if total_facts else 0.0,
            "open_threads": [
                {
                    "thread_label": t.thread_label,
                    "chapter_planted": t.chapter_planted,
                    "reinforcements": t.reinforcement_count,
                }
                for t in open_threads
            ],
            "foreshadowing_open_count": len(open_threads),
            "chapters": chapter_summaries,
        }


_API_ENDPOINT_SPECS: list[dict[str, str]] = [
    {"method": "GET", "path": "/health"},
    {"method": "GET", "path": "/api/meta"},
    {"method": "GET", "path": "/api/mock/import"},
    {"method": "POST", "path": "/api/import"},
    {"method": "GET", "path": "/api/run-snapshot"},
    {"method": "GET", "path": "/api/branch-snapshot"},
    {"method": "GET", "path": "/api/chapter-bundle"},
    {"method": "GET", "path": "/api/chapter-qa-context"},
    {"method": "GET", "path": "/api/chapter-source"},
    {"method": "GET", "path": "/api/chapter-jobs"},
    {"method": "GET", "path": "/api/chapter-job-events"},
    {"method": "GET", "path": "/api/review-clusters"},
    {"method": "GET", "path": "/api/review-cluster-summary"},
    {"method": "GET", "path": "/api/review-cluster-history"},
    {"method": "POST", "path": "/api/review-cluster-update"},
    {"method": "POST", "path": "/api/review-batch-execute"},
    {"method": "GET", "path": "/api/review-batch-history"},
    {"method": "GET", "path": "/api/library"},
    {"method": "GET", "path": "/api/job-events"},
    {"method": "POST", "path": "/api/start"},
    {"method": "POST", "path": "/api/recovery"},
    {"method": "POST", "path": "/api/pipeline/start-range"},
    {"method": "GET", "path": "/api/pipeline/status"},
    {"method": "GET", "path": "/api/pipeline/runs"},
    {"method": "GET", "path": "/api/pipeline/progress-stream"},
    {"method": "GET", "path": "/api/runtime-health"},
    {"method": "GET", "path": "/api/provider-health"},
    {"method": "GET", "path": "/api/quality-dashboard"},
    {"method": "GET", "path": "/api/whole-book-imitation-readiness"},
    {"method": "POST", "path": "/api/whole-book-imitation-run"},
    {"method": "POST", "path": "/api/search-branch"},
    {"method": "POST", "path": "/api/ask-branch"},
    {"method": "POST", "path": "/api/ask-branch-stream"},
    {"method": "GET", "path": "/api/branch-exports"},
    {"method": "GET", "path": "/api/download"},
]


def _json_payload(value: Any) -> bytes:
    if hasattr(value, "__dataclass_fields__") and not isinstance(value, type):
        value = asdict(value)
    return json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8")


def _response(
    start_response: StartResponse,
    *,
    status: str,
    payload: Any,
) -> list[bytes]:
    body = _json_payload(payload)
    start_response(
        status,
        [
            ("Content-Type", "application/json; charset=utf-8"),
            ("Access-Control-Allow-Origin", "*"),
            ("Access-Control-Allow-Headers", "Content-Type"),
            ("Access-Control-Allow-Methods", "GET,POST,OPTIONS"),
            ("Content-Length", str(len(body))),
        ],
    )
    return [body]


def _stream_response(
    start_response: StartResponse,
    event_iterable: Any,
) -> Any:
    start_response(
        "200 OK",
        [
            ("Content-Type", "text/event-stream; charset=utf-8"),
            ("Cache-Control", "no-cache"),
            ("Access-Control-Allow-Origin", "*"),
            ("Access-Control-Allow-Headers", "Content-Type"),
            ("Access-Control-Allow-Methods", "GET,POST,OPTIONS"),
            ("X-Accel-Buffering", "no"),
        ],
    )
    return event_iterable


def _sse_event(payload: dict[str, Any]) -> bytes:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode()


def _query(environ: dict[str, Any]) -> dict[str, str]:
    raw = parse_qs(environ.get("QUERY_STRING", ""))
    return {key: values[-1] for key, values in raw.items() if values}


def _json_body(environ: dict[str, Any]) -> dict[str, Any]:
    length = int(environ.get("CONTENT_LENGTH") or "0")
    if length <= 0:
        return {}
    raw = environ["wsgi.input"].read(length)
    if not raw:
        return {}
    return cast(dict[str, Any], json.loads(raw.decode("utf-8")))


class _UploadedMultipartFile:
    def __init__(self, *, filename: str, file: io.BytesIO) -> None:
        self.filename = filename
        self.file = file


def _multipart_form(environ: dict[str, Any]) -> dict[str, Any]:
    length = int(environ.get("CONTENT_LENGTH") or "0")
    if length <= 0:
        return {}
    raw = environ["wsgi.input"].read(length)
    if not raw:
        return {}

    content_type = environ.get("CONTENT_TYPE", "")
    headers = f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("utf-8")
    message = BytesParser(policy=default).parsebytes(headers + raw)
    if not message.is_multipart():
        return {}

    payload: dict[str, Any] = {}
    for part in message.iter_parts():
        key = part.get_param("name", header="content-disposition")
        if not key:
            continue
        filename = part.get_filename()
        if filename:
            payload[key] = _UploadedMultipartFile(
                filename=filename,
                file=io.BytesIO(part.get_payload(decode=True) or b""),
            )
            continue
        payload[key] = part.get_content()
    return payload


def _body(environ: dict[str, Any]) -> dict[str, Any]:
    content_type = environ.get("CONTENT_TYPE", "")
    if content_type.startswith("application/json"):
        return _json_body(environ)
    if "multipart/form-data" in content_type:
        return _multipart_form(environ)
    if content_type.startswith("application/x-www-form-urlencoded"):
        length = int(environ.get("CONTENT_LENGTH") or "0")
        encoded = environ["wsgi.input"].read(length).decode("utf-8")
        return _query({"QUERY_STRING": encoded})
    return {}


def _require(params: dict[str, str], *keys: str) -> tuple[bool, str | None]:
    for key in keys:
        if not params.get(key):
            return False, key
    return True, None


def _review_filters(params: dict[str, str]) -> dict[str, str]:
    return {
        key: str(params.get(key) or "").strip()
        for key in (
            "cluster_status",
            "review_owner",
            "review_result",
            "review_priority",
            "pattern_label",
        )
        if str(params.get(key) or "").strip()
    }


def _review_contract() -> dict[str, object]:
    return {
        "contract_version": "review-workflow.v1",
        "stable_contract_version": "review-api-pre-v1",
        "allowed_cluster_statuses": sorted(ALLOWED_CLUSTER_STATUSES),
        "allowed_review_results": sorted(ALLOWED_REVIEW_RESULTS),
    }


def _whole_book_mapping_pack(body: dict[str, Any]) -> Any:
    from novel_analyzer.domain.schemas import StoryMappingPack

    return StoryMappingPack(
        project_title=str(body.get("project_title") or ""),
        source_work_name=str(body.get("source_work_name") or ""),
        target_work_name=str(body.get("target_work_name") or ""),
        world_mapping=cast(dict[str, str], body.get("world_mapping") or {}),
        character_mapping=cast(dict[str, str], body.get("character_mapping") or {}),
        faction_mapping=cast(dict[str, str], body.get("faction_mapping") or {}),
        power_mapping=cast(dict[str, str], body.get("power_mapping") or {}),
        rule_overrides=[str(item) for item in cast(list[Any], body.get("rule_overrides") or [])],
        forbidden_transformations=[
            str(item) for item in cast(list[Any], body.get("forbidden_transformations") or [])
        ],
    )


def _whole_book_chapter_goals(body: dict[str, Any]) -> list[tuple[int, str]]:
    raw_items = cast(list[dict[str, Any]], body.get("chapter_specs") or [])
    chapter_goals: list[tuple[int, str]] = []
    for item in raw_items:
        chapter_index = int(item.get("source_chapter_index") or 0)
        target_goal = str(item.get("target_goal") or "").strip()
        if chapter_index <= 0 or not target_goal:
            raise ValueError("chapter_specs must contain positive source_chapter_index and non-empty target_goal")
        chapter_goals.append((chapter_index, target_goal))
    return chapter_goals


def _whole_book_readiness_payload(
    branch_id: str | None,
    database_url: str | None,
) -> dict[str, object]:
    runtime = get_settings().model_copy(deep=True)
    if database_url:
        runtime.database_url = database_url
    factory = create_session_factory(runtime)
    with factory() as session:
        target_branch_id = branch_id or session.scalar(
            select(ChapterArtifact.branch_id)
            .where(ChapterArtifact.artifact_type == "chapter_analysis")
            .group_by(ChapterArtifact.branch_id)
            .order_by(func.count(ChapterArtifact.id).desc())
            .limit(1)
        )

        branch_summary: dict[str, object] = {
            "branch_id": target_branch_id or "",
            "exists": False,
            "chapter_analysis_count": 0,
            "fact_record_count": 0,
            "chapter_span": {"min": None, "max": None},
            "run_id": "",
            "branch_name": "",
            "status": "",
            "novel_title": "",
        }
        if target_branch_id:
            branch = session.get(RunBranch, target_branch_id)
            if branch is not None:
                analysis_count = session.scalar(
                    select(func.count())
                    .select_from(ChapterArtifact)
                    .where(
                        ChapterArtifact.branch_id == target_branch_id,
                        ChapterArtifact.artifact_type == "chapter_analysis",
                    )
                ) or 0
                fact_count = session.scalar(
                    select(func.count())
                    .select_from(FactRecord)
                    .where(FactRecord.branch_id == target_branch_id)
                ) or 0
                chapter_min, chapter_max = session.execute(
                    select(
                        func.min(ChapterArtifact.chapter_index),
                        func.max(ChapterArtifact.chapter_index),
                    ).where(
                        ChapterArtifact.branch_id == target_branch_id,
                        ChapterArtifact.artifact_type == "chapter_analysis",
                    )
                ).one()
                novel_title = session.scalar(
                    select(NovelSource.title)
                    .join(AnalysisRun, AnalysisRun.novel_id == NovelSource.id)
                    .where(AnalysisRun.id == branch.run_id)
                ) or ""
                branch_summary = {
                    "branch_id": target_branch_id,
                    "exists": True,
                    "chapter_analysis_count": int(analysis_count),
                    "fact_record_count": int(fact_count),
                    "chapter_span": {"min": chapter_min, "max": chapter_max},
                    "run_id": branch.run_id,
                    "branch_name": branch.name,
                    "status": branch.status,
                    "novel_title": novel_title,
                }

    provider_health = read_provider_health(runtime)
    return {
        "contract_version": "whole-book-imitation-readiness.v1",
        "stable_contract_version": "whole-book-imitation-readiness-pre-v1",
        "whole_book_contract_version": "whole-book-imitation.v1",
        "whole_book_stable_contract_version": "whole-book-imitation-pre-v1",
        "database": {
            "masked_database_url": runtime.masked_database_url,
            "effective_db_name": runtime.effective_db_name,
        },
        "provider": {
            "provider_name": runtime.llm_provider_name,
            "base_url": runtime.resolved_llm_base_url,
            "api_key_present": bool(runtime.resolved_llm_api_key),
            "model_name": runtime.llm_model_name,
            "stage_model_name": runtime.llm_stage_model_name,
            "qa_model_name": runtime.llm_qa_model_name,
            "provider_health": asdict(provider_health),
        },
        "branch_candidate": branch_summary,
        "readiness_notes": [
            "如果 api_key_present=false，则不能做真实 provider-backed whole-book execute。",
            "如果 provider_health.last_status=degraded，应先确认上游 provider 是否恢复。",
            "如果 branch_candidate.chapter_analysis_count < 2，则不适合做 whole-book imitation freeze evidence。",
        ],
    }


def _whole_book_run_error_payload(exc: Exception) -> tuple[str, dict[str, object]]:
    message = str(exc)
    lowered = message.lower()
    payload: dict[str, object] = {
        "error": message,
        "error_type": type(exc).__name__,
        "retryable": False,
        "upstream_status": None,
        "error_code": "whole_book_run_failed",
    }
    status = "500 Internal Server Error"
    if "daily usage limit exceeded" in lowered or "billing_error" in lowered:
        payload["error_code"] = "provider_billing_limited"
        payload["retryable"] = False
        payload["upstream_status"] = 403
        status = "503 Service Unavailable"
    elif "bad gateway" in lowered or "502" in lowered:
        payload["error_code"] = "provider_bad_gateway"
        payload["retryable"] = True
        payload["upstream_status"] = 502
        status = "503 Service Unavailable"
    elif "timed out" in lowered or "timeout" in lowered:
        payload["error_code"] = "provider_timeout"
        payload["retryable"] = True
        status = "503 Service Unavailable"
    return status, payload


def _apply_review_filters(
    items: list[dict[str, object]],
    filters: dict[str, str],
) -> list[dict[str, object]]:
    if not filters:
        return items
    return [
        item
        for item in items
        if all(str(item.get(key) or "") == value for key, value in filters.items())
    ]


def _review_summary_payload(
    *,
    items: list[dict[str, object]],
    review_storage_mode: object,
    filters: dict[str, str],
) -> dict[str, object]:
    batch_suggestions: dict[str, list[dict[str, object]]] = {}
    by_status: dict[str, int] = {}
    by_result: dict[str, int] = {}
    by_owner: dict[str, int] = {}
    by_actor: dict[str, int] = {}
    by_latest_event_type: dict[str, int] = {}
    by_workflow_lane: dict[str, int] = {}
    by_queue_priority: dict[str, int] = {}
    by_deadline_level: dict[str, int] = {}
    by_batch_operation_hint: dict[str, int] = {}
    by_escalation_tier: dict[str, int] = {}
    by_auto_next_action_code: dict[str, int] = {}
    by_auto_next_action: dict[str, int] = {}
    by_escalation_reason_code: dict[str, int] = {}
    by_escalation_reason: dict[str, int] = {}
    by_priority: dict[str, int] = {}
    by_pattern: dict[str, int] = {}
    pending_assignment_count = 0
    pending_escalation_count = 0
    resolved_count = 0
    needs_review_count = 0
    action_required_count = 0
    close_ready_count = 0
    for item in items:
        status_key = str(item.get("cluster_status") or "")
        result_key = str(item.get("review_result") or "")
        owner_key = str(item.get("review_owner") or "")
        actor_key = str(item.get("latest_review_event", {}).get("review_actor") or "")
        event_type_key = str(item.get("latest_review_event", {}).get("event_type") or "")
        workflow_lane_key = str(item.get("workflow_lane") or "")
        queue_priority_key = str(item.get("queue_priority") or "")
        deadline_level_key = str(item.get("suggested_deadline_level") or "")
        batch_operation_hint_key = str(item.get("batch_operation_hint") or "")
        escalation_tier_key = str(item.get("escalation_tier") or "")
        action_required_value = bool(item.get("action_required"))
        close_ready_value = bool(item.get("close_ready_gate"))
        auto_next_action_code_key = str(item.get("auto_next_action_code") or "")
        auto_next_action_key = str(item.get("auto_next_action") or "")
        escalation_reason_code_key = str(item.get("escalation_reason_code") or "")
        escalation_reason_key = str(item.get("escalation_reason") or "")
        priority_key = str(item.get("review_priority") or "")
        pattern_key = str(item.get("pattern_label") or "")
        if status_key:
            by_status[status_key] = by_status.get(status_key, 0) + 1
            if status_key == "resolved":
                resolved_count += 1
            if status_key == "needs_review":
                needs_review_count += 1
        if result_key:
            by_result[result_key] = by_result.get(result_key, 0) + 1
            if result_key == "needs-escalation":
                pending_escalation_count += 1
        if owner_key:
            by_owner[owner_key] = by_owner.get(owner_key, 0) + 1
        if actor_key:
            by_actor[actor_key] = by_actor.get(actor_key, 0) + 1
        if event_type_key:
            by_latest_event_type[event_type_key] = by_latest_event_type.get(event_type_key, 0) + 1
            if event_type_key == "assignment_update" and status_key != "resolved":
                pending_assignment_count += 1
        if workflow_lane_key:
            by_workflow_lane[workflow_lane_key] = by_workflow_lane.get(workflow_lane_key, 0) + 1
        if queue_priority_key:
            by_queue_priority[queue_priority_key] = by_queue_priority.get(queue_priority_key, 0) + 1
        if deadline_level_key:
            by_deadline_level[deadline_level_key] = by_deadline_level.get(deadline_level_key, 0) + 1
        if batch_operation_hint_key:
            by_batch_operation_hint[batch_operation_hint_key] = (
                by_batch_operation_hint.get(batch_operation_hint_key, 0) + 1
            )
        if escalation_tier_key:
            by_escalation_tier[escalation_tier_key] = (
                by_escalation_tier.get(escalation_tier_key, 0) + 1
            )
        if action_required_value:
            action_required_count += 1
        if close_ready_value:
            close_ready_count += 1
        if auto_next_action_code_key:
            by_auto_next_action_code[auto_next_action_code_key] = (
                by_auto_next_action_code.get(auto_next_action_code_key, 0) + 1
            )
        if auto_next_action_key:
            by_auto_next_action[auto_next_action_key] = (
                by_auto_next_action.get(auto_next_action_key, 0) + 1
            )
        if escalation_reason_code_key:
            by_escalation_reason_code[escalation_reason_code_key] = (
                by_escalation_reason_code.get(escalation_reason_code_key, 0) + 1
            )
        if escalation_reason_key:
            by_escalation_reason[escalation_reason_key] = (
                by_escalation_reason.get(escalation_reason_key, 0) + 1
            )
        if priority_key:
            by_priority[priority_key] = by_priority.get(priority_key, 0) + 1
        if pattern_key:
            by_pattern[pattern_key] = by_pattern.get(pattern_key, 0) + 1
        batch_hint = str(item.get("batch_operation_hint") or "")
        if batch_hint:
            batch_suggestions.setdefault(batch_hint, []).append(item)
    latest_review_at = max(
        [
            str(item.get("latest_review_event", {}).get("created_at") or "")
            for item in items
            if isinstance(item.get("latest_review_event"), dict)
            and str(item.get("latest_review_event", {}).get("created_at") or "")
        ]
        or [""]
    )
    latest_review_owner = next(
        (
            str(item.get("latest_review_event", {}).get("review_owner") or "")
            for item in items
            if isinstance(item.get("latest_review_event"), dict)
            and str(item.get("latest_review_event", {}).get("created_at") or "") == latest_review_at
        ),
        "",
    )
    latest_review_result = next(
        (
            str(item.get("latest_review_event", {}).get("review_result") or "")
            for item in items
            if isinstance(item.get("latest_review_event"), dict)
            and str(item.get("latest_review_event", {}).get("created_at") or "") == latest_review_at
        ),
        "",
    )
    latest_review_actor = next(
        (
            str(item.get("latest_review_event", {}).get("review_actor") or "")
            for item in items
            if isinstance(item.get("latest_review_event"), dict)
            and str(item.get("latest_review_event", {}).get("created_at") or "") == latest_review_at
        ),
        "",
    )
    latest_review_event_type = next(
        (
            str(item.get("latest_review_event", {}).get("event_type") or "")
            for item in items
            if isinstance(item.get("latest_review_event"), dict)
            and str(item.get("latest_review_event", {}).get("created_at") or "") == latest_review_at
        ),
        "",
    )
    current_owner_top = (
        sorted(by_owner.items(), key=lambda item: (-item[1], item[0]))[0][0] if by_owner else ""
    )
    current_owner_top_count = by_owner.get(current_owner_top, 0) if current_owner_top else 0
    latest_actor_top = (
        sorted(by_actor.items(), key=lambda item: (-item[1], item[0]))[0][0] if by_actor else ""
    )
    latest_actor_top_count = by_actor.get(latest_actor_top, 0) if latest_actor_top else 0
    latest_event_type_top = (
        sorted(by_latest_event_type.items(), key=lambda item: (-item[1], item[0]))[0][0]
        if by_latest_event_type
        else ""
    )
    latest_event_type_top_count = (
        by_latest_event_type.get(latest_event_type_top, 0) if latest_event_type_top else 0
    )
    workflow_lane_top = (
        sorted(by_workflow_lane.items(), key=lambda item: (-item[1], item[0]))[0][0]
        if by_workflow_lane
        else ""
    )
    workflow_lane_top_count = by_workflow_lane.get(workflow_lane_top, 0) if workflow_lane_top else 0
    queue_priority_top = (
        sorted(by_queue_priority.items(), key=lambda item: (-item[1], item[0]))[0][0]
        if by_queue_priority
        else ""
    )
    queue_priority_top_count = by_queue_priority.get(queue_priority_top, 0) if queue_priority_top else 0
    deadline_level_top = (
        sorted(by_deadline_level.items(), key=lambda item: (-item[1], item[0]))[0][0]
        if by_deadline_level
        else ""
    )
    deadline_level_top_count = by_deadline_level.get(deadline_level_top, 0) if deadline_level_top else 0
    batch_operation_hint_top = (
        sorted(by_batch_operation_hint.items(), key=lambda item: (-item[1], item[0]))[0][0]
        if by_batch_operation_hint
        else ""
    )
    batch_operation_hint_top_count = (
        by_batch_operation_hint.get(batch_operation_hint_top, 0) if batch_operation_hint_top else 0
    )
    escalation_tier_top = (
        sorted(by_escalation_tier.items(), key=lambda item: (-item[1], item[0]))[0][0]
        if by_escalation_tier
        else ""
    )
    escalation_tier_top_count = (
        by_escalation_tier.get(escalation_tier_top, 0) if escalation_tier_top else 0
    )
    auto_next_action_top = (
        sorted(by_auto_next_action.items(), key=lambda item: (-item[1], item[0]))[0][0]
        if by_auto_next_action
        else ""
    )
    auto_next_action_top_count = (
        by_auto_next_action.get(auto_next_action_top, 0) if auto_next_action_top else 0
    )
    auto_next_action_code_top = (
        sorted(by_auto_next_action_code.items(), key=lambda item: (-item[1], item[0]))[0][0]
        if by_auto_next_action_code
        else ""
    )
    auto_next_action_code_top_count = (
        by_auto_next_action_code.get(auto_next_action_code_top, 0)
        if auto_next_action_code_top
        else 0
    )
    escalation_reason_top = (
        sorted(by_escalation_reason.items(), key=lambda item: (-item[1], item[0]))[0][0]
        if by_escalation_reason
        else ""
    )
    escalation_reason_top_count = (
        by_escalation_reason.get(escalation_reason_top, 0) if escalation_reason_top else 0
    )
    escalation_reason_code_top = (
        sorted(by_escalation_reason_code.items(), key=lambda item: (-item[1], item[0]))[0][0]
        if by_escalation_reason_code
        else ""
    )
    escalation_reason_code_top_count = (
        by_escalation_reason_code.get(escalation_reason_code_top, 0)
        if escalation_reason_code_top
        else 0
    )
    batch_suggestion_items: list[dict[str, object]] = []
    title_map = {
        "batch_escalate_candidates": "可批量升级处理",
        "batch_owner_handoff_followup": "可批量催办交接",
        "batch_human_review_queue": "可批量人工复核",
        "batch_archive_candidates": "可批量归档关闭",
        "batch_monitoring_watchlist": "可批量观察跟踪",
    }
    for hint, grouped_items in batch_suggestions.items():
        if not grouped_items:
            continue
        sample = grouped_items[0]
        action_bucket_map = {
            "batch_escalate_candidates": "escalate",
            "batch_owner_handoff_followup": "followup",
            "batch_human_review_queue": "review",
            "batch_archive_candidates": "archive",
            "batch_monitoring_watchlist": "monitor",
        }
        batch_priority_map = {
            "batch_escalate_candidates": "urgent",
            "batch_owner_handoff_followup": "high",
            "batch_human_review_queue": "medium",
            "batch_archive_candidates": "low",
            "batch_monitoring_watchlist": "low",
        }
        group_strategy = (
            "by_owner"
            if hint in {"batch_owner_handoff_followup", "batch_archive_candidates"}
            else "by_checker"
        )
        group_key = (
            str(sample.get("review_owner") or "").strip() or "unassigned"
            if group_strategy == "by_owner"
            else str(sample.get("checker_names", ["unknown"])[0] if sample.get("checker_names") else "unknown")
        )
        batch_suggestion_items.append(
            {
                "hint_code": hint,
                "hint_title": title_map.get(hint, hint),
                "action_bucket": action_bucket_map.get(hint, "monitor"),
                "batch_priority": batch_priority_map.get(hint, "low"),
                "group_strategy": group_strategy,
                "group_key": group_key,
                "cluster_count": len(grouped_items),
                "cluster_keys": [str(item.get("cluster_key") or "") for item in grouped_items[:5]],
                "suggested_cluster_order": [
                    str(item.get("cluster_key") or "") for item in grouped_items[:5]
                ],
                "suggested_cluster_order_titles": [
                    str(item.get("cluster_title") or "") for item in grouped_items[:5]
                ],
                "suggested_cluster_order_details": [
                    {
                        "cluster_key": str(item.get("cluster_key") or ""),
                        "cluster_title": str(item.get("cluster_title") or ""),
                        "queue_priority": str(item.get("queue_priority") or ""),
                        "review_priority": str(item.get("review_priority") or ""),
                        "chapter_count": int(item.get("chapter_count", 0) or 0),
                        "confidence": float(item.get("max_confidence", 0.0) or 0.0),
                        "chapter_span_width": max(
                            int(item.get("last_chapter", item.get("first_chapter", 0)) or 0)
                            - int(item.get("first_chapter", 0) or 0),
                            0,
                        ),
                        "batch_rank_score": (
                            {
                                "urgent": 500.0,
                                "high": 400.0,
                                "medium": 300.0,
                                "low": 200.0,
                                "done": 100.0,
                            }.get(str(item.get("queue_priority") or ""), 0.0)
                            + {
                                "P1": 30.0,
                                "P2": 20.0,
                                "P3": 10.0,
                            }.get(str(item.get("review_priority") or ""), 0.0)
                            + min(float(int(item.get("chapter_count", 0) or 0)), 10.0) * 2.0
                            + float(item.get("max_confidence", 0.0) or 0.0) * 10.0
                            + min(
                                float(
                                    max(
                                        int(item.get("last_chapter", item.get("first_chapter", 0)) or 0)
                                        - int(item.get("first_chapter", 0) or 0),
                                        0,
                                    )
                                ),
                                10.0,
                            )
                        ),
                        "order_reason": (
                            f"queue={item.get('queue_priority')} | priority={item.get('review_priority')} | "
                            f"chapter_count={item.get('chapter_count')} | confidence={item.get('max_confidence')} | "
                            f"span_width={max(int(item.get('last_chapter', item.get('first_chapter', 0)) or 0) - int(item.get('first_chapter', 0) or 0), 0)}"
                        ),
                    }
                    for item in grouped_items[:5]
                ],
                "ordering_strategy": "queue_priority -> review_priority -> chapter_count -> confidence -> chapter_span_width -> first_chapter",
                "suggested_first_cluster_reason": (
                    f"queue={sample.get('queue_priority')} | priority={sample.get('review_priority')} | "
                    f"chapter_count={sample.get('chapter_count')} | confidence={sample.get('max_confidence')} | "
                    f"span_width={max(int(sample.get('last_chapter', sample.get('first_chapter', 0)) or 0) - int(sample.get('first_chapter', 0) or 0), 0)}"
                ),
                "cluster_titles": [str(item.get("cluster_title") or "") for item in grouped_items[:3]],
                "owners": [
                    str(item.get("review_owner") or "")
                    for item in grouped_items
                    if str(item.get("review_owner") or "")
                ][:3],
                "suggested_owner": next(
                    (
                        str(item.get("review_owner") or "")
                        for item in grouped_items
                        if str(item.get("review_owner") or "")
                    ),
                    "",
                ),
                "primary_checker": str(
                    sample.get("checker_names", [""])[0] if sample.get("checker_names") else ""
                ),
                "risk_types": [
                    str(value)
                    for value in dict.fromkeys(
                        value
                        for item in grouped_items
                        for value in (item.get("risk_types") or [])
                        if str(value).strip()
                    )
                ][:4],
                "chapter_spans": [
                    str(value)
                    for value in dict.fromkeys(
                        item.get("chapter_span")
                        for item in grouped_items
                        if str(item.get("chapter_span") or "").strip()
                    )
                ][:3],
                "queue_priority_top": str(sample.get("queue_priority") or ""),
                "deadline_level_top": str(sample.get("suggested_deadline_level") or ""),
                "action_required": any(bool(item.get("action_required")) for item in grouped_items),
                "resolved_candidate_count": sum(
                    1 for item in grouped_items if str(item.get("cluster_status") or "") == "resolved"
                ),
                "escalation_candidate_count": sum(
                    1
                    for item in grouped_items
                    if str(item.get("review_result") or "") == "needs-escalation"
                ),
                "recommended_batch_action": str(sample.get("auto_next_action") or ""),
            }
        )
    batch_suggestion_items.sort(
        key=lambda item: (
            {
                "batch_escalate_candidates": 0,
                "batch_owner_handoff_followup": 1,
                "batch_human_review_queue": 2,
                "batch_archive_candidates": 3,
                "batch_monitoring_watchlist": 4,
            }.get(str(item.get("hint_code") or ""), 5),
            -int(item.get("cluster_count", 0) or 0),
        )
    )
    return {
        "review_storage_mode": review_storage_mode,
        "cluster_count": len(items),
        "filters": filters,
        "by_status": by_status,
        "by_result": by_result,
        "by_owner": by_owner,
        "by_actor": by_actor,
        "by_latest_event_type": by_latest_event_type,
        "by_workflow_lane": by_workflow_lane,
        "by_queue_priority": by_queue_priority,
        "by_deadline_level": by_deadline_level,
        "by_batch_operation_hint": by_batch_operation_hint,
        "by_escalation_tier": by_escalation_tier,
        "by_auto_next_action_code": by_auto_next_action_code,
        "by_auto_next_action": by_auto_next_action,
        "by_escalation_reason_code": by_escalation_reason_code,
        "by_escalation_reason": by_escalation_reason,
        "by_priority": by_priority,
        "by_pattern": by_pattern,
        "history_event_count": sum(int(item.get("review_history_count", 0) or 0) for item in items),
        "latest_review_at": latest_review_at,
        "latest_review_owner": latest_review_owner,
        "latest_review_actor": latest_review_actor,
        "latest_review_event_type": latest_review_event_type,
        "latest_review_result": latest_review_result,
        "latest_review_result_label": ExportService._review_result_label(latest_review_result),
        "current_owner_top": current_owner_top,
        "current_owner_top_count": current_owner_top_count,
        "latest_actor_top": latest_actor_top,
        "latest_actor_top_count": latest_actor_top_count,
        "latest_event_type_top": latest_event_type_top,
        "latest_event_type_top_count": latest_event_type_top_count,
        "workflow_lane_top": workflow_lane_top,
        "workflow_lane_top_count": workflow_lane_top_count,
        "queue_priority_top": queue_priority_top,
        "queue_priority_top_count": queue_priority_top_count,
        "deadline_level_top": deadline_level_top,
        "deadline_level_top_count": deadline_level_top_count,
        "batch_operation_hint_top": batch_operation_hint_top,
        "batch_operation_hint_top_count": batch_operation_hint_top_count,
        "escalation_tier_top": escalation_tier_top,
        "escalation_tier_top_count": escalation_tier_top_count,
        "auto_next_action_code_top": auto_next_action_code_top,
        "auto_next_action_code_top_count": auto_next_action_code_top_count,
        "auto_next_action_top": auto_next_action_top,
        "auto_next_action_top_count": auto_next_action_top_count,
        "escalation_reason_code_top": escalation_reason_code_top,
        "escalation_reason_code_top_count": escalation_reason_code_top_count,
        "escalation_reason_top": escalation_reason_top,
        "escalation_reason_top_count": escalation_reason_top_count,
        "pending_assignment_count": pending_assignment_count,
        "pending_escalation_count": pending_escalation_count,
        "resolved_count": resolved_count,
        "needs_review_count": needs_review_count,
        "action_required_count": action_required_count,
        "close_ready_count": close_ready_count,
        "batch_suggestions": batch_suggestion_items,
    }


def _apply_history_filters(
    items: list[dict[str, object]],
    *,
    event_type_filter: str,
    owner_filter: str,
    result_filter: str,
    limit: int,
) -> list[dict[str, object]]:
    filtered = items
    if event_type_filter:
        filtered = [
            item for item in filtered if str(item.get("event_type") or "") == event_type_filter
        ]
    if owner_filter:
        filtered = [
            item for item in filtered if str(item.get("review_owner") or "") == owner_filter
        ]
    if result_filter:
        filtered = [
            item for item in filtered if str(item.get("review_result") or "") == result_filter
        ]
    if limit > 0:
        filtered = filtered[-limit:]
    return filtered


def _find_batch_suggestion(
    batch_suggestions: list[dict[str, object]],
    *,
    hint_code: str,
    group_strategy: str,
    group_key: str,
) -> dict[str, object] | None:
    for item in batch_suggestions:
        if (
            str(item.get("hint_code") or "") == hint_code
            and str(item.get("group_strategy") or "") == group_strategy
            and str(item.get("group_key") or "") == group_key
        ):
            return item
    return None


_BATCH_ACTION_CONFIG: dict[str, dict[str, object]] = {
    "batch_review_assign": {
        "allowed_hints": {"batch_human_review_queue", "batch_owner_handoff_followup"},
        "cluster_status": "reviewed",
        "default_review_result": "deferred",
    },
    "batch_escalate": {
        "allowed_hints": {"batch_escalate_candidates"},
        "cluster_status": "escalated",
        "default_review_result": "needs-escalation",
    },
    "batch_close": {
        "allowed_hints": {"batch_close_ready_candidates"},
        "cluster_status": "resolved",
        "default_review_result": "confirmed-benign",
    },
    "batch_archive": {
        "allowed_hints": {"batch_archive_candidates"},
        "cluster_status": "resolved",
        "default_review_result": "",
        "preserve_existing_state": True,
    },
}


def _mock_import(profile: str) -> dict[str, Any]:
    pipeline_state = "ready" if profile == "manual" else "auto_running"
    return {
        "novel_id": "novel-001",
        "manifest_id": "manifest-001",
        "run_id": "run-001",
        "branch_id": "branch-001",
        "pipeline_profile": profile,
        "pipeline_state": pipeline_state,
        "existing": False,
    }


def _mock_run_snapshot(profile: str) -> dict[str, Any]:
    return {
        "run_id": "run-001",
        "branch_id": "branch-001",
        "branch_name": "main",
        "pipeline_state": "ready" if profile == "manual" else "auto_running",
        "manifest_chapter_count": 120,
        "completed_chapters": 0 if profile == "manual" else 3,
        "failed_jobs": 0,
        "running_jobs": 0 if profile == "manual" else 1,
        "next_chapter": 1 if profile == "manual" else 4,
        "allowed_actions": ["start", "refresh"] if profile == "manual" else ["refresh"],
        "setup_status": "ok",
    }


def _mock_branch_snapshot(profile: str) -> dict[str, Any]:
    return {
        "branch_id": "branch-001",
        "pipeline_state": "ready" if profile == "manual" else "auto_running",
        "allowed_actions": ["start", "refresh", "export-basic"]
        if profile == "manual"
        else ["refresh"],
        "chapter_rows": [
            {
                "chapter_index": 1,
                "title": "第1章",
                "job_status": "validated",
                "has_artifact": True,
                "has_retrieval": True,
                "hook_score": 0.82,
                "needs_human_review": False,
                "summary": "样例章节摘要",
                "risk_level": "medium",
                "risk_count": 2,
            }
        ],
        "failed_summary": [],
        "risk_summary": {
            "risk_card_count": 1,
            "checker_result_count": 2,
            "high_risk_chapters": [],
            "risk_counts_by_domain": {"character": 1, "rules": 1},
            "risk_counts_by_severity": {"medium": 2},
        },
    }


def _runtime_cache_root() -> Path:
    return runtime_cache_root(get_settings())


def _migrate_legacy_runtime_dirs() -> None:
    global _RUNTIME_MIGRATED
    if _RUNTIME_MIGRATED:
        return

    migrate_legacy_runtime_dirs(get_settings())
    _RUNTIME_MIGRATED = True


def _stable_export_dir(run_id: str, branch_id: str) -> str:
    _migrate_legacy_runtime_dirs()
    base = (
        _runtime_cache_root()
        / "runtime-exports"
        / run_id
        / branch_id
        / datetime.now().strftime("%Y%m%dT%H%M%S")
    )
    base.mkdir(parents=True, exist_ok=True)
    return str(base)


def _persist_uploaded_text(file_item: Any) -> str:
    _migrate_legacy_runtime_dirs()
    filename = Path(getattr(file_item, "filename", "upload.txt")).name or "upload.txt"
    target_dir = _runtime_cache_root() / "uploads"
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / f"{uuid4().hex}-{filename}"

    with target_path.open("wb") as handle:
        shutil.copyfileobj(file_item.file, handle)

    return str(target_path.resolve())


def _resolve_source_path(path_value: str) -> Path:
    _migrate_legacy_runtime_dirs()
    path = Path(path_value)
    if path.exists():
        return path

    legacy_marker = ".omx/uploads"
    if legacy_marker in path_value:
        migrated = _runtime_cache_root() / "uploads" / path.name
        if migrated.exists():
            return migrated
        legacy_path = get_settings().legacy_runtime_dir / "uploads" / path.name
        if legacy_path.exists():
            return legacy_path

    raise FileNotFoundError(f"No such file or directory: '{path_value}'")


def _export_query_runtime(params: dict[str, str]) -> Any:
    runtime = get_settings().model_copy(deep=True)
    if params.get("database_url"):
        runtime.database_url = params["database_url"]
    return runtime


def _chapter_source_payload(
    *,
    branch_id: str,
    chapter_index: int,
    database_url: str | None,
) -> dict[str, Any]:
    runtime = get_settings().model_copy(deep=True)
    if database_url:
        runtime.database_url = database_url
    factory = create_session_factory(runtime)
    with factory() as session:
        branch = session.get(RunBranch, branch_id)
        if branch is None:
            raise ValueError("branch not found")
        manifest = session.get(ChapterManifest, branch.run.manifest_id)
        if manifest is None:
            raise ValueError("manifest not found")
        segment = session.scalar(
            session.query(ChapterSegment)
            .filter(ChapterSegment.manifest_id == manifest.id)
            .filter(ChapterSegment.chapter_index == chapter_index)
            .statement
        )
        if segment is None:
            raise ValueError("chapter segment not found")
        novel = session.get(NovelSource, manifest.novel_id)
        if novel is None:
            raise ValueError("novel source not found")
        text = _resolve_source_path(novel.source_path).read_text(encoding="utf-8")
        content = text[segment.start_offset : segment.end_offset].strip()
        return {
            "chapter_index": chapter_index,
            "raw_heading": segment.raw_heading,
            "normalized_title": segment.normalized_title,
            "start_offset": segment.start_offset,
            "end_offset": segment.end_offset,
            "source_excerpt": content,
        }


def _library_payload(database_url: str | None, limit: int, owner_user_id: str | None = None) -> dict[str, Any]:
    runtime = get_settings().model_copy(deep=True)
    if database_url:
        runtime.database_url = database_url
    factory = create_session_factory(runtime)
    rows: list[dict[str, Any]] = []
    with factory() as session:
        query = session.query(RunBranch)
        if owner_user_id is not None:
            query = query.filter(RunBranch.owner_user_id == owner_user_id)
        branches = session.scalars(
            query.order_by(RunBranch.updated_at.desc()).limit(limit).statement
        ).all()
        for branch in branches:
            run = session.get(AnalysisRun, branch.run_id)
            if run is None:
                continue
            novel = session.get(NovelSource, run.novel_id)
            manifest = session.get(ChapterManifest, run.manifest_id)
            if novel is None or manifest is None:
                continue
            status = StatusService(session).get_run_status(run.id, branch.id)
            rows.append(
                {
                    "novel_id": novel.id,
                    "title": novel.title,
                    "run_id": run.id,
                    "branch_id": branch.id,
                    "branch_name": branch.name,
                    "pipeline_state": _derive_pipeline_state(
                        session, run.id, branch.id, status.next_chapter
                    ),
                    "completed_chapters": status.completed_chapters,
                    "manifest_chapter_count": status.manifest_chapter_count,
                    "next_chapter": status.next_chapter,
                    "failed_jobs": status.failed_jobs,
                    "running_jobs": status.running_jobs,
                    "setup_status": _setup_status(session, run.id),
                    "updated_at": branch.updated_at.isoformat() if branch.updated_at else None,
                }
            )
    return {"items": rows}


def _job_events_payload(branch_id: str, database_url: str | None, limit: int) -> dict[str, Any]:
    runtime = get_settings().model_copy(deep=True)
    if database_url:
        runtime.database_url = database_url
    factory = create_session_factory(runtime)
    with factory() as session:
        rows = JobEventService(session).list_for_branch(branch_id, limit)
    return {
        "items": [
            {
                "id": row.id,
                "run_id": row.run_id,
                "branch_id": row.branch_id,
                "chapter_index": row.chapter_index,
                "event_type": row.event_type,
                "stage": row.stage,
                "level": row.level,
                "message": row.message,
                "payload_json": row.payload_json,
                "created_at": row.created_at.isoformat()
                if hasattr(row.created_at, "isoformat")
                else str(row.created_at),
            }
            for row in rows
        ]
    }


def _chapter_job_events_payload(
    branch_id: str, chapter_index: int, database_url: str | None, limit: int
) -> dict[str, Any]:
    runtime = get_settings().model_copy(deep=True)
    if database_url:
        runtime.database_url = database_url
    factory = create_session_factory(runtime)
    with factory() as session:
        rows = JobEventService(session).list_for_chapter(branch_id, chapter_index, limit)
    return {
        "items": [
            {
                "id": row.id,
                "run_id": row.run_id,
                "branch_id": row.branch_id,
                "chapter_index": row.chapter_index,
                "event_type": row.event_type,
                "stage": row.stage,
                "level": row.level,
                "message": row.message,
                "payload_json": row.payload_json,
                "created_at": row.created_at.isoformat()
                if hasattr(row.created_at, "isoformat")
                else str(row.created_at),
            }
            for row in rows
        ]
    }


def application(environ: dict[str, Any], start_response: StartResponse) -> list[bytes]:
    """Soft-cutover (v5 T10): only /api/review-batch-execute remains here.

    All other endpoints have moved to apps/api/app/fastapi_app.py and
    are served by uvicorn (`make api-dev`). WSGI dispatch is now reached
    via `make api-wsgi-legacy` (rollback) or via the FastAPI router
    delegation in risk_review.py for /api/review-batch-execute.
    """
    method = environ.get("REQUEST_METHOD", "GET")
    path = environ.get("PATH_INFO", "/")

    if method == "OPTIONS":
        return _response(start_response, status="200 OK", payload={"ok": True})

    if path == "/api/review-batch-execute" and method == "POST":
        body = _body(environ)
        run_id = str(body.get("run_id") or "")
        branch_id = str(body.get("branch_id") or "")
        action = str(body.get("action") or "")
        hint_code = str(body.get("hint_code") or "")
        group_strategy = str(body.get("group_strategy") or "")
        group_key = str(body.get("group_key") or "")
        cluster_keys = body.get("cluster_keys") or []
        if (
            not run_id
            or not branch_id
            or not action
            or not hint_code
            or not group_strategy
            or not group_key
        ):
            return _response(
                start_response,
                status="400 Bad Request",
                payload={
                    "error": "run_id, branch_id, action, hint_code, group_strategy and group_key are required"
                },
            )
        action_config = _BATCH_ACTION_CONFIG.get(action)
        if action_config is None:
            return _response(
                start_response,
                status="400 Bad Request",
                payload={"error": "unsupported batch action"},
            )
        if not isinstance(cluster_keys, list) or not all(isinstance(item, str) for item in cluster_keys):
            return _response(
                start_response,
                status="400 Bad Request",
                payload={"error": "cluster_keys must be a list[str]"},
            )
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
                    return _response(
                        start_response,
                        status="404 Not Found",
                        payload={"error": "batch suggestion not found"},
                    )
                allowed_hints = cast(set[str], action_config["allowed_hints"])
                if hint_code not in allowed_hints:
                    return _response(
                        start_response,
                        status="400 Bad Request",
                        payload={"error": f"hint_code {hint_code} is not valid for action {action}"},
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
                        return _response(
                            start_response,
                            status="400 Bad Request",
                            payload={
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
                    return _response(
                        start_response,
                        status="200 OK",
                        payload={
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
                        },
                    )
                success_results: list[dict[str, str]] = []
                failed_results: list[dict[str, str]] = []
                target_cluster_status = cast(str, action_config["cluster_status"])
                preserve_existing_state = bool(action_config.get("preserve_existing_state"))
                for cluster_key in target_cluster_keys:
                    try:
                        cluster_snapshot = target_cluster_map.get(cluster_key, {})
                        effective_cluster_status = target_cluster_status
                        effective_review_result = review_result or cast(
                            str,
                            action_config["default_review_result"],
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
                return _response(
                    start_response,
                    status="200 OK",
                    payload={
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
                    },
                )
        except Exception as exc:  # noqa: BLE001
            return _response(
                start_response,
                status="500 Internal Server Error",
                payload={"error": str(exc)},
            )


    return _response(
        start_response,
        status="404 Not Found",
        payload={
            "error": "endpoint not found",
            "hint": "Most paths moved to FastAPI (uvicorn :8011). Only /api/review-batch-execute is served here.",
        },
    )

def main() -> None:
    """Run the prototype backend locally."""

    host = "127.0.0.1"
    port = 8011
    _migrate_legacy_runtime_dirs()
    with make_server(host, port, application, server_class=ThreadingWSGIServer) as httpd:
        print(f"apps/api running on http://{host}:{port}")
        httpd.serve_forever()


if __name__ == "__main__":
    main()
