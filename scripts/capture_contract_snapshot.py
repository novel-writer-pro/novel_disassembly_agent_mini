#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from io import BytesIO
from pathlib import Path
from typing import Any, cast
from wsgiref.types import StartResponse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from apps.api.app.main import application


def call(path: str, method: str = "GET", body: bytes = b"") -> tuple[str, dict]:
    captured: dict[str, Any] = {}
    path_info, _, query = path.partition("?")

    def start_response(status: str, headers: list, exc_info=None) -> object:
        captured["status"] = status
        return lambda chunk: None

    raw = b"".join(
        application(
            {
                "REQUEST_METHOD": method,
                "PATH_INFO": path_info,
                "QUERY_STRING": query,
                "CONTENT_TYPE": "application/json",
                "CONTENT_LENGTH": str(len(body)),
                "wsgi.input": BytesIO(body),
            },
            cast(StartResponse, start_response),
        )
    )
    try:
        payload = json.loads(raw)
    except Exception:
        payload = {}
    return captured["status"], payload


def keys_recursive(obj: Any, depth: int = 0, max_depth: int = 2) -> Any:
    if depth >= max_depth:
        return type(obj).__name__
    if isinstance(obj, dict):
        return {k: keys_recursive(v, depth + 1, max_depth) for k, v in sorted(obj.items())}
    if isinstance(obj, list):
        if not obj:
            return ["<empty>"]
        return [keys_recursive(obj[0], depth + 1, max_depth)]
    return type(obj).__name__


def main() -> int:
    snapshot: dict[str, Any] = {
        "schema_version": "writer-studio-v2-baseline-1",
        "captured_at": "2026-05-14",
        "endpoints": {},
    }
    endpoints = [
        ("GET", "/health", b""),
        ("GET", "/api/meta", b""),
        ("GET", "/api/library", b""),
        ("GET", "/api/runtime-health", b""),
        ("GET", "/api/provider-health", b""),
        ("GET", "/api/mock/import?profile=auto-lite", b""),
        ("GET", "/api/whole-book-imitation-readiness", b""),
        ("GET", "/api/job-events", b""),
        ("GET", "/api/chapter-bundle", b""),
        ("GET", "/api/run-snapshot", b""),
        ("GET", "/api/branch-snapshot", b""),
        ("GET", "/api/chapter-source", b""),
        ("GET", "/api/chapter-jobs", b""),
        ("GET", "/api/review-clusters", b""),
        ("GET", "/api/quality-dashboard", b""),
    ]

    for method, path, body in endpoints:
        try:
            status, payload = call(path, method, body)
            snapshot["endpoints"][f"{method} {path}"] = {
                "status": status,
                "shape": keys_recursive(payload),
            }
        except Exception as e:
            snapshot["endpoints"][f"{method} {path}"] = {"error": str(e)[:200]}

    out = ROOT / "tests/contract/baseline.snapshot.json"
    out.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False, sort_keys=True))
    print(f"wrote {out}  ({len(snapshot['endpoints'])} endpoints captured)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
