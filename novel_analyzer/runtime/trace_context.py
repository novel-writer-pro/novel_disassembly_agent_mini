"""Request-scoped trace context using contextvars.

Provides a lightweight, async-safe way to propagate request identity
(request_id, user_id) through the call stack without threading issues.

Usage::

    with with_request_context(request_id="req-123", user_id="alice") as ctx:
        # anywhere in the call stack:
        ctx = get_current_context()
        print(ctx.user_id)  # "alice"

FastAPI middleware integration (T8-T11)::

    @app.middleware("http")
    async def trace_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-Id", str(uuid4()))
        user_id = request.headers.get("X-User-Id", "local-default")
        with with_request_context(request_id=request_id, user_id=user_id):
            return await call_next(request)
"""

from __future__ import annotations

import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Generator


@dataclass(frozen=True)
class RequestContext:
    """Immutable per-request identity carrier."""

    request_id: str
    user_id: str = "local-default"
    tenant_id: str | None = None
    started_at: float = field(default_factory=time.monotonic)


_current_context: ContextVar[RequestContext | None] = ContextVar(
    "_current_context", default=None
)


def get_current_context() -> RequestContext | None:
    """Return the active RequestContext, or None if outside a request."""
    return _current_context.get()


def set_current_context(ctx: RequestContext) -> None:
    """Set the active RequestContext (low-level; prefer with_request_context)."""
    _current_context.set(ctx)


@contextmanager
def with_request_context(
    request_id: str | None = None,
    user_id: str = "local-default",
    tenant_id: str | None = None,
) -> Generator[RequestContext, None, None]:
    """Context manager that sets a RequestContext for the duration of the block.

    Automatically resets to the previous value on exit, making it safe to nest.

    Args:
        request_id: Unique request identifier. Auto-generated if not provided.
        user_id: Caller identity. Defaults to "local-default" for dev.
        tenant_id: Optional tenant scope (reserved for future multi-tenancy).

    Yields:
        The active RequestContext.
    """
    ctx = RequestContext(
        request_id=request_id or str(uuid.uuid4()),
        user_id=user_id,
        tenant_id=tenant_id,
    )
    token = _current_context.set(ctx)
    try:
        yield ctx
    finally:
        _current_context.reset(token)
