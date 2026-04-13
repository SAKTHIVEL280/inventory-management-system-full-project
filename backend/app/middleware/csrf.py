"""CSRF protection middleware for cookie-authenticated browser sessions."""
from __future__ import annotations

from hmac import compare_digest
from typing import Iterable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


class CSRFMiddleware(BaseHTTPMiddleware):
    """Validate CSRF header against CSRF cookie for mutating cookie-auth requests."""

    def __init__(
        self,
        app,
        *,
        cookie_name: str,
        header_name: str,
        exempt_paths: Iterable[str] | None = None,
    ) -> None:
        super().__init__(app)
        self.cookie_name = cookie_name
        self.header_name = header_name
        self.exempt_paths = tuple((path or "").strip() for path in (exempt_paths or []))

    def _is_exempt_path(self, path: str) -> bool:
        for exempt in self.exempt_paths:
            if not exempt:
                continue
            if exempt.endswith("*") and path.startswith(exempt[:-1]):
                return True
            if path == exempt:
                return True
        return False

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method in SAFE_METHODS:
            return await call_next(request)

        path = request.url.path
        if self._is_exempt_path(path):
            return await call_next(request)

        auth_header = (request.headers.get("Authorization") or "").strip().lower()
        if auth_header.startswith("bearer "):
            return await call_next(request)

        # Only enforce CSRF when session cookies are used.
        if not request.cookies.get("access_token"):
            return await call_next(request)

        cookie_token = request.cookies.get(self.cookie_name)
        header_token = request.headers.get(self.header_name)

        if not cookie_token or not header_token or not compare_digest(cookie_token, header_token):
            return JSONResponse(status_code=403, content={"detail": "CSRF validation failed"})

        return await call_next(request)
