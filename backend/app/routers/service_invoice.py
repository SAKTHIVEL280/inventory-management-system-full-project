"""Service Invoice module (Module M5, BRD §8).

GST-compliant service invoices, available to ALL plans (module-gated as
"service_invoice", which every plan includes). FREE tier is capped at 10 invoices
per calendar month. Tenant-scoped by company_id. Money is in paise (INTEGER),
consistent with the rest of the system.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

import re

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, extract
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_permissions, require_module
from app.models.user import User
from app.models.service_invoice import ServiceInvoice, ServiceInvoiceItem
from app.services.order_number_service import generate_service_invoice_number
from app.services.plan_service import free_invoice_cap, normalize_plan, PLAN_FREE
from app.services.audit_service import log_audit_event

try:
    from app.services.pdf_service import _amount_in_words
except Exception:  # pragma: no cover - amount-in-words is best-effort
    def _amount_in_words(paise: int, currency_code: str = "INR", numbering_system: str = "indian") -> str:
        return ""

router = APIRouter(
    prefix="/api/v1/service-invoices",
    tags=["service-invoices"],
    dependencies=[Depends(require_module("service_invoice"))],
)


# Validation per BRD §8.1 / §8.2.
_GSTIN_RE = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
# A valid Indian mobile number is 10 digits starting 6-9. Numbers starting with
# 0-5 (e.g. a leading 1) are invalid prefixes and rejected.
_CONTACT_RE = re.compile(r"^[6-9][0-9]{9}$")
_ALLOWED_GST_RATES = {0, 5, 12, 18, 28}


# ───────────────────────────── Schemas ──────────────────────────────────────
class ServiceInvoiceItemIn(BaseModel):
    item_name: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None
    hsn_sac_code: str = Field(min_length=1, max_length=20)  # §8.2 mandatory per line
    quantity: Decimal = Field(default=Decimal(1), gt=0)
    basic_price: int = Field(ge=0)  # paise
    discount_percent: Decimal = Field(default=Decimal(0), ge=0, le=100)
    is_free: bool = False
    gst_rate: int = Field(default=18)

    @field_validator("gst_rate")
    @classmethod
    def _check_gst_rate(cls, v: int) -> int:
        if v not in _ALLOWED_GST_RATES:
            raise ValueError("GST rate must be one of 0, 5, 12, 18, 28.")
        return v


class ServiceInvoiceIn(BaseModel):
    invoice_date: date
    due_date: Optional[date] = None
    customer_name: str = Field(min_length=1, max_length=255)
    customer_gstin: Optional[str] = Field(default=None, max_length=15)
    customer_email: str = Field(min_length=1)  # §8.1 Required
    customer_contact: str = Field(min_length=1)  # §8.1 Required
    billing_address: str = Field(min_length=1)  # §8.1 Required
    customer_state_code: Optional[str] = None
    supply_type: str = Field(default="intra")  # intra | inter
    notes: Optional[str] = None
    items: List[ServiceInvoiceItemIn] = Field(min_length=1)

    @field_validator("customer_gstin")
    @classmethod
    def _check_gstin(cls, v: Optional[str]) -> Optional[str]:
        # GSTIN is optional (unregistered/B2C customers have none) but, when given,
        # must be a valid 15-character GST number (§8.1 "format validated").
        if v is None:
            return None
        v = v.strip().upper()
        if not v:
            return None
        if not _GSTIN_RE.match(v):
            raise ValueError("Customer GSTIN must be a valid 15-character GST number.")
        return v

    @field_validator("customer_email")
    @classmethod
    def _check_email(cls, v: str) -> str:
        v = (v or "").strip()
        if not _EMAIL_RE.match(v):
            raise ValueError("Customer email must be a valid email address.")
        return v

    @field_validator("customer_contact")
    @classmethod
    def _check_contact(cls, v: str) -> str:
        raw = (v or "").strip()
        # Normalise: drop spaces/dashes/parentheses and a leading +91 / 91 / 0 so
        # numbers entered with a country code still validate on the 10-digit core.
        digits = re.sub(r"[\s\-()]", "", raw)
        if digits.startswith("+"):
            digits = digits[1:]
        if len(digits) == 12 and digits.startswith("91"):
            digits = digits[2:]
        elif len(digits) == 11 and digits.startswith("0"):
            digits = digits[1:]
        if not _CONTACT_RE.match(digits):
            raise ValueError(
                "Customer contact must be a valid 10-digit mobile number starting with 6-9 "
                "(numbers starting with 0-5 are not allowed)."
            )
        return digits


class CancelRequest(BaseModel):
    reason: str = Field(min_length=1)


# ───────────────────────────── GST calculation ──────────────────────────────
def _round(x: Decimal | float) -> int:
    return int(Decimal(x).to_integral_value(rounding="ROUND_HALF_UP"))


def _compute(items: List[ServiceInvoiceItemIn], supply_type: str) -> tuple[list[dict], dict]:
    intra = (supply_type or "intra").strip().lower() != "inter"
    computed: list[dict] = []
    tot = {k: 0 for k in (
        "subtotal", "total_discount", "total_taxable_amount",
        "total_cgst", "total_sgst", "total_igst", "total_gst", "grand_total",
    )}
    for idx, it in enumerate(items, start=1):
        if it.is_free:
            row = {
                "sr_no": idx, "item_name": it.item_name, "description": it.description,
                "hsn_sac_code": it.hsn_sac_code, "quantity": it.quantity,
                "basic_price": it.basic_price, "discount_percent": Decimal(0),
                "discount_amount": 0, "is_free": True, "taxable_amount": 0,
                "gst_rate": it.gst_rate, "cgst_amount": 0, "sgst_amount": 0,
                "igst_amount": 0, "total_amount": 0,
            }
            computed.append(row)
            continue

        line_base = _round(Decimal(it.basic_price) * Decimal(it.quantity))
        discount_amount = _round(Decimal(line_base) * Decimal(it.discount_percent) / Decimal(100))
        taxable = line_base - discount_amount
        cgst = sgst = igst = 0
        if intra:
            cgst = _round(Decimal(taxable) * Decimal(it.gst_rate) / Decimal(200))
            sgst = cgst
        else:
            igst = _round(Decimal(taxable) * Decimal(it.gst_rate) / Decimal(100))
        total = taxable + cgst + sgst + igst
        computed.append({
            "sr_no": idx, "item_name": it.item_name, "description": it.description,
            "hsn_sac_code": it.hsn_sac_code, "quantity": it.quantity,
            "basic_price": it.basic_price, "discount_percent": it.discount_percent,
            "discount_amount": discount_amount, "is_free": False, "taxable_amount": taxable,
            "gst_rate": it.gst_rate, "cgst_amount": cgst, "sgst_amount": sgst,
            "igst_amount": igst, "total_amount": total,
        })
        tot["subtotal"] += line_base
        tot["total_discount"] += discount_amount
        tot["total_taxable_amount"] += taxable
        tot["total_cgst"] += cgst
        tot["total_sgst"] += sgst
        tot["total_igst"] += igst

    tot["total_gst"] = tot["total_cgst"] + tot["total_sgst"] + tot["total_igst"]
    raw_grand = tot["total_taxable_amount"] + tot["total_gst"]
    # Round grand total to the nearest rupee (100 paise) per BRD §8.2.
    tot["grand_total"] = int(round(raw_grand / 100.0)) * 100
    return computed, tot


def _serialize(inv: ServiceInvoice) -> dict:
    return {
        "id": str(inv.id),
        "invoice_number": inv.invoice_number,
        "invoice_date": inv.invoice_date,
        "due_date": inv.due_date,
        "customer_name": inv.customer_name,
        "customer_gstin": inv.customer_gstin,
        "customer_email": inv.customer_email,
        "customer_contact": inv.customer_contact,
        "billing_address": inv.billing_address,
        "supply_type": inv.supply_type,
        "subtotal": inv.subtotal,
        "total_discount": inv.total_discount,
        "total_taxable_amount": inv.total_taxable_amount,
        "total_cgst": inv.total_cgst,
        "total_sgst": inv.total_sgst,
        "total_igst": inv.total_igst,
        "total_gst": inv.total_gst,
        "grand_total": inv.grand_total,
        "amount_in_words": inv.amount_in_words,
        "status": inv.status,
        "payment_status": inv.payment_status,
        "notes": inv.notes,
        "cancel_reason": inv.cancel_reason,
        "items": [
            {
                "sr_no": i.sr_no, "item_name": i.item_name, "description": i.description,
                "hsn_sac_code": i.hsn_sac_code, "quantity": float(i.quantity),
                "basic_price": i.basic_price, "discount_percent": float(i.discount_percent),
                "discount_amount": i.discount_amount, "is_free": i.is_free,
                "taxable_amount": i.taxable_amount, "gst_rate": i.gst_rate,
                "cgst_amount": i.cgst_amount, "sgst_amount": i.sgst_amount,
                "igst_amount": i.igst_amount, "total_amount": i.total_amount,
            }
            for i in sorted(inv.items, key=lambda x: x.sr_no)
        ],
    }


def _free_cap_usage(db: Session, company) -> dict:
    """Return FREE-plan monthly usage for the tenant (used by the UI banner)."""
    plan = normalize_plan(getattr(company, "subscription_plan", None))
    today = date.today()
    # DB-configured monthly cap for the plan (None = unlimited). Capped only when set.
    cap = free_invoice_cap(plan)
    count = (
        db.query(func.count(ServiceInvoice.id))
        .filter(
            ServiceInvoice.company_id == company.id,
            ServiceInvoice.is_deleted == False,
            ServiceInvoice.is_platform_invoice == False,  # Mecandria's bills don't count
            ServiceInvoice.status != "cancelled",
            extract("year", ServiceInvoice.invoice_date) == today.year,
            extract("month", ServiceInvoice.invoice_date) == today.month,
        )
        .scalar()
    ) or 0
    capped = cap is not None
    return {
        "plan": plan,
        "capped": capped,
        "cap": cap if capped else None,
        "used_this_month": count,
        "remaining": (cap - count) if capped else None,
    }


# ───────────────────────────── Endpoints ────────────────────────────────────
@router.get("/cap-status")
async def cap_status(
    db: Session = Depends(get_db),
    company=Depends(require_module("service_invoice")),
    _: User = Depends(require_permissions("service_invoice_read")),
):
    return _free_cap_usage(db, company)


@router.get("")
async def list_service_invoices(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("service_invoice_read")),
    search: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    date_from: Optional[date] = Query(default=None),
    date_to: Optional[date] = Query(default=None),
):
    q = db.query(ServiceInvoice).filter(
        ServiceInvoice.company_id == current_user.company_id,
        ServiceInvoice.is_deleted == False,
        ServiceInvoice.is_platform_invoice == False,  # exclude Mecandria's bills to this tenant
    )
    if search:
        like = f"%{search.strip()}%"
        q = q.filter(
            (ServiceInvoice.invoice_number.ilike(like))
            | (ServiceInvoice.customer_name.ilike(like))
        )
    if status:
        q = q.filter(ServiceInvoice.status == status.strip().lower())
    if date_from:
        q = q.filter(ServiceInvoice.invoice_date >= date_from)
    if date_to:
        q = q.filter(ServiceInvoice.invoice_date <= date_to)
    rows = q.order_by(ServiceInvoice.created_at.desc()).all()
    return {"service_invoices": [_serialize(r) for r in rows], "count": len(rows)}


@router.post("", status_code=201)
async def create_service_invoice(
    payload: ServiceInvoiceIn,
    request: Request,
    db: Session = Depends(get_db),
    company=Depends(require_module("service_invoice")),
    current_user: User = Depends(require_permissions("service_invoice_write")),
):
    # FREE plan monthly cap (BRD §5.1 / §8).
    usage = _free_cap_usage(db, company)
    if usage["capped"] and usage["used_this_month"] >= usage["cap"]:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Your FREE plan allows {usage['cap']} service invoices per month and "
                f"you have reached the limit. Please upgrade to create more."
            ),
        )

    computed, tot = _compute(payload.items, payload.supply_type)
    inv = ServiceInvoice(
        invoice_number=generate_service_invoice_number(db, current_user.company_id),
        invoice_date=payload.invoice_date,
        due_date=payload.due_date,
        customer_name=payload.customer_name,
        customer_gstin=payload.customer_gstin,
        customer_email=payload.customer_email,
        customer_contact=payload.customer_contact,
        billing_address=payload.billing_address,
        customer_state_code=payload.customer_state_code,
        supply_type="inter" if (payload.supply_type or "").strip().lower() == "inter" else "intra",
        notes=payload.notes,
        status="draft",
        payment_status="unpaid",
        company_id=current_user.company_id,
        created_by=current_user.id,
        **{k: tot[k] for k in tot},
    )
    inv.amount_in_words = _amount_in_words(tot["grand_total"])
    for row in computed:
        inv.items.append(ServiceInvoiceItem(**row))
    db.add(inv)
    db.commit()
    db.refresh(inv)

    log_audit_event(
        db, action="CREATE_SERVICE_INVOICE", resource_type="service_invoice",
        status="success", user_id=current_user.id, resource_id=inv.id,
        company_id=current_user.company_id, details={"number": inv.invoice_number},
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    return _serialize(inv)


def _get_owned(db: Session, current_user: User, invoice_id: UUID) -> ServiceInvoice:
    inv = (
        db.query(ServiceInvoice)
        .filter(
            ServiceInvoice.id == invoice_id,
            ServiceInvoice.company_id == current_user.company_id,
            ServiceInvoice.is_deleted == False,
        )
        .first()
    )
    if not inv:
        raise HTTPException(status_code=404, detail="Service invoice not found.")
    return inv


@router.get("/{invoice_id}")
async def get_service_invoice(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("service_invoice_read")),
):
    return _serialize(_get_owned(db, current_user, invoice_id))


@router.get("/{invoice_id}/pdf")
async def download_service_invoice_pdf(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("service_invoice_read")),
):
    """Download a service invoice as a PDF (BRD §8.4). Available to all plans,
    including FREE (read access)."""
    from app.services.pdf_service import generate_service_invoice_pdf

    inv = _get_owned(db, current_user, invoice_id)  # tenant-scoped 404 if not owned
    pdf_bytes = generate_service_invoice_pdf(db, inv.id)
    safe = inv.invoice_number.replace("/", "-")
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{safe}.pdf"'},
    )


@router.put("/{invoice_id}")
async def update_service_invoice(
    invoice_id: UUID,
    payload: ServiceInvoiceIn,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("service_invoice_write")),
):
    inv = _get_owned(db, current_user, invoice_id)
    if inv.status != "draft":
        raise HTTPException(status_code=400, detail="Only draft service invoices can be edited.")

    computed, tot = _compute(payload.items, payload.supply_type)
    inv.invoice_date = payload.invoice_date
    inv.due_date = payload.due_date
    inv.customer_name = payload.customer_name
    inv.customer_gstin = payload.customer_gstin
    inv.customer_email = payload.customer_email
    inv.customer_contact = payload.customer_contact
    inv.billing_address = payload.billing_address
    inv.customer_state_code = payload.customer_state_code
    inv.supply_type = "inter" if (payload.supply_type or "").strip().lower() == "inter" else "intra"
    inv.notes = payload.notes
    for k in tot:
        setattr(inv, k, tot[k])
    inv.amount_in_words = _amount_in_words(tot["grand_total"])
    inv.items.clear()
    db.flush()
    for row in computed:
        inv.items.append(ServiceInvoiceItem(**row))
    db.commit()
    db.refresh(inv)
    log_audit_event(
        db, action="UPDATE_SERVICE_INVOICE", resource_type="service_invoice",
        status="success", user_id=current_user.id, resource_id=inv.id,
        company_id=current_user.company_id, details={"number": inv.invoice_number},
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    return _serialize(inv)


@router.post("/{invoice_id}/issue")
async def issue_service_invoice(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("service_invoice_write")),
):
    inv = _get_owned(db, current_user, invoice_id)
    if inv.status != "draft":
        raise HTTPException(status_code=400, detail="Only draft service invoices can be issued.")
    inv.status = "issued"
    db.commit()
    db.refresh(inv)
    return _serialize(inv)


@router.post("/{invoice_id}/mark-paid")
async def mark_paid(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("service_invoice_write")),
):
    inv = _get_owned(db, current_user, invoice_id)
    if inv.status == "cancelled":
        raise HTTPException(status_code=400, detail="A cancelled service invoice cannot be marked paid.")
    inv.payment_status = "paid"
    inv.status = "paid"
    db.commit()
    db.refresh(inv)
    return _serialize(inv)


@router.post("/{invoice_id}/cancel")
async def cancel_service_invoice(
    invoice_id: UUID,
    payload: CancelRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("service_invoice_write")),
):
    inv = _get_owned(db, current_user, invoice_id)
    if inv.status == "cancelled":
        raise HTTPException(status_code=400, detail="This service invoice is already cancelled.")
    inv.status = "cancelled"
    inv.cancel_reason = payload.reason
    db.commit()
    db.refresh(inv)
    log_audit_event(
        db, action="CANCEL_SERVICE_INVOICE", resource_type="service_invoice",
        status="success", user_id=current_user.id, resource_id=inv.id,
        company_id=current_user.company_id, details={"reason": payload.reason},
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    return _serialize(inv)


@router.delete("/{invoice_id}")
async def delete_service_invoice(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("service_invoice_write")),
):
    inv = _get_owned(db, current_user, invoice_id)
    if inv.status not in ("draft", "cancelled"):
        raise HTTPException(
            status_code=400,
            detail="Only draft or cancelled service invoices can be deleted.",
        )
    inv.is_deleted = True
    inv.deleted_at = datetime.utcnow()
    db.commit()
    return {"detail": "Service invoice deleted."}
