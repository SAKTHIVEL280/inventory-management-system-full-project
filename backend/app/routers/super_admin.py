"""Super Admin portal (Module M4).

Platform-level administration for Mecandria's internal team. Every endpoint
requires `is_super_admin`. Super Admins are not bound to a tenant, so these
endpoints operate ACROSS tenants (the only place cross-tenant access is allowed,
per BRD §11). Covers tenant (ERP customer) lifecycle, plan management, the
platform dashboard, password reset, impersonation and CSV export (BRD §4).
"""
from __future__ import annotations

import csv
import io
import re
import secrets
from datetime import date, datetime, timedelta
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.dependencies import require_super_admin, create_access_token
from app.models.company import Company
from app.models.user import User
from app.models.sales import SalesInvoice
from app.models.purchase import PurchaseOrder
from app.models.service_invoice import ServiceInvoice, ServiceInvoiceItem
from app.models.platform_company import PlatformCompany
from app.services.auth_service import hash_password
from app.services.plan_service import (
    ALL_PLANS, normalize_plan, plan_user_limit, entitlements,
)
from app.services.audit_service import log_audit_event

router = APIRouter(prefix="/api/v1/admin", tags=["super-admin"])


# ── Validation helpers (BRD §4.2 / §8.1) ─────────────────────────────────────
# GSTIN: 2-digit state code + 10-char PAN + entity digit + 'Z' + checksum (15 chars).
_GSTIN_RE = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$")
_CONTACT_RE = re.compile(r"^[0-9]{10}$")
_ACCOUNT_STATUSES = ("active", "inactive", "suspended", "trial")
_PAYMENT_STATUSES = ("paid", "pending", "overdue")


def _norm_gstin(v: Optional[str]) -> Optional[str]:
    if v is None:
        return None
    v = v.strip().upper()
    if not v:
        return None
    if not _GSTIN_RE.match(v):
        raise ValueError("GSTIN must be a valid 15-character GST Registration Number.")
    return v


def _norm_contact(v: Optional[str]) -> Optional[str]:
    if v is None:
        return None
    v = v.strip()
    if not v:
        return None
    if not _CONTACT_RE.match(v):
        raise ValueError("Contact number must be a 10-digit number.")
    return v


# ───────────────────────────── Schemas ──────────────────────────────────────
class TenantCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    gstin: Optional[str] = Field(default=None, max_length=15)
    contact_person_name: Optional[str] = None
    contact_number: Optional[str] = None
    email: Optional[EmailStr] = None
    business_category: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    pincode: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    subscription_plan: str = "FREE"
    account_status: str = "active"
    payment_status: str = "paid"
    subscription_start_date: Optional[date] = None
    subscription_expiry_date: Optional[date] = None
    tenant_code: Optional[str] = None
    # Tenant admin (created with the tenant)
    admin_full_name: str = Field(min_length=1, max_length=150)
    admin_email: EmailStr
    admin_password: Optional[str] = None  # auto-generated if omitted

    _v_gstin = field_validator("gstin")(lambda cls, v: _norm_gstin(v))
    _v_contact = field_validator("contact_number")(lambda cls, v: _norm_contact(v))


class TenantUpdateRequest(BaseModel):
    name: Optional[str] = None
    gstin: Optional[str] = None
    contact_person_name: Optional[str] = None
    contact_number: Optional[str] = None
    email: Optional[EmailStr] = None
    business_category: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    pincode: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    subscription_start_date: Optional[date] = None
    subscription_expiry_date: Optional[date] = None
    payment_status: Optional[str] = None
    tenant_code: Optional[str] = None

    _v_gstin = field_validator("gstin")(lambda cls, v: _norm_gstin(v))
    _v_contact = field_validator("contact_number")(lambda cls, v: _norm_contact(v))


class PlanChangeRequest(BaseModel):
    subscription_plan: str


class RenewRequest(BaseModel):
    subscription_start_date: Optional[date] = None
    subscription_expiry_date: date
    payment_status: Optional[str] = "paid"


class StatusChangeRequest(BaseModel):
    account_status: str  # active | inactive | suspended | trial


class ResetPasswordRequest(BaseModel):
    new_password: Optional[str] = None  # auto-generated if omitted


# ───────────────────────────── Helpers ──────────────────────────────────────
def _tenant_metrics(db: Session, company_id: UUID) -> dict:
    invoices = (
        db.query(func.count(SalesInvoice.id))
        .filter(SalesInvoice.company_id == company_id)
        .scalar()
    ) or 0
    pos = (
        db.query(func.count(PurchaseOrder.id))
        .filter(PurchaseOrder.company_id == company_id)
        .scalar()
    ) or 0
    users = (
        db.query(func.count(User.id))
        .filter(User.company_id == company_id, User.is_deleted == False)
        .scalar()
    ) or 0
    return {"total_sales_invoices": invoices, "total_purchase_orders": pos, "active_users": users}


def _compose_address(c: Company) -> str:
    parts = [
        getattr(c, "address_line1", None), getattr(c, "address_line2", None),
        c.city, c.state, getattr(c, "pincode", None), c.country,
    ]
    return ", ".join(p for p in parts if p)


def _tenant_to_dict(db: Session, c: Company, with_metrics: bool = True) -> dict:
    data = {
        "id": str(c.id),
        "name": c.name,
        "gstin": c.gstin,
        "contact_person_name": getattr(c, "contact_person_name", None),
        "contact_number": getattr(c, "contact_number", None),
        "email": c.email,
        "phone": getattr(c, "phone", None),
        "website": getattr(c, "website", None),
        "business_category": getattr(c, "business_category", None),
        "address_line1": getattr(c, "address_line1", None),
        "address_line2": getattr(c, "address_line2", None),
        "city": c.city,
        "state": c.state,
        "country": c.country,
        "pincode": getattr(c, "pincode", None),
        "business_address": _compose_address(c),
        "subscription_plan": normalize_plan(getattr(c, "subscription_plan", None)),
        "account_status": getattr(c, "account_status", None),
        "payment_status": getattr(c, "payment_status", None),
        "onboarding_date": getattr(c, "onboarding_date", None),
        "subscription_start_date": getattr(c, "subscription_start_date", None),
        "subscription_expiry_date": getattr(c, "subscription_expiry_date", None),
        "tenant_code": getattr(c, "tenant_code", None),
        "user_limit": plan_user_limit(getattr(c, "subscription_plan", None)),
    }
    if with_metrics:
        data.update(_tenant_metrics(db, c.id))
    return data


def _validate_account_status(value: str) -> str:
    v = (value or "").strip().lower()
    if v not in _ACCOUNT_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Choose one of: {', '.join(_ACCOUNT_STATUSES)}.",
        )
    return v


def _validate_payment_status(value: str) -> str:
    v = (value or "").strip().lower()
    if v not in _PAYMENT_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid payment status. Choose one of: {', '.join(_PAYMENT_STATUSES)}.",
        )
    return v


def _get_tenant_or_404(db: Session, tenant_id: UUID) -> Company:
    c = db.query(Company).filter(Company.id == tenant_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="ERP customer (tenant) not found.")
    return c


def _generate_tenant_code(db: Session) -> str:
    """Next available sequential tenant code (e.g. TEN-0001), skipping any taken."""
    existing = {
        c[0] for c in db.query(Company.tenant_code).filter(Company.tenant_code.isnot(None)).all()
    }
    n = db.query(func.count(Company.id)).scalar() or 0
    while True:
        n += 1
        code = f"TEN-{n:04d}"
        if code not in existing:
            return code


def _validate_plan(plan: str) -> str:
    p = (plan or "").strip().upper()
    if p not in ALL_PLANS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid plan. Choose one of: {', '.join(ALL_PLANS)}.",
        )
    # A retired (inactive) plan cannot be assigned to a tenant (Plan Configuration).
    from app.services.plan_service import plan_is_active
    if not plan_is_active(p):
        raise HTTPException(
            status_code=400,
            detail=f"The {p} plan is currently inactive and cannot be assigned. "
                   f"Activate it in Plan Configuration first.",
        )
    return p


# ───────────────────────────── Dashboard ────────────────────────────────────
@router.get("/dashboard")
async def platform_dashboard(
    db: Session = Depends(get_db),
    _: User = Depends(require_super_admin),
):
    """Platform-wide metrics (BRD §4.1)."""
    today = date.today()
    soon = today + timedelta(days=30)

    total = db.query(func.count(Company.id)).scalar() or 0
    active = (
        db.query(func.count(Company.id))
        .filter(Company.account_status.in_(["active", "trial"]))
        .scalar()
    ) or 0
    plan_rows = (
        db.query(Company.subscription_plan, func.count(Company.id))
        .group_by(Company.subscription_plan)
        .all()
    )
    plan_distribution = {normalize_plan(p): n for p, n in plan_rows}
    expiring = (
        db.query(func.count(Company.id))
        .filter(
            Company.subscription_expiry_date.isnot(None),
            Company.subscription_expiry_date >= today,
            Company.subscription_expiry_date <= soon,
        )
        .scalar()
    ) or 0

    # Service-invoice metrics (BRD §4.1). Revenue is summed from non-cancelled
    # service invoices' grand_total (stored in paise) → rupees. MTD = this calendar
    # month, YTD = this calendar year, by invoice_date.
    month_start = today.replace(day=1)
    year_start = today.replace(month=1, day=1)
    # "Total Service Invoices Raised" / "Revenue from subscriptions" (§4.1) = the
    # platform (Mecandria → tenant) service invoices raised via §4.3, not tenants'
    # own customer invoices.
    total_service_invoices = (
        db.query(func.count(ServiceInvoice.id))
        .filter(
            ServiceInvoice.is_deleted == False,
            ServiceInvoice.is_platform_invoice == True,  # noqa: E712
            ServiceInvoice.status != "cancelled",
        )
        .scalar()
    ) or 0

    def _revenue_since(start: date) -> float:
        paise = (
            db.query(func.coalesce(func.sum(ServiceInvoice.grand_total), 0))
            .filter(
                ServiceInvoice.is_deleted == False,
                ServiceInvoice.is_platform_invoice == True,  # noqa: E712
                ServiceInvoice.status != "cancelled",
                ServiceInvoice.invoice_date >= start,
            )
            .scalar()
        ) or 0
        return round(paise / 100.0, 2)

    return {
        "total_erp_customers": total,
        "active_erp_customers": active,
        "inactive_erp_customers": total - active,
        "total_sales_invoices": db.query(func.count(SalesInvoice.id)).scalar() or 0,
        "total_purchase_orders": db.query(func.count(PurchaseOrder.id)).scalar() or 0,
        "total_service_invoices": total_service_invoices,
        "revenue_mtd": _revenue_since(month_start),
        "revenue_ytd": _revenue_since(year_start),
        "plan_distribution": plan_distribution,
        "expiring_subscriptions_30d": expiring,
    }


# ───────────────────────────── Tenant CRUD ──────────────────────────────────
@router.get("/tenants")
async def list_tenants(
    db: Session = Depends(get_db),
    _: User = Depends(require_super_admin),
    plan: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
):
    q = db.query(Company)
    if plan:
        q = q.filter(Company.subscription_plan == plan.strip().upper())
    if status:
        q = q.filter(Company.account_status == status.strip().lower())
    if search:
        like = f"%{search.strip()}%"
        q = q.filter((Company.name.ilike(like)) | (Company.gstin.ilike(like)))
    companies = q.order_by(Company.created_at.desc()).all()
    return {"tenants": [_tenant_to_dict(db, c) for c in companies], "count": len(companies)}


@router.post("/tenants", status_code=201)
async def create_tenant(
    payload: TenantCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    plan = _validate_plan(payload.subscription_plan)
    account_status = _validate_account_status(payload.account_status)
    payment_status = _validate_payment_status(payload.payment_status)

    # Field-specific uniqueness checks (clear messages instead of a generic DB error).
    if db.query(Company).filter(func.lower(Company.name) == payload.name.strip().lower()).first():
        raise HTTPException(status_code=400, detail="Company Name already exists.")
    if payload.gstin and db.query(Company).filter(Company.gstin == payload.gstin).first():
        raise HTTPException(status_code=400, detail="GSTIN already exists.")
    if db.query(User).filter(User.email == payload.admin_email, User.is_deleted == False).first():
        raise HTTPException(status_code=400, detail="Admin Email is already registered.")
    # Tenant Code: validate uniqueness ONLY when the user entered one; otherwise
    # auto-generate the next available sequential code.
    user_tenant_code = (payload.tenant_code or "").strip()
    if user_tenant_code:
        if db.query(Company).filter(Company.tenant_code == user_tenant_code).first():
            raise HTTPException(status_code=400, detail="Tenant Code already exists.")
        tenant_code_value = user_tenant_code
    else:
        tenant_code_value = _generate_tenant_code(db)
    if payload.contact_number and db.query(Company).filter(Company.contact_number == payload.contact_number).first():
        raise HTTPException(status_code=400, detail="Contact Number already exists.")

    company = Company(
        name=payload.name,
        gstin=payload.gstin,
        contact_person_name=payload.contact_person_name,
        contact_number=payload.contact_number,
        email=payload.email,
        phone=payload.phone,
        website=payload.website,
        business_category=payload.business_category,
        address_line1=payload.address_line1,
        address_line2=payload.address_line2,
        city=payload.city,
        state=payload.state,
        country=payload.country,
        pincode=payload.pincode,
        subscription_plan=plan,
        account_status=account_status,
        payment_status=payment_status,
        onboarding_date=date.today(),
        subscription_start_date=payload.subscription_start_date,
        # FREE plan has no subscription fee and never expires (BRD §5.1).
        subscription_expiry_date=None if plan == "FREE" else payload.subscription_expiry_date,
        tenant_code=tenant_code_value,
    )
    db.add(company)
    db.flush()  # get company.id

    generated_password = payload.admin_password or secrets.token_urlsafe(9)
    admin_user = User(
        full_name=payload.admin_full_name,
        email=payload.admin_email,
        hashed_password=hash_password(generated_password),
        role="admin",  # Tenant Admin
        is_active=True,
        force_password_change=True,
        company_id=company.id,
        created_by=current_user.id,
    )
    db.add(admin_user)
    db.commit()
    db.refresh(company)

    log_audit_event(
        db, action="SUPERADMIN_CREATE_TENANT", resource_type="company",
        status="success", user_id=current_user.id, resource_id=company.id,
        company_id=company.id, details={"name": company.name, "plan": plan},
        ip_address=request.client.host if request.client else None,
    )
    db.commit()

    result = _tenant_to_dict(db, company)
    # Return the generated admin password ONCE so the Super Admin can share it.
    result["admin_email"] = payload.admin_email
    if not payload.admin_password:
        result["admin_temporary_password"] = generated_password
    return result


@router.get("/tenants/export")
async def export_tenants(
    db: Session = Depends(get_db),
    _: User = Depends(require_super_admin),
):
    """Export the ERP customer list as CSV (BRD §4.3)."""
    companies = db.query(Company).order_by(Company.created_at.desc()).all()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "Name", "GSTIN", "Business Category", "Plan", "Status", "Payment",
        "Contact Person", "Contact Number", "Email", "Business Address",
        "Onboarded", "Start", "Expiry",
        "Sales Invoices", "Purchase Orders", "Active Users", "User Limit",
    ])
    for c in companies:
        m = _tenant_metrics(db, c.id)
        writer.writerow([
            c.name, c.gstin or "", getattr(c, "business_category", "") or "",
            normalize_plan(getattr(c, "subscription_plan", None)),
            getattr(c, "account_status", ""), getattr(c, "payment_status", ""),
            getattr(c, "contact_person_name", "") or "", getattr(c, "contact_number", "") or "",
            c.email or "", _compose_address(c),
            getattr(c, "onboarding_date", "") or "",
            getattr(c, "subscription_start_date", "") or "",
            getattr(c, "subscription_expiry_date", "") or "",
            m["total_sales_invoices"], m["total_purchase_orders"], m["active_users"],
            plan_user_limit(getattr(c, "subscription_plan", None)),
        ])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=erp_customers.csv"},
    )


@router.get("/tenants/{tenant_id}")
async def get_tenant(
    tenant_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_super_admin),
):
    c = _get_tenant_or_404(db, tenant_id)
    data = _tenant_to_dict(db, c)
    data["entitlements"] = entitlements(getattr(c, "subscription_plan", None))
    return data


@router.get("/tenants/{tenant_id}/audit-logs")
async def get_tenant_audit_trail(
    tenant_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_super_admin),
    user: Optional[str] = Query(default=None, description="Search by acting user name/email"),
    date_from: Optional[date] = Query(default=None),
    date_to: Optional[date] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
):
    """View a specific ERP customer's activity log (BRD §4.3 'View Audit Trail').

    Supports search by user, a date range, and server-side pagination. Cross-tenant
    read is permitted only here, at the Super Admin level (BRD §11), scoped strictly
    to the requested tenant's company_id.
    """
    _get_tenant_or_404(db, tenant_id)

    where = ["a.company_id = :cid"]
    params: dict = {"cid": str(tenant_id)}
    if user and user.strip():
        where.append("(a.username ILIKE :u OR u.full_name ILIKE :u OR u.email ILIKE :u)")
        params["u"] = f"%{user.strip()}%"
    if date_from:
        where.append("a.created_at::date >= :df")
        params["df"] = date_from
    if date_to:
        where.append("a.created_at::date <= :dt")
        params["dt"] = date_to
    where_sql = " AND ".join(where)
    join_sql = "FROM audit_logs a LEFT JOIN users u ON u.id = a.user_id WHERE " + where_sql

    total = db.execute(text(f"SELECT COUNT(*) {join_sql}"), params).scalar() or 0
    params["lim"] = page_size
    params["off"] = (page - 1) * page_size
    rows = db.execute(
        text(
            "SELECT a.created_at, "
            "       COALESCE(NULLIF(TRIM(a.username), ''), u.full_name, u.email) AS actor, "
            "       a.action, a.action_type, a.module_name, a.description, a.status, a.ip_address "
            f"{join_sql} ORDER BY a.created_at DESC LIMIT :lim OFFSET :off"
        ),
        params,
    ).fetchall()
    return {
        "tenant_id": str(tenant_id),
        "total": total,
        "page": page,
        "page_size": page_size,
        "count": len(rows),
        "logs": [
            {
                "created_at": r[0], "username": r[1], "action": r[2], "action_type": r[3],
                "module": r[4], "description": r[5], "status": r[6], "ip_address": r[7],
            }
            for r in rows
        ],
    }


@router.put("/tenants/{tenant_id}")
async def update_tenant(
    tenant_id: UUID,
    payload: TenantUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    c = _get_tenant_or_404(db, tenant_id)
    # Field-specific uniqueness guards (only when the value changes).
    if payload.name and payload.name.strip().lower() != (c.name or "").strip().lower() and (
        db.query(Company).filter(func.lower(Company.name) == payload.name.strip().lower(), Company.id != c.id).first()
    ):
        raise HTTPException(status_code=400, detail="Company Name already exists.")
    if payload.gstin and payload.gstin != c.gstin and (
        db.query(Company).filter(Company.gstin == payload.gstin, Company.id != c.id).first()
    ):
        raise HTTPException(status_code=400, detail="GSTIN already exists.")
    if payload.tenant_code and payload.tenant_code != c.tenant_code and (
        db.query(Company).filter(Company.tenant_code == payload.tenant_code, Company.id != c.id).first()
    ):
        raise HTTPException(status_code=400, detail="Tenant Code already exists.")
    if payload.contact_number and payload.contact_number != c.contact_number and (
        db.query(Company).filter(Company.contact_number == payload.contact_number, Company.id != c.id).first()
    ):
        raise HTTPException(status_code=400, detail="Contact Number already exists.")
    if payload.payment_status is not None:
        c.payment_status = _validate_payment_status(payload.payment_status)
    for field in (
        "name", "gstin", "contact_person_name", "contact_number", "email",
        "phone", "website", "business_category",
        "address_line1", "address_line2", "city", "state", "country", "pincode",
        "subscription_start_date", "subscription_expiry_date", "tenant_code",
    ):
        val = getattr(payload, field)
        if val is not None:
            setattr(c, field, val)
    db.commit()
    db.refresh(c)
    log_audit_event(
        db, action="SUPERADMIN_UPDATE_TENANT", resource_type="company",
        status="success", user_id=current_user.id, resource_id=c.id, company_id=c.id,
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    return _tenant_to_dict(db, c)


@router.post("/tenants/{tenant_id}/plan")
async def change_plan(
    tenant_id: UUID,
    payload: PlanChangeRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    from app.services.plan_service import role_allowed_for_plan
    from app.services.auth_service import normalize_role

    c = _get_tenant_or_404(db, tenant_id)
    new_plan = _validate_plan(payload.subscription_plan)
    new_limit = plan_user_limit(new_plan)

    # Validate existing users against the new plan (BRD §5.6 / §11). On downgrade,
    # users whose role is not available in the new plan can no longer function, so
    # they are flagged for deactivation. The Tenant Admin is always retained.
    tenant_users = (
        db.query(User)
        .filter(User.company_id == c.id, User.is_deleted == False)
        .all()
    )
    deactivated_for_role: list[str] = []
    for u in tenant_users:
        if u.is_active and normalize_role(u.role) != "admin" and not role_allowed_for_plan(new_plan, u.role):
            u.is_active = False
            deactivated_for_role.append(u.email)

    # After role-based deactivation, enforce the plan's user-count limit.
    remaining_active = sum(
        1 for u in tenant_users if u.is_active and not u.is_deleted
    )
    if remaining_active > new_limit:
        db.rollback()  # undo deactivations — nothing changes until admin reduces users
        raise HTTPException(
            status_code=400,
            detail=(
                f"Cannot switch to {new_plan}: it allows {new_limit} user(s) but the "
                f"tenant would still have {remaining_active} active. Deactivate "
                f"{remaining_active - new_limit} more user(s) first."
            ),
        )

    old_plan = normalize_plan(getattr(c, "subscription_plan", None))
    c.subscription_plan = new_plan
    # FREE plan never expires; clear any inherited expiry date (BRD §5.1).
    if new_plan == "FREE":
        c.subscription_expiry_date = None
    db.commit()
    log_audit_event(
        db, action="SUPERADMIN_CHANGE_PLAN", resource_type="company",
        status="success", user_id=current_user.id, resource_id=c.id, company_id=c.id,
        details={"from": old_plan, "to": new_plan, "deactivated_for_role": deactivated_for_role},
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    result = _tenant_to_dict(db, c)
    result["deactivated_for_role"] = deactivated_for_role
    return result


@router.post("/tenants/{tenant_id}/renew")
async def renew_subscription(
    tenant_id: UUID,
    payload: RenewRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    c = _get_tenant_or_404(db, tenant_id)
    if payload.subscription_start_date:
        c.subscription_start_date = payload.subscription_start_date
    c.subscription_expiry_date = payload.subscription_expiry_date
    if payload.payment_status:
        c.payment_status = payload.payment_status.strip().lower()
    # Renewing reactivates a lapsed tenant.
    if getattr(c, "account_status", None) in ("inactive", "suspended"):
        c.account_status = "active"
    db.commit()
    log_audit_event(
        db, action="SUPERADMIN_RENEW", resource_type="company",
        status="success", user_id=current_user.id, resource_id=c.id, company_id=c.id,
        details={"expiry": str(payload.subscription_expiry_date)},
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    return _tenant_to_dict(db, c)


@router.post("/tenants/{tenant_id}/status")
async def change_status(
    tenant_id: UUID,
    payload: StatusChangeRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    c = _get_tenant_or_404(db, tenant_id)
    new_status = (payload.account_status or "").strip().lower()
    if new_status not in ("active", "inactive", "suspended", "trial"):
        raise HTTPException(
            status_code=400,
            detail="Status must be one of: active, inactive, suspended, trial.",
        )
    c.account_status = new_status
    db.commit()
    log_audit_event(
        db, action="SUPERADMIN_CHANGE_STATUS", resource_type="company",
        status="success", user_id=current_user.id, resource_id=c.id, company_id=c.id,
        details={"status": new_status},
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    return _tenant_to_dict(db, c)


@router.post("/tenants/{tenant_id}/reset-admin-password")
async def reset_admin_password(
    tenant_id: UUID,
    payload: ResetPasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    c = _get_tenant_or_404(db, tenant_id)
    admin_user = (
        db.query(User)
        .filter(User.company_id == c.id, User.role == "admin", User.is_deleted == False)
        .order_by(User.created_at.asc())
        .first()
    )
    if not admin_user:
        raise HTTPException(status_code=404, detail="This tenant has no admin user to reset.")

    new_password = payload.new_password or secrets.token_urlsafe(9)
    admin_user.hashed_password = hash_password(new_password)
    admin_user.force_password_change = True
    admin_user.failed_login_attempts = 0
    admin_user.locked_until = None
    db.commit()
    log_audit_event(
        db, action="SUPERADMIN_RESET_ADMIN_PASSWORD", resource_type="user",
        status="success", user_id=current_user.id, resource_id=admin_user.id, company_id=c.id,
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    result = {"admin_email": admin_user.email}
    if not payload.new_password:
        result["temporary_password"] = new_password
    return result


@router.post("/tenants/{tenant_id}/impersonate")
async def impersonate_tenant_admin(
    tenant_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """Issue an access token as the tenant's admin for support (BRD §4.3, audited)."""
    c = _get_tenant_or_404(db, tenant_id)
    admin_user = (
        db.query(User)
        .filter(User.company_id == c.id, User.role == "admin", User.is_deleted == False)
        .order_by(User.created_at.asc())
        .first()
    )
    if not admin_user:
        raise HTTPException(status_code=404, detail="This tenant has no admin user to impersonate.")

    token = create_access_token(
        data={
            "sub": str(admin_user.id),
            "company_id": str(admin_user.company_id) if admin_user.company_id else None,
            "impersonated_by": str(current_user.id),
        },
        expires_delta=timedelta(minutes=30),
    )
    log_audit_event(
        db, action="SUPERADMIN_IMPERSONATE", resource_type="user",
        status="success", user_id=current_user.id, resource_id=admin_user.id, company_id=c.id,
        details={"impersonated_email": admin_user.email},
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    return {"access_token": token, "token_type": "bearer", "impersonating": admin_user.email}


# ─────────────────── Raise Service Invoice (Mecandria → tenant) ───────────────
def _financial_year(d: date) -> str:
    """Indian FY label e.g. 2026-27 (Apr–Mar)."""
    start = d.year if d.month >= 4 else d.year - 1
    return f"{start}-{str(start + 1)[-2:]}"


def _next_platform_invoice_number(db: Session, d: date) -> str:
    """Sequential Mecandria invoice number: MEC/INV/XXX/YYYY-YY (BRD §8.1)."""
    fy = _financial_year(d)
    seq = (
        db.query(func.count(ServiceInvoice.id))
        .filter(ServiceInvoice.is_platform_invoice == True)  # noqa: E712
        .scalar()
    ) or 0
    return f"MEC/INV/{seq + 1:03d}/{fy}"


class RaiseServiceInvoiceRequest(BaseModel):
    invoice_date: Optional[date] = None
    due_date: Optional[date] = None
    supply_type: str = "intra"  # intra | inter
    notes: Optional[str] = None
    items: list  # validated below via ServiceInvoiceItemIn


@router.get("/tenants/{tenant_id}/service-invoices")
async def list_tenant_service_invoices(
    tenant_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_super_admin),
):
    """List the Mecandria (platform) service invoices raised TO this tenant (§4.3)."""
    from app.routers.service_invoice import _serialize

    _get_tenant_or_404(db, tenant_id)
    rows = (
        db.query(ServiceInvoice)
        .filter(
            ServiceInvoice.company_id == tenant_id,
            ServiceInvoice.is_platform_invoice == True,  # noqa: E712
            ServiceInvoice.is_deleted == False,
        )
        .order_by(ServiceInvoice.created_at.desc())
        .all()
    )
    return {"service_invoices": [_serialize(r) for r in rows], "count": len(rows)}


@router.post("/tenants/{tenant_id}/service-invoice", status_code=201)
async def raise_service_invoice(
    tenant_id: UUID,
    payload: RaiseServiceInvoiceRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """Raise a Mecandria subscription service invoice TO an ERP customer (BRD §4.3).

    Reuses the verified Service-Invoice GST engine. The invoice is stored against
    the tenant (company_id) but flagged is_platform_invoice so it stays out of the
    tenant's own invoice list / FREE cap and counts as platform revenue (§4.1).
    """
    from app.routers.service_invoice import _compute, ServiceInvoiceItemIn, _amount_in_words

    c = _get_tenant_or_404(db, tenant_id)
    if not payload.items:
        raise HTTPException(status_code=400, detail="At least one line item is required.")
    try:
        items = [ServiceInvoiceItemIn(**it) for it in payload.items]
    except Exception as exc:  # pydantic validation → 400
        raise HTTPException(status_code=400, detail=f"Invalid line item: {exc}")
    # §8.1: Description is required per line item.
    for idx, it in enumerate(items, start=1):
        if not (it.description or "").strip():
            raise HTTPException(status_code=400, detail=f"Line item {idx}: description is required.")

    inv_date = payload.invoice_date or date.today()
    # §8.2 state detection: intra if customer GSTIN state-code matches Mecandria's
    # registered state, else inter. Falls back to the provided supply_type when
    # either GSTIN/seller-state is unavailable.
    _platform = get_platform_company(db)
    seller_sc = (
        (getattr(_platform, "state_code", None) or (_platform.gstin or "")[:2] or "").strip()
    )
    cust_sc = (c.gstin or "").strip()[:2]
    if seller_sc and cust_sc:
        supply_type = "intra" if cust_sc == seller_sc else "inter"
    else:
        supply_type = "inter" if (payload.supply_type or "").strip().lower() == "inter" else "intra"
    computed, tot = _compute(items, supply_type)
    inv = ServiceInvoice(
        invoice_number=_next_platform_invoice_number(db, inv_date),
        invoice_date=inv_date,
        due_date=payload.due_date,
        customer_name=c.name,
        customer_gstin=c.gstin,
        customer_email=c.email,
        customer_contact=getattr(c, "contact_number", None),
        billing_address=_compose_address(c),
        customer_state_code=(c.gstin or "")[:2] or None,
        supply_type=supply_type,
        notes=payload.notes,
        status="issued",
        payment_status="unpaid",
        is_platform_invoice=True,
        company_id=c.id,
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
        db, action="SUPERADMIN_RAISE_SERVICE_INVOICE", resource_type="service_invoice",
        status="success", user_id=current_user.id, resource_id=inv.id, company_id=c.id,
        details={"invoice_number": inv.invoice_number, "grand_total": inv.grand_total},
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    from app.routers.service_invoice import _serialize
    return _serialize(inv)


# ───────── Platform service-invoice lifecycle (history / preview / PDF / etc.) ──
class CancelInvoiceRequest(BaseModel):
    reason: str = Field(min_length=1)


def _get_platform_invoice_or_404(db: Session, invoice_id: UUID) -> ServiceInvoice:
    inv = (
        db.query(ServiceInvoice)
        .filter(
            ServiceInvoice.id == invoice_id,
            ServiceInvoice.is_platform_invoice == True,  # noqa: E712
            ServiceInvoice.is_deleted == False,
        )
        .first()
    )
    if not inv:
        raise HTTPException(status_code=404, detail="Service invoice not found.")
    return inv


@router.get("/service-invoices")
async def list_all_service_invoices(
    db: Session = Depends(get_db),
    _: User = Depends(require_super_admin),
    tenant_id: Optional[UUID] = Query(default=None),
    status: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
):
    """Invoice History (§8.4): all Mecandria service invoices across ERP customers."""
    from app.routers.service_invoice import _serialize

    q = db.query(ServiceInvoice).filter(
        ServiceInvoice.is_platform_invoice == True,  # noqa: E712
        ServiceInvoice.is_deleted == False,
    )
    if tenant_id:
        q = q.filter(ServiceInvoice.company_id == tenant_id)
    if status:
        q = q.filter(ServiceInvoice.status == status.strip().lower())
    if search:
        like = f"%{search.strip()}%"
        q = q.filter(
            (ServiceInvoice.invoice_number.ilike(like)) | (ServiceInvoice.customer_name.ilike(like))
        )
    rows = q.order_by(ServiceInvoice.created_at.desc()).all()
    return {"service_invoices": [_serialize(r) for r in rows], "count": len(rows)}


@router.get("/service-invoices/{invoice_id}")
async def get_service_invoice(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_super_admin),
):
    """Preview (§8.4): full computed invoice for on-screen preview before download."""
    from app.routers.service_invoice import _serialize

    return _serialize(_get_platform_invoice_or_404(db, invoice_id))


@router.post("/service-invoices/{invoice_id}/mark-paid")
async def mark_service_invoice_paid(
    invoice_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """Mark as Paid (§8.4)."""
    inv = _get_platform_invoice_or_404(db, invoice_id)
    if inv.status == "cancelled":
        raise HTTPException(status_code=400, detail="A cancelled invoice cannot be marked paid.")
    inv.status = "paid"
    inv.payment_status = "paid"
    db.commit()
    log_audit_event(
        db, action="SUPERADMIN_SERVICE_INVOICE_PAID", resource_type="service_invoice",
        status="success", user_id=current_user.id, resource_id=inv.id, company_id=inv.company_id,
        details={"invoice_number": inv.invoice_number},
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    from app.routers.service_invoice import _serialize
    return _serialize(inv)


@router.post("/service-invoices/{invoice_id}/cancel")
async def cancel_service_invoice(
    invoice_id: UUID,
    payload: CancelInvoiceRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """Cancel Invoice with reason (§8.4) — creates a cancellation record."""
    inv = _get_platform_invoice_or_404(db, invoice_id)
    if inv.status == "paid":
        raise HTTPException(status_code=400, detail="A paid invoice cannot be cancelled.")
    inv.status = "cancelled"
    inv.cancel_reason = payload.reason.strip()
    db.commit()
    log_audit_event(
        db, action="SUPERADMIN_SERVICE_INVOICE_CANCEL", resource_type="service_invoice",
        status="success", user_id=current_user.id, resource_id=inv.id, company_id=inv.company_id,
        details={"invoice_number": inv.invoice_number, "reason": inv.cancel_reason},
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    from app.routers.service_invoice import _serialize
    return _serialize(inv)


@router.get("/service-invoices/{invoice_id}/pdf")
async def download_service_invoice_pdf(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_super_admin),
):
    """Download as PDF (§8.4)."""
    from app.services.pdf_service import generate_service_invoice_pdf

    inv = _get_platform_invoice_or_404(db, invoice_id)
    pdf_bytes = generate_service_invoice_pdf(db, inv.id)
    safe = inv.invoice_number.replace("/", "-")
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{safe}.pdf"'},
    )


@router.post("/service-invoices/{invoice_id}/email")
async def email_service_invoice(
    invoice_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """Email Invoice (§8.4): send the PDF to the customer's registered email."""
    from app.services.pdf_service import generate_service_invoice_pdf
    from app.services.email_service import send_pdf_email

    inv = _get_platform_invoice_or_404(db, invoice_id)
    recipient = (inv.customer_email or "").strip()
    if not recipient:
        raise HTTPException(status_code=400, detail="This customer has no email address on file.")
    pdf_bytes = generate_service_invoice_pdf(db, inv.id)
    safe = inv.invoice_number.replace("/", "-")
    seller_name = get_platform_company(db).name or "Mecandria"
    result = send_pdf_email(
        recipient=recipient,
        subject=f"Service Invoice {inv.invoice_number} from {seller_name}",
        body=(
            f"Dear {inv.customer_name},\n\nPlease find attached service invoice "
            f"{inv.invoice_number} for the amount of INR {inv.grand_total / 100:,.2f}.\n\n"
            f"Regards,\n{seller_name}"
        ),
        pdf_filename=f"{safe}.pdf",
        pdf_bytes=pdf_bytes,
    )
    log_audit_event(
        db, action="SUPERADMIN_SERVICE_INVOICE_EMAIL", resource_type="service_invoice",
        status="success", user_id=current_user.id, resource_id=inv.id, company_id=inv.company_id,
        details={"invoice_number": inv.invoice_number, "to": recipient, "delivery": result.get("delivery")},
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    return {"invoice_number": inv.invoice_number, "recipient": recipient, **result}


# ─────────────────── Platform (Mecandria) Company Profile (§ seller) ──────────
class PlatformCompanyUpdate(BaseModel):
    name: Optional[str] = None
    legal_name: Optional[str] = None
    gstin: Optional[str] = None
    gstin_status: Optional[str] = None
    pan: Optional[str] = None
    import_export_number: Optional[str] = None
    company_director_name: Optional[str] = None
    company_director_contact: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    state_code: Optional[str] = None
    pincode: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    bank_name: Optional[str] = None
    account_holder_name: Optional[str] = None
    bank_account_no: Optional[str] = None
    bank_ifsc: Optional[str] = None
    bank_branch: Optional[str] = None


def get_platform_company(db: Session) -> PlatformCompany:
    """Return the single platform seller profile row, creating it if missing."""
    row = db.query(PlatformCompany).order_by(PlatformCompany.created_at.asc()).first()
    if row is None:
        row = PlatformCompany(name="Mecandria")
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def _platform_to_dict(c: PlatformCompany) -> dict:
    from app.routers.company import _resolve_logo_file_path, _build_logo_data_url

    def _data_url(url):
        if not url:
            return None
        fp = _resolve_logo_file_path(url)
        return _build_logo_data_url(fp) if fp else None

    fields = [
        "name", "legal_name", "gstin", "gstin_status", "pan", "import_export_number",
        "company_director_name", "company_director_contact",
        "address_line1", "address_line2", "city", "state", "country", "state_code", "pincode",
        "phone", "email", "website",
        "bank_name", "account_holder_name", "bank_account_no", "bank_ifsc", "bank_branch",
    ]
    data = {f: getattr(c, f, None) for f in fields}
    data["id"] = str(c.id)
    data["logo_url"] = c.logo_url
    data["ambassador_logo_url"] = c.ambassador_logo_url
    data["logo_data_url"] = _data_url(c.logo_url)
    data["ambassador_logo_data_url"] = _data_url(c.ambassador_logo_url)
    return data


@router.get("/company")
async def get_company_profile(db: Session = Depends(get_db), _: User = Depends(require_super_admin)):
    """Platform (Mecandria) seller company profile."""
    return _platform_to_dict(get_platform_company(db))


@router.put("/company")
async def update_company_profile(
    payload: PlatformCompanyUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    c = get_platform_company(db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(c, field, value)
    db.commit()
    db.refresh(c)
    log_audit_event(
        db, action="SUPERADMIN_UPDATE_COMPANY_PROFILE", resource_type="platform_company",
        status="success", user_id=current_user.id, resource_id=c.id,
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    return _platform_to_dict(c)


@router.post("/company/logo")
async def upload_company_logo(
    logo: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: User = Depends(require_super_admin),
):
    from app.routers.company import _validate_upload_image, _save_company_static_image, _delete_previous_image

    content_type = logo.content_type or ""
    file_bytes = await logo.read()
    _validate_upload_image(content_type, file_bytes, label="Logo")
    c = get_platform_company(db)
    previous = c.logo_url
    c.logo_url = _save_company_static_image(base_name="platform_logo", content_type=content_type, file_bytes=file_bytes)
    db.commit()
    _delete_previous_image(previous)
    return {"logo_url": c.logo_url}


@router.post("/company/ambassador-logo")
async def upload_company_ambassador_logo(
    logo: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: User = Depends(require_super_admin),
):
    from app.routers.company import _validate_upload_image, _save_company_static_image, _delete_previous_image

    content_type = logo.content_type or ""
    file_bytes = await logo.read()
    _validate_upload_image(content_type, file_bytes, label="Ambassador logo")
    c = get_platform_company(db)
    previous = c.ambassador_logo_url
    c.ambassador_logo_url = _save_company_static_image(base_name="platform_ambassador_logo", content_type=content_type, file_bytes=file_bytes)
    db.commit()
    _delete_previous_image(previous)
    return {"ambassador_logo_url": c.ambassador_logo_url}


@router.delete("/company/ambassador-logo")
async def remove_company_ambassador_logo(
    db: Session = Depends(get_db),
    _: User = Depends(require_super_admin),
):
    from app.routers.company import _resolve_logo_file_path, _remove_if_exists

    c = get_platform_company(db)
    if c.ambassador_logo_url:
        fp = _resolve_logo_file_path(c.ambassador_logo_url)
        if fp:
            _remove_if_exists(fp)
    c.ambassador_logo_url = None
    db.commit()
    return {"message": "Ambassador logo removed."}
