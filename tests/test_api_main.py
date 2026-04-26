from io import BytesIO
from types import TracebackType
from typing import Any, cast
from wsgiref.types import StartResponse

from apps.api.app.main import application


def _call(path: str) -> tuple[str, bytes]:
    captured: dict[str, Any] = {}
    path_info, _, query = path.partition("?")

    def start_response(
        status: str,
        headers: list[tuple[str, str]],
        exc_info:
        tuple[type[BaseException], BaseException, TracebackType]
        | tuple[None, None, None]
        | None = None,
    ) -> object:
        _ = exc_info
        captured["status"] = status
        captured["headers"] = headers
        return lambda chunk: None

    start = cast(StartResponse, start_response)
    body = b"".join(
        application(
            {
                "REQUEST_METHOD": "GET",
                "PATH_INFO": path_info,
                "QUERY_STRING": query,
                "wsgi.input": BytesIO(),
            },
            start,
        )
    )
    return captured["status"], body


def test_health_endpoint_returns_ok() -> None:
    status, body = _call("/health")
    assert status == "200 OK"
    assert b'"status": "ok"' in body


def test_meta_endpoint_lists_available_routes() -> None:
    status, body = _call("/api/meta")
    assert status == "200 OK"
    assert b"/api/mock/import" in body


def test_mock_import_endpoint_uses_profile_query() -> None:
    status, body = _call("/api/mock/import?profile=manual")
    assert status == "200 OK"
    assert b'"pipeline_profile": "manual"' in body


def test_run_snapshot_requires_query_params() -> None:
    status, body = _call("/api/run-snapshot")
    assert status == "400 Bad Request"
    assert b"missing query parameter" in body


def test_chapter_bundle_requires_query_params() -> None:
    status, body = _call("/api/chapter-bundle")
    assert status == "400 Bad Request"
    assert b"missing query parameter" in body


def test_chapter_qa_context_requires_query_params() -> None:
    status, body = _call("/api/chapter-qa-context")
    assert status == "400 Bad Request"
    assert b"missing query parameter" in body


def test_import_endpoint_requires_uploaded_file() -> None:
    captured: dict[str, Any] = {}

    def start_response(
        status: str,
        headers: list[tuple[str, str]],
        exc_info:
        tuple[type[BaseException], BaseException, TracebackType]
        | tuple[None, None, None]
        | None = None,
    ) -> object:
        _ = exc_info
        captured["status"] = status
        captured["headers"] = headers
        return lambda chunk: None

    body = b"".join(
        application(
            {
                "REQUEST_METHOD": "POST",
                "PATH_INFO": "/api/import",
                "CONTENT_TYPE": "multipart/form-data; boundary=test",
                "CONTENT_LENGTH": "0",
                "QUERY_STRING": "",
                "wsgi.input": BytesIO(),
            },
            cast(StartResponse, start_response),
        )
    )
    assert captured["status"] == "400 Bad Request"
    assert b"missing uploaded file" in body


def test_recovery_endpoint_requires_action_fields() -> None:
    captured: dict[str, Any] = {}

    def start_response(
        status: str,
        headers: list[tuple[str, str]],
        exc_info:
        tuple[type[BaseException], BaseException, TracebackType]
        | tuple[None, None, None]
        | None = None,
    ) -> object:
        _ = exc_info
        captured["status"] = status
        captured["headers"] = headers
        return lambda chunk: None

    payload = b"{}"
    body = b"".join(
        application(
            {
                "REQUEST_METHOD": "POST",
                "PATH_INFO": "/api/recovery",
                "CONTENT_TYPE": "application/json",
                "CONTENT_LENGTH": str(len(payload)),
                "QUERY_STRING": "",
                "wsgi.input": BytesIO(payload),
            },
            cast(StartResponse, start_response),
        )
    )
    assert captured["status"] == "400 Bad Request"
    assert b"run_id, branch_id and action are required" in body
