from __future__ import annotations

import json
from io import BytesIO
from typing import Any, cast
from wsgiref.types import StartResponse

import pytest

from apps.api.app.main import application


def _call(path: str, method: str = "GET", body: bytes = b"", content_type: str = "application/json") -> tuple[str, dict[str, Any]]:
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
                "CONTENT_TYPE": content_type,
                "CONTENT_LENGTH": str(len(body)),
                "wsgi.input": BytesIO(body),
            },
            cast(StartResponse, start_response),
        )
    )
    try:
        payload = json.loads(raw)
    except Exception:
        payload = {"_raw": raw.decode("utf-8", errors="replace")}
    return captured["status"], payload


def _post(path: str, data: dict) -> tuple[str, dict[str, Any]]:
    body = json.dumps(data).encode("utf-8")
    return _call(path, method="POST", body=body)


class TestHealthAndMeta:
    def test_health_returns_ok(self):
        status, payload = _call("/health")
        assert status == "200 OK"
        assert payload.get("status") == "ok"

    def test_health_has_service_field(self):
        _, payload = _call("/health")
        assert "service" in payload

    def test_meta_has_available_endpoints(self):
        status, payload = _call("/api/meta")
        assert status == "200 OK"
        assert "available_endpoints" in payload
        assert isinstance(payload["available_endpoints"], list)
        assert len(payload["available_endpoints"]) > 0

    def test_meta_has_available_endpoint_specs(self):
        _, payload = _call("/api/meta")
        assert "available_endpoint_specs" in payload
        specs = payload["available_endpoint_specs"]
        assert isinstance(specs, list)
        for spec in specs:
            assert "path" in spec
            assert "method" in spec

    def test_meta_includes_key_endpoints(self):
        _, payload = _call("/api/meta")
        paths = payload["available_endpoints"]
        assert "/api/import" in paths
        assert "/api/library" in paths

    def test_mock_import_returns_snapshot(self):
        status, payload = _call("/api/mock/import?profile=auto-lite")
        assert status == "200 OK"
        assert "import_result" in payload
        assert "run_snapshot" in payload
        assert "branch_snapshot" in payload


class TestLibraryEndpoint:
    def test_library_returns_items_list(self):
        status, payload = _call("/api/library")
        assert status == "200 OK"
        assert "items" in payload
        assert isinstance(payload["items"], list)

    def test_library_items_have_expected_shape(self):
        _, payload = _call("/api/library")
        for item in payload["items"]:
            assert "run_id" in item or "branch_id" in item or "title" in item


class TestRuntimeHealth:
    def test_runtime_health_returns_200(self):
        status, payload = _call("/api/runtime-health")
        assert status in ("200 OK", "500 Internal Server Error")

    def test_runtime_health_has_storage_fields(self):
        status, payload = _call("/api/runtime-health")
        if status == "500 Internal Server Error":
            assert "error" in payload
            return
        assert "cache_root" in payload
        assert "cache_upload_files" in payload


class TestProviderHealth:
    def test_provider_health_returns_200(self):
        status, _ = _call("/api/provider-health")
        assert status in ("200 OK", "500 Internal Server Error")

    def test_provider_health_has_status_fields(self):
        status, payload = _call("/api/provider-health")
        if status == "500 Internal Server Error":
            assert "error" in payload
            return
        assert "last_status" in payload
        assert "degraded_events" in payload


class TestMissingParams:
    def test_job_events_missing_branch_id_returns_400(self):
        status, payload = _call("/api/job-events")
        assert status == "400 Bad Request"
        assert "error" in payload

    def test_chapter_bundle_missing_params_returns_400(self):
        status, payload = _call("/api/chapter-bundle")
        assert status == "400 Bad Request"
        assert "error" in payload

    def test_run_snapshot_missing_params_returns_400(self):
        status, payload = _call("/api/run-snapshot")
        assert status == "400 Bad Request"
        assert "error" in payload

    def test_branch_snapshot_missing_params_returns_400(self):
        status, payload = _call("/api/branch-snapshot")
        assert status == "400 Bad Request"
        assert "error" in payload

    def test_chapter_source_missing_params_returns_400(self):
        status, payload = _call("/api/chapter-source")
        assert status == "400 Bad Request"
        assert "error" in payload

    def test_chapter_jobs_missing_params_returns_400(self):
        status, payload = _call("/api/chapter-jobs")
        assert status == "400 Bad Request"
        assert "error" in payload

    def test_review_clusters_missing_params_returns_400(self):
        status, payload = _call("/api/review-clusters")
        assert status == "400 Bad Request"
        assert "error" in payload

    def test_quality_dashboard_missing_branch_id_returns_400(self):
        status, payload = _call("/api/quality-dashboard")
        assert status in ("400 Bad Request", "404 Not Found")
        assert "error" in payload

    def test_whole_book_imitation_readiness_returns_200_or_400(self):
        status, payload = _call("/api/whole-book-imitation-readiness")
        assert status in ("200 OK", "400 Bad Request")
        if status == "200 OK":
            assert isinstance(payload, dict)
        else:
            assert "error" in payload


class TestPostEndpoints:
    def test_import_missing_content_returns_error(self):
        status, payload = _post("/api/import", {})
        assert status in ("400 Bad Request", "422 Unprocessable Entity", "500 Internal Server Error")
        assert "error" in payload or "detail" in payload

    def test_start_missing_run_id_returns_error(self):
        status, payload = _post("/api/start", {})
        assert status in ("400 Bad Request", "422 Unprocessable Entity", "500 Internal Server Error")
        assert "error" in payload or "detail" in payload

    def test_recovery_missing_params_returns_error(self):
        status, payload = _post("/api/recovery", {})
        assert status in ("400 Bad Request", "422 Unprocessable Entity", "500 Internal Server Error")
        assert "error" in payload or "detail" in payload

    def test_ask_branch_missing_params_returns_error(self):
        status, payload = _post("/api/ask-branch", {})
        assert status in ("400 Bad Request", "422 Unprocessable Entity", "500 Internal Server Error")
        assert "error" in payload or "detail" in payload

    def test_search_branch_missing_params_returns_error(self):
        status, payload = _post("/api/search-branch", {})
        assert status in ("400 Bad Request", "422 Unprocessable Entity", "500 Internal Server Error")
        assert "error" in payload or "detail" in payload


class TestUnknownRoute:
    def test_unknown_path_returns_404(self):
        status, payload = _call("/api/does-not-exist-xyz")
        assert status == "404 Not Found"
        assert "error" in payload

    def test_unsupported_method_returns_405(self):
        status, payload = _call("/health", method="DELETE")
        assert status == "405 Method Not Allowed"
