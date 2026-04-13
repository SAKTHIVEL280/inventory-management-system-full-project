"""HTTPS enforcement middleware."""
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response


class HTTPSRedirectMiddleware(BaseHTTPMiddleware):
    """Redirect insecure HTTP traffic to HTTPS in production deployments."""

    async def dispatch(self, request: Request, call_next) -> Response:
        forwarded_proto = (request.headers.get("X-Forwarded-Proto") or "").strip().lower()
        if request.url.scheme == "https" or forwarded_proto == "https":
            return await call_next(request)

        target_url = request.url.replace(scheme="https")
        return RedirectResponse(url=str(target_url), status_code=307)
