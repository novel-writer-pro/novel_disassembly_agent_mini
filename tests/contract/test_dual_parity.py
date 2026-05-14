"""WSGI vs FastAPI parity tests for the 18 dual-implementation endpoints.

T1 of v5-fastapi-cutover plan. Surfaces schema drift between
apps/api/app/main.py (WSGI) and apps/api/app/fastapi_app.py (FastAPI).

Each test uses a "missing required params" probe. Once T2-T4 fix the
drifts, these tests will all pass and form the cutover gate.
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

    raw = b"".join(
        application(
            {
                "REQUEST_METHOD": method,
                "PATH_INFO": pi,
                "QUERY_STRING": qs,
                "CONTENT_TYPE": "application/json",
                "CONTENT_LENGTH": str(len(body)),
                "wsgi.input": BytesIO(body),
            },
            cast(StartResponse, sr),
        )
    )
    try:
        payload = json.loads(raw) if raw else {}
    except Exception:
        payload = {"_raw": raw.decode("utf-8", errors="replace")[:200]}
    return captured.get("status", "0"), payload


@pytest.fixture(scope="module")
def fastapi_client():
    return TestClient(create_app())


def _fastapi_call(client: TestClient, method: str, path: str, body: bytes = b"") -> tuple[str, dict[str, Any]]:
    if method == "GET":
        r = client.get(path)
    elif method == "POST":
        r = client.post(path, content=body, headers={"Content-Type": "application/json"})
    else:
        raise ValueError(method)
    status_line = f"{r.status_code} {r.reason_phrase}"
    try:
        payload = r.json()
    except Exception:
        payload = {"_raw": r.text[:200]}
    return status_line, payload


def _assert_status_and_error_shape(wsgi_result: tuple[str, dict], fastapi_result: tuple[str, dict], path: str):
    """Both sides must return same status code AND same error envelope shape."""
    w_status, w_body = wsgi_result
    f_status, f_body = fastapi_result
    w_code = int(w_status.split()[0])
    f_code = int(f_status.split()[0])
    assert w_code == f_code, (
        f"[{path}] status code drift: WSGI={w_status} FastAPI={f_status}\n"
        f"  WSGI body: {json.dumps(w_body, ensure_ascii=False)[:200]}\n"
        f"  FastAPI body: {json.dumps(f_body, ensure_ascii=False)[:200]}"
    )
    if w_code >= 400:
        w_keys = sorted(w_body.keys())
        f_keys = sorted(f_body.keys())
        assert w_keys == f_keys, (
            f"[{path}] error envelope drift: WSGI keys={w_keys} FastAPI keys={f_keys}\n"
            f"  WSGI body: {json.dumps(w_body, ensure_ascii=False)[:200]}\n"
            f"  FastAPI body: {json.dumps(f_body, ensure_ascii=False)[:200]}"
        )


def _assert_same_keys(wsgi_result: tuple[str, dict], fastapi_result: tuple[str, dict], path: str):
    w_status, w_body = wsgi_result
    f_status, f_body = fastapi_result
    if w_status != f_status:
        pytest.fail(f"[{path}] status drift before key check: {w_status} vs {f_status}")
    if int(w_status.split()[0]) >= 400:
        return
    w_keys = sorted(w_body.keys()) if isinstance(w_body, dict) else []
    f_keys = sorted(f_body.keys()) if isinstance(f_body, dict) else []
    assert w_keys == f_keys, (
        f"[{path}] success body schema drift:\n"
        f"  WSGI keys={w_keys}\n"
        f"  FastAPI keys={f_keys}\n"
        f"  WSGI extra: {sorted(set(w_keys) - set(f_keys))}\n"
        f"  FastAPI extra: {sorted(set(f_keys) - set(w_keys))}"
    )


GET_NO_PARAM_ENDPOINTS = [
    "/api/branch-snapshot",
    "/api/chapter-bundle",
    "/api/chapter-jobs",
    "/api/chapter-qa-context",
    "/api/chapter-source",
    "/api/run-snapshot",
    "/api/review-clusters",
    "/api/review-cluster-summary",
]

GET_NO_PARAM_OK_ENDPOINTS = [
    "/api/library",
]

GET_WITH_REQUIRED = [
    ("/api/branch-exports", "?run_id=fake&branch_id=fake"),
    ("/api/pipeline/runs", "?branch_id=fake"),
]

POST_MISSING_BODY_ENDPOINTS = [
    "/api/import",
    "/api/recovery",
    "/api/pipeline/start-range",
    "/api/review-cluster-update",
    "/api/ask-branch",
    "/api/ask-branch-stream",
    "/api/search-branch",
]


@pytest.mark.parametrize("path", GET_NO_PARAM_ENDPOINTS)
def test_get_missing_params_parity(fastapi_client, path):
    """Endpoints that require query params should reject identically on both sides."""
    w = _wsgi_call("GET", path)
    f = _fastapi_call(fastapi_client, "GET", path)
    _assert_status_and_error_shape(w, f, path)


@pytest.mark.parametrize("path", GET_NO_PARAM_OK_ENDPOINTS)
def test_get_no_required_params_parity(fastapi_client, path):
    """Endpoints with no required params should return same shape on both sides."""
    w = _wsgi_call("GET", path)
    f = _fastapi_call(fastapi_client, "GET", path)
    _assert_same_keys(w, f, path)


@pytest.mark.parametrize("path,query", GET_WITH_REQUIRED)
def test_get_with_required_parity(fastapi_client, path, query):
    """Endpoints called with all required params (even if data is empty/fake)."""
    w = _wsgi_call("GET", path + query)
    f = _fastapi_call(fastapi_client, "GET", path + query)
    w_code = int(w[0].split()[0])
    f_code = int(f[0].split()[0])
    assert w_code == f_code, f"[{path}] status drift: WSGI={w[0]} FastAPI={f[0]}"


@pytest.mark.parametrize("path", POST_MISSING_BODY_ENDPOINTS)
def test_post_missing_body_parity(fastapi_client, path):
    """POST endpoints with empty body should reject identically."""
    body = b"{}"
    w = _wsgi_call("POST", path, body)
    f = _fastapi_call(fastapi_client, "POST", path, body)
    _assert_status_and_error_shape(w, f, path)
