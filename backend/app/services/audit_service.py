"""Audit logging utilities."""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_SENSITIVE_TOKENS = {
    "password",
    "passwd",
    "token",
    "secret",
    "authorization",
    "cookie",
    "session",
    "api_key",
    "apikey",
}
_RETENTION_CHECK_INTERVAL_SECONDS = 3600
_last_retention_check_at = 0.0


def _ensure_audit_logs_table(db: Session) -> None:
    db.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS audit_logs (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID REFERENCES users(id),
                username VARCHAR(255),
                action VARCHAR(120) NOT NULL,
                action_type VARCHAR(40) NOT NULL,
                module_name VARCHAR(80) NOT NULL,
                resource_type VARCHAR(80),
                resource_id UUID,
                record_reference VARCHAR(255),
                description TEXT,
                status VARCHAR(20) NOT NULL,
                details JSONB NOT NULL DEFAULT '{}'::jsonb,
                ip_address VARCHAR(64),
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
    )
    db.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS username VARCHAR(255)"))
    db.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS action_type VARCHAR(40)"))
    db.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS module_name VARCHAR(80)"))
    db.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS record_reference VARCHAR(255)"))
    db.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS description TEXT"))
    db.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()"))
    db.execute(text("CREATE INDEX IF NOT EXISTS ix_audit_logs_created_at ON audit_logs (created_at)"))
    db.execute(text("CREATE INDEX IF NOT EXISTS ix_audit_logs_user_id ON audit_logs (user_id)"))
    db.execute(text("CREATE INDEX IF NOT EXISTS ix_audit_logs_module_name ON audit_logs (module_name)"))
    db.execute(text("CREATE INDEX IF NOT EXISTS ix_audit_logs_action_type ON audit_logs (action_type)"))
    db.execute(text("CREATE INDEX IF NOT EXISTS ix_audit_logs_record_reference ON audit_logs (record_reference)"))


def _is_sensitive_key(key: str) -> bool:
    token = (key or "").strip().lower()
    return any(fragment in token for fragment in _SENSITIVE_TOKENS)


def _sanitize_details(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for k, v in value.items():
            key = str(k)
            if _is_sensitive_key(key):
                sanitized[key] = "***"
            else:
                sanitized[key] = _sanitize_details(v)
        return sanitized
    if isinstance(value, list):
        return [_sanitize_details(v) for v in value]
    return value


def _derive_action_type(action: str) -> str:
    token = (action or "").strip()
    if not token:
        return "UNKNOWN"
    return token.split(":", 1)[0].strip().upper()


def _derive_record_reference(resource_id: UUID | str | None, details: dict[str, Any]) -> str | None:
    preferred_keys = [
        "record_reference",
        "reference",
        "invoice_number",
        "invoice_no",
        "sales_invoice_no",
        "po_number",
        "po_no",
        "grn_number",
        "grn_no",
        "payment_number",
        "receipt_number",
        "count_number",
        "product_code",
        "customer_code",
        "supplier_code",
    ]
    for key in preferred_keys:
        value = details.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    if resource_id:
        return str(resource_id)
    return None


def _maybe_cleanup_old_audit_logs(db: Session) -> None:
    global _last_retention_check_at
    now = time.monotonic()
    if now - _last_retention_check_at < _RETENTION_CHECK_INTERVAL_SECONDS:
        return
    _last_retention_check_at = now

    retention_days = int(os.getenv("AUDIT_LOG_RETENTION_DAYS", "365") or "365")
    if retention_days <= 0:
        return

    db.execute(
        text(
            """
            DELETE FROM audit_logs
            WHERE created_at < NOW() - (:retention_days::text || ' days')::interval
            """
        ),
        {"retention_days": retention_days},
    )


def ensure_audit_logs_storage(db: Session) -> None:
    """Public helper for endpoints that need guaranteed audit table availability."""
    _ensure_audit_logs_table(db)


def log_audit_event(
    db: Session,
    *,
    action: str,
    resource_type: str,
    status: str,
    user_id: UUID | str | None = None,
    resource_id: UUID | None = None,
    details: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> None:
    """Write a best-effort audit event.

    This function must never break request flow, so failures are swallowed.
    """
    try:
        _ensure_audit_logs_table(db)

        safe_details = _sanitize_details(details or {})
        action_type = _derive_action_type(action)
        module_name = (resource_type or "system").strip().lower() or "system"
        record_reference = _derive_record_reference(resource_id, safe_details if isinstance(safe_details, dict) else {})
        description = ""
        if isinstance(safe_details, dict):
            description = str(safe_details.get("description") or safe_details.get("message") or "").strip()
        if not description:
            description = f"{action_type} on {module_name}"
        username = ""
        if isinstance(safe_details, dict):
            username = str(
                safe_details.get("username")
                or safe_details.get("user_name")
                or safe_details.get("email")
                or ""
            ).strip()

        with db.begin_nested():
            db.execute(
                text(
                    """
                    INSERT INTO audit_logs (
                        user_id, username, action, action_type, module_name, resource_type, resource_id,
                        record_reference, description, status, details, ip_address
                    ) VALUES (
                        :user_id, :username, :action, :action_type, :module_name, :resource_type, :resource_id,
                        :record_reference, :description, :status, CAST(:details AS JSONB), :ip_address
                    )
                    """
                ),
                {
                    "user_id": str(user_id) if user_id else None,
                    "username": username or None,
                    "action": action,
                    "action_type": action_type,
                    "module_name": module_name,
                    "resource_type": resource_type,
                    "resource_id": str(resource_id) if resource_id else None,
                    "record_reference": record_reference,
                    "description": description,
                    "status": status,
                    "details": json.dumps(safe_details),
                    "ip_address": ip_address,
                },
            )
            _maybe_cleanup_old_audit_logs(db)
        logger.info(
            "AUDIT action=%s action_type=%s module=%s status=%s user_id=%s reference=%s",
            action,
            action_type,
            module_name,
            status,
            str(user_id) if user_id else "anonymous",
            record_reference or "-",
        )
    except Exception:
        # Best-effort logging should not interrupt business flow.
        return
