"""Request-level audit trail middleware."""
from __future__ import annotations

from typing import Any

from jose import JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.config import settings
from app.database import SessionLocal
from app.services.audit_service import log_audit_event


MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class AuditTrailMiddleware(BaseHTTPMiddleware):
    """Persist audit trail records for mutating API traffic.

    Route-specific business audit logs still exist. This middleware provides a
    baseline audit record for every state-changing API request.
    """

    def _extract_user_id(self, request: Request) -> str | None:
        token = None
        auth_header = (request.headers.get("Authorization") or "").strip()
        if auth_header.lower().startswith("bearer "):
            token = auth_header.split(" ", 1)[1].strip()
        if not token:
            token = request.cookies.get("access_token")
        if not token:
            return None

        try:
            payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
            user_id = payload.get("sub")
            return str(user_id) if user_id else None
        except JWTError:
            return None

    def _resource_from_path(self, path: str) -> str:
        cleaned = path.strip("/")
        if not cleaned:
            return "root"
        parts = cleaned.split("/")
        if len(parts) >= 3 and parts[0] == "api" and parts[1] in {"v1", "v2"}:
            return parts[2]
        return parts[0]

    def _should_log(self, request: Request) -> bool:
        if request.method.upper() not in MUTATING_METHODS:
            return False
        path = request.url.path
        if not path.startswith("/api/"):
            return False
        # Auth endpoints already emit explicit audit events with richer details.
        if path.startswith("/api/v1/auth/") or path.startswith("/api/v2/auth/"):
            return False
        return True

    def _log_event(self, request: Request, response: Response, *, error: str | None = None) -> None:
        try:
            db = SessionLocal()
            try:
                user_id = self._extract_user_id(request)
                detail_payload: dict[str, Any] = {
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "request_id": getattr(request.state, "request_id", None),
                }
                if error:
                    detail_payload["error"] = error

                log_audit_event(
                    db,
                    action=f"{request.method}:{request.url.path}",
                    resource_type=self._resource_from_path(request.url.path),
                    status="success" if response.status_code < 400 else "failure",
                    user_id=user_id,
                    details=detail_payload,
                    ip_address=request.client.host if request.client else None,
                )
                db.commit()
            finally:
                db.close()
        except Exception:
            # Audit trail is best-effort and should never break request handling.
            return

    async def dispatch(self, request: Request, call_next) -> Response:
        if not self._should_log(request):
            return await call_next(request)

        try:
            response = await call_next(request)
        except Exception as exc:
            # Re-raise after logging a synthetic server-error audit entry.
            synthetic_response = Response(status_code=500)
            self._log_event(request, synthetic_response, error=str(exc))
            raise

        self._log_event(request, response)
        return response
