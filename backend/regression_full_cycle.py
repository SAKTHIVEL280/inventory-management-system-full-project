"""End-to-end API regression cycle for critical fixes.

Covers:
- REC-001 customer payment guard
- PRO-003 Base Unit required
- SUP state_code contract removal check
- CUS-006/CUS-010 customer defaults
- GRN/Sales date-rule guard (invoice payload validation path)
- SAL-026 due-date override (create + update)
- SAL-001 Sales Order module removal
- Dashboard pending SO and cashflow draft exclusion
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from dataclasses import dataclass
import json
import os
import sys
from typing import Any

import httpx


BASE_URL = os.getenv("IMS_BASE_URL", "http://127.0.0.1:8001")
ADMIN_EMAIL = os.getenv("IMS_TEST_EMAIL", "admin@company.com")
ADMIN_PASSWORD = os.getenv("IMS_TEST_PASSWORD", "Admin@123")
TIMEOUT = float(os.getenv("IMS_TEST_TIMEOUT", "25"))


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str


def _today_iso() -> str:
    return date.today().isoformat()


def _date_plus(days: int) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


def _as_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=True)
    except Exception:
        return str(value)


def _collect_detail(resp: httpx.Response) -> str:
    try:
        data = resp.json()
    except Exception:
        return f"status={resp.status_code}, body={resp.text[:400]}"
    detail = data.get("detail", data)
    return f"status={resp.status_code}, detail={_as_text(detail)[:400]}"


def _new_domestic_customer_payload(tag: str, with_full_billing: bool) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "company_name": f"QA Customer {tag}",
        "phone": "+919876543210",
        "customer_type": "regular",
        "gstin_status": "non-registered",
        "business_type": "domestic",
        "same_as_billing": True,
        "currency_code": "INR",
    }
    if with_full_billing:
        payload.update(
            {
                "billing_address_line1": "12 QA Street",
                "billing_city": "Chennai",
                "billing_state": "Tamil Nadu",
                "billing_state_code": "TN",
                "billing_country": "India",
                "billing_pincode": "600001",
            }
        )
    return payload


def _find_product_with_batch(api: httpx.Client) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    products = api.get("/api/v1/products", params={"page": 1, "page_size": 200})
    if products.status_code != 200:
        return None, None

    for product in products.json().get("items", []):
        batch_opts = api.get("/api/v1/invoices/batch-options", params={"product_id": product["id"]})
        if batch_opts.status_code != 200:
            continue
        valid = [
            row
            for row in batch_opts.json().get("items", [])
            if float(row.get("available_qty") or 0) >= 1
            and row.get("batch_no")
            and row.get("manufacture_date")
            and row.get("expiry_date")
        ]
        if valid:
            return product, valid[0]

    return None, None


def _seed_batch_inventory_data(
    api: httpx.Client,
    run_tag: str,
    category_id: str,
    uom_id: str,
) -> tuple[bool, str]:
    supplier_resp = api.post(
        "/api/v1/suppliers",
        json={
            "company_name": f"QA Supplier {run_tag}",
            "phone": "+919876500001",
            "gstin_status": "non-registered",
            "business_type": "domestic",
            "city": "Chennai",
            "state": "Tamil Nadu",
            "billing_country": "India",
            "pincode": "600001",
            "payment_terms_days": 30,
            "currency_code": "INR",
        },
    )
    if supplier_resp.status_code != 201:
        return False, f"supplier create failed: {_collect_detail(supplier_resp)}"
    supplier_id = supplier_resp.json().get("id")

    product_resp = api.post(
        "/api/v1/products",
        json={
            "name": f"QA Batch Product {run_tag}",
            "sku": "PCS",
            "category_id": category_id,
            "uom_id": uom_id,
            "hsn_code": "300490",
            "gst_rate": 12,
            "purchase_price": 100,
            "selling_price": 150,
            "mrp": 200,
            "is_active": True,
        },
    )
    if product_resp.status_code != 201:
        return False, f"product create failed: {_collect_detail(product_resp)}"
    product_id = product_resp.json().get("id")

    po_resp = api.post(
        "/api/v1/purchase-orders",
        json={
            "supplier_id": supplier_id,
            "order_date": _today_iso(),
            "expected_delivery_date": _date_plus(2),
            "items": [
                {
                    "product_id": product_id,
                    "quantity": 10,
                    "unit_price": 100,
                    "discount_percent": 0,
                    "gst_rate": 12,
                }
            ],
        },
    )
    if po_resp.status_code != 200:
        return False, f"PO create failed: {_collect_detail(po_resp)}"
    po_id = po_resp.json().get("id")

    po_sent = api.patch(f"/api/v1/purchase-orders/{po_id}/status", json={"status": "sent"})
    if po_sent.status_code != 200:
        return False, f"PO send failed: {_collect_detail(po_sent)}"

    grn_resp = api.post(
        "/api/v1/grn",
        json={
            "supplier_id": supplier_id,
            "purchase_order_id": po_id,
            "supplier_invoice_number": f"QA-INV-{run_tag}",
            "receipt_date": _today_iso(),
            "items": [
                {
                    "product_id": product_id,
                    "batch_no": f"QA-BATCH-{run_tag}",
                    "manufacture_date": _date_plus(-30),
                    "expiry_date": _date_plus(180),
                    "quantity": 10,
                    "free_quantity": 0,
                    "unit_price": 100,
                    "discount_percent": 0,
                    "gst_rate": 12,
                }
            ],
        },
    )
    if grn_resp.status_code != 200:
        return False, f"GRN create failed: {_collect_detail(grn_resp)}"
    grn_id = grn_resp.json().get("id")

    grn_confirm = api.post(f"/api/v1/grn/{grn_id}/confirm")
    if grn_confirm.status_code != 200:
        return False, f"GRN confirm failed: {_collect_detail(grn_confirm)}"

    return True, "Seeded supplier/product/PO/GRN for batch regression"


def run() -> int:
    results: list[CheckResult] = []

    with httpx.Client(base_url=BASE_URL, timeout=TIMEOUT) as client:
        # Health check
        health = client.get("/health")
        if health.status_code == 200 and health.json().get("status") == "ok":
            results.append(CheckResult("health", True, "API health endpoint returned ok"))
        else:
            results.append(CheckResult("health", False, _collect_detail(health)))
            _print_results(results)
            return 1

        # Login
        login = client.post(
            "/api/v1/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        )
        if login.status_code != 200:
            results.append(CheckResult("auth_login", False, _collect_detail(login)))
            _print_results(results)
            return 1

        token = login.json().get("access_token")
        if not token:
            results.append(CheckResult("auth_login", False, "Missing access_token in login response"))
            _print_results(results)
            return 1

        results.append(CheckResult("auth_login", True, "Authenticated as admin"))

    headers = {"Authorization": f"Bearer {token}"}

    with httpx.Client(base_url=BASE_URL, timeout=TIMEOUT, headers=headers) as api:
        # SAL-001: Sales Order module removed
        so_list = api.get("/api/v1/sales-orders")
        so_ok = so_list.status_code == 410 and "removed" in _collect_detail(so_list).lower()
        results.append(
            CheckResult(
                "sal_001_sales_order_removed",
                so_ok,
                _collect_detail(so_list),
            )
        )

        # Dashboard sanity: pending sales orders should remain zero
        dashboard = api.get("/api/v1/reports/dashboard")
        if dashboard.status_code == 200:
            d = dashboard.json()
            pending_so = int(d.get("pending_sales_orders", -1))
            results.append(
                CheckResult(
                    "dashboard_pending_sales_orders_zero",
                    pending_so == 0,
                    f"pending_sales_orders={pending_so}",
                )
            )
        else:
            results.append(CheckResult("dashboard_pending_sales_orders_zero", False, _collect_detail(dashboard)))

        # Supplier contract: state_code should not be exposed in response
        suppliers = api.get("/api/v1/suppliers", params={"page": 1, "page_size": 10})
        if suppliers.status_code == 200:
            items = suppliers.json().get("items", [])
            if items:
                first = items[0]
                ok = "state_code" not in first
                results.append(
                    CheckResult(
                        "supplier_state_code_hidden",
                        ok,
                        "state_code key absent" if ok else "state_code key still present in supplier response",
                    )
                )
            else:
                results.append(
                    CheckResult(
                        "supplier_state_code_hidden",
                        True,
                        "No supplier rows returned; endpoint reachable",
                    )
                )
        else:
            results.append(CheckResult("supplier_state_code_hidden", False, _collect_detail(suppliers)))

        # CUS-010/CUS-006 defaults check on new domestic customer
        run_tag = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        c_default = api.post("/api/v1/customers", json=_new_domestic_customer_payload(f"DEFAULT-{run_tag}", False))
        default_customer_id: str | None = None
        if c_default.status_code == 201:
            c_data = c_default.json()
            default_customer_id = c_data.get("id")
            billing_country = (c_data.get("billing_country") or "").strip().lower()
            has_billing_defaults = all(
                (c_data.get(k) or "").strip()
                for k in ["billing_address_line1", "billing_city", "billing_state", "billing_pincode"]
            )
            results.append(
                CheckResult(
                    "cus_010_billing_defaults",
                    has_billing_defaults,
                    "Billing defaults applied from company" if has_billing_defaults else "Missing one or more billing defaults",
                )
            )
            results.append(
                CheckResult(
                    "cus_006_default_billing_country",
                    billing_country == "india",
                    f"billing_country={c_data.get('billing_country')}",
                )
            )
        else:
            results.append(CheckResult("cus_010_billing_defaults", False, _collect_detail(c_default)))
            results.append(CheckResult("cus_006_default_billing_country", False, _collect_detail(c_default)))

        # REC-001: no open invoice guard for customer payment
        if default_customer_id:
            pay_no_open = api.post(
                "/api/v1/payments",
                json={
                    "payment_type": "receipt",
                    "party_type": "customer",
                    "customer_id": default_customer_id,
                    "payment_date": _today_iso(),
                    "amount": 100,
                    "payment_mode": "cash",
                    "allocations": [],
                },
            )
            no_open_ok = pay_no_open.status_code == 400 and "no open invoice" in _collect_detail(pay_no_open).lower()
            results.append(CheckResult("rec_001_no_open_invoice_guard", no_open_ok, _collect_detail(pay_no_open)))
        else:
            results.append(CheckResult("rec_001_no_open_invoice_guard", False, "Skipped: default customer creation failed"))

        # PRO-003: Base Unit required in backend
        categories = api.get("/api/v1/products/categories")
        uoms = api.get("/api/v1/products/uom")
        category_id: str | None = None
        uom_id: str | None = None
        if categories.status_code == 200 and uoms.status_code == 200 and categories.json() and uoms.json():
            category_id = categories.json()[0]["id"]
            uom_id = uoms.json()[0]["id"]
            product_missing_sku = api.post(
                "/api/v1/products",
                json={
                    "name": f"QA Product Missing SKU {run_tag}",
                    "category_id": category_id,
                    "uom_id": uom_id,
                    "hsn_code": "300490",
                    "gst_rate": 12,
                    "purchase_price": 100,
                    "selling_price": 150,
                    "mrp": 200,
                    "is_active": True,
                },
            )
            body = _collect_detail(product_missing_sku).lower()
            pro_ok = product_missing_sku.status_code in (400, 422) and "base unit is required" in body
            results.append(CheckResult("pro_003_base_unit_required", pro_ok, _collect_detail(product_missing_sku)))
        else:
            results.append(
                CheckResult(
                    "pro_003_base_unit_required",
                    False,
                    f"Prereq fetch failed: categories={categories.status_code}, uom={uoms.status_code}",
                )
            )

        # Prepare invoice customer (complete shipping/billing for invoice save)
        c_invoice = api.post("/api/v1/customers", json=_new_domestic_customer_payload(f"INV-{run_tag}", True))
        invoice_customer_id: str | None = None
        if c_invoice.status_code == 201:
            invoice_customer_id = c_invoice.json().get("id")
        else:
            results.append(CheckResult("invoice_customer_setup", False, _collect_detail(c_invoice)))

        # Find a product with at least one available batch option
        product_with_batch, selected_batch = _find_product_with_batch(api)
        if not product_with_batch or not selected_batch:
            if category_id and uom_id:
                seeded, seed_detail = _seed_batch_inventory_data(api, run_tag, category_id, uom_id)
                results.append(CheckResult("invoice_batch_seed_setup", seeded, seed_detail))
                if seeded:
                    product_with_batch, selected_batch = _find_product_with_batch(api)
            else:
                results.append(
                    CheckResult(
                        "invoice_batch_seed_setup",
                        False,
                        "Cannot seed batch data because categories/uom prerequisites failed",
                    )
                )

        invoice_id: str | None = None
        invoice_customer_name = f"QA Customer INV-{run_tag}"

        if invoice_customer_id and product_with_batch and selected_batch:
            due_date_1 = _date_plus(7)
            unit_price = int(product_with_batch.get("selling_price") or 1)
            gst_rate = int(product_with_batch.get("gst_rate") or 0)

            create_invoice_payload = {
                "customer_id": invoice_customer_id,
                "invoice_date": _today_iso(),
                "due_date": due_date_1,
                "bill_to_customer_id": invoice_customer_id,
                "items": [
                    {
                        "product_id": product_with_batch["id"],
                        "batch_no": selected_batch["batch_no"],
                        "manufacture_date": selected_batch["manufacture_date"],
                        "expiry_date": selected_batch["expiry_date"],
                        "quantity": 1,
                        "unit_price": unit_price,
                        "discount_percent": 0,
                        "gst_rate": gst_rate,
                    }
                ],
            }

            created_invoice = api.post("/api/v1/invoices", json=create_invoice_payload)
            if created_invoice.status_code == 200:
                inv = created_invoice.json()
                invoice_id = inv.get("id")
                due_saved = inv.get("due_date")
                results.append(
                    CheckResult(
                        "sal_026_due_date_override_create",
                        due_saved == due_date_1,
                        f"expected={due_date_1}, actual={due_saved}",
                    )
                )

                due_date_2 = _date_plus(12)
                update_payload = dict(create_invoice_payload)
                update_payload["due_date"] = due_date_2
                updated_invoice = api.put(f"/api/v1/invoices/{invoice_id}", json=update_payload)
                if updated_invoice.status_code == 200:
                    due_updated = updated_invoice.json().get("due_date")
                    results.append(
                        CheckResult(
                            "sal_026_due_date_override_update",
                            due_updated == due_date_2,
                            f"expected={due_date_2}, actual={due_updated}",
                        )
                    )
                else:
                    results.append(CheckResult("sal_026_due_date_override_update", False, _collect_detail(updated_invoice)))

                # Date-rule guard path in sales invoice save flow
                invalid_date_payload = dict(create_invoice_payload)
                invalid_date_payload["items"] = [
                    {
                        "product_id": product_with_batch["id"],
                        "batch_no": selected_batch["batch_no"],
                        "manufacture_date": _today_iso(),
                        "expiry_date": selected_batch["expiry_date"],
                        "quantity": 1,
                        "unit_price": unit_price,
                        "discount_percent": 0,
                        "gst_rate": gst_rate,
                    }
                ]
                invalid_invoice = api.post("/api/v1/invoices", json=invalid_date_payload)
                detail = _collect_detail(invalid_invoice).lower()
                invalid_ok = invalid_invoice.status_code == 400 and (
                    "invalid date range" in detail
                    or "mfg/exp date mismatch" in detail
                )
                results.append(CheckResult("sales_date_validation_guard", invalid_ok, _collect_detail(invalid_invoice)))
            else:
                results.append(CheckResult("sal_026_due_date_override_create", False, _collect_detail(created_invoice)))
                results.append(CheckResult("sal_026_due_date_override_update", False, "Skipped: invoice creation failed"))
                results.append(CheckResult("sales_date_validation_guard", False, "Skipped: invoice creation failed"))
        else:
            reason = "missing invoice customer" if not invoice_customer_id else "no product with available batch options"
            results.append(CheckResult("sal_026_due_date_override_create", False, f"Skipped: {reason}"))
            results.append(CheckResult("sal_026_due_date_override_update", False, f"Skipped: {reason}"))
            results.append(CheckResult("sales_date_validation_guard", False, f"Skipped: {reason}"))

        # Dashboard cashflow should ignore draft invoices
        dashboard_after = api.get("/api/v1/reports/dashboard")
        if dashboard_after.status_code == 200:
            data = dashboard_after.json()
            cash_flow = data.get("cash_in_flow", {})
            names = set()
            for bucket in ("daily", "weekly", "monthly"):
                for row in cash_flow.get(bucket, []) or []:
                    names.add((row.get("customer_name") or "").strip())
            excluded = invoice_customer_name not in names
            results.append(
                CheckResult(
                    "dashboard_cashflow_excludes_draft",
                    excluded,
                    "Draft-invoice customer excluded from cashflow" if excluded else "Draft-invoice customer appears in cashflow",
                )
            )
        else:
            results.append(CheckResult("dashboard_cashflow_excludes_draft", False, _collect_detail(dashboard_after)))

    _print_results(results)
    return 0 if all(r.ok for r in results) else 1


def _print_results(results: list[CheckResult]) -> None:
    total = len(results)
    passed = sum(1 for r in results if r.ok)
    failed = total - passed

    print("\n=== REGRESSION RESULTS ===")
    for r in results:
        status = "PASS" if r.ok else "FAIL"
        print(f"[{status}] {r.name}: {r.detail}")

    print("\n=== SUMMARY ===")
    print(f"total={total}, passed={passed}, failed={failed}")


if __name__ == "__main__":
    raise SystemExit(run())
