"""Lightweight WSGI backend for the workbench prototype."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any
from urllib.parse import parse_qs
from wsgiref.simple_server import make_server
from wsgiref.types import StartResponse

from novel_analyzer.application import get_branch_snapshot, get_run_snapshot


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
            ("Content-Length", str(len(body))),
        ],
    )
    return [body]


def _query(environ: dict[str, Any]) -> dict[str, str]:
    raw = parse_qs(environ.get("QUERY_STRING", ""))
    return {key: values[-1] for key, values in raw.items() if values}


def _require(params: dict[str, str], *keys: str) -> tuple[bool, str | None]:
    for key in keys:
        if not params.get(key):
            return False, key
    return True, None


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
            }
        ],
        "failed_summary": [],
    }


def application(environ: dict[str, Any], start_response: StartResponse) -> list[bytes]:
    method = environ.get("REQUEST_METHOD", "GET")
    path = environ.get("PATH_INFO", "/")
    params = _query(environ)

    if method != "GET":
        return _response(
            start_response,
            status="405 Method Not Allowed",
            payload={"error": "only GET is supported in the current prototype"},
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
                    "/api/run-snapshot",
                    "/api/branch-snapshot",
                ],
                "notes": [
                    "Current backend is dependency-light WSGI JSON.",
                    "Real write-side import/upload endpoints are still future work.",
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

    return _response(
        start_response,
        status="404 Not Found",
        payload={"error": "route not found"},
    )


def main() -> None:
    """Run the prototype backend locally."""

    host = "127.0.0.1"
    port = 8011
    with make_server(host, port, application) as httpd:
        print(f"apps/api running on http://{host}:{port}")
        httpd.serve_forever()


if __name__ == "__main__":
    main()
