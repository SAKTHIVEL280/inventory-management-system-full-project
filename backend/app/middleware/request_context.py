"""Request context middleware utilities."""
from __future__ import annotations

import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach a request ID for traceability across logs and responses."""

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = (request.headers.get("X-Request-ID") or "").strip() or str(uuid.uuid4())
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers.setdefault("X-Request-ID", request_id)
        return response
