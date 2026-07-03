"""Proforma Invoice router.

Independent, end-to-end replica of the Quotation workflow
(see app/routers/sales.py Quotation section). All behaviour — validations,
GST mode auto-detection, ownership/company scoping, auto-expiry, status
transitions, archive/restore, PDF, e-mail — mirrors Quotation exactly.

Only the module identity changes:
- "Quotation"        -> "Proforma Invoice"
- "Quotation Number" -> "Proforma Invoice Number"  (PFI-00001 …)
- "Quotation Date"   -> "Proforma Invoice Date"

The existing Quotation module is left untouched.
"""
from datetime import date, datetime
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.database import get_db
from app.dependencies import enforce_resource_ownership, require_permissions, require_role, scope_query_to_company
from app.models.user import User
from app.models.product import Product
from app.models.customer import Customer
from app.models.proforma import ProformaInvoice, ProformaInvoiceItem
from app.schemas.proforma import (
    ProformaInvoiceCreateRequest,
    ProformaInvoiceStatusRequest,
    ProformaInvoiceResponse,
    ProformaInvoicesListResponse,
)
from app.services.order_number_service import generate_proforma_invoice_number
from app.services.gst_service import determine_tax_mode, calc_line_item
from app.services.auth_service import normalize_role, PRIVILEGED_ROLES
from app.utils.input_validation import validate_optional_token

router = APIRouter(tags=["proforma-invoices"])


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


def _auto_expire(p: ProformaInvoice) -> None:
    """Auto-expire proforma invoice if valid_until has passed."""
    if p.status in {"draft", "sent"} and p.valid_until and p.valid_until < date.today():
        p.status = "expired"


# ────────────────────────────── Proforma Invoices ─────────────────────────────

@router.get("/api/v1/proforma-invoices", response_model=ProformaInvoicesListResponse)
async def list_proforma_invoices(
    status: str | None = Query(default=None),
    archived_only: bool = Query(default=False),
    include_archived: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("proforma_read")),
):
    status = validate_optional_token(
        status,
        field_name="status",
        allowed={"draft", "sent", "accepted", "rejected", "expired", "converted", "cancelled"},
    )

    query = db.query(ProformaInvoice)
    query = _scope_to_owner(query, ProformaInvoice, current_user)
    if archived_only:
        query = query.filter(ProformaInvoice.is_deleted == True)
    elif not include_archived:
        query = query.filter(ProformaInvoice.is_deleted == False)
    if status:
        query = query.filter(ProformaInvoice.status == status)
    total = query.count()
    rows = query.order_by(ProformaInvoice.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    # Auto-expire on read
    changed = False
    for p in rows:
        if p.status in {"draft", "sent"} and p.valid_until and p.valid_until < date.today():
            p.status = "expired"
            changed = True
    if changed:
        db.commit()

    return ProformaInvoicesListResponse(
        items=[ProformaInvoiceResponse.model_validate(p) for p in rows],
        total=total,
        page=page,
        page_size=page_size,
        has_more=(page * page_size) < total,
    )


@router.post("/api/v1/proforma-invoices", response_model=ProformaInvoiceResponse)
async def create_proforma_invoice(
    payload: ProformaInvoiceCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("proforma_write")),
):
    customer = db.query(Customer).filter(Customer.id == payload.customer_id, Customer.is_deleted == False).first()
    if not customer:
        raise HTTPException(status_code=400, detail="Invalid customer")
    _enforce_owner(customer, current_user)

    # Valid Until must be a future date
    if payload.valid_until and payload.valid_until <= date.today():
        raise HTTPException(status_code=400, detail="Valid Until date must be a future date")

    # Auto-detect GST mode
    tax_mode = determine_tax_mode(db, "customer", payload.customer_id)
    is_igst = tax_mode["is_igst"]
    gst_applicable = tax_mode["gst_applicable"]

    p = ProformaInvoice(
        proforma_number=generate_proforma_invoice_number(db, current_user.company_id),
        customer_id=payload.customer_id,
        proforma_date=payload.proforma_date,
        valid_until=payload.valid_until,
        sold_to_customer_id=payload.sold_to_customer_id or payload.customer_id,
        bill_to_customer_id=payload.bill_to_customer_id or payload.customer_id,
        ship_to_customer_id=payload.ship_to_customer_id or payload.customer_id,
        notes=payload.notes,
        terms_conditions=payload.terms_conditions,
        status="draft",  # Always force draft on creation
        company_id=current_user.company_id,
        created_by=current_user.id,
    )
    db.add(p)
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
        db.add(ProformaInvoiceItem(
            proforma_invoice_id=p.id,
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

    p.subtotal = subtotal
    p.total_discount = total_discount
    p.total_taxable_amount = total_taxable
    p.total_cgst = total_cgst
    p.total_sgst = total_sgst
    p.total_igst = total_igst
    p.total_gst = total_cgst + total_sgst + total_igst
    p.total_amount = total_taxable + p.total_gst
    db.commit()
    db.refresh(p)
    return p


@router.get("/api/v1/proforma-invoices/{proforma_id}", response_model=dict)
async def get_proforma_invoice(
    proforma_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("proforma_read")),
):
    p = db.query(ProformaInvoice).filter(ProformaInvoice.id == proforma_id, ProformaInvoice.is_deleted == False).first()
    if not p:
        raise HTTPException(status_code=404, detail="Proforma Invoice not found")
    _enforce_owner(p, current_user)
    # Auto-expire on read
    _auto_expire(p)
    db.commit()
    items = db.query(ProformaInvoiceItem).filter(ProformaInvoiceItem.proforma_invoice_id == proforma_id).all()
    return {
        "proforma_invoice": ProformaInvoiceResponse.model_validate(p).model_dump(mode="json"),
        "items": [jsonable_encoder(item) for item in items],
    }


@router.put("/api/v1/proforma-invoices/{proforma_id}", response_model=ProformaInvoiceResponse)
async def update_proforma_invoice(
    proforma_id: UUID,
    payload: ProformaInvoiceCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("proforma_write")),
):
    p = db.query(ProformaInvoice).filter(ProformaInvoice.id == proforma_id, ProformaInvoice.is_deleted == False).first()
    if not p:
        raise HTTPException(status_code=404, detail="Proforma Invoice not found")
    _enforce_owner(p, current_user)
    if p.status not in {"draft", "sent"}:
        raise HTTPException(status_code=400, detail="Proforma Invoice cannot be edited in current status")

    # Valid Until must be a future date
    if payload.valid_until and payload.valid_until <= date.today():
        raise HTTPException(status_code=400, detail="Valid Until date must be a future date")

    # Auto-detect GST mode
    customer = db.query(Customer).filter(Customer.id == payload.customer_id, Customer.is_deleted == False).first()
    if not customer:
        raise HTTPException(status_code=400, detail="Invalid customer")
    _enforce_owner(customer, current_user)

    tax_mode = determine_tax_mode(db, "customer", payload.customer_id)
    is_igst = tax_mode["is_igst"]
    gst_applicable = tax_mode["gst_applicable"]

    p.customer_id = payload.customer_id
    p.proforma_date = payload.proforma_date
    p.valid_until = payload.valid_until
    p.sold_to_customer_id = payload.sold_to_customer_id or payload.customer_id
    p.bill_to_customer_id = payload.bill_to_customer_id or payload.customer_id
    p.ship_to_customer_id = payload.ship_to_customer_id or payload.customer_id
    p.notes = payload.notes
    p.terms_conditions = payload.terms_conditions

    db.query(ProformaInvoiceItem).filter(ProformaInvoiceItem.proforma_invoice_id == proforma_id).delete()
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
        db.add(ProformaInvoiceItem(
            proforma_invoice_id=p.id,
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

    p.subtotal = subtotal
    p.total_discount = total_discount
    p.total_taxable_amount = total_taxable
    p.total_cgst = total_cgst
    p.total_sgst = total_sgst
    p.total_igst = total_igst
    p.total_gst = total_cgst + total_sgst + total_igst
    p.total_amount = total_taxable + p.total_gst
    db.commit()
    db.refresh(p)
    return p


@router.patch("/api/v1/proforma-invoices/{proforma_id}/status", response_model=ProformaInvoiceResponse)
async def proforma_invoice_status(
    proforma_id: UUID,
    payload: ProformaInvoiceStatusRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    p = db.query(ProformaInvoice).filter(ProformaInvoice.id == proforma_id, ProformaInvoice.is_deleted == False).first()
    if not p:
        raise HTTPException(status_code=404, detail="Proforma Invoice not found")
    _enforce_owner(p, current_user)

    allowed = {
        "draft": {"sent", "expired"},
        "sent": {"accepted", "rejected", "expired"},
        "accepted": {"converted"},
    }
    if payload.status not in allowed.get(p.status, set()):
        raise HTTPException(status_code=400, detail="Invalid status transition")

    p.status = payload.status
    db.commit()
    db.refresh(p)
    return p


@router.patch("/api/v1/proforma-invoices/{proforma_id}/archive", response_model=ProformaInvoiceResponse)
async def archive_proforma_invoice(
    proforma_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("proforma_write")),
):
    p = db.query(ProformaInvoice).filter(ProformaInvoice.id == proforma_id, ProformaInvoice.is_deleted == False).first()
    if not p:
        raise HTTPException(status_code=404, detail="Proforma Invoice not found")
    _enforce_owner(p, current_user)

    p.is_deleted = True
    p.deleted_at = datetime.utcnow()
    db.commit()
    db.refresh(p)
    return p


@router.patch("/api/v1/proforma-invoices/{proforma_id}/restore", response_model=ProformaInvoiceResponse)
async def restore_proforma_invoice(
    proforma_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("proforma_write")),
):
    p = db.query(ProformaInvoice).filter(ProformaInvoice.id == proforma_id, ProformaInvoice.is_deleted == True).first()
    if not p:
        raise HTTPException(status_code=404, detail="Archived Proforma Invoice not found")
    _enforce_owner(p, current_user)

    p.is_deleted = False
    p.deleted_at = None
    db.commit()
    db.refresh(p)
    return p


# ────────────────────────── Proforma Invoice PDF / Email ──────────────────────

@router.get("/api/v1/proforma-invoices/{proforma_id}/pdf")
async def download_proforma_invoice_pdf(
    proforma_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("proforma_read")),
):
    """Download Proforma Invoice as a professional PDF (same format as Quotation/Tax Invoice)."""
    from fastapi.responses import Response
    from app.services.pdf_service import generate_proforma_invoice_pdf

    p = db.query(ProformaInvoice).filter(ProformaInvoice.id == proforma_id, ProformaInvoice.is_deleted == False).first()
    if not p:
        raise HTTPException(status_code=404, detail="Proforma Invoice not found")
    _enforce_owner(p, current_user)

    pdf_bytes = generate_proforma_invoice_pdf(db, proforma_id)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename={p.proforma_number}.pdf"},
    )


@router.post("/api/v1/proforma-invoices/{proforma_id}/send-email")
async def send_proforma_invoice_email(
    proforma_id: UUID,
    payload: dict | None = Body(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("proforma_write")),
):
    from app.services.pdf_service import generate_proforma_invoice_pdf
    # Reuse the shared sales e-mail helper so delivery behaviour is identical.
    from app.routers.sales import _send_pdf_email

    p = db.query(ProformaInvoice).filter(ProformaInvoice.id == proforma_id, ProformaInvoice.is_deleted == False).first()
    if not p:
        raise HTTPException(status_code=404, detail="Proforma Invoice not found")
    _enforce_owner(p, current_user)

    recipient = (payload or {}).get("email") if payload else None
    if not recipient:
        customer = db.query(Customer).filter(Customer.id == p.customer_id, Customer.is_deleted == False).first()
        if customer:
            _enforce_owner(customer, current_user)
        recipient = customer.email if customer else None

    if not recipient:
        raise HTTPException(status_code=400, detail="Recipient email is required")

    pdf_bytes = generate_proforma_invoice_pdf(db, proforma_id)
    subject = f"Proforma Invoice {p.proforma_number}"
    body = f"Please find attached Proforma Invoice {p.proforma_number}."
    sent = _send_pdf_email(
        recipient=recipient,
        subject=subject,
        body=body,
        pdf_filename=f"{p.proforma_number}.pdf",
        pdf_bytes=pdf_bytes,
    )

    return {
        "message": sent["message"],
        "delivery": sent["delivery"],
        "proforma_number": p.proforma_number,
        "recipient": recipient,
        "outbox_file": sent.get("outbox_file"),
    }
