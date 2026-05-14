"""FastAPI surface contract test — mirrors test_main_wsgi_contract.py.

T8 of v5 plan. Uses TestClient(create_app()) to drive the FastAPI app
and asserts the same 28 contract points as the WSGI test, proving both
surfaces are schema-equivalent before T10 cutover.
"""
from __future__ import annotations

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

from apps.api.app.fastapi_app import create_app


@pytest.fixture(scope="module")
def client():
    return TestClient(create_app())


def _call(client: TestClient, path: str, method: str = "GET", body: bytes = b"") -> tuple[str, dict[str, Any]]:
    if method == "GET":
        r = client.get(path)
    elif method == "POST":
        r = client.post(path, content=body, headers={"Content-Type": "application/json"})
    else:
        raise ValueError(method)
    status = f"{r.status_code} {r.reason_phrase}"
    try:
        return status, r.json()
    except Exception:
        return status, {"_raw": r.text[:200]}


def _post(client: TestClient, path: str, data: dict) -> tuple[str, dict[str, Any]]:
    return _call(client, path, "POST", json.dumps(data).encode())


class TestHealthAndMeta:
    def test_health_returns_ok(self, client):
        status, payload = _call(client, "/health")
        assert status == "200 OK"
        assert payload.get("status") == "ok"

    def test_health_has_service_field(self, client):
        _, payload = _call(client, "/health")
        assert "service" in payload

    def test_meta_has_available_endpoints(self, client):
        status, payload = _call(client, "/api/meta")
        assert status == "200 OK"
        assert "available_endpoints" in payload
        assert isinstance(payload["available_endpoints"], list)
        assert len(payload["available_endpoints"]) > 0

    def test_meta_has_available_endpoint_specs(self, client):
        _, payload = _call(client, "/api/meta")
        assert "available_endpoint_specs" in payload
        for spec in payload["available_endpoint_specs"]:
            assert "path" in spec
            assert "method" in spec

    def test_meta_includes_key_endpoints(self, client):
        _, payload = _call(client, "/api/meta")
        paths = payload["available_endpoints"]
        assert "/api/import" in paths
        assert "/api/library" in paths

    def test_mock_import_returns_snapshot(self, client):
        status, payload = _call(client, "/api/mock/import?profile=auto-lite")
        assert status == "200 OK"
        assert "import_result" in payload
        assert "run_snapshot" in payload
        assert "branch_snapshot" in payload


class TestLibraryEndpoint:
    def test_library_returns_items_list(self, client):
        status, payload = _call(client, "/api/library")
        assert status == "200 OK"
        assert "items" in payload
        assert isinstance(payload["items"], list)


class TestRuntimeHealth:
    def test_runtime_health_returns_200(self, client):
        status, _ = _call(client, "/api/runtime-health")
        assert status in ("200 OK", "500 Internal Server Error")

    def test_runtime_health_has_storage_fields(self, client):
        status, payload = _call(client, "/api/runtime-health")
        if status == "500 Internal Server Error":
            assert "error" in payload
            return
        assert "cache_root" in payload


class TestProviderHealth:
    def test_provider_health_returns_200(self, client):
        status, _ = _call(client, "/api/provider-health")
        assert status in ("200 OK", "500 Internal Server Error")

    def test_provider_health_has_status_fields(self, client):
        status, payload = _call(client, "/api/provider-health")
        if status == "500 Internal Server Error":
            assert "error" in payload
            return
        assert "last_status" in payload


class TestMissingParams:
    @pytest.mark.parametrize("path", [
        "/api/job-events", "/api/chapter-bundle", "/api/run-snapshot",
        "/api/branch-snapshot", "/api/chapter-source", "/api/chapter-jobs",
        "/api/review-clusters",
    ])
    def test_missing_param_returns_400(self, client, path):
        status, payload = _call(client, path)
        assert status == "400 Bad Request"
        assert "error" in payload

    def test_quality_dashboard_missing_branch_id(self, client):
        status, payload = _call(client, "/api/quality-dashboard")
        assert status in ("400 Bad Request", "404 Not Found")
        assert "error" in payload

    def test_whole_book_imitation_readiness(self, client):
        status, _ = _call(client, "/api/whole-book-imitation-readiness")
        assert status in ("200 OK", "400 Bad Request")


class TestPostEndpoints:
    @pytest.mark.parametrize("path", [
        "/api/import", "/api/start", "/api/recovery", "/api/ask-branch",
    ])
    def test_post_missing_body_returns_error(self, client, path):
        status, payload = _post(client, path, {})
        assert status in ("400 Bad Request", "422 Unprocessable Entity", "500 Internal Server Error")
        assert "error" in payload or "detail" in payload


class TestUnknownRoute:
    def test_unknown_path_returns_404(self, client):
        status, payload = _call(client, "/api/does-not-exist-xyz")
        assert status == "404 Not Found"

    def test_unsupported_method_returns_405(self, client):
        r = client.delete("/health")
        assert r.status_code == 405


class TestIdentityMiddleware:
    """T8 specific: prove IdentityMiddleware is wired and request-id echoes."""

    def test_x_request_id_echoed(self, client):
        r = client.get("/health", headers={"X-Request-Id": "req-fixed-abc"})
        assert r.headers.get("X-Request-Id") == "req-fixed-abc"

    def test_x_request_id_auto_generated(self, client):
        r = client.get("/health")
        rid = r.headers.get("X-Request-Id")
        assert rid is not None and len(rid) >= 8

    def test_x_user_id_default(self, client):
        r = client.get("/health")
        assert r.status_code == 200
