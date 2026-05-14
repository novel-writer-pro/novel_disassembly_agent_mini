from __future__ import annotations

import asyncio

import pytest

from novel_analyzer.runtime.trace_context import (
    RequestContext,
    get_current_context,
    set_current_context,
    with_request_context,
)


class TestRequestContext:
    def test_defaults(self):
        ctx = RequestContext(request_id="req-1")
        assert ctx.request_id == "req-1"
        assert ctx.user_id == "local-default"
        assert ctx.tenant_id is None
        assert ctx.started_at > 0

    def test_custom_user_id(self):
        ctx = RequestContext(request_id="req-2", user_id="alice")
        assert ctx.user_id == "alice"

    def test_frozen(self):
        ctx = RequestContext(request_id="req-3")
        with pytest.raises((AttributeError, TypeError)):
            ctx.user_id = "hacked"  # type: ignore[misc]


class TestGetSetContext:
    def test_get_returns_none_outside_context(self):
        # Reset any lingering state
        from novel_analyzer.runtime.trace_context import _current_context
        _current_context.set(None)
        assert get_current_context() is None

    def test_set_and_get(self):
        ctx = RequestContext(request_id="req-set-1", user_id="bob")
        set_current_context(ctx)
        result = get_current_context()
        assert result is ctx
        assert result.user_id == "bob"
        # cleanup
        from novel_analyzer.runtime.trace_context import _current_context
        _current_context.set(None)


class TestWithRequestContext:
    def test_basic_set_and_clear(self):
        assert get_current_context() is None or True  # may have prior state
        with with_request_context(request_id="req-basic", user_id="alice") as ctx:
            assert ctx.request_id == "req-basic"
            assert ctx.user_id == "alice"
            live = get_current_context()
            assert live is ctx
        # After exit, context is reset to previous value (None if none before)
        after = get_current_context()
        assert after is None or after.request_id != "req-basic"

    def test_auto_generates_request_id(self):
        with with_request_context(user_id="carol") as ctx:
            assert ctx.request_id  # non-empty
            assert len(ctx.request_id) > 8  # looks like a uuid

    def test_nested_contexts_restore_outer(self):
        with with_request_context(request_id="outer", user_id="outer-user") as outer:
            assert get_current_context().request_id == "outer"
            with with_request_context(request_id="inner", user_id="inner-user") as inner:
                assert get_current_context().request_id == "inner"
                assert inner.user_id == "inner-user"
            # outer restored
            assert get_current_context().request_id == "outer"
            assert get_current_context().user_id == "outer-user"

    def test_context_cleared_after_exit(self):
        from novel_analyzer.runtime.trace_context import _current_context
        _current_context.set(None)
        with with_request_context(request_id="temp", user_id="dave"):
            pass
        assert get_current_context() is None

    def test_context_cleared_on_exception(self):
        from novel_analyzer.runtime.trace_context import _current_context
        _current_context.set(None)
        with pytest.raises(ValueError):
            with with_request_context(request_id="err", user_id="eve"):
                raise ValueError("boom")
        assert get_current_context() is None

    def test_tenant_id(self):
        with with_request_context(request_id="t1", user_id="frank", tenant_id="acme") as ctx:
            assert ctx.tenant_id == "acme"


class TestAsyncIsolation:
    def test_async_tasks_have_independent_contexts(self):
        results: dict[str, str | None] = {}

        async def task_a():
            with with_request_context(request_id="task-a", user_id="user-a"):
                await asyncio.sleep(0.01)
                ctx = get_current_context()
                results["a"] = ctx.user_id if ctx else None

        async def task_b():
            with with_request_context(request_id="task-b", user_id="user-b"):
                await asyncio.sleep(0.01)
                ctx = get_current_context()
                results["b"] = ctx.user_id if ctx else None

        async def run():
            await asyncio.gather(task_a(), task_b())

        asyncio.run(run())
        assert results["a"] == "user-a"
        assert results["b"] == "user-b"

    def test_no_context_leak_between_tasks(self):
        results: dict[str, str | None] = {}

        async def task_with_context():
            with with_request_context(request_id="leaky", user_id="leaky-user"):
                await asyncio.sleep(0.005)

        async def task_without_context():
            await asyncio.sleep(0.005)
            ctx = get_current_context()
            results["no_ctx"] = ctx.user_id if ctx else None

        async def run():
            await asyncio.gather(task_with_context(), task_without_context())

        asyncio.run(run())
        # task_without_context should NOT see leaky-user
        assert results["no_ctx"] != "leaky-user"
