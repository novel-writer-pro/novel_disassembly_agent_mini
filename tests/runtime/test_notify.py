from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest

from novel_analyzer.runtime.notify import notify_pipeline_complete


def test_no_op_when_env_unset(monkeypatch):
    monkeypatch.delenv("N8N_WEBHOOK_PIPELINE_COMPLETE_URL", raising=False)
    with patch("httpx.Client") as mock_client:
        notify_pipeline_complete(branch_id="b1", status="success")
    mock_client.assert_not_called()


def test_no_op_when_env_empty(monkeypatch):
    monkeypatch.setenv("N8N_WEBHOOK_PIPELINE_COMPLETE_URL", "")
    with patch("httpx.Client") as mock_client:
        notify_pipeline_complete(branch_id="b1", status="success")
    mock_client.assert_not_called()


def test_posts_when_env_set(monkeypatch):
    monkeypatch.setenv("N8N_WEBHOOK_PIPELINE_COMPLETE_URL", "http://fake-n8n/webhook/x")
    posted = {}

    class _MockResp:
        status_code = 200

        def raise_for_status(self):
            pass

    class _MockClient:
        def __init__(self, *a, **kw):
            posted["timeout"] = kw.get("timeout")

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def post(self, url, json=None):
            posted["url"] = url
            posted["json"] = json
            return _MockResp()

    with patch("novel_analyzer.runtime.notify.httpx.Client", _MockClient):
        notify_pipeline_complete(
            branch_id="b1",
            status="success",
            user_id="alice",
            metadata={"chapter_count": 5},
        )

    assert posted["url"] == "http://fake-n8n/webhook/x"
    assert posted["json"]["branch_id"] == "b1"
    assert posted["json"]["status"] == "success"
    assert posted["json"]["user_id"] == "alice"
    assert posted["json"]["metadata"] == {"chapter_count": 5}
    assert posted["timeout"] == 2.0


def test_swallows_timeout(monkeypatch, caplog):
    monkeypatch.setenv("N8N_WEBHOOK_PIPELINE_COMPLETE_URL", "http://fake-n8n/webhook/x")

    class _SlowClient:
        def __init__(self, *a, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def post(self, *a, **kw):
            raise httpx.TimeoutException("slow")

    with patch("novel_analyzer.runtime.notify.httpx.Client", _SlowClient):
        notify_pipeline_complete(branch_id="b1", status="success")

    assert any("timed out" in r.message for r in caplog.records)


def test_swallows_connection_error(monkeypatch, caplog):
    monkeypatch.setenv("N8N_WEBHOOK_PIPELINE_COMPLETE_URL", "http://fake-n8n/webhook/x")

    class _DeadClient:
        def __init__(self, *a, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def post(self, *a, **kw):
            raise httpx.ConnectError("nope")

    with patch("novel_analyzer.runtime.notify.httpx.Client", _DeadClient):
        notify_pipeline_complete(branch_id="b1", status="success")

    assert any("HTTP error" in r.message for r in caplog.records)


def test_swallows_unexpected_exception(monkeypatch, caplog):
    monkeypatch.setenv("N8N_WEBHOOK_PIPELINE_COMPLETE_URL", "http://fake-n8n/webhook/x")

    class _BrokenClient:
        def __init__(self, *a, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def post(self, *a, **kw):
            raise RuntimeError("unexpected")

    with patch("novel_analyzer.runtime.notify.httpx.Client", _BrokenClient):
        notify_pipeline_complete(branch_id="b1", status="success")

    assert any("unexpected error" in r.message for r in caplog.records)
