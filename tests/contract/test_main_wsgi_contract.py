"""WSGI contract test — post-v5-cutover reduced surface.

After v5 T10 (soft cutover), apps/api/app/main.py:application() only
serves /api/review-batch-execute plus a 404 fallback. The original
28-assertion contract has moved to test_main_fastapi_contract.py
(canonical surface served by uvicorn).

This file's job is now narrow: confirm the WSGI rollback path still
boots and the 404 fallback returns the expected envelope.
"""
from __future__ import annotations

import json
from io import BytesIO
from typing import Any, cast
from wsgiref.types import StartResponse

import pytest

from apps.api.app.main import application


def _call(path: str, method: str = "GET", body: bytes = b"") -> tuple[str, dict[str, Any]]:
    captured: dict[str, Any] = {}
    pi, _, qs = path.partition("?")

    def start_response(status: str, headers: list, exc_info=None) -> object:
        captured["status"] = status
        return lambda chunk: None

    raw = b"".join(application({
        "REQUEST_METHOD": method,
        "PATH_INFO": pi,
        "QUERY_STRING": qs,
        "CONTENT_TYPE": "application/json",
        "CONTENT_LENGTH": str(len(body)),
        "wsgi.input": BytesIO(body),
    }, cast(StartResponse, start_response)))
    try:
        payload = json.loads(raw) if raw else {}
    except Exception:
        payload = {"_raw": raw.decode("utf-8", errors="replace")[:200]}
    return captured.get("status", "0"), payload


class TestReducedWsgiSurface:
    def test_review_batch_execute_empty_body_400(self):
        """The one path WSGI still serves: review-batch-execute."""
        status, payload = _call("/api/review-batch-execute", "POST", b"{}")
        assert status == "400 Bad Request"
        assert "error" in payload

    def test_unknown_path_returns_404_with_hint(self):
        """Every other path now returns the 404 fallback envelope."""
        status, payload = _call("/health")
        assert status == "404 Not Found"
        assert "error" in payload
        assert "hint" in payload  # Should mention FastAPI/uvicorn
        assert "uvicorn" in payload["hint"].lower() or "FastAPI" in payload["hint"]

    def test_options_returns_200(self):
        """CORS preflight still works on the WSGI surface."""
        status, payload = _call("/api/review-batch-execute", "OPTIONS")
        assert status == "200 OK"
        assert payload.get("ok") is True

    def test_other_paths_now_404_not_400(self):
        """Confirm /api/library etc no longer have inline handlers — they all 404."""
        for path in ["/api/library", "/api/meta", "/api/import", "/api/chapter-bundle"]:
            status, payload = _call(path)
            assert status == "404 Not Found", f"{path}: expected 404 after cutover, got {status}"
