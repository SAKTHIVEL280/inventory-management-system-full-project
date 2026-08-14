"""Sales workflow router (Quotation, SO, Invoice, Sales Return).

Production-ready with fixes for:
- BUG-01: Materialized view refresh after stock changes
- BUG-02: IGST auto-detection from state codes
- BUG-05: Added convert-to-invoice endpoint
- BUG-13: Force draft status on creation
- BUG-14: Quotation expiry check on read
- BUG-19: Sales return tax matches original invoice
- BUG-25: Sales return adjusts invoice amount_due
"""
from datetime import date, datetime, timedelta
from email.message import EmailMessage
from pathlib import Path
import re
import smtplib
import ssl
from typing import Any
from types import SimpleNamespace
from uuid import UUID
from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from app.database import get_db
from app.dependencies import enforce_resource_ownership, require_permissions, require_role, scope_query_to_company
from app.models.user import User
from app.models.product import Product, StockLedger
from app.services.audit_service import build_audit_changes
from app.models.customer import Customer
from app.models.inventory_count import InventoryCountDifferenceAudit, InventoryCountItem
from app.models.purchase import GoodsReceiptNote, GRNItem, PurchaseReturn, PurchaseReturnItem
from app.models.rdn import ReturnDeliveryNote, ReturnDeliveryNoteItem, RdnCreditNote, RdnCreditNoteItem
from app.models.sales import (
    Quotation,
    QuotationItem,
    SalesOrder,
    SalesOrderItem,
    SalesInvoice,
    SalesInvoiceItem,
    SalesReturn,
    SalesReturnItem,
)
from app.schemas.sales import (
    QuotationCreateRequest,
    QuotationStatusRequest,
    SalesOrderCreateRequest,
    SalesOrderStatusRequest,
    SalesInvoiceCreateRequest,
    SalesReturnCreateRequest,
    QuotationResponse,
    QuotationsListResponse,
    SalesOrderResponse,
    SalesOrdersListResponse,
    SalesInvoiceResponse,
    SalesInvoicesListResponse,
)
from app.services.order_number_service import (
    generate_quotation_number,
    generate_so_number,
    generate_invoice_number,
    generate_sales_return_number,
)
from app.services.gst_service import determine_tax_mode, determine_default_invoice_type, invoice_type_tax_mode, is_india_country, calc_line_item, split_tax
from app.utils.rounding import round_paise_to_nearest_5
from app.services.auth_service import normalize_role, PRIVILEGED_ROLES
from app.services.stock_service import get_current_stock, get_product_batch_snapshot, add_stock_entry, refresh_materialized_view
from app.config import settings
from app.utils.input_validation import validate_optional_token

router = APIRouter(tags=["sales"])
GSTIN_REGEX = re.compile(r"^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")


def _scope_to_owner(query, model, current_user: User):
    """Scope by company_id first, then by ownership for non-privileged users."""
    if current_user.company_id is not None:
        query = scope_query_to_company(query, model, current_user.company_id)
    if normalize_role(current_user.role) in PRIVILEGED_ROLES:
        return query
    owner_col = getattr(model, "created_by", None)
    if owner_col is None:
        return query
    return query.filter(or_(owner_col == current_user.id, owner_col.is_(None)))


def _enforce_owner(record, current_user: User) -> None:
    enforce_resource_ownership(getattr(record, "created_by", None), current_user)


def _compute_invoice_status(amount_paid: int, total_amount: int) -> str:
    if amount_paid <= 0:
        return "issued"
    if amount_paid >= total_amount:
        return "paid"
    return "partial_paid"


def _derive_invoice_status(raw_status: str | None, amount_paid: int, total_amount: int) -> str:
    token = (raw_status or "").strip().lower()
    if token in {"draft", "cancelled", "returned"}:
        return token
    return _compute_invoice_status(int(amount_paid or 0), int(total_amount or 0))


def _auto_expire_quotation(q: Quotation) -> None:
    """BUG-14: Auto-expire quotation if valid_until has passed."""
    if q.status in {"draft", "sent"} and q.valid_until and q.valid_until < date.today():
        q.status = "expired"


def _calculate_invoice_due_date(invoice_date: date, customer: Customer) -> date:
    """Auto-calculate due date with true calendar arithmetic (month-end/leap-year safe)."""
    payment_terms_days = customer.payment_terms_days if customer.payment_terms_days is not None else 0
    if payment_terms_days < 0:
        payment_terms_days = 0
    return invoice_date + timedelta(days=payment_terms_days)


def _enforce_bill_to_gstin_for_gst_invoice(
    db: Session,
    payload: SalesInvoiceCreateRequest,
    current_user: User,
    *,
    primary_customer: Customer,
    gst_applicable: bool,
) -> None:
    if not gst_applicable:
        return

    bill_to_customer_id = payload.bill_to_customer_id or payload.customer_id
    bill_to_customer = primary_customer if bill_to_customer_id == primary_customer.id else None
    if bill_to_customer is None:
        bill_to_customer = (
            db.query(Customer)
            .filter(Customer.id == bill_to_customer_id, Customer.is_deleted == False)
            .first()
        )
    if not bill_to_customer:
        raise HTTPException(status_code=400, detail="Invalid bill-to customer")

    _enforce_owner(bill_to_customer, current_user)

    # GSTIN is mandatory only for India customers.
    if not is_india_country(_customer_country_for_invoice(bill_to_customer)):
        return

    gstin_status = (bill_to_customer.gstin_status or "").strip().lower()
    gstin = ((bill_to_customer.gstin or "") or "").strip().upper()
    if gstin:
        if not GSTIN_REGEX.match(gstin):
            raise HTTPException(
                status_code=400,
                detail=f"Billing GSTIN is invalid: {gstin}",
            )
        return

    if gstin_status == "registered":
        raise HTTPException(
            status_code=400,
            detail="Billing GSTIN is required for GST-reportable invoices",
        )

    state = (bill_to_customer.shipping_state or bill_to_customer.billing_state or "").strip()
    state_code = (bill_to_customer.shipping_state_code or bill_to_customer.billing_state_code or "").strip()
    errors: list[str] = []
    if not state:
        errors.append("State is required for Non-Registered GST customers")
    if not state_code:
        errors.append("State Code is required for GST calculation")
    if errors:
        raise HTTPException(status_code=400, detail=errors)


def _sales_order_module_removed() -> None:
    raise HTTPException(
        status_code=410,
        detail="Sales Order module has been removed from this build.",
    )


def _customer_country_for_invoice(customer: Customer) -> str | None:
    shipping_country = (customer.shipping_country or "").strip()
    if shipping_country:
        return shipping_country
    billing_country = (customer.billing_country or "").strip()
    if billing_country:
        return billing_country
    if (customer.business_type or "").strip().lower() == "domestic":
        return "India"
    return None


def _validate_invoice_type_for_country(invoice_type: str, customer: Customer) -> None:
    """Validate invoice type against customer country rules."""
    customer_in_india = is_india_country(_customer_country_for_invoice(customer))
    if customer_in_india and invoice_type == "export_invoice":
        raise HTTPException(
            status_code=400,
            detail="Export Invoice is allowed only for non-India customers.",
        )
    if (not customer_in_india) and invoice_type != "export_invoice":
        raise HTTPException(
            status_code=400,
            detail="For non-India customers, only Export Invoice is allowed.",
        )


def _validate_invoice_type_for_location(db: Session, invoice_type: str, customer: Customer) -> None:
    """Enforce exact invoice type based on customer shipping-first GST location logic."""
    expected_invoice_type = determine_default_invoice_type(db, customer.id)
    if invoice_type != expected_invoice_type:
        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid invoice type for selected customer location. "
                f"Expected '{expected_invoice_type}'."
            ),
        )


def _has_text(value: Any) -> bool:
    return bool(str(value).strip()) if value is not None else False


def _validate_invoice_master_fields(payload: SalesInvoiceCreateRequest) -> tuple[str, str, str]:
    """Enhancement 3 (FR-19): Stockist Name, Stockist City and Sales Manager Name
    are mandatory on every invoice save. Returns the trimmed values."""
    stockist_name = (payload.stockist_name or "").strip()
    stockist_city = (payload.stockist_city or "").strip()
    sales_manager_name = (payload.sales_manager_name or "").strip()
    errors: list[str] = []
    if not stockist_name:
        errors.append("Stockist Name is required")
    if not stockist_city:
        errors.append("Stockist City is required")
    if not sales_manager_name:
        errors.append("Sales Manager Name is required")
    if errors:
        raise HTTPException(status_code=400, detail=errors)
    return stockist_name, stockist_city, sales_manager_name


def _validate_shipping_address_for_invoice(customer: Customer) -> None:
    """SAL-043: Ensure shipping address is complete before invoice save."""
    required_missing = (
        not _has_text(customer.shipping_address_line1)
        or not _has_text(customer.shipping_city)
        or not _has_text(customer.shipping_state)
        or not _has_text(customer.shipping_country)
    )
    if required_missing:
        raise HTTPException(
            status_code=400,
            detail="Please complete Shipping Address before creating invoice",
        )

    if is_india_country(customer.shipping_country) and not _has_text(customer.shipping_pincode):
        raise HTTPException(
            status_code=400,
            detail="Please complete Shipping Address before creating invoice",
        )


def _build_product_batch_snapshot(db: Session, product_id: UUID) -> dict[str, dict[str, Any]]:
    """Build positive available batch map for a product from transactional data."""
    batch_balances: dict[str, float] = {}
    batch_meta: dict[str, tuple[date | None, date | None]] = {}

    def _accumulate(batch_no, manufacture_date, expiry_date, qty_delta):
        token = (batch_no or "").strip()
        if not token:
            return
        if token not in batch_meta:
            batch_meta[token] = (manufacture_date, expiry_date)
        else:
            prev_mfg, prev_exp = batch_meta[token]
            batch_meta[token] = (
                prev_mfg or manufacture_date,
                prev_exp or expiry_date,
            )
        batch_balances[token] = batch_balances.get(token, 0.0) + float(qty_delta or 0)

    grn_rows = (
        db.query(
            GRNItem.batch_no,
            GRNItem.manufacture_date,
            GRNItem.expiry_date,
            func.coalesce(func.sum(GRNItem.quantity), 0).label("qty"),
            func.coalesce(func.sum(GRNItem.free_quantity), 0).label("free_qty"),
        )
        .join(GoodsReceiptNote, GRNItem.grn_id == GoodsReceiptNote.id)
        .filter(
            GRNItem.product_id == product_id,
            GoodsReceiptNote.status == "confirmed",
            GoodsReceiptNote.is_deleted == False,
            GRNItem.is_deleted == False,
        )
        .group_by(GRNItem.batch_no, GRNItem.manufacture_date, GRNItem.expiry_date)
        .all()
    )
    for row in grn_rows:
        _accumulate(
            row.batch_no,
            row.manufacture_date,
            row.expiry_date,
            float(row.qty or 0) + float(row.free_qty or 0),
        )

    purchase_return_rows = (
        db.query(
            GRNItem.batch_no,
            GRNItem.manufacture_date,
            GRNItem.expiry_date,
            func.coalesce(func.sum(PurchaseReturnItem.quantity), 0).label("qty"),
        )
        .join(PurchaseReturn, PurchaseReturnItem.purchase_return_id == PurchaseReturn.id)
        .outerjoin(GRNItem, PurchaseReturnItem.grn_item_id == GRNItem.id)
        .filter(
            PurchaseReturnItem.product_id == product_id,
            PurchaseReturn.status == "confirmed",
            PurchaseReturn.is_deleted == False,
            PurchaseReturnItem.is_deleted == False,
        )
        .group_by(GRNItem.batch_no, GRNItem.manufacture_date, GRNItem.expiry_date)
        .all()
    )
    for row in purchase_return_rows:
        _accumulate(
            row.batch_no,
            row.manufacture_date,
            row.expiry_date,
            -float(row.qty or 0),
        )

    sales_issue_rows = (
        db.query(
            SalesInvoiceItem.batch_no,
            SalesInvoiceItem.manufacture_date,
            SalesInvoiceItem.expiry_date,
            # MCN-BUG-02: deduct billed + free quantity (matches the stock ledger).
            func.coalesce(func.sum(SalesInvoiceItem.quantity + func.coalesce(SalesInvoiceItem.free_quantity, 0)), 0).label("qty"),
        )
        .join(SalesInvoice, SalesInvoiceItem.invoice_id == SalesInvoice.id)
        .filter(
            SalesInvoiceItem.product_id == product_id,
            func.lower(func.trim(SalesInvoice.status)).in_(["issued", "partial_paid", "paid", "returned"]),
            SalesInvoice.is_deleted == False,
            SalesInvoiceItem.is_deleted == False,
        )
        .group_by(
            SalesInvoiceItem.batch_no,
            SalesInvoiceItem.manufacture_date,
            SalesInvoiceItem.expiry_date,
        )
        .all()
    )
    for row in sales_issue_rows:
        _accumulate(
            row.batch_no,
            row.manufacture_date,
            row.expiry_date,
            -float(row.qty or 0),
        )

    sales_return_rows = (
        db.query(
            SalesInvoiceItem.batch_no,
            SalesInvoiceItem.manufacture_date,
            SalesInvoiceItem.expiry_date,
            func.coalesce(func.sum(SalesReturnItem.quantity), 0).label("qty"),
        )
        .join(SalesReturn, SalesReturnItem.sales_return_id == SalesReturn.id)
        .outerjoin(SalesInvoiceItem, SalesReturnItem.invoice_item_id == SalesInvoiceItem.id)
        .filter(
            SalesReturnItem.product_id == product_id,
            SalesReturn.status == "confirmed",
            SalesReturn.is_deleted == False,
            SalesReturnItem.is_deleted == False,
        )
        .group_by(
            SalesInvoiceItem.batch_no,
            SalesInvoiceItem.manufacture_date,
            SalesInvoiceItem.expiry_date,
        )
        .all()
    )
    for row in sales_return_rows:
        _accumulate(
            row.batch_no,
            row.manufacture_date,
            row.expiry_date,
            float(row.qty or 0),
        )

    rdn_rows = (
        db.query(
            ReturnDeliveryNoteItem.batch_no,
            ReturnDeliveryNoteItem.manufacture_date,
            ReturnDeliveryNoteItem.expiry_date,
            func.coalesce(func.sum(ReturnDeliveryNoteItem.return_quantity), 0).label("qty"),
        )
        .join(ReturnDeliveryNote, ReturnDeliveryNoteItem.rdn_id == ReturnDeliveryNote.id)
        .filter(
            ReturnDeliveryNoteItem.product_id == product_id,
            ReturnDeliveryNote.status == "confirmed",
            ReturnDeliveryNote.is_deleted == False,
            ReturnDeliveryNoteItem.is_deleted == False,
        )
        .group_by(
            ReturnDeliveryNoteItem.batch_no,
            ReturnDeliveryNoteItem.manufacture_date,
            ReturnDeliveryNoteItem.expiry_date,
        )
        .all()
    )
    for row in rdn_rows:
        _accumulate(
            row.batch_no,
            row.manufacture_date,
            row.expiry_date,
            float(row.qty or 0),
        )

    inventory_count_diff_rows = (
        db.query(
            InventoryCountItem.batch_no,
            InventoryCountItem.manufacture_date,
            InventoryCountItem.expiry_date,
            func.coalesce(func.sum(InventoryCountDifferenceAudit.difference_qty), 0).label("qty"),
        )
        .join(
            InventoryCountDifferenceAudit,
            InventoryCountDifferenceAudit.inventory_count_item_id == InventoryCountItem.id,
        )
        .filter(InventoryCountItem.product_id == product_id)
        .group_by(
            InventoryCountItem.batch_no,
            InventoryCountItem.manufacture_date,
            InventoryCountItem.expiry_date,
        )
        .all()
    )
    for row in inventory_count_diff_rows:
        _accumulate(
            row.batch_no,
            row.manufacture_date,
            row.expiry_date,
            float(row.qty or 0),
        )

    snapshot: dict[str, dict[str, Any]] = {}
    for batch_no, qty in batch_balances.items():
        if qty <= 1e-6:
            continue
        manufacture_date, expiry_date = batch_meta.get(batch_no, (None, None))
        snapshot[batch_no] = {
            "available_qty": round(float(qty), 4),
            "manufacture_date": manufacture_date,
            "expiry_date": expiry_date,
        }
    return snapshot


def _collect_batch_and_date_errors(
    batch_no: str | None,
    manufacture_date: date | None,
    expiry_date: date | None,
    batch_snapshot: dict[str, dict[str, Any]],
    today: date,
) -> list[str]:
    """SAL-044: Validate selected batch and enforce MFG/EXP rules."""
    if not batch_snapshot:
        return []

    errors: list[str] = []
    token = (batch_no or "").strip()
    if not token or token not in batch_snapshot:
        return ["Invalid batch selected"]

    expected = batch_snapshot[token]
    expected_mfg = expected.get("manufacture_date")
    expected_exp = expected.get("expiry_date")

    if manufacture_date != expected_mfg or expiry_date != expected_exp:
        errors.append("MFG/EXP date mismatch with batch")

    if expected_mfg and expected_mfg >= today:
        errors.append("Invalid date range")
    if expected_exp and expected_exp <= today:
        errors.append("Invalid date range")
    if expected_mfg and expected_exp and expected_exp <= expected_mfg:
        errors.append("Invalid date range")

    return errors


def _validate_invoice_line_items_for_save(
    db: Session,
    items,
    current_user: User,
    allow_deleted_products: bool = False,
) -> dict[str, Product]:
    """Validate invoice items and return product cache for reuse in save flow."""
    product_cache: dict[str, Product] = {}
    batch_cache: dict[str, dict[str, dict[str, Any]]] = {}
    batch_requested: dict[str, float] = {}
    today = date.today()
    validation_errors: list[str] = []

    for index, item in enumerate(items):
        product_key = str(item.product_id)
        if product_key not in product_cache:
            product_query = db.query(Product).filter(Product.id == item.product_id)
            if not allow_deleted_products:
                product_query = product_query.filter(Product.is_deleted == False)
            product = product_query.first()
            if not product:
                raise HTTPException(status_code=400, detail="Invalid product")
            _enforce_owner(product, current_user)
            product_cache[product_key] = product
            batch_cache[product_key] = _build_product_batch_snapshot(db, item.product_id)

        for err in _collect_batch_and_date_errors(
            getattr(item, "batch_no", None),
            getattr(item, "manufacture_date", None),
            getattr(item, "expiry_date", None),
            batch_cache[product_key],
            today,
        ):
            if err not in validation_errors:
                validation_errors.append(err)

        batch_token = (getattr(item, "batch_no", None) or "").strip()
        if not batch_token:
            msg = f"Line item {index + 1}: Batch is required. Please select a batch."
            if msg not in validation_errors:
                validation_errors.append(msg)
        if batch_token and batch_token in batch_cache[product_key]:
            available_qty = float(batch_cache[product_key][batch_token].get("available_qty", 0.0))
            requested_qty = float(getattr(item, "quantity", 0) or 0) + float(getattr(item, "free_quantity", 0) or 0)
            cache_key = f"{product_key}::{batch_token}"
            next_requested = batch_requested.get(cache_key, 0.0) + requested_qty
            batch_requested[cache_key] = next_requested
            if next_requested - available_qty > 1e-6:
                validation_errors.append(
                    f"Line item {index + 1}: Entered quantity exceeds available stock in selected batch"
                )

    if validation_errors:
        raise HTTPException(status_code=400, detail=validation_errors)

    return product_cache


def _mail_config_looks_configured() -> bool:
    placeholders = {
        "your@gmail.com",
        "your-gmail-app-password",
        "noreply@yourcompany.com",
        "smtp.gmail.com",
    }
    username = (settings.mail_username or "").strip()
    password = (settings.mail_password or "").strip()
    sender = (settings.mail_from or "").strip()
    server = (settings.mail_server or "").strip()
    return bool(username and password and sender and server) and username not in placeholders and password not in placeholders


def _write_email_outbox_copy(
    *,
    recipient: str,
    subject: str,
    body: str,
    pdf_filename: str,
    pdf_bytes: bytes,
) -> str:
    outbox_dir = Path(__file__).resolve().parents[2] / "static" / "mail_outbox"
    outbox_dir.mkdir(parents=True, exist_ok=True)

    token = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
    base_name = f"{token}_{pdf_filename.replace(' ', '_')}"
    pdf_path = outbox_dir / base_name
    meta_path = outbox_dir / f"{token}.txt"

    pdf_path.write_bytes(pdf_bytes)
    meta_path.write_text(
        "\n".join(
            [
                f"to={recipient}",
                f"subject={subject}",
                "body=",
                body,
                "",
                f"attachment={pdf_path.name}",
            ]
        ),
        encoding="utf-8",
    )

    return str(pdf_path.relative_to(Path(__file__).resolve().parents[2]).as_posix())


def _send_pdf_email(
    *,
    recipient: str,
    subject: str,
    body: str,
    pdf_filename: str,
    pdf_bytes: bytes,
) -> dict[str, str]:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = (settings.mail_from or "").strip()
    msg["To"] = recipient
    msg.set_content(body)
    msg.add_attachment(pdf_bytes, maintype="application", subtype="pdf", filename=pdf_filename)

    if _mail_config_looks_configured():
        try:
            if settings.mail_ssl_tls:
                with smtplib.SMTP_SSL(settings.mail_server, settings.mail_port, timeout=20) as smtp:
                    smtp.login(settings.mail_username, settings.mail_password)
                    smtp.send_message(msg)
            else:
                with smtplib.SMTP(settings.mail_server, settings.mail_port, timeout=20) as smtp:
                    smtp.ehlo()
                    if settings.mail_starttls:
                        smtp.starttls(context=ssl.create_default_context())
                        smtp.ehlo()
                    smtp.login(settings.mail_username, settings.mail_password)
                    smtp.send_message(msg)

            return {
                "delivery": "smtp",
                "message": "Email sent successfully",
            }
        except Exception:
            outbox_file = _write_email_outbox_copy(
                recipient=recipient,
                subject=subject,
                body=body,
                pdf_filename=pdf_filename,
                pdf_bytes=pdf_bytes,
            )
            return {
                "delivery": "outbox",
                "message": "SMTP send failed; saved email copy to local outbox",
                "outbox_file": outbox_file,
            }

    outbox_file = _write_email_outbox_copy(
        recipient=recipient,
        subject=subject,
        body=body,
        pdf_filename=pdf_filename,
        pdf_bytes=pdf_bytes,
    )
    return {
        "delivery": "outbox",
        "message": "SMTP not configured; saved email copy to local outbox",
        "outbox_file": outbox_file,
    }


# ────────────────────────────── Quotations ───────────────────────────────────

@router.get("/api/v1/quotations", response_model=QuotationsListResponse)
async def list_quotations(
    status: str | None = Query(default=None),
    archived_only: bool = Query(default=False),
    include_archived: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("quotations_read")),
):
    status = validate_optional_token(
        status,
        field_name="status",
        allowed={"draft", "sent", "accepted", "rejected", "expired", "converted", "cancelled"},
    )

    query = db.query(Quotation)
    query = _scope_to_owner(query, Quotation, current_user)
    if archived_only:
        query = query.filter(Quotation.is_deleted == True)
    elif not include_archived:
        query = query.filter(Quotation.is_deleted == False)
    if status:
        query = query.filter(Quotation.status == status)
    total = query.count()
    rows = query.order_by(Quotation.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    # BUG-14: Auto-expire on read
    changed = False
    for q in rows:
        if q.status in {"draft", "sent"} and q.valid_until and q.valid_until < date.today():
            q.status = "expired"
            changed = True
    if changed:
        db.commit()

    return QuotationsListResponse(
        items=[QuotationResponse.model_validate(q) for q in rows],
        total=total,
        page=page,
        page_size=page_size,
        has_more=(page * page_size) < total
    )


@router.post("/api/v1/quotations", response_model=QuotationResponse)
async def create_quotation(
    payload: QuotationCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("quotations_write")),
):
    customer = db.query(Customer).filter(Customer.id == payload.customer_id, Customer.is_deleted == False).first()
    if not customer:
        raise HTTPException(status_code=400, detail="Invalid customer")
    _enforce_owner(customer, current_user)

    # SAL-006: Valid Until must be a future date
    if payload.valid_until and payload.valid_until <= date.today():
        raise HTTPException(status_code=400, detail="Valid Until date must be a future date")

    # BUG-02: Auto-detect GST mode
    tax_mode = determine_tax_mode(db, "customer", payload.customer_id)
    is_igst = tax_mode["is_igst"]
    gst_applicable = tax_mode["gst_applicable"]

    q = Quotation(
        quotation_number=generate_quotation_number(db, current_user.company_id),
        customer_id=payload.customer_id,
        quotation_date=payload.quotation_date,
        valid_until=payload.valid_until,
        sold_to_customer_id=payload.sold_to_customer_id or payload.customer_id,
        bill_to_customer_id=payload.bill_to_customer_id or payload.customer_id,
        ship_to_customer_id=payload.ship_to_customer_id or payload.customer_id,
        notes=payload.notes,
        terms_conditions=payload.terms_conditions,
        status="draft",  # BUG-13: Always force draft
        company_id=current_user.company_id,
        created_by=current_user.id,
    )
    db.add(q)
    db.flush()

    subtotal = total_discount = total_taxable = total_cgst = total_sgst = total_igst = 0
    for item in payload.items:
        product = db.query(Product).filter(Product.id == item.product_id, Product.is_deleted == False).first()
        if not product:
            raise HTTPException(status_code=400, detail=f"Invalid product: {item.product_id}")
        _enforce_owner(product, current_user)
        calc = calc_line_item(
            item.quantity,
            item.unit_price,
            item.discount_percent,
            item.gst_rate,
            is_igst,
            gst_applicable,
        )
        db.add(QuotationItem(
            quotation_id=q.id,
            product_id=item.product_id,
            description=item.description,
            quantity=item.quantity,
            unit_price=item.unit_price,
            discount_percent=item.discount_percent,
            discount_amount=calc["discount"],
            taxable_amount=calc["taxable"],
            gst_rate=calc["gst_rate"],
            cgst_amount=calc["cgst"],
            sgst_amount=calc["sgst"],
            igst_amount=calc["igst"],
            total_amount=calc["total"],
        ))
        subtotal += calc["gross"]
        total_discount += calc["discount"]
        total_taxable += calc["taxable"]
        total_cgst += calc["cgst"]
        total_sgst += calc["sgst"]
        total_igst += calc["igst"]

    q.subtotal = subtotal
    q.total_discount = total_discount
    q.total_taxable_amount = total_taxable
    q.total_cgst = total_cgst
    q.total_sgst = total_sgst
    q.total_igst = total_igst
    q.total_gst = total_cgst + total_sgst + total_igst
    q.total_amount = total_taxable + q.total_gst
    db.commit()
    db.refresh(q)
    return q


@router.get("/api/v1/quotations/{quotation_id}", response_model=dict)
async def get_quotation(
    quotation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("quotations_read")),
):
    q = db.query(Quotation).filter(Quotation.id == quotation_id, Quotation.is_deleted == False).first()
    if not q:
        raise HTTPException(status_code=404, detail="Quotation not found")
    _enforce_owner(q, current_user)
    # BUG-14: Auto-expire on read
    _auto_expire_quotation(q)
    db.commit()
    items = db.query(QuotationItem).filter(QuotationItem.quotation_id == quotation_id).all()
    return {
        "quotation": QuotationResponse.model_validate(q).model_dump(mode="json"),
        "items": [jsonable_encoder(item) for item in items],
    }


@router.put("/api/v1/quotations/{quotation_id}", response_model=QuotationResponse)
async def update_quotation(
    quotation_id: UUID,
    payload: QuotationCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("quotations_write")),
):
    q = db.query(Quotation).filter(Quotation.id == quotation_id, Quotation.is_deleted == False).first()
    if not q:
        raise HTTPException(status_code=404, detail="Quotation not found")
    _enforce_owner(q, current_user)
    if q.status not in {"draft", "sent"}:
        raise HTTPException(status_code=400, detail="Quotation cannot be edited in current status")

    # SAL-006: Valid Until must be a future date
    if payload.valid_until and payload.valid_until <= date.today():
        raise HTTPException(status_code=400, detail="Valid Until date must be a future date")

    # BUG-02: Auto-detect GST mode
    customer = db.query(Customer).filter(Customer.id == payload.customer_id, Customer.is_deleted == False).first()
    if not customer:
        raise HTTPException(status_code=400, detail="Invalid customer")
    _enforce_owner(customer, current_user)

    tax_mode = determine_tax_mode(db, "customer", payload.customer_id)
    is_igst = tax_mode["is_igst"]
    gst_applicable = tax_mode["gst_applicable"]

    q.customer_id = payload.customer_id
    q.quotation_date = payload.quotation_date
    q.valid_until = payload.valid_until
    q.sold_to_customer_id = payload.sold_to_customer_id or payload.customer_id
    q.bill_to_customer_id = payload.bill_to_customer_id or payload.customer_id
    q.ship_to_customer_id = payload.ship_to_customer_id or payload.customer_id
    q.notes = payload.notes
    q.terms_conditions = payload.terms_conditions

    db.query(QuotationItem).filter(QuotationItem.quotation_id == quotation_id).delete()
    db.flush()

    subtotal = total_discount = total_taxable = total_cgst = total_sgst = total_igst = 0
    for item in payload.items:
        product = db.query(Product).filter(Product.id == item.product_id, Product.is_deleted == False).first()
        if not product:
            raise HTTPException(status_code=400, detail=f"Invalid product: {item.product_id}")
        _enforce_owner(product, current_user)
        calc = calc_line_item(
            item.quantity,
            item.unit_price,
            item.discount_percent,
            item.gst_rate,
            is_igst,
            gst_applicable,
        )
        db.add(QuotationItem(
            quotation_id=q.id,
            product_id=item.product_id,
            description=item.description,
            quantity=item.quantity,
            unit_price=item.unit_price,
            discount_percent=item.discount_percent,
            discount_amount=calc["discount"],
            taxable_amount=calc["taxable"],
            gst_rate=calc["gst_rate"],
            cgst_amount=calc["cgst"],
            sgst_amount=calc["sgst"],
            igst_amount=calc["igst"],
            total_amount=calc["total"],
        ))
        subtotal += calc["gross"]
        total_discount += calc["discount"]
        total_taxable += calc["taxable"]
        total_cgst += calc["cgst"]
        total_sgst += calc["sgst"]
        total_igst += calc["igst"]

    q.subtotal = subtotal
    q.total_discount = total_discount
    q.total_taxable_amount = total_taxable
    q.total_cgst = total_cgst
    q.total_sgst = total_sgst
    q.total_igst = total_igst
    q.total_gst = total_cgst + total_sgst + total_igst
    q.total_amount = total_taxable + q.total_gst
    db.commit()
    db.refresh(q)
    return q


@router.patch("/api/v1/quotations/{quotation_id}/status", response_model=QuotationResponse)
async def quotation_status(
    quotation_id: UUID,
    payload: QuotationStatusRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    q = db.query(Quotation).filter(Quotation.id == quotation_id, Quotation.is_deleted == False).first()
    if not q:
        raise HTTPException(status_code=404, detail="Quotation not found")
    _enforce_owner(q, current_user)

    allowed = {
        "draft": {"sent", "expired"},
        "sent": {"accepted", "rejected", "expired"},
        "accepted": {"converted"},
    }
    if payload.status not in allowed.get(q.status, set()):
        raise HTTPException(status_code=400, detail="Invalid status transition")

    q.status = payload.status
    db.commit()
    db.refresh(q)
    return q


@router.patch("/api/v1/quotations/{quotation_id}/archive", response_model=QuotationResponse)
async def archive_quotation(
    quotation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("quotations_write")),
):
    q = db.query(Quotation).filter(Quotation.id == quotation_id, Quotation.is_deleted == False).first()
    if not q:
        raise HTTPException(status_code=404, detail="Quotation not found")
    _enforce_owner(q, current_user)

    q.is_deleted = True
    q.deleted_at = datetime.utcnow()
    db.commit()
    db.refresh(q)
    return q


@router.patch("/api/v1/quotations/{quotation_id}/restore", response_model=QuotationResponse)
async def restore_quotation(
    quotation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("quotations_write")),
):
    q = db.query(Quotation).filter(Quotation.id == quotation_id, Quotation.is_deleted == True).first()
    if not q:
        raise HTTPException(status_code=404, detail="Archived quotation not found")
    _enforce_owner(q, current_user)

    q.is_deleted = False
    q.deleted_at = None
    db.commit()
    db.refresh(q)
    return q


@router.post("/api/v1/quotations/{quotation_id}/convert-to-so")
async def convert_quotation_to_so(
    quotation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("sales_orders_write")),
):
    _sales_order_module_removed()
    q = db.query(Quotation).filter(Quotation.id == quotation_id, Quotation.is_deleted == False).first()
    if not q:
        raise HTTPException(status_code=404, detail="Quotation not found")
    _enforce_owner(q, current_user)
    if q.status not in {"sent", "accepted"}:
        raise HTTPException(status_code=400, detail="Quotation cannot be converted in current status")

    so = SalesOrder(
        so_number=generate_so_number(db, current_user.company_id),
        quotation_id=q.id,
        customer_id=q.customer_id,
        order_date=date.today(),
        expected_delivery_date=None,
        status="draft",
        sold_to_customer_id=q.sold_to_customer_id,
        bill_to_customer_id=q.bill_to_customer_id,
        ship_to_customer_id=q.ship_to_customer_id,
        subtotal=q.subtotal,
        total_discount=q.total_discount,
        total_taxable_amount=q.total_taxable_amount,
        total_cgst=q.total_cgst,
        total_sgst=q.total_sgst,
        total_igst=q.total_igst,
        total_gst=q.total_gst,
        total_amount=q.total_amount,
        notes=q.notes,
        terms_conditions=q.terms_conditions,
        company_id=current_user.company_id,
        created_by=current_user.id,
    )
    db.add(so)
    db.flush()

    q_items = db.query(QuotationItem).filter(QuotationItem.quotation_id == q.id).all()
    for item in q_items:
        db.add(SalesOrderItem(
            sales_order_id=so.id,
            product_id=item.product_id,
            description=item.description,
            quantity=item.quantity,
            unit_price=item.unit_price,
            discount_percent=item.discount_percent,
            discount_amount=item.discount_amount,
            taxable_amount=item.taxable_amount,
            gst_rate=item.gst_rate,
            cgst_amount=item.cgst_amount,
            sgst_amount=item.sgst_amount,
            igst_amount=item.igst_amount,
            total_amount=item.total_amount,
            fulfilled_quantity=0,
        ))

    q.status = "converted"
    db.commit()
    db.refresh(so)
    return so


# ────────────────────────────── Sales Orders ─────────────────────────────────

@router.get("/api/v1/sales-orders", response_model=SalesOrdersListResponse)
async def list_sales_orders(
    status: str | None = Query(default=None),
    archived_only: bool = Query(default=False),
    include_archived: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("sales_orders_read")),
):
    _sales_order_module_removed()
    status = validate_optional_token(
        status,
        field_name="status",
        allowed={"draft", "confirmed", "partial", "fulfilled", "cancelled"},
    )

    query = db.query(SalesOrder)
    if archived_only:
        query = query.filter(SalesOrder.is_deleted == True)
    elif not include_archived:
        query = query.filter(SalesOrder.is_deleted == False)
    if status:
        query = query.filter(SalesOrder.status == status)
    total = query.count()
    rows = query.order_by(SalesOrder.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return SalesOrdersListResponse(
        items=[SalesOrderResponse.model_validate(so) for so in rows],
        total=total,
        page=page,
        page_size=page_size,
        has_more=(page * page_size) < total
    )


@router.post("/api/v1/sales-orders", response_model=SalesOrderResponse)
async def create_sales_order(
    payload: SalesOrderCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("sales_orders_write")),
):
    _sales_order_module_removed()
    customer = db.query(Customer).filter(Customer.id == payload.customer_id, Customer.is_deleted == False).first()
    if not customer:
        raise HTTPException(status_code=400, detail="Invalid customer")

    # BUG-02: Auto-detect GST mode
    tax_mode = determine_tax_mode(db, "customer", payload.customer_id)
    is_igst = tax_mode["is_igst"]
    gst_applicable = tax_mode["gst_applicable"]

    so = SalesOrder(
        so_number=generate_so_number(db, current_user.company_id),
        quotation_id=payload.quotation_id,
        customer_id=payload.customer_id,
        order_date=payload.order_date,
        expected_delivery_date=payload.expected_delivery_date,
        status="draft",  # BUG-13: Always force draft
        currency_code=payload.currency_code,
        exchange_rate=payload.exchange_rate,
        sold_to_customer_id=payload.sold_to_customer_id or payload.customer_id,
        bill_to_customer_id=payload.bill_to_customer_id or payload.customer_id,
        ship_to_customer_id=payload.ship_to_customer_id or payload.customer_id,
        notes=payload.notes,
        terms_conditions=payload.terms_conditions,
        company_id=current_user.company_id,
        created_by=current_user.id,
    )
    db.add(so)
    db.flush()

    subtotal = total_discount = total_taxable = total_cgst = total_sgst = total_igst = 0
    for item in payload.items:
        calc = calc_line_item(
            item.quantity,
            item.unit_price,
            item.discount_percent,
            item.gst_rate,
            is_igst,
            gst_applicable,
        )
        db.add(SalesOrderItem(
            sales_order_id=so.id,
            product_id=item.product_id,
            description=item.description,
            quantity=item.quantity,
            unit_price=item.unit_price,
            discount_percent=item.discount_percent,
            discount_amount=calc["discount"],
            taxable_amount=calc["taxable"],
            gst_rate=calc["gst_rate"],
            cgst_amount=calc["cgst"],
            sgst_amount=calc["sgst"],
            igst_amount=calc["igst"],
            total_amount=calc["total"],
        ))
        subtotal += calc["gross"]
        total_discount += calc["discount"]
        total_taxable += calc["taxable"]
        total_cgst += calc["cgst"]
        total_sgst += calc["sgst"]
        total_igst += calc["igst"]

    so.subtotal = subtotal
    so.total_discount = total_discount
    so.total_taxable_amount = total_taxable
    so.total_cgst = total_cgst
    so.total_sgst = total_sgst
    so.total_igst = total_igst
    so.total_gst = total_cgst + total_sgst + total_igst
    so.total_amount = total_taxable + so.total_gst

    db.commit()
    db.refresh(so)
    return so


@router.get("/api/v1/sales-orders/{so_id}")
async def get_sales_order(
    so_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("sales_orders_read")),
):
    _sales_order_module_removed()
    so = db.query(SalesOrder).filter(SalesOrder.id == so_id, SalesOrder.is_deleted == False).first()
    if not so:
        raise HTTPException(status_code=404, detail="Sales order not found")
    items = db.query(SalesOrderItem).filter(SalesOrderItem.sales_order_id == so_id).all()
    return {"sales_order": so, "items": items}

@router.get("/api/v1/sales-orders/search/{so_number}")
async def get_sales_order_by_number(
    so_number: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("sales_orders_read")),
):
    _sales_order_module_removed()
    so = db.query(SalesOrder).filter(SalesOrder.so_number == so_number, SalesOrder.is_deleted == False).first()
    if not so:
        raise HTTPException(status_code=404, detail="Sales order not found")
    items = db.query(SalesOrderItem).filter(SalesOrderItem.sales_order_id == so.id).all()
    return {"sales_order": so, "items": items}


@router.put("/api/v1/sales-orders/{so_id}")
async def update_sales_order(
    so_id: UUID,
    payload: SalesOrderCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("sales_orders_write")),
):
    _sales_order_module_removed()
    so = db.query(SalesOrder).filter(SalesOrder.id == so_id, SalesOrder.is_deleted == False).first()
    if not so:
        raise HTTPException(status_code=404, detail="Sales order not found")
    if so.status != "draft":
        raise HTTPException(status_code=400, detail="Only draft sales order can be edited")

    # BUG-02: Auto-detect GST mode
    tax_mode = determine_tax_mode(db, "customer", payload.customer_id)
    is_igst = tax_mode["is_igst"]
    gst_applicable = tax_mode["gst_applicable"]

    so.customer_id = payload.customer_id
    so.quotation_id = payload.quotation_id
    so.order_date = payload.order_date
    so.expected_delivery_date = payload.expected_delivery_date
    so.currency_code = payload.currency_code
    so.exchange_rate = payload.exchange_rate
    so.sold_to_customer_id = payload.sold_to_customer_id or payload.customer_id
    so.bill_to_customer_id = payload.bill_to_customer_id or payload.customer_id
    so.ship_to_customer_id = payload.ship_to_customer_id or payload.customer_id
    so.notes = payload.notes
    so.terms_conditions = payload.terms_conditions

    db.query(SalesOrderItem).filter(SalesOrderItem.sales_order_id == so_id).delete()
    db.flush()

    subtotal = total_discount = total_taxable = total_cgst = total_sgst = total_igst = 0
    for item in payload.items:
        calc = calc_line_item(
            item.quantity,
            item.unit_price,
            item.discount_percent,
            item.gst_rate,
            is_igst,
            gst_applicable,
        )
        db.add(SalesOrderItem(
            sales_order_id=so.id,
            product_id=item.product_id,
            description=item.description,
            quantity=item.quantity,
            unit_price=item.unit_price,
            discount_percent=item.discount_percent,
            discount_amount=calc["discount"],
            taxable_amount=calc["taxable"],
            gst_rate=calc["gst_rate"],
            cgst_amount=calc["cgst"],
            sgst_amount=calc["sgst"],
            igst_amount=calc["igst"],
            total_amount=calc["total"],
        ))
        subtotal += calc["gross"]
        total_discount += calc["discount"]
        total_taxable += calc["taxable"]
        total_cgst += calc["cgst"]
        total_sgst += calc["sgst"]
        total_igst += calc["igst"]

    so.subtotal = subtotal
    so.total_discount = total_discount
    so.total_taxable_amount = total_taxable
    so.total_cgst = total_cgst
    so.total_sgst = total_sgst
    so.total_igst = total_igst
    so.total_gst = total_cgst + total_sgst + total_igst
    so.total_amount = total_taxable + so.total_gst

    db.commit()
    db.refresh(so)
    return so


@router.patch("/api/v1/sales-orders/{so_id}/status", response_model=SalesOrderResponse)
async def sales_order_status(
    so_id: UUID,
    payload: SalesOrderStatusRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("sales_orders_write")),
):
    _sales_order_module_removed()
    so = db.query(SalesOrder).filter(SalesOrder.id == so_id, SalesOrder.is_deleted == False).first()
    if not so:
        raise HTTPException(status_code=404, detail="Sales order not found")

    # Status flow: draft → confirmed → partial/fulfilled → cancelled
    # Database schema CHECK constraint: status IN ('draft','confirmed','partial','fulfilled','cancelled')
    if payload.status == "confirmed":
        items = db.query(SalesOrderItem).filter(SalesOrderItem.sales_order_id == so.id).all()
        shortages = []
        for item in items:
            stock = get_current_stock(db, item.product_id)
            if stock < float(item.quantity):
                shortages.append({
                    "product_id": str(item.product_id),
                    "required": float(item.quantity),
                    "available": stock,
                })
        if shortages:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "Insufficient stock for one or more items",
                    "error_code": "INSUFFICIENT_STOCK",
                    "shortages": shortages,
                },
            )

    allowed = {
        "draft": {"confirmed", "cancelled"},
        "confirmed": {"partial", "fulfilled", "cancelled"},
        "partial": {"fulfilled", "cancelled"},
        "fulfilled": {"cancelled"},
    }
    if payload.status not in allowed.get(so.status, set()):
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid status transition: {so.status} → {payload.status}. Allowed: {allowed.get(so.status, set())}"
        )

    so.status = payload.status
    db.commit()
    db.refresh(so)
    return so


@router.patch("/api/v1/sales-orders/{so_id}/archive", response_model=SalesOrderResponse)
async def archive_sales_order(
    so_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("sales_orders_write")),
):
    _sales_order_module_removed()
    so = db.query(SalesOrder).filter(SalesOrder.id == so_id, SalesOrder.is_deleted == False).first()
    if not so:
        raise HTTPException(status_code=404, detail="Sales order not found")

    so.is_deleted = True
    so.deleted_at = datetime.utcnow()
    db.commit()
    db.refresh(so)
    return so


@router.patch("/api/v1/sales-orders/{so_id}/restore", response_model=SalesOrderResponse)
async def restore_sales_order(
    so_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("sales_orders_write")),
):
    _sales_order_module_removed()
    so = db.query(SalesOrder).filter(SalesOrder.id == so_id, SalesOrder.is_deleted == True).first()
    if not so:
        raise HTTPException(status_code=404, detail="Archived sales order not found")

    so.is_deleted = False
    so.deleted_at = None
    db.commit()
    db.refresh(so)
    return so


# BUG-05: NEW — Convert Sales Order to Invoice
@router.post("/api/v1/sales-orders/{so_id}/convert-to-invoice", response_model=SalesInvoiceResponse)
async def convert_so_to_invoice(
    so_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("sales_invoices_write")),
):
    """Convert a confirmed/fulfilled/partial sales order to a draft invoice."""
    _sales_order_module_removed()
    so = db.query(SalesOrder).filter(SalesOrder.id == so_id, SalesOrder.is_deleted == False).first()
    if not so:
        raise HTTPException(status_code=404, detail="Sales order not found")
    if so.status not in {"fulfilled", "partial"}:
        raise HTTPException(status_code=400, detail="Only partial or fulfilled sales orders can be converted to invoice")

    customer = db.query(Customer).filter(Customer.id == so.customer_id, Customer.is_deleted == False).first()
    if not customer:
        raise HTTPException(status_code=400, detail="Invalid customer")

    invoice_date = date.today()

    invoice_type = determine_default_invoice_type(db, so.customer_id)
    tax_mode = determine_tax_mode(db, "customer", so.customer_id)
    invoice_tax_mode = invoice_type_tax_mode(invoice_type, fallback_is_igst=tax_mode["is_igst"])
    is_igst = invoice_tax_mode["is_igst"]
    gst_applicable = invoice_tax_mode["gst_applicable"]
    if not tax_mode["gst_applicable"]:
        is_igst = False
        gst_applicable = False

    payload_stub = SimpleNamespace(
        customer_id=so.customer_id,
        bill_to_customer_id=so.bill_to_customer_id,
    )
    _enforce_bill_to_gstin_for_gst_invoice(
        db,
        payload_stub,
        current_user,
        primary_customer=customer,
        gst_applicable=gst_applicable,
    )

    invoice = SalesInvoice(
        invoice_number=generate_invoice_number(db, current_user.company_id),
        sales_order_id=so.id,
        quotation_id=so.quotation_id,
        customer_id=so.customer_id,
        invoice_date=invoice_date,
        due_date=_calculate_invoice_due_date(invoice_date, customer),
        status="draft",
        sold_to_customer_id=so.sold_to_customer_id,
        bill_to_customer_id=so.bill_to_customer_id,
        ship_to_customer_id=so.ship_to_customer_id,
        invoice_type=invoice_type,
        is_igst=is_igst,
        amount_paid=0,
        amount_due=0,
        notes=so.notes,
        terms_conditions=so.terms_conditions,
        company_id=current_user.company_id,
        created_by=current_user.id,
    )
    db.add(invoice)
    db.flush()

    so_items = db.query(SalesOrderItem).filter(SalesOrderItem.sales_order_id == so.id).all()
    subtotal = total_discount = total_taxable = total_cgst = total_sgst = total_igst = 0
    for item in so_items:
        product = db.query(Product).filter(Product.id == item.product_id).first()
        calc = calc_line_item(
            item.quantity,
            item.unit_price,
            item.discount_percent,
            item.gst_rate,
            is_igst,
            gst_applicable,
        )
        db.add(SalesInvoiceItem(
            invoice_id=invoice.id,
            product_id=item.product_id,
            description=item.description,
            quantity=item.quantity,
            unit_price=item.unit_price,
            mrp=product.mrp if product else 0,
            discount_percent=item.discount_percent,
            discount_amount=calc["discount"],
            taxable_amount=calc["taxable"],
            gst_rate=calc["gst_rate"],
            cgst_amount=calc["cgst"],
            sgst_amount=calc["sgst"],
            igst_amount=calc["igst"],
            total_amount=calc["total"],
        ))
        subtotal += calc["gross"]
        total_discount += calc["discount"]
        total_taxable += calc["taxable"]
        total_cgst += calc["cgst"]
        total_sgst += calc["sgst"]
        total_igst += calc["igst"]

    invoice.subtotal = subtotal
    invoice.total_discount = total_discount
    invoice.total_taxable_amount = total_taxable
    invoice.total_cgst = total_cgst
    invoice.total_sgst = total_sgst
    invoice.total_igst = total_igst
    invoice.total_gst = total_cgst + total_sgst + total_igst
    exact_total = total_taxable + invoice.total_gst
    invoice.total_amount = _round_invoice_total(exact_total, invoice.currency_code)
    invoice.amount_due = invoice.total_amount

    db.commit()
    db.refresh(invoice)
    return invoice


# ────────────────────────────── Invoices ──────────────────────────────────────

@router.get("/api/v1/invoices", response_model=SalesInvoicesListResponse)
async def list_invoices(
    status: str | None = Query(default=None),
    search: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    stockist: list[str] | None = Query(default=None),
    sales_manager: list[str] | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("sales_invoices_read")),
):
    status = validate_optional_token(
        status,
        field_name="status",
        allowed={"draft", "issued", "partial_paid", "paid", "cancelled", "returned"},
    )

    query = db.query(SalesInvoice).filter(SalesInvoice.is_deleted == False)
    query = _scope_to_owner(query, SalesInvoice, current_user)

    # Enhancement 3 (FR-21/FR-22/FR-23): Stockist & Sales Manager multi-select
    # filters. Both work standalone and combine with each other and the existing
    # date-range / customer / status / search filters.
    stockist_values = [s.strip() for s in (stockist or []) if s and s.strip()]
    if stockist_values:
        query = query.filter(SalesInvoice.stockist_name.in_(stockist_values))
    sales_manager_values = [s.strip() for s in (sales_manager or []) if s and s.strip()]
    if sales_manager_values:
        query = query.filter(SalesInvoice.sales_manager_name.in_(sales_manager_values))
    if status:
        normalized_status = status.strip().lower()
        if normalized_status in {"issued", "partial_paid", "paid"}:
            query = query.filter(SalesInvoice.status.in_(["issued", "partial_paid", "paid"]))
            if normalized_status == "issued":
                query = query.filter(SalesInvoice.amount_paid <= 0)
            elif normalized_status == "partial_paid":
                query = query.filter(SalesInvoice.amount_paid > 0, SalesInvoice.amount_paid < SalesInvoice.total_amount)
            elif normalized_status == "paid":
                query = query.filter(SalesInvoice.total_amount > 0, SalesInvoice.amount_paid >= SalesInvoice.total_amount)
        else:
            query = query.filter(SalesInvoice.status == normalized_status)

    # MCN-BUG-001: server-side date-range filter (keeps pagination counts correct)
    if date_from:
        query = query.filter(SalesInvoice.invoice_date >= date_from)
    if date_to:
        query = query.filter(SalesInvoice.invoice_date <= date_to)

    # MCN-BUG-001: server-side search across invoice number, customer name and status
    search_term = (search or "").strip()
    if search_term:
        like = f"%{search_term}%"
        query = query.outerjoin(Customer, SalesInvoice.customer_id == Customer.id).filter(
            or_(
                SalesInvoice.invoice_number.ilike(like),
                SalesInvoice.status.ilike(like),
                Customer.company_name.ilike(like),
            )
        )

    total = query.count()
    rows = query.order_by(SalesInvoice.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    # Resolve customer name/code for display. Deliberately NOT filtered by
    # is_deleted so historical invoices of soft-deleted customers still render the
    # original customer. Scoped to the tenant for isolation.
    customer_ids = {inv.customer_id for inv in rows if inv.customer_id}
    customer_map: dict = {}
    if customer_ids:
        for cid, cname, ccode in (
            db.query(Customer.id, Customer.company_name, Customer.customer_code)
            .filter(Customer.id.in_(customer_ids), Customer.company_id == current_user.company_id)
            .all()
        ):
            customer_map[cid] = (cname, ccode)

    for inv in rows:
        inv.status = _derive_invoice_status(inv.status, int(inv.amount_paid or 0), int(inv.total_amount or 0))
        resolved = customer_map.get(inv.customer_id)
        inv.customer_name = resolved[0] if resolved else None
        inv.customer_code = resolved[1] if resolved else None

    return SalesInvoicesListResponse(
        items=[SalesInvoiceResponse.model_validate(inv) for inv in rows],
        total=total,
        page=page,
        page_size=page_size,
        has_more=(page * page_size) < total
    )


@router.get("/api/v1/invoices/batch-options")
async def get_invoice_batch_options(
    product_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("sales_invoices_read")),
):
    """Return available batch options for a product with qty and MFG/EXP dates."""
    product = db.query(Product).filter(Product.id == product_id, Product.is_deleted == False).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    _enforce_owner(product, current_user)

    snapshot = _build_product_batch_snapshot(db, product_id)
    batch_items = [
        {
            "batch_no": batch_no,
            "available_qty": meta.get("available_qty", 0),
            "manufacture_date": meta.get("manufacture_date").isoformat() if meta.get("manufacture_date") else None,
            "expiry_date": meta.get("expiry_date").isoformat() if meta.get("expiry_date") else None,
        }
        for batch_no, meta in snapshot.items()
    ]
    batch_items.sort(key=lambda row: (row["expiry_date"] is None, row["expiry_date"] or "", row["batch_no"]))

    return {
        "product_id": str(product_id),
        "items": batch_items,
    }


# The tenant's base/home currency. All GST and base-currency reporting is in INR.
BASE_CURRENCY = "INR"


def _resolve_invoice_currency(customer, payload) -> tuple[str, float]:
    """Determine the invoice's transaction currency + exchange rate to base (INR).

    Currency is authoritative from the Customer Directory (customer.currency_code).
    Base-currency (INR) invoices never carry a rate (forced to 1.0). Foreign-currency
    invoices REQUIRE an exchange rate > 0 (captured per invoice, so historical
    invoices keep their original rate).
    """
    code = (getattr(customer, "currency_code", None) or BASE_CURRENCY).strip().upper() or BASE_CURRENCY
    if code == BASE_CURRENCY:
        return BASE_CURRENCY, 1.0
    rate = payload.exchange_rate
    if rate is None or float(rate) <= 0:
        raise HTTPException(
            status_code=400,
            detail=f"Exchange rate is required and must be greater than zero for {code} invoices.",
        )
    return code, float(rate)


def _round_invoice_total(exact_total: int, currency_code: str | None) -> int:
    """Round the invoice grand total. The 'nearest ₹5 (down)' rule is a base-currency
    (INR) cash convention and would badly distort a foreign total (e.g. $18.00 -> $15.00),
    so it is applied ONLY to INR invoices; foreign invoices keep the exact total."""
    if (currency_code or BASE_CURRENCY).strip().upper() != BASE_CURRENCY:
        return int(round(float(exact_total or 0)))
    return round_paise_to_nearest_5(exact_total)


@router.post("/api/v1/invoices", response_model=SalesInvoiceResponse)
async def create_invoice(
    payload: SalesInvoiceCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("sales_invoices_write")),
):
    customer = db.query(Customer).filter(Customer.id == payload.customer_id, Customer.is_deleted == False).first()
    if not customer:
        raise HTTPException(status_code=400, detail="Invalid customer")
    # Inactive (soft-deleted / deactivated) customers cannot be used for new/draft
    # invoices. Already-issued invoices keep their customer; only draft save is gated.
    if not customer.is_active:
        raise HTTPException(status_code=400, detail="This customer is inactive and cannot be used for new invoices")
    _enforce_owner(customer, current_user)

    _validate_shipping_address_for_invoice(customer)

    stockist_name, stockist_city, sales_manager_name = _validate_invoice_master_fields(payload)

    product_cache = _validate_invoice_line_items_for_save(db, payload.items, current_user)

    calculated_due_date = _calculate_invoice_due_date(payload.invoice_date, customer)
    resolved_due_date = payload.due_date or calculated_due_date

    if payload.sales_order_id:
        raise HTTPException(
            status_code=400,
            detail="Sales Order module has been removed. Create invoice directly.",
        )

    # BUG-02: Auto-detect GST mode from country + state/state-code
    tax_mode = determine_tax_mode(db, "customer", payload.customer_id)
    expected_invoice_type = determine_default_invoice_type(db, payload.customer_id)
    invoice_type = payload.invoice_type or expected_invoice_type
    _validate_invoice_type_for_country(invoice_type, customer)
    _validate_invoice_type_for_location(db, invoice_type, customer)
    invoice_tax_mode = invoice_type_tax_mode(invoice_type, fallback_is_igst=tax_mode["is_igst"])
    is_igst = invoice_tax_mode["is_igst"]
    gst_applicable = invoice_tax_mode["gst_applicable"]
    if not tax_mode["gst_applicable"]:
        is_igst = False
        gst_applicable = False

    _enforce_bill_to_gstin_for_gst_invoice(
        db,
        payload,
        current_user,
        primary_customer=customer,
        gst_applicable=gst_applicable,
    )

    # Transaction currency + exchange rate (per-invoice; INR invoices => rate 1.0).
    currency_code, exchange_rate = _resolve_invoice_currency(customer, payload)

    invoice = SalesInvoice(
        invoice_number=generate_invoice_number(db, current_user.company_id),
        sales_order_id=None,
        quotation_id=payload.quotation_id,
        customer_id=payload.customer_id,
        invoice_date=payload.invoice_date,
        due_date=resolved_due_date,
        status="draft",
        sold_to_customer_id=payload.sold_to_customer_id or payload.customer_id,
        bill_to_customer_id=payload.bill_to_customer_id or payload.customer_id,
        ship_to_customer_id=payload.ship_to_customer_id or payload.customer_id,
        supply_state=payload.supply_state,
        supply_state_code=payload.supply_state_code,
        invoice_type=invoice_type,
        import_export_code=payload.import_export_code,
        is_igst=is_igst,
        currency_code=currency_code,
        exchange_rate=exchange_rate,
        stockist_name=stockist_name,
        stockist_city=stockist_city,
        sales_manager_name=sales_manager_name,
        notes=payload.notes,
        terms_conditions=payload.terms_conditions,
        company_id=current_user.company_id,
        created_by=current_user.id,
    )
    db.add(invoice)
    db.flush()

    subtotal = total_discount = total_taxable = total_cgst = total_sgst = total_igst = 0
    for item in payload.items:
        product = product_cache[str(item.product_id)]
        calc = calc_line_item(
            item.quantity,
            item.unit_price,
            item.discount_percent,
            item.gst_rate,
            is_igst,
            gst_applicable,
        )
        db.add(SalesInvoiceItem(
            invoice_id=invoice.id,
            product_id=item.product_id,
            description=item.description,
            order_unit=item.order_unit,
            batch_no=item.batch_no,
            manufacture_date=item.manufacture_date,
            expiry_date=item.expiry_date,
            quantity=item.quantity,
            free_quantity=item.free_quantity,
            unit_price=item.unit_price,
            mrp=product.mrp,
            discount_percent=item.discount_percent,
            discount_amount=calc["discount"],
            taxable_amount=calc["taxable"],
            gst_rate=calc["gst_rate"],
            cgst_amount=calc["cgst"],
            sgst_amount=calc["sgst"],
            igst_amount=calc["igst"],
            total_amount=calc["total"],
        ))
        subtotal += calc["gross"]
        total_discount += calc["discount"]
        total_taxable += calc["taxable"]
        total_cgst += calc["cgst"]
        total_sgst += calc["sgst"]
        total_igst += calc["igst"]

    invoice.subtotal = subtotal
    invoice.total_discount = total_discount
    invoice.total_taxable_amount = total_taxable
    invoice.total_cgst = total_cgst
    invoice.total_sgst = total_sgst
    invoice.total_igst = total_igst
    invoice.total_gst = total_cgst + total_sgst + total_igst
    exact_total = total_taxable + invoice.total_gst
    invoice.total_amount = _round_invoice_total(exact_total, invoice.currency_code)
    invoice.amount_due = invoice.total_amount

    db.commit()
    db.refresh(invoice)
    return invoice


@router.get("/api/v1/invoices/{invoice_id}")
async def get_invoice(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("sales_invoices_read")),
):
    invoice = db.query(SalesInvoice).filter(SalesInvoice.id == invoice_id, SalesInvoice.is_deleted == False).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    _enforce_owner(invoice, current_user)
    invoice.status = _derive_invoice_status(invoice.status, int(invoice.amount_paid or 0), int(invoice.total_amount or 0))
    items = db.query(SalesInvoiceItem).filter(SalesInvoiceItem.invoice_id == invoice_id).all()

    return_rows = (
        db.query(
            RdnCreditNoteItem.invoice_item_id,
            func.coalesce(func.sum(RdnCreditNoteItem.return_quantity), 0).label("qty"),
            func.coalesce(func.sum(RdnCreditNoteItem.taxable_amount), 0).label("taxable"),
            func.coalesce(func.sum(RdnCreditNoteItem.cgst_amount), 0).label("cgst"),
            func.coalesce(func.sum(RdnCreditNoteItem.sgst_amount), 0).label("sgst"),
            func.coalesce(func.sum(RdnCreditNoteItem.igst_amount), 0).label("igst"),
            func.coalesce(func.sum(RdnCreditNoteItem.total_amount), 0).label("total"),
        )
        .join(RdnCreditNote, RdnCreditNoteItem.credit_note_id == RdnCreditNote.id)
        .filter(
            RdnCreditNote.sales_invoice_id == invoice_id,
            RdnCreditNote.status == "posted",
            RdnCreditNote.is_deleted == False,
            RdnCreditNoteItem.is_deleted == False,
            RdnCreditNoteItem.invoice_item_id.isnot(None),
        )
        .group_by(RdnCreditNoteItem.invoice_item_id)
        .all()
    )
    returned_by_item = {
        str(row.invoice_item_id): {
            "qty": float(row.qty or 0),
            "taxable": int(row.taxable or 0),
            "cgst": int(row.cgst or 0),
            "sgst": int(row.sgst or 0),
            "igst": int(row.igst or 0),
            "total": int(row.total or 0),
        }
        for row in return_rows
        if row.invoice_item_id is not None
    }

    items_payload = []
    for item in items:
        payload = jsonable_encoder(item)
        returned = returned_by_item.get(str(item.id))
        if returned:
            returned_qty = float(returned.get("qty", 0.0))
            payload["returned_quantity"] = returned_qty
            payload["net_quantity"] = max(0.0, float(item.quantity or 0) - returned_qty)
            payload["net_taxable_amount"] = max(0, int(item.taxable_amount or 0) - int(returned.get("taxable", 0)))
            payload["net_cgst_amount"] = max(0, int(item.cgst_amount or 0) - int(returned.get("cgst", 0)))
            payload["net_sgst_amount"] = max(0, int(item.sgst_amount or 0) - int(returned.get("sgst", 0)))
            payload["net_igst_amount"] = max(0, int(item.igst_amount or 0) - int(returned.get("igst", 0)))
            payload["net_total_amount"] = max(0, int(item.total_amount or 0) - int(returned.get("total", 0)))
        items_payload.append(payload)

    # Resolve customer name/code (not filtered by is_deleted) so a soft-deleted
    # customer's historical invoice still shows the original details.
    customer_row = (
        db.query(Customer.company_name, Customer.customer_code)
        .filter(Customer.id == invoice.customer_id, Customer.company_id == current_user.company_id)
        .first()
    )

    _rate = float(invoice.exchange_rate or 1) or 1.0
    return {
        "invoice": invoice,
        "items": items_payload,
        "customer_name": customer_row[0] if customer_row else None,
        "customer_code": customer_row[1] if customer_row else None,
        # Currency display for the detail view / PDF (INR = base).
        "currency_code": invoice.currency_code or BASE_CURRENCY,
        "exchange_rate": _rate,
        "base_currency": BASE_CURRENCY,
        "base_currency_total": int(round(int(invoice.total_amount or 0) * _rate)),
    }


@router.put("/api/v1/invoices/{invoice_id}")
async def update_invoice(
    invoice_id: UUID,
    payload: SalesInvoiceCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("sales_invoices_write")),
):
    invoice = db.query(SalesInvoice).filter(SalesInvoice.id == invoice_id, SalesInvoice.is_deleted == False).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    _enforce_owner(invoice, current_user)
    if invoice.status != "draft":
        raise HTTPException(status_code=400, detail="Only draft invoice can be edited")

    # Snapshot pre-edit values so the audit trail can show exact field-level changes.
    old_total_amount = invoice.total_amount
    old_total_discount = invoice.total_discount
    old_total_gst = invoice.total_gst
    old_invoice_date = invoice.invoice_date
    old_due_date = invoice.due_date
    old_invoice_type = invoice.invoice_type
    old_notes = invoice.notes
    old_terms = invoice.terms_conditions
    old_stockist_name = invoice.stockist_name
    old_stockist_city = invoice.stockist_city
    old_sales_manager_name = invoice.sales_manager_name
    old_customer_id = invoice.customer_id
    old_customer = (
        db.query(Customer).filter(Customer.id == old_customer_id).first()
        if old_customer_id else None
    )
    old_items_by_product: dict[str, dict[str, Any]] = {}
    old_product_counts: dict[str, int] = {}
    for it in db.query(SalesInvoiceItem).filter(SalesInvoiceItem.invoice_id == invoice_id).all():
        pid = str(it.product_id)
        old_product_counts[pid] = old_product_counts.get(pid, 0) + 1
        old_items_by_product[pid] = {
            "quantity": it.quantity,
            "free_quantity": it.free_quantity,
            "unit_price": it.unit_price,
            "discount_percent": it.discount_percent,
            "batch_no": it.batch_no,
        }

    customer = db.query(Customer).filter(Customer.id == payload.customer_id, Customer.is_deleted == False).first()
    if not customer:
        raise HTTPException(status_code=400, detail="Invalid customer")
    # Inactive (soft-deleted / deactivated) customers cannot be used for new/draft
    # invoices. Already-issued invoices keep their customer; only draft save is gated.
    if not customer.is_active:
        raise HTTPException(status_code=400, detail="This customer is inactive and cannot be used for new invoices")
    _enforce_owner(customer, current_user)

    _validate_shipping_address_for_invoice(customer)

    stockist_name, stockist_city, sales_manager_name = _validate_invoice_master_fields(payload)

    product_cache = _validate_invoice_line_items_for_save(db, payload.items, current_user)

    calculated_due_date = _calculate_invoice_due_date(payload.invoice_date, customer)
    resolved_due_date = payload.due_date or calculated_due_date

    # BUG-02: Auto-detect GST mode (country + state/state-code)
    tax_mode = determine_tax_mode(db, "customer", payload.customer_id)
    expected_invoice_type = determine_default_invoice_type(db, payload.customer_id)
    invoice_type = payload.invoice_type or expected_invoice_type
    _validate_invoice_type_for_country(invoice_type, customer)
    _validate_invoice_type_for_location(db, invoice_type, customer)
    invoice_tax_mode = invoice_type_tax_mode(invoice_type, fallback_is_igst=tax_mode["is_igst"])
    is_igst = invoice_tax_mode["is_igst"]
    gst_applicable = invoice_tax_mode["gst_applicable"]
    if not tax_mode["gst_applicable"]:
        is_igst = False
        gst_applicable = False

    if payload.sales_order_id:
        raise HTTPException(
            status_code=400,
            detail="Sales Order module has been removed. Create invoice directly.",
        )

    # Re-resolve transaction currency + exchange rate for the draft (the customer,
    # and therefore the currency, may have changed). Foreign invoices require a rate > 0.
    invoice.currency_code, invoice.exchange_rate = _resolve_invoice_currency(customer, payload)
    invoice.customer_id = payload.customer_id
    invoice.sales_order_id = None
    invoice.quotation_id = payload.quotation_id
    invoice.invoice_date = payload.invoice_date
    invoice.due_date = resolved_due_date
    invoice.sold_to_customer_id = payload.sold_to_customer_id or payload.customer_id
    invoice.bill_to_customer_id = payload.bill_to_customer_id or payload.customer_id
    invoice.ship_to_customer_id = payload.ship_to_customer_id or payload.customer_id
    invoice.supply_state = payload.supply_state
    invoice.supply_state_code = payload.supply_state_code
    invoice.invoice_type = invoice_type
    invoice.import_export_code = payload.import_export_code
    invoice.is_igst = is_igst
    invoice.stockist_name = stockist_name
    invoice.stockist_city = stockist_city
    invoice.sales_manager_name = sales_manager_name
    invoice.notes = payload.notes
    invoice.terms_conditions = payload.terms_conditions

    db.query(SalesInvoiceItem).filter(SalesInvoiceItem.invoice_id == invoice_id).delete()
    db.flush()

    subtotal = total_discount = total_taxable = total_cgst = total_sgst = total_igst = 0
    for item in payload.items:
        product = product_cache[str(item.product_id)]
        calc = calc_line_item(
            item.quantity,
            item.unit_price,
            item.discount_percent,
            item.gst_rate,
            is_igst,
            gst_applicable,
        )
        db.add(SalesInvoiceItem(
            invoice_id=invoice.id,
            product_id=item.product_id,
            description=item.description,
            order_unit=item.order_unit,
            batch_no=item.batch_no,
            manufacture_date=item.manufacture_date,
            expiry_date=item.expiry_date,
            quantity=item.quantity,
            free_quantity=item.free_quantity,
            unit_price=item.unit_price,
            mrp=product.mrp,
            discount_percent=item.discount_percent,
            discount_amount=calc["discount"],
            taxable_amount=calc["taxable"],
            gst_rate=calc["gst_rate"],
            cgst_amount=calc["cgst"],
            sgst_amount=calc["sgst"],
            igst_amount=calc["igst"],
            total_amount=calc["total"],
        ))
        subtotal += calc["gross"]
        total_discount += calc["discount"]
        total_taxable += calc["taxable"]
        total_cgst += calc["cgst"]
        total_sgst += calc["sgst"]
        total_igst += calc["igst"]

    invoice.subtotal = subtotal
    invoice.total_discount = total_discount
    invoice.total_taxable_amount = total_taxable
    invoice.total_cgst = total_cgst
    invoice.total_sgst = total_sgst
    invoice.total_igst = total_igst
    invoice.total_gst = total_cgst + total_sgst + total_igst
    exact_total = total_taxable + invoice.total_gst
    invoice.total_amount = _round_invoice_total(exact_total, invoice.currency_code)
    invoice.amount_due = max(0, invoice.total_amount - invoice.amount_paid)

    # Record exact field-level changes for the audit trail (rendered as
    # "<Field> changed from <old> to <new>"). The baseline audit middleware merges
    # these in, keeping a single readable audit entry per edit. Reference the
    # invoice number, not the UUID.
    old_customer_name = (old_customer.company_name or "").strip() if old_customer else ""
    new_customer_name = (customer.company_name or "").strip()
    audit_changes = build_audit_changes([
        ("customer", old_customer_name, new_customer_name),
        ("invoice_date", old_invoice_date, invoice.invoice_date),
        ("due_date", old_due_date, invoice.due_date),
        ("invoice_type", old_invoice_type, invoice.invoice_type),
        ("stockist_name", old_stockist_name, invoice.stockist_name),
        ("stockist_city", old_stockist_city, invoice.stockist_city),
        ("sales_manager_name", old_sales_manager_name, invoice.sales_manager_name),
        ("notes", old_notes, invoice.notes),
        ("terms_conditions", old_terms, invoice.terms_conditions),
        ("total_discount", old_total_discount, invoice.total_discount),
        ("total_amount", old_total_amount, invoice.total_amount),
    ])

    # Per-line changes, attributed to the product. Only diff products that appear
    # exactly once on each side (so "old -> new" is unambiguous); otherwise just
    # note the line as added/removed. Header totals above still capture the rest.
    new_product_counts: dict[str, int] = {}
    new_items_by_product: dict[str, Any] = {}
    for line in payload.items:
        pid = str(line.product_id)
        new_product_counts[pid] = new_product_counts.get(pid, 0) + 1
        new_items_by_product[pid] = line

    def _product_name(pid: str) -> str:
        cached = product_cache.get(pid)
        if cached is not None:
            return cached.name
        prod = db.query(Product).filter(Product.id == pid).first()
        return prod.name if prod else "Item"

    for pid in list(old_items_by_product.keys()) + [p for p in new_items_by_product if p not in old_items_by_product]:
        in_old = pid in old_items_by_product
        in_new = pid in new_items_by_product
        name = _product_name(pid)
        if in_old and not in_new:
            audit_changes.append({"field": "line_item", "product": name,
                                  "old_value": "present", "new_value": "removed"})
            continue
        if in_new and not in_old:
            audit_changes.append({"field": "line_item", "product": name,
                                  "old_value": "absent", "new_value": "added"})
            continue
        # Present on both sides: only emit precise diffs when unambiguous.
        if old_product_counts.get(pid, 0) != 1 or new_product_counts.get(pid, 0) != 1:
            continue
        old_line = old_items_by_product[pid]
        new_line = new_items_by_product[pid]
        audit_changes.extend(build_audit_changes([
            ("quantity", old_line["quantity"], new_line.quantity, name),
            ("free_quantity", old_line["free_quantity"], new_line.free_quantity, name),
            ("unit_price", old_line["unit_price"], new_line.unit_price, name),
            ("discount_percent", old_line["discount_percent"], new_line.discount_percent, name),
            ("batch_no", old_line["batch_no"], new_line.batch_no, name),
        ]))

    request.state.audit_reference = invoice.invoice_number
    if audit_changes:
        request.state.audit_changes = audit_changes

    db.commit()
    db.refresh(invoice)
    return invoice


@router.put("/api/v1/invoices/{invoice_id}/issued-details")
async def update_issued_invoice(
    invoice_id: UUID,
    payload: SalesInvoiceCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """Edit an already-ISSUED Sales Invoice (authorized users only).

    Issued invoices have posted stock and an established receivable. This endpoint
    reverses the invoice's original stock 'sale' postings, rebuilds the line items,
    recomputes tax/totals, re-posts the corrected 'sale' entries, and recomputes
    amount_due/status — so stock, tax, totals and the derived accounting stay correct.
    Every field change (old -> new) is written to the audit trail with the acting user
    and timestamp (via the audit middleware, which references the invoice number).

    Editing is blocked when a (non-cancelled) receipt is allocated or a confirmed sales
    return exists for the invoice, because changing quantities/totals would desync those
    postings — clear them first. Draft invoices continue to use PUT /api/v1/invoices/{id}.
    """
    from app.models.payment import Payment, PaymentAllocation

    invoice = (
        db.query(SalesInvoice)
        .filter(SalesInvoice.id == invoice_id, SalesInvoice.is_deleted == False)
        .with_for_update()
        .first()
    )
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    _enforce_owner(invoice, current_user)
    if invoice.status not in {"issued", "partial_paid", "paid"}:
        raise HTTPException(
            status_code=400,
            detail="Only issued invoices can be edited here. Draft invoices use the standard edit form.",
        )

    # Financial-integrity guards (mirror GRN confirmed-edit).
    has_payment = (
        db.query(PaymentAllocation)
        .join(Payment, PaymentAllocation.payment_id == Payment.id)
        .filter(
            PaymentAllocation.invoice_id == invoice_id,
            PaymentAllocation.is_deleted == False,
            Payment.is_deleted == False,
            Payment.status != "cancelled",
        )
        .first()
    )
    if has_payment:
        raise HTTPException(
            status_code=400,
            detail="Cannot edit: a payment is allocated to this invoice. Cancel/bounce the payment first.",
        )

    has_return = (
        db.query(SalesReturn)
        .filter(
            SalesReturn.invoice_id == invoice_id,
            SalesReturn.is_deleted == False,
            SalesReturn.status == "confirmed",
        )
        .first()
    )
    if has_return:
        raise HTTPException(
            status_code=400,
            detail="Cannot edit: a confirmed sales return exists for this invoice.",
        )

    # Snapshot pre-edit values for the audit trail (field-level old -> new).
    old_total_amount = invoice.total_amount
    old_total_discount = invoice.total_discount
    old_invoice_date = invoice.invoice_date
    old_due_date = invoice.due_date
    old_invoice_type = invoice.invoice_type
    old_notes = invoice.notes
    old_terms = invoice.terms_conditions
    old_stockist_name = invoice.stockist_name
    old_stockist_city = invoice.stockist_city
    old_sales_manager_name = invoice.sales_manager_name
    old_customer_id = invoice.customer_id
    old_customer = (
        db.query(Customer).filter(Customer.id == old_customer_id).first()
        if old_customer_id else None
    )
    old_item_rows = db.query(SalesInvoiceItem).filter(SalesInvoiceItem.invoice_id == invoice_id).all()
    old_items_by_product: dict[str, dict[str, Any]] = {}
    old_product_counts: dict[str, int] = {}
    for it in old_item_rows:
        pid = str(it.product_id)
        old_product_counts[pid] = old_product_counts.get(pid, 0) + 1
        old_items_by_product[pid] = {
            "quantity": it.quantity,
            "free_quantity": it.free_quantity,
            "unit_price": it.unit_price,
            "discount_percent": it.discount_percent,
            "batch_no": it.batch_no,
        }

    customer = db.query(Customer).filter(Customer.id == payload.customer_id, Customer.is_deleted == False).first()
    if not customer:
        raise HTTPException(status_code=400, detail="Invalid customer")
    _enforce_owner(customer, current_user)
    _validate_shipping_address_for_invoice(customer)

    stockist_name, stockist_city, sales_manager_name = _validate_invoice_master_fields(payload)

    product_cache = _validate_invoice_line_items_for_save(db, payload.items, current_user)

    calculated_due_date = _calculate_invoice_due_date(payload.invoice_date, customer)
    resolved_due_date = payload.due_date or calculated_due_date

    tax_mode = determine_tax_mode(db, "customer", payload.customer_id)
    expected_invoice_type = determine_default_invoice_type(db, payload.customer_id)
    invoice_type = payload.invoice_type or expected_invoice_type
    _validate_invoice_type_for_country(invoice_type, customer)
    _validate_invoice_type_for_location(db, invoice_type, customer)
    invoice_tax_mode = invoice_type_tax_mode(invoice_type, fallback_is_igst=tax_mode["is_igst"])
    is_igst = invoice_tax_mode["is_igst"]
    gst_applicable = invoice_tax_mode["gst_applicable"]
    if not tax_mode["gst_applicable"]:
        is_igst = False
        gst_applicable = False

    if payload.sales_order_id:
        raise HTTPException(
            status_code=400,
            detail="Sales Order module has been removed. Create invoice directly.",
        )

    today = date.today()

    # Reverse the original stock 'sale' postings (qty + free) so on-hand returns to
    # its pre-issue level before the corrected lines are re-posted.
    for it in old_item_rows:
        add_stock_entry(
            db=db,
            product_id=it.product_id,
            transaction_type="adjustment",
            reference_type="inv_edit_reversal",
            reference_id=invoice.id,
            reference_number=f"{invoice.invoice_number}-EDIT-REV",
            quantity=float(it.quantity or 0),
            rate=it.unit_price,
            transaction_date=today,
            created_by=current_user.id,
            notes="Issued-invoice edit: reverse original sale",
        )
        if it.free_quantity and float(it.free_quantity) > 0:
            add_stock_entry(
                db=db,
                product_id=it.product_id,
                transaction_type="adjustment",
                reference_type="inv_edit_reversal",
                reference_id=invoice.id,
                reference_number=f"{invoice.invoice_number}-FREE-EDIT-REV",
                quantity=float(it.free_quantity),
                rate=0,
                transaction_date=today,
                created_by=current_user.id,
                notes="Issued-invoice edit: reverse original free sale",
            )
    db.flush()

    # Validate stock availability for the corrected lines against on-hand (which now
    # reflects the reversal), aggregated per product so a reduced/raised line is fair.
    new_demand_by_product: dict[str, float] = {}
    for line in payload.items:
        pid = str(line.product_id)
        new_demand_by_product[pid] = (
            new_demand_by_product.get(pid, 0.0)
            + float(line.quantity or 0) + float(line.free_quantity or 0)
        )
    for pid, demand in new_demand_by_product.items():
        available = get_current_stock(db, UUID(pid))
        if demand - available > 1e-6:
            product = product_cache.get(pid)
            label = product.name if product else pid
            raise HTTPException(status_code=400, detail=f"Insufficient stock for product {label}")

    invoice.customer_id = payload.customer_id
    invoice.sales_order_id = None
    invoice.quotation_id = payload.quotation_id
    invoice.invoice_date = payload.invoice_date
    invoice.due_date = resolved_due_date
    invoice.sold_to_customer_id = payload.sold_to_customer_id or payload.customer_id
    invoice.bill_to_customer_id = payload.bill_to_customer_id or payload.customer_id
    invoice.ship_to_customer_id = payload.ship_to_customer_id or payload.customer_id
    invoice.supply_state = payload.supply_state
    invoice.supply_state_code = payload.supply_state_code
    invoice.invoice_type = invoice_type
    invoice.import_export_code = payload.import_export_code
    invoice.is_igst = is_igst
    invoice.stockist_name = stockist_name
    invoice.stockist_city = stockist_city
    invoice.sales_manager_name = sales_manager_name
    invoice.notes = payload.notes
    invoice.terms_conditions = payload.terms_conditions

    db.query(SalesInvoiceItem).filter(SalesInvoiceItem.invoice_id == invoice_id).delete()
    db.flush()

    subtotal = total_discount = total_taxable = total_cgst = total_sgst = total_igst = 0
    for item in payload.items:
        product = product_cache[str(item.product_id)]
        calc = calc_line_item(
            item.quantity,
            item.unit_price,
            item.discount_percent,
            item.gst_rate,
            is_igst,
            gst_applicable,
        )
        db.add(SalesInvoiceItem(
            invoice_id=invoice.id,
            product_id=item.product_id,
            description=item.description,
            order_unit=item.order_unit,
            batch_no=item.batch_no,
            manufacture_date=item.manufacture_date,
            expiry_date=item.expiry_date,
            quantity=item.quantity,
            free_quantity=item.free_quantity,
            unit_price=item.unit_price,
            mrp=product.mrp,
            discount_percent=item.discount_percent,
            discount_amount=calc["discount"],
            taxable_amount=calc["taxable"],
            gst_rate=calc["gst_rate"],
            cgst_amount=calc["cgst"],
            sgst_amount=calc["sgst"],
            igst_amount=calc["igst"],
            total_amount=calc["total"],
        ))
        subtotal += calc["gross"]
        total_discount += calc["discount"]
        total_taxable += calc["taxable"]
        total_cgst += calc["cgst"]
        total_sgst += calc["sgst"]
        total_igst += calc["igst"]

        # Re-post the corrected sale (stock out) at the new quantity/rate.
        add_stock_entry(
            db=db,
            product_id=item.product_id,
            transaction_type="sale",
            reference_type="invoice",
            reference_id=invoice.id,
            reference_number=invoice.invoice_number,
            quantity=-float(item.quantity),
            rate=item.unit_price,
            transaction_date=invoice.invoice_date,
            created_by=current_user.id,
            notes="Issued-invoice edit: corrected sale",
        )
        if item.free_quantity and float(item.free_quantity) > 0:
            add_stock_entry(
                db=db,
                product_id=item.product_id,
                transaction_type="sale",
                reference_type="invoice",
                reference_id=invoice.id,
                reference_number=f"{invoice.invoice_number}-FREE",
                quantity=-float(item.free_quantity),
                rate=0,
                transaction_date=invoice.invoice_date,
                created_by=current_user.id,
                notes="Issued-invoice edit: corrected free sale",
            )

    invoice.subtotal = subtotal
    invoice.total_discount = total_discount
    invoice.total_taxable_amount = total_taxable
    invoice.total_cgst = total_cgst
    invoice.total_sgst = total_sgst
    invoice.total_igst = total_igst
    invoice.total_gst = total_cgst + total_sgst + total_igst
    exact_total = total_taxable + invoice.total_gst
    invoice.total_amount = _round_invoice_total(exact_total, invoice.currency_code)
    invoice.amount_due = max(0, invoice.total_amount - invoice.amount_paid)
    # Recompute the payment status from the corrected total (amount_paid is unchanged).
    invoice.status = _compute_invoice_status(invoice.amount_paid, invoice.total_amount)

    refresh_materialized_view(db)

    # Field-level audit (rendered "<Field> changed from <old> to <new>"). The audit
    # middleware merges these into a single readable row with the acting user + timestamp.
    old_customer_name = (old_customer.company_name or "").strip() if old_customer else ""
    new_customer_name = (customer.company_name or "").strip()
    audit_changes = build_audit_changes([
        ("customer", old_customer_name, new_customer_name),
        ("invoice_date", old_invoice_date, invoice.invoice_date),
        ("due_date", old_due_date, invoice.due_date),
        ("invoice_type", old_invoice_type, invoice.invoice_type),
        ("stockist_name", old_stockist_name, invoice.stockist_name),
        ("stockist_city", old_stockist_city, invoice.stockist_city),
        ("sales_manager_name", old_sales_manager_name, invoice.sales_manager_name),
        ("notes", old_notes, invoice.notes),
        ("terms_conditions", old_terms, invoice.terms_conditions),
        ("total_discount", old_total_discount, invoice.total_discount),
        ("total_amount", old_total_amount, invoice.total_amount),
    ])

    new_product_counts: dict[str, int] = {}
    new_items_by_product: dict[str, Any] = {}
    for line in payload.items:
        pid = str(line.product_id)
        new_product_counts[pid] = new_product_counts.get(pid, 0) + 1
        new_items_by_product[pid] = line

    def _product_name(pid: str) -> str:
        cached = product_cache.get(pid)
        if cached is not None:
            return cached.name
        prod = db.query(Product).filter(Product.id == pid).first()
        return prod.name if prod else "Item"

    for pid in list(old_items_by_product.keys()) + [p for p in new_items_by_product if p not in old_items_by_product]:
        in_old = pid in old_items_by_product
        in_new = pid in new_items_by_product
        name = _product_name(pid)
        if in_old and not in_new:
            audit_changes.append({"field": "line_item", "product": name,
                                  "old_value": "present", "new_value": "removed"})
            continue
        if in_new and not in_old:
            audit_changes.append({"field": "line_item", "product": name,
                                  "old_value": "absent", "new_value": "added"})
            continue
        if old_product_counts.get(pid, 0) != 1 or new_product_counts.get(pid, 0) != 1:
            continue
        old_line = old_items_by_product[pid]
        new_line = new_items_by_product[pid]
        audit_changes.extend(build_audit_changes([
            ("quantity", old_line["quantity"], new_line.quantity, name),
            ("free_quantity", old_line["free_quantity"], new_line.free_quantity, name),
            ("unit_price", old_line["unit_price"], new_line.unit_price, name),
            ("discount_percent", old_line["discount_percent"], new_line.discount_percent, name),
            ("batch_no", old_line["batch_no"], new_line.batch_no, name),
        ]))

    request.state.audit_reference = invoice.invoice_number
    if audit_changes:
        request.state.audit_changes = audit_changes

    db.commit()
    db.refresh(invoice)
    return invoice


@router.post("/api/v1/invoices/{invoice_id}/issue")
async def issue_invoice(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    invoice = (
        db.query(SalesInvoice)
        .filter(SalesInvoice.id == invoice_id, SalesInvoice.is_deleted == False)
        .with_for_update()
        .first()
    )
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    _enforce_owner(invoice, current_user)
    if invoice.status != "draft":
        raise HTTPException(status_code=400, detail="Only draft invoices can be issued")

    existing_issue = (
        db.query(StockLedger.id)
        .filter(
            StockLedger.reference_type == "invoice",
            StockLedger.reference_id == invoice.id,
            StockLedger.transaction_type == "sale",
            StockLedger.is_deleted == False,
        )
        .first()
    )
    if existing_issue:
        raise HTTPException(status_code=400, detail="Stock already deducted for this invoice")

    items = db.query(SalesInvoiceItem).filter(SalesInvoiceItem.invoice_id == invoice.id).all()

    # SAL-044 safety guard: block issue if stored batch/date data is invalid.
    _validate_invoice_line_items_for_save(db, items, current_user, allow_deleted_products=True)

    batch_snapshots = {
        str(item.product_id): get_product_batch_snapshot(db, item.product_id)
        for item in items
        if item.batch_no
    }
    stock_cache = {}
    for item in items:
        batch_token = (item.batch_no or "").strip()
        product_key = str(item.product_id)
        cache_key = f"{product_key}_{batch_token}"
        
        if cache_key not in stock_cache:
            if batch_token:
                stock_cache[cache_key] = float(batch_snapshots.get(product_key, {}).get(batch_token, {}).get("available_qty", 0.0))
            else:
                stock_cache[cache_key] = get_current_stock(db, item.product_id)
                
        total_qty = float(item.quantity) + float(item.free_quantity or 0)
        if stock_cache[cache_key] < total_qty:
            raise HTTPException(status_code=400, detail=f"Insufficient stock for product {item.product_id}")
            
        stock_cache[cache_key] -= total_qty

    # BUG-01: Use stock service for entries
    for item in items:
        add_stock_entry(
            db=db,
            product_id=item.product_id,
            transaction_type="sale",
            reference_type="invoice",
            reference_id=invoice.id,
            reference_number=invoice.invoice_number,
            quantity=-float(item.quantity),
            rate=item.unit_price,
            transaction_date=invoice.invoice_date,
            created_by=current_user.id,
        )
        if item.free_quantity and float(item.free_quantity) > 0:
            add_stock_entry(
                db=db,
                product_id=item.product_id,
                transaction_type="sale",
                reference_type="invoice",
                reference_id=invoice.id,
                reference_number=f"{invoice.invoice_number}-FREE",
                quantity=-float(item.free_quantity),
                rate=0,
                transaction_date=invoice.invoice_date,
                created_by=current_user.id,
            )

    # BUG-01: Refresh materialized view
    refresh_materialized_view(db)

    invoice.status = _compute_invoice_status(invoice.amount_paid, invoice.total_amount)
    invoice.amount_due = max(0, invoice.total_amount - invoice.amount_paid)
    invoice.pdf_url = f"/api/v1/invoices/{invoice.id}/pdf"

    # Update SO fulfillment status
    if invoice.sales_order_id:
        so = db.query(SalesOrder).filter(SalesOrder.id == invoice.sales_order_id, SalesOrder.is_deleted == False).first()
        if so:
            so_items = db.query(SalesOrderItem).filter(SalesOrderItem.sales_order_id == so.id).all()
            by_product = {}
            for item in items:
                by_product.setdefault(str(item.product_id), 0)
                by_product[str(item.product_id)] += float(item.quantity)
            for so_item in so_items:
                fulfilled_add = by_product.get(str(so_item.product_id), 0)
                so_item.fulfilled_quantity = float(so_item.fulfilled_quantity) + fulfilled_add

            if so_items and all(float(i.fulfilled_quantity) >= float(i.quantity) for i in so_items):
                so.status = "fulfilled"
            else:
                so.status = "partial"

    db.commit()
    db.refresh(invoice)
    return invoice


@router.post("/api/v1/invoices/{invoice_id}/send-email")
async def send_invoice_email(
    invoice_id: UUID,
    payload: dict | None = Body(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("sales_invoices_write")),
):
    from app.services.pdf_service import generate_invoice_pdf

    invoice = db.query(SalesInvoice).filter(SalesInvoice.id == invoice_id, SalesInvoice.is_deleted == False).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    _enforce_owner(invoice, current_user)

    recipient = (payload or {}).get("email") if payload else None
    if not recipient:
        customer = db.query(Customer).filter(Customer.id == invoice.customer_id, Customer.is_deleted == False).first()
        if customer:
            _enforce_owner(customer, current_user)
        recipient = customer.email if customer else None

    if not recipient:
        raise HTTPException(status_code=400, detail="Recipient email is required")

    pdf_bytes = generate_invoice_pdf(db, invoice_id)
    subject = f"Sales Invoice {invoice.invoice_number}"
    body = f"Please find attached Sales Invoice {invoice.invoice_number}."
    sent = _send_pdf_email(
        recipient=recipient,
        subject=subject,
        body=body,
        pdf_filename=f"{invoice.invoice_number}.pdf",
        pdf_bytes=pdf_bytes,
    )

    return {
        "message": sent["message"],
        "delivery": sent["delivery"],
        "invoice_number": invoice.invoice_number,
        "recipient": recipient,
        "outbox_file": sent.get("outbox_file"),
    }


# ────────────────────────────── Sales Returns ────────────────────────────────

@router.get("/api/v1/sales-returns")
async def list_sales_returns(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("sales_returns_read")),
):
    query = db.query(SalesReturn).filter(SalesReturn.is_deleted == False)
    query = _scope_to_owner(query, SalesReturn, current_user)
    total = query.count()
    rows = query.order_by(SalesReturn.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"items": rows, "total": total, "page": page, "page_size": page_size, "has_more": (page * page_size) < total}


@router.post("/api/v1/sales-returns")
async def create_sales_return(
    payload: SalesReturnCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("sales_returns_write")),
):
    invoice = db.query(SalesInvoice).filter(SalesInvoice.id == payload.invoice_id, SalesInvoice.is_deleted == False).first()
    if not invoice:
        raise HTTPException(status_code=400, detail="Invalid invoice")
    _enforce_owner(invoice, current_user)

    customer = db.query(Customer).filter(Customer.id == payload.customer_id, Customer.is_deleted == False).first()
    if not customer:
        raise HTTPException(status_code=400, detail="Invalid customer")
    _enforce_owner(customer, current_user)

    # BUG-19: Keep return tax mode aligned with India-only GST applicability.
    tax_mode = determine_tax_mode(db, "customer", payload.customer_id)
    gst_applicable = tax_mode["gst_applicable"]
    is_igst = invoice.is_igst if gst_applicable else False

    ret = SalesReturn(
        return_number=generate_sales_return_number(db, current_user.company_id),
        invoice_id=payload.invoice_id,
        customer_id=payload.customer_id,
        return_date=payload.return_date,
        reason=payload.reason,
        status="draft",
        company_id=current_user.company_id,
        created_by=current_user.id,
    )
    db.add(ret)
    db.flush()

    subtotal = total_gst = 0
    for item in payload.items:
        invoice_item = db.query(SalesInvoiceItem).filter(SalesInvoiceItem.id == item.invoice_item_id).first() if item.invoice_item_id else None
        if invoice_item:
            _enforce_owner(invoice_item, current_user)
            if invoice_item.invoice_id != payload.invoice_id:
                raise HTTPException(status_code=400, detail="Invoice item does not belong to invoice")
        if invoice_item and float(item.quantity) > float(invoice_item.quantity):
            raise HTTPException(status_code=400, detail="Return quantity exceeds invoiced quantity")

        product = db.query(Product).filter(Product.id == item.product_id, Product.is_deleted == False).first()
        if not product:
            raise HTTPException(status_code=400, detail=f"Invalid product: {item.product_id}")
        _enforce_owner(product, current_user)

        taxable = round(item.unit_price * item.quantity)
        # BUG-19: Use invoice's IGST flag for consistent tax
        effective_gst_rate = item.gst_rate if gst_applicable else 0
        cgst, sgst, igst = split_tax(taxable, effective_gst_rate, is_igst, gst_applicable)
        total = taxable + cgst + sgst + igst
        db.add(SalesReturnItem(
            sales_return_id=ret.id,
            product_id=item.product_id,
            invoice_item_id=item.invoice_item_id,
            quantity=item.quantity,
            unit_price=item.unit_price,
            taxable_amount=taxable,
            gst_rate=effective_gst_rate,
            cgst_amount=cgst,
            sgst_amount=sgst,
            igst_amount=igst,
            total_amount=total,
        ))
        subtotal += taxable
        total_gst += cgst + sgst + igst

    ret.subtotal = subtotal
    ret.total_gst = total_gst
    ret.total_amount = subtotal + total_gst
    db.commit()
    db.refresh(ret)
    return ret


@router.get("/api/v1/sales-returns/{return_id}")
async def get_sales_return(
    return_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("sales_returns_read")),
):
    ret = db.query(SalesReturn).filter(SalesReturn.id == return_id, SalesReturn.is_deleted == False).first()
    if not ret:
        raise HTTPException(status_code=404, detail="Sales return not found")
    _enforce_owner(ret, current_user)
    items = db.query(SalesReturnItem).filter(SalesReturnItem.sales_return_id == return_id).all()
    return {"sales_return": ret, "items": items}


@router.post("/api/v1/sales-returns/{return_id}/confirm")
async def confirm_sales_return(
    return_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("sales_returns_write")),
):
    ret = db.query(SalesReturn).filter(SalesReturn.id == return_id, SalesReturn.is_deleted == False).first()
    if not ret:
        raise HTTPException(status_code=404, detail="Sales return not found")
    _enforce_owner(ret, current_user)
    if ret.status != "draft":
        raise HTTPException(status_code=400, detail="Only draft sales return can be confirmed")

    items = db.query(SalesReturnItem).filter(SalesReturnItem.sales_return_id == ret.id).all()
    for item in items:
        # BUG-01: Use stock service with reference_id
        add_stock_entry(
            db=db,
            product_id=item.product_id,
            transaction_type="sale_return",
            reference_type="sales_return",
            reference_id=ret.id,
            reference_number=ret.return_number,
            quantity=float(item.quantity),
            rate=item.unit_price,
            transaction_date=ret.return_date,
            created_by=current_user.id,
        )

    # BUG-01: Refresh materialized view
    refresh_materialized_view(db)

    # BUG-25: Adjust invoice amount_due (credit note behavior)
    invoice = db.query(SalesInvoice).filter(SalesInvoice.id == ret.invoice_id).first()
    if invoice:
        _enforce_owner(invoice, current_user)
        invoice.amount_due = max(0, invoice.amount_due - ret.total_amount)
        if invoice.amount_due == 0:
            invoice.status = "paid"
        elif invoice.amount_paid > 0:
            invoice.status = "partial_paid"

    ret.status = "confirmed"
    db.commit()
    db.refresh(ret)
    return ret


@router.post("/api/v1/sales-returns/{return_id}/cancel")
async def cancel_sales_return(
    return_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("sales_returns_write")),
):
    ret = db.query(SalesReturn).filter(SalesReturn.id == return_id, SalesReturn.is_deleted == False).first()
    if not ret:
        raise HTTPException(status_code=404, detail="Sales return not found")
    _enforce_owner(ret, current_user)
    if ret.status != "draft":
        raise HTTPException(status_code=400, detail="Only draft sales return can be cancelled")

    ret.status = "cancelled"
    db.commit()
    db.refresh(ret)
    return ret


# ────────────────────────────── Invoice PDF Download ──────────────────────────

@router.get("/api/v1/invoices/{invoice_id}/pdf")
async def download_invoice_pdf(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("sales_invoices_read")),
):
    """Download Sales Invoice as a professional PDF."""
    from fastapi.responses import Response
    from app.services.pdf_service import generate_invoice_pdf

    invoice = db.query(SalesInvoice).filter(SalesInvoice.id == invoice_id, SalesInvoice.is_deleted == False).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    _enforce_owner(invoice, current_user)

    pdf_bytes = generate_invoice_pdf(db, invoice_id)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename={invoice.invoice_number}.pdf"},
    )


# ────────────────────────────── Quotation PDF Download ────────────────────────

@router.get("/api/v1/quotations/{quotation_id}/pdf")
async def download_quotation_pdf(
    quotation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("quotations_read")),
):
    """Download Quotation as a professional PDF (same format as Tax Invoice, header = 'Quotation')."""
    from fastapi.responses import Response
    from app.services.pdf_service import generate_quotation_pdf

    q = db.query(Quotation).filter(Quotation.id == quotation_id, Quotation.is_deleted == False).first()
    if not q:
        raise HTTPException(status_code=404, detail="Quotation not found")
    _enforce_owner(q, current_user)

    pdf_bytes = generate_quotation_pdf(db, quotation_id)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename={q.quotation_number}.pdf"},
    )


@router.post("/api/v1/quotations/{quotation_id}/send-email")
async def send_quotation_email(
    quotation_id: UUID,
    payload: dict | None = Body(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("quotations_write")),
):
    from app.services.pdf_service import generate_quotation_pdf

    q = db.query(Quotation).filter(Quotation.id == quotation_id, Quotation.is_deleted == False).first()
    if not q:
        raise HTTPException(status_code=404, detail="Quotation not found")
    _enforce_owner(q, current_user)

    recipient = (payload or {}).get("email") if payload else None
    if not recipient:
        customer = db.query(Customer).filter(Customer.id == q.customer_id, Customer.is_deleted == False).first()
        if customer:
            _enforce_owner(customer, current_user)
        recipient = customer.email if customer else None

    if not recipient:
        raise HTTPException(status_code=400, detail="Recipient email is required")

    pdf_bytes = generate_quotation_pdf(db, quotation_id)
    subject = f"Quotation {q.quotation_number}"
    body = f"Please find attached Quotation {q.quotation_number}."
    sent = _send_pdf_email(
        recipient=recipient,
        subject=subject,
        body=body,
        pdf_filename=f"{q.quotation_number}.pdf",
        pdf_bytes=pdf_bytes,
    )

    return {
        "message": sent["message"],
        "delivery": sent["delivery"],
        "quotation_number": q.quotation_number,
        "recipient": recipient,
        "outbox_file": sent.get("outbox_file"),
    }

