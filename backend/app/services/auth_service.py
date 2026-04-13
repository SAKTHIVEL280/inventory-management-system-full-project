"""Authentication service."""
import bcrypt
from sqlalchemy.orm import Session
from app.models.user import User
from app.schemas.auth import UserResponse
from typing import Optional, List, Dict, Any

# Define role defaults - which modules each role has access to
ROLE_DEFAULTS = {
    "admin": [
        "company_read", "company_write",
        "users_read", "users_write",
        "customers_read", "customers_write",
        "suppliers_read", "suppliers_write",
        "products_read", "products_write",
        "categories_read", "categories_write",
        "uom_read", "uom_write",
        "purchase_orders_read", "purchase_orders_write",
        "grn_read", "grn_write",
        "purchase_returns_read", "purchase_returns_write",
        "stock_ledger_read", "stock_ledger_write",
        "stock_adjustment_read", "stock_adjustment_write",
        "quotations_read", "quotations_write",
        "sales_orders_read", "sales_orders_write",
        "sales_invoices_read", "sales_invoices_write",
        "sales_returns_read", "sales_returns_write",
        "receipts_read", "receipts_write",
        "payments_read", "payments_write",
        "reports_read", "dashboard_read",
    ],
    "accounting": [
        "company_read",
        "customers_read",
        "suppliers_read",
        "products_read",
        "purchase_orders_read",
        "grn_read",
        "purchase_returns_read",
        "stock_ledger_read",
        "quotations_read",
        "sales_orders_read",
        "sales_invoices_read",
        "sales_returns_read",
        "receipts_read", "receipts_write",
        "payments_read", "payments_write",
        "reports_read", "dashboard_read",
    ],
    "sales": [
        "customers_read", "customers_write",
        "products_read",
        "quotations_read", "quotations_write",
        "sales_orders_read", "sales_orders_write",
        "sales_invoices_read", "sales_invoices_write",
        "sales_returns_read", "sales_returns_write",
        "stock_ledger_read",
        "reports_read", "dashboard_read",
    ],
    "inventory": [
        "customers_read",
        "suppliers_read", "suppliers_write",
        "products_read", "products_write",
        "categories_read", "categories_write",
        "uom_read", "uom_write",
        "purchase_orders_read", "purchase_orders_write",
        "grn_read", "grn_write",
        "purchase_returns_read", "purchase_returns_write",
        "stock_ledger_read", "stock_ledger_write",
        "stock_adjustment_read", "stock_adjustment_write",
        "sales_orders_read",
        "stock_ledger_read",
        "reports_read", "dashboard_read",
    ],
}


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password."""
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


def calculate_effective_access(
    role: str,
    permission_overrides: Optional[Dict[str, Any]] = None,
) -> List[str]:
    """
    Calculate effective access for a user.
    
    Effective access = role defaults + allowed overrides - denied overrides.
    Overrides cannot grant access to admin-only modules unless user role is admin.
    """
    base_permissions = set(ROLE_DEFAULTS.get(role, []))
    
    if not permission_overrides:
        return sorted(list(base_permissions))
    
    # Support both documented keys (allow/deny) and legacy keys (allowed/denied).
    allowed = permission_overrides.get("allow", permission_overrides.get("allowed", []))
    denied = permission_overrides.get("deny", permission_overrides.get("denied", []))
    
    # Filter allowed: cannot grant admin-only modules unless user is admin
    admin_only_modules = {"company_write", "users_read", "users_write"}
    if role != "admin":
        allowed = [p for p in allowed if not any(ao in p for ao in admin_only_modules)]
    
    effective = base_permissions.union(set(allowed)) - set(denied)
    return sorted(list(effective))


def get_user_response(user: User) -> UserResponse:
    """Convert User model to UserResponse with effective access."""
    effective_access = calculate_effective_access(user.role, user.permission_overrides)
    return UserResponse(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        role=user.role,
        permission_overrides=user.permission_overrides,
        effective_access=effective_access,
        force_password_change=user.force_password_change,
    )


def authenticate_user(
    db: Session,
    email: str,
    password: str,
) -> Optional[User]:
    """Authenticate user by email and password with lockout protection.
    
    After 5 failed attempts, the account is locked for 30 minutes.
    Raises ValueError with specific messages for lockout scenarios.
    """
    from datetime import datetime, timedelta, timezone

    def _to_utc(dt: datetime) -> datetime:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    user = db.query(User).filter(
        User.email == email,
        User.is_active == True,
        User.is_deleted == False,
    ).first()
    
    if not user:
        return None

    # Check if account is locked
    now_utc = datetime.now(timezone.utc)
    locked_until_utc = _to_utc(user.locked_until) if user.locked_until else None

    if locked_until_utc and locked_until_utc > now_utc:
        remaining = (locked_until_utc - now_utc).total_seconds()
        remaining_minutes = int(remaining // 60) + 1
        raise ValueError(
            f"Account is locked due to too many failed login attempts. "
            f"Please try again in {remaining_minutes} minute(s)."
        )
    
    # If lock has expired, reset the counter
    if locked_until_utc and locked_until_utc <= now_utc:
        user.failed_login_attempts = 0
        user.locked_until = None
        db.commit()
    
    if not verify_password(password, user.hashed_password):
        # Increment failed attempts
        user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
        
        if user.failed_login_attempts >= 5:
            user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=30)
            db.commit()
            raise ValueError(
                "Account has been locked for 30 minutes due to 5 failed login attempts."
            )
        
        remaining_attempts = 5 - user.failed_login_attempts
        db.commit()
        raise ValueError(
            f"Invalid password. {remaining_attempts} attempt(s) remaining before account lockout."
        )
    
    # Successful login — reset counter
    if user.failed_login_attempts > 0 or user.locked_until is not None:
        user.failed_login_attempts = 0
        user.locked_until = None
        db.commit()
    
    return user

