"""Lightweight runtime review state registry for risk clusters."""

from __future__ import annotations

import json
from dataclasses import dataclass
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
    resolved_at: str = ""
    review_result: str = ""


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
                "resolved_at": str(value.get("resolved_at") or ""),
                "review_result": str(value.get("review_result") or ""),
            }
    return result


def write_cluster_review_state(
    branch_id: str,
    cluster_key: str,
    cluster_status: str,
    *,
    review_notes: str = "",
    review_owner: str = "",
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
    payload[cluster_key] = {
        "cluster_status": cluster_status,
        "review_notes": review_notes,
        "review_owner": review_owner,
        "resolved_at": resolved_at,
        "review_result": review_result,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return ClusterReviewState(
        branch_id=branch_id,
        cluster_key=cluster_key,
        cluster_status=cluster_status,
        review_notes=review_notes,
        review_owner=review_owner,
        resolved_at=resolved_at,
        review_result=review_result,
    )
