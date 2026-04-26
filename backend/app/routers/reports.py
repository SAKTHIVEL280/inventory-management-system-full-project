"""Reports router."""
from collections import defaultdict
from datetime import date, datetime, timedelta
from io import BytesIO
import os
import re
import json
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_permissions
from app.models.user import User
from app.models.inventory_count import InventoryCountDifferenceAudit, InventoryCountItem
from app.models.product import Product, StockLedger
from app.models.sales import SalesInvoice, SalesInvoiceItem, SalesOrder, SalesReturn, SalesReturnItem
from app.models.purchase import GoodsReceiptNote, GRNItem, PurchaseOrder, PurchaseReturn, PurchaseReturnItem
from app.models.customer import Customer
from app.models.supplier import Supplier
from app.models.company import Company
from app.models.payment import Payment, PaymentAllocation
from app.services.audit_service import ensure_audit_logs_storage, log_audit_event
from app.services.gst_service import (
    INVOICE_TYPE_EXPORT,
    INVOICE_TYPE_OTHER_STATES,
    INVOICE_TYPE_UNION_TERRITORY,
    INVOICE_TYPE_WITHIN_STATE,
    is_india_country,
)

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


GSTIN_REGEX = re.compile(r"^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
GST_REPORT_FREQUENCY_LABELS: dict[str, str] = {
    "monthly": "Monthly",
    "quarterly": "Quarterly",
    "annually": "Annually",
}
GST_ALLOWED_SLABS = {0.0, 0.1, 0.25, 3.0, 5.0, 12.0, 18.0, 28.0}
UNION_TERRITORY_CODES = {"01", "04", "07", "26", "31", "34", "35", "37", "38"}
UNION_TERRITORY_NAMES = {
    "ANDAMAN AND NICOBAR ISLANDS",
    "CHANDIGARH",
    "DADRA AND NAGAR HAVELI AND DAMAN AND DIU",
    "DELHI",
    "JAMMU AND KASHMIR",
    "LADAKH",
    "LAKSHADWEEP",
    "PUDUCHERRY",
}
GST_REPORT_BASE_CURRENCY = "INR"


def _load_report_fx_rates() -> dict[str, float]:
    rates = {GST_REPORT_BASE_CURRENCY: 1.0}
    raw = (os.getenv("GST_REPORT_FX_RATES") or "").strip()
    if not raw:
        return rates
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return rates
    if not isinstance(parsed, dict):
        return rates
    for code, value in parsed.items():
        token = (str(code or "").strip().upper())
        if len(token) != 3 or not token.isalpha():
            continue
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            continue
        if numeric > 0:
            rates[token] = numeric
    return rates


GST_REPORT_FX_RATES = _load_report_fx_rates()


def _derive_invoice_status(raw_status: str | None, amount_paid: int, total_amount: int) -> str:
    token = (raw_status or "").strip().lower()
    if token in {"draft", "cancelled"}:
        return token
    paid = int(amount_paid or 0)
    total = int(total_amount or 0)
    if paid <= 0:
        return "issued"
    if paid >= total and total > 0:
        return "paid"
    return "partial_paid"


def _ensure_valid_date_range(from_date: date, to_date: date) -> None:
    """Validate report date range parameters."""
    if from_date > to_date:
        raise HTTPException(
            status_code=422,
            detail="from_date must be less than or equal to to_date",
        )


def _normalize_frequency(frequency: str) -> tuple[str, str]:
    token = (frequency or "").strip().lower()
    if token not in GST_REPORT_FREQUENCY_LABELS:
        allowed = ", ".join(GST_REPORT_FREQUENCY_LABELS.keys())
        raise HTTPException(
            status_code=422,
            detail=f"Invalid frequency. Allowed values: {allowed}",
        )
    return token, GST_REPORT_FREQUENCY_LABELS[token]


def _validate_frequency_date_window(from_date: date, to_date: date, frequency: str) -> None:
    _ensure_valid_date_range(from_date, to_date)
    today = date.today()
    if to_date > today:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "End date cannot be in the future",
                "code": "VAL-001",
                "frequency": frequency,
                "from_date": from_date.isoformat(),
                "to_date": to_date.isoformat(),
                "today": today.isoformat(),
            },
        )
    total_days = (to_date - from_date).days + 1
    if total_days > 366:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Maximum report period is 12 months",
                "code": "VAL-001",
                "frequency": frequency,
                "from_date": from_date.isoformat(),
                "to_date": to_date.isoformat(),
                "selected_days": total_days,
                "allowed_days": 366,
            },
        )

    max_days = {
        "monthly": 31,
        "quarterly": 93,
        "annually": 366,
    }[frequency]
    if total_days > max_days:
        raise HTTPException(
            status_code=422,
            detail={
                "message": f"Selected date range exceeds {GST_REPORT_FREQUENCY_LABELS[frequency]} limits",
                "code": "VAL-001",
                "frequency": frequency,
                "from_date": from_date.isoformat(),
                "to_date": to_date.isoformat(),
                "selected_days": total_days,
                "allowed_days": max_days,
                "hint": f"Choose a shorter date range or switch frequency from {GST_REPORT_FREQUENCY_LABELS[frequency]}",
            },
        )


def _round_2(value: float | int) -> float:
    return round(float(value or 0.0), 2)


def _format_tax_percent(value: float | int | None) -> str:
    if value is None:
        return ""
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return ""


def _coerce_tax_percent(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return _round_2(float(value))
    except (TypeError, ValueError):
        return None


def _paise_to_amount(value: int | None) -> float:
    return _round_2(float(int(value or 0)) / 100.0)


def _amount_to_paise(value: float | int | None) -> int:
    return int(round(float(value or 0.0) * 100.0))


def _convert_with_rate(amount: float | int | None, rate: float) -> float:
    return _round_2(float(amount or 0.0) * float(rate or 1.0))


def _resolve_report_fx_rate(
    currency: str,
    *,
    stored_exchange_rate: float | int | None,
) -> tuple[float | None, str | None, str | None]:
    token = (currency or "").strip().upper()
    if token == GST_REPORT_BASE_CURRENCY:
        return 1.0, "base_currency", None

    rate = float(stored_exchange_rate or 0.0)
    if rate > 0:
        return rate, "stored_exchange_rate", None

    configured_rate = GST_REPORT_FX_RATES.get(token)
    if configured_rate and configured_rate > 0:
        return float(configured_rate), "configured_fx_rate", None

    # Non-strict fallback: keep the transaction included even when FX metadata is missing.
    return 1.0, "fallback_assumed_inr", None


def _format_ddmmyyyy(value: date | None) -> str | None:
    return value.strftime("%d.%m.%Y") if value else None


def _normalize_invoice_type(invoice_type: str | None, fallback_is_igst: bool) -> str:
    token = (invoice_type or "").strip().lower()
    if token in {
        INVOICE_TYPE_EXPORT,
        INVOICE_TYPE_OTHER_STATES,
        INVOICE_TYPE_UNION_TERRITORY,
        INVOICE_TYPE_WITHIN_STATE,
    }:
        return token
    return INVOICE_TYPE_OTHER_STATES if fallback_is_igst else INVOICE_TYPE_WITHIN_STATE


def _raise_gstr1_validation_error(errors: list[str]) -> None:
    if not errors:
        return
    raise HTTPException(
        status_code=422,
        detail={
            "message": "GSTR-1 validation failed",
            "errors": errors[:100],
        },
    )


def _raise_gstr2_validation_error(errors: list[str]) -> None:
    if not errors:
        return
    raise HTTPException(
        status_code=422,
        detail={
            "message": "GSTR-2 validation failed",
            "errors": errors[:100],
        },
    )


def _normalized_state_token(state_code: str | None, state_name: str | None) -> str:
    code = (state_code or "").strip().upper()
    if code:
        return code
    return (state_name or "").strip().upper()


def _is_union_territory(state_code: str | None, state_name: str | None) -> bool:
    token_code = (state_code or "").strip().upper()
    token_name = (state_name or "").strip().upper()
    return token_code in UNION_TERRITORY_CODES or token_name in UNION_TERRITORY_NAMES


def _customer_country_for_gstr(customer: Customer | None) -> str | None:
    if not customer:
        return None
    shipping_country = (customer.shipping_country or "").strip()
    if shipping_country:
        return shipping_country
    billing_country = (customer.billing_country or "").strip()
    if billing_country:
        return billing_country
    if (customer.business_type or "").strip().lower() == "domestic":
        return "India"
    return None


def _ensure_finance_tax_user(current_user: User) -> None:
    if current_user.role not in {"admin", "accounting"}:
        raise HTTPException(
            status_code=403,
            detail="Only Finance/Tax users are allowed to generate GST reports",
        )


def _ensure_action_log_view_user(current_user: User) -> None:
    if current_user.role not in {"admin", "accounting", "auditor"}:
        raise HTTPException(
            status_code=403,
            detail="Only Admin/Auditor users can view action logs",
        )


def _ensure_gst_report_audit_table(db: Session) -> None:
    db.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS gst_report_audit_logs (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID REFERENCES users(id),
                action VARCHAR(120) NOT NULL,
                report_type VARCHAR(40) NOT NULL,
                start_date DATE NOT NULL,
                end_date DATE NOT NULL,
                frequency VARCHAR(20) NOT NULL,
                "timestamp" TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                status VARCHAR(20) NOT NULL,
                details JSONB NOT NULL DEFAULT '{}'::jsonb
            )
            """
        )
    )
    db.execute(text("CREATE INDEX IF NOT EXISTS ix_gst_report_audit_logs_timestamp ON gst_report_audit_logs (\"timestamp\")"))
    db.execute(text("CREATE INDEX IF NOT EXISTS ix_gst_report_audit_logs_report_type ON gst_report_audit_logs (report_type)"))
    db.execute(text("CREATE INDEX IF NOT EXISTS ix_gst_report_audit_logs_user_id ON gst_report_audit_logs (user_id)"))


def _log_gst_report_event(
    db: Session,
    *,
    user_id: str | None,
    action: str,
    report_type: str,
    start_date: date,
    end_date: date,
    frequency: str,
    status: str,
    details: dict[str, Any] | None = None,
) -> None:
    try:
        _ensure_gst_report_audit_table(db)
        db.execute(
            text(
                """
                INSERT INTO gst_report_audit_logs (
                    user_id, action, report_type, start_date, end_date, frequency, status, details
                )
                VALUES (
                    :user_id, :action, :report_type, :start_date, :end_date, :frequency, :status, CAST(:details AS JSONB)
                )
                """
            ),
            {
                "user_id": user_id,
                "action": action,
                "report_type": report_type,
                "start_date": start_date,
                "end_date": end_date,
                "frequency": frequency,
                "status": status,
                "details": json.dumps(details or {}),
            },
        )
    except Exception:
        # Keep report generation resilient if audit storage fails.
        pass


@router.get("/dashboard")
async def dashboard_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("dashboard_read")),
):
    today = date.today()
    month_start = today.replace(day=1)
    receivable_statuses = ["issued", "partial_paid"]
    cash_receipt_statuses = ["pending", "cleared"]

    # Count totals
    total_products = db.query(func.count(Product.id)).filter(
        Product.is_deleted == False
    ).scalar() or 0

    total_customers = db.query(func.count(Customer.id)).filter(
        Customer.is_deleted == False,
        Customer.is_active == True
    ).scalar() or 0

    total_suppliers = db.query(func.count(Supplier.id)).filter(
        Supplier.is_deleted == False,
        Supplier.is_active == True
    ).scalar() or 0

    # Low stock count
    low_stock_count = 0
    safety_stock_count = 0
    products = db.query(Product).filter(Product.is_deleted == False).all()
    for product in products:
        qty_scalar = db.query(func.coalesce(func.sum(StockLedger.quantity), 0)).filter(StockLedger.product_id == product.id).scalar() or 0
        qty = float(qty_scalar)
        safety = float(product.safety_stock or 0)
        minimum = float(product.safety_stock or 0)
        
        if qty <= safety and qty > 0:
            safety_stock_count += 1
        if qty <= minimum:
            low_stock_count += 1

    # Pending purchase orders
    pending_po_count = db.query(func.count(PurchaseOrder.id)).filter(
        PurchaseOrder.status.in_(["pending", "approved", "partial_received"]),
        PurchaseOrder.is_deleted == False,
    ).scalar() or 0

    # Sales Order module removed from active workflow.
    pending_so_count = 0

    # Today sales
    today_sales = db.query(func.coalesce(func.sum(SalesInvoice.total_amount), 0)).filter(
        SalesInvoice.invoice_date == today,
        SalesInvoice.status.in_(["issued", "partial_paid", "paid"]),
        SalesInvoice.is_deleted == False,
    ).scalar() or 0

    # Month sales
    month_sales = db.query(func.coalesce(func.sum(SalesInvoice.total_amount), 0)).filter(
        SalesInvoice.invoice_date >= month_start,
        SalesInvoice.invoice_date <= today,
        SalesInvoice.status.in_(["issued", "partial_paid", "paid"]),
        SalesInvoice.is_deleted == False,
    ).scalar() or 0

    # Outstanding receivables
    outstanding_receivables = db.query(func.coalesce(func.sum(SalesInvoice.amount_due), 0)).filter(
        SalesInvoice.amount_due > 0,
        SalesInvoice.status.in_(receivable_statuses),
        SalesInvoice.is_deleted == False,
    ).scalar() or 0

    # Overdue invoices count
    overdue_invoices_count = db.query(func.count(SalesInvoice.id)).filter(
        SalesInvoice.due_date < today,
        SalesInvoice.status.in_(["issued", "partial_paid"]),
        SalesInvoice.is_deleted == False,
    ).scalar() or 0

    # Sales trend (last 7 days)
    sales_trend = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        amount = db.query(func.coalesce(func.sum(SalesInvoice.total_amount), 0)).filter(
            SalesInvoice.invoice_date == day,
            SalesInvoice.status.in_(["issued", "partial_paid", "paid"]),
            SalesInvoice.is_deleted == False,
        ).scalar() or 0
        sales_trend.append({"date": day.isoformat(), "amount": int(amount)})

    # Top products
    top_products_query = db.query(
        Product.name,
        func.coalesce(func.sum(SalesInvoiceItem.quantity), 0).label("quantity_sold"),
        func.coalesce(func.sum(SalesInvoiceItem.total_amount), 0).label("amount"),
    ).join(SalesInvoiceItem, SalesInvoiceItem.product_id == Product.id).join(
        SalesInvoice, SalesInvoice.id == SalesInvoiceItem.invoice_id
    ).filter(
        SalesInvoice.invoice_date >= month_start,
        SalesInvoice.invoice_date <= today,
        SalesInvoice.status.in_(["issued", "partial_paid", "paid"]),
        SalesInvoice.is_deleted == False,
        Product.is_deleted == False,
    ).group_by(Product.id, Product.name).order_by(text("quantity_sold DESC")).limit(5).all()

    top_products = [
        {
            "product_name": row.name,
            "quantity_sold": float(row.quantity_sold),
            "amount": int(row.amount),
        }
        for row in top_products_query
    ]

    def _build_cash_in_flow_metrics(start_date: date):
        payment_rows = (
            db.query(
                Payment.id,
                Payment.customer_id,
                Payment.amount,
                Customer.company_name,
            )
            .join(Customer, Payment.customer_id == Customer.id)
            .filter(
                Payment.party_type == "customer",
                Payment.payment_type == "receipt",
                Payment.status.in_(cash_receipt_statuses),
                Payment.is_deleted == False,
                Customer.is_deleted == False,
                Payment.payment_date >= start_date,
                Payment.payment_date <= today,
            )
            .all()
        )

        if not payment_rows:
            empty_summary = {
                "total_received_amount": 0,
                "fully_settled_amount": 0,
                "partially_settled_amount": 0,
            }
            return [], empty_summary

        payment_ids = [row.id for row in payment_rows]
        allocation_rows = (
            db.query(
                PaymentAllocation.payment_id,
                PaymentAllocation.invoice_id,
                PaymentAllocation.allocated_amount,
            )
            .filter(
                PaymentAllocation.payment_id.in_(payment_ids),
                PaymentAllocation.is_deleted == False,
                PaymentAllocation.invoice_id.isnot(None),
            )
            .all()
        )

        allocations_by_payment: dict[str, list[tuple[str, int]]] = defaultdict(list)
        invoice_ids = set()
        for row in allocation_rows:
            if not row.invoice_id:
                continue
            amount = int(row.allocated_amount or 0)
            if amount <= 0:
                continue
            payment_key = str(row.payment_id)
            invoice_key = str(row.invoice_id)
            allocations_by_payment[payment_key].append((invoice_key, amount))
            invoice_ids.add(row.invoice_id)

        invoice_due_map: dict[str, int] = {}
        if invoice_ids:
            invoice_rows = (
                db.query(SalesInvoice.id, SalesInvoice.amount_due)
                .filter(SalesInvoice.id.in_(list(invoice_ids)), SalesInvoice.is_deleted == False)
                .all()
            )
            invoice_due_map = {str(row.id): int(row.amount_due or 0) for row in invoice_rows}

        by_customer: dict[str, dict[str, int | str]] = {}
        for row in payment_rows:
            if not row.customer_id:
                continue

            customer_key = str(row.customer_id)
            if customer_key not in by_customer:
                by_customer[customer_key] = {
                    "customer_id": customer_key,
                    "customer_name": row.company_name or customer_key,
                    "total_received_amount": 0,
                    "fully_settled_amount": 0,
                    "partially_settled_amount": 0,
                }

            entry = by_customer[customer_key]
            receipt_amount = int(row.amount or 0)
            entry["total_received_amount"] = int(entry["total_received_amount"]) + receipt_amount

            allocations = allocations_by_payment.get(str(row.id), [])
            allocated_total = 0
            fully_settled = 0
            partially_settled = 0
            for invoice_id, allocated_amount in allocations:
                allocated_total += allocated_amount
                invoice_due = invoice_due_map.get(invoice_id)
                if invoice_due is not None and invoice_due <= 0:
                    fully_settled += allocated_amount
                else:
                    partially_settled += allocated_amount

            # Any receipt value not mapped to invoice allocations is treated as partial.
            unallocated = max(0, receipt_amount - allocated_total)
            partially_settled += unallocated

            entry["fully_settled_amount"] = int(entry["fully_settled_amount"]) + fully_settled
            entry["partially_settled_amount"] = int(entry["partially_settled_amount"]) + partially_settled

        rows = sorted(
            by_customer.values(),
            key=lambda row: int(row["total_received_amount"]),
            reverse=True,
        )
        summary = {
            "total_received_amount": int(sum(int(row["total_received_amount"]) for row in rows)),
            "fully_settled_amount": int(sum(int(row["fully_settled_amount"]) for row in rows)),
            "partially_settled_amount": int(sum(int(row["partially_settled_amount"]) for row in rows)),
        }

        return rows[:12], summary

    daily_rows, daily_summary = _build_cash_in_flow_metrics(today)
    weekly_rows, weekly_summary = _build_cash_in_flow_metrics(today - timedelta(days=6))
    monthly_rows, monthly_summary = _build_cash_in_flow_metrics(month_start)

    cash_in_flow = {
        "daily": daily_rows,
        "weekly": weekly_rows,
        "monthly": monthly_rows,
    }

    cash_in_flow_summary = {
        "daily": daily_summary,
        "weekly": weekly_summary,
        "monthly": monthly_summary,
    }

    # Recent invoices with customer names
    recent_invoices_rows = db.query(
        SalesInvoice, 
        Customer.company_name
    ).join(
        Customer, SalesInvoice.customer_id == Customer.id
    ).filter(
        SalesInvoice.is_deleted == False
    ).order_by(
        SalesInvoice.created_at.desc()
    ).limit(5).all()
    
    recent_invoices = [
        {
            "invoice_number": invoice.invoice_number,
            "customer_name": company_name,
            "amount": invoice.total_amount,
            "status": _derive_invoice_status(invoice.status, int(invoice.amount_paid or 0), int(invoice.total_amount or 0)),
            "date": invoice.invoice_date.isoformat() if invoice.invoice_date else "",
        }
        for invoice, company_name in recent_invoices_rows
    ]

    # Outstanding payables
    outstanding_payables = db.query(func.coalesce(func.sum(GoodsReceiptNote.total_amount), 0)).filter(
        GoodsReceiptNote.status == "confirmed",
        GoodsReceiptNote.is_deleted == False,
    ).scalar() or 0

    return {
        "total_products": int(total_products),
        "total_customers": int(total_customers),
        "total_suppliers": int(total_suppliers),
        "low_stock_count": int(low_stock_count),
        "safety_stock_count": int(safety_stock_count),
        "pending_purchase_orders": int(pending_po_count),
        "pending_sales_orders": int(pending_so_count),
        "today_sales": int(today_sales),
        "month_sales": int(month_sales),
        "outstanding_receivables": int(outstanding_receivables),
        "outstanding_payables": int(outstanding_payables),
        "overdue_invoices_count": int(overdue_invoices_count),
        "sales_trend": sales_trend,
        "top_products": top_products,
        "cash_in_flow": cash_in_flow,
        "cash_in_flow_summary": cash_in_flow_summary,
        "recent_invoices": recent_invoices,
    }


@router.get("/stock")
async def stock_report(
    low_stock_only: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("stock_ledger_read", "reports_read")),
):
    rows = []
    NO_BATCH_TOKEN = "__UNASSIGNED__"

    def _normalize_batch(batch_no: str | None) -> str:
        token = (batch_no or "").strip()
        return token if token else NO_BATCH_TOKEN

    # Product-level totals remain sourced from stock ledger for consistency with
    # all stock-affecting flows and manual adjustments.
    product_totals = {
        str(row.product_id): float(row.qty or 0)
        for row in (
            db.query(
                StockLedger.product_id,
                func.coalesce(func.sum(StockLedger.quantity), 0).label("qty"),
            )
            .group_by(StockLedger.product_id)
            .all()
        )
    }

    # Build batch-wise balance from transactional references.
    # Key by (product, batch) so date metadata differences do not split the same batch.
    batch_balances: dict[tuple[str, str], float] = {}
    batch_meta: dict[tuple[str, str], tuple[date | None, date | None]] = {}

    def _accumulate(
        product_id,
        batch_no,
        manufacture_date,
        expiry_date,
        qty_delta,
    ):
        if not product_id:
            return
        key = (str(product_id), _normalize_batch(batch_no))
        if key not in batch_meta:
            batch_meta[key] = (manufacture_date, expiry_date)
        else:
            prev_mfg, prev_exp = batch_meta[key]
            batch_meta[key] = (
                prev_mfg or manufacture_date,
                prev_exp or expiry_date,
            )
        batch_balances[key] = batch_balances.get(key, 0.0) + float(qty_delta or 0)

    grn_rows = (
        db.query(
            GRNItem.product_id,
            GRNItem.batch_no,
            GRNItem.manufacture_date,
            GRNItem.expiry_date,
            func.coalesce(func.sum(GRNItem.quantity), 0).label("qty"),
            func.coalesce(func.sum(GRNItem.free_quantity), 0).label("free_qty"),
        )
        .join(GoodsReceiptNote, GRNItem.grn_id == GoodsReceiptNote.id)
        .filter(
            GoodsReceiptNote.status == "confirmed",
            GoodsReceiptNote.is_deleted == False,
            GRNItem.is_deleted == False,
        )
        .group_by(
            GRNItem.product_id,
            GRNItem.batch_no,
            GRNItem.manufacture_date,
            GRNItem.expiry_date,
        )
        .all()
    )
    for row in grn_rows:
        _accumulate(
            row.product_id,
            row.batch_no,
            row.manufacture_date,
            row.expiry_date,
            float(row.qty or 0) + float(row.free_qty or 0),
        )

    purchase_return_rows = (
        db.query(
            PurchaseReturnItem.product_id,
            GRNItem.batch_no,
            GRNItem.manufacture_date,
            GRNItem.expiry_date,
            func.coalesce(func.sum(PurchaseReturnItem.quantity), 0).label("qty"),
        )
        .join(PurchaseReturn, PurchaseReturnItem.purchase_return_id == PurchaseReturn.id)
        .outerjoin(GRNItem, PurchaseReturnItem.grn_item_id == GRNItem.id)
        .filter(
            PurchaseReturn.status == "confirmed",
            PurchaseReturn.is_deleted == False,
            PurchaseReturnItem.is_deleted == False,
        )
        .group_by(
            PurchaseReturnItem.product_id,
            GRNItem.batch_no,
            GRNItem.manufacture_date,
            GRNItem.expiry_date,
        )
        .all()
    )
    for row in purchase_return_rows:
        _accumulate(
            row.product_id,
            row.batch_no,
            row.manufacture_date,
            row.expiry_date,
            -float(row.qty or 0),
        )

    sales_issue_rows = (
        db.query(
            SalesInvoiceItem.product_id,
            SalesInvoiceItem.batch_no,
            SalesInvoiceItem.manufacture_date,
            SalesInvoiceItem.expiry_date,
            func.coalesce(func.sum(SalesInvoiceItem.quantity), 0).label("qty"),
        )
        .join(SalesInvoice, SalesInvoiceItem.invoice_id == SalesInvoice.id)
        .filter(
            SalesInvoice.status.in_(["issued", "partial_paid", "paid"]),
            SalesInvoice.is_deleted == False,
            SalesInvoiceItem.is_deleted == False,
        )
        .group_by(
            SalesInvoiceItem.product_id,
            SalesInvoiceItem.batch_no,
            SalesInvoiceItem.manufacture_date,
            SalesInvoiceItem.expiry_date,
        )
        .all()
    )
    for row in sales_issue_rows:
        _accumulate(
            row.product_id,
            row.batch_no,
            row.manufacture_date,
            row.expiry_date,
            -float(row.qty or 0),
        )

    sales_return_rows = (
        db.query(
            SalesReturnItem.product_id,
            SalesInvoiceItem.batch_no,
            SalesInvoiceItem.manufacture_date,
            SalesInvoiceItem.expiry_date,
            func.coalesce(func.sum(SalesReturnItem.quantity), 0).label("qty"),
        )
        .join(SalesReturn, SalesReturnItem.sales_return_id == SalesReturn.id)
        .outerjoin(SalesInvoiceItem, SalesReturnItem.invoice_item_id == SalesInvoiceItem.id)
        .filter(
            SalesReturn.status == "confirmed",
            SalesReturn.is_deleted == False,
            SalesReturnItem.is_deleted == False,
        )
        .group_by(
            SalesReturnItem.product_id,
            SalesInvoiceItem.batch_no,
            SalesInvoiceItem.manufacture_date,
            SalesInvoiceItem.expiry_date,
        )
        .all()
    )
    for row in sales_return_rows:
        _accumulate(
            row.product_id,
            row.batch_no,
            row.manufacture_date,
            row.expiry_date,
            float(row.qty or 0),
        )

    inventory_count_diff_rows = (
        db.query(
            InventoryCountItem.product_id,
            InventoryCountItem.batch_no,
            InventoryCountItem.manufacture_date,
            InventoryCountItem.expiry_date,
            func.coalesce(func.sum(InventoryCountDifferenceAudit.difference_qty), 0).label("qty"),
        )
        .join(
            InventoryCountDifferenceAudit,
            InventoryCountDifferenceAudit.inventory_count_item_id == InventoryCountItem.id,
        )
        .group_by(
            InventoryCountItem.product_id,
            InventoryCountItem.batch_no,
            InventoryCountItem.manufacture_date,
            InventoryCountItem.expiry_date,
        )
        .all()
    )
    for row in inventory_count_diff_rows:
        _accumulate(
            row.product_id,
            row.batch_no,
            row.manufacture_date,
            row.expiry_date,
            float(row.qty or 0),
        )

    balances_by_product: dict[str, list[tuple[str, date | None, date | None, float]]] = {}
    for (product_id, batch_no), qty in batch_balances.items():
        if abs(qty) < 1e-6:
            continue
        manufacture_date, expiry_date = batch_meta.get((product_id, batch_no), (None, None))
        balances_by_product.setdefault(product_id, []).append(
            (batch_no, manufacture_date, expiry_date, qty)
        )

    products = db.query(Product).filter(Product.is_deleted == False).all()
    for product in products:
        product_id = str(product.id)
        safety = float(product.safety_stock or 0)
        product_qty = float(product_totals.get(product_id, 0.0))

        # STO-003/004/005: Keep low-stock status product-based; only row expansion
        # changes from product-level to batch-level.
        status = "Low Stock" if product_qty <= safety else "In Stock"
        if low_stock_only and status != "Low Stock":
            continue

        product_batches = list(balances_by_product.get(product_id, []))
        allocated_qty = sum(float(entry[3]) for entry in product_batches)
        unassigned_qty = product_qty - allocated_qty

        # Add reconciliation row only for positive residual quantity.
        # Negative residuals are data mismatches and should not create confusing
        # negative rows in Stock Master.
        if unassigned_qty > 1e-6 or not product_batches:
            product_batches.append((NO_BATCH_TOKEN, None, None, unassigned_qty if product_batches else product_qty))

        product_batches.sort(key=lambda entry: (entry[0] == NO_BATCH_TOKEN, entry[0]))

        for batch_no, manufacture_date, expiry_date, batch_qty in product_batches:
            rows.append({
                "product_code": product.product_code,
                "product_name": product.name,
                "hsn": product.hsn_code,
                "batch_no": None if batch_no == NO_BATCH_TOKEN else batch_no,
                "manufacture_date": manufacture_date,
                "expiry_date": expiry_date,
                "closing_qty": float(batch_qty),
                "min_stock": float(safety),
                "safety_stock": float(safety),
                "status": status,
            })

    rows.sort(key=lambda row: (row["product_name"] or "", row["batch_no"] or "~"))
    return {"items": rows, "total": len(rows)}


@router.get("/sales")
async def sales_report(
    from_date: date,
    to_date: date,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("reports_read")),
):
    _ensure_valid_date_range(from_date, to_date)
    rows = db.query(SalesInvoice).filter(
        SalesInvoice.invoice_date >= from_date,
        SalesInvoice.invoice_date <= to_date,
        SalesInvoice.status.in_(["issued", "partial_paid", "paid"]),
        SalesInvoice.is_deleted == False,
    ).all()
    return {
        "count": len(rows),
        "total_amount": int(sum(row.total_amount for row in rows)),
        "items": [
            {
                "invoice_number": row.invoice_number,
                "invoice_date": row.invoice_date.isoformat() if row.invoice_date else None,
                "total_amount": row.total_amount,
                "amount_paid": row.amount_paid,
                "amount_due": row.amount_due,
                "status": row.status,
            }
            for row in rows
        ],
    }


@router.get("/purchase")
async def purchase_report(
    from_date: date,
    to_date: date,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("reports_read")),
):
    _ensure_valid_date_range(from_date, to_date)
    rows = db.query(GoodsReceiptNote).filter(
        GoodsReceiptNote.receipt_date >= from_date,
        GoodsReceiptNote.receipt_date <= to_date,
        GoodsReceiptNote.status == "confirmed",
        GoodsReceiptNote.is_deleted == False,
    ).all()
    return {
        "count": len(rows),
        "total_amount": int(sum(row.total_amount for row in rows)),
        "items": [
            {
                "grn_number": row.grn_number,
                "receipt_date": row.receipt_date.isoformat() if row.receipt_date else None,
                "supplier_id": str(row.supplier_id),
                "total_amount": row.total_amount,
            }
            for row in rows
        ],
    }


@router.get("/outstanding-receivables")
async def outstanding_receivables(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("reports_read")),
):
    rows = db.query(SalesInvoice).filter(
        SalesInvoice.amount_due > 0,
        SalesInvoice.status.in_(["issued", "partial_paid"]),
        SalesInvoice.is_deleted == False,
    ).all()
    return {
        "total_outstanding": int(sum(row.amount_due for row in rows)),
        "items": [
            {
                "invoice_number": row.invoice_number,
                "invoice_date": row.invoice_date.isoformat() if row.invoice_date else None,
                "due_date": row.due_date.isoformat() if row.due_date else None,
                "balance_due": row.amount_due,
            }
            for row in rows
        ],
    }


@router.get("/outstanding-payables")
async def outstanding_payables(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("reports_read")),
):
    rows = db.query(GoodsReceiptNote).filter(
        GoodsReceiptNote.status == "confirmed",
        GoodsReceiptNote.is_deleted == False,
    ).all()
    return {
        "total_outstanding": int(sum(row.total_amount for row in rows)),
        "items": [
            {
                "grn_number": row.grn_number,
                "receipt_date": row.receipt_date.isoformat() if row.receipt_date else None,
                "balance_due": row.total_amount,
            }
            for row in rows
        ],
    }


@router.get("/gstr1")
async def gstr1_report(
    from_date: date,
    to_date: date,
    frequency: str = Query(default="monthly"),
    strict_validation: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("reports_read")),
):
    _ensure_finance_tax_user(current_user)

    normalized_frequency, frequency_label = _normalize_frequency(frequency)
    _validate_frequency_date_window(from_date, to_date, normalized_frequency)

    invoices = (
        db.query(SalesInvoice)
        .filter(
            SalesInvoice.invoice_date >= from_date,
            SalesInvoice.invoice_date <= to_date,
            SalesInvoice.status.in_(["issued", "partial_paid", "paid"]),
            SalesInvoice.is_deleted == False,
        )
        .order_by(SalesInvoice.invoice_date.asc(), SalesInvoice.invoice_number.asc())
        .all()
    )

    invoice_ids = [row.id for row in invoices]
    invoice_id_map = {str(row.id): row for row in invoices}

    invoice_totals_map: dict[str, dict[str, float]] = {}
    invoice_rate_map: dict[str, set[float]] = defaultdict(set)
    validation_errors: list[str] = []

    if invoice_ids:
        item_rows = (
            db.query(
                SalesInvoiceItem.invoice_id,
                func.sum(SalesInvoiceItem.taxable_amount).label("taxable_amount"),
                func.sum(SalesInvoiceItem.cgst_amount).label("cgst_amount"),
                func.sum(SalesInvoiceItem.sgst_amount).label("sgst_amount"),
                func.sum(SalesInvoiceItem.igst_amount).label("igst_amount"),
            )
            .filter(
                SalesInvoiceItem.invoice_id.in_(invoice_ids),
                SalesInvoiceItem.is_deleted == False,
            )
            .group_by(SalesInvoiceItem.invoice_id)
            .all()
        )
        for item in item_rows:
            invoice_key = str(item.invoice_id)
            invoice_totals_map[invoice_key] = {
                "taxable_amount": _paise_to_amount(item.taxable_amount),
                "cgst_amount": _paise_to_amount(item.cgst_amount),
                "sgst_amount": _paise_to_amount(item.sgst_amount),
                "igst_amount": _paise_to_amount(item.igst_amount),
            }

        rate_rows = (
            db.query(SalesInvoiceItem.invoice_id, SalesInvoiceItem.gst_rate)
            .filter(
                SalesInvoiceItem.invoice_id.in_(invoice_ids),
                SalesInvoiceItem.is_deleted == False,
            )
            .all()
        )
        for item in rate_rows:
            invoice_key = str(item.invoice_id)
            slab = _round_2(float(item.gst_rate or 0.0))
            if slab not in GST_ALLOWED_SLABS:
                invoice = invoice_id_map.get(invoice_key)
                invoice_number = invoice.invoice_number if invoice else invoice_key
                validation_errors.append(
                    f"VAL-003 Tax Rate Validity failed for invoice {invoice_number}: invalid GST slab {slab}"
                )
            invoice_rate_map[invoice_key].add(slab)

    sales_order_ids = {row.sales_order_id for row in invoices if row.sales_order_id is not None}
    sales_order_currency_map: dict[str, dict[str, float | str | None]] = {}
    if sales_order_ids:
        order_rows = (
            db.query(SalesOrder.id, SalesOrder.currency_code, SalesOrder.exchange_rate)
            .filter(SalesOrder.id.in_(list(sales_order_ids)), SalesOrder.is_deleted == False)
            .all()
        )
        sales_order_currency_map = {
            str(row.id): {
                "currency_code": ((row.currency_code or "") or GST_REPORT_BASE_CURRENCY).strip().upper(),
                "exchange_rate": float(row.exchange_rate or 0.0),
            }
            for row in order_rows
        }

    customer_ids = {
        customer_id
        for row in invoices
        for customer_id in [row.customer_id, row.bill_to_customer_id, row.ship_to_customer_id]
        if customer_id is not None
    }
    customers = (
        db.query(Customer)
        .filter(Customer.id.in_(list(customer_ids)), Customer.is_deleted == False)
        .all()
        if customer_ids
        else []
    )
    customer_map = {str(row.id): row for row in customers}

    duplicate_invoice_numbers = {
        invoice_number
        for invoice_number, count in (
            db.query(SalesInvoice.invoice_number, func.count(SalesInvoice.id).label("cnt"))
            .filter(
                SalesInvoice.invoice_date >= from_date,
                SalesInvoice.invoice_date <= to_date,
                SalesInvoice.status.in_(["issued", "partial_paid", "paid"]),
                SalesInvoice.is_deleted == False,
            )
            .group_by(SalesInvoice.invoice_number)
            .having(func.count(SalesInvoice.id) > 1)
            .all()
        )
    }
    for duplicate_number in sorted(duplicate_invoice_numbers):
        validation_errors.append(
            f"VAL-008 Duplicate Invoice Check failed: invoice number {duplicate_number} appears more than once"
        )

    report_rows: list[dict] = []
    problematic_records: list[dict] = []
    subtotal = {
        "invoice_amount": 0.0,
        "cgst_amount": 0.0,
        "sgst_amount": 0.0,
        "igst_amount": 0.0,
        "ugst_amount": 0.0,
        "export_amount": 0.0,
        "total_tax_amount": 0.0,
    }

    serial_no = 1
    for invoice in invoices:
        row_error_start_index = len(validation_errors)
        invoice_key = str(invoice.id)
        invoice_number = (invoice.invoice_number or "").strip()
        bill_to_id = str(invoice.bill_to_customer_id or invoice.customer_id) if (invoice.bill_to_customer_id or invoice.customer_id) else None
        ship_to_id = str(invoice.ship_to_customer_id or invoice.customer_id) if (invoice.ship_to_customer_id or invoice.customer_id) else None
        bill_to_customer = customer_map.get(bill_to_id) if bill_to_id else None
        ship_to_customer = customer_map.get(ship_to_id) if ship_to_id else None

        bill_to_name = (bill_to_customer.company_name if bill_to_customer else "").strip()
        ship_to_name = (ship_to_customer.company_name if ship_to_customer else "").strip()
        bill_to_gstin = ((bill_to_customer.gstin if bill_to_customer else "") or "").strip().upper()
        place_of_supply = (
            (invoice.supply_state or "").strip()
            or ((ship_to_customer.shipping_state if ship_to_customer else "") or "").strip()
            or ((ship_to_customer.billing_state if ship_to_customer else "") or "").strip()
            or ((bill_to_customer.shipping_state if bill_to_customer else "") or "").strip()
            or ((bill_to_customer.billing_state if bill_to_customer else "") or "").strip()
        )

        order_currency = sales_order_currency_map.get(str(invoice.sales_order_id or ""), {})
        currency = (
            (order_currency.get("currency_code") if order_currency else None)
            or (bill_to_customer.currency_code if bill_to_customer else None)
            or GST_REPORT_BASE_CURRENCY
        )
        currency = str(currency).strip().upper()

        stored_exchange_rate = float(order_currency.get("exchange_rate") or 0.0) if order_currency else 0.0

        totals = invoice_totals_map.get(invoice_key) or {
            "taxable_amount": _paise_to_amount(invoice.total_taxable_amount),
            "cgst_amount": _paise_to_amount(invoice.total_cgst),
            "sgst_amount": _paise_to_amount(invoice.total_sgst),
            "igst_amount": _paise_to_amount(invoice.total_igst),
        }

        source_invoice_amount = _round_2(totals["taxable_amount"])
        source_cgst = _round_2(totals["cgst_amount"])
        source_sgst = _round_2(totals["sgst_amount"])
        source_igst = _round_2(totals["igst_amount"])
        source_total_gst = _round_2(source_cgst + source_sgst + source_igst)

        invoice_type = _normalize_invoice_type(invoice.invoice_type, bool(invoice.is_igst))
        bill_to_country = _customer_country_for_gstr(bill_to_customer)
        bill_to_is_india = is_india_country(bill_to_country)
        is_export_transaction = invoice_type == INVOICE_TYPE_EXPORT or (not bill_to_is_india)
        display_bill_to_gstin = bill_to_gstin if bill_to_is_india else (bill_to_gstin or "N/A")
        invoice_rates = sorted(invoice_rate_map.get(invoice_key, set()))

        conversion_rate, conversion_source, conversion_error = _resolve_report_fx_rate(
            currency,
            stored_exchange_rate=stored_exchange_rate,
        )

        if not invoice.invoice_date:
            validation_errors.append(f"VAL-010 Mandatory Fields Check failed for invoice {invoice_number}: invoice date is required")
        if not invoice_number:
            validation_errors.append("VAL-010 Mandatory Fields Check failed: invoice number is required")
        if not bill_to_name:
            validation_errors.append(f"VAL-010 Mandatory Fields Check failed for invoice {invoice_number}: bill-to party name is required")
        if not ship_to_name:
            validation_errors.append(f"VAL-010 Mandatory Fields Check failed for invoice {invoice_number}: ship-to party name is required")
        if not is_export_transaction:
            if not bill_to_gstin:
                validation_errors.append(f"VAL-010 Mandatory Fields Check failed for invoice {invoice_number}: billing GSTIN is required")
            elif not GSTIN_REGEX.match(bill_to_gstin):
                validation_errors.append(
                    f"VAL-002 GSTIN Format Check failed for invoice {invoice_number}: GSTIN {bill_to_gstin} is invalid"
                )
        if not place_of_supply:
            validation_errors.append(f"VAL-010 Mandatory Fields Check failed for invoice {invoice_number}: place of supply is required")
        if source_invoice_amount <= 0:
            validation_errors.append(
                f"VAL-010 Mandatory Fields Check failed for invoice {invoice_number}: invoice amount must be positive"
            )
        if len(currency) != 3 or not currency.isalpha():
            validation_errors.append(f"VAL-010 Mandatory Fields Check failed for invoice {invoice_number}: currency must be valid ISO-4217 code")
        if conversion_error:
            validation_errors.append(
                f"VAL-009 Currency Consistency failed for invoice {invoice_number}: {conversion_error}"
            )

        has_positive_tax = any(rate > 0 for rate in invoice_rates) or source_total_gst > 0.01

        if abs(source_total_gst - _round_2(source_cgst + source_sgst + source_igst)) > 0.01:
            validation_errors.append(
                f"VAL-005 Total Tax Verification failed for invoice {invoice_number}: invoice tax totals are inconsistent"
            )

        if invoice_type == INVOICE_TYPE_WITHIN_STATE:
            if abs(source_igst) > 0.01:
                validation_errors.append(
                    f"VAL-004 Intra/Inter State Logic failed for invoice {invoice_number}: IGST must be zero for intra-state supply"
                )
            if has_positive_tax and (source_cgst <= 0 or source_sgst <= 0):
                validation_errors.append(
                    f"VAL-004 Intra/Inter State Logic failed for invoice {invoice_number}: CGST and SGST must be populated"
                )

        if invoice_type == INVOICE_TYPE_OTHER_STATES:
            if abs(source_cgst) > 0.01 or abs(source_sgst) > 0.01:
                validation_errors.append(
                    f"VAL-004 Intra/Inter State Logic failed for invoice {invoice_number}: CGST and SGST must be zero for inter-state supply"
                )
            if has_positive_tax and source_igst <= 0:
                validation_errors.append(
                    f"VAL-004 Intra/Inter State Logic failed for invoice {invoice_number}: IGST must be populated"
                )

        if invoice_type == INVOICE_TYPE_UNION_TERRITORY:
            if abs(source_igst) > 0.01:
                validation_errors.append(
                    f"VAL-004 Intra/Inter State Logic failed for invoice {invoice_number}: IGST must be zero for Union Territory supply"
                )
            if has_positive_tax and (source_cgst <= 0 or source_sgst <= 0):
                validation_errors.append(
                    f"VAL-004 Intra/Inter State Logic failed for invoice {invoice_number}: CGST and UGST must be populated"
                )

        if invoice_type == INVOICE_TYPE_EXPORT:
            if abs(source_cgst) > 0.01 or abs(source_sgst) > 0.01 or abs(source_igst) > 0.01:
                validation_errors.append(
                    f"VAL-004 Intra/Inter State Logic failed for invoice {invoice_number}: export transaction must be zero-rated"
                )
            if source_invoice_amount <= 0:
                validation_errors.append(
                    f"VAL-010 Mandatory Fields Check failed for invoice {invoice_number}: export amount must be populated"
                )

        row_errors = validation_errors[row_error_start_index:]
        if row_errors:
            problematic_records.append(
                {
                    "document_type": "invoice",
                    "document_no": invoice_number,
                    "document_date": _format_ddmmyyyy(invoice.invoice_date),
                    "errors": row_errors[:20],
                }
            )

        taxable_amount = _convert_with_rate(source_invoice_amount, float(conversion_rate or 1.0))
        cgst_amount = _convert_with_rate(source_cgst, float(conversion_rate or 1.0))
        sgst_amount = _convert_with_rate(source_sgst, float(conversion_rate or 1.0))
        igst_amount = _convert_with_rate(source_igst, float(conversion_rate or 1.0))
        ugst_amount = 0.0
        export_amount = 0.0

        if invoice_type == INVOICE_TYPE_UNION_TERRITORY:
            ugst_amount = sgst_amount
            sgst_amount = 0.0
        elif invoice_type == INVOICE_TYPE_EXPORT:
            export_amount = taxable_amount
            cgst_amount = 0.0
            sgst_amount = 0.0
            igst_amount = 0.0
            ugst_amount = 0.0

        tax_percent = _round_2(invoice_rates[0]) if len(invoice_rates) == 1 else None
        total_tax_amount = _round_2(cgst_amount + sgst_amount + igst_amount + ugst_amount + export_amount)

        report_rows.append(
            {
                "s_no": serial_no,
                "sales_invoice_date": _format_ddmmyyyy(invoice.invoice_date),
                "sales_invoice_no": invoice_number,
                "bill_to_party_name": bill_to_name,
                "bill_to_party_gstin_no": display_bill_to_gstin,
                "place_of_supply": place_of_supply,
                "ship_to_party_name": ship_to_name,
                "invoice_amount": taxable_amount,
                "currency": GST_REPORT_BASE_CURRENCY,
                "source_currency": currency,
                "conversion_rate_to_inr": _round_2(float(conversion_rate or 1.0)),
                "conversion_source": conversion_source,
                "tax_percent": tax_percent,
                "cgst_amount": cgst_amount,
                "sgst_amount": sgst_amount,
                "igst_amount": igst_amount,
                "ugst_amount": ugst_amount,
                "export_amount": export_amount,
                "total_tax_amount": total_tax_amount,
            }
        )
        serial_no += 1

        subtotal["invoice_amount"] = _round_2(subtotal["invoice_amount"] + taxable_amount)
        subtotal["cgst_amount"] = _round_2(subtotal["cgst_amount"] + cgst_amount)
        subtotal["sgst_amount"] = _round_2(subtotal["sgst_amount"] + sgst_amount)
        subtotal["igst_amount"] = _round_2(subtotal["igst_amount"] + igst_amount)
        subtotal["ugst_amount"] = _round_2(subtotal["ugst_amount"] + ugst_amount)
        subtotal["export_amount"] = _round_2(subtotal["export_amount"] + export_amount)
        subtotal["total_tax_amount"] = _round_2(subtotal["total_tax_amount"] + total_tax_amount)

    if validation_errors and strict_validation:
        _log_gst_report_event(
            db,
            user_id=current_user.id,
            action="GENERATE_GSTR1",
            report_type="GSTR-1",
            start_date=from_date,
            end_date=to_date,
            frequency=normalized_frequency,
            status="failed",
            details={
                "error_count": len(validation_errors),
                "strict_validation": True,
            },
        )
        log_audit_event(
            db,
            action="REPORT:GSTR1_GENERATION_FAILED",
            resource_type="reports",
            status="failure",
            user_id=current_user.id,
            details={
                "report": "gstr1",
                "from_date": from_date.isoformat(),
                "to_date": to_date.isoformat(),
                "frequency": normalized_frequency,
                "error_count": len(validation_errors),
                "strict_validation": True,
            },
        )
        db.commit()
        _raise_gstr1_validation_error(validation_errors)

    summary = {
        "total_taxable": _amount_to_paise(sum(row.get("invoice_amount", 0.0) for row in report_rows)),
        "total_cgst": _amount_to_paise(sum(row.get("cgst_amount", 0.0) for row in report_rows)),
        "total_sgst": _amount_to_paise(sum(row.get("sgst_amount", 0.0) for row in report_rows)),
        "total_igst": _amount_to_paise(sum(row.get("igst_amount", 0.0) for row in report_rows)),
    }

    _log_gst_report_event(
        db,
        user_id=current_user.id,
        action="GENERATE_GSTR1",
        report_type="GSTR-1",
        start_date=from_date,
        end_date=to_date,
        frequency=normalized_frequency,
        status="success",
        details={
            "row_count": len(report_rows),
            "validation_error_count": len(validation_errors),
            "strict_validation": strict_validation,
        },
    )

    log_audit_event(
        db,
        action="REPORT:GSTR1_GENERATED_WITH_WARNINGS" if validation_errors else "REPORT:GSTR1_GENERATED",
        resource_type="reports",
        status="success" if not validation_errors else "warning",
        user_id=current_user.id,
        details={
            "report": "gstr1",
            "from_date": from_date.isoformat(),
            "to_date": to_date.isoformat(),
            "frequency": normalized_frequency,
            "row_count": len(report_rows),
            "generated_at": datetime.utcnow().isoformat(),
            "validation_error_count": len(validation_errors),
            "strict_validation": strict_validation,
        },
    )
    db.commit()

    return {
        "report_title": "GSTR-1 (Sales / Output Tax Report)",
        "frequency": normalized_frequency,
        "frequency_label": frequency_label,
        "from_date": from_date.isoformat(),
        "to_date": to_date.isoformat(),
        "from_date_display": _format_ddmmyyyy(from_date),
        "to_date_display": _format_ddmmyyyy(to_date),
        "summary": summary,
        "count": len(report_rows),
        "items": report_rows,
        "subtotal": subtotal,
        "strict_validation": strict_validation,
        "validation_error_count": len(validation_errors),
        "validation_errors": validation_errors[:100],
        "problematic_records": problematic_records[:200],
    }


@router.get("/gstr1/export")
async def gstr1_export(
    from_date: date,
    to_date: date,
    frequency: str = Query(default="monthly"),
    format: str = Query(default="xlsx"),
    strict_validation: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("reports_read")),
):
    format_token = (format or "xlsx").strip().lower()
    if format_token not in {"xlsx", "pdf"}:
        raise HTTPException(status_code=422, detail="Invalid format. Allowed values: xlsx, pdf")

    payload = await gstr1_report(
        from_date=from_date,
        to_date=to_date,
        frequency=frequency,
        strict_validation=strict_validation,
        db=db,
        current_user=current_user,
    )

    report_items = payload.get("items", [])
    subtotal = payload.get("subtotal", {})
    filename_base = f"gstr1_{from_date.isoformat()}_{to_date.isoformat()}"

    if format_token == "xlsx":
        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws.title = "GSTR-1"

        ws.append([payload.get("report_title", "GSTR-1 (Sales / Output Tax Report)")])
        ws.append([
            f"Period: {payload.get('from_date_display') or from_date.isoformat()} to {payload.get('to_date_display') or to_date.isoformat()} | Frequency: {payload.get('frequency_label', '')}"
        ])
        ws.append([])

        headers = [
            "S.No",
            "Sales Invoice Date",
            "Sales Invoice No",
            "Name of the Bill to Party",
            "Bill to Party GSTIN No",
            "Place of Supply",
            "Name of the Ship to Party",
            "Invoice Amount",
            "Currency",
            "Tax %",
            "CGST Amount",
            "SGST Amount",
            "IGST Amount",
            "UGST Amount",
            "Export",
            "Total Tax Amount",
        ]
        ws.append(headers)

        for row in report_items:
            ws.append([
                row.get("s_no"),
                row.get("sales_invoice_date"),
                row.get("sales_invoice_no"),
                row.get("bill_to_party_name"),
                row.get("bill_to_party_gstin_no"),
                row.get("place_of_supply"),
                row.get("ship_to_party_name"),
                row.get("invoice_amount"),
                row.get("currency"),
                row.get("tax_percent"),
                row.get("cgst_amount"),
                row.get("sgst_amount"),
                row.get("igst_amount"),
                row.get("ugst_amount"),
                row.get("export_amount"),
                row.get("total_tax_amount"),
            ])

        ws.append([
            "",
            "",
            "",
            "",
            "",
            "",
            "Sub Total",
            subtotal.get("invoice_amount", 0.0),
            "",
            "",
            subtotal.get("cgst_amount", 0.0),
            subtotal.get("sgst_amount", 0.0),
            subtotal.get("igst_amount", 0.0),
            subtotal.get("ugst_amount", 0.0),
            subtotal.get("export_amount", 0.0),
            subtotal.get("total_tax_amount", 0.0),
        ])

        stream = BytesIO()
        wb.save(stream)
        stream.seek(0)

        log_audit_event(
            db,
            action="REPORT:GSTR1_EXPORTED_XLSX",
            resource_type="reports",
            status="success",
            user_id=current_user.id,
            details={
                "report": "gstr1",
                "from_date": from_date.isoformat(),
                "to_date": to_date.isoformat(),
                "frequency": payload.get("frequency"),
                "generated_at": datetime.utcnow().isoformat(),
            },
        )
        _log_gst_report_event(
            db,
            user_id=current_user.id,
            action="EXPORT_GSTR1_XLSX",
            report_type="GSTR-1",
            start_date=from_date,
            end_date=to_date,
            frequency=payload.get("frequency", "monthly"),
            status="success",
            details={"format": "xlsx", "row_count": len(report_items)},
        )
        db.commit()

        return StreamingResponse(
            stream,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename_base}.xlsx"},
        )

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    stream = BytesIO()
    doc = SimpleDocTemplate(stream, pagesize=landscape(A4), leftMargin=18, rightMargin=18, topMargin=18, bottomMargin=18)
    styles = getSampleStyleSheet()

    story = [
        Paragraph(payload.get("report_title", "GSTR-1 (Sales / Output Tax Report)"), styles["Heading2"]),
        Paragraph(
            f"Period: {payload.get('from_date_display') or from_date.isoformat()} to {payload.get('to_date_display') or to_date.isoformat()} | Frequency: {payload.get('frequency_label', '')}",
            styles["Normal"],
        ),
        Spacer(1, 8),
    ]

    table_data = [[
        "S.No", "Sales Invoice Date", "Sales Invoice No", "Bill To", "Bill GSTIN", "Place", "Ship To",
        "Invoice Amount", "Currency", "Tax %", "CGST", "SGST", "IGST", "UGST", "Export", "Total Tax",
    ]]

    for row in report_items:
        table_data.append([
            row.get("s_no", ""),
            row.get("sales_invoice_date", ""),
            row.get("sales_invoice_no", ""),
            row.get("bill_to_party_name", ""),
            row.get("bill_to_party_gstin_no", ""),
            row.get("place_of_supply", ""),
            row.get("ship_to_party_name", ""),
            f"{float(row.get('invoice_amount', 0.0)):.2f}",
            row.get("currency", ""),
            _format_tax_percent(row.get("tax_percent")),
            f"{float(row.get('cgst_amount', 0.0)):.2f}",
            f"{float(row.get('sgst_amount', 0.0)):.2f}",
            f"{float(row.get('igst_amount', 0.0)):.2f}",
            f"{float(row.get('ugst_amount', 0.0)):.2f}",
            f"{float(row.get('export_amount', 0.0)):.2f}",
            f"{float(row.get('total_tax_amount', 0.0)):.2f}",
        ])

    table_data.append([
        "", "", "", "", "", "", "Sub Total",
        f"{float(subtotal.get('invoice_amount', 0.0)):.2f}",
        "",
        "",
        f"{float(subtotal.get('cgst_amount', 0.0)):.2f}",
        f"{float(subtotal.get('sgst_amount', 0.0)):.2f}",
        f"{float(subtotal.get('igst_amount', 0.0)):.2f}",
        f"{float(subtotal.get('ugst_amount', 0.0)):.2f}",
        f"{float(subtotal.get('export_amount', 0.0)):.2f}",
        f"{float(subtotal.get('total_tax_amount', 0.0)):.2f}",
    ])

    table = Table(table_data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E5E7EB")),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#9CA3AF")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(table)

    doc.build(story)
    stream.seek(0)

    log_audit_event(
        db,
        action="REPORT:GSTR1_EXPORTED_PDF",
        resource_type="reports",
        status="success",
        user_id=current_user.id,
        details={
            "report": "gstr1",
            "from_date": from_date.isoformat(),
            "to_date": to_date.isoformat(),
            "frequency": payload.get("frequency"),
            "generated_at": datetime.utcnow().isoformat(),
        },
    )
    _log_gst_report_event(
        db,
        user_id=current_user.id,
        action="EXPORT_GSTR1_PDF",
        report_type="GSTR-1",
        start_date=from_date,
        end_date=to_date,
        frequency=payload.get("frequency", "monthly"),
        status="success",
        details={"format": "pdf", "row_count": len(report_items)},
    )
    db.commit()

    return StreamingResponse(
        stream,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename_base}.pdf"},
    )


@router.get("/gstr3b")
async def gstr3b_report(
    from_date: date,
    to_date: date,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("reports_read")),
):
    _ensure_finance_tax_user(current_user)
    _ensure_valid_date_range(from_date, to_date)
    sales_rows = db.query(SalesInvoice).filter(
        SalesInvoice.invoice_date >= from_date,
        SalesInvoice.invoice_date <= to_date,
        SalesInvoice.status.in_(["issued", "partial_paid", "paid"]),
        SalesInvoice.is_deleted == False,
    ).all()
    purchase_rows = db.query(GoodsReceiptNote).filter(
        GoodsReceiptNote.receipt_date >= from_date,
        GoodsReceiptNote.receipt_date <= to_date,
        GoodsReceiptNote.status == "confirmed",
        GoodsReceiptNote.is_deleted == False,
    ).all()

    output_tax = sum(row.total_gst for row in sales_rows)
    input_tax = sum(row.total_gst for row in purchase_rows)

    _log_gst_report_event(
        db,
        user_id=current_user.id,
        action="GENERATE_GSTR3B",
        report_type="GSTR-3B",
        start_date=from_date,
        end_date=to_date,
        frequency="monthly",
        status="success",
        details={
            "output_tax": int(output_tax),
            "itc": int(input_tax),
        },
    )

    return {
        "output_tax": int(output_tax),
        "itc": int(input_tax),
        "net_tax_payable": int(output_tax - input_tax),
    }


@router.get("/gstr2")
async def gstr2_report(
    from_date: date,
    to_date: date,
    frequency: str = Query(default="monthly"),
    strict_validation: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("reports_read")),
):
    _ensure_finance_tax_user(current_user)

    normalized_frequency, frequency_label = _normalize_frequency(frequency)
    _validate_frequency_date_window(from_date, to_date, normalized_frequency)

    grns = (
        db.query(GoodsReceiptNote)
        .filter(
            GoodsReceiptNote.receipt_date >= from_date,
            GoodsReceiptNote.receipt_date <= to_date,
            GoodsReceiptNote.status == "confirmed",
            GoodsReceiptNote.is_deleted == False,
        )
        .order_by(GoodsReceiptNote.receipt_date.asc(), GoodsReceiptNote.grn_number.asc())
        .all()
    )

    grn_ids = [row.id for row in grns]
    grn_id_map = {str(row.id): row for row in grns}

    grn_totals_map: dict[str, dict[str, float]] = {}
    grn_rate_map: dict[str, set[float]] = defaultdict(set)
    validation_errors: list[str] = []

    if grn_ids:
        item_rows = (
            db.query(
                GRNItem.grn_id,
                func.sum(GRNItem.taxable_amount).label("taxable_amount"),
                func.sum(GRNItem.cgst_amount).label("cgst_amount"),
                func.sum(GRNItem.sgst_amount).label("sgst_amount"),
                func.sum(GRNItem.igst_amount).label("igst_amount"),
            )
            .filter(
                GRNItem.grn_id.in_(grn_ids),
                GRNItem.is_deleted == False,
            )
            .group_by(GRNItem.grn_id)
            .all()
        )
        for item in item_rows:
            grn_key = str(item.grn_id)
            grn_totals_map[grn_key] = {
                "taxable_amount": _paise_to_amount(item.taxable_amount),
                "cgst_amount": _paise_to_amount(item.cgst_amount),
                "sgst_amount": _paise_to_amount(item.sgst_amount),
                "igst_amount": _paise_to_amount(item.igst_amount),
            }

        rate_rows = (
            db.query(GRNItem.grn_id, GRNItem.gst_rate)
            .filter(
                GRNItem.grn_id.in_(grn_ids),
                GRNItem.is_deleted == False,
            )
            .all()
        )
        for item in rate_rows:
            grn_key = str(item.grn_id)
            slab = _round_2(float(item.gst_rate or 0.0))
            if slab not in GST_ALLOWED_SLABS:
                grn = grn_id_map.get(grn_key)
                grn_number = grn.grn_number if grn else grn_key
                validation_errors.append(
                    f"VAL-003 Tax Rate Validity failed for GRN {grn_number}: invalid GST slab {slab}"
                )
            grn_rate_map[grn_key].add(slab)

    purchase_order_ids = {row.purchase_order_id for row in grns if row.purchase_order_id is not None}
    purchase_order_currency_map: dict[str, dict[str, float | str | None]] = {}
    if purchase_order_ids:
        po_rows = (
            db.query(PurchaseOrder.id, PurchaseOrder.currency_code, PurchaseOrder.exchange_rate)
            .filter(PurchaseOrder.id.in_(list(purchase_order_ids)), PurchaseOrder.is_deleted == False)
            .all()
        )
        purchase_order_currency_map = {
            str(row.id): {
                "currency_code": ((row.currency_code or "") or GST_REPORT_BASE_CURRENCY).strip().upper(),
                "exchange_rate": float(row.exchange_rate or 0.0),
            }
            for row in po_rows
        }

    supplier_ids = {row.supplier_id for row in grns if row.supplier_id is not None}
    suppliers = (
        db.query(Supplier)
        .filter(Supplier.id.in_(list(supplier_ids)), Supplier.is_deleted == False)
        .all()
        if supplier_ids
        else []
    )
    supplier_map = {str(row.id): row for row in suppliers}

    company = db.query(Company).first()
    business_place = (
        ", ".join([part for part in [company.city if company else None, company.state if company else None] if part])
        if company else ""
    )
    if not business_place:
        business_place = (company.name if company else "") or "Primary Business Place"

    company_state_token = _normalized_state_token(company.state_code if company else None, company.state if company else None)

    duplicate_grn_numbers = {
        grn_number
        for grn_number, count in (
            db.query(GoodsReceiptNote.grn_number, func.count(GoodsReceiptNote.id).label("cnt"))
            .filter(
                GoodsReceiptNote.receipt_date >= from_date,
                GoodsReceiptNote.receipt_date <= to_date,
                GoodsReceiptNote.status == "confirmed",
                GoodsReceiptNote.is_deleted == False,
            )
            .group_by(GoodsReceiptNote.grn_number)
            .having(func.count(GoodsReceiptNote.id) > 1)
            .all()
        )
    }
    for duplicate_number in sorted(duplicate_grn_numbers):
        validation_errors.append(
            f"VAL-008 Duplicate Invoice Check failed: GRN number {duplicate_number} appears more than once"
        )

    report_rows: list[dict] = []
    problematic_records: list[dict] = []
    subtotal = {
        "grn_amount": 0.0,
        "cgst_amount": 0.0,
        "sgst_amount": 0.0,
        "igst_amount": 0.0,
        "ugst_amount": 0.0,
        "import_amount": 0.0,
        "total_tax_amount": 0.0,
    }

    serial_no = 1
    for grn in grns:
        row_error_start_index = len(validation_errors)
        grn_key = str(grn.id)
        grn_number = (grn.grn_number or "").strip()
        supplier = supplier_map.get(str(grn.supplier_id)) if grn.supplier_id else None

        supplier_name = (supplier.company_name if supplier else "").strip()
        supplier_gstin = ((supplier.gstin if supplier else "") or "").strip().upper()
        place_of_supply = ((supplier.place_of_supply if supplier else "") or (supplier.state if supplier else "") or "").strip()
        supplier_business_type = ((supplier.business_type if supplier else "domestic") or "domestic").strip().lower()
        supplier_country = ((supplier.billing_country if supplier else "") or "").strip()
        supplier_is_india = is_india_country(supplier_country) or (not supplier_country and supplier_business_type == "domestic")
        display_supplier_gstin = supplier_gstin if supplier_is_india else (supplier_gstin or "N/A")
        po_currency = purchase_order_currency_map.get(str(grn.purchase_order_id or ""), {})
        currency = (
            (po_currency.get("currency_code") if po_currency else None)
            or (supplier.currency_code if supplier else None)
            or GST_REPORT_BASE_CURRENCY
        )
        currency = str(currency).strip().upper()
        stored_exchange_rate = float(po_currency.get("exchange_rate") or 0.0) if po_currency else 0.0

        totals = grn_totals_map.get(grn_key)
        if totals is None:
            source_grn_amount = _paise_to_amount(grn.total_taxable_amount)
            source_cgst = _paise_to_amount(grn.total_cgst)
            source_sgst = _paise_to_amount(grn.total_sgst)
            source_igst = _paise_to_amount(grn.total_igst)
            source_total_gst = _paise_to_amount(grn.total_gst)
            validation_errors.append(
                f"VAL-010 Mandatory Fields Check failed for GRN {grn_number}: tax line-item totals are missing"
            )
        else:
            source_grn_amount = _round_2(totals["taxable_amount"])
            source_cgst = _round_2(totals["cgst_amount"])
            source_sgst = _round_2(totals["sgst_amount"])
            source_igst = _round_2(totals["igst_amount"])
            source_total_gst = _round_2(source_cgst + source_sgst + source_igst)
        source_total_gst = _round_2(source_cgst + source_sgst + source_igst)

        supplier_state_token = _normalized_state_token(supplier.state_code if supplier else None, supplier.state if supplier else None)
        is_import = supplier_business_type != "domestic" or (supplier_country and not supplier_is_india)
        is_ut = _is_union_territory(supplier.state_code if supplier else None, supplier.state if supplier else None)
        is_inter_state = bool(company_state_token and supplier_state_token and company_state_token != supplier_state_token)

        grn_rate_values = grn_rate_map.get(grn_key, set())
        tax_percent = _round_2(next(iter(grn_rate_values))) if len(grn_rate_values) == 1 else None
        has_positive_tax = any(slab > 0 for slab in grn_rate_values) or source_total_gst > 0.01

        conversion_rate, conversion_source, conversion_error = _resolve_report_fx_rate(
            currency,
            stored_exchange_rate=stored_exchange_rate,
        )

        if not grn.receipt_date:
            validation_errors.append(f"VAL-010 Mandatory Fields Check failed for GRN {grn_number}: GRN date is required")
        if not grn_number:
            validation_errors.append("VAL-010 Mandatory Fields Check failed: GRN number is required")
        if not supplier_name:
            validation_errors.append(f"VAL-010 Mandatory Fields Check failed for GRN {grn_number}: supplier name is required")
        if supplier_is_india:
            if not supplier_gstin:
                validation_errors.append(f"VAL-010 Mandatory Fields Check failed for GRN {grn_number}: supplier GSTIN is required")
            elif not GSTIN_REGEX.match(supplier_gstin):
                validation_errors.append(
                    f"VAL-002 GSTIN Format Check failed for GRN {grn_number}: GSTIN {supplier_gstin} is invalid"
                )
        if not place_of_supply:
            validation_errors.append(f"VAL-010 Mandatory Fields Check failed for GRN {grn_number}: place of supply is required")
        if source_grn_amount <= 0:
            validation_errors.append(
                f"VAL-010 Mandatory Fields Check failed for GRN {grn_number}: GRN amount must be positive"
            )
        if len(currency) != 3 or not currency.isalpha():
            validation_errors.append(f"VAL-010 Mandatory Fields Check failed for GRN {grn_number}: currency must be valid ISO-4217 code")
        if conversion_error:
            validation_errors.append(
                f"VAL-009 Currency Consistency failed for GRN {grn_number}: {conversion_error}"
            )

        if abs(source_total_gst - _round_2(source_cgst + source_sgst + source_igst)) > 0.01:
            validation_errors.append(
                f"VAL-005 Total Tax Verification failed for GRN {grn_number}: GRN tax totals are inconsistent"
            )

        if not is_import and is_inter_state:
            if abs(source_cgst) > 0.01 or abs(source_sgst) > 0.01:
                validation_errors.append(
                    f"VAL-004 Intra/Inter State Logic failed for GRN {grn_number}: CGST and SGST must be zero for inter-state purchase"
                )
            if has_positive_tax and source_igst <= 0:
                validation_errors.append(
                    f"VAL-004 Intra/Inter State Logic failed for GRN {grn_number}: IGST must be populated"
                )

        if not is_import and (not is_inter_state) and is_ut:
            if abs(source_igst) > 0.01:
                validation_errors.append(
                    f"VAL-004 Intra/Inter State Logic failed for GRN {grn_number}: IGST must be zero for Union Territory purchase"
                )
            if has_positive_tax and (source_cgst <= 0 or source_sgst <= 0):
                validation_errors.append(
                    f"VAL-004 Intra/Inter State Logic failed for GRN {grn_number}: CGST and UGST must be populated"
                )

        if not is_import and (not is_inter_state) and (not is_ut):
            if abs(source_igst) > 0.01:
                validation_errors.append(
                    f"VAL-004 Intra/Inter State Logic failed for GRN {grn_number}: IGST must be zero for intra-state purchase"
                )
            if has_positive_tax and (source_cgst <= 0 or source_sgst <= 0):
                validation_errors.append(
                    f"VAL-004 Intra/Inter State Logic failed for GRN {grn_number}: CGST and SGST must be populated"
                )

        if is_import and source_igst <= 0 and has_positive_tax:
            validation_errors.append(
                f"VAL-004 Intra/Inter State Logic failed for GRN {grn_number}: import IGST must be populated"
            )

        row_errors = validation_errors[row_error_start_index:]
        if row_errors:
            problematic_records.append(
                {
                    "document_type": "grn",
                    "document_no": grn_number,
                    "document_date": _format_ddmmyyyy(grn.receipt_date),
                    "errors": row_errors[:20],
                }
            )

        grn_amount = _convert_with_rate(source_grn_amount, float(conversion_rate or 1.0))
        cgst_amount = _convert_with_rate(source_cgst, float(conversion_rate or 1.0))
        sgst_amount = _convert_with_rate(source_sgst, float(conversion_rate or 1.0))
        igst_amount = _convert_with_rate(source_igst, float(conversion_rate or 1.0))
        ugst_amount = 0.0
        import_amount = 0.0

        if is_import:
            import_amount = igst_amount
            igst_amount = 0.0
            cgst_amount = 0.0
            sgst_amount = 0.0
            ugst_amount = 0.0
        elif is_ut and not is_inter_state:
            ugst_amount = sgst_amount
            sgst_amount = 0.0

        total_tax_amount = _round_2(cgst_amount + sgst_amount + igst_amount + ugst_amount + import_amount)

        report_rows.append(
            {
                "s_no": serial_no,
                "grn_date": _format_ddmmyyyy(grn.receipt_date),
                "grn_no": grn_number,
                "supplier_name": supplier_name,
                "supplier_gstin_no": display_supplier_gstin,
                "business_place": business_place,
                "place_of_supply": place_of_supply,
                "grn_amount": grn_amount,
                "currency": GST_REPORT_BASE_CURRENCY,
                "source_currency": currency,
                "conversion_rate_to_inr": _round_2(float(conversion_rate or 1.0)),
                "conversion_source": conversion_source,
                "tax_percent": tax_percent,
                "cgst_amount": cgst_amount,
                "sgst_amount": sgst_amount,
                "igst_amount": igst_amount,
                "ugst_amount": ugst_amount,
                "import_amount": import_amount,
                "total_tax_amount": total_tax_amount,
            }
        )
        serial_no += 1

        subtotal["grn_amount"] = _round_2(subtotal["grn_amount"] + grn_amount)
        subtotal["cgst_amount"] = _round_2(subtotal["cgst_amount"] + cgst_amount)
        subtotal["sgst_amount"] = _round_2(subtotal["sgst_amount"] + sgst_amount)
        subtotal["igst_amount"] = _round_2(subtotal["igst_amount"] + igst_amount)
        subtotal["ugst_amount"] = _round_2(subtotal["ugst_amount"] + ugst_amount)
        subtotal["import_amount"] = _round_2(subtotal["import_amount"] + import_amount)
        subtotal["total_tax_amount"] = _round_2(subtotal["total_tax_amount"] + total_tax_amount)

    if validation_errors and strict_validation:
        _log_gst_report_event(
            db,
            user_id=current_user.id,
            action="GENERATE_GSTR2",
            report_type="GSTR-2",
            start_date=from_date,
            end_date=to_date,
            frequency=normalized_frequency,
            status="failed",
            details={
                "error_count": len(validation_errors),
                "strict_validation": True,
            },
        )
        log_audit_event(
            db,
            action="REPORT:GSTR2_GENERATION_FAILED",
            resource_type="reports",
            status="failure",
            user_id=current_user.id,
            details={
                "report": "gstr2",
                "from_date": from_date.isoformat(),
                "to_date": to_date.isoformat(),
                "frequency": normalized_frequency,
                "error_count": len(validation_errors),
                "strict_validation": True,
            },
        )
        db.commit()
        _raise_gstr2_validation_error(validation_errors)

    summary = {
        "total_taxable": _amount_to_paise(sum(row.get("grn_amount", 0.0) for row in report_rows)),
        "total_cgst": _amount_to_paise(sum(row.get("cgst_amount", 0.0) for row in report_rows)),
        "total_sgst": _amount_to_paise(sum(row.get("sgst_amount", 0.0) for row in report_rows)),
        "total_igst": _amount_to_paise(sum(row.get("igst_amount", 0.0) for row in report_rows)),
    }

    _log_gst_report_event(
        db,
        user_id=current_user.id,
        action="GENERATE_GSTR2",
        report_type="GSTR-2",
        start_date=from_date,
        end_date=to_date,
        frequency=normalized_frequency,
        status="success",
        details={
            "row_count": len(report_rows),
            "validation_error_count": len(validation_errors),
            "strict_validation": strict_validation,
        },
    )

    log_audit_event(
        db,
        action="REPORT:GSTR2_GENERATED_WITH_WARNINGS" if validation_errors else "REPORT:GSTR2_GENERATED",
        resource_type="reports",
        status="success" if not validation_errors else "warning",
        user_id=current_user.id,
        details={
            "report": "gstr2",
            "from_date": from_date.isoformat(),
            "to_date": to_date.isoformat(),
            "frequency": normalized_frequency,
            "row_count": len(report_rows),
            "generated_at": datetime.utcnow().isoformat(),
            "validation_error_count": len(validation_errors),
            "strict_validation": strict_validation,
        },
    )
    db.commit()

    return {
        "report_title": "GSTR-2 (Purchase / Input Tax Report)",
        "frequency": normalized_frequency,
        "frequency_label": frequency_label,
        "from_date": from_date.isoformat(),
        "to_date": to_date.isoformat(),
        "from_date_display": _format_ddmmyyyy(from_date),
        "to_date_display": _format_ddmmyyyy(to_date),
        "summary": summary,
        "count": len(report_rows),
        "items": report_rows,
        "subtotal": subtotal,
        "strict_validation": strict_validation,
        "validation_error_count": len(validation_errors),
        "validation_errors": validation_errors[:100],
        "problematic_records": problematic_records[:200],
    }


@router.get("/gstr2/export")
async def gstr2_export(
    from_date: date,
    to_date: date,
    frequency: str = Query(default="monthly"),
    format: str = Query(default="xlsx"),
    strict_validation: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("reports_read")),
):
    format_token = (format or "xlsx").strip().lower()
    if format_token not in {"xlsx", "pdf"}:
        raise HTTPException(status_code=422, detail="Invalid format. Allowed values: xlsx, pdf")

    payload = await gstr2_report(
        from_date=from_date,
        to_date=to_date,
        frequency=frequency,
        strict_validation=strict_validation,
        db=db,
        current_user=current_user,
    )

    report_items = payload.get("items", [])
    subtotal = payload.get("subtotal", {})
    filename_base = f"gstr2_{from_date.isoformat()}_{to_date.isoformat()}"

    if format_token == "xlsx":
        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws.title = "GSTR-2"

        ws.append([payload.get("report_title", "GSTR-2 (Purchase / Input Tax Report)")])
        ws.append([
            f"Period: {payload.get('from_date_display') or from_date.isoformat()} to {payload.get('to_date_display') or to_date.isoformat()} | Frequency: {payload.get('frequency_label', '')}"
        ])
        ws.append([])

        headers = [
            "S.No",
            "GRN Date",
            "GRN No",
            "Name of the Supplier",
            "Supplier GSTIN No",
            "Business Place",
            "Place of Supply",
            "GRN Amount",
            "Currency",
            "Tax %",
            "CGST Amount",
            "SGST Amount",
            "IGST Amount",
            "UGST Amount",
            "Import",
            "Total Tax Amount",
        ]
        ws.append(headers)

        for row in report_items:
            ws.append([
                row.get("s_no"),
                row.get("grn_date"),
                row.get("grn_no"),
                row.get("supplier_name"),
                row.get("supplier_gstin_no"),
                row.get("business_place"),
                row.get("place_of_supply"),
                row.get("grn_amount"),
                row.get("currency"),
                row.get("tax_percent"),
                row.get("cgst_amount"),
                row.get("sgst_amount"),
                row.get("igst_amount"),
                row.get("ugst_amount"),
                row.get("import_amount"),
                row.get("total_tax_amount"),
            ])

        ws.append([
            "",
            "",
            "",
            "",
            "",
            "",
            "Sub Total",
            subtotal.get("grn_amount", 0.0),
            "",
            "",
            subtotal.get("cgst_amount", 0.0),
            subtotal.get("sgst_amount", 0.0),
            subtotal.get("igst_amount", 0.0),
            subtotal.get("ugst_amount", 0.0),
            subtotal.get("import_amount", 0.0),
            subtotal.get("total_tax_amount", 0.0),
        ])

        stream = BytesIO()
        wb.save(stream)
        stream.seek(0)

        log_audit_event(
            db,
            action="REPORT:GSTR2_EXPORTED_XLSX",
            resource_type="reports",
            status="success",
            user_id=current_user.id,
            details={
                "report": "gstr2",
                "from_date": from_date.isoformat(),
                "to_date": to_date.isoformat(),
                "frequency": payload.get("frequency"),
                "generated_at": datetime.utcnow().isoformat(),
            },
        )
        _log_gst_report_event(
            db,
            user_id=current_user.id,
            action="EXPORT_GSTR2_XLSX",
            report_type="GSTR-2",
            start_date=from_date,
            end_date=to_date,
            frequency=payload.get("frequency", "monthly"),
            status="success",
            details={"format": "xlsx", "row_count": len(report_items)},
        )
        db.commit()

        return StreamingResponse(
            stream,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename_base}.xlsx"},
        )

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    stream = BytesIO()
    doc = SimpleDocTemplate(stream, pagesize=landscape(A4), leftMargin=18, rightMargin=18, topMargin=18, bottomMargin=18)
    styles = getSampleStyleSheet()

    story = [
        Paragraph(payload.get("report_title", "GSTR-2 (Purchase / Input Tax Report)"), styles["Heading2"]),
        Paragraph(
            f"Period: {payload.get('from_date_display') or from_date.isoformat()} to {payload.get('to_date_display') or to_date.isoformat()} | Frequency: {payload.get('frequency_label', '')}",
            styles["Normal"],
        ),
        Spacer(1, 8),
    ]

    table_data = [[
        "S.No", "GRN Date", "GRN No", "Supplier", "Supplier GSTIN", "Business Place", "Place of Supply",
        "GRN Amount", "Currency", "Tax %", "CGST", "SGST", "IGST", "UGST", "Import", "Total Tax",
    ]]

    for row in report_items:
        table_data.append([
            row.get("s_no", ""),
            row.get("grn_date", ""),
            row.get("grn_no", ""),
            row.get("supplier_name", ""),
            row.get("supplier_gstin_no", ""),
            row.get("business_place", ""),
            row.get("place_of_supply", ""),
            f"{float(row.get('grn_amount', 0.0)):.2f}",
            row.get("currency", ""),
            _format_tax_percent(row.get("tax_percent")),
            f"{float(row.get('cgst_amount', 0.0)):.2f}",
            f"{float(row.get('sgst_amount', 0.0)):.2f}",
            f"{float(row.get('igst_amount', 0.0)):.2f}",
            f"{float(row.get('ugst_amount', 0.0)):.2f}",
            f"{float(row.get('import_amount', 0.0)):.2f}",
            f"{float(row.get('total_tax_amount', 0.0)):.2f}",
        ])

    table_data.append([
        "", "", "", "", "", "", "Sub Total",
        f"{float(subtotal.get('grn_amount', 0.0)):.2f}",
        "",
        "",
        f"{float(subtotal.get('cgst_amount', 0.0)):.2f}",
        f"{float(subtotal.get('sgst_amount', 0.0)):.2f}",
        f"{float(subtotal.get('igst_amount', 0.0)):.2f}",
        f"{float(subtotal.get('ugst_amount', 0.0)):.2f}",
        f"{float(subtotal.get('import_amount', 0.0)):.2f}",
        f"{float(subtotal.get('total_tax_amount', 0.0)):.2f}",
    ])

    table = Table(table_data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E5E7EB")),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#9CA3AF")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(table)

    doc.build(story)
    stream.seek(0)

    log_audit_event(
        db,
        action="REPORT:GSTR2_EXPORTED_PDF",
        resource_type="reports",
        status="success",
        user_id=current_user.id,
        details={
            "report": "gstr2",
            "from_date": from_date.isoformat(),
            "to_date": to_date.isoformat(),
            "frequency": payload.get("frequency"),
            "generated_at": datetime.utcnow().isoformat(),
        },
    )
    _log_gst_report_event(
        db,
        user_id=current_user.id,
        action="EXPORT_GSTR2_PDF",
        report_type="GSTR-2",
        start_date=from_date,
        end_date=to_date,
        frequency=payload.get("frequency", "monthly"),
        status="success",
        details={"format": "pdf", "row_count": len(report_items)},
    )
    db.commit()

    return StreamingResponse(
        stream,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename_base}.pdf"},
    )


@router.get("/gst-reconciliation")
async def gst_reconciliation_report(
    from_date: date,
    to_date: date,
    frequency: str = Query(default="monthly"),
    strict_validation: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("reports_read")),
):
    _ensure_finance_tax_user(current_user)

    gstr1_payload = await gstr1_report(
        from_date=from_date,
        to_date=to_date,
        frequency=frequency,
        strict_validation=strict_validation,
        db=db,
        current_user=current_user,
    )
    gstr2_payload = await gstr2_report(
        from_date=from_date,
        to_date=to_date,
        frequency=frequency,
        strict_validation=strict_validation,
        db=db,
        current_user=current_user,
    )

    company = db.query(Company).first()
    business_place = (
        ", ".join([part for part in [company.city if company else None, company.state if company else None] if part])
        if company else ""
    )
    if not business_place:
        business_place = (company.name if company else "") or "Primary Business Place"

    items: list[dict] = []
    running_s_no = 1

    subtotal_input_tax = {
        "transaction_amount": 0.0,
        "cgst_amount": 0.0,
        "sgst_amount": 0.0,
        "igst_amount": 0.0,
        "ugst_amount": 0.0,
        "import_export_amount": 0.0,
        "total_tax_amount": 0.0,
    }
    subtotal_output_tax = {
        "transaction_amount": 0.0,
        "cgst_amount": 0.0,
        "sgst_amount": 0.0,
        "igst_amount": 0.0,
        "ugst_amount": 0.0,
        "import_export_amount": 0.0,
        "total_tax_amount": 0.0,
    }

    for row in gstr2_payload.get("items", []):
        amount = _round_2(float(row.get("grn_amount", 0.0)))
        cgst_amount = _round_2(float(row.get("cgst_amount", 0.0)))
        sgst_amount = _round_2(float(row.get("sgst_amount", 0.0)))
        igst_amount = _round_2(float(row.get("igst_amount", 0.0)))
        ugst_amount = _round_2(float(row.get("ugst_amount", 0.0)))
        import_export_amount = _round_2(float(row.get("import_amount", 0.0)))
        total_tax_amount = _round_2(float(row.get("total_tax_amount", 0.0)))

        items.append(
            {
                "s_no": running_s_no,
                "tax_type": "Input Tax (Purchase)",
                "date": row.get("grn_date"),
                "name_of_partner": row.get("supplier_name", ""),
                "partner_gstin_no": row.get("supplier_gstin_no", ""),
                "business_place": row.get("business_place") or business_place,
                "place_of_supply": row.get("place_of_supply", ""),
                "grn_or_invoice_amount": amount,
                "currency": row.get("currency", "INR"),
                "tax_percent": _coerce_tax_percent(row.get("tax_percent")),
                "cgst_amount": cgst_amount,
                "sgst_amount": sgst_amount,
                "igst_amount": igst_amount,
                "ugst_amount": ugst_amount,
                "import_export_amount": import_export_amount,
                "total_tax_amount": total_tax_amount,
                "sub_total_input_tax": None,
                "sub_total_output_tax": None,
                "difference_amount": None,
            }
        )
        running_s_no += 1

        subtotal_input_tax["transaction_amount"] = _round_2(subtotal_input_tax["transaction_amount"] + amount)
        subtotal_input_tax["cgst_amount"] = _round_2(subtotal_input_tax["cgst_amount"] + cgst_amount)
        subtotal_input_tax["sgst_amount"] = _round_2(subtotal_input_tax["sgst_amount"] + sgst_amount)
        subtotal_input_tax["igst_amount"] = _round_2(subtotal_input_tax["igst_amount"] + igst_amount)
        subtotal_input_tax["ugst_amount"] = _round_2(subtotal_input_tax["ugst_amount"] + ugst_amount)
        subtotal_input_tax["import_export_amount"] = _round_2(subtotal_input_tax["import_export_amount"] + import_export_amount)
        subtotal_input_tax["total_tax_amount"] = _round_2(subtotal_input_tax["total_tax_amount"] + total_tax_amount)

    for row in gstr1_payload.get("items", []):
        amount = _round_2(float(row.get("invoice_amount", 0.0)))
        cgst_amount = _round_2(float(row.get("cgst_amount", 0.0)))
        sgst_amount = _round_2(float(row.get("sgst_amount", 0.0)))
        igst_amount = _round_2(float(row.get("igst_amount", 0.0)))
        ugst_amount = _round_2(float(row.get("ugst_amount", 0.0)))
        import_export_amount = _round_2(float(row.get("export_amount", 0.0)))
        total_tax_amount = _round_2(float(row.get("total_tax_amount", 0.0)))

        items.append(
            {
                "s_no": running_s_no,
                "tax_type": "Output Tax (Sales)",
                "date": row.get("sales_invoice_date"),
                "name_of_partner": row.get("bill_to_party_name", ""),
                "partner_gstin_no": row.get("bill_to_party_gstin_no", ""),
                "business_place": business_place,
                "place_of_supply": row.get("place_of_supply", ""),
                "grn_or_invoice_amount": amount,
                "currency": row.get("currency", "INR"),
                "tax_percent": _coerce_tax_percent(row.get("tax_percent")),
                "cgst_amount": cgst_amount,
                "sgst_amount": sgst_amount,
                "igst_amount": igst_amount,
                "ugst_amount": ugst_amount,
                "import_export_amount": import_export_amount,
                "total_tax_amount": total_tax_amount,
                "sub_total_input_tax": None,
                "sub_total_output_tax": None,
                "difference_amount": None,
            }
        )
        running_s_no += 1

        subtotal_output_tax["transaction_amount"] = _round_2(subtotal_output_tax["transaction_amount"] + amount)
        subtotal_output_tax["cgst_amount"] = _round_2(subtotal_output_tax["cgst_amount"] + cgst_amount)
        subtotal_output_tax["sgst_amount"] = _round_2(subtotal_output_tax["sgst_amount"] + sgst_amount)
        subtotal_output_tax["igst_amount"] = _round_2(subtotal_output_tax["igst_amount"] + igst_amount)
        subtotal_output_tax["ugst_amount"] = _round_2(subtotal_output_tax["ugst_amount"] + ugst_amount)
        subtotal_output_tax["import_export_amount"] = _round_2(subtotal_output_tax["import_export_amount"] + import_export_amount)
        subtotal_output_tax["total_tax_amount"] = _round_2(subtotal_output_tax["total_tax_amount"] + total_tax_amount)

    difference_amount = {
        "transaction_amount": _round_2(subtotal_output_tax["transaction_amount"] - subtotal_input_tax["transaction_amount"]),
        "cgst_amount": _round_2(subtotal_output_tax["cgst_amount"] - subtotal_input_tax["cgst_amount"]),
        "sgst_amount": _round_2(subtotal_output_tax["sgst_amount"] - subtotal_input_tax["sgst_amount"]),
        "igst_amount": _round_2(subtotal_output_tax["igst_amount"] - subtotal_input_tax["igst_amount"]),
        "ugst_amount": _round_2(subtotal_output_tax["ugst_amount"] - subtotal_input_tax["ugst_amount"]),
        "import_export_amount": _round_2(subtotal_output_tax["import_export_amount"] - subtotal_input_tax["import_export_amount"]),
        "total_tax_amount": _round_2(subtotal_output_tax["total_tax_amount"] - subtotal_input_tax["total_tax_amount"]),
    }

    validation_errors = [
        *(gstr1_payload.get("validation_errors", []) or []),
        *(gstr2_payload.get("validation_errors", []) or []),
    ]
    problematic_records = [
        *(gstr1_payload.get("problematic_records", []) or []),
        *(gstr2_payload.get("problematic_records", []) or []),
    ]

    _log_gst_report_event(
        db,
        user_id=current_user.id,
        action="GENERATE_GST_RECONCILIATION",
        report_type="GST_RECONCILIATION",
        start_date=from_date,
        end_date=to_date,
        frequency=gstr1_payload.get("frequency", "monthly"),
        status="success",
        details={
            "row_count": len(items),
            "validation_error_count": len(validation_errors),
            "strict_validation": strict_validation,
        },
    )

    log_audit_event(
        db,
        action="REPORT:GST_RECONCILIATION_GENERATED_WITH_WARNINGS" if validation_errors else "REPORT:GST_RECONCILIATION_GENERATED",
        resource_type="reports",
        status="success" if not validation_errors else "warning",
        user_id=current_user.id,
        details={
            "report": "gst_reconciliation",
            "from_date": from_date.isoformat(),
            "to_date": to_date.isoformat(),
            "frequency": gstr1_payload.get("frequency", "monthly"),
            "row_count": len(items),
            "generated_at": datetime.utcnow().isoformat(),
            "validation_error_count": len(validation_errors),
            "strict_validation": strict_validation,
        },
    )
    db.commit()

    return {
        "report_title": "GST Reconciliation Report (Input vs Output Tax)",
        "frequency": gstr1_payload.get("frequency", "monthly"),
        "frequency_label": gstr1_payload.get("frequency_label", "Monthly"),
        "from_date": from_date.isoformat(),
        "to_date": to_date.isoformat(),
        "from_date_display": _format_ddmmyyyy(from_date),
        "to_date_display": _format_ddmmyyyy(to_date),
        "count": len(items),
        "items": items,
        "subtotal_input_tax": subtotal_input_tax,
        "subtotal_output_tax": subtotal_output_tax,
        "difference_amount": difference_amount,
        "strict_validation": strict_validation,
        "validation_error_count": len(validation_errors),
        "validation_errors": validation_errors[:100],
        "problematic_records": problematic_records[:200],
    }


@router.get("/gst-reconciliation/export")
async def gst_reconciliation_export(
    from_date: date,
    to_date: date,
    frequency: str = Query(default="monthly"),
    format: str = Query(default="xlsx"),
    strict_validation: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("reports_read")),
):
    format_token = (format or "xlsx").strip().lower()
    if format_token not in {"xlsx", "pdf"}:
        raise HTTPException(status_code=422, detail="Invalid format. Allowed values: xlsx, pdf")

    payload = await gst_reconciliation_report(
        from_date=from_date,
        to_date=to_date,
        frequency=frequency,
        strict_validation=strict_validation,
        db=db,
        current_user=current_user,
    )

    report_items = payload.get("items", [])
    subtotal_input = payload.get("subtotal_input_tax", {})
    subtotal_output = payload.get("subtotal_output_tax", {})
    difference_amount = payload.get("difference_amount", {})

    filename_base = f"gst_reconciliation_{from_date.isoformat()}_{to_date.isoformat()}"

    if format_token == "xlsx":
        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws.title = "GST Reconciliation"

        ws.append([payload.get("report_title", "GST Reconciliation Report")])
        ws.append([
            f"Period: {payload.get('from_date_display') or from_date.isoformat()} to {payload.get('to_date_display') or to_date.isoformat()} | Frequency: {payload.get('frequency_label', '')}"
        ])
        ws.append([])

        headers = [
            "S.No",
            "Tax Type",
            "Date",
            "Name of the Partner",
            "Partner GSTIN No",
            "Business Place",
            "Place of Supply",
            "GRN / Invoice Amount",
            "Currency",
            "Tax %",
            "CGST Amount",
            "SGST Amount",
            "IGST Amount",
            "UGST Amount",
            "Import / Export",
            "Total Tax Amount",
        ]
        ws.append(headers)

        for row in report_items:
            ws.append([
                row.get("s_no"),
                row.get("tax_type"),
                row.get("date"),
                row.get("name_of_partner"),
                row.get("partner_gstin_no"),
                row.get("business_place"),
                row.get("place_of_supply"),
                row.get("grn_or_invoice_amount"),
                row.get("currency"),
                row.get("tax_percent"),
                row.get("cgst_amount"),
                row.get("sgst_amount"),
                row.get("igst_amount"),
                row.get("ugst_amount"),
                row.get("import_export_amount"),
                row.get("total_tax_amount"),
            ])

        ws.append([])
        ws.append(["Sub Total (Input Tax)", "", "", "", "", "", "", subtotal_input.get("transaction_amount", 0.0), "", "", subtotal_input.get("cgst_amount", 0.0), subtotal_input.get("sgst_amount", 0.0), subtotal_input.get("igst_amount", 0.0), subtotal_input.get("ugst_amount", 0.0), subtotal_input.get("import_export_amount", 0.0), subtotal_input.get("total_tax_amount", 0.0)])
        ws.append(["Sub Total (Output Tax)", "", "", "", "", "", "", subtotal_output.get("transaction_amount", 0.0), "", "", subtotal_output.get("cgst_amount", 0.0), subtotal_output.get("sgst_amount", 0.0), subtotal_output.get("igst_amount", 0.0), subtotal_output.get("ugst_amount", 0.0), subtotal_output.get("import_export_amount", 0.0), subtotal_output.get("total_tax_amount", 0.0)])
        ws.append(["Difference Amount (Output - Input)", "", "", "", "", "", "", difference_amount.get("transaction_amount", 0.0), "", "", difference_amount.get("cgst_amount", 0.0), difference_amount.get("sgst_amount", 0.0), difference_amount.get("igst_amount", 0.0), difference_amount.get("ugst_amount", 0.0), difference_amount.get("import_export_amount", 0.0), difference_amount.get("total_tax_amount", 0.0)])

        stream = BytesIO()
        wb.save(stream)
        stream.seek(0)

        log_audit_event(
            db,
            action="REPORT:GST_RECONCILIATION_EXPORTED_XLSX",
            resource_type="reports",
            status="success",
            user_id=current_user.id,
            details={
                "report": "gst_reconciliation",
                "from_date": from_date.isoformat(),
                "to_date": to_date.isoformat(),
                "frequency": payload.get("frequency"),
                "generated_at": datetime.utcnow().isoformat(),
            },
        )
        _log_gst_report_event(
            db,
            user_id=current_user.id,
            action="EXPORT_GST_RECONCILIATION_XLSX",
            report_type="GST_RECONCILIATION",
            start_date=from_date,
            end_date=to_date,
            frequency=payload.get("frequency", "monthly"),
            status="success",
            details={
                "format": "xlsx",
                "row_count": len(report_items),
            },
        )
        db.commit()

        return StreamingResponse(
            stream,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename_base}.xlsx"},
        )

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    stream = BytesIO()
    doc = SimpleDocTemplate(stream, pagesize=landscape(A4), leftMargin=18, rightMargin=18, topMargin=18, bottomMargin=18)
    styles = getSampleStyleSheet()

    story = [
        Paragraph(payload.get("report_title", "GST Reconciliation Report"), styles["Heading2"]),
        Paragraph(
            f"Period: {payload.get('from_date_display') or from_date.isoformat()} to {payload.get('to_date_display') or to_date.isoformat()} | Frequency: {payload.get('frequency_label', '')}",
            styles["Normal"],
        ),
        Spacer(1, 8),
    ]

    table_data = [[
        "S.No", "Tax Type", "Date", "Partner", "GSTIN", "Business Place", "Place of Supply",
        "Amount", "Currency", "Tax %", "CGST", "SGST", "IGST", "UGST", "Imp/Exp", "Total Tax",
    ]]

    for row in report_items:
        table_data.append([
            row.get("s_no", ""),
            row.get("tax_type", ""),
            row.get("date", ""),
            row.get("name_of_partner", ""),
            row.get("partner_gstin_no", ""),
            row.get("business_place", ""),
            row.get("place_of_supply", ""),
            f"{float(row.get('grn_or_invoice_amount', 0.0)):.2f}",
            row.get("currency", ""),
            _format_tax_percent(row.get("tax_percent")),
            f"{float(row.get('cgst_amount', 0.0)):.2f}",
            f"{float(row.get('sgst_amount', 0.0)):.2f}",
            f"{float(row.get('igst_amount', 0.0)):.2f}",
            f"{float(row.get('ugst_amount', 0.0)):.2f}",
            f"{float(row.get('import_export_amount', 0.0)):.2f}",
            f"{float(row.get('total_tax_amount', 0.0)):.2f}",
        ])

    table = Table(table_data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E5E7EB")),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#9CA3AF")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(table)
    story.append(Spacer(1, 8))
    story.append(Paragraph(f"Sub Total (Input Tax) - Total Tax: {float(subtotal_input.get('total_tax_amount', 0.0)):.2f}", styles["Normal"]))
    story.append(Paragraph(f"Sub Total (Output Tax) - Total Tax: {float(subtotal_output.get('total_tax_amount', 0.0)):.2f}", styles["Normal"]))
    story.append(Paragraph(f"Difference (Output - Input) - Total Tax: {float(difference_amount.get('total_tax_amount', 0.0)):.2f}", styles["Normal"]))

    doc.build(story)
    stream.seek(0)

    log_audit_event(
        db,
        action="REPORT:GST_RECONCILIATION_EXPORTED_PDF",
        resource_type="reports",
        status="success",
        user_id=current_user.id,
        details={
            "report": "gst_reconciliation",
            "from_date": from_date.isoformat(),
            "to_date": to_date.isoformat(),
            "frequency": payload.get("frequency"),
            "generated_at": datetime.utcnow().isoformat(),
        },
    )
    _log_gst_report_event(
        db,
        user_id=current_user.id,
        action="EXPORT_GST_RECONCILIATION_PDF",
        report_type="GST_RECONCILIATION",
        start_date=from_date,
        end_date=to_date,
        frequency=payload.get("frequency", "monthly"),
        status="success",
        details={
            "format": "pdf",
            "row_count": len(report_items),
        },
    )
    db.commit()

    return StreamingResponse(
        stream,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename_base}.pdf"},
    )


@router.get("/gst-audit-trail")
async def gst_audit_trail_report(
    from_date: date,
    to_date: date,
    frequency: str = Query(default="monthly"),
    report_type: str = Query(default="all"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("reports_read")),
):
    """Return GST report generation/export audit events for the selected period."""
    _ensure_finance_tax_user(current_user)
    normalized_frequency, frequency_label = _normalize_frequency(frequency)
    _validate_frequency_date_window(from_date, to_date, normalized_frequency)

    report_type_token = (report_type or "all").strip().lower()
    report_type_map = {
        "gstr1": "GSTR-1",
        "gstr-1": "GSTR-1",
        "gstr2": "GSTR-2",
        "gstr-2": "GSTR-2",
        "gstr3b": "GSTR-3B",
        "gstr-3b": "GSTR-3B",
        "reconciliation": "GST_RECONCILIATION",
        "gst_reconciliation": "GST_RECONCILIATION",
        "gst-reconciliation": "GST_RECONCILIATION",
    }
    selected_report_type = None if report_type_token == "all" else report_type_map.get(report_type_token)
    if report_type_token != "all" and not selected_report_type:
        raise HTTPException(
            status_code=422,
            detail="Invalid report_type. Allowed: all, gstr1, gstr2, gstr3b, reconciliation",
        )

    _ensure_gst_report_audit_table(db)
    total_count = int(
        db.execute(
            text(
                """
                SELECT COUNT(*)
                FROM gst_report_audit_logs
                WHERE start_date >= :from_date
                  AND end_date <= :to_date
                  AND (:report_type IS NULL OR report_type = :report_type)
                """
            ),
            {
                "from_date": from_date,
                "to_date": to_date,
                "report_type": selected_report_type,
            },
        ).scalar()
        or 0
    )

    offset = (page - 1) * page_size
    rows = db.execute(
        text(
            """
            SELECT
                                a.id,
                                a.user_id,
                                COALESCE(NULLIF(TRIM(u.full_name), ''), u.email, 'Unknown User') AS user_name,
                                a.action,
                                a.report_type,
                                a.start_date,
                                a.end_date,
                                a.frequency,
                                a.status,
                                a.details,
                                a."timestamp"
                        FROM gst_report_audit_logs a
                        LEFT JOIN users u ON u.id = a.user_id
                        WHERE a.start_date >= :from_date
                            AND a.end_date <= :to_date
                            AND (:report_type IS NULL OR a.report_type = :report_type)
                        ORDER BY a."timestamp" DESC
            LIMIT :page_size OFFSET :offset
            """
        ),
        {
            "from_date": from_date,
            "to_date": to_date,
            "report_type": selected_report_type,
            "page_size": page_size,
            "offset": offset,
        },
    ).mappings().all()

    items = []
    for row in rows:
        details = row.get("details")
        if isinstance(details, str):
            try:
                details = json.loads(details)
            except Exception:
                details = {}

        items.append(
            {
                "id": str(row.get("id")),
                "user_id": str(row.get("user_id")) if row.get("user_id") else None,
                "user_name": row.get("user_name") or "Unknown User",
                "action": row.get("action"),
                "report_type": row.get("report_type"),
                "start_date": row.get("start_date").isoformat() if row.get("start_date") else None,
                "end_date": row.get("end_date").isoformat() if row.get("end_date") else None,
                "frequency": row.get("frequency"),
                "status": row.get("status"),
                "details": details if isinstance(details, dict) else {},
                "timestamp": row.get("timestamp").isoformat() if row.get("timestamp") else None,
            }
        )

    total_pages = (total_count + page_size - 1) // page_size if total_count else 0

    _log_gst_report_event(
        db,
        user_id=current_user.id,
        action="VIEW_GST_AUDIT_TRAIL",
        report_type="GST_AUDIT_TRAIL",
        start_date=from_date,
        end_date=to_date,
        frequency=normalized_frequency,
        status="success",
        details={
            "selected_report_type": selected_report_type or "all",
            "page": page,
            "page_size": page_size,
            "result_count": len(items),
        },
    )
    db.commit()

    return {
        "report_title": "GST Audit Trail",
        "frequency": normalized_frequency,
        "frequency_label": frequency_label,
        "from_date": from_date.isoformat(),
        "to_date": to_date.isoformat(),
        "from_date_display": _format_ddmmyyyy(from_date),
        "to_date_display": _format_ddmmyyyy(to_date),
        "report_type": selected_report_type or "all",
        "page": page,
        "page_size": page_size,
        "total": total_count,
        "total_pages": total_pages,
        "count": len(items),
        "items": items,
    }


@router.get("/action-logs")
async def action_logs_report(
    from_date: date,
    to_date: date,
    module: str = Query(default="all"),
    action_type: str = Query(default="all"),
    user_query: str = Query(default=""),
    reference: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("reports_read")),
):
    """Return system-wide action logs with role-restricted filtered access."""
    _ensure_action_log_view_user(current_user)
    _ensure_valid_date_range(from_date, to_date)
    ensure_audit_logs_storage(db)

    module_token = (module or "all").strip().lower()
    selected_module = None if module_token in {"", "all"} else module_token

    action_type_token = (action_type or "all").strip().upper()
    selected_action_type = None if action_type_token in {"", "ALL"} else action_type_token

    user_token = (user_query or "").strip()
    user_filter = f"%{user_token}%" if user_token else None

    reference_token = (reference or "").strip()
    reference_filter = f"%{reference_token}%" if reference_token else None

    count_row = db.execute(
        text(
            """
            SELECT COUNT(*)
            FROM audit_logs a
            LEFT JOIN users u ON u.id = a.user_id
            WHERE a.created_at::date >= :from_date
              AND a.created_at::date <= :to_date
              AND (:module_name IS NULL OR LOWER(COALESCE(a.module_name, '')) = :module_name)
              AND (:action_type IS NULL OR UPPER(COALESCE(a.action_type, '')) = :action_type)
              AND (
                    :user_filter IS NULL
                    OR CAST(a.user_id AS TEXT) ILIKE :user_filter
                    OR COALESCE(a.username, '') ILIKE :user_filter
                    OR COALESCE(u.full_name, '') ILIKE :user_filter
                    OR COALESCE(u.email, '') ILIKE :user_filter
                  )
              AND (:reference_filter IS NULL OR COALESCE(a.record_reference, '') ILIKE :reference_filter)
            """
        ),
        {
            "from_date": from_date,
            "to_date": to_date,
            "module_name": selected_module,
            "action_type": selected_action_type,
            "user_filter": user_filter,
            "reference_filter": reference_filter,
        },
    ).scalar()
    total_count = int(count_row or 0)
    offset = (page - 1) * page_size

    rows = db.execute(
        text(
            """
            SELECT
                a.id,
                a.user_id,
                COALESCE(NULLIF(TRIM(a.username), ''), NULLIF(TRIM(u.full_name), ''), u.email, 'System') AS user_name,
                COALESCE(a.action_type, '') AS action_type,
                COALESCE(a.module_name, '') AS module_name,
                a.action,
                a.record_reference,
                a.description,
                a.status,
                a.created_at,
                a.details
            FROM audit_logs a
            LEFT JOIN users u ON u.id = a.user_id
            WHERE a.created_at::date >= :from_date
              AND a.created_at::date <= :to_date
              AND (:module_name IS NULL OR LOWER(COALESCE(a.module_name, '')) = :module_name)
              AND (:action_type IS NULL OR UPPER(COALESCE(a.action_type, '')) = :action_type)
              AND (
                    :user_filter IS NULL
                    OR CAST(a.user_id AS TEXT) ILIKE :user_filter
                    OR COALESCE(a.username, '') ILIKE :user_filter
                    OR COALESCE(u.full_name, '') ILIKE :user_filter
                    OR COALESCE(u.email, '') ILIKE :user_filter
                  )
              AND (:reference_filter IS NULL OR COALESCE(a.record_reference, '') ILIKE :reference_filter)
            ORDER BY a.created_at DESC
            LIMIT :page_size OFFSET :offset
            """
        ),
        {
            "from_date": from_date,
            "to_date": to_date,
            "module_name": selected_module,
            "action_type": selected_action_type,
            "user_filter": user_filter,
            "reference_filter": reference_filter,
            "page_size": page_size,
            "offset": offset,
        },
    ).mappings().all()

    items = []
    for row in rows:
        details_value = row.get("details")
        details: dict[str, Any]
        if isinstance(details_value, dict):
            details = details_value
        elif isinstance(details_value, str):
            try:
                parsed = json.loads(details_value)
                details = parsed if isinstance(parsed, dict) else {}
            except Exception:
                details = {}
        else:
            details = {}

        items.append(
            {
                "id": str(row.get("id")),
                "user_id": str(row.get("user_id")) if row.get("user_id") else None,
                "user_name": row.get("user_name") or "System",
                "action": row.get("action") or "",
                "action_type": row.get("action_type") or "",
                "module_name": row.get("module_name") or "",
                "record_reference": row.get("record_reference") or "",
                "description": row.get("description") or "",
                "status": row.get("status") or "",
                "timestamp": row.get("created_at").isoformat() if row.get("created_at") else None,
                "details": details,
            }
        )

    total_pages = (total_count + page_size - 1) // page_size if total_count else 0

    log_audit_event(
        db,
        action="VIEW_ACTION_LOGS",
        resource_type="audit",
        status="success",
        user_id=current_user.id,
        details={
            "module": selected_module or "all",
            "action_type": selected_action_type or "all",
            "user_query": user_token,
            "reference": reference_token,
            "from_date": from_date.isoformat(),
            "to_date": to_date.isoformat(),
            "page": page,
            "page_size": page_size,
            "result_count": len(items),
        },
    )
    db.commit()

    return {
        "report_title": "Action Logs",
        "from_date": from_date.isoformat(),
        "to_date": to_date.isoformat(),
        "from_date_display": _format_ddmmyyyy(from_date),
        "to_date_display": _format_ddmmyyyy(to_date),
        "module": selected_module or "all",
        "action_type": selected_action_type or "all",
        "user_query": user_token,
        "reference": reference_token,
        "page": page,
        "page_size": page_size,
        "total": total_count,
        "total_pages": total_pages,
        "count": len(items),
        "items": items,
    }


@router.get("/pl")
async def profit_and_loss_report(
    from_date: date,
    to_date: date,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("reports_read")),
):
    _ensure_valid_date_range(from_date, to_date)
    sales_rows = db.query(SalesInvoice).filter(
        SalesInvoice.invoice_date >= from_date,
        SalesInvoice.invoice_date <= to_date,
        SalesInvoice.status.in_(["issued", "partial_paid", "paid"]),
        SalesInvoice.is_deleted == False,
    ).all()
    purchase_rows = db.query(GoodsReceiptNote).filter(
        GoodsReceiptNote.receipt_date >= from_date,
        GoodsReceiptNote.receipt_date <= to_date,
        GoodsReceiptNote.status == "confirmed",
        GoodsReceiptNote.is_deleted == False,
    ).all()

    net_sales = int(sum(row.total_taxable_amount for row in sales_rows))
    purchases = int(sum(row.total_taxable_amount for row in purchase_rows))
    gross_profit = net_sales - purchases

    margin = 0
    if net_sales > 0:
        margin = round((gross_profit / net_sales) * 100, 2)

    return {
        "net_sales": net_sales,
        "purchases": purchases,
        "gross_profit": gross_profit,
        "gross_profit_margin_percent": margin,
        "net_profit": gross_profit,
    }
