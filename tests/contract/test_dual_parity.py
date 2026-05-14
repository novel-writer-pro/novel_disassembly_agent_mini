"""Dual-implementation parity — post-v5-cutover.

Pre-cutover this file checked 18 endpoints served by both WSGI and
FastAPI. After T10 only /api/review-batch-execute is served by both
(WSGI directly, FastAPI via delegation). This file verifies that the
single remaining dual path stays equivalent.

When v5.1 inlines review-batch-execute logic into the FastAPI router,
this file can be deleted entirely.
"""
from __future__ import annotations

import json
from io import BytesIO
from typing import Any, cast
from wsgiref.types import StartResponse

import pytest
from fastapi.testclient import TestClient

from apps.api.app.fastapi_app import create_app
from apps.api.app.main import application


def _wsgi_call(method: str, path: str, body: bytes = b"") -> tuple[str, dict[str, Any]]:
    captured: dict[str, Any] = {}
    pi, _, qs = path.partition("?")

    def sr(status: str, headers: list, exc_info=None) -> object:
        captured["status"] = status
        return lambda chunk: None

    raw = b"".join(application({
        "REQUEST_METHOD": method,
        "PATH_INFO": pi,
        "QUERY_STRING": qs,
        "CONTENT_TYPE": "application/json",
        "CONTENT_LENGTH": str(len(body)),
        "wsgi.input": BytesIO(body),
    }, cast(StartResponse, sr)))
    try:
        payload = json.loads(raw) if raw else {}
    except Exception:
        payload = {"_raw": raw.decode("utf-8", errors="replace")[:200]}
    return captured.get("status", "0"), payload


@pytest.fixture(scope="module")
def fastapi_client():
    return TestClient(create_app())


class TestReviewBatchExecuteParity:
    """The only path served by both surfaces after T10 cutover."""

    def test_empty_body_parity(self, fastapi_client):
        body = b"{}"
        w_status, w_body = _wsgi_call("POST", "/api/review-batch-execute", body)
        r = fastapi_client.post(
            "/api/review-batch-execute",
            content=body,
            headers={"Content-Type": "application/json"},
        )
        f_status = f"{r.status_code} {r.reason_phrase}"
        f_body = r.json()

        # Both should reject identically: 400 with {"error": "..."}
        assert int(w_status.split()[0]) == r.status_code
        assert sorted(w_body.keys()) == sorted(f_body.keys())
        assert w_body == f_body  # Same error message
