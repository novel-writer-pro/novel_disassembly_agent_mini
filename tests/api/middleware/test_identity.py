from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.app.middleware import IdentityMiddleware, get_current_user
from novel_analyzer.runtime.trace_context import get_current_context


@pytest.fixture
def client():
    app = FastAPI()
    app.add_middleware(IdentityMiddleware)

    @app.get("/__whoami")
    def whoami():
        ctx = get_current_context()
        return {
            "user_id": get_current_user(),
            "request_id": ctx.request_id if ctx else None,
        }

    return TestClient(app)


def test_x_user_id_header_propagates(client):
    r = client.get("/__whoami", headers={"X-User-Id": "alice"})
    assert r.status_code == 200
    assert r.json()["user_id"] == "alice"


def test_missing_header_falls_back_to_local_default(client):
    r = client.get("/__whoami")
    assert r.status_code == 200
    assert r.json()["user_id"] == "local-default"


def test_empty_header_falls_back(client):
    r = client.get("/__whoami", headers={"X-User-Id": "  "})
    assert r.status_code == 200
    assert r.json()["user_id"] == "local-default"


def test_request_id_echoed_in_response_header(client):
    r = client.get("/__whoami", headers={"X-Request-Id": "req-fixed-123"})
    assert r.headers["X-Request-Id"] == "req-fixed-123"
    assert r.json()["request_id"] == "req-fixed-123"


def test_request_id_auto_generated_when_missing(client):
    r = client.get("/__whoami")
    assert "X-Request-Id" in r.headers
    assert len(r.headers["X-Request-Id"]) >= 8


def test_get_current_user_returns_default_outside_request():
    assert get_current_user() == "local-default"
