"""Lightweight runtime review state registry for risk clusters."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from novel_analyzer.config.settings import Settings, get_settings
from novel_analyzer.runtime.storage import runtime_cache_root

ALLOWED_REVIEW_RESULTS = {
    "",
    "confirmed-issue",
    "confirmed-benign",
    "needs-escalation",
    "deferred",
}

ALLOWED_CLUSTER_STATUSES = {
    "open",
    "needs_review",
    "reviewed",
    "escalated",
    "reopened",
    "resolved",
}


def _normalize_review_snapshot(payload: dict[str, object] | None) -> dict[str, str]:
    source = payload or {}
    return {
        "cluster_status": str(source.get("cluster_status") or ""),
        "review_result": str(source.get("review_result") or ""),
        "review_notes": str(source.get("review_notes") or ""),
        "review_owner": str(source.get("review_owner") or ""),
        "review_actor": str(source.get("review_actor") or ""),
        "resolved_at": str(source.get("resolved_at") or ""),
    }


def _changed_review_fields(
    previous: dict[str, str],
    current: dict[str, str],
) -> list[str]:
    fields = [
        "cluster_status",
        "review_result",
        "review_notes",
        "review_owner",
        "review_actor",
        "resolved_at",
    ]
    return [field for field in fields if previous.get(field, "") != current.get(field, "")]


def infer_review_event_type(
    previous: dict[str, str] | None,
    current: dict[str, str] | None,
) -> str:
    prev = _normalize_review_snapshot(previous)
    curr = _normalize_review_snapshot(current)
    changed_fields = _changed_review_fields(prev, curr)
    if not changed_fields:
        return "noop_update"
    if changed_fields == ["review_actor"]:
        return "actor_update"
    if changed_fields == ["review_owner"]:
        return "owner_update"
    if "review_owner" in changed_fields and "review_actor" in changed_fields:
        return "assignment_update"
    if changed_fields == ["review_notes"]:
        return "note_update"
    if changed_fields == ["resolved_at"]:
        return "resolution_marker_update"
    if changed_fields == ["review_result"]:
        return "result_update"
    if "cluster_status" in changed_fields:
        return "status_update"
    return "review_update"


def build_review_history_event(
    *,
    branch_id: str,
    cluster_key: str,
    event_index: int,
    previous: dict[str, object] | None,
    current: dict[str, object] | None,
    created_at: str,
    event_type: str | None = None,
) -> dict[str, str | int | list[str] | dict[str, str]]:
    prev = _normalize_review_snapshot(previous)
    curr = _normalize_review_snapshot(current)
    changed_fields = _changed_review_fields(prev, curr)
    resolved_event_type = event_type or infer_review_event_type(prev, curr)
    return {
        "event_index": event_index,
        "event_id": f"{branch_id}:{cluster_key}:{event_index}",
        "audit_key": f"{branch_id}:{cluster_key}:{event_index}",
        "previous_values": prev,
        "current_values": curr,
        "previous_cluster_status": prev["cluster_status"],
        "previous_review_result": prev["review_result"],
        "previous_review_notes": prev["review_notes"],
        "previous_review_owner": prev["review_owner"],
        "previous_review_actor": prev["review_actor"],
        "previous_resolved_at": prev["resolved_at"],
        "cluster_status": curr["cluster_status"],
        "review_result": curr["review_result"],
        "review_notes": curr["review_notes"],
        "review_owner": curr["review_owner"],
        "review_actor": curr["review_actor"],
        "resolved_at": curr["resolved_at"],
        "event_type": resolved_event_type,
        "changed_fields": changed_fields,
        "transition": f"{prev['cluster_status'] or 'new'}->{curr['cluster_status'] or 'unknown'}",
        "created_at": created_at,
    }


def _cluster_review_root(settings: Settings | None = None) -> Path:
    root = runtime_cache_root(settings) / "cluster-review"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _cluster_review_path(branch_id: str, settings: Settings | None = None) -> Path:
    return _cluster_review_root(settings) / f"{branch_id}.json"


@dataclass(frozen=True, slots=True)
class ClusterReviewState:
    branch_id: str
    cluster_key: str
    cluster_status: str
    review_notes: str = ""
    review_owner: str = ""
    review_actor: str = ""
    resolved_at: str = ""
    review_result: str = ""


def _cluster_review_history_path(branch_id: str, settings: Settings | None = None) -> Path:
    return _cluster_review_root(settings) / f"{branch_id}.history.json"


def _utc_timestamp() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def read_cluster_review_state(branch_id: str, settings: Settings | None = None) -> dict[str, dict[str, str]]:
    runtime = settings or get_settings()
    path = _cluster_review_path(branch_id, runtime)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(payload, dict):
        return {}
    result: dict[str, dict[str, str]] = {}
    for key, value in payload.items():
        if isinstance(key, str) and isinstance(value, dict):
            result[key] = {
                "cluster_status": str(value.get("cluster_status") or ""),
                "review_notes": str(value.get("review_notes") or ""),
                "review_owner": str(value.get("review_owner") or ""),
                "review_actor": str(value.get("review_actor") or ""),
                "resolved_at": str(value.get("resolved_at") or ""),
                "review_result": str(value.get("review_result") or ""),
            }
    return result


def read_cluster_review_history(
    branch_id: str,
    cluster_key: str,
    settings: Settings | None = None,
) -> list[dict[str, object]]:
    runtime = settings or get_settings()
    path = _cluster_review_history_path(branch_id, runtime)
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(payload, dict):
        return []
    events = payload.get(cluster_key, [])
    if not isinstance(events, list):
        return []
    result: list[dict[str, object]] = []
    for index, event in enumerate(events, start=1):
        if isinstance(event, dict):
            previous = {
                "cluster_status": event.get("previous_cluster_status"),
                "review_result": event.get("previous_review_result"),
                "review_notes": event.get("previous_review_notes"),
                "review_owner": event.get("previous_review_owner"),
                "review_actor": event.get("previous_review_actor"),
                "resolved_at": event.get("previous_resolved_at"),
            }
            current = {
                "cluster_status": event.get("cluster_status"),
                "review_result": event.get("review_result"),
                "review_notes": event.get("review_notes"),
                "review_owner": event.get("review_owner"),
                "review_actor": event.get("review_actor"),
                "resolved_at": event.get("resolved_at"),
            }
            result.append(
                build_review_history_event(
                    branch_id=branch_id,
                    cluster_key=cluster_key,
                    event_index=index,
                    previous=previous,
                    current=current,
                    created_at=str(event.get("created_at") or ""),
                    event_type=str(event.get("event_type") or "") or None,
                )
            )
    return result


def write_cluster_review_state(
    branch_id: str,
    cluster_key: str,
    cluster_status: str,
    *,
    review_notes: str = "",
    review_owner: str = "",
    review_actor: str = "",
    resolved_at: str = "",
    review_result: str = "",
    settings: Settings | None = None,
) -> ClusterReviewState:
    runtime = settings or get_settings()
    if cluster_status not in ALLOWED_CLUSTER_STATUSES:
        raise ValueError(
            f"Unsupported cluster_status: {cluster_status}. "
            f"Allowed: {sorted(ALLOWED_CLUSTER_STATUSES)}"
        )
    if review_result not in ALLOWED_REVIEW_RESULTS:
        raise ValueError(
            f"Unsupported review_result: {review_result}. "
            f"Allowed: {sorted(ALLOWED_REVIEW_RESULTS)}"
        )
    if cluster_status == "resolved" and not review_result:
        raise ValueError("cluster_status=resolved requires a non-empty review_result")
    if cluster_status == "escalated" and review_result != "needs-escalation":
        raise ValueError("cluster_status=escalated requires review_result=needs-escalation")
    if cluster_status == "resolved" and review_result == "needs-escalation":
        raise ValueError("cluster_status=resolved cannot be paired with review_result=needs-escalation")
    if review_result == "needs-escalation" and not review_notes.strip():
        raise ValueError("review_result=needs-escalation requires non-empty review_notes")
    path = _cluster_review_path(branch_id, runtime)
    payload = read_cluster_review_state(branch_id, runtime)
    previous = payload.get(cluster_key, {})
    payload[cluster_key] = {
        "cluster_status": cluster_status,
        "review_notes": review_notes,
        "review_owner": review_owner,
        "review_actor": review_actor or review_owner,
        "resolved_at": resolved_at,
        "review_result": review_result,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    history_path = _cluster_review_history_path(branch_id, runtime)
    try:
        history_payload = json.loads(history_path.read_text(encoding="utf-8")) if history_path.exists() else {}
    except Exception:
        history_payload = {}
    if not isinstance(history_payload, dict):
        history_payload = {}
    events = history_payload.get(cluster_key)
    if not isinstance(events, list):
        events = []
    current = {
        "cluster_status": cluster_status,
        "review_result": review_result,
        "review_notes": review_notes,
        "review_owner": review_owner,
        "review_actor": review_actor or review_owner,
        "resolved_at": resolved_at,
    }
    events.append(
        build_review_history_event(
            branch_id=branch_id,
            cluster_key=cluster_key,
            event_index=len(events) + 1,
            previous=previous,
            current=current,
            created_at=_utc_timestamp(),
        )
    )
    history_payload[cluster_key] = events
    history_path.write_text(json.dumps(history_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return ClusterReviewState(
        branch_id=branch_id,
        cluster_key=cluster_key,
        cluster_status=cluster_status,
        review_notes=review_notes,
        review_owner=review_owner,
        review_actor=review_actor or review_owner,
        resolved_at=resolved_at,
        review_result=review_result,
    )
