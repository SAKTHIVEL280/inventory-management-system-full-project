"""Audit logging utilities."""
from __future__ import annotations

import json
import logging
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session


logger = logging.getLogger(__name__)


def log_audit_event(
    db: Session,
    *,
    action: str,
    resource_type: str,
    status: str,
    user_id: UUID | None = None,
    resource_id: UUID | None = None,
    details: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> None:
    """Write a best-effort audit event.

    This function must never break request flow, so failures are swallowed.
    """
    try:
        with db.begin_nested():
            db.execute(
                text(
                    """
                    INSERT INTO audit_logs (
                        user_id, action, resource_type, resource_id, status, details, ip_address
                    ) VALUES (
                        :user_id, :action, :resource_type, :resource_id, :status, CAST(:details AS JSONB), :ip_address
                    )
                    """
                ),
                {
                    "user_id": str(user_id) if user_id else None,
                    "action": action,
                    "resource_type": resource_type,
                    "resource_id": str(resource_id) if resource_id else None,
                    "status": status,
                    "details": json.dumps(details or {}),
                    "ip_address": ip_address,
                },
            )
        logger.info(
            "AUDIT action=%s status=%s resource=%s user_id=%s",
            action,
            status,
            resource_type,
            str(user_id) if user_id else "anonymous",
        )
    except Exception:
        # Best-effort logging should not interrupt business flow.
        return
