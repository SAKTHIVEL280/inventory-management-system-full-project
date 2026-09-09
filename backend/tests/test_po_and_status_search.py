"""Unit tests for the Purchase-Order tenant-scoping helper (Draft PO visibility
fix). Pure (no DB): they assert the scoping/branch logic only."""
import inspect

from app.routers import purchase


# ── Issue 1: PO access is company-scoped, not created_by-scoped ───────────────
def test_get_company_po_helper_scopes_by_company():
    src = inspect.getsource(purchase._get_company_po)
    assert "company_id == current_user.company_id" in src   # tenant isolation
    assert "PurchaseOrder.created_by" not in src            # not owner-gated (no created_by filter)


def test_po_by_id_endpoints_use_company_scope_not_owner():
    # get / update / status / archive / restore / pdf must fetch via _get_company_po
    # and must NOT re-introduce the created_by ownership gate.
    for fn in (purchase.get_purchase_order, purchase.update_purchase_order,
               purchase.update_purchase_order_status, purchase.archive_purchase_order,
               purchase.restore_purchase_order, purchase.download_po_pdf):
        src = inspect.getsource(fn)
        assert "_get_company_po(" in src, f"{fn.__name__} should use _get_company_po"
        assert "_enforce_owner(po" not in src, f"{fn.__name__} must not owner-gate the PO"


def test_list_is_company_scoped_not_owner_scoped():
    # The PO list must be visible tenant-wide (an approver sees drafts raised by
    # others). It must scope by company_id and NOT via the created_by owner-gate
    # (_scope_to_owner) — otherwise a role that fails to resolve into PRIVILEGED_ROLES
    # would see only its own POs, hiding another user's draft.
    src = inspect.getsource(purchase.list_purchase_orders)
    assert "scope_query_to_company(" in src   # tenant isolation by company_id
    assert "_scope_to_owner(" not in src       # no created_by owner-gate on the list
