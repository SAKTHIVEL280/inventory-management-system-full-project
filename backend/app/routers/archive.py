"""Archive lifecycle reminders and explicit purge confirmation endpoints.

This module intentionally avoids automatic hard deletes for financial/stock-critical
records. It only surfaces reminders and performs purge when an admin confirms.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
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


ARCHIVE_POLICIES: list[ArchivePolicy] = [
    ArchivePolicy("customers", "Customers", Customer, 90, True),
    ArchivePolicy("suppliers", "Suppliers", Supplier, 90, True),
    ArchivePolicy("products", "Products", Product, 120, True),
    ArchivePolicy("categories", "Categories", ProductCategory, 120, True),
    ArchivePolicy("quotations", "Quotations", Quotation, 120, True),
    ArchivePolicy("purchase_orders", "Purchase Orders", PurchaseOrder, 180, True),
    ArchivePolicy("grn", "Goods Receipt Notes", GoodsReceiptNote, 180, True),
    # Protected modules: no automatic hard delete. Explicit decision required.
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


def _compute_stats(db: Session, policy: ArchivePolicy, today: date) -> dict[str, Any]:
    rows = (
        db.query(policy.model.id, policy.model.deleted_at)
        .filter(policy.model.is_deleted == True)
        .all()
    )

    total_archived = 0
    due_soon = 0
    overdue = 0

    for _record_id, deleted_at in rows:
        deleted_on = _to_date(deleted_at)
        if not deleted_on:
            continue

        total_archived += 1
        purge_on = deleted_on + timedelta(days=policy.retention_days)
        days_left = (purge_on - today).days

        if days_left < 0:
            overdue += 1
        elif 0 <= days_left <= 7:
            due_soon += 1

    return {
        "key": policy.key,
        "label": policy.label,
        "retention_days": policy.retention_days,
        "purge_allowed": policy.purge_allowed,
        "total_archived": total_archived,
        "due_soon": due_soon,
        "overdue": overdue,
    }


def _all_stats(db: Session) -> list[dict[str, Any]]:
    today = date.today()
    return [_compute_stats(db, policy, today) for policy in ARCHIVE_POLICIES]


@router.get("/login-alerts")
async def login_alerts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stats = _all_stats(db)

    remind_modules = [s for s in stats if s["due_soon"] > 0 or s["overdue"] > 0]
    protected = [s for s in remind_modules if not s["purge_allowed"]]
    actionable = [s for s in remind_modules if s["purge_allowed"]]

    return {
        "requires_attention": len(remind_modules) > 0,
        "modules": remind_modules,
        "actionable_modules": actionable,
        "protected_modules": protected,
        "message": "Archived records nearing retention deadline require review.",
        "default_action": "extend_retention",
        "policy": {
            "no_auto_hard_delete_for": ["sales_invoices", "payments", "stock_ledger"],
            "review_window_days": 7,
        },
    }


@router.get("/purge-preview")
async def purge_preview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)

    stats = _all_stats(db)
    purge_candidates = sum(s["overdue"] for s in stats if s["purge_allowed"])
    expected_text = f"DELETE {purge_candidates} RECORDS"

    return {
        "modules": stats,
        "purge_candidates": purge_candidates,
        "expected_confirmation_text": expected_text,
        "warning": "Protected modules are excluded from hard delete and remain archived until explicitly handled.",
    }


@router.post("/purge-confirm")
async def purge_confirm(
    payload: PurgeConfirmRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)

    stats = _all_stats(db)
    purge_candidates = sum(s["overdue"] for s in stats if s["purge_allowed"])
    expected_text = f"DELETE {purge_candidates} RECORDS"

    if payload.confirmation_text != expected_text:
        raise HTTPException(
            status_code=400,
            detail=f"Confirmation text mismatch. Expected: {expected_text}",
        )

    today = date.today()
    deleted = 0
    skipped = 0

    for policy in ARCHIVE_POLICIES:
        if not policy.purge_allowed:
            continue

        records = db.query(policy.model).filter(policy.model.is_deleted == True).all()
        for record in records:
            deleted_on = _to_date(getattr(record, "deleted_at", None))
            if not deleted_on:
                continue
            purge_on = deleted_on + timedelta(days=policy.retention_days)
            if purge_on > today:
                continue

            try:
                with db.begin_nested():
                    db.delete(record)
                    db.flush()
                deleted += 1
            except IntegrityError:
                skipped += 1

    db.commit()

    return {
        "deleted": deleted,
        "skipped": skipped,
        "protected_modules_kept_archived": [p.key for p in ARCHIVE_POLICIES if not p.purge_allowed],
        "message": "Manual purge completed.",
    }
