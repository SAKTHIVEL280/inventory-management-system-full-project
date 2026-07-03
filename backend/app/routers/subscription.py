"""Subscription / plan entitlements endpoint (Module M2).

Exposes the current tenant's plan, module entitlements, user limit and live
usage so the frontend (M6) can render locked-module indicators, upgrade CTAs,
the active-plan banner and user-limit alerts. Read-only; tenant-scoped.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_current_company
from app.models.user import User
from app.models.company import Company
from app.services.plan_service import entitlements, plan_allows_role
from app.services.auth_service import ROLE_METADATA

router = APIRouter(prefix="/api/v1/subscription", tags=["subscription"])


@router.get("/me")
async def my_subscription(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
):
    """Return the calling tenant's plan entitlements and current usage."""
    data = entitlements(getattr(company, "subscription_plan", None))

    active_users = (
        db.query(User)
        .filter(User.company_id == company.id, User.is_deleted == False)
        .count()
    )

    # Role catalogue for the UI (colour-coded), with whether the current plan
    # permits assigning each. FREE offers Basic User; from SILVER onwards the Basic
    # role is replaced by Administrator (Admin). Availability follows PLAN_ROLES.
    plan = getattr(company, "subscription_plan", None)
    assignable_roles = ["admin", "accounts", "inventory", "management", "hr", "basic"]
    roles_catalog = [
        {
            "role": r,
            "color": ROLE_METADATA.get(r, {}).get("color"),
            "label": ROLE_METADATA.get(r, {}).get("label"),
            "available": plan_allows_role(plan, r),
        }
        for r in assignable_roles
    ]

    return {
        **data,
        "roles_catalog": roles_catalog,
        "company_id": str(company.id),
        "company_name": company.name,
        "account_status": getattr(company, "account_status", None),
        "payment_status": getattr(company, "payment_status", None),
        "subscription_start_date": getattr(company, "subscription_start_date", None),
        "subscription_expiry_date": getattr(company, "subscription_expiry_date", None),
        "active_user_count": active_users,
    }
