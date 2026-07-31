"""Unit tests for core business logic (roles/permissions, plans, financial year).

All pure functions — no database access."""
from datetime import date

from app.services.auth_service import normalize_role, calculate_effective_access
from app.services.plan_service import normalize_plan
from app.routers.reports import _current_financial_year, _fy_month_year


# ── Roles & permissions ──────────────────────────────────────────────────────
def test_normalize_role_aliases():
    assert normalize_role("Admin") == "admin"
    assert normalize_role("general manager") == "accounts"
    assert normalize_role("inventory manager") == "inventory"


def test_admin_has_admin_only_scopes():
    access = calculate_effective_access("admin")
    assert "company_write" in access
    assert "users_write" in access


def test_basic_role_limited_to_service_invoice():
    access = calculate_effective_access("basic")
    assert access == ["service_invoice_read", "service_invoice_write"]


def test_overrides_cannot_grant_admin_only_to_non_admin():
    # Accounts user tries to gain users_write via an allow-override -> denied.
    access = calculate_effective_access("accounts", {"allow": ["users_write"], "deny": []})
    assert "users_write" not in access


def test_deny_override_removes_scope():
    access = calculate_effective_access("accounts", {"allow": [], "deny": ["customers_write"]})
    assert "customers_write" not in access


# ── Subscription plans ───────────────────────────────────────────────────────
def test_normalize_plan():
    assert normalize_plan("gold") == "GOLD"
    assert normalize_plan("SILVER") == "SILVER"
    assert normalize_plan("nonsense") == "PLATINUM"   # safe default


# ── Financial year (April–March) ─────────────────────────────────────────────
def test_current_financial_year():
    # Apr–Dec belong to that year's FY; Jan–Mar belong to the previous FY.
    assert _current_financial_year(date(2025, 5, 1)) == 2025
    assert _current_financial_year(date(2025, 4, 1)) == 2025
    assert _current_financial_year(date(2025, 2, 15)) == 2024
    assert _current_financial_year(date(2025, 3, 31)) == 2024


def test_fy_month_year_mapping():
    # In FY 2025-26: April..December are in 2025, January..March are in 2026.
    assert _fy_month_year(2025, 4) == 2025
    assert _fy_month_year(2025, 12) == 2025
    assert _fy_month_year(2025, 1) == 2026
    assert _fy_month_year(2025, 3) == 2026
