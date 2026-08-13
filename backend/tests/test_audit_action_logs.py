"""Unit tests for Customer/Supplier Action Log tracking (BE-269) and the
audit retention-cleanup regression fix (BE-270). Pure functions — no database."""
import inspect

from app.services import audit_service
from app.services.audit_service import (
    int_to_roman,
    build_audit_changes,
    compose_audit_description,
    _is_versionable_edit,
    _FINANCIAL_MODULES,
    _VERSIONED_EDIT_MODULES,
)

_UUID = "2b1c9c5e-0000-4000-8000-000000000000"


# ── Sequential versions (Version I, II, III…) ────────────────────────────────
def test_roman_versions():
    assert [int_to_roman(n) for n in range(1, 6)] == ["I", "II", "III", "IV", "V"]
    assert int_to_roman(9) == "IX"
    assert int_to_roman(0) == ""


# ── Customers & Suppliers are tracked + version-tracked ──────────────────────
def test_customers_suppliers_are_tracked_and_versioned():
    for module in ("customers", "suppliers"):
        assert module in _FINANCIAL_MODULES        # persisted by the audit middleware
        assert module in _VERSIONED_EDIT_MODULES    # updates get sequential versions


def test_updates_are_versionable_creates_are_not():
    # PUT on a customer/supplier resource is a versioned edit…
    assert _is_versionable_edit("customers", "PUT", {"path": f"/api/v2/customers/{_UUID}"}) is True
    assert _is_versionable_edit("suppliers", "PUT", {"path": f"/api/v2/suppliers/{_UUID}"}) is True
    # …a create (POST, no id in the path) is not versioned…
    assert _is_versionable_edit("customers", "POST", {"path": "/api/v2/customers"}) is False
    # …and a module that is not version-tracked stays unversioned even on PUT.
    assert _is_versionable_edit("products", "PUT", {"path": f"/api/v2/products/{_UUID}"}) is False


# ── Field-level change capture ───────────────────────────────────────────────
def test_build_audit_changes_keeps_only_real_changes():
    changes = build_audit_changes([
        ("company_name", "Acme", "Acme Corp"),   # changed -> kept
        ("phone", "123", "123"),                 # unchanged -> dropped
        ("email", None, "x@acme.com"),           # empty -> value, kept
    ])
    assert [c["field"] for c in changes] == ["company_name", "email"]


# ── Human-readable descriptions ──────────────────────────────────────────────
def test_customer_create_and_update_descriptions():
    created = compose_audit_description(
        action_type="POST", module_name="customers",
        document_reference="CUST-KA-00001",
        details={"path": "/api/v1/customers"}, status="success",
    )
    assert created == "Customer CUST-KA-00001 created."

    updated = compose_audit_description(
        action_type="PUT", module_name="customers",
        document_reference="CUST-KA-00001",
        details={"changes": build_audit_changes([("company_name", "Acme", "Acme Corp")])},
        status="success",
    )
    lines = updated.splitlines()
    assert lines[0] == "Customer CUST-KA-00001 updated."
    assert "Company Name changed from Acme to Acme Corp." in lines


def test_supplier_description_uses_supplier_label():
    desc = compose_audit_description(
        action_type="POST", module_name="suppliers",
        document_reference="SUPP-MH-00003", details={}, status="success",
    )
    assert desc == "Supplier SUPP-MH-00003 created."


# ── BE-270 regression guard: retention cleanup SQL must not reintroduce the
#    bind/`::`-cast collision that silently discarded audit rows. ─────────────
def test_retention_cleanup_uses_safe_interval_sql():
    src = inspect.getsource(audit_service._maybe_cleanup_old_audit_logs)
    assert "* INTERVAL '1 day'" in src            # the corrected construction
    assert "days')::interval" not in src          # the old buggy string-concat cast
