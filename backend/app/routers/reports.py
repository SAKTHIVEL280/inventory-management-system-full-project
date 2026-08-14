"""Reports router."""
from collections import defaultdict
from datetime import date, datetime, timedelta
from uuid import UUID
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
from app.dependencies import require_permissions, require_role, require_module, scope_query_to_company
from app.models.user import User
from app.models.inventory_count import InventoryCountDifferenceAudit, InventoryCountItem
from app.models.product import Product, StockLedger
from app.models.sales import SalesInvoice, SalesInvoiceItem, SalesOrder, SalesReturn, SalesReturnItem
from app.models.service_invoice import ServiceInvoice
from app.models.purchase import GoodsReceiptNote, GRNItem, PurchaseOrder, PurchaseReturn, PurchaseReturnItem
from app.models.rdn import ReturnDeliveryNote, ReturnDeliveryNoteItem, RdnCreditNote, RdnCreditNoteItem
from app.models.customer import Customer
from app.models.supplier import Supplier
from app.models.company import Company
from app.models.payment import Payment, PaymentAllocation
from app.services.audit_service import ensure_audit_logs_storage, log_audit_event, _extract_document_reference, int_to_roman, compose_audit_description
from app.services.auth_service import normalize_role
from app.services.gst_service import (
    INVOICE_TYPE_EXPORT,
    INVOICE_TYPE_OTHER_STATES,
    INVOICE_TYPE_UNION_TERRITORY,
    INVOICE_TYPE_WITHIN_STATE,
    is_india_country,
)

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


# ── Tenant Service Invoices in sales/revenue aggregates ──────────────────────
# A tenant's own service invoices are real sales revenue and must be included in
# Sales, P&L, Reports, Analytics and Dashboard totals — alongside Sales Invoices.
# Rules (mirrors the Sales Invoice revenue criteria + tenant isolation):
#   * company_id == the current tenant                 (tenant isolation)
#   * is_platform_invoice == False                     (exclude Mecandria's own
#                                                        subscription bills TO the tenant)
#   * is_deleted == False
#   * status in ('issued','paid')                      (finalised, not draft/cancelled)
# Amounts: grand_total is tax-inclusive (≈ SalesInvoice.total_amount);
#          total_taxable_amount is the pre-tax base (≈ SalesInvoice.total_taxable_amount).
_SVC_REVENUE_STATUSES = ("issued", "paid")


def _svc_revenue_filters(company_id):
    """Filter conditions selecting a tenant's own revenue-bearing service invoices."""
    return [
        ServiceInvoice.company_id == company_id,
        ServiceInvoice.is_deleted == False,
        ServiceInvoice.is_platform_invoice == False,
        ServiceInvoice.status.in_(_SVC_REVENUE_STATUSES),
    ]


def _svc_revenue_sum(db, company_id, column, *extra_filters):
    """Sum a service-invoice money column for the tenant's revenue invoices."""
    if not company_id:
        return 0
    q = db.query(func.coalesce(func.sum(column), 0)).filter(*_svc_revenue_filters(company_id))
    if extra_filters:
        q = q.filter(*extra_filters)
    return int(q.scalar() or 0)


def _base_amount(column):
    """SQL expression converting a Sales-Invoice money column to the tenant's base
    currency (INR) using the invoice's per-invoice exchange_rate, rounded to whole
    minor units. Base-currency (INR) invoices store exchange_rate=1.0, so existing
    data is numerically unchanged — this only affects foreign-currency invoices."""
    return func.round(column * SalesInvoice.exchange_rate)


def _to_base(amount_minor, exchange_rate) -> int:
    """Python-side equivalent of _base_amount for ORM-row aggregation."""
    return int(round(int(amount_minor or 0) * float(exchange_rate or 1)))


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
    if token in {"draft", "cancelled", "returned"}:
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


def _frequency_date_window(anchor_date: date, frequency: str) -> tuple[date, date]:
    if frequency == "monthly":
        start = anchor_date.replace(day=1)
        if start.month == 12:
            end = date(start.year + 1, 1, 1) - timedelta(days=1)
        else:
            end = date(start.year, start.month + 1, 1) - timedelta(days=1)
        return start, end

    if frequency == "quarterly":
        quarter_index = (anchor_date.month - 1) // 3
        start_month = quarter_index * 3 + 1
        start = date(anchor_date.year, start_month, 1)
        if start_month == 10:
            end = date(anchor_date.year + 1, 1, 1) - timedelta(days=1)
        else:
            end = date(anchor_date.year, start_month + 3, 1) - timedelta(days=1)
        return start, end

    start = date(anchor_date.year, 1, 1)
    end = date(anchor_date.year, 12, 31)
    return start, end


def _validate_frequency_date_window(from_date: date, to_date: date, frequency: str) -> tuple[date, date]:
    _ensure_valid_date_range(from_date, to_date)

    normalized_from_date, normalized_to_date = _frequency_date_window(from_date, frequency)
    total_days = (normalized_to_date - normalized_from_date).days + 1
    if total_days > 366:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Maximum report period is 12 months",
                "code": "VAL-001",
                "frequency": frequency,
                "from_date": normalized_from_date.isoformat(),
                "to_date": normalized_to_date.isoformat(),
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
                "from_date": normalized_from_date.isoformat(),
                "to_date": normalized_to_date.isoformat(),
                "selected_days": total_days,
                "allowed_days": max_days,
                "hint": f"Choose a shorter date range or switch frequency from {GST_REPORT_FREQUENCY_LABELS[frequency]}",
            },
        )

    return normalized_from_date, normalized_to_date


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


def _round_quantity(value: float | int | None) -> float:
    return round(float(value or 0.0), 4)


def _compose_item_description(
    product_name: str | None,
    item_description: str | None,
    product_description: str | None = None,
) -> str:
    name = (product_name or "").strip()
    item_desc = (item_description or "").strip()
    product_desc = (product_description or "").strip()
    detail = item_desc or product_desc
    if name and detail:
        if detail.lower() in name.lower():
            return name
        return f"{name} - {detail}"
    return name or detail


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
    # GST reports are part of the Reports module → Tenant Admin or Management role.
    if normalize_role(current_user.role) not in {"admin", "management"}:
        raise HTTPException(
            status_code=403,
            detail="Only Admin or Management users are allowed to generate GST reports",
        )


def _get_company_details_for_gst_reports(db: Session, company_id=None) -> dict:
    """Fetch the tenant's company details for GST report headers (PDF & Excel).

    Multi-tenant: scoped to the requesting tenant's company_id so a tenant's GST
    report never shows another tenant's (e.g. Tenant #1's) seller identity.
    """
    import base64
    import io
    from pathlib import Path
    from PIL import Image, ImageFile

    company = (
        db.query(Company).filter(Company.id == company_id).first()
        if company_id is not None else None
    )
    
    if not company:
        return {
            "name": "N/A",
            "address": "N/A",
            "gstin": "N/A",
            "phone": "N/A",
            "logo_data_uri": None,
            "ambassador_logo_bytes": None,
        }
    
    # Build address
    address_parts = [
        getattr(company, "address_line1", ""),
        getattr(company, "address_line2", ""),
        getattr(company, "city", ""),
        getattr(company, "state", ""),
        getattr(company, "country", ""),
        getattr(company, "pincode", ""),
    ]
    address = ", ".join([p.strip() for p in address_parts if p and p.strip()])
    
    # Resolve logo to data URI for PDF embedding
    logo_data_uri = None
    logo_url = getattr(company, "logo_url", None)
    if logo_url:
        logo_path = None
        if logo_url.startswith("/static/"):
            from pathlib import Path
            static_dir = Path(__file__).resolve().parents[2] / "static"
            logo_path = static_dir / logo_url.replace("/static/", "")
        else:
            p = Path(logo_url)
            if p.exists():
                logo_path = p
        
        if logo_path and logo_path.exists():
            try:
                raw = logo_path.read_bytes()
                ImageFile.LOAD_TRUNCATED_IMAGES = True
                with Image.open(io.BytesIO(raw)) as img:
                    normalized = img.convert("RGBA") if img.mode in {"RGBA", "LA", "P"} else img.convert("RGB")
                    out = io.BytesIO()
                    normalized.save(out, format="PNG")
                    data = base64.b64encode(out.getvalue()).decode("ascii")
                logo_data_uri = f"data:image/png;base64,{data}"
            except Exception:
                pass
    
    # Resolve ambassador logo bytes for watermark
    ambassador_logo_bytes = None
    ambassador_logo_url = getattr(company, "ambassador_logo_url", None)
    if ambassador_logo_url:
        ambassador_path = None
        if ambassador_logo_url.startswith("/static/"):
            from pathlib import Path
            static_dir = Path(__file__).resolve().parents[2] / "static"
            ambassador_path = static_dir / ambassador_logo_url.replace("/static/", "")
        else:
            p = Path(ambassador_logo_url)
            if p.exists():
                ambassador_path = p
        
        if ambassador_path and ambassador_path.exists():
            try:
                ambassador_logo_bytes = ambassador_path.read_bytes()
            except Exception:
                pass
    
    return {
        "name": getattr(company, "name", "N/A") or "N/A",
        "address": address or "N/A",
        "gstin": getattr(company, "gstin", "N/A") or "N/A",
        "phone": getattr(company, "phone", "N/A") or "N/A",
        "logo_data_uri": logo_data_uri,
        "ambassador_logo_bytes": ambassador_logo_bytes,
    }


def _add_ambassador_watermark_to_pdf(pdf_bytes: bytes, ambassador_logo_bytes: bytes | None) -> bytes:
    """Add ambassador logo as watermark to all pages of a PDF."""
    if not ambassador_logo_bytes:
        return pdf_bytes
    
    try:
        from PyPDF2 import PdfReader, PdfWriter
        from reportlab.pdfgen import canvas
        from reportlab.lib.utils import ImageReader
        import io
        
        # Constants for watermark
        WATERMARK_OPACITY = 0.15
        WATERMARK_MAX_WIDTH_PT = 300
        WATERMARK_PAGE_WIDTH_RATIO = 0.4
        
        reader = PdfReader(io.BytesIO(pdf_bytes))
        writer = PdfWriter()
        
        for page in reader.pages:
            page_width = float(page.mediabox.width)
            page_height = float(page.mediabox.height)
            
            # Create watermark for this page
            watermark_buffer = io.BytesIO()
            c = canvas.Canvas(watermark_buffer, pagesize=(page_width, page_height))
            
            try:
                image_reader = ImageReader(io.BytesIO(ambassador_logo_bytes))
                image_width, image_height = image_reader.getSize()
                
                if image_width and image_height:
                    # Calculate target size
                    target_width = min(WATERMARK_MAX_WIDTH_PT, page_width * WATERMARK_PAGE_WIDTH_RATIO)
                    target_height = target_width * (float(image_height) / float(image_width))
                    
                    max_height = page_height * 0.55
                    if target_height > max_height:
                        target_height = max_height
                        target_width = target_height * (float(image_width) / float(image_height))
                    
                    # Center the watermark
                    x = (page_width - target_width) / 2
                    y = (page_height - target_height) / 2
                    
                    # Set opacity
                    c.saveState()
                    c.setFillAlpha(WATERMARK_OPACITY)
                    c.setStrokeAlpha(WATERMARK_OPACITY)
                    
                    # Draw the image
                    c.drawImage(
                        image_reader,
                        x, y,
                        width=target_width,
                        height=target_height,
                        preserveAspectRatio=True,
                        mask='auto'
                    )
                    c.restoreState()
            except Exception:
                pass
            
            c.save()
            watermark_buffer.seek(0)
            
            # Merge watermark with page
            watermark_page = PdfReader(watermark_buffer).pages[0]
            watermark_page.merge_page(page)
            writer.add_page(watermark_page)
        
        # Write to output
        output_buffer = io.BytesIO()
        writer.write(output_buffer)
        output_buffer.seek(0)
        return output_buffer.read()
    except Exception:
        # If watermarking fails, return original PDF
        return pdf_bytes


def _ensure_action_log_view_user(current_user: User) -> None:
    if normalize_role(current_user.role) != "admin":
        raise HTTPException(
            status_code=403,
            detail="Only admin users can view action logs",
        )


FINANCIAL_ACTION_LOG_MODULES = (
    "invoices",
    "purchase-orders",
    "grn",
    "payments",
    "stock",
    "sales-returns",
    "purchase-returns",
    "rdn",
    # Master-data modules surfaced in Action Logs (create/update tracked + versioned).
    "customers",
    "suppliers",
)
FINANCIAL_ACTION_LOG_MODULES_SQL = "', '".join(FINANCIAL_ACTION_LOG_MODULES)


def _parse_uuid(value: str | None) -> UUID | None:
    if not value:
        return None
    try:
        return UUID(str(value))
    except (ValueError, TypeError):
        return None


def _format_inr_amount(value: int | float | None) -> str | None:
    if value is None:
        return None
    try:
        amount = float(value) / 100.0
    except (TypeError, ValueError):
        return None
    return f"INR {amount:,.2f}"


def _resolve_action_log_amount(
    db: Session,
    module_name: str,
    record_reference: str | None,
) -> int | None:
    token = (module_name or "").strip().lower()
    reference = (record_reference or "").strip()
    if not reference:
        return None

    record_id = _parse_uuid(reference)

    if token == "invoices":
        query = db.query(SalesInvoice).filter(SalesInvoice.is_deleted == False)
        invoice = (
            query.filter(SalesInvoice.id == record_id).first()
            if record_id else
            query.filter(SalesInvoice.invoice_number == reference).first()
        )
        return invoice.total_amount if invoice else None
    if token == "purchase-orders":
        query = db.query(PurchaseOrder).filter(PurchaseOrder.is_deleted == False)
        po = (
            query.filter(PurchaseOrder.id == record_id).first()
            if record_id else
            query.filter(PurchaseOrder.po_number == reference).first()
        )
        return po.total_amount if po else None
    if token == "grn":
        query = db.query(GoodsReceiptNote).filter(GoodsReceiptNote.is_deleted == False)
        grn = (
            query.filter(GoodsReceiptNote.id == record_id).first()
            if record_id else
            query.filter(GoodsReceiptNote.grn_number == reference).first()
        )
        return grn.total_amount if grn else None
    if token == "payments":
        query = db.query(Payment).filter(Payment.is_deleted == False)
        payment = (
            query.filter(Payment.id == record_id).first()
            if record_id else
            query.filter(Payment.payment_number == reference).first()
        )
        return payment.amount if payment else None
    if token == "sales-returns":
        query = db.query(SalesReturn).filter(SalesReturn.is_deleted == False)
        sales_return = (
            query.filter(SalesReturn.id == record_id).first()
            if record_id else
            query.filter(SalesReturn.return_number == reference).first()
        )
        return sales_return.total_amount if sales_return else None
    if token == "purchase-returns":
        query = db.query(PurchaseReturn).filter(PurchaseReturn.is_deleted == False)
        purchase_return = (
            query.filter(PurchaseReturn.id == record_id).first()
            if record_id else
            query.filter(PurchaseReturn.return_number == reference).first()
        )
        return purchase_return.total_amount if purchase_return else None

    return None


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


@router.get("/dashboard", dependencies=[Depends(require_module("dashboard"))])
async def dashboard_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("dashboard_read")),
):
    today = date.today()
    month_start = today.replace(day=1)
    receivable_statuses = ["issued", "partial_paid"]
    cash_receipt_statuses = ["pending", "cleared"]
    cid = current_user.company_id

    # Count totals — scoped by company
    product_q = db.query(func.count(Product.id)).filter(Product.is_deleted == False)
    if cid:
        product_q = product_q.filter(Product.company_id == cid)
    total_products = product_q.scalar() or 0

    customer_q = db.query(func.count(Customer.id)).filter(Customer.is_deleted == False, Customer.is_active == True)
    if cid:
        customer_q = customer_q.filter(Customer.company_id == cid)
    total_customers = customer_q.scalar() or 0

    supplier_q = db.query(func.count(Supplier.id)).filter(Supplier.is_deleted == False, Supplier.is_active == True)
    if cid:
        supplier_q = supplier_q.filter(Supplier.company_id == cid)
    total_suppliers = supplier_q.scalar() or 0

    # Low stock count
    low_stock_count = 0
    safety_stock_count = 0
    product_list_q = db.query(Product).filter(Product.is_deleted == False)
    if cid:
        product_list_q = product_list_q.filter(Product.company_id == cid)
    products = product_list_q.all()
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
    po_q = db.query(func.count(PurchaseOrder.id)).filter(
        PurchaseOrder.status.in_(["pending", "approved", "partial_received"]),
        PurchaseOrder.is_deleted == False,
    )
    if cid:
        po_q = po_q.filter(PurchaseOrder.company_id == cid)
    pending_po_count = po_q.scalar() or 0

    # Sales Order module removed from active workflow.
    pending_so_count = 0

    # Today sales
    today_sales_q = db.query(func.coalesce(func.sum(_base_amount(SalesInvoice.total_amount)), 0)).filter(
        SalesInvoice.company_id == current_user.company_id,
        SalesInvoice.invoice_date == today,
        SalesInvoice.status.in_(["issued", "partial_paid", "paid"]),
        SalesInvoice.is_deleted == False,
    )
    if cid:
        today_sales_q = today_sales_q.filter(SalesInvoice.company_id == cid)
    today_sales = today_sales_q.scalar() or 0
    # + tenant Service Invoices raised today
    today_sales = int(today_sales) + _svc_revenue_sum(
        db, cid, ServiceInvoice.grand_total, ServiceInvoice.invoice_date == today
    )

    # Month sales
    month_sales_q = db.query(func.coalesce(func.sum(_base_amount(SalesInvoice.total_amount)), 0)).filter(
        SalesInvoice.company_id == current_user.company_id,
        SalesInvoice.invoice_date >= month_start,
        SalesInvoice.invoice_date <= today,
        SalesInvoice.status.in_(["issued", "partial_paid", "paid"]),
        SalesInvoice.is_deleted == False,
    )
    if cid:
        month_sales_q = month_sales_q.filter(SalesInvoice.company_id == cid)
    month_sales = month_sales_q.scalar() or 0
    # + tenant Service Invoices raised this month
    month_sales = int(month_sales) + _svc_revenue_sum(
        db, cid, ServiceInvoice.grand_total,
        ServiceInvoice.invoice_date >= month_start,
        ServiceInvoice.invoice_date <= today,
    )

    # Outstanding receivables
    receivables_q = db.query(func.coalesce(func.sum(SalesInvoice.amount_due), 0)).filter(
        SalesInvoice.company_id == current_user.company_id,
        SalesInvoice.amount_due > 0,
        SalesInvoice.status.in_(receivable_statuses),
        SalesInvoice.is_deleted == False,
    )
    if cid:
        receivables_q = receivables_q.filter(SalesInvoice.company_id == cid)
    outstanding_receivables = receivables_q.scalar() or 0
    # + tenant Service Invoices that are issued but not yet paid (open receivables).
    if cid:
        svc_receivables = int(
            db.query(func.coalesce(func.sum(ServiceInvoice.grand_total), 0))
            .filter(
                ServiceInvoice.company_id == cid,
                ServiceInvoice.is_deleted == False,
                ServiceInvoice.is_platform_invoice == False,
                ServiceInvoice.status == "issued",
            )
            .scalar()
            or 0
        )
        outstanding_receivables = int(outstanding_receivables) + svc_receivables

    # Overdue invoices count
    overdue_q = db.query(func.count(SalesInvoice.id)).filter(
        SalesInvoice.company_id == current_user.company_id,
        SalesInvoice.due_date < today,
        SalesInvoice.status.in_(["issued", "partial_paid"]),
        SalesInvoice.is_deleted == False,
    )
    if cid:
        overdue_q = overdue_q.filter(SalesInvoice.company_id == cid)
    overdue_invoices_count = overdue_q.scalar() or 0

    # Sales trend (last 7 days)
    sales_trend = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        trend_q = db.query(func.coalesce(func.sum(_base_amount(SalesInvoice.total_amount)), 0)).filter(
            SalesInvoice.company_id == current_user.company_id,
            SalesInvoice.invoice_date == day,
            func.lower(func.trim(SalesInvoice.status)).in_(["issued", "partial_paid", "paid", "returned"]),
            SalesInvoice.is_deleted == False,
        )
        if cid:
            trend_q = trend_q.filter(SalesInvoice.company_id == cid)
        amount = trend_q.scalar() or 0
        # + tenant Service Invoices raised that day
        amount = int(amount) + _svc_revenue_sum(
            db, cid, ServiceInvoice.grand_total, ServiceInvoice.invoice_date == day
        )
        sales_trend.append({"date": day.isoformat(), "amount": int(amount)})

    # Top products
    top_products_base = db.query(
        Product.name,
        func.coalesce(func.sum(SalesInvoiceItem.quantity), 0).label("quantity_sold"),
        func.coalesce(func.sum(SalesInvoiceItem.total_amount), 0).label("amount"),
    ).join(SalesInvoiceItem, SalesInvoiceItem.product_id == Product.id).join(
        SalesInvoice, SalesInvoice.id == SalesInvoiceItem.invoice_id
    ).filter(
        SalesInvoice.company_id == current_user.company_id,
        SalesInvoice.invoice_date >= month_start,
        SalesInvoice.invoice_date <= today,
        SalesInvoice.status.in_(["issued", "partial_paid", "paid"]),
        SalesInvoice.is_deleted == False,
        Product.is_deleted == False,
    )
    if cid:
        top_products_base = top_products_base.filter(SalesInvoice.company_id == cid)
    top_products_query = top_products_base.group_by(Product.id, Product.name).order_by(text("quantity_sold DESC")).limit(5).all()

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

    # MCN-BUG-002: Revenue generation per Sales Manager (invoice creator) and per
    # Stockist (customer), pre-computed for today / this week / this month windows so
    # the two dashboard panels render from a single fetch with independent toggles.
    def _build_revenue_generation_metrics(start_date: date):
        revenue_filter = [
            SalesInvoice.invoice_date >= start_date,
            SalesInvoice.invoice_date <= today,
            SalesInvoice.status.in_(["issued", "partial_paid", "paid"]),
            SalesInvoice.is_deleted == False,
        ]

        # MCN-BUG-04: group revenue by the invoice's assigned Sales Manager
        # (SalesInvoice.sales_manager_name, Enhancement 3) — NOT by created_by (the
        # user who created the invoice). Grouping by created_by collapsed the report
        # to a single row (usually the one admin/accounts user); grouping by the
        # actual sales manager surfaces every distinct manager with sales.
        sales_manager_query = (
            db.query(
                SalesInvoice.sales_manager_name.label("name"),
                func.coalesce(func.sum(_base_amount(SalesInvoice.total_amount)), 0).label("revenue"),
            )
            .filter(*revenue_filter)
        )
        if cid:
            sales_manager_query = sales_manager_query.filter(SalesInvoice.company_id == cid)
        sales_manager_query = sales_manager_query.group_by(SalesInvoice.sales_manager_name).all()
        sales_manager_rows = [
            {
                "id": (row.name or "unassigned"),
                "name": row.name or "Unassigned",
                "revenue": int(row.revenue or 0),
            }
            for row in sales_manager_query
            if int(row.revenue or 0) != 0
        ]
        sales_manager_rows.sort(key=lambda row: row["revenue"], reverse=True)

        stockist_query = (
            db.query(
                SalesInvoice.customer_id.label("cust_id"),
                Customer.company_name.label("name"),
                func.coalesce(func.sum(_base_amount(SalesInvoice.total_amount)), 0).label("revenue"),
            )
            .join(Customer, SalesInvoice.customer_id == Customer.id)
            .filter(*revenue_filter)
        )
        if cid:
            stockist_query = stockist_query.filter(SalesInvoice.company_id == cid)
        stockist_query = stockist_query.group_by(SalesInvoice.customer_id, Customer.company_name).all()
        stockist_rows = [
            {
                "id": str(row.cust_id),
                "name": row.name or "Unknown",
                "revenue": int(row.revenue or 0),
            }
            for row in stockist_query
            if int(row.revenue or 0) != 0
        ]
        stockist_rows.sort(key=lambda row: row["revenue"], reverse=True)

        return sales_manager_rows[:12], stockist_rows[:12]

    sm_daily, st_daily = _build_revenue_generation_metrics(today)
    sm_weekly, st_weekly = _build_revenue_generation_metrics(today - timedelta(days=6))
    sm_monthly, st_monthly = _build_revenue_generation_metrics(month_start)

    revenue_generation = {
        "sales_manager": {"daily": sm_daily, "weekly": sm_weekly, "monthly": sm_monthly},
        "stockist": {"daily": st_daily, "weekly": st_weekly, "monthly": st_monthly},
    }

    # Outstanding payables
    outstanding_payables = db.query(func.coalesce(func.sum(GoodsReceiptNote.total_amount), 0)).filter(
        GoodsReceiptNote.company_id == current_user.company_id,
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
        "revenue_generation": revenue_generation,
    }


# ── MCN-BUG-01: Financial-Year sales trend ───────────────────────────────────
# Indian Financial Year runs April → March. FY "2025-26" = 1 Apr 2025 → 31 Mar 2026.
# The graph groups sales by FY month (Apr..Mar order); selecting a month drills into
# that month's daily totals. Revenue mirrors the Sales report / P&L status set
# (issued/partial_paid/paid) + the tenant's own finalized service invoices, and is
# strictly scoped to the caller's company_id (multi-tenant isolation).
_SALES_TREND_STATUSES = ("issued", "partial_paid", "paid")
_FY_MONTH_ORDER = (4, 5, 6, 7, 8, 9, 10, 11, 12, 1, 2, 3)  # Apr → Mar
_MONTH_LABELS = {
    1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
    7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec",
}


def _current_financial_year(today: date | None = None) -> int:
    """Start year of the FY that contains `today` (Jan-Mar belongs to prior FY)."""
    d = today or date.today()
    return d.year if d.month >= 4 else d.year - 1


def _fy_month_year(fy_start: int, month: int) -> int:
    """Calendar year for a given month within FY starting `fy_start`.

    Apr-Dec are in fy_start; Jan-Mar are in fy_start + 1.
    """
    return fy_start if month >= 4 else fy_start + 1


@router.get("/sales-trend", dependencies=[Depends(require_module("dashboard"))])
async def sales_trend_report(
    financial_year: int | None = Query(default=None, description="FY start year, e.g. 2025 for FY 2025-26"),
    month: int | None = Query(default=None, ge=1, le=12),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("dashboard_read")),
):
    cid = current_user.company_id
    fy_start = int(financial_year) if financial_year else _current_financial_year()
    fy_label = f"{fy_start}-{str(fy_start + 1)[-2:]}"  # e.g. 2025-26

    def _sales_sum(d_from: date, d_to: date) -> int:
        q = db.query(func.coalesce(func.sum(_base_amount(SalesInvoice.total_amount)), 0)).filter(
            SalesInvoice.company_id == cid,
            SalesInvoice.invoice_date >= d_from,
            SalesInvoice.invoice_date <= d_to,
            func.lower(func.trim(SalesInvoice.status)).in_(_SALES_TREND_STATUSES),
            SalesInvoice.is_deleted == False,
        )
        base = int(q.scalar() or 0)
        base += _svc_revenue_sum(
            db, cid, ServiceInvoice.grand_total,
            ServiceInvoice.invoice_date >= d_from, ServiceInvoice.invoice_date <= d_to,
        )
        return base

    points: list[dict] = []

    if month is not None:
        # Drill-down: daily totals for the selected FY month.
        import calendar
        year = _fy_month_year(fy_start, month)
        days_in_month = calendar.monthrange(year, month)[1]
        for day_num in range(1, days_in_month + 1):
            d = date(year, month, day_num)
            amount = _sales_sum(d, d)
            points.append({"label": str(day_num), "period": d.isoformat(), "amount": amount})
        granularity = "day"
    else:
        # 12 monthly buckets in FY order (Apr..Mar).
        import calendar
        for m in _FY_MONTH_ORDER:
            year = _fy_month_year(fy_start, m)
            last_day = calendar.monthrange(year, m)[1]
            d_from = date(year, m, 1)
            d_to = date(year, m, last_day)
            amount = _sales_sum(d_from, d_to)
            points.append({
                "label": _MONTH_LABELS[m],
                "period": f"{year}-{m:02d}",
                "amount": amount,
            })
        granularity = "month"

    return {
        "financial_year": fy_start,
        "financial_year_label": fy_label,
        "month": month,
        "granularity": granularity,
        "total": sum(p["amount"] for p in points),
        "points": points,
    }


# Stock overview powers BOTH the Inventory → Stock page (inventory module) and the
# Reports → Stock tab (reports module). Gate on EITHER module (OR) so a plan that
# includes inventory but not reports (e.g. SILVER with Inventory enabled) can still
# open the Stock page. Mirrors the user-permission OR (stock_ledger_read/reports_read).
@router.get("/stock", dependencies=[Depends(require_module("inventory", "reports"))])
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
            .filter(StockLedger.is_deleted == False)
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
            GoodsReceiptNote.company_id == current_user.company_id,
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
            PurchaseReturn.company_id == current_user.company_id,
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
            # MCN-BUG-02: deduct billed + free quantity (matches the stock ledger).
            func.coalesce(func.sum(SalesInvoiceItem.quantity + func.coalesce(SalesInvoiceItem.free_quantity, 0)), 0).label("qty"),
        )
        .join(SalesInvoice, SalesInvoiceItem.invoice_id == SalesInvoice.id)
        .filter(
            SalesInvoice.company_id == current_user.company_id,
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
            SalesReturn.company_id == current_user.company_id,
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

    rdn_rows = (
        db.query(
            ReturnDeliveryNoteItem.product_id,
            ReturnDeliveryNoteItem.batch_no,
            ReturnDeliveryNoteItem.manufacture_date,
            ReturnDeliveryNoteItem.expiry_date,
            func.coalesce(func.sum(ReturnDeliveryNoteItem.return_quantity), 0).label("qty"),
        )
        .join(ReturnDeliveryNote, ReturnDeliveryNoteItem.rdn_id == ReturnDeliveryNote.id)
        .filter(
            ReturnDeliveryNote.company_id == current_user.company_id,
            ReturnDeliveryNote.status == "confirmed",
            ReturnDeliveryNote.is_deleted == False,
            ReturnDeliveryNoteItem.is_deleted == False,
        )
        .group_by(
            ReturnDeliveryNoteItem.product_id,
            ReturnDeliveryNoteItem.batch_no,
            ReturnDeliveryNoteItem.manufacture_date,
            ReturnDeliveryNoteItem.expiry_date,
        )
        .all()
    )
    for row in rdn_rows:
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

    # Tenant isolation: only the logged-in tenant's products (batch/ledger totals
    # are keyed by product_id, which is unique to one tenant, so per-product figures
    # stay correct once the product set is scoped).
    products = (
        db.query(Product)
        .filter(Product.is_deleted == False, Product.company_id == current_user.company_id)
        .all()
    )
    grand_total_mrp_value = 0.0
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
            total_mrp_value = float(batch_qty) * float(product.mrp or 0)
            grand_total_mrp_value += total_mrp_value
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
                "total_mrp_value": total_mrp_value,
            })

    rows.sort(key=lambda row: (row["product_name"] or "", row["batch_no"] or "~"))
    return {"items": rows, "total": len(rows), "grand_total_mrp_value": grand_total_mrp_value}


@router.get("/sales", dependencies=[Depends(require_module("reports"))])
async def sales_report(
    from_date: date,
    to_date: date,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("reports_read")),
):
    _ensure_valid_date_range(from_date, to_date)
    # Join the customer so the Sales Report can display the full customer name per invoice
    # (MCN-BUG-005). bill_to_customer_id is the invoice's billed party; fall back to
    # customer_id for legacy rows where only customer_id is populated.
    rows = (
        db.query(SalesInvoice, Customer.company_name.label("customer_name"))
        .outerjoin(
            Customer,
            Customer.id == func.coalesce(SalesInvoice.bill_to_customer_id, SalesInvoice.customer_id),
        )
        .filter(
            SalesInvoice.company_id == current_user.company_id,
            SalesInvoice.invoice_date >= from_date,
            SalesInvoice.invoice_date <= to_date,
            SalesInvoice.status.in_(["issued", "partial_paid", "paid"]),
            SalesInvoice.is_deleted == False,
        )
        .all()
    )
    # Tenant Service Invoices in the same window count as sales too (tenant-isolated,
    # excluding Mecandria's platform subscription bills). They are appended to the
    # item list (tagged source='service') and included in the combined total_amount.
    svc_rows = (
        db.query(ServiceInvoice)
        .filter(
            *_svc_revenue_filters(current_user.company_id),
            ServiceInvoice.invoice_date >= from_date,
            ServiceInvoice.invoice_date <= to_date,
        )
        .all()
    )

    sales_items = [
        {
            "invoice_number": row.SalesInvoice.invoice_number,
            "invoice_date": row.SalesInvoice.invoice_date.isoformat() if row.SalesInvoice.invoice_date else None,
            "customer_name": row.customer_name or "-",
            "total_amount": row.SalesInvoice.total_amount,
            "amount_paid": row.SalesInvoice.amount_paid,
            "amount_due": row.SalesInvoice.amount_due,
            "status": row.SalesInvoice.status,
            "source": "sales",
        }
        for row in rows
    ]
    service_items = [
        {
            "invoice_number": s.invoice_number,
            "invoice_date": s.invoice_date.isoformat() if s.invoice_date else None,
            "customer_name": s.customer_name or "-",
            "total_amount": int(s.grand_total or 0),
            "amount_paid": int(s.grand_total or 0) if s.status == "paid" else 0,
            "amount_due": int(s.grand_total or 0) if s.status == "issued" else 0,
            "status": s.status,
            "source": "service",
        }
        for s in svc_rows
    ]
    items = sales_items + service_items
    items.sort(key=lambda it: it["invoice_date"] or "", reverse=True)

    # Convert each foreign-currency invoice to base (INR) with its stored rate.
    sales_total = int(sum(_to_base(row.SalesInvoice.total_amount, row.SalesInvoice.exchange_rate) for row in rows))
    service_total = int(sum(int(s.grand_total or 0) for s in svc_rows))
    return {
        "count": len(items),
        "total_amount": sales_total + service_total,
        "sales_invoice_total": sales_total,
        "service_invoice_total": service_total,
        "items": items,
    }


@router.get("/purchase", dependencies=[Depends(require_module("reports"))])
async def purchase_report(
    from_date: date,
    to_date: date,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("reports_read")),
):
    _ensure_valid_date_range(from_date, to_date)
    rows = db.query(GoodsReceiptNote).filter(
        GoodsReceiptNote.company_id == current_user.company_id,
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


@router.get("/outstanding-receivables", dependencies=[Depends(require_module("reports"))])
async def outstanding_receivables(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("reports_read")),
):
    rows = db.query(SalesInvoice).filter(
        SalesInvoice.company_id == current_user.company_id,
        SalesInvoice.amount_due > 0,
        SalesInvoice.status.in_(["issued", "partial_paid"]),
        SalesInvoice.is_deleted == False,
    ).all()
    return {
        # Base-currency (INR) total: foreign invoices converted via their stored rate.
        "total_outstanding": int(sum(_to_base(row.amount_due, row.exchange_rate) for row in rows)),
        "items": [
            {
                "invoice_number": row.invoice_number,
                "invoice_date": row.invoice_date.isoformat() if row.invoice_date else None,
                "due_date": row.due_date.isoformat() if row.due_date else None,
                "balance_due": row.amount_due,             # in the invoice's currency
                "currency_code": row.currency_code or "INR",
                "exchange_rate": float(row.exchange_rate or 1),
                "balance_due_base": _to_base(row.amount_due, row.exchange_rate),  # INR
            }
            for row in rows
        ],
    }


@router.get("/outstanding-payables", dependencies=[Depends(require_module("reports"))])
async def outstanding_payables(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("reports_read")),
):
    rows = db.query(GoodsReceiptNote).filter(
        GoodsReceiptNote.company_id == current_user.company_id,
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


@router.get("/gstr1", dependencies=[Depends(require_module("reports"))])
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
    from_date, to_date = _validate_frequency_date_window(from_date, to_date, normalized_frequency)

    invoices = (
        db.query(SalesInvoice)
        .filter(
            SalesInvoice.company_id == current_user.company_id,
            SalesInvoice.invoice_date >= from_date,
            SalesInvoice.invoice_date <= to_date,
            SalesInvoice.status.in_(["issued", "partial_paid", "paid"]),
            SalesInvoice.is_deleted == False,
        )
        .order_by(SalesInvoice.invoice_date.asc(), SalesInvoice.invoice_number.asc())
        .all()
    )

    credit_notes = (
        db.query(RdnCreditNote)
        .filter(
            RdnCreditNote.company_id == current_user.company_id,
            RdnCreditNote.credit_note_date >= from_date,
            RdnCreditNote.credit_note_date <= to_date,
            RdnCreditNote.status == "posted",
            RdnCreditNote.is_deleted == False,
        )
        .order_by(RdnCreditNote.credit_note_date.asc(), RdnCreditNote.credit_note_number.asc())
        .all()
    )

    invoice_ids = [row.id for row in invoices]
    invoice_id_map = {str(row.id): row for row in invoices}
    credit_note_ids = [row.id for row in credit_notes]

    invoice_item_map: dict[str, list[dict]] = defaultdict(list)
    if invoice_ids:
        item_rows = (
            db.query(
                SalesInvoiceItem.invoice_id,
                SalesInvoiceItem.description.label("item_description"),
                SalesInvoiceItem.quantity,
                SalesInvoiceItem.taxable_amount,
                SalesInvoiceItem.cgst_amount,
                SalesInvoiceItem.sgst_amount,
                SalesInvoiceItem.igst_amount,
                SalesInvoiceItem.gst_rate,
                Product.name.label("product_name"),
                Product.description.label("product_description"),
                Product.hsn_code.label("hsn_code"),
            )
            .outerjoin(Product, SalesInvoiceItem.product_id == Product.id)
            .filter(
                SalesInvoiceItem.invoice_id.in_(invoice_ids),
                SalesInvoiceItem.is_deleted == False,
            )
            .all()
        )
        for item in item_rows:
            invoice_key = str(item.invoice_id)
            invoice_item_map[invoice_key].append(
                {
                    "item_description": item.item_description,
                    "product_name": item.product_name,
                    "product_description": item.product_description,
                    "hsn_code": item.hsn_code,
                    "quantity": _round_quantity(item.quantity),
                    "taxable_amount": _paise_to_amount(item.taxable_amount),
                    "cgst_amount": _paise_to_amount(item.cgst_amount),
                    "sgst_amount": _paise_to_amount(item.sgst_amount),
                    "igst_amount": _paise_to_amount(item.igst_amount),
                    "gst_rate": _round_2(float(item.gst_rate or 0.0)),
                }
            )

    credit_note_item_map: dict[str, list[dict]] = defaultdict(list)
    credit_note_rate_map: dict[str, set[float]] = defaultdict(set)
    if credit_note_ids:
        credit_item_rows = (
            db.query(
                RdnCreditNoteItem.credit_note_id,
                RdnCreditNoteItem.return_quantity,
                RdnCreditNoteItem.taxable_amount,
                RdnCreditNoteItem.cgst_amount,
                RdnCreditNoteItem.sgst_amount,
                RdnCreditNoteItem.igst_amount,
                RdnCreditNoteItem.gst_rate,
                Product.name.label("product_name"),
                Product.description.label("product_description"),
                Product.hsn_code.label("hsn_code"),
            )
            .outerjoin(Product, RdnCreditNoteItem.product_id == Product.id)
            .filter(
                RdnCreditNoteItem.credit_note_id.in_(credit_note_ids),
                RdnCreditNoteItem.is_deleted == False,
            )
            .all()
        )
        for item in credit_item_rows:
            note_key = str(item.credit_note_id)
            credit_note_item_map[note_key].append(
                {
                    "product_name": item.product_name,
                    "product_description": item.product_description,
                    "hsn_code": item.hsn_code,
                    "quantity": _round_quantity(item.return_quantity),
                    "taxable_amount": _paise_to_amount(item.taxable_amount),
                    "cgst_amount": _paise_to_amount(item.cgst_amount),
                    "sgst_amount": _paise_to_amount(item.sgst_amount),
                    "igst_amount": _paise_to_amount(item.igst_amount),
                    "gst_rate": _round_2(float(item.gst_rate or 0.0)),
                }
            )
            credit_note_rate_map[note_key].add(_round_2(float(item.gst_rate or 0.0)))

    invoice_totals_map: dict[str, dict[str, float]] = {}
    invoice_rate_map: dict[str, set[float]] = defaultdict(set)
    validation_errors: list[str] = []

    credit_note_totals_map: dict[str, dict[str, float]] = {
        str(note.id): {
            "taxable_amount": _paise_to_amount(note.total_taxable_amount),
            "cgst_amount": _paise_to_amount(note.total_cgst),
            "sgst_amount": _paise_to_amount(note.total_sgst),
            "igst_amount": _paise_to_amount(note.total_igst),
        }
        for note in credit_notes
    }

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

    credit_note_invoice_ids = {note.sales_invoice_id for note in credit_notes}
    credit_note_invoices = (
        db.query(SalesInvoice)
        .filter(SalesInvoice.id.in_(list(credit_note_invoice_ids)), SalesInvoice.is_deleted == False)
        .all()
        if credit_note_invoice_ids
        else []
    )
    credit_note_invoice_map = {str(row.id): row for row in credit_note_invoices}

    sales_order_ids = {row.sales_order_id for row in invoices if row.sales_order_id is not None}
    sales_order_ids.update({row.sales_order_id for row in credit_note_invoices if row.sales_order_id is not None})
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
    customer_ids.update(
        {
            customer_id
            for row in credit_note_invoices
            for customer_id in [row.customer_id, row.bill_to_customer_id, row.ship_to_customer_id]
            if customer_id is not None
        }
    )
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
                SalesInvoice.company_id == current_user.company_id,
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
    detail_rows: list[dict] = []
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
    detail_subtotal = {
        "invoice_amount": 0.0,
        "cgst_amount": 0.0,
        "sgst_amount": 0.0,
        "igst_amount": 0.0,
        "ugst_amount": 0.0,
        "export_amount": 0.0,
        "total_tax_amount": 0.0,
    }

    serial_no = 1
    detail_serial_no = 1
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
        bill_to_gstin_status = ((bill_to_customer.gstin_status if bill_to_customer else "") or "non-registered").strip().lower()
        bill_to_state = (
            (ship_to_customer.shipping_state if ship_to_customer else "")
            or (ship_to_customer.billing_state if ship_to_customer else "")
            or (bill_to_customer.shipping_state if bill_to_customer else "")
            or (bill_to_customer.billing_state if bill_to_customer else "")
            or ""
        ).strip()
        bill_to_state_code = (
            (ship_to_customer.shipping_state_code if ship_to_customer else "")
            or (ship_to_customer.billing_state_code if ship_to_customer else "")
            or (bill_to_customer.shipping_state_code if bill_to_customer else "")
            or (bill_to_customer.billing_state_code if bill_to_customer else "")
            or ""
        ).strip()
        place_of_supply = (
            (invoice.supply_state or "").strip()
            or ((invoice.supply_state_code or "").strip())
            or bill_to_state
            or bill_to_state_code
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
            if bill_to_is_india:
                if bill_to_gstin:
                    if not GSTIN_REGEX.match(bill_to_gstin):
                        validation_errors.append(
                            f"VAL-002 GSTIN Format Check failed for invoice {invoice_number}: GSTIN {bill_to_gstin} is invalid"
                        )
                elif bill_to_gstin_status == "registered":
                    validation_errors.append(
                        f"VAL-010 Mandatory Fields Check failed for invoice {invoice_number}: billing GSTIN is required"
                    )
                else:
                    if not bill_to_state:
                        validation_errors.append(
                            f"VAL-010 Mandatory Fields Check failed for invoice {invoice_number}: state is required for non-registered GST customers"
                        )
                    if not bill_to_state_code:
                        validation_errors.append(
                            f"VAL-010 Mandatory Fields Check failed for invoice {invoice_number}: state code is required for GST calculation"
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

        for item in invoice_item_map.get(invoice_key, []):
            item_name = _compose_item_description(
                item.get("product_name"),
                item.get("item_description"),
                item.get("product_description"),
            )
            line_amount = _convert_with_rate(item.get("taxable_amount"), float(conversion_rate or 1.0))
            line_cgst = _convert_with_rate(item.get("cgst_amount"), float(conversion_rate or 1.0))
            line_sgst = _convert_with_rate(item.get("sgst_amount"), float(conversion_rate or 1.0))
            line_igst = _convert_with_rate(item.get("igst_amount"), float(conversion_rate or 1.0))
            line_ugst = 0.0
            line_export = 0.0

            if invoice_type == INVOICE_TYPE_UNION_TERRITORY:
                line_ugst = line_sgst
                line_sgst = 0.0
            elif invoice_type == INVOICE_TYPE_EXPORT:
                line_export = line_amount
                line_cgst = 0.0
                line_sgst = 0.0
                line_igst = 0.0
                line_ugst = 0.0

            line_total_tax = _round_2(line_cgst + line_sgst + line_igst + line_ugst + line_export)

            detail_rows.append(
                {
                    "s_no": detail_serial_no,
                    "sales_invoice_date": _format_ddmmyyyy(invoice.invoice_date),
                    "sales_invoice_no": invoice_number,
                    "bill_to_party_name": bill_to_name,
                    "bill_to_party_gstin_no": display_bill_to_gstin,
                    "place_of_supply": place_of_supply,
                    "ship_to_party_name": ship_to_name,
                    "item_name_description": item_name,
                    "hsn": (item.get("hsn_code") or ""),
                    "quantity": item.get("quantity", 0.0),
                    "invoice_amount": line_amount,
                    "currency": GST_REPORT_BASE_CURRENCY,
                    "tax_percent": item.get("gst_rate"),
                    "cgst_amount": line_cgst,
                    "sgst_amount": line_sgst,
                    "igst_amount": line_igst,
                    "ugst_amount": line_ugst,
                    "export_amount": line_export,
                    "total_tax_amount": line_total_tax,
                }
            )
            detail_serial_no += 1

            detail_subtotal["invoice_amount"] = _round_2(detail_subtotal["invoice_amount"] + line_amount)
            detail_subtotal["cgst_amount"] = _round_2(detail_subtotal["cgst_amount"] + line_cgst)
            detail_subtotal["sgst_amount"] = _round_2(detail_subtotal["sgst_amount"] + line_sgst)
            detail_subtotal["igst_amount"] = _round_2(detail_subtotal["igst_amount"] + line_igst)
            detail_subtotal["ugst_amount"] = _round_2(detail_subtotal["ugst_amount"] + line_ugst)
            detail_subtotal["export_amount"] = _round_2(detail_subtotal["export_amount"] + line_export)
            detail_subtotal["total_tax_amount"] = _round_2(detail_subtotal["total_tax_amount"] + line_total_tax)
        serial_no += 1

        subtotal["invoice_amount"] = _round_2(subtotal["invoice_amount"] + taxable_amount)
        subtotal["cgst_amount"] = _round_2(subtotal["cgst_amount"] + cgst_amount)
        subtotal["sgst_amount"] = _round_2(subtotal["sgst_amount"] + sgst_amount)
        subtotal["igst_amount"] = _round_2(subtotal["igst_amount"] + igst_amount)
        subtotal["ugst_amount"] = _round_2(subtotal["ugst_amount"] + ugst_amount)
        subtotal["export_amount"] = _round_2(subtotal["export_amount"] + export_amount)
        subtotal["total_tax_amount"] = _round_2(subtotal["total_tax_amount"] + total_tax_amount)

    for credit_note in credit_notes:
        invoice = credit_note_invoice_map.get(str(credit_note.sales_invoice_id))
        if not invoice:
            continue

        note_key = str(credit_note.id)
        invoice_number = (credit_note.credit_note_number or "").strip()
        bill_to_id = str(invoice.bill_to_customer_id or invoice.customer_id) if (invoice.bill_to_customer_id or invoice.customer_id) else None
        ship_to_id = str(invoice.ship_to_customer_id or invoice.customer_id) if (invoice.ship_to_customer_id or invoice.customer_id) else None
        bill_to_customer = customer_map.get(bill_to_id) if bill_to_id else None
        ship_to_customer = customer_map.get(ship_to_id) if ship_to_id else None

        bill_to_name = (bill_to_customer.company_name if bill_to_customer else "").strip()
        ship_to_name = (ship_to_customer.company_name if ship_to_customer else "").strip()
        bill_to_gstin = ((bill_to_customer.gstin if bill_to_customer else "") or "").strip().upper()
        bill_to_state = (
            (ship_to_customer.shipping_state if ship_to_customer else "")
            or (ship_to_customer.billing_state if ship_to_customer else "")
            or (bill_to_customer.shipping_state if bill_to_customer else "")
            or (bill_to_customer.billing_state if bill_to_customer else "")
            or ""
        ).strip()
        bill_to_state_code = (
            (ship_to_customer.shipping_state_code if ship_to_customer else "")
            or (ship_to_customer.billing_state_code if ship_to_customer else "")
            or (bill_to_customer.shipping_state_code if bill_to_customer else "")
            or (bill_to_customer.billing_state_code if bill_to_customer else "")
            or ""
        ).strip()
        place_of_supply = (
            (invoice.supply_state or "").strip()
            or ((invoice.supply_state_code or "").strip())
            or bill_to_state
            or bill_to_state_code
        )

        order_currency = sales_order_currency_map.get(str(invoice.sales_order_id or ""), {})
        currency = (
            (order_currency.get("currency_code") if order_currency else None)
            or (bill_to_customer.currency_code if bill_to_customer else None)
            or GST_REPORT_BASE_CURRENCY
        )
        currency = str(currency).strip().upper()

        stored_exchange_rate = float(order_currency.get("exchange_rate") or 0.0) if order_currency else 0.0

        totals = credit_note_totals_map.get(note_key) or {
            "taxable_amount": _paise_to_amount(credit_note.total_taxable_amount),
            "cgst_amount": _paise_to_amount(credit_note.total_cgst),
            "sgst_amount": _paise_to_amount(credit_note.total_sgst),
            "igst_amount": _paise_to_amount(credit_note.total_igst),
        }

        source_invoice_amount = _round_2(-totals["taxable_amount"])
        source_cgst = _round_2(-totals["cgst_amount"])
        source_sgst = _round_2(-totals["sgst_amount"])
        source_igst = _round_2(-totals["igst_amount"])

        invoice_type = _normalize_invoice_type(invoice.invoice_type, bool(invoice.is_igst))
        bill_to_country = _customer_country_for_gstr(bill_to_customer)
        bill_to_is_india = is_india_country(bill_to_country)
        is_export_transaction = invoice_type == INVOICE_TYPE_EXPORT or (not bill_to_is_india)
        display_bill_to_gstin = bill_to_gstin if bill_to_is_india else (bill_to_gstin or "N/A")
        invoice_rates = sorted(credit_note_rate_map.get(note_key, set()))

        conversion_rate, conversion_source, _ = _resolve_report_fx_rate(
            currency,
            stored_exchange_rate=stored_exchange_rate,
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
                "sales_invoice_date": _format_ddmmyyyy(credit_note.credit_note_date),
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

        for item in credit_note_item_map.get(note_key, []):
            item_name = _compose_item_description(
                item.get("product_name"),
                None,
                item.get("product_description"),
            )
            line_amount = _convert_with_rate(-item.get("taxable_amount", 0.0), float(conversion_rate or 1.0))
            line_cgst = _convert_with_rate(-item.get("cgst_amount", 0.0), float(conversion_rate or 1.0))
            line_sgst = _convert_with_rate(-item.get("sgst_amount", 0.0), float(conversion_rate or 1.0))
            line_igst = _convert_with_rate(-item.get("igst_amount", 0.0), float(conversion_rate or 1.0))
            line_ugst = 0.0
            line_export = 0.0

            if invoice_type == INVOICE_TYPE_UNION_TERRITORY:
                line_ugst = line_sgst
                line_sgst = 0.0
            elif invoice_type == INVOICE_TYPE_EXPORT:
                line_export = line_amount
                line_cgst = 0.0
                line_sgst = 0.0
                line_igst = 0.0
                line_ugst = 0.0

            line_total_tax = _round_2(line_cgst + line_sgst + line_igst + line_ugst + line_export)

            detail_rows.append(
                {
                    "s_no": detail_serial_no,
                    "sales_invoice_date": _format_ddmmyyyy(credit_note.credit_note_date),
                    "sales_invoice_no": invoice_number,
                    "bill_to_party_name": bill_to_name,
                    "bill_to_party_gstin_no": display_bill_to_gstin,
                    "place_of_supply": place_of_supply,
                    "ship_to_party_name": ship_to_name,
                    "item_name_description": item_name,
                    "hsn": (item.get("hsn_code") or ""),
                    "quantity": item.get("quantity", 0.0),
                    "invoice_amount": line_amount,
                    "currency": GST_REPORT_BASE_CURRENCY,
                    "tax_percent": item.get("gst_rate"),
                    "cgst_amount": line_cgst,
                    "sgst_amount": line_sgst,
                    "igst_amount": line_igst,
                    "ugst_amount": line_ugst,
                    "export_amount": line_export,
                    "total_tax_amount": line_total_tax,
                }
            )
            detail_serial_no += 1

            detail_subtotal["invoice_amount"] = _round_2(detail_subtotal["invoice_amount"] + line_amount)
            detail_subtotal["cgst_amount"] = _round_2(detail_subtotal["cgst_amount"] + line_cgst)
            detail_subtotal["sgst_amount"] = _round_2(detail_subtotal["sgst_amount"] + line_sgst)
            detail_subtotal["igst_amount"] = _round_2(detail_subtotal["igst_amount"] + line_igst)
            detail_subtotal["ugst_amount"] = _round_2(detail_subtotal["ugst_amount"] + line_ugst)
            detail_subtotal["export_amount"] = _round_2(detail_subtotal["export_amount"] + line_export)
            detail_subtotal["total_tax_amount"] = _round_2(detail_subtotal["total_tax_amount"] + line_total_tax)

        serial_no += 1

        subtotal["invoice_amount"] = _round_2(subtotal["invoice_amount"] + taxable_amount)
        subtotal["cgst_amount"] = _round_2(subtotal["cgst_amount"] + cgst_amount)
        subtotal["sgst_amount"] = _round_2(subtotal["sgst_amount"] + sgst_amount)
        subtotal["igst_amount"] = _round_2(subtotal["igst_amount"] + igst_amount)
        subtotal["ugst_amount"] = _round_2(subtotal["ugst_amount"] + ugst_amount)
        subtotal["export_amount"] = _round_2(subtotal["export_amount"] + export_amount)
        subtotal["total_tax_amount"] = _round_2(subtotal["total_tax_amount"] + total_tax_amount)

    if validation_errors and strict_validation:
        _raise_gstr1_validation_error(validation_errors)

    summary = {
        "total_taxable": _amount_to_paise(sum(row.get("invoice_amount", 0.0) for row in report_rows)),
        "total_cgst": _amount_to_paise(sum(row.get("cgst_amount", 0.0) for row in report_rows)),
        "total_sgst": _amount_to_paise(sum(row.get("sgst_amount", 0.0) for row in report_rows)),
        "total_igst": _amount_to_paise(sum(row.get("igst_amount", 0.0) for row in report_rows)),
    }

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
        "detail_count": len(detail_rows),
        "detail_items": detail_rows,
        "subtotal": subtotal,
        "detail_subtotal": detail_subtotal,
        "strict_validation": strict_validation,
        "validation_error_count": len(validation_errors),
        "validation_errors": validation_errors[:100],
        "problematic_records": problematic_records[:200],
    }


@router.get("/gstr1/export", dependencies=[Depends(require_module("reports"))])
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

    report_items = payload.get("detail_items") or payload.get("items", [])
    subtotal = payload.get("detail_subtotal") or payload.get("subtotal", {})
    filename_base = f"gstr1_{from_date.isoformat()}_{to_date.isoformat()}"
    
    # Fetch company details
    company_details = _get_company_details_for_gst_reports(db, current_user.company_id)

    if format_token == "xlsx":
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font
        from openpyxl.utils import get_column_letter

        wb = Workbook()
        ws = wb.active
        ws.title = "GSTR-1"

        # Add company details at the top
        ws.append([company_details["name"]])
        ws.cell(row=1, column=1).font = Font(bold=True, size=14)
        
        ws.append([company_details["address"]])
        ws.append([f"GSTIN: {company_details['gstin']}"])
        ws.append([f"Phone: {company_details['phone']}"])
        ws.append([])  # Empty row
        
        # Add report title and period
        ws.append([payload.get("report_title", "GSTR-1 (Sales / Output Tax Report)")])
        ws.cell(row=ws.max_row, column=1).font = Font(bold=True, size=12)
        
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
            "Item Name & Description",
            "HSN",
            "Quantity",
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

        header_row = ws.max_row
        ws.row_dimensions[header_row].height = 30
        header_alignment = Alignment(wrapText=True, horizontal="center", vertical="center")
        header_font = Font(bold=True)
        for col_idx in range(1, len(headers) + 1):
            cell = ws.cell(row=header_row, column=col_idx)
            cell.alignment = header_alignment
            cell.font = header_font

        column_widths = [
            6,   # S.No
            18,  # Tax Type
            14,  # Date
            22,  # Partner
            20,  # GSTIN
            20,  # Business Place
            20,  # Place of Supply
            30,  # Item Name & Description
            10,  # HSN
            10,  # Quantity
            16,  # GRN / Invoice Amount
            8,   # Currency
            8,   # Tax %
            12,  # CGST
            12,  # SGST
            12,  # IGST
            12,  # UGST
            12,  # Import / Export
            14,  # Total Tax
        ]
        for idx, width in enumerate(column_widths, start=1):
            ws.column_dimensions[get_column_letter(idx)].width = width

        header_row = ws.max_row
        ws.row_dimensions[header_row].height = 30
        header_alignment = Alignment(wrapText=True, horizontal="center", vertical="center")
        header_font = Font(bold=True)
        for col_idx in range(1, len(headers) + 1):
            cell = ws.cell(row=header_row, column=col_idx)
            cell.alignment = header_alignment
            cell.font = header_font

        column_widths = [
            6,   # S.No
            16,  # GRN Date
            18,  # GRN No
            22,  # Supplier
            20,  # Supplier GSTIN
            20,  # Business Place
            20,  # Place of Supply
            30,  # Item Name & Description
            10,  # HSN
            10,  # Quantity
            14,  # GRN Amount
            8,   # Currency
            8,   # Tax %
            12,  # CGST
            12,  # SGST
            12,  # IGST
            12,  # UGST
            10,  # Import
            14,  # Total Tax
        ]
        for idx, width in enumerate(column_widths, start=1):
            ws.column_dimensions[get_column_letter(idx)].width = width

        header_row = ws.max_row
        ws.row_dimensions[header_row].height = 30
        header_alignment = Alignment(wrapText=True, horizontal="center", vertical="center")
        header_font = Font(bold=True)
        for col_idx in range(1, len(headers) + 1):
            cell = ws.cell(row=header_row, column=col_idx)
            cell.alignment = header_alignment
            cell.font = header_font

        column_widths = [
            6,   # S.No
            16,  # Sales Invoice Date
            18,  # Sales Invoice No
            22,  # Bill To
            20,  # Bill GSTIN
            22,  # Place of Supply
            22,  # Ship To
            30,  # Item Name & Description
            10,  # HSN
            10,  # Quantity
            14,  # Invoice Amount
            8,   # Currency
            8,   # Tax %
            12,  # CGST
            12,  # SGST
            12,  # IGST
            12,  # UGST
            10,  # Export
            14,  # Total Tax
        ]
        for idx, width in enumerate(column_widths, start=1):
            ws.column_dimensions[get_column_letter(idx)].width = width

        for row in report_items:
            ws.append([
                row.get("s_no"),
                row.get("sales_invoice_date"),
                row.get("sales_invoice_no"),
                row.get("bill_to_party_name"),
                row.get("bill_to_party_gstin_no"),
                row.get("place_of_supply"),
                row.get("ship_to_party_name"),
                row.get("item_name_description"),
                row.get("hsn"),
                row.get("quantity"),
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
            "",
            "Sub Total",
            "",
            "",
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
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle, Image as RLImage
    from xml.sax.saxutils import escape as xml_escape

    stream = BytesIO()
    doc = SimpleDocTemplate(stream, pagesize=landscape(A4), leftMargin=18, rightMargin=18, topMargin=18, bottomMargin=18)
    styles = getSampleStyleSheet()
    table_cell_style = ParagraphStyle(
        "gstr1_table_cell",
        parent=styles["Normal"],
        fontSize=5.5,
        leading=6.5,
        spaceBefore=0,
        spaceAfter=0,
        wordWrap="CJK",
    )

    def to_table_paragraph(value: object) -> Paragraph:
        text = "" if value is None else str(value)
        return Paragraph(xml_escape(text), table_cell_style)

    # Build company header
    story = []
    if company_details["logo_data_uri"]:
        try:
            logo_img = RLImage(company_details["logo_data_uri"], width=50, height=50)
        except Exception:
            logo_img = Paragraph("<b>LOGO</b>", styles["Normal"])
    else:
        logo_img = Paragraph("<b>LOGO</b>", styles["Normal"])
    
    company_info_text = f"""
        <b>{xml_escape(company_details['name'])}</b><br/>
        {xml_escape(company_details['address'])}<br/>
        <b>GSTIN:</b> {xml_escape(company_details['gstin'])}<br/>
        <b>Phone:</b> {xml_escape(company_details['phone'])}
    """
    company_info = Paragraph(company_info_text, styles["Normal"])
    
    header_table = Table([[logo_img, company_info]], colWidths=[60, doc.width - 60])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 12))
    
    # Add report title and period
    story.append(Paragraph(payload.get("report_title", "GSTR-1 (Sales / Output Tax Report)"), styles["Heading2"]))
    story.append(Paragraph(
        f"Period: {payload.get('from_date_display') or from_date.isoformat()} to {payload.get('to_date_display') or to_date.isoformat()} | Frequency: {payload.get('frequency_label', '')}",
        styles["Normal"],
    ))
    story.append(Spacer(1, 8))

    table_data = [[
        to_table_paragraph("S.No"),
        to_table_paragraph("Sales Invoice Date"),
        to_table_paragraph("Sales Invoice No"),
        to_table_paragraph("Bill To"),
        to_table_paragraph("Bill GSTIN"),
        to_table_paragraph("Place of Supply"),
        to_table_paragraph("Ship To"),
        to_table_paragraph("Item Name & Description"),
        to_table_paragraph("HSN"),
        to_table_paragraph("Qty"),
        to_table_paragraph("Invoice Amount"),
        to_table_paragraph("Currency"),
        to_table_paragraph("Tax %"),
        to_table_paragraph("CGST"),
        to_table_paragraph("SGST"),
        to_table_paragraph("IGST"),
        to_table_paragraph("UGST"),
        to_table_paragraph("Export"),
        to_table_paragraph("Total Tax"),
    ]]

    for row in report_items:
        table_data.append([
            row.get("s_no", ""),
            row.get("sales_invoice_date", ""),
            row.get("sales_invoice_no", ""),
            to_table_paragraph(row.get("bill_to_party_name", "")),
            to_table_paragraph(row.get("bill_to_party_gstin_no", "")),
            to_table_paragraph(row.get("place_of_supply", "")),
            to_table_paragraph(row.get("ship_to_party_name", "")),
            to_table_paragraph(row.get("item_name_description", "")),
            row.get("hsn", ""),
            f"{float(row.get('quantity', 0.0)):.2f}",
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
        "", "", "", "", "", "", "",
        "Sub Total",
        "",
        "",
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

    col_fractions = [
        0.02,  # S.No
        0.05,  # Sales Invoice Date
        0.065,  # Sales Invoice No
        0.085,  # Bill To
        0.075,  # Bill GSTIN
        0.075,  # Place
        0.085,  # Ship To
        0.09,  # Item Name
        0.035,  # HSN
        0.035,  # Qty
        0.055,  # Invoice Amount
        0.035,  # Currency
        0.035,  # Tax %
        0.042,  # CGST
        0.042,  # SGST
        0.042,  # IGST
        0.042,  # UGST
        0.042,  # Export
        0.05,  # Total Tax
    ]
    col_widths = [doc.width * f for f in col_fractions]
    table = Table(table_data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E5E7EB")),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#9CA3AF")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 5.5),
        ("VALIGN", (0, 0), (-1, 0), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 1.5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 1.5),
        ("TOPPADDING", (0, 0), (-1, -1), 1.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(table)

    doc.build(story)
    stream.seek(0)
    pdf_bytes = stream.read()
    
    # Add ambassador watermark
    pdf_with_watermark = _add_ambassador_watermark_to_pdf(pdf_bytes, company_details["ambassador_logo_bytes"])
    stream = BytesIO(pdf_with_watermark)


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


@router.get("/gstr3b", dependencies=[Depends(require_module("reports"))])
async def gstr3b_report(
    from_date: date,
    to_date: date,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("reports_read")),
):
    _ensure_finance_tax_user(current_user)
    _ensure_valid_date_range(from_date, to_date)
    sales_rows = db.query(SalesInvoice).filter(
        SalesInvoice.company_id == current_user.company_id,
        SalesInvoice.invoice_date >= from_date,
        SalesInvoice.invoice_date <= to_date,
        SalesInvoice.status.in_(["issued", "partial_paid", "paid"]),
        SalesInvoice.is_deleted == False,
    ).all()
    purchase_rows = db.query(GoodsReceiptNote).filter(
        GoodsReceiptNote.company_id == current_user.company_id,
        GoodsReceiptNote.receipt_date >= from_date,
        GoodsReceiptNote.receipt_date <= to_date,
        GoodsReceiptNote.status == "confirmed",
        GoodsReceiptNote.is_deleted == False,
    ).all()

    output_tax = sum(row.total_gst for row in sales_rows)
    input_tax = sum(row.total_gst for row in purchase_rows)

    return {
        "output_tax": int(output_tax),
        "itc": int(input_tax),
        "net_tax_payable": int(output_tax - input_tax),
    }


@router.get("/gstr2", dependencies=[Depends(require_module("reports"))])
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
    from_date, to_date = _validate_frequency_date_window(from_date, to_date, normalized_frequency)

    grns = (
        db.query(GoodsReceiptNote)
        .filter(
            GoodsReceiptNote.company_id == current_user.company_id,
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

    grn_item_map: dict[str, list[dict]] = defaultdict(list)
    if grn_ids:
        item_rows = (
            db.query(
                GRNItem.grn_id,
                GRNItem.quantity,
                GRNItem.taxable_amount,
                GRNItem.cgst_amount,
                GRNItem.sgst_amount,
                GRNItem.igst_amount,
                GRNItem.gst_rate,
                Product.name.label("product_name"),
                Product.description.label("product_description"),
                Product.hsn_code.label("hsn_code"),
            )
            .outerjoin(Product, GRNItem.product_id == Product.id)
            .filter(
                GRNItem.grn_id.in_(grn_ids),
                GRNItem.is_deleted == False,
            )
            .all()
        )
        for item in item_rows:
            grn_key = str(item.grn_id)
            grn_item_map[grn_key].append(
                {
                    "product_name": item.product_name,
                    "product_description": item.product_description,
                    "hsn_code": item.hsn_code,
                    "quantity": _round_quantity(item.quantity),
                    "taxable_amount": _paise_to_amount(item.taxable_amount),
                    "cgst_amount": _paise_to_amount(item.cgst_amount),
                    "sgst_amount": _paise_to_amount(item.sgst_amount),
                    "igst_amount": _paise_to_amount(item.igst_amount),
                    "gst_rate": _round_2(float(item.gst_rate or 0.0)),
                }
            )

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

    company = db.query(Company).filter(Company.id == current_user.company_id).first()
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
                GoodsReceiptNote.company_id == current_user.company_id,
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
    detail_rows: list[dict] = []
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
    detail_subtotal = {
        "grn_amount": 0.0,
        "cgst_amount": 0.0,
        "sgst_amount": 0.0,
        "igst_amount": 0.0,
        "ugst_amount": 0.0,
        "import_amount": 0.0,
        "total_tax_amount": 0.0,
    }

    serial_no = 1
    detail_serial_no = 1
    for grn in grns:
        row_error_start_index = len(validation_errors)
        grn_key = str(grn.id)
        grn_number = (grn.grn_number or "").strip()
        supplier = supplier_map.get(str(grn.supplier_id)) if grn.supplier_id else None

        supplier_name = (supplier.company_name if supplier else "").strip()
        supplier_gstin = ((supplier.gstin if supplier else "") or "").strip().upper()
        supplier_gstin_status = ((supplier.gstin_status if supplier else "") or "non-registered").strip().lower()
        supplier_state = ((supplier.state if supplier else "") or "").strip()
        supplier_state_code = ((supplier.state_code if supplier else "") or "").strip()
        place_of_supply = (
            (supplier.place_of_supply if supplier else "")
            or supplier_state
            or supplier_state_code
            or ""
        ).strip()
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
            if supplier_gstin:
                if not GSTIN_REGEX.match(supplier_gstin):
                    validation_errors.append(
                        f"VAL-002 GSTIN Format Check failed for GRN {grn_number}: GSTIN {supplier_gstin} is invalid"
                    )
            elif supplier_gstin_status == "registered":
                validation_errors.append(
                    f"VAL-010 Mandatory Fields Check failed for GRN {grn_number}: supplier GSTIN is required"
                )
            else:
                if not supplier_state:
                    validation_errors.append(
                        f"VAL-010 Mandatory Fields Check failed for GRN {grn_number}: state is required for non-registered GST suppliers"
                    )
                if not supplier_state_code:
                    validation_errors.append(
                        f"VAL-010 Mandatory Fields Check failed for GRN {grn_number}: state code is required for GST calculation"
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

        for item in grn_item_map.get(grn_key, []):
            item_name = _compose_item_description(
                item.get("product_name"),
                None,
                item.get("product_description"),
            )
            line_amount = _convert_with_rate(item.get("taxable_amount"), float(conversion_rate or 1.0))
            line_cgst = _convert_with_rate(item.get("cgst_amount"), float(conversion_rate or 1.0))
            line_sgst = _convert_with_rate(item.get("sgst_amount"), float(conversion_rate or 1.0))
            line_igst = _convert_with_rate(item.get("igst_amount"), float(conversion_rate or 1.0))
            line_ugst = 0.0
            line_import = 0.0

            if is_import:
                line_import = line_igst
                line_igst = 0.0
                line_cgst = 0.0
                line_sgst = 0.0
                line_ugst = 0.0
            elif is_ut and not is_inter_state:
                line_ugst = line_sgst
                line_sgst = 0.0

            line_total_tax = _round_2(line_cgst + line_sgst + line_igst + line_ugst + line_import)

            detail_rows.append(
                {
                    "s_no": detail_serial_no,
                    "grn_date": _format_ddmmyyyy(grn.receipt_date),
                    "grn_no": grn_number,
                    "supplier_name": supplier_name,
                    "supplier_gstin_no": display_supplier_gstin,
                    "business_place": business_place,
                    "place_of_supply": place_of_supply,
                    "item_name_description": item_name,
                    "hsn": (item.get("hsn_code") or ""),
                    "quantity": item.get("quantity", 0.0),
                    "grn_amount": line_amount,
                    "currency": GST_REPORT_BASE_CURRENCY,
                    "tax_percent": item.get("gst_rate"),
                    "cgst_amount": line_cgst,
                    "sgst_amount": line_sgst,
                    "igst_amount": line_igst,
                    "ugst_amount": line_ugst,
                    "import_amount": line_import,
                    "total_tax_amount": line_total_tax,
                }
            )
            detail_serial_no += 1

            detail_subtotal["grn_amount"] = _round_2(detail_subtotal["grn_amount"] + line_amount)
            detail_subtotal["cgst_amount"] = _round_2(detail_subtotal["cgst_amount"] + line_cgst)
            detail_subtotal["sgst_amount"] = _round_2(detail_subtotal["sgst_amount"] + line_sgst)
            detail_subtotal["igst_amount"] = _round_2(detail_subtotal["igst_amount"] + line_igst)
            detail_subtotal["ugst_amount"] = _round_2(detail_subtotal["ugst_amount"] + line_ugst)
            detail_subtotal["import_amount"] = _round_2(detail_subtotal["import_amount"] + line_import)
            detail_subtotal["total_tax_amount"] = _round_2(detail_subtotal["total_tax_amount"] + line_total_tax)
        serial_no += 1

        subtotal["grn_amount"] = _round_2(subtotal["grn_amount"] + grn_amount)
        subtotal["cgst_amount"] = _round_2(subtotal["cgst_amount"] + cgst_amount)
        subtotal["sgst_amount"] = _round_2(subtotal["sgst_amount"] + sgst_amount)
        subtotal["igst_amount"] = _round_2(subtotal["igst_amount"] + igst_amount)
        subtotal["ugst_amount"] = _round_2(subtotal["ugst_amount"] + ugst_amount)
        subtotal["import_amount"] = _round_2(subtotal["import_amount"] + import_amount)
        subtotal["total_tax_amount"] = _round_2(subtotal["total_tax_amount"] + total_tax_amount)

    if validation_errors and strict_validation:
        _raise_gstr2_validation_error(validation_errors)

    summary = {
        "total_taxable": _amount_to_paise(sum(row.get("grn_amount", 0.0) for row in report_rows)),
        "total_cgst": _amount_to_paise(sum(row.get("cgst_amount", 0.0) for row in report_rows)),
        "total_sgst": _amount_to_paise(sum(row.get("sgst_amount", 0.0) for row in report_rows)),
        "total_igst": _amount_to_paise(sum(row.get("igst_amount", 0.0) for row in report_rows)),
    }

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
        "detail_count": len(detail_rows),
        "detail_items": detail_rows,
        "subtotal": subtotal,
        "detail_subtotal": detail_subtotal,
        "strict_validation": strict_validation,
        "validation_error_count": len(validation_errors),
        "validation_errors": validation_errors[:100],
        "problematic_records": problematic_records[:200],
    }


@router.get("/gstr2/export", dependencies=[Depends(require_module("reports"))])
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

    report_items = payload.get("detail_items") or payload.get("items", [])
    subtotal = payload.get("detail_subtotal") or payload.get("subtotal", {})
    filename_base = f"gstr2_{from_date.isoformat()}_{to_date.isoformat()}"
    
    # Fetch company details
    company_details = _get_company_details_for_gst_reports(db, current_user.company_id)

    if format_token == "xlsx":
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font
        from openpyxl.utils import get_column_letter

        wb = Workbook()
        ws = wb.active
        ws.title = "GSTR-2"

        # Add company details at the top
        ws.append([company_details["name"]])
        ws.cell(row=1, column=1).font = Font(bold=True, size=14)
        
        ws.append([company_details["address"]])
        ws.append([f"GSTIN: {company_details['gstin']}"])
        ws.append([f"Phone: {company_details['phone']}"])
        ws.append([])  # Empty row
        
        # Add report title and period
        ws.append([payload.get("report_title", "GSTR-2 (Purchase / Input Tax Report)")])
        ws.cell(row=ws.max_row, column=1).font = Font(bold=True, size=12)
        
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
            "Item Name & Description",
            "HSN",
            "Quantity",
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
                row.get("item_name_description"),
                row.get("hsn"),
                row.get("quantity"),
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
            "",
            "Sub Total",
            "",
            "",
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
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle, Image as RLImage
    from xml.sax.saxutils import escape as xml_escape

    stream = BytesIO()
    doc = SimpleDocTemplate(stream, pagesize=landscape(A4), leftMargin=18, rightMargin=18, topMargin=18, bottomMargin=18)
    styles = getSampleStyleSheet()
    table_cell_style = ParagraphStyle(
        "gstr2_table_cell",
        parent=styles["Normal"],
        fontSize=5.5,
        leading=6.5,
        spaceBefore=0,
        spaceAfter=0,
        wordWrap="CJK",
    )

    def to_table_paragraph(value: object) -> Paragraph:
        text = "" if value is None else str(value)
        return Paragraph(xml_escape(text), table_cell_style)

    # Build company header
    story = []
    if company_details["logo_data_uri"]:
        try:
            logo_img = RLImage(company_details["logo_data_uri"], width=50, height=50)
        except Exception:
            logo_img = Paragraph("<b>LOGO</b>", styles["Normal"])
    else:
        logo_img = Paragraph("<b>LOGO</b>", styles["Normal"])
    
    company_info_text = f"""
        <b>{xml_escape(company_details['name'])}</b><br/>
        {xml_escape(company_details['address'])}<br/>
        <b>GSTIN:</b> {xml_escape(company_details['gstin'])}<br/>
        <b>Phone:</b> {xml_escape(company_details['phone'])}
    """
    company_info = Paragraph(company_info_text, styles["Normal"])
    
    header_table = Table([[logo_img, company_info]], colWidths=[60, doc.width - 60])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 12))
    
    # Add report title and period
    story.append(Paragraph(payload.get("report_title", "GSTR-2 (Purchase / Input Tax Report)"), styles["Heading2"]))
    story.append(Paragraph(
        f"Period: {payload.get('from_date_display') or from_date.isoformat()} to {payload.get('to_date_display') or to_date.isoformat()} | Frequency: {payload.get('frequency_label', '')}",
        styles["Normal"],
    ))
    story.append(Spacer(1, 8))

    table_data = [[
        to_table_paragraph("S.No"),
        to_table_paragraph("GRN Date"),
        to_table_paragraph("GRN No"),
        to_table_paragraph("Supplier"),
        to_table_paragraph("Supplier GSTIN"),
        to_table_paragraph("Business Place"),
        to_table_paragraph("Place of Supply"),
        to_table_paragraph("Item Name & Description"),
        to_table_paragraph("HSN"),
        to_table_paragraph("Qty"),
        to_table_paragraph("GRN Amount"),
        to_table_paragraph("Currency"),
        to_table_paragraph("Tax %"),
        to_table_paragraph("CGST"),
        to_table_paragraph("SGST"),
        to_table_paragraph("IGST"),
        to_table_paragraph("UGST"),
        to_table_paragraph("Import"),
        to_table_paragraph("Total Tax"),
    ]]

    for row in report_items:
        table_data.append([
            row.get("s_no", ""),
            row.get("grn_date", ""),
            row.get("grn_no", ""),
            to_table_paragraph(row.get("supplier_name", "")),
            to_table_paragraph(row.get("supplier_gstin_no", "")),
            to_table_paragraph(row.get("business_place", "")),
            to_table_paragraph(row.get("place_of_supply", "")),
            to_table_paragraph(row.get("item_name_description", "")),
            row.get("hsn", ""),
            f"{float(row.get('quantity', 0.0)):.2f}",
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
        "", "", "", "", "", "", "",
        "Sub Total",
        "",
        "",
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

    col_fractions = [
        0.02,  # S.No
        0.05,  # GRN Date
        0.065,  # GRN No
        0.085,  # Supplier
        0.075,  # Supplier GSTIN
        0.075,  # Business Place
        0.07,  # Place of Supply
        0.105,  # Item Name
        0.035,  # HSN
        0.035,  # Qty
        0.055,  # GRN Amount
        0.035,  # Currency
        0.035,  # Tax %
        0.042,  # CGST
        0.042,  # SGST
        0.042,  # IGST
        0.042,  # UGST
        0.042,  # Import
        0.05,  # Total Tax
    ]
    col_widths = [doc.width * f for f in col_fractions]
    table = Table(table_data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E5E7EB")),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#9CA3AF")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 5.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 1.5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 1.5),
        ("TOPPADDING", (0, 0), (-1, -1), 1.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(table)

    doc.build(story)
    stream.seek(0)
    pdf_bytes = stream.read()
    
    # Add ambassador watermark
    pdf_with_watermark = _add_ambassador_watermark_to_pdf(pdf_bytes, company_details["ambassador_logo_bytes"])
    stream = BytesIO(pdf_with_watermark)

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


@router.get("/gst-reconciliation", dependencies=[Depends(require_module("reports"))])
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

    company = db.query(Company).filter(Company.id == current_user.company_id).first()
    business_place = (
        ", ".join([part for part in [company.city if company else None, company.state if company else None] if part])
        if company else ""
    )
    if not business_place:
        business_place = (company.name if company else "") or "Primary Business Place"

    items: list[dict] = []
    running_s_no = 1

    detail_items: list[dict] = []
    detail_running_s_no = 1

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
                "reference_no": row.get("grn_no", ""),
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
                "reference_no": row.get("sales_invoice_no", ""),
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

    for row in gstr2_payload.get("detail_items", []) or []:
        detail_items.append(
            {
                "s_no": detail_running_s_no,
                "tax_type": "Input Tax (Purchase)",
                "date": row.get("grn_date"),
                "reference_no": row.get("grn_no", ""),
                "name_of_partner": row.get("supplier_name", ""),
                "partner_gstin_no": row.get("supplier_gstin_no", ""),
                "business_place": row.get("business_place") or business_place,
                "place_of_supply": row.get("place_of_supply", ""),
                "item_name_description": row.get("item_name_description", ""),
                "hsn": row.get("hsn", ""),
                "quantity": row.get("quantity", 0.0),
                "grn_or_invoice_amount": _round_2(float(row.get("grn_amount", 0.0))),
                "currency": row.get("currency", "INR"),
                "tax_percent": _coerce_tax_percent(row.get("tax_percent")),
                "cgst_amount": _round_2(float(row.get("cgst_amount", 0.0))),
                "sgst_amount": _round_2(float(row.get("sgst_amount", 0.0))),
                "igst_amount": _round_2(float(row.get("igst_amount", 0.0))),
                "ugst_amount": _round_2(float(row.get("ugst_amount", 0.0))),
                "import_export_amount": _round_2(float(row.get("import_amount", 0.0))),
                "total_tax_amount": _round_2(float(row.get("total_tax_amount", 0.0))),
            }
        )
        detail_running_s_no += 1

    for row in gstr1_payload.get("detail_items", []) or []:
        detail_items.append(
            {
                "s_no": detail_running_s_no,
                "tax_type": "Output Tax (Sales)",
                "date": row.get("sales_invoice_date"),
                "reference_no": row.get("sales_invoice_no", ""),
                "name_of_partner": row.get("bill_to_party_name", ""),
                "partner_gstin_no": row.get("bill_to_party_gstin_no", ""),
                "business_place": business_place,
                "place_of_supply": row.get("place_of_supply", ""),
                "item_name_description": row.get("item_name_description", ""),
                "hsn": row.get("hsn", ""),
                "quantity": row.get("quantity", 0.0),
                "grn_or_invoice_amount": _round_2(float(row.get("invoice_amount", 0.0))),
                "currency": row.get("currency", "INR"),
                "tax_percent": _coerce_tax_percent(row.get("tax_percent")),
                "cgst_amount": _round_2(float(row.get("cgst_amount", 0.0))),
                "sgst_amount": _round_2(float(row.get("sgst_amount", 0.0))),
                "igst_amount": _round_2(float(row.get("igst_amount", 0.0))),
                "ugst_amount": _round_2(float(row.get("ugst_amount", 0.0))),
                "import_export_amount": _round_2(float(row.get("export_amount", 0.0))),
                "total_tax_amount": _round_2(float(row.get("total_tax_amount", 0.0))),
            }
        )
        detail_running_s_no += 1

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
        "detail_count": len(detail_items),
        "detail_items": detail_items,
        "subtotal_input_tax": subtotal_input_tax,
        "subtotal_output_tax": subtotal_output_tax,
        "difference_amount": difference_amount,
        "strict_validation": strict_validation,
        "validation_error_count": len(validation_errors),
        "validation_errors": validation_errors[:100],
        "problematic_records": problematic_records[:200],
    }


@router.get("/gst-reconciliation/export", dependencies=[Depends(require_module("reports"))])
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

    report_items = payload.get("detail_items") or payload.get("items", [])
    subtotal_input = payload.get("subtotal_input_tax", {})
    subtotal_output = payload.get("subtotal_output_tax", {})
    difference_amount = payload.get("difference_amount", {})

    filename_base = f"gst_reconciliation_{from_date.isoformat()}_{to_date.isoformat()}"
    
    # Fetch company details
    company_details = _get_company_details_for_gst_reports(db, current_user.company_id)

    if format_token == "xlsx":
        from openpyxl import Workbook
        from openpyxl.styles import Font

        wb = Workbook()
        ws = wb.active
        ws.title = "GST Reconciliation"

        # Add company details at the top
        ws.append([company_details["name"]])
        ws.cell(row=1, column=1).font = Font(bold=True, size=14)
        
        ws.append([company_details["address"]])
        ws.append([f"GSTIN: {company_details['gstin']}"])
        ws.append([f"Phone: {company_details['phone']}"])
        ws.append([])  # Empty row
        
        # Add report title and period
        ws.append([payload.get("report_title", "GST Reconciliation Report")])
        ws.cell(row=ws.max_row, column=1).font = Font(bold=True, size=12)
        
        ws.append([
            f"Period: {payload.get('from_date_display') or from_date.isoformat()} to {payload.get('to_date_display') or to_date.isoformat()} | Frequency: {payload.get('frequency_label', '')}"
        ])
        ws.append([])

        headers = [
            "S.No",
            "Tax Type",
            "Date",
            "Reference No",
            "Name of the Partner",
            "Partner GSTIN No",
            "Business Place",
            "Place of Supply",
            "Item Name & Description",
            "HSN",
            "Quantity",
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
                row.get("reference_no"),
                row.get("name_of_partner"),
                row.get("partner_gstin_no"),
                row.get("business_place"),
                row.get("place_of_supply"),
                row.get("item_name_description"),
                row.get("hsn"),
                row.get("quantity"),
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
        ws.append(["Sub Total (Input Tax)", "", "", "", "", "", "", "", "", "", "", subtotal_input.get("transaction_amount", 0.0), "", "", subtotal_input.get("cgst_amount", 0.0), subtotal_input.get("sgst_amount", 0.0), subtotal_input.get("igst_amount", 0.0), subtotal_input.get("ugst_amount", 0.0), subtotal_input.get("import_export_amount", 0.0), subtotal_input.get("total_tax_amount", 0.0)])
        ws.append(["Sub Total (Output Tax)", "", "", "", "", "", "", "", "", "", "", subtotal_output.get("transaction_amount", 0.0), "", "", subtotal_output.get("cgst_amount", 0.0), subtotal_output.get("sgst_amount", 0.0), subtotal_output.get("igst_amount", 0.0), subtotal_output.get("ugst_amount", 0.0), subtotal_output.get("import_export_amount", 0.0), subtotal_output.get("total_tax_amount", 0.0)])
        ws.append(["Difference Amount (Output - Input)", "", "", "", "", "", "", "", "", "", "", difference_amount.get("transaction_amount", 0.0), "", "", difference_amount.get("cgst_amount", 0.0), difference_amount.get("sgst_amount", 0.0), difference_amount.get("igst_amount", 0.0), difference_amount.get("ugst_amount", 0.0), difference_amount.get("import_export_amount", 0.0), difference_amount.get("total_tax_amount", 0.0)])

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
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle, Image as RLImage
    from xml.sax.saxutils import escape as xml_escape

    stream = BytesIO()
    doc = SimpleDocTemplate(stream, pagesize=landscape(A4), leftMargin=18, rightMargin=18, topMargin=18, bottomMargin=18)
    styles = getSampleStyleSheet()
    table_cell_style = ParagraphStyle(
        "gst_recon_table_cell",
        parent=styles["Normal"],
        fontSize=5.5,
        leading=6.5,
        spaceBefore=0,
        spaceAfter=0,
        wordWrap="CJK",
    )

    def to_table_paragraph(value: object) -> Paragraph:
        text = "" if value is None else str(value)
        return Paragraph(xml_escape(text), table_cell_style)

    # Build company header
    story = []
    if company_details["logo_data_uri"]:
        try:
            logo_img = RLImage(company_details["logo_data_uri"], width=50, height=50)
        except Exception:
            logo_img = Paragraph("<b>LOGO</b>", styles["Normal"])
    else:
        logo_img = Paragraph("<b>LOGO</b>", styles["Normal"])
    
    company_info_text = f"""
        <b>{xml_escape(company_details['name'])}</b><br/>
        {xml_escape(company_details['address'])}<br/>
        <b>GSTIN:</b> {xml_escape(company_details['gstin'])}<br/>
        <b>Phone:</b> {xml_escape(company_details['phone'])}
    """
    company_info = Paragraph(company_info_text, styles["Normal"])
    
    header_table = Table([[logo_img, company_info]], colWidths=[60, doc.width - 60])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 12))
    
    # Add report title and period
    story.append(Paragraph(payload.get("report_title", "GST Reconciliation Report"), styles["Heading2"]))
    story.append(Paragraph(
        f"Period: {payload.get('from_date_display') or from_date.isoformat()} to {payload.get('to_date_display') or to_date.isoformat()} | Frequency: {payload.get('frequency_label', '')}",
        styles["Normal"],
    ))
    story.append(Spacer(1, 8))

    table_data = [[
        to_table_paragraph("S.No"),
        to_table_paragraph("Tax Type"),
        to_table_paragraph("Date"),
        to_table_paragraph("Reference No"),
        to_table_paragraph("Partner"),
        to_table_paragraph("GSTIN"),
        to_table_paragraph("Business Place"),
        to_table_paragraph("Place of Supply"),
        to_table_paragraph("Item Name & Description"),
        to_table_paragraph("HSN"),
        to_table_paragraph("Qty"),
        to_table_paragraph("Amount"),
        to_table_paragraph("Currency"),
        to_table_paragraph("Tax %"),
        to_table_paragraph("CGST"),
        to_table_paragraph("SGST"),
        to_table_paragraph("IGST"),
        to_table_paragraph("UGST"),
        to_table_paragraph("Imp/Exp"),
        to_table_paragraph("Total Tax"),
    ]]

    for row in report_items:
        table_data.append([
            row.get("s_no", ""),
            to_table_paragraph(row.get("tax_type", "")),
            row.get("date", ""),
            to_table_paragraph(row.get("reference_no", "")),
            to_table_paragraph(row.get("name_of_partner", "")),
            to_table_paragraph(row.get("partner_gstin_no", "")),
            to_table_paragraph(row.get("business_place", "")),
            to_table_paragraph(row.get("place_of_supply", "")),
            to_table_paragraph(row.get("item_name_description", "")),
            row.get("hsn", ""),
            f"{float(row.get('quantity', 0.0)):.2f}",
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

    col_fractions = [
        0.02,  # S.No
        0.075,  # Tax Type
        0.06,  # Date
        0.04,  # Reference No
        0.075,  # Partner
        0.075,  # GSTIN
        0.07,  # Business Place
        0.07,  # Place of Supply
        0.06,  # Item Name (reduced to make space for Reference No)
        0.035,  # HSN
        0.035,  # Qty
        0.055,  # Amount
        0.035,  # Currency
        0.035,  # Tax %
        0.04,  # CGST
        0.04,  # SGST
        0.04,  # IGST
        0.04,  # UGST
        0.04,  # Imp/Exp
        0.05,  # Total Tax
    ]
    col_widths = [doc.width * f for f in col_fractions]
    table = Table(table_data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E5E7EB")),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#9CA3AF")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 5.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 1.5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 1.5),
        ("TOPPADDING", (0, 0), (-1, -1), 1.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(table)
    story.append(Spacer(1, 8))
    story.append(Paragraph(f"Sub Total (Input Tax) - Total Tax: {float(subtotal_input.get('total_tax_amount', 0.0)):.2f}", styles["Normal"]))
    story.append(Paragraph(f"Sub Total (Output Tax) - Total Tax: {float(subtotal_output.get('total_tax_amount', 0.0)):.2f}", styles["Normal"]))
    story.append(Paragraph(f"Difference (Output - Input) - Total Tax: {float(difference_amount.get('total_tax_amount', 0.0)):.2f}", styles["Normal"]))

    doc.build(story)
    stream.seek(0)
    pdf_bytes = stream.read()
    
    # Add ambassador watermark
    pdf_with_watermark = _add_ambassador_watermark_to_pdf(pdf_bytes, company_details["ambassador_logo_bytes"])
    stream = BytesIO(pdf_with_watermark)

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


@router.get("/gst-audit-trail", dependencies=[Depends(require_module("reports"))])
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
    from_date, to_date = _validate_frequency_date_window(from_date, to_date, normalized_frequency)

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


@router.get("/action-logs", dependencies=[Depends(require_module("audit_logs"))])
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
    if selected_module and selected_module not in FINANCIAL_ACTION_LOG_MODULES:
        return {
            "report_title": "Action Logs",
            "from_date": from_date.isoformat(),
            "to_date": to_date.isoformat(),
            "from_date_display": _format_ddmmyyyy(from_date),
            "to_date_display": _format_ddmmyyyy(to_date),
            "module": selected_module,
            "action_type": (action_type or "all").strip().upper() or "all",
            "user_query": (user_query or "").strip(),
            "reference": (reference or "").strip(),
            "page": page,
            "page_size": page_size,
            "total": 0,
            "total_pages": 0,
            "count": 0,
            "items": [],
        }

    action_type_token = (action_type or "all").strip().upper()
    selected_action_type = None if action_type_token in {"", "ALL"} else action_type_token

    user_token = (user_query or "").strip()
    user_filter = f"%{user_token}%" if user_token else None

    reference_token = (reference or "").strip()
    reference_filter = f"%{reference_token}%" if reference_token else None

    count_row = db.execute(
        text(
            f"""
            SELECT COUNT(*)
            FROM audit_logs a
            LEFT JOIN users u ON u.id = a.user_id
            WHERE a.created_at::date >= :from_date
              AND a.created_at::date <= :to_date
              AND LOWER(COALESCE(a.module_name, '')) IN ('{FINANCIAL_ACTION_LOG_MODULES_SQL}')
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
              AND (:company_id IS NULL OR a.company_id = CAST(:company_id AS UUID))
            """
        ),
        {
            "from_date": from_date,
            "to_date": to_date,
            "module_name": selected_module,
            "action_type": selected_action_type,
            "user_filter": user_filter,
            "reference_filter": reference_filter,
            "company_id": str(current_user.company_id) if current_user.company_id else None,
        },
    ).scalar()
    total_count = int(count_row or 0)
    offset = (page - 1) * page_size

    rows = db.execute(
        text(
            f"""
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
                a.details,
                a.version
            FROM audit_logs a
            LEFT JOIN users u ON u.id = a.user_id
            WHERE a.created_at::date >= :from_date
              AND a.created_at::date <= :to_date
              AND LOWER(COALESCE(a.module_name, '')) IN ('{FINANCIAL_ACTION_LOG_MODULES_SQL}')
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
              AND (:company_id IS NULL OR a.company_id = CAST(:company_id AS UUID))
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
            "company_id": str(current_user.company_id) if current_user.company_id else None,
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

        module_name = (row.get("module_name") or "").strip().lower()
        record_reference = (row.get("record_reference") or "").strip()

        # Resolve a human-friendly document number (INV-00027, PO-001, GRN-001, ...).
        extracted_ref = _extract_document_reference(row.get("record_reference"), details, db, module_name)
        document_ref = extracted_ref or ("" if _parse_uuid(record_reference) else record_reference)

        # Re-compose the description in plain business language: document number
        # (never a UUID), past-tense action, and field-level "old -> new" changes
        # when captured. This also upgrades historical rows whose stored text was
        # built before the resolved document number was available.
        description = compose_audit_description(
            action_type=(row.get("action_type") or ""),
            module_name=module_name,
            document_reference=document_ref,
            details=details,
            status=(row.get("status") or "success"),
        )

        # When no explicit field changes were captured, surface the document amount
        # as context (e.g. created/issued documents) instead of an "old -> new" line.
        if not (isinstance(details, dict) and details.get("changes")):
            amount_value = _resolve_action_log_amount(db, module_name, record_reference)
            amount_label = _format_inr_amount(amount_value)
            if amount_label:
                description = f"{description}\nAmount: {amount_label}"

        version_value = row.get("version")
        version_int = int(version_value) if version_value is not None else None

        items.append(
            {
                "id": str(row.get("id")),
                "version": version_int,
                "version_label": f"Version {int_to_roman(version_int)}" if version_int else None,
                "user_id": str(row.get("user_id")) if row.get("user_id") else None,
                "user_name": row.get("user_name") or "System",
                "action": row.get("action") or "",
                "action_type": row.get("action_type") or "",
                "module_name": row.get("module_name") or "",
                "record_reference": row.get("record_reference") or "",
                "reference": extracted_ref,
                "description": description,
                "status": row.get("status") or "",
                "timestamp": row.get("created_at").isoformat() if row.get("created_at") else None,
                "details": details,
            }
        )

    total_pages = (total_count + page_size - 1) // page_size if total_count else 0

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


@router.get("/retention-status", dependencies=[Depends(require_module("audit_logs"))])
async def retention_status_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("reports_read")),
):
    """
    Get retention status for audit logs and GST audit trail.
    
    Shows:
    - Current retention policy (15 days)
    - Total records in each table
    - Number of old records (>15 days)
    - Oldest record date in each table
    """
    from app.services.retention_cleanup import get_retention_status
    
    try:
        status = get_retention_status(db)
        return status
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting retention status: {str(e)}")


@router.post("/retention-cleanup", dependencies=[Depends(require_module("audit_logs"))])
async def run_retention_cleanup_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """
    Manually trigger retention cleanup.
    
    Deletes audit logs and GST audit trail records older than 15 days.
    Requires admin permissions.
    """
    from app.services.retention_cleanup import run_retention_cleanup
    
    try:
        stats = run_retention_cleanup(db)
        
        log_audit_event(
            db,
            action="RETENTION:CLEANUP_EXECUTED",
            resource_type="system",
            status="success",
            user_id=current_user.id,
            details={
                "action_logs_deleted": stats["action_logs_deleted"],
                "gst_audit_logs_deleted": stats["gst_audit_logs_deleted"],
                "cutoff_date": stats["cutoff_date"],
                "executed_at": datetime.utcnow().isoformat(),
            },
        )
        db.commit()
        
        return {
            "success": True,
            "message": "Retention cleanup completed successfully",
            "stats": stats,
        }
    except Exception as e:
        log_audit_event(
            db,
            action="RETENTION:CLEANUP_FAILED",
            resource_type="system",
            status="error",
            user_id=current_user.id,
            details={
                "error": str(e),
                "executed_at": datetime.utcnow().isoformat(),
            },
        )
        db.commit()
        raise HTTPException(status_code=500, detail=f"Retention cleanup failed: {str(e)}")


@router.get("/pl", dependencies=[Depends(require_module("reports"))])
async def profit_and_loss_report(
    from_date: date,
    to_date: date,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("reports_read")),
):
    _ensure_valid_date_range(from_date, to_date)
    sales_rows = db.query(SalesInvoice).filter(
        SalesInvoice.company_id == current_user.company_id,
        SalesInvoice.invoice_date >= from_date,
        SalesInvoice.invoice_date <= to_date,
        SalesInvoice.status.in_(["issued", "partial_paid", "paid"]),
        SalesInvoice.is_deleted == False,
    ).all()
    purchase_rows = db.query(GoodsReceiptNote).filter(
        GoodsReceiptNote.company_id == current_user.company_id,
        GoodsReceiptNote.receipt_date >= from_date,
        GoodsReceiptNote.receipt_date <= to_date,
        GoodsReceiptNote.status == "confirmed",
        GoodsReceiptNote.is_deleted == False,
    ).all()

    # Net sales = Sales Invoices + tenant Service Invoices (taxable base), so the
    # P&L reflects total tenant revenue. Service invoices are tenant-isolated and
    # exclude Mecandria's platform subscription bills.
    svc_taxable = _svc_revenue_sum(
        db, current_user.company_id, ServiceInvoice.total_taxable_amount,
        ServiceInvoice.invoice_date >= from_date,
        ServiceInvoice.invoice_date <= to_date,
    )
    # Sales invoices converted to base (INR) via each invoice's stored exchange rate.
    net_sales = int(sum(_to_base(row.total_taxable_amount, row.exchange_rate) for row in sales_rows)) + svc_taxable
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
