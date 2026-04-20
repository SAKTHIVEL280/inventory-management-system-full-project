"""Request context middleware utilities."""
from __future__ import annotations

from contextvars import ContextVar
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)
request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach a request ID for traceability across logs and responses."""

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = (request.headers.get("X-Request-ID") or "").strip() or str(uuid.uuid4())
        request_correlation_id = (request.headers.get("X-Correlation-ID") or "").strip() or request_id
        request_id_ctx.set(request_id)
        correlation_id.set(request_correlation_id)
        request.state.request_id = request_id
        request.state.correlation_id = request_correlation_id

        response = await call_next(request)
        response.headers.setdefault("X-Request-ID", request_id)
        response.headers.setdefault("X-Correlation-ID", request_correlation_id)
        return response
