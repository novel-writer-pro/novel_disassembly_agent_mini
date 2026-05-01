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
    ChapterManifest,
    ChapterSegment,
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
from novel_analyzer.services.job_event_service import JobEventService
from novel_analyzer.services.qa_service import BranchQAService
from novel_analyzer.services.retrieval_service import RetrievalService
from novel_analyzer.services.status_service import StatusService


class ThreadingWSGIServer(ThreadingMixIn, WSGIServer):
    """Serve concurrent WSGI requests so long operations don't block the whole API."""

    daemon_threads = True


_RUNTIME_MIGRATED = False


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


def _library_payload(database_url: str | None, limit: int) -> dict[str, Any]:
    runtime = get_settings().model_copy(deep=True)
    if database_url:
        runtime.database_url = database_url
    factory = create_session_factory(runtime)
    rows: list[dict[str, Any]] = []
    with factory() as session:
        branches = session.scalars(
            session.query(RunBranch).order_by(RunBranch.updated_at.desc()).limit(limit).statement
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
    method = environ.get("REQUEST_METHOD", "GET")
    path = environ.get("PATH_INFO", "/")
    params = _query(environ)

    if method == "OPTIONS":
        return _response(start_response, status="200 OK", payload={"ok": True})

    if method not in {"GET", "POST"}:
        return _response(
            start_response,
            status="405 Method Not Allowed",
            payload={"error": "only GET/POST are supported in the current prototype"},
        )

    if path == "/health":
        return _response(
            start_response,
            status="200 OK",
            payload={"status": "ok", "service": "apps/api"},
        )

    if path == "/api/meta":
        return _response(
            start_response,
            status="200 OK",
            payload={
                "service": "novel-analyzer-api-prototype",
                "available_endpoints": [
                    "/health",
                    "/api/meta",
                    "/api/mock/import",
                    "/api/import",
                    "/api/run-snapshot",
                    "/api/branch-snapshot",
                    "/api/chapter-bundle",
                    "/api/chapter-qa-context",
                    "/api/chapter-source",
                    "/api/chapter-jobs",
                    "/api/chapter-job-events",
                    "/api/review-clusters",
                    "/api/review-cluster-summary",
                    "/api/review-cluster-history",
                    "/api/review-cluster-update",
                    "/api/review-batch-execute",
                    "/api/review-batch-history",
                    "/api/library",
                    "/api/job-events",
                    "/api/pipeline/start-range",
                    "/api/pipeline/status",
                    "/api/pipeline/runs",
                    "/api/pipeline/pause",
                    "/api/pipeline/resume",
                    "/api/pipeline/cancel",
                    "/api/runtime-health",
                    "/api/provider-health",
                    "/api/search-branch",
                    "/api/ask-branch",
                    "/api/ask-branch-stream",
                    "/api/branch-exports",
                    "/api/download",
                ],
                "notes": [
                    "Current backend is dependency-light WSGI JSON.",
                    "The import/upload endpoint is available; broader write-side workflow surfaces remain incrementally productized.",
                ],
            },
        )

    if path == "/api/mock/import":
        profile = params.get("profile", "auto-lite")
        return _response(
            start_response,
            status="200 OK",
            payload={
                "import_result": _mock_import(profile),
                "run_snapshot": _mock_run_snapshot(profile),
                "branch_snapshot": _mock_branch_snapshot(profile),
            },
        )

    if path == "/api/import" and method == "POST":
        body = _body(environ)
        file_item = body.get("file")
        if file_item is None:
            return _response(
                start_response,
                status="400 Bad Request",
                payload={"error": "missing uploaded file"},
            )
        path_on_disk = _persist_uploaded_text(file_item)
        title = str(body.get("title") or "")
        profile = str(body.get("pipeline_profile") or "auto-lite")
        database_url = str(body.get("database_url") or "") or None
        max_chapters_raw = str(body.get("max_chapters") or "").strip()
        max_chapters = int(max_chapters_raw) if max_chapters_raw else None
        try:
            result = ingest_and_start_pipeline(
                path=path_on_disk,
                title=title or None,
                pipeline_profile=profile,
                max_chapters=max_chapters,
                database_url=database_url,
            )
            run_snapshot = None
            branch_snapshot = None
            if result.run_id and result.branch_id:
                run_snapshot = get_run_snapshot(
                    run_id=result.run_id,
                    branch_id=result.branch_id,
                    database_url=database_url,
                )
                branch_snapshot = get_branch_snapshot(
                    run_id=result.run_id,
                    branch_id=result.branch_id,
                    database_url=database_url,
                )
        except Exception as exc:  # noqa: BLE001
            return _response(
                start_response,
                status="500 Internal Server Error",
                payload={"error": str(exc)},
            )
        return _response(
            start_response,
            status="200 OK",
            payload={
                "import_result": asdict(result),
                "run_snapshot": asdict(run_snapshot) if run_snapshot else None,
                "branch_snapshot": asdict(branch_snapshot) if branch_snapshot else None,
            },
        )

    if path == "/api/start" and method == "POST":
        body = _body(environ)
        run_id = str(body.get("run_id") or "")
        branch_id = str(body.get("branch_id") or "")
        if not run_id or not branch_id:
            return _response(
                start_response,
                status="400 Bad Request",
                payload={"error": "run_id and branch_id are required"},
            )
        profile = str(body.get("pipeline_profile") or "auto-lite")
        database_url = str(body.get("database_url") or "") or None
        max_chapters_raw = str(body.get("max_chapters") or "").strip()
        max_chapters = int(max_chapters_raw) if max_chapters_raw else None
        try:
            processed_chapters, next_chapter, pipeline_state = start_pipeline(
                run_id=run_id,
                branch_id=branch_id,
                pipeline_profile=profile,
                max_chapters=max_chapters,
                database_url=database_url,
            )
        except Exception as exc:  # noqa: BLE001
            return _response(
                start_response,
                status="500 Internal Server Error",
                payload={"error": str(exc)},
            )
        return _response(
            start_response,
            status="200 OK",
            payload={
                "processed_chapters": processed_chapters,
                "next_chapter": next_chapter,
                "pipeline_state": pipeline_state,
            },
        )

    if path == "/api/recovery" and method == "POST":
        body = _body(environ)
        run_id = str(body.get("run_id") or "")
        branch_id = str(body.get("branch_id") or "")
        action = str(body.get("action") or "")
        if not run_id or not branch_id or not action:
            return _response(
                start_response,
                status="400 Bad Request",
                payload={"error": "run_id, branch_id and action are required"},
            )
        chapter_index_raw = str(body.get("chapter_index") or "").strip()
        chapter_index = int(chapter_index_raw) if chapter_index_raw else None
        database_url = str(body.get("database_url") or "") or None
        try:
            recovery_result = recover_branch(
                action=action,
                run_id=run_id,
                branch_id=branch_id,
                chapter_index=chapter_index,
                database_url=database_url,
            )
        except Exception as exc:  # noqa: BLE001
            return _response(
                start_response,
                status="500 Internal Server Error",
                payload={"error": str(exc)},
            )
        return _response(start_response, status="200 OK", payload=recovery_result)

    if path == "/api/run-snapshot":
        ok, missing = _require(params, "run_id", "branch_id")
        if not ok:
            return _response(
                start_response,
                status="400 Bad Request",
                payload={"error": f"missing query parameter: {missing}"},
            )
        try:
            run_snapshot = get_run_snapshot(
                run_id=params["run_id"],
                branch_id=params["branch_id"],
                database_url=params.get("database_url"),
            )
        except Exception as exc:  # noqa: BLE001
            return _response(
                start_response,
                status="500 Internal Server Error",
                payload={"error": str(exc)},
            )
        return _response(start_response, status="200 OK", payload=run_snapshot)

    if path == "/api/branch-snapshot":
        ok, missing = _require(params, "run_id", "branch_id")
        if not ok:
            return _response(
                start_response,
                status="400 Bad Request",
                payload={"error": f"missing query parameter: {missing}"},
            )
        try:
            branch_snapshot = get_branch_snapshot(
                run_id=params["run_id"],
                branch_id=params["branch_id"],
                database_url=params.get("database_url"),
            )
        except Exception as exc:  # noqa: BLE001
            return _response(
                start_response,
                status="500 Internal Server Error",
                payload={"error": str(exc)},
            )
        return _response(start_response, status="200 OK", payload=branch_snapshot)

    if path == "/api/chapter-bundle":
        ok, missing = _require(params, "branch_id", "chapter_index")
        if not ok:
            return _response(
                start_response,
                status="400 Bad Request",
                payload={"error": f"missing query parameter: {missing}"},
            )
        runtime = get_settings().model_copy(deep=True)
        if params.get("database_url"):
            runtime.database_url = params["database_url"]
        try:
            factory = create_session_factory(runtime)
            with factory() as session:
                bundle = ExportService(session).export_chapter_bundle(
                    params["branch_id"],
                    int(params["chapter_index"]),
                )
        except Exception as exc:  # noqa: BLE001
            return _response(
                start_response,
                status="500 Internal Server Error",
                payload={"error": str(exc)},
            )
        return _response(start_response, status="200 OK", payload=bundle)

    if path == "/api/chapter-qa-context":
        ok, missing = _require(params, "branch_id", "chapter_index")
        if not ok:
            return _response(
                start_response,
                status="400 Bad Request",
                payload={"error": f"missing query parameter: {missing}"},
            )
        runtime = get_settings().model_copy(deep=True)
        if params.get("database_url"):
            runtime.database_url = params["database_url"]
        try:
            factory = create_session_factory(runtime)
            with factory() as session:
                qa_payload = ExportService(session).export_chapter_qa_context(
                    params["branch_id"],
                    int(params["chapter_index"]),
                )
        except Exception as exc:  # noqa: BLE001
            return _response(
                start_response,
                status="500 Internal Server Error",
                payload={"error": str(exc)},
            )
        return _response(start_response, status="200 OK", payload=qa_payload)

    if path == "/api/chapter-source":
        ok, missing = _require(params, "branch_id", "chapter_index")
        if not ok:
            return _response(
                start_response,
                status="400 Bad Request",
                payload={"error": f"missing query parameter: {missing}"},
            )
        try:
            payload = _chapter_source_payload(
                branch_id=params["branch_id"],
                chapter_index=int(params["chapter_index"]),
                database_url=params.get("database_url"),
            )
        except Exception as exc:  # noqa: BLE001
            return _response(
                start_response,
                status="500 Internal Server Error",
                payload={"error": str(exc)},
            )
        return _response(start_response, status="200 OK", payload=payload)

    if path == "/api/chapter-jobs":
        ok, missing = _require(params, "branch_id")
        if not ok:
            return _response(
                start_response,
                status="400 Bad Request",
                payload={"error": f"missing query parameter: {missing}"},
            )
        try:
            rows = get_branch_job_rows(
                branch_id=params["branch_id"],
                database_url=params.get("database_url"),
                limit=int(params.get("limit", "200")),
            )
        except Exception as exc:  # noqa: BLE001
            return _response(
                start_response,
                status="500 Internal Server Error",
                payload={"error": str(exc)},
            )
        return _response(
            start_response, status="200 OK", payload={"items": [asdict(item) for item in rows]}
        )

    if path == "/api/library":
        database_url = params.get("database_url")
        limit = int(params.get("limit", "100"))
        try:
            payload = _library_payload(database_url, limit)
        except Exception as exc:  # noqa: BLE001
            return _response(
                start_response,
                status="500 Internal Server Error",
                payload={"error": str(exc)},
            )
        return _response(start_response, status="200 OK", payload=payload)

    if path == "/api/job-events":
        ok, missing = _require(params, "branch_id")
        if not ok:
            return _response(
                start_response,
                status="400 Bad Request",
                payload={"error": f"missing query parameter: {missing}"},
            )
        database_url = params.get("database_url")
        limit = int(params.get("limit", "100"))
        try:
            payload = _job_events_payload(params["branch_id"], database_url, limit)
        except Exception as exc:  # noqa: BLE001
            return _response(
                start_response,
                status="500 Internal Server Error",
                payload={"error": str(exc)},
            )
        return _response(start_response, status="200 OK", payload=payload)

    if path == "/api/chapter-job-events":
        ok, missing = _require(params, "branch_id", "chapter_index")
        if not ok:
            return _response(
                start_response,
                status="400 Bad Request",
                payload={"error": f"missing query parameter: {missing}"},
            )
        database_url = params.get("database_url")
        limit = int(params.get("limit", "100"))
        try:
            payload = _chapter_job_events_payload(
                params["branch_id"],
                int(params["chapter_index"]),
                database_url,
                limit,
            )
        except Exception as exc:  # noqa: BLE001
            return _response(
                start_response,
                status="500 Internal Server Error",
                payload={"error": str(exc)},
            )
        return _response(start_response, status="200 OK", payload=payload)

    if path == "/api/review-clusters":
        ok, missing = _require(params, "run_id", "branch_id")
        if not ok:
            return _response(
                start_response,
                status="400 Bad Request",
                payload={"error": f"missing query parameter: {missing}"},
            )
        runtime = get_settings().model_copy(deep=True)
        if params.get("database_url"):
            runtime.database_url = params["database_url"]
        try:
            factory = create_session_factory(runtime)
            with factory() as session:
                bundle = ExportService(session).export_branch_bundle(
                    params["run_id"],
                    params["branch_id"],
                )
                filters = _review_filters(params)
                candidate_clusters = cast(
                    list[dict[str, object]],
                    bundle.get("risk_summary", {}).get("review_candidate_clusters", []),
                )
                items = _apply_review_filters(candidate_clusters, filters)
                payload = {
                    **_review_contract(),
                    "review_storage_mode": bundle.get("review_storage_mode"),
                    "filters": filters,
                    "items": items,
                }
        except Exception as exc:  # noqa: BLE001
            return _response(
                start_response,
                status="500 Internal Server Error",
                payload={"error": str(exc)},
            )
        return _response(start_response, status="200 OK", payload=payload)

    if path == "/api/review-cluster-summary":
        ok, missing = _require(params, "run_id", "branch_id")
        if not ok:
            return _response(
                start_response,
                status="400 Bad Request",
                payload={"error": f"missing query parameter: {missing}"},
            )
        runtime = get_settings().model_copy(deep=True)
        if params.get("database_url"):
            runtime.database_url = params["database_url"]
        try:
            factory = create_session_factory(runtime)
            with factory() as session:
                bundle = ExportService(session).export_branch_bundle(
                    params["run_id"],
                    params["branch_id"],
                )
                filters = _review_filters(params)
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
                payload = {**_review_contract(), **payload}
        except Exception as exc:  # noqa: BLE001
            return _response(
                start_response,
                status="500 Internal Server Error",
                payload={"error": str(exc)},
            )
        return _response(start_response, status="200 OK", payload=payload)

    if path == "/api/review-cluster-history":
        ok, missing = _require(params, "branch_id", "cluster_key")
        if not ok:
            return _response(
                start_response,
                status="400 Bad Request",
                payload={"error": f"missing query parameter: {missing}"},
            )
        runtime = get_settings().model_copy(deep=True)
        if params.get("database_url"):
            runtime.database_url = params["database_url"]
        event_type_filter = str(params.get("event_type") or "").strip()
        owner_filter = str(params.get("review_owner") or "").strip()
        result_filter = str(params.get("review_result") or "").strip()
        limit = int(params.get("limit", "0") or "0")
        try:
            factory = create_session_factory(runtime)
            with factory() as session:
                try:
                    items = ClusterReviewService(session).read_history(
                        params["branch_id"],
                        params["cluster_key"],
                    )
                    review_storage_mode = "db"
                except ClusterReviewStorageUnavailable:
                    items = read_cluster_review_history(
                        params["branch_id"],
                        params["cluster_key"],
                        runtime,
                    )
                    review_storage_mode = "file-fallback"
                items = _apply_history_filters(
                    items,
                    event_type_filter=event_type_filter,
                    owner_filter=owner_filter,
                    result_filter=result_filter,
                    limit=limit,
                )
                payload = {
                    **_review_contract(),
                    "review_storage_mode": review_storage_mode,
                    "filters": {
                        key: value
                        for key, value in {
                            "event_type": event_type_filter,
                            "review_owner": owner_filter,
                            "review_result": result_filter,
                        }.items()
                        if value
                    },
                    "items": items,
                }
        except Exception as exc:  # noqa: BLE001
            if not ClusterReviewService._is_missing_relation_error(exc):
                return _response(
                    start_response,
                    status="500 Internal Server Error",
                    payload={"error": str(exc)},
                )
            payload = {
                **_review_contract(),
                "review_storage_mode": "file-fallback",
                "filters": {
                    key: value
                    for key, value in {
                        "event_type": event_type_filter,
                        "review_owner": owner_filter,
                        "review_result": result_filter,
                    }.items()
                    if value
                },
                "items": _apply_history_filters(
                    read_cluster_review_history(
                        params["branch_id"],
                        params["cluster_key"],
                        runtime,
                    ),
                    event_type_filter=event_type_filter,
                    owner_filter=owner_filter,
                    result_filter=result_filter,
                    limit=limit,
                ),
            }
        return _response(start_response, status="200 OK", payload=payload)

    if path == "/api/review-cluster-update" and method == "POST":
        body = _body(environ)
        branch_id = str(body.get("branch_id") or "")
        cluster_key = str(body.get("cluster_key") or "")
        cluster_status = str(body.get("cluster_status") or "")
        if not branch_id or not cluster_key or not cluster_status:
            return _response(
                start_response,
                status="400 Bad Request",
                payload={"error": "branch_id, cluster_key and cluster_status are required"},
            )
        runtime = get_settings().model_copy(deep=True)
        database_url = str(body.get("database_url") or "") or None
        if database_url:
            runtime.database_url = database_url
        review_payload = {
            "review_notes": str(body.get("review_notes") or ""),
        "review_owner": str(body.get("review_owner") or ""),
        "review_actor": str(body.get("review_actor") or ""),
        "resolved_at": str(body.get("resolved_at") or ""),
        "review_result": str(body.get("review_result") or ""),
    }
        try:
            factory = create_session_factory(runtime)
            review_storage_mode = "db"
            with factory() as session:
                state = ClusterReviewService(session).write(
                    branch_id=branch_id,
                    cluster_key=cluster_key,
                    cluster_status=cluster_status,
                    **review_payload,
                )
                payload = {**_review_contract(), **asdict(state), "review_storage_mode": "db"}
        except ValueError as exc:
            return _response(
                start_response,
                status="400 Bad Request",
                payload={"error": str(exc)},
            )
        except Exception as exc:  # noqa: BLE001
            if not ClusterReviewService._is_missing_relation_error(exc):
                return _response(
                    start_response,
                    status="500 Internal Server Error",
                    payload={"error": str(exc)},
                )
            state = write_cluster_review_state(
                branch_id=branch_id,
                cluster_key=cluster_key,
                cluster_status=cluster_status,
                settings=runtime,
                **review_payload,
            )
            payload = {
                **_review_contract(),
                **asdict(state),
                "review_storage_mode": "file-fallback",
            }
        return _response(start_response, status="200 OK", payload=payload)

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

    if path == "/api/review-batch-history":
        ok, missing = _require(params, "branch_id")
        if not ok:
            return _response(
                start_response,
                status="400 Bad Request",
                payload={"error": f"missing query parameter: {missing}"},
            )
        runtime = get_settings().model_copy(deep=True)
        if params.get("database_url"):
            runtime.database_url = params["database_url"]
        limit = int(params.get("limit", "0") or "0")
        items = read_batch_execution_history(params["branch_id"], runtime)
        if limit > 0:
            items = items[-limit:]
        return _response(
            start_response,
            status="200 OK",
            payload={
                **_review_contract(),
                "branch_id": params["branch_id"],
                "items": items,
            },
        )

    if path == "/api/pipeline/start-range" and method == "POST":
        body = _body(environ)
        run_id = str(body.get("run_id") or "")
        branch_id = str(body.get("branch_id") or "")
        if not run_id or not branch_id:
            return _response(
                start_response,
                status="400 Bad Request",
                payload={"error": "run_id and branch_id are required"},
            )
        try:
            snapshot = start_pipeline_run_async(
                run_id=run_id,
                branch_id=branch_id,
                target_from_chapter=int(str(body.get("from_chapter")))
                if body.get("from_chapter")
                else None,
                target_to_chapter=int(str(body.get("to_chapter")))
                if body.get("to_chapter")
                else None,
                concurrency=int(str(body.get("concurrency") or "1")),
                provider_profile=str(body.get("provider_profile") or "") or None,
                created_by="api",
                database_url=str(body.get("database_url") or "") or None,
            )
        except Exception as exc:  # noqa: BLE001
            return _response(
                start_response,
                status="500 Internal Server Error",
                payload={"error": str(exc)},
            )
        return _response(start_response, status="200 OK", payload=asdict(snapshot))

    if path == "/api/pipeline/status":
        ok, missing = _require(params, "pipeline_run_id")
        if not ok:
            return _response(
                start_response,
                status="400 Bad Request",
                payload={"error": f"missing query parameter: {missing}"},
            )
        try:
            snapshot = get_pipeline_run_status(
                pipeline_run_id=params["pipeline_run_id"],
                database_url=params.get("database_url"),
            )
        except Exception as exc:  # noqa: BLE001
            return _response(
                start_response, status="500 Internal Server Error", payload={"error": str(exc)}
            )
        return _response(start_response, status="200 OK", payload=asdict(snapshot))

    if path == "/api/pipeline/runs":
        ok, missing = _require(params, "branch_id")
        if not ok:
            return _response(
                start_response,
                status="400 Bad Request",
                payload={"error": f"missing query parameter: {missing}"},
            )
        try:
            rows = list_pipeline_runs(
                branch_id=params["branch_id"],
                limit=int(params.get("limit", "20")),
                database_url=params.get("database_url"),
            )
        except Exception as exc:  # noqa: BLE001
            return _response(
                start_response, status="500 Internal Server Error", payload={"error": str(exc)}
            )
        return _response(
            start_response, status="200 OK", payload={"items": [asdict(item) for item in rows]}
        )

    if (
        path in {"/api/pipeline/pause", "/api/pipeline/resume", "/api/pipeline/cancel"}
        and method == "POST"
    ):
        body = _body(environ)
        pipeline_run_id = str(body.get("pipeline_run_id") or "")
        if not pipeline_run_id:
            return _response(
                start_response,
                status="400 Bad Request",
                payload={"error": "pipeline_run_id is required"},
            )
        try:
            if path.endswith("/pause"):
                snapshot = pause_pipeline_run(
                    pipeline_run_id=pipeline_run_id,
                    database_url=str(body.get("database_url") or "") or None,
                )
            elif path.endswith("/resume"):
                snapshot = resume_pipeline_run(
                    pipeline_run_id=pipeline_run_id,
                    database_url=str(body.get("database_url") or "") or None,
                )
            else:
                snapshot = cancel_pipeline_run(
                    pipeline_run_id=pipeline_run_id,
                    database_url=str(body.get("database_url") or "") or None,
                )
        except Exception as exc:  # noqa: BLE001
            return _response(
                start_response, status="500 Internal Server Error", payload={"error": str(exc)}
            )
        return _response(start_response, status="200 OK", payload=asdict(snapshot))

    if path == "/api/runtime-health":
        try:
            report = describe_runtime_storage(get_settings())
        except Exception as exc:  # noqa: BLE001
            return _response(
                start_response,
                status="500 Internal Server Error",
                payload={"error": str(exc)},
            )
        return _response(start_response, status="200 OK", payload=asdict(report))

    if path == "/api/provider-health":
        try:
            report = read_provider_health(get_settings())
        except Exception as exc:  # noqa: BLE001
            return _response(
                start_response,
                status="500 Internal Server Error",
                payload={"error": str(exc)},
            )
        return _response(start_response, status="200 OK", payload=asdict(report))

    if path == "/api/search-branch":
        ok, missing = _require(params, "branch_id", "q")
        if not ok:
            return _response(
                start_response,
                status="400 Bad Request",
                payload={"error": f"missing query parameter: {missing}"},
            )
        runtime = get_settings().model_copy(deep=True)
        if params.get("database_url"):
            runtime.database_url = params["database_url"]
        limit = int(params.get("limit", "8"))
        try:
            factory = create_session_factory(runtime)
            with factory() as session:
                hits = RetrievalService(session, runtime).search_branch(
                    params["branch_id"], params["q"], limit
                )
        except Exception as exc:  # noqa: BLE001
            return _response(
                start_response,
                status="500 Internal Server Error",
                payload={"error": str(exc)},
            )
        return _response(
            start_response, status="200 OK", payload={"hits": [asdict(hit) for hit in hits]}
        )

    if path == "/api/ask-branch" and method == "POST":
        body = _body(environ)
        branch_id = str(body.get("branch_id") or "")
        question = str(body.get("question") or "")
        if not branch_id or not question:
            return _response(
                start_response,
                status="400 Bad Request",
                payload={"error": "branch_id and question are required"},
            )
        runtime = get_settings().model_copy(deep=True)
        database_url = str(body.get("database_url") or "") or None
        if database_url:
            runtime.database_url = database_url
        limit = int(str(body.get("limit") or "6"))
        try:
            factory = create_session_factory(runtime)
            with factory() as session:
                result = BranchQAService(session, runtime).answer_question(
                    branch_id, question, limit
                )
        except Exception as exc:  # noqa: BLE001
            return _response(
                start_response,
                status="500 Internal Server Error",
                payload={"error": str(exc)},
            )
        return _response(start_response, status="200 OK", payload=result.model_dump(mode="json"))

    if path == "/api/ask-branch-stream" and method == "POST":
        body = _body(environ)
        branch_id = str(body.get("branch_id") or "")
        question = str(body.get("question") or "")
        if not branch_id or not question:
            return _response(
                start_response,
                status="400 Bad Request",
                payload={"error": "branch_id and question are required"},
            )
        runtime = get_settings().model_copy(deep=True)
        database_url = str(body.get("database_url") or "") or None
        if database_url:
            runtime.database_url = database_url
        limit = int(str(body.get("limit") or "6"))

        def _event_iter() -> Any:
            yield _sse_event({"type": "status", "message": "正在检索相关章节…"})
            try:
                factory = create_session_factory(runtime)
                with factory() as session:
                    hits = RetrievalService(session, runtime).search_branch(
                        branch_id, question, limit
                    )
                    yield _sse_event(
                        {
                            "type": "retrieval",
                            "hits": [asdict(hit) for hit in hits],
                        }
                    )
                    yield _sse_event(
                        {"type": "status", "message": "正在结合证据与图谱线索组织回答…"}
                    )
                    result = BranchQAService(session, runtime).answer_question(
                        branch_id, question, limit
                    )
                answer_text = result.answer or ""
                for index in range(0, len(answer_text), 20):
                    yield _sse_event({"type": "delta", "delta": answer_text[index : index + 20]})
                yield _sse_event({"type": "final", "result": result.model_dump(mode="json")})
            except Exception as exc:  # noqa: BLE001
                yield _sse_event({"type": "error", "error": str(exc)})

        return _stream_response(start_response, _event_iter())

    if path == "/api/branch-exports":
        ok, missing = _require(params, "run_id", "branch_id")
        if not ok:
            return _response(
                start_response,
                status="400 Bad Request",
                payload={"error": f"missing query parameter: {missing}"},
            )
        try:
            refs = export_branch_refs(
                run_id=params["run_id"],
                branch_id=params["branch_id"],
                output_dir=_stable_export_dir(params["run_id"], params["branch_id"]),
                database_url=params.get("database_url"),
            )
        except Exception as exc:  # noqa: BLE001
            return _response(
                start_response,
                status="500 Internal Server Error",
                payload={"error": str(exc)},
            )
        return _response(
            start_response,
            status="200 OK",
            payload={
                "branch_bundle": {
                    "download_ref": f"/api/download?path={refs.branch_bundle_path}",
                    "content_type": "application/json",
                },
                "branch_qa_context": {
                    "download_ref": f"/api/download?path={refs.branch_qa_context_path}",
                    "content_type": "application/json",
                },
                "branch_report": {
                    "download_ref": f"/api/download?path={refs.branch_report_path}",
                    "content_type": "text/markdown",
                },
            },
        )

    if path == "/api/download":
        ok, missing = _require(params, "path")
        if not ok:
            return _response(
                start_response,
                status="400 Bad Request",
                payload={"error": f"missing query parameter: {missing}"},
            )
        file_path = Path(params["path"])
        if not file_path.exists() or not file_path.is_file():
            return _response(
                start_response,
                status="404 Not Found",
                payload={"error": "export file not found"},
            )
        content_type = (
            "text/markdown; charset=utf-8"
            if file_path.suffix == ".md"
            else "application/json; charset=utf-8"
        )
        file_body = file_path.read_bytes()
        start_response(
            "200 OK",
            [
                ("Content-Type", content_type),
                ("Access-Control-Allow-Origin", "*"),
                ("Content-Length", str(len(file_body))),
                ("Content-Disposition", f'attachment; filename="{file_path.name}"'),
            ],
        )
        return [file_body]

    return _response(
        start_response,
        status="404 Not Found",
        payload={"error": "route not found"},
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
