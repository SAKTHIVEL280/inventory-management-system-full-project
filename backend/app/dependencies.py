"""FastAPI dependencies for auth and database."""
from datetime import date, datetime, timedelta
from typing import Optional
from uuid import UUID
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.services.auth_service import normalize_role

security = HTTPBearer(auto_error=False)

# Message shown (and returned to the frontend) when a paid subscription has lapsed.
SUBSCRIPTION_EXPIRED_DETAIL = (
    "Your subscription has expired. Please renew to restore access. Your data is "
    "safe and will be available immediately after renewal."
)


def is_subscription_expired(plan, expiry_date) -> bool:
    """True when a PAID plan's subscription has lapsed (date-based, live).

    Rules:
      * FREE never expires.
      * No expiry date configured (NULL) is treated as NOT expired — the tenant has
        no fixed term (e.g. the legacy tenant), so access is preserved until a
        Super Admin sets an expiry. This avoids locking out un-dated tenants.
      * Otherwise expired when expiry_date is strictly before today (access is
        allowed through the whole expiry day).
    """
    from app.services.plan_service import normalize_plan, PLAN_FREE

    if normalize_plan(plan) == PLAN_FREE:
        return False
    if expiry_date is None:
        return False
    return expiry_date < date.today()


def _enforce_active_subscription(company, current_user: User) -> None:
    """Block tenant access when the subscription has expired (data is untouched).

    Impersonated Super Admin sessions (support/renewal) bypass this so the platform
    team can still reach the tenant. Raises 403 with an `X-Subscription-Status:
    expired` header the frontend can detect.
    """
    if getattr(current_user, "is_impersonated", False):
        return
    plan = getattr(company, "subscription_plan", None)
    expiry = getattr(company, "subscription_expiry_date", None)
    if is_subscription_expired(plan, expiry):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=SUBSCRIPTION_EXPIRED_DETAIL,
            headers={"X-Subscription-Status": "expired"},
        )


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """Extract and validate JWT token from bearer header or cookie."""
    token = credentials.credentials if credentials else request.cookies.get("access_token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    user = db.query(User).filter(
        User.id == user_id,
        User.is_active == True,
        User.is_deleted == False,
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    # Mark impersonated Super Admin support sessions (token carries `impersonated_by`)
    # so subscription-expiry gates can let the platform team through to the tenant.
    # Transient, non-persisted attribute — never a DB column.
    user.is_impersonated = bool(payload.get("impersonated_by"))

    # Multi-tenant (M4): block access when the user's tenant is not active
    # (deactivated/suspended by a Super Admin). Super Admins (no tenant) skip this.
    if not getattr(user, "is_super_admin", False) and user.company_id is not None:
        from app.models.company import Company

        company = db.query(Company.account_status).filter(
            Company.id == user.company_id
        ).first()
        if company is not None and (company[0] or "active") not in ("active", "trial"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Your organisation's account is currently inactive or suspended. "
                    "Please contact your administrator."
                ),
            )

    return user


def require_super_admin(current_user: User = Depends(get_current_user)) -> User:
    """Dependency: allow only platform Super Admins (Mecandria internal team)."""
    if not getattr(current_user, "is_super_admin", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super Admin privileges are required for this action.",
        )
    return current_user


def require_tenant(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    """Dependency: require an active tenant context for tenant-scoped endpoints.

    Hard tenant-isolation boundary (BRD §10 Data Isolation, §4): a platform Super
    Admin has NO tenant of their own and must NOT read or write any single tenant's
    data through the tenant APIs — they operate only via the Super Admin portal, or
    by explicitly impersonating a tenant admin (which issues a token whose subject
    IS that tenant's admin, so this guard then passes naturally).

    Blocking here also closes the latent cross-tenant leak in endpoints that filter
    with a soft `if company_id:` guard: without a tenant those filters were skipped,
    returning every tenant's rows merged. Requiring a tenant guarantees the filter
    always applies.

    Also enforces subscription expiry: an expired PAID plan is blocked here (data is
    preserved and untouched) so no tenant data endpoint is reachable past expiry.
    """
    if getattr(current_user, "is_super_admin", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Super Admins cannot access tenant data directly. Use 'Login As' "
                "to impersonate a tenant for support."
            ),
        )
    if current_user.company_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not associated with any company",
        )

    from app.models.company import Company
    sub = db.query(
        Company.subscription_plan, Company.subscription_expiry_date
    ).filter(Company.id == current_user.company_id).first()
    if sub is not None:
        _enforce_active_subscription(
            type("_Sub", (), {"subscription_plan": sub[0], "subscription_expiry_date": sub[1]})(),
            current_user,
        )
    return current_user


def require_role(*roles: str):
    """Dependency to enforce specific roles."""
    async def check_role(current_user: User = Depends(get_current_user)) -> User:
        current_role = normalize_role(current_user.role)
        allowed_roles = {normalize_role(role) for role in roles}
        if current_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user
    return check_role


def require_permissions(*permissions: str):
    """Dependency to enforce effective permission scopes."""

    async def check_permissions(current_user: User = Depends(get_current_user)) -> User:
        from app.services.auth_service import calculate_effective_access

        effective_access = set(
            calculate_effective_access(current_user.role, current_user.permission_overrides)
        )
        if not any(permission in effective_access for permission in permissions):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user

    return check_permissions


def enforce_resource_ownership(
    record_owner_id: UUID | None,
    current_user: User,
    *,
    privileged_roles: tuple[str, ...] | None = None,
) -> None:
    """Block access to user-owned resources when requester is not privileged.

    Records created before ownership tracking may have a null owner and remain
    accessible to avoid breaking legacy data workflows.
    """
    from app.services.auth_service import PRIVILEGED_ROLES

    privileged = (
        {normalize_role(r) for r in privileged_roles}
        if privileged_roles is not None
        else PRIVILEGED_ROLES
    )
    if normalize_role(current_user.role) in privileged:
        return
    if record_owner_id is None:
        return
    if str(record_owner_id) != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions for this resource",
        )


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.access_token_expire_minutes
        )
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode, settings.secret_key, algorithm=settings.algorithm
    )
    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    """Create JWT refresh token (longer expiry)."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.refresh_token_expire_minutes)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode, settings.secret_key, algorithm=settings.algorithm
    )
    return encoded_jwt


async def get_current_company_id(
    current_user: User = Depends(get_current_user),
) -> UUID:
    """Extract and validate the company_id from the current user.

    Returns the user's company_id or raises 403 if the user is not
    associated with any company.
    """
    if current_user.company_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not associated with any company",
        )
    return current_user.company_id


def scope_query_to_company(query, model_cls, company_id: UUID):
    """Apply company_id filter to a SQLAlchemy query.

    Ensures tenant isolation by restricting results to the given company.
    Gracefully handles models that lack a company_id column (no-op).
    """
    company_col = getattr(model_cls, "company_id", None)
    if company_col is None:
        return query
    return query.filter(company_col == company_id)


def get_current_company(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Load the current user's tenant (company) row, or 403 if unassigned."""
    from app.models.company import Company

    if current_user.company_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not associated with any company",
        )
    company = db.query(Company).filter(Company.id == current_user.company_id).first()
    if company is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not associated with any company",
        )
    return company


def require_module(*modules: str):
    """Dependency: allow the request only if the tenant's plan includes a module.

    Tenant-level capability gate (distinct from the user-level `require_permissions`
    role gate). Passing several modules treats them as OR (any one grants access);
    used where a router serves a module group. Returns the company so endpoints can
    reuse it. The legacy/existing tenant is PLATINUM, so every gate passes — no
    behaviour change until non-PLATINUM tenants exist.
    """
    from app.services.plan_service import plan_allows_any_module, upgrade_message

    async def check_module(
        company=Depends(get_current_company),
        current_user: User = Depends(get_current_user),
    ):
        # Subscription expiry is enforced first: an expired paid plan blocks every
        # module (data preserved). Impersonated Super Admin sessions bypass it.
        _enforce_active_subscription(company, current_user)
        plan = getattr(company, "subscription_plan", None)
        if not plan_allows_any_module(plan, modules):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=upgrade_message(modules[0], plan),
            )
        return company

    return check_module

