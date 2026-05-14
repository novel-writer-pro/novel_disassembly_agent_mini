from __future__ import annotations

import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from novel_analyzer.runtime.trace_context import (
    get_current_context,
    with_request_context,
)


class IdentityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        user_id = (request.headers.get("X-User-Id") or "local-default").strip() or "local-default"
        request_id = (request.headers.get("X-Request-Id") or str(uuid.uuid4())).strip()

        with with_request_context(request_id=request_id, user_id=user_id) as ctx:
            response: Response = await call_next(request)
            response.headers["X-Request-Id"] = ctx.request_id
            return response


def get_current_user() -> str:
    ctx = get_current_context()
    return ctx.user_id if ctx else "local-default"
