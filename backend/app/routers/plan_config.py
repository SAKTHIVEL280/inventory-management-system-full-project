"""Super Admin → Plan Configuration (platform-level).

DB-backed management of subscription plans (FREE / SILVER / GOLD / PLATINUM):
name, pricing, billing period, user limit, module access, feature access and
active/inactive status. Every endpoint requires `is_super_admin`.

Changes are persisted to `subscription_plans` and take effect IMMEDIATELY for all
tenants on the plan: after each write we invalidate the plan_service cache
(`refresh_plan_cache`), so `require_module`, user-limit checks, the entitlements
API and the tenant UI all reflect the new configuration on the next request.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_super_admin
from app.models.user import User
from app.models.subscription_plan import SubscriptionPlan
from app.services.audit_service import log_audit_event
from app.services import plan_service
from app.services.plan_service import (
    ALL_PLANS, ALL_MODULES, BILLING_PERIODS,
    MODULE_CATALOG, ROLE_PLAN_FAMILY,
    default_plan_configs, refresh_plan_cache, derive_features,
)

router = APIRouter(prefix="/api/v1/admin/plans", tags=["super-admin", "plan-config"])

# Assignable role families that may be toggled per plan ('admin' is always implied).
ASSIGNABLE_ROLES = ("admin", "accounts", "inventory", "management", "hr", "basic")


class PlanUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, max_length=80)
    price_paise: Optional[int] = Field(default=None, ge=0)
    billing_period: Optional[str] = None
    user_limit: Optional[int] = Field(default=None, ge=1, le=10000)
    modules: Optional[list[str]] = None
    roles: Optional[list[str]] = None
    free_invoice_cap: Optional[int] = Field(default=None, ge=0)
    is_active: Optional[bool] = None

    @field_validator("billing_period")
    @classmethod
    def _v_billing(cls, v):
        if v is None:
            return v
        v = v.strip().lower()
        if v not in BILLING_PERIODS:
            raise ValueError(f"billing_period must be one of: {', '.join(BILLING_PERIODS)}.")
        return v

    @field_validator("name")
    @classmethod
    def _v_name(cls, v):
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("Plan name cannot be empty.")
        return v

    @field_validator("modules")
    @classmethod
    def _v_modules(cls, v):
        if v is None:
            return v
        invalid = [m for m in v if m not in ALL_MODULES]
        if invalid:
            raise ValueError(f"Unknown module(s): {', '.join(invalid)}.")
        return sorted(set(v))

    @field_validator("roles")
    @classmethod
    def _v_roles(cls, v):
        if v is None:
            return v
        invalid = [r for r in v if r not in ROLE_PLAN_FAMILY]
        if invalid:
            raise ValueError(f"Unknown role(s): {', '.join(invalid)}.")
        return sorted(set(v))


def _ensure_seeded(db: Session) -> None:
    """Create any missing plan rows from the code defaults (idempotent)."""
    existing = {row[0] for row in db.query(SubscriptionPlan.plan_key).all()}
    created = False
    for cfg in default_plan_configs():
        if cfg["plan_key"] in existing:
            continue
        db.add(SubscriptionPlan(
            plan_key=cfg["plan_key"],
            name=cfg["name"],
            price_paise=cfg["price_paise"],
            billing_period=cfg["billing_period"],
            user_limit=cfg["user_limit"],
            modules=sorted(cfg["modules"]),
            features=sorted(cfg["features"]),
            roles=sorted(cfg["roles"]),
            free_invoice_cap=cfg["free_invoice_cap"],
            is_active=cfg["is_active"],
            sort_order=cfg["sort_order"],
        ))
        created = True
    if created:
        db.commit()
        refresh_plan_cache()


def _plan_to_dict(p: SubscriptionPlan) -> dict:
    return {
        "plan_key": p.plan_key,
        "name": p.name,
        "price_paise": int(p.price_paise or 0),
        "billing_period": p.billing_period,
        "user_limit": int(p.user_limit or 0),
        "modules": sorted(p.modules or []),
        # Features are auto-derived from the enabled modules (read-only display).
        "features": sorted(derive_features(p.modules or [])),
        "roles": sorted(p.roles or []),
        "free_invoice_cap": p.free_invoice_cap,
        "is_active": bool(p.is_active),
        "sort_order": int(p.sort_order or 0),
    }


@router.get("")
async def list_plans(
    db: Session = Depends(get_db),
    _: User = Depends(require_super_admin),
):
    """Return all plan configurations plus the module/feature/role catalogues."""
    _ensure_seeded(db)
    plans = (
        db.query(SubscriptionPlan)
        .order_by(SubscriptionPlan.sort_order.asc(), SubscriptionPlan.plan_key.asc())
        .all()
    )
    return {
        "plans": [_plan_to_dict(p) for p in plans],
        "module_catalog": MODULE_CATALOG,
        "role_catalog": list(ASSIGNABLE_ROLES),
        "billing_periods": list(BILLING_PERIODS),
    }


@router.put("/{plan_key}")
async def update_plan(
    plan_key: str,
    payload: PlanUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """Update a plan's configuration. Takes effect immediately for all tenants."""
    key = (plan_key or "").strip().upper()
    if key not in ALL_PLANS:
        raise HTTPException(status_code=400, detail=f"Invalid plan. Choose one of: {', '.join(ALL_PLANS)}.")

    _ensure_seeded(db)
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.plan_key == key).first()
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found.")

    data = payload.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=400, detail="No changes supplied.")

    # Capture before-state for the audit trail (only for fields being changed).
    before = _plan_to_dict(plan)
    changes: dict[str, dict] = {}

    field_cols = {
        "name": "name",
        "price_paise": "price_paise",
        "billing_period": "billing_period",
        "user_limit": "user_limit",
        "modules": "modules",
        "roles": "roles",
        "free_invoice_cap": "free_invoice_cap",
        "is_active": "is_active",
    }
    for field, col in field_cols.items():
        if field not in data:
            continue
        new_val = data[field]
        old_val = before.get(field)
        if old_val != new_val:
            changes[field] = {"from": old_val, "to": new_val}
            setattr(plan, col, new_val)

    if not changes:
        return {"plan": _plan_to_dict(plan), "message": "No effective changes."}

    db.commit()
    db.refresh(plan)

    # Invalidate the entitlement cache so the change is live for all tenants now.
    refresh_plan_cache()

    log_audit_event(
        db,
        action="plan_config_update",
        resource_type="subscription_plan",
        status="success",
        user_id=current_user.id,
        resource_id=plan.id,
        details={"plan": key, "changes": changes, "username": getattr(current_user, "email", None)},
        ip_address=getattr(getattr(request, "client", None), "host", None),
        force_persist=True,  # platform/config event (not a financial module)
    )
    db.commit()  # persist the audit row (get_db does not auto-commit)

    return {"plan": _plan_to_dict(plan), "message": f"{key} plan updated.", "changes": changes}
