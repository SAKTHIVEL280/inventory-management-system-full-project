"""Authentication service."""
import bcrypt
from sqlalchemy.orm import Session
from app.models.user import User
from app.models.company import Company
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
        "proforma_read", "proforma_write",
        "sales_orders_read", "sales_orders_write",
        "sales_invoices_read", "sales_invoices_write",
        "sales_returns_read", "sales_returns_write",
        "rdn_read", "rdn_write",
        "receipts_read", "receipts_write",
        "payments_read", "payments_write",
        "service_invoice_read", "service_invoice_write",
        "action_logs_read",
        "reports_read", "dashboard_read",
    ],
    # ── BRD role model (§6.2 module-access matrix). These map module
    #    access to the existing permission scopes. None of them get the
    #    admin-only scopes (company_*/users_*) — only the Tenant Admin ('admin')
    #    manages company settings and users. service_invoice_*/hr_* are
    #    placeholders for modules delivered in later modules (M5 / HR BRD).
    # Basic (Red): Service Invoice only.
    "basic": [
        "service_invoice_read", "service_invoice_write",
    ],
    # Accounts (Blue): Masters, Purchase, Sales, Accounts, Dashboard.
    "accounts": [
        "customers_read", "customers_write",
        "suppliers_read", "suppliers_write",
        "products_read", "products_write",
        "categories_read", "categories_write",
        "uom_read",
        "purchase_orders_read", "purchase_orders_write",
        "grn_read", "grn_write",
        "purchase_returns_read", "purchase_returns_write",
        "quotations_read", "quotations_write",
        "proforma_read", "proforma_write",
        "sales_orders_read", "sales_orders_write",
        "sales_invoices_read", "sales_invoices_write",
        "sales_returns_read", "sales_returns_write",
        "rdn_read", "rdn_write",
        "receipts_read", "receipts_write",
        "payments_read", "payments_write",
        "dashboard_read",
    ],
    # Inventory (Green): Masters, Purchase, Sales, Inventory.
    "inventory": [
        "customers_read", "customers_write",
        "suppliers_read", "suppliers_write",
        "products_read", "products_write",
        "categories_read", "categories_write",
        "uom_read", "uom_write",
        "purchase_orders_read", "purchase_orders_write",
        "grn_read", "grn_write",
        "purchase_returns_read", "purchase_returns_write",
        "quotations_read", "quotations_write",
        "proforma_read", "proforma_write",
        "sales_orders_read", "sales_orders_write",
        "sales_invoices_read", "sales_invoices_write",
        "sales_returns_read", "sales_returns_write",
        "rdn_read", "rdn_write",
        "stock_ledger_read", "stock_ledger_write",
        "stock_adjustment_read", "stock_adjustment_write",
    ],
    # Management (Violet): all operational modules + Reports + Audit Logs
    #    (+ Export/POS capabilities in PLATINUM). Excludes company/user admin.
    "management": [
        "customers_read", "customers_write",
        "suppliers_read", "suppliers_write",
        "products_read", "products_write",
        "categories_read", "categories_write",
        "uom_read", "uom_write",
        "purchase_orders_read", "purchase_orders_write",
        "grn_read", "grn_write",
        "purchase_returns_read", "purchase_returns_write",
        "quotations_read", "quotations_write",
        "proforma_read", "proforma_write",
        "sales_orders_read", "sales_orders_write",
        "sales_invoices_read", "sales_invoices_write",
        "sales_returns_read", "sales_returns_write",
        "rdn_read", "rdn_write",
        "receipts_read", "receipts_write",
        "payments_read", "payments_write",
        "stock_ledger_read", "stock_ledger_write",
        "stock_adjustment_read", "stock_adjustment_write",
        "reports_read", "dashboard_read",
        "action_logs_read",
    ],
    # HR (Brown): HR Module only (placeholder scopes; HR BRD pending).
    "hr": [
        "hr_read", "hr_write",
    ],
}


# Colour-coded role metadata for the UI (BRD §6.1). 'admin' is the Tenant Admin;
# the five end-user roles below are the only assignable roles (plan-gated).
ROLE_METADATA = {
    "admin": {"color": "admin", "label": "Administrator"},
    "basic": {"color": "red", "label": "Basic User"},
    "accounts": {"color": "blue", "label": "Accounts User"},
    "inventory": {"color": "green", "label": "Inventory User"},
    "management": {"color": "violet", "label": "Management User"},
    "hr": {"color": "brown", "label": "HR User"},
}

# The five BRD end-user roles plus the Tenant Admin (the complete valid role set).
VALID_ROLES = {"admin", "basic", "accounts", "inventory", "management", "hr"}

# Roles that may view ALL of their tenant's records (not just ones they created).
# Record-ownership scoping is dormant for every known role today — kept so isolation
# is enforced at the company_id level (the legacy roles behaved the same way).
PRIVILEGED_ROLES = {"admin", "basic", "accounts", "inventory", "management", "hr"}

# Normalisation only: legacy stored role values are mapped to their BRD replacement
# (General Manager → Accounts, Inventory Manager → Inventory) so any not-yet-migrated
# row or cached JWT still resolves correctly. These are NOT assignable roles.
ROLE_ALIASES = {
    "general manager": "accounts",
    "general_manager": "accounts",
    "inventory manager": "inventory",
    "inventory_manager": "inventory",
}


def normalize_role(role: str) -> str:
    """Collapse UI-facing role aliases to their canonical backend role."""
    token = (role or "").strip().lower()
    return ROLE_ALIASES.get(token, token)


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
    normalized_role = normalize_role(role)
    base_permissions = set(ROLE_DEFAULTS.get(normalized_role, []))
    
    if not permission_overrides:
        return sorted(list(base_permissions))
    
    # Support both documented keys (allow/deny) and legacy keys (allowed/denied).
    allowed = permission_overrides.get("allow", permission_overrides.get("allowed", []))
    denied = permission_overrides.get("deny", permission_overrides.get("denied", []))
    
    # Filter allowed: cannot grant admin-only modules unless user is admin
    admin_only_modules = {
        "company_read",
        "company_write",
        "users_read",
        "users_write",
        "action_logs_read",
    }
    if normalized_role != "admin":
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
        company_id=user.company_id,
        permission_overrides=user.permission_overrides,
        effective_access=effective_access,
        force_password_change=user.force_password_change,
        is_super_admin=bool(getattr(user, "is_super_admin", False)),
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

    # Ensure tenant assignment exists for legacy/seeded users
    if user.company_id is None:
        company = db.query(Company).order_by(Company.created_at.asc()).first()
        if company is not None:
            user.company_id = company.id
            db.commit()
    
    return user

