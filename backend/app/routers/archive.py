"""Archive lifecycle reminders and explicit purge confirmation endpoints.

This module intentionally avoids automatic hard deletes for financial/stock-critical
records. It only surfaces reminders and performs purge when an admin confirms.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, scope_query_to_company
from app.models.customer import Customer
from app.models.payment import Payment
from app.models.product import Product, ProductCategory, StockLedger
from app.models.purchase import GoodsReceiptNote, PurchaseOrder
from app.models.sales import Quotation, SalesInvoice
from app.models.supplier import Supplier
from app.models.user import User


router = APIRouter(prefix="/api/v1/archive", tags=["archive"])


@dataclass(frozen=True)
class ArchivePolicy:
    key: str
    label: str
    model: Any
    retention_days: int
    purge_allowed: bool


# Soft-delete is permanent across the ERP: an archived (is_deleted=True) record is
# retained indefinitely so it stays available for reports, audit logs, accounting and
# references (e.g. a soft-deleted customer must keep resolving on its historical
# invoices). NO module is ever hard-deleted, so purge_allowed is False everywhere.
# retention_days is kept only as informational metadata for the archive summary.
ARCHIVE_POLICIES: list[ArchivePolicy] = [
    ArchivePolicy("customers", "Customers", Customer, 90, False),
    ArchivePolicy("suppliers", "Suppliers", Supplier, 90, False),
    ArchivePolicy("products", "Products", Product, 120, False),
    ArchivePolicy("categories", "Categories", ProductCategory, 120, False),
    ArchivePolicy("quotations", "Quotations", Quotation, 120, False),
    ArchivePolicy("purchase_orders", "Purchase Orders", PurchaseOrder, 180, False),
    ArchivePolicy("grn", "Goods Receipt Notes", GoodsReceiptNote, 180, False),
    ArchivePolicy("sales_invoices", "Sales Invoices", SalesInvoice, 365, False),
    ArchivePolicy("payments", "Payments", Payment, 365, False),
    ArchivePolicy("stock_ledger", "Stock Ledger", StockLedger, 365, False),
]


class PurgeConfirmRequest(BaseModel):
    confirmation_text: str


def _require_admin(user: User) -> None:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")


def _to_date(value: datetime | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    return value


def _compute_stats(db: Session, policy: ArchivePolicy, today: date, company_id=None) -> dict[str, Any]:
    q = db.query(policy.model.id, policy.model.deleted_at).filter(policy.model.is_deleted == True)
    company_col = getattr(policy.model, "company_id", None)
    if company_id is not None and company_col is not None:
        q = q.filter(company_col == company_id)
    rows = q.all()

    # Count archived (soft-deleted) records only. There is NO purge deadline anymore:
    # archived records are retained indefinitely, so nothing is ever "due soon" or
    # "overdue" for deletion.
    total_archived = sum(1 for _record_id, deleted_at in rows if _to_date(deleted_at) is not None)

    return {
        "key": policy.key,
        "label": policy.label,
        "retention_days": policy.retention_days,
        "purge_allowed": policy.purge_allowed,
        "total_archived": total_archived,
        "due_soon": 0,
        "overdue": 0,
    }


def _all_stats(db: Session, company_id=None) -> list[dict[str, Any]]:
    today = date.today()
    return [_compute_stats(db, policy, today, company_id) for policy in ARCHIVE_POLICIES]


@router.get("/login-alerts")
async def login_alerts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stats = _all_stats(db, company_id=current_user.company_id)

    # Archived records are retained indefinitely (soft-archive only) — nothing is ever
    # hard-deleted, so there is no retention deadline and no review is required.
    return {
        "requires_attention": False,
        "modules": [],
        "actionable_modules": [],
        "protected_modules": stats,
        "message": "Archived records are retained indefinitely. No records are ever hard-deleted.",
        "default_action": "none",
        "policy": {
            "no_auto_hard_delete_for": [p.key for p in ARCHIVE_POLICIES],
            "review_window_days": 0,
        },
    }


@router.get("/purge-preview")
async def purge_preview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)

    stats = _all_stats(db, company_id=current_user.company_id)
    # Hard delete has been removed ERP-wide: there are never any purge candidates.
    return {
        "modules": stats,
        "purge_candidates": 0,
        "expected_confirmation_text": "",
        "warning": "Archived records are retained indefinitely as soft-archive. No records are ever hard-deleted.",
    }


@router.post("/purge-confirm")
async def purge_confirm(
    payload: PurgeConfirmRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Hard delete has been permanently removed from the ERP.

    Business records are only ever soft-archived (is_deleted=True) and are retained
    indefinitely so they remain available for reports, audit logs, accounting and
    historical references. This endpoint is kept for backward compatibility but NEVER
    physically deletes any record — there is no hard-delete path.
    """
    _require_admin(current_user)

    return {
        "deleted": 0,
        "skipped": 0,
        "protected_modules_kept_archived": [p.key for p in ARCHIVE_POLICIES],
        "message": "No records were deleted. Archived records are retained as soft-archive; hard delete is disabled.",
    }
