"""API version compatibility middleware."""
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class ApiVersionCompatibilityMiddleware(BaseHTTPMiddleware):
    """Support /api/v2 by transparently routing to /api/v1 handlers."""

    async def dispatch(self, request: Request, call_next) -> Response:
        original_path = request.scope.get("path", "")
        requested_version = "v1"

        if original_path in {"/api/v2", "/api/v2/"}:
            requested_version = "v2"
        elif original_path.startswith("/api/v2/"):
            request.scope["path"] = "/api/v1" + original_path[len("/api/v2") :]
            requested_version = "v2"

        response = await call_next(request)
        response.headers.setdefault("X-API-Version", requested_version)
        if requested_version == "v2":
            response.headers.setdefault("X-API-Compatible-With", "v1")
        return response
