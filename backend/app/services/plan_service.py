"""Subscription plan engine (Module M2 / Super Admin Plan Configuration).

Single source of truth for what each subscription tier (FREE / SILVER / GOLD /
PLATINUM) is entitled to: which ERP modules and features are accessible, the
maximum number of user accounts, the user roles that may be assigned, pricing,
billing period and active/inactive status.

Plan configuration is stored in the `subscription_plans` DB table (Super Admin →
Plan Configuration) and cached in-process here. The hardcoded matrix below is the
DEFAULT/SEED and a safety FALLBACK used only when a plan row is missing or the
table is unavailable (e.g. migration not yet run) — so the engine never hard-fails
and never silently locks a tenant out. Whenever a plan is saved, the Super Admin
router calls `refresh_plan_cache()` so changes take effect immediately for every
tenant on that plan.
"""
from __future__ import annotations

import threading
import time
from typing import Iterable

# ── Canonical module keys (lowercase) ────────────────────────────────────────
MODULE_SERVICE_INVOICE = "service_invoice"
MODULE_MASTERS = "masters"
MODULE_PURCHASE = "purchase"
MODULE_SALES = "sales"
MODULE_ACCOUNTS = "accounts"
MODULE_DASHBOARD = "dashboard"
MODULE_INVENTORY = "inventory"
MODULE_REPORTS = "reports"
MODULE_AUDIT_LOGS = "audit_logs"
MODULE_EXPORT = "export"
MODULE_POS = "pos"
MODULE_HR = "hr"

# Ordered catalogue (key + human label) for the Plan Configuration module matrix.
MODULE_CATALOG: list[dict[str, str]] = [
    {"key": MODULE_DASHBOARD, "label": "Dashboard"},
    {"key": MODULE_MASTERS, "label": "Masters"},
    {"key": MODULE_PURCHASE, "label": "Purchase"},
    {"key": MODULE_SALES, "label": "Sales"},
    {"key": MODULE_INVENTORY, "label": "Inventory"},
    {"key": MODULE_ACCOUNTS, "label": "Accounts"},
    {"key": MODULE_REPORTS, "label": "Reports"},
    {"key": MODULE_AUDIT_LOGS, "label": "Audit Logs"},
    {"key": MODULE_SERVICE_INVOICE, "label": "Service Invoice"},
    {"key": MODULE_EXPORT, "label": "Data Export"},
    {"key": MODULE_POS, "label": "Point of Sale"},
    {"key": MODULE_HR, "label": "HR"},
]
ALL_MODULES = tuple(m["key"] for m in MODULE_CATALOG)

# ── Canonical feature keys (cross-cutting capabilities) ──────────────────────
# Features are NO LONGER configured separately in Plan Configuration. Each feature
# is derived automatically from the plan's enabled MODULES via MODULE_FEATURE_MAP
# below — enabling a module implicitly grants its features. This keeps a single
# source of truth (modules) and prevents drift between a module and its features.
FEATURE_DATA_EXPORT = "data_export"
FEATURE_ADVANCED_REPORTS = "advanced_reports"
FEATURE_GST_FILING = "gst_filing"
FEATURE_EMAIL_INVOICES = "email_invoices"
FEATURE_AUDIT_TRAIL = "audit_trail"

# Which features each module unlocks. Only modules that actually back a working
# capability appear here (Bulk Import / Multi-Currency / API Access were removed —
# they had no implementation and no owning module).
MODULE_FEATURE_MAP: dict[str, set[str]] = {
    MODULE_SERVICE_INVOICE: {FEATURE_EMAIL_INVOICES},
    MODULE_SALES: {FEATURE_EMAIL_INVOICES},
    MODULE_REPORTS: {FEATURE_ADVANCED_REPORTS, FEATURE_GST_FILING},
    MODULE_EXPORT: {FEATURE_DATA_EXPORT},
    MODULE_AUDIT_LOGS: {FEATURE_AUDIT_TRAIL},
}
ALL_FEATURES = tuple(sorted({f for feats in MODULE_FEATURE_MAP.values() for f in feats}))


def derive_features(modules: Iterable[str]) -> set[str]:
    """Features implied by a set of enabled modules (auto, not configured)."""
    mods = set(modules)
    out: set[str] = set()
    for module, feats in MODULE_FEATURE_MAP.items():
        if module in mods:
            out |= feats
    return out

# ── Canonical plan keys ──────────────────────────────────────────────────────
PLAN_FREE = "FREE"
PLAN_SILVER = "SILVER"
PLAN_GOLD = "GOLD"
PLAN_PLATINUM = "PLATINUM"
ALL_PLANS = (PLAN_FREE, PLAN_SILVER, PLAN_GOLD, PLAN_PLATINUM)

BILLING_PERIODS = ("none", "monthly", "yearly")

# ── Module access per plan (BRD §5.5) — DEFAULT/FALLBACK ─────────────────────
_SILVER_MODULES = {
    MODULE_SERVICE_INVOICE, MODULE_MASTERS, MODULE_PURCHASE, MODULE_SALES,
    MODULE_ACCOUNTS, MODULE_DASHBOARD,
}
_GOLD_MODULES = _SILVER_MODULES | {
    MODULE_INVENTORY, MODULE_REPORTS, MODULE_AUDIT_LOGS,
}
_PLATINUM_MODULES = _GOLD_MODULES | {
    MODULE_EXPORT, MODULE_POS, MODULE_HR,
}

PLAN_MODULES: dict[str, set[str]] = {
    PLAN_FREE: {MODULE_SERVICE_INVOICE},
    PLAN_SILVER: set(_SILVER_MODULES),
    PLAN_GOLD: set(_GOLD_MODULES),
    PLAN_PLATINUM: set(_PLATINUM_MODULES),
}

# Feature access per plan is DERIVED from the plan's modules (see derive_features);
# it is no longer configured or stored separately.

# ── Maximum user accounts per plan (BRD §5.5) — DEFAULT/FALLBACK ─────────────
PLAN_USER_LIMITS: dict[str, int] = {
    PLAN_FREE: 1,
    PLAN_SILVER: 2,
    PLAN_GOLD: 4,
    PLAN_PLATINUM: 6,
}

# ── User roles available per plan (BRD §6, new role model) ───────────────────
ROLE_ADMIN = "admin"
ROLE_BASIC = "basic"
ROLE_ACCOUNTS = "accounts"
ROLE_INVENTORY = "inventory"
ROLE_MANAGEMENT = "management"
ROLE_HR = "hr"

# Assignable roles per plan. FREE offers only the Basic User; from SILVER onwards
# the Basic role is replaced by the Administrator (Admin) as an assignable role.
PLAN_ROLES: dict[str, set[str]] = {
    PLAN_FREE: {ROLE_BASIC},
    PLAN_SILVER: {ROLE_ADMIN, ROLE_ACCOUNTS},
    PLAN_GOLD: {ROLE_ADMIN, ROLE_ACCOUNTS, ROLE_INVENTORY, ROLE_MANAGEMENT},
    PLAN_PLATINUM: {ROLE_ADMIN, ROLE_ACCOUNTS, ROLE_INVENTORY, ROLE_MANAGEMENT, ROLE_HR},
}

# FREE tier: max service invoices per calendar month (BRD §5.1 / §8).
FREE_PLAN_INVOICE_CAP = 10

# Default display metadata (name / price paise / billing period) used to SEED the
# subscription_plans table and as fallback when a row is missing.
PLAN_DEFAULT_META: dict[str, dict] = {
    PLAN_FREE: {"name": "Free", "price_paise": 0, "billing_period": "none", "sort_order": 1},
    PLAN_SILVER: {"name": "Silver", "price_paise": 99900, "billing_period": "monthly", "sort_order": 2},
    PLAN_GOLD: {"name": "Gold", "price_paise": 199900, "billing_period": "monthly", "sort_order": 3},
    PLAN_PLATINUM: {"name": "Platinum", "price_paise": 499900, "billing_period": "monthly", "sort_order": 4},
}


def _fallback_config(plan_key: str) -> dict:
    """Code-level default entitlement snapshot for a known plan key."""
    p = plan_key if plan_key in PLAN_MODULES else PLAN_PLATINUM
    meta = PLAN_DEFAULT_META[p]
    return {
        "plan_key": p,
        "name": meta["name"],
        "price_paise": meta["price_paise"],
        "billing_period": meta["billing_period"],
        "user_limit": PLAN_USER_LIMITS[p],
        "modules": set(PLAN_MODULES[p]),
        "features": derive_features(PLAN_MODULES[p]),
        "roles": set(PLAN_ROLES[p]),
        "free_invoice_cap": FREE_PLAN_INVOICE_CAP if p == PLAN_FREE else None,
        "is_active": True,
        "sort_order": meta["sort_order"],
    }


def default_plan_configs() -> list[dict]:
    """The full default configuration for all plans (used to seed the DB)."""
    return [_fallback_config(p) for p in ALL_PLANS]


# ── In-process cache of DB plan configs ──────────────────────────────────────
_CACHE_TTL_SECONDS = 300
_cache_lock = threading.Lock()
_cache: dict[str, dict] | None = None
_cache_loaded_at: float = 0.0


def _load_configs_from_db() -> dict[str, dict]:
    """Read all plan rows from the DB. Returns {} on any failure (→ fallback)."""
    try:
        from app.database import SessionLocal
        from app.models.subscription_plan import SubscriptionPlan
    except Exception:
        return {}

    session = None
    try:
        session = SessionLocal()
        rows = session.query(SubscriptionPlan).all()
        out: dict[str, dict] = {}
        for r in rows:
            key = (r.plan_key or "").strip().upper()
            if not key:
                continue
            out[key] = {
                "plan_key": key,
                "name": r.name,
                "price_paise": int(r.price_paise or 0),
                "billing_period": r.billing_period or "monthly",
                "user_limit": int(r.user_limit or 0),
                "modules": set(r.modules or []),
                # Features are derived from the enabled modules, NOT the stored
                # features column (which is now ignored/legacy).
                "features": derive_features(r.modules or []),
                "roles": set(r.roles or []),
                "free_invoice_cap": r.free_invoice_cap,
                "is_active": bool(r.is_active),
                "sort_order": int(r.sort_order or 0),
            }
        return out
    except Exception:
        return {}
    finally:
        if session is not None:
            session.close()


def refresh_plan_cache() -> None:
    """Invalidate the cache so the next read reloads plan config from the DB.

    Call this after any Super Admin change to plan configuration so entitlements
    take effect immediately for all tenants on the plan.
    """
    global _cache, _cache_loaded_at
    with _cache_lock:
        _cache = None
        _cache_loaded_at = 0.0


def _get_all_configs() -> dict[str, dict]:
    """Return the effective config for every plan (DB overlaid on fallback)."""
    global _cache, _cache_loaded_at
    now = time.time()
    with _cache_lock:
        if _cache is not None and (now - _cache_loaded_at) < _CACHE_TTL_SECONDS:
            return _cache
        db_configs = _load_configs_from_db()
        merged: dict[str, dict] = {}
        for p in ALL_PLANS:
            merged[p] = db_configs.get(p) or _fallback_config(p)
        # Preserve any custom/extra plan keys present in the DB.
        for key, cfg in db_configs.items():
            merged.setdefault(key, cfg)
        _cache = merged
        _cache_loaded_at = now
        return merged


def _config(plan: str | None) -> dict:
    return _get_all_configs()[normalize_plan(plan)]


# ── Public helpers (DB-backed with code fallback) ────────────────────────────
def normalize_plan(plan: str | None) -> str:
    """Coerce a stored plan value to a known plan key (defaults to PLATINUM).

    PLATINUM is the safe default so an unrecognised/legacy value never silently
    locks a tenant out of modules it previously had.
    """
    token = (plan or "").strip().upper()
    return token if token in PLAN_MODULES else PLAN_PLATINUM


def plan_modules(plan: str | None) -> set[str]:
    return set(_config(plan)["modules"])


def plan_allows_module(plan: str | None, module: str) -> bool:
    return module in _config(plan)["modules"]


def plan_allows_any_module(plan: str | None, modules: Iterable[str]) -> bool:
    allowed = _config(plan)["modules"]
    return any(m in allowed for m in modules)


def plan_features(plan: str | None) -> set[str]:
    return set(_config(plan)["features"])


def plan_allows_feature(plan: str | None, feature: str) -> bool:
    return feature in _config(plan)["features"]


def plan_user_limit(plan: str | None) -> int:
    return int(_config(plan)["user_limit"])


def plan_is_active(plan: str | None) -> bool:
    return bool(_config(plan)["is_active"])


def plan_price_paise(plan: str | None) -> int:
    return int(_config(plan)["price_paise"])


def plan_allows_role(plan: str | None, role: str) -> bool:
    return (role or "").strip().lower() in _config(plan)["roles"]


def plan_roles(plan: str | None) -> set[str]:
    return set(_config(plan)["roles"])


# Maps every assignable role (new BRD roles AND legacy roles) to the BRD plan
# role-family used for plan availability checks. 'admin' is the Tenant Admin and
# is always allowed regardless of plan. Legacy roles map to their nearest family.
ROLE_PLAN_FAMILY = {
    "admin": "admin",
    "basic": ROLE_BASIC,
    "accounts": ROLE_ACCOUNTS,
    "inventory": ROLE_INVENTORY,
    "management": ROLE_MANAGEMENT,
    "hr": ROLE_HR,
    "inventory manager": ROLE_INVENTORY,
    "general manager": ROLE_ACCOUNTS,
}


def role_allowed_for_plan(plan: str | None, role: str | None) -> bool:
    """True if a role may be assigned under the tenant's plan.

    The Tenant Admin ('admin') is always allowed. Unknown/custom roles are
    permitted (fail-open) so this check never blocks bespoke setups; known roles
    are gated by the plan's role family (BRD §5.5/§6).
    """
    family = ROLE_PLAN_FAMILY.get((role or "").strip().lower())
    if family is None:
        return True
    if family == "admin":
        return True
    return plan_allows_role(plan, family)


def role_not_available_message(plan: str | None, role: str | None) -> str:
    return (
        f"The '{role}' role is not available on your {normalize_plan(plan)} plan. "
        f"Please upgrade your subscription to assign it."
    )


def upgrade_message(module: str, plan: str | None) -> str:
    """Business-friendly 'module not in your plan' message."""
    pretty = module.replace("_", " ").title()
    return (
        f"The {pretty} module is not included in your {normalize_plan(plan)} plan. "
        f"Please upgrade your subscription to access it."
    )


def free_invoice_cap(plan: str | None) -> int | None:
    """Monthly service-invoice cap for the plan (None = unlimited)."""
    return _config(plan)["free_invoice_cap"]


def entitlements(plan: str | None) -> dict:
    """Full entitlement snapshot for a plan (used by the entitlements API/UI)."""
    cfg = _config(plan)
    return {
        "plan": cfg["plan_key"],
        "plan_name": cfg["name"],
        "price_paise": cfg["price_paise"],
        "billing_period": cfg["billing_period"],
        "is_active": cfg["is_active"],
        "modules": sorted(cfg["modules"]),
        "features": sorted(cfg["features"]),
        "user_limit": cfg["user_limit"],
        "roles": sorted(cfg["roles"]),
        "free_invoice_cap": cfg["free_invoice_cap"],
    }
