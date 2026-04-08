#!/usr/bin/env python3
"""Full closure suite for unresolved tracker IDs.

This script validates all non-pass TC IDs extracted from:
  backend/non_pass_tracker_rows_clean.csv

It runs a mix of:
- API behavior checks
- PDF output checks
- Static frontend/backend source checks

Output:
- backend/full_non_pass_closure_report.json
- backend/full_non_pass_closure_report.md
"""

from __future__ import annotations

import csv
import json
import random
import re
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Any
from uuid import uuid4

import requests
from pypdf import PdfReader


BASE_URL = "http://127.0.0.1:8001"
ADMIN_EMAIL = "admin@company.com"
ADMIN_PASSWORD = "Admin@123"

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
FRONTEND_DIR = ROOT / "frontend"

NON_PASS_CSV = BACKEND_DIR / "non_pass_tracker_rows_clean.csv"
REPORT_JSON = BACKEND_DIR / "full_non_pass_closure_report.json"
REPORT_MD = BACKEND_DIR / "full_non_pass_closure_report.md"


def _now_token() -> str:
    return datetime.now().strftime("%Y%m%d%H%M%S") + f"-{random.randint(100, 999)}"


def _contains_all(text: str, needles: list[str]) -> None:
    missing = [needle for needle in needles if needle not in text]
    if missing:
        raise AssertionError(f"Missing tokens: {missing}")


def _contains_any(text: str, needles: list[str]) -> None:
    if not any(needle in text for needle in needles):
        raise AssertionError(f"Expected any of {needles}, but none were found")


def _read_text(path: Path) -> str:
    if not path.exists():
        raise AssertionError(f"Missing file: {path}")
    return path.read_text(encoding="utf-8")


def _pdf_text(pdf_bytes: bytes) -> str:
    reader = PdfReader(BytesIO(pdf_bytes))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


@dataclass
class TCRunResult:
    tc_id: str
    status: str
    check_name: str
    detail: str


@dataclass
class SuiteResult:
    tc_ids: set[str]
    results: dict[str, TCRunResult] = field(default_factory=dict)

    def mark(self, ids: list[str], passed: bool, check_name: str, detail: str) -> None:
        status = "PASS" if passed else "FAIL"
        for tc_id in ids:
            self.results[tc_id] = TCRunResult(
                tc_id=tc_id,
                status=status,
                check_name=check_name,
                detail=detail,
            )

    def finalize_uncovered(self) -> None:
        for tc_id in sorted(self.tc_ids):
            if tc_id not in self.results:
                self.results[tc_id] = TCRunResult(
                    tc_id=tc_id,
                    status="FAIL",
                    check_name="coverage",
                    detail="No validation mapped for this TC ID",
                )

    def summary(self) -> dict[str, Any]:
        total = len(self.tc_ids)
        passed = sum(1 for r in self.results.values() if r.status == "PASS")
        failed = total - passed
        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": round((passed / total) * 100, 2) if total else 0.0,
        }


class API:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.s = requests.Session()
        self.s.headers.update({"Content-Type": "application/json"})

    def login(self, email: str, password: str) -> None:
        r = self.s.post(
            f"{self.base_url}/api/v1/auth/login",
            json={"email": email, "password": password},
            timeout=30,
        )
        if r.status_code != 200:
            raise AssertionError(f"Login failed ({r.status_code}): {r.text[:500]}")
        token = r.json().get("access_token")
        if not token:
            raise AssertionError("Login response missing access_token")
        self.s.headers["Authorization"] = f"Bearer {token}"

    def request(
        self,
        method: str,
        path: str,
        *,
        expected: tuple[int, ...] = (200,),
        json_body: Any | None = None,
        params: dict[str, Any] | None = None,
        raw: bool = False,
    ) -> Any:
        url = f"{self.base_url}{path}"
        r = self.s.request(method, url, json=json_body, params=params, timeout=45)
        if r.status_code not in expected:
            raise AssertionError(
                f"{method} {path} expected {expected}, got {r.status_code}: {r.text[:600]}"
            )
        if raw:
            return r
        if "application/json" in (r.headers.get("content-type") or ""):
            return r.json()
        return r


class ClosureSuite:
    def __init__(self) -> None:
        self.api = API(BASE_URL)
        self.token = _now_token()
        self.category_id: str | None = None
        self.uom_ids: list[str] = []

    def load_non_pass_ids(self) -> set[str]:
        ids: set[str] = set()
        with NON_PASS_CSV.open("r", encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                tc_id = (row.get("TC_ID") or "").strip().upper()
                if tc_id:
                    ids.add(tc_id)
        return ids

    def bootstrap(self) -> None:
        self.api.login(ADMIN_EMAIL, ADMIN_PASSWORD)
        categories = self.api.request("GET", "/api/v1/products/categories")
        if not categories:
            raise AssertionError("No product categories found")
        self.category_id = categories[0]["id"]

        uoms = self.api.request("GET", "/api/v1/products/uom")
        if not uoms:
            raise AssertionError("No UOM entries found")
        self.uom_ids = [u["id"] for u in uoms]

    def _unique(self, prefix: str) -> str:
        return f"{prefix}-{self.token}-{uuid4().hex[:8]}"

    def _short_code(self, prefix: str) -> str:
        return f"{prefix[:4].upper()}-{uuid4().hex[:8]}"[:20]

    def create_supplier(
        self,
        *,
        payment_terms_days: int = 30,
        country: str = "India",
        business_type: str = "domestic",
    ) -> dict[str, Any]:
        payload = {
            "supplier_code": self._short_code("SUP"),
            "company_name": self._unique("SUPP"),
            "phone": f"+91{random.randint(8000000000, 9999999999)}",
            "email": f"{self._unique('supplier').lower()}@example.com",
            "business_type": business_type,
            "gstin_status": "non-registered",
            "city": "Bengaluru",
            "state": "Karnataka",
            "billing_country": country,
            "payment_terms_days": payment_terms_days,
            "currency_code": "INR",
        }
        return self.api.request("POST", "/api/v1/suppliers", expected=(201,), json_body=payload)

    def create_customer(
        self,
        *,
        country: str = "India",
        business_type: str = "domestic",
        shipping_complete: bool = True,
        same_as_billing: bool = False,
        payment_terms_days: int | None = 30,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "customer_code": self._short_code("CUST"),
            "company_name": self._unique("CUST"),
            "customer_type": "regular",
            "phone": f"+91{random.randint(8000000000, 9999999999)}",
            "email": f"{self._unique('customer').lower()}@example.com",
            "business_type": business_type,
            "gstin_status": "non-registered",
            "billing_address_line1": "42 Main Street",
            "billing_city": "Bengaluru",
            "billing_state": "Karnataka",
            "billing_state_code": "KA",
            "billing_country": country,
            "billing_pincode": "560001",
            "same_as_billing": same_as_billing,
            "currency_code": "INR",
            "payment_terms_days": payment_terms_days,
            "credit_limit": 10000,
        }

        if shipping_complete:
            payload.update(
                {
                    "shipping_address_line1": "42 Shipping Street",
                    "shipping_city": "Bengaluru",
                    "shipping_state": "Karnataka",
                    "shipping_state_code": "KA",
                    "shipping_country": country,
                    "shipping_pincode": "560001",
                }
            )
        else:
            payload.update(
                {
                    "shipping_address_line1": None,
                    "shipping_city": None,
                    "shipping_state": None,
                    "shipping_state_code": None,
                    "shipping_country": None,
                    "shipping_pincode": None,
                }
            )
        return self.api.request("POST", "/api/v1/customers", expected=(201,), json_body=payload)

    def create_product(
        self,
        *,
        opening_stock: int = 120,
        alt_mapping: bool = False,
        gst_rate: int = 12,
    ) -> dict[str, Any]:
        if not self.category_id or not self.uom_ids:
            raise AssertionError("Suite not bootstrapped")
        payload: dict[str, Any] = {
            "name": self._unique("Product"),
            "sku": "PCS",
            "category_id": self.category_id,
            "uom_id": self.uom_ids[0],
            "hsn_code": "300490",
            "gst_rate": gst_rate,
            "purchase_price": 100,
            "selling_price": 150,
            "mrp": 200,
            "minimum_stock": 0,
            "safety_stock": 10,
            "opening_stock": opening_stock,
            "status": "active",
            "is_active": True,
        }
        if alt_mapping and len(self.uom_ids) > 1:
            payload["alt_uom_id"] = self.uom_ids[1]
            payload["alt_uom_conversion"] = 10
        return self.api.request("POST", "/api/v1/products", expected=(201,), json_body=payload)

    def create_po(
        self,
        *,
        supplier_id: str,
        product_id: str,
        qty: float,
        under_tol: float,
        over_tol: float,
    ) -> dict[str, Any]:
        payload = {
            "supplier_id": supplier_id,
            "order_date": date.today().isoformat(),
            "currency_code": "INR",
            "exchange_rate": 1,
            "under_delivery_tolerance": under_tol,
            "over_delivery_tolerance": over_tol,
            "items": [
                {
                    "product_id": product_id,
                    "quantity": qty,
                    "unit_price": 100,
                    "discount_percent": 0,
                    "gst_rate": 12,
                }
            ],
        }
        return self.api.request("POST", "/api/v1/purchase-orders", expected=(200,), json_body=payload)

    def send_po(self, po_id: str) -> dict[str, Any]:
        return self.api.request(
            "PATCH",
            f"/api/v1/purchase-orders/{po_id}/status",
            expected=(200,),
            json_body={"status": "sent"},
        )

    def create_grn(
        self,
        *,
        supplier_id: str,
        product_id: str,
        qty: float,
        po_id: str | None = None,
        mfg_date: str | None = None,
        exp_date: str | None = None,
        batch_no: str | None = None,
        expected: tuple[int, ...] = (200,),
    ) -> Any:
        payload: dict[str, Any] = {
            "supplier_id": supplier_id,
            "purchase_order_id": po_id,
            "receipt_date": date.today().isoformat(),
            "supplier_invoice_number": self._unique("INV"),
            "supplier_invoice_date": date.today().isoformat(),
            "items": [
                {
                    "product_id": product_id,
                    "quantity": qty,
                    "free_quantity": 0,
                    "unit_price": 100,
                    "discount_percent": 0,
                    "gst_rate": 12,
                    "batch_no": batch_no,
                    "manufacture_date": mfg_date,
                    "expiry_date": exp_date,
                }
            ],
        }
        return self.api.request("POST", "/api/v1/grn", expected=expected, json_body=payload)

    def confirm_grn(self, grn_id: str) -> dict[str, Any]:
        return self.api.request("POST", f"/api/v1/grn/{grn_id}/confirm", expected=(200,))

    def get_grn_detail(self, grn_id: str) -> dict[str, Any]:
        return self.api.request("GET", f"/api/v1/grn/{grn_id}")

    def create_invoice(
        self,
        *,
        customer_id: str,
        product_id: str,
        invoice_type: str,
        qty: float = 1,
        due_date: str | None = None,
        batch_no: str | None = None,
        mfg_date: str | None = None,
        exp_date: str | None = None,
        import_export_code: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "customer_id": customer_id,
            "invoice_date": date.today().isoformat(),
            "invoice_type": invoice_type,
            "due_date": due_date,
            "import_export_code": import_export_code,
            "items": [
                {
                    "product_id": product_id,
                    "quantity": qty,
                    "unit_price": 200,
                    "discount_percent": 0,
                    "gst_rate": 12,
                    "order_unit": "Box",
                    "batch_no": batch_no,
                    "manufacture_date": mfg_date,
                    "expiry_date": exp_date,
                }
            ],
        }
        return self.api.request("POST", "/api/v1/invoices", expected=(200,), json_body=payload)

    def issue_invoice(self, invoice_id: str) -> dict[str, Any]:
        return self.api.request("POST", f"/api/v1/invoices/{invoice_id}/issue", expected=(200,))

    def get_invoice_detail(self, invoice_id: str) -> dict[str, Any]:
        return self.api.request("GET", f"/api/v1/invoices/{invoice_id}")

    def get_invoice_pdf_text(self, invoice_id: str) -> str:
        resp = self.api.request("GET", f"/api/v1/invoices/{invoice_id}/pdf", expected=(200,), raw=True)
        return _pdf_text(resp.content)

    def get_po_pdf_text(self, po_id: str) -> str:
        resp = self.api.request("GET", f"/api/v1/purchase-orders/{po_id}/pdf", expected=(200,), raw=True)
        return _pdf_text(resp.content)

    def record_payment(self, payload: dict[str, Any], expected: tuple[int, ...] = (200, 201)) -> Any:
        return self.api.request("POST", "/api/v1/payments", expected=expected, json_body=payload)

    def update_payment_status(self, payment_id: str, status_value: str) -> dict[str, Any]:
        return self.api.request(
            "PATCH",
            f"/api/v1/payments/{payment_id}/status",
            expected=(200,),
            json_body={"status": status_value},
        )

    # ---------------- checks ----------------

    def check_company_invoice_types_export(self) -> None:
        # COM-001 + SAL-029/030/031/037/038/039
        company = self.api.request("GET", "/api/v1/company")
        company_update = dict(company)
        company_update["name"] = company.get("name") or "My Company"
        company_update["import_export_number"] = f"IEC-{self.token}"
        self.api.request("PUT", "/api/v1/company", expected=(200,), json_body=company_update)

        product = self.create_product(opening_stock=200, gst_rate=12)
        domestic = self.create_customer(country="India", business_type="domestic", shipping_complete=True)
        international = self.create_customer(country="Thailand", business_type="international", shipping_complete=True)

        inv_within = self.create_invoice(
            customer_id=domestic["id"],
            product_id=product["id"],
            invoice_type="within_state",
        )
        d_within = self.get_invoice_detail(inv_within["id"])["invoice"]
        if not (d_within["total_cgst"] > 0 and d_within["total_sgst"] > 0 and d_within["total_igst"] == 0):
            raise AssertionError(f"Within-state tax split invalid: {d_within}")

        inv_other = self.create_invoice(
            customer_id=domestic["id"],
            product_id=product["id"],
            invoice_type="other_states",
        )
        d_other = self.get_invoice_detail(inv_other["id"])["invoice"]
        if not (d_other["total_igst"] > 0 and d_other["total_cgst"] == 0 and d_other["total_sgst"] == 0):
            raise AssertionError(f"Other-state tax split invalid: {d_other}")

        inv_ut = self.create_invoice(
            customer_id=domestic["id"],
            product_id=product["id"],
            invoice_type="union_territory",
        )
        d_ut = self.get_invoice_detail(inv_ut["id"])["invoice"]
        if not (d_ut["total_cgst"] > 0 and d_ut["total_sgst"] > 0 and d_ut["total_igst"] == 0):
            raise AssertionError(f"Union-territory tax split invalid: {d_ut}")

        inv_export = self.create_invoice(
            customer_id=international["id"],
            product_id=product["id"],
            invoice_type="export_invoice",
            import_export_code=f"CUST-IEC-{self.token}",
        )
        d_export = self.get_invoice_detail(inv_export["id"])["invoice"]
        if not (d_export["total_gst"] == 0 and d_export["total_cgst"] == 0 and d_export["total_sgst"] == 0 and d_export["total_igst"] == 0):
            raise AssertionError(f"Export invoice should be zero-GST: {d_export}")

        export_pdf = self.get_invoice_pdf_text(inv_export["id"]).upper()
        _contains_all(export_pdf, ["EXPORT INVOICE", f"IEC-{self.token}".upper()])

        invoice_page = _read_text(FRONTEND_DIR / "src/pages/InvoicesPage.tsx")
        _contains_all(
            invoice_page,
            [
                "export_invoice",
                "within_state",
                "other_states",
                "union_territory",
                "Import &amp; Export Code",
            ],
        )

    def check_dashboard_cashflow_filters(self) -> None:
        # DAS-002/003/004
        product = self.create_product(opening_stock=80)
        c1 = self.create_customer(country="India", business_type="domestic", shipping_complete=True)
        c2 = self.create_customer(country="India", business_type="domestic", shipping_complete=True)

        issued_invoice = self.create_invoice(
            customer_id=c1["id"],
            product_id=product["id"],
            invoice_type="within_state",
        )
        self.issue_invoice(issued_invoice["id"])

        # Draft invoice should not appear in cash in flow.
        self.create_invoice(
            customer_id=c2["id"],
            product_id=product["id"],
            invoice_type="within_state",
        )

        dashboard = self.api.request("GET", "/api/v1/reports/dashboard")
        cash = dashboard.get("cash_in_flow") or {}
        for bucket in ("daily", "weekly", "monthly"):
            rows = cash.get(bucket)
            if not isinstance(rows, list):
                raise AssertionError(f"cash_in_flow.{bucket} missing or invalid")

        daily_names = {row.get("customer_name") for row in cash["daily"]}
        weekly_names = {row.get("customer_name") for row in cash["weekly"]}
        monthly_names = {row.get("customer_name") for row in cash["monthly"]}

        if c1["company_name"] not in daily_names:
            raise AssertionError("Issued customer missing from daily cash flow")
        if c2["company_name"] in daily_names or c2["company_name"] in weekly_names or c2["company_name"] in monthly_names:
            raise AssertionError("Draft invoice customer should not appear in cash flow")

    def check_customer_features(self) -> None:
        # CUS-005/006/010/012/013/014/015/016/017/018/019/020/021/022/023/024/025
        customers_page = _read_text(FRONTEND_DIR / "src/pages/CustomersPage.tsx")
        _contains_all(
            customers_page,
            [
                "Credit Limit in Currency",
                "same_as_billing",
                "shipping_address_line1",
                "billing_country",
                "currency_code",
                "DEFAULT_PHONE_COUNTRY_CODES = ['+91', '+66', '+65'",
                "payment_terms_days: undefined",
            ],
        )

        options = self.api.request("GET", "/api/v1/customers/customization-options")
        if not options.get("countries") or not options.get("currencies"):
            raise AssertionError("Customer customization options missing countries/currencies")

        # CUS-010: billing address auto-copy from company profile.
        company = self.api.request("GET", "/api/v1/company")
        company_update = dict(company)
        company_update["name"] = company.get("name") or "My Company"
        company_update["address_line1"] = f"HQ-{self.token}"
        company_update["city"] = "Chennai"
        company_update["state"] = "Tamil Nadu"
        company_update["state_code"] = "TN"
        company_update["pincode"] = "600001"
        self.api.request("PUT", "/api/v1/company", expected=(200,), json_body=company_update)

        c_auto = self.api.request(
            "POST",
            "/api/v1/customers",
            expected=(201,),
            json_body={
                "customer_code": self._short_code("AUTO"),
                "company_name": self._unique("AUTO-CUST"),
                "customer_type": "regular",
                "phone": f"+91{random.randint(8000000000, 9999999999)}",
                "business_type": "domestic",
                "gstin_status": "non-registered",
                "same_as_billing": True,
                "currency_code": "INR",
                "payment_terms_days": None,
            },
        )
        if c_auto.get("billing_address_line1") != f"HQ-{self.token}":
            raise AssertionError("Customer billing address did not auto-copy from company profile")

        # CUS-006: country flows to invoice billing address (PDF text).
        c_country = self.create_customer(country="Singapore", business_type="international", shipping_complete=True)
        product = self.create_product(opening_stock=40)
        inv = self.create_invoice(
            customer_id=c_country["id"],
            product_id=product["id"],
            invoice_type="export_invoice",
        )
        pdf_text = self.get_invoice_pdf_text(inv["id"]).upper()
        if "SINGAPORE" not in pdf_text:
            raise AssertionError("Invoice PDF missing customer billing country")

    def check_supplier_features(self) -> None:
        # SUP-005/010/011/012/013
        suppliers_page = _read_text(FRONTEND_DIR / "src/pages/SuppliersPage.tsx")
        _contains_all(suppliers_page, ["Billing Address", "Currency", "billing_country", "currency_code"])
        if "supplier_state_code" in suppliers_page or "State Code" in suppliers_page:
            raise AssertionError("Supplier page still shows State Code field")

        s = self.create_supplier(payment_terms_days=21)
        if not s.get("currency_code"):
            raise AssertionError("Supplier currency_code missing")

        options = self.api.request("GET", "/api/v1/suppliers/customization-options")
        if not options.get("currencies"):
            raise AssertionError("Supplier customization currencies missing")

    def check_product_features(self) -> None:
        # PRO-001/002/004/005/014/015
        page = _read_text(FRONTEND_DIR / "src/pages/ProductsPage.tsx")
        _contains_all(
            page,
            [
                "Base Unit *",
                "TypeaheadInput",
                "Order Unit / Packing (optional)",
                "Base Unit Qty",
                "Min Safety Stock",
            ],
        )
        if "Opening Stock" in page:
            raise AssertionError("Opening Stock field still present in Products page")

        p = self.create_product(opening_stock=0, alt_mapping=True)
        if len(self.uom_ids) > 1 and not p.get("alt_uom_id"):
            raise AssertionError("Order Unit/Base Unit mapping not persisted")

    def check_purchase_grn_features(self) -> None:
        # PUR-003/004/005/006/007/008/009/010
        # GRN-002/004/005/007/012/013/014/015
        po_page = _read_text(FRONTEND_DIR / "src/pages/PurchaseOrderPage.tsx")
        _contains_all(
            po_page,
            [
                "Under Delivery Tolerance",
                "Over Delivery Tolerance",
                "newItem.gst_rate ?? ''",
                "e.target.value === '' ? undefined",
            ],
        )

        grn_page = _read_text(FRONTEND_DIR / "src/pages/GRNPage.tsx")
        _contains_all(
            grn_page,
            [
                "S.No",
                "itemSearchQuery",
                "MFG Date must be a past date",
                "expiry date must be a future date",
                "Partial (Confirmed)",
            ],
        )

        supplier = self.create_supplier(payment_terms_days=10)
        product = self.create_product(opening_stock=0)

        po = self.create_po(
            supplier_id=supplier["id"],
            product_id=product["id"],
            qty=10,
            under_tol=5,
            over_tol=15,
        )
        po_id = po["id"]

        # Draft PO PDF watermark and no GST % labels for totals.
        draft_pdf = self.get_po_pdf_text(po_id).upper()
        _contains_any(draft_pdf, ["NOT APPROVED", "DRAFT"])
        if re.search(r"CGST\s*%", draft_pdf) or re.search(r"SGST\s*%", draft_pdf):
            raise AssertionError("PO PDF still shows CGST/SGST with percent near footer")

        self.send_po(po_id)
        sent_pdf = self.get_po_pdf_text(po_id).upper()
        _contains_any(sent_pdf, ["APPROVED", "SENT"])

        # GRN-002 / GRN-007: future MFG blocked.
        future_day = (date.today() + timedelta(days=2)).isoformat()
        exp_future = (date.today() + timedelta(days=365)).isoformat()
        err = self.create_grn(
            supplier_id=supplier["id"],
            product_id=product["id"],
            qty=5,
            po_id=po_id,
            mfg_date=future_day,
            exp_date=exp_future,
            batch_no=self._unique("BATCH"),
            expected=(400,),
        )
        if "MFG Date must be a past date" not in json.dumps(err):
            raise AssertionError(f"Unexpected GRN MFG validation error: {err}")

        # Valid partial GRN and due date check.
        mfg_past = (date.today() - timedelta(days=120)).isoformat()
        exp_ok = (date.today() + timedelta(days=180)).isoformat()
        grn = self.create_grn(
            supplier_id=supplier["id"],
            product_id=product["id"],
            qty=5,
            po_id=po_id,
            mfg_date=mfg_past,
            exp_date=exp_ok,
            batch_no=self._unique("BATCH"),
        )
        grn_id = grn["id"]
        detail = self.get_grn_detail(grn_id)
        grn_data = detail["grn"]

        if float(grn_data.get("under_delivery_tolerance") or 0) != 5.0:
            raise AssertionError("PO under delivery tolerance did not flow to GRN")
        if float(grn_data.get("over_delivery_tolerance") or 0) != 15.0:
            raise AssertionError("PO over delivery tolerance did not flow to GRN")

        expected_due = (date.today() + timedelta(days=10)).isoformat()
        if grn_data.get("payment_due_date") != expected_due:
            raise AssertionError(
                f"GRN payment_due_date mismatch. expected={expected_due} actual={grn_data.get('payment_due_date')}"
            )

        self.confirm_grn(grn_id)
        confirmed = self.get_grn_detail(grn_id)
        if "Partial" not in (confirmed["grn"].get("status_display") or ""):
            raise AssertionError(f"GRN partial status display missing: {confirmed['grn'].get('status_display')}")

        # GRN-013/015: reject over-delivery beyond configured tolerance.
        too_high = self.create_grn(
            supplier_id=supplier["id"],
            product_id=product["id"],
            qty=21,
            po_id=po_id,
            mfg_date=mfg_past,
            exp_date=exp_ok,
            batch_no=self._unique("BATCH"),
            expected=(400,),
        )
        if "Over delivery exceeded allowed tolerance" not in json.dumps(too_high):
            raise AssertionError(f"Over-delivery tolerance did not trigger correctly: {too_high}")

    def check_sales_features(self) -> None:
        # SAL-010/017/018/020/026/032/033/034/035/036/040/041/042/043/044
        # SI-001/SI-002
        quotations_page = _read_text(FRONTEND_DIR / "src/pages/QuotationsPage.tsx")
        _contains_all(quotations_page, ["Send PDF", "sendQuotationEmail", "Download PDF"])

        invoices_page = _read_text(FRONTEND_DIR / "src/pages/InvoicesPage.tsx")
        _contains_all(
            invoices_page,
            [
                "MFG Date",
                "EXP Date",
                "MRP (₹)",
                "Packing Unit",
                "getInvoiceBatchOptions",
                "MFG date must be a past date",
                "EXP date must be a future date",
            ],
        )

        # SAL-026: due date manual override accepted.
        product = self.create_product(opening_stock=150)
        customer = self.create_customer(country="India", business_type="domestic", shipping_complete=True, payment_terms_days=45)
        manual_due = (date.today() + timedelta(days=7)).isoformat()
        inv = self.create_invoice(
            customer_id=customer["id"],
            product_id=product["id"],
            invoice_type="within_state",
            due_date=manual_due,
        )
        inv_detail = self.get_invoice_detail(inv["id"])["invoice"]
        if inv_detail.get("due_date") != manual_due:
            raise AssertionError("Invoice due date manual override not retained")

        # GRN-001 + SI-001: draft/approved watermark and tax labels on invoice PDF.
        draft_pdf = self.get_invoice_pdf_text(inv["id"]).upper()
        _contains_any(draft_pdf, ["NOT APPROVED", "DRAFT"])

        pdf_service = _read_text(BACKEND_DIR / "app/services/pdf_service.py")
        _contains_all(
            pdf_service,
            [
                'tax_col_1_label = "CGST"',
                'tax_col_2_label = "UTGST" if show_utgst else "SGST"',
                '>IGST</th>',
            ],
        )

        self.issue_invoice(inv["id"])
        issued_pdf = self.get_invoice_pdf_text(inv["id"]).upper()
        _contains_any(issued_pdf, ["APPROVED", "ISSUED"])

        # SAL-032/033 batch API includes MFG/EXP, and SAL-044 mismatch/date validation blocks create.
        supplier = self.create_supplier(payment_terms_days=15)
        po = self.create_po(
            supplier_id=supplier["id"],
            product_id=product["id"],
            qty=40,
            under_tol=25,
            over_tol=40,
        )
        self.send_po(po["id"])
        mfg = (date.today() - timedelta(days=200)).isoformat()
        exp = (date.today() + timedelta(days=200)).isoformat()
        grn = self.create_grn(
            supplier_id=supplier["id"],
            product_id=product["id"],
            qty=20,
            po_id=po["id"],
            mfg_date=mfg,
            exp_date=exp,
            batch_no=self._unique("INVBATCH"),
        )
        self.confirm_grn(grn["id"])

        options = self.api.request("GET", "/api/v1/invoices/batch-options", params={"product_id": product["id"]})
        items = options.get("items") or []
        if not items:
            raise AssertionError("Invoice batch options empty after GRN confirmation")
        first = items[0]
        if not first.get("manufacture_date") or not first.get("expiry_date"):
            raise AssertionError("Batch options missing manufacture/expiry dates")

        bad_create = self.api.request(
            "POST",
            "/api/v1/invoices",
            expected=(400,),
            json_body={
                "customer_id": customer["id"],
                "invoice_date": date.today().isoformat(),
                "invoice_type": "within_state",
                "items": [
                    {
                        "product_id": product["id"],
                        "quantity": 1,
                        "unit_price": 200,
                        "discount_percent": 0,
                        "gst_rate": 12,
                        "batch_no": "NON-EXISTENT-BATCH",
                        "manufacture_date": (date.today() - timedelta(days=10)).isoformat(),
                        "expiry_date": (date.today() + timedelta(days=10)).isoformat(),
                    }
                ],
            },
        )
        err_text = json.dumps(bad_create)
        if "Invalid batch selected" not in err_text and "MFG/EXP" not in err_text:
            raise AssertionError(f"Invalid batch/date validation not enforced: {bad_create}")

        # SAL-035/SAL-043 shipping validation on invoice creation.
        no_ship_customer = self.create_customer(
            country="India",
            business_type="domestic",
            shipping_complete=False,
            same_as_billing=False,
        )
        ship_err = self.api.request(
            "POST",
            "/api/v1/invoices",
            expected=(400,),
            json_body={
                "customer_id": no_ship_customer["id"],
                "invoice_date": date.today().isoformat(),
                "invoice_type": "within_state",
                "items": [
                    {
                        "product_id": product["id"],
                        "quantity": 1,
                        "unit_price": 200,
                        "discount_percent": 0,
                        "gst_rate": 12,
                    }
                ],
            },
        )
        if "Shipping Address" not in json.dumps(ship_err):
            raise AssertionError(f"Shipping validation not triggered: {ship_err}")

    def check_stock_features(self) -> None:
        # STO-001/002/004/005/006/007/008/009/010
        stock_page = _read_text(FRONTEND_DIR / "src/pages/StockPage.tsx")
        css = _read_text(FRONTEND_DIR / "src/index.css")
        _contains_all(stock_page, ["hms-low-stock-blink", "Batch No"])
        _contains_all(css, ["@keyframes hms-low-stock-blink", ".hms-low-stock-blink"])

        # Stock batch line expansion via reports stock endpoint.
        supplier = self.create_supplier(payment_terms_days=12)
        product = self.create_product(opening_stock=0)
        po = self.create_po(
            supplier_id=supplier["id"],
            product_id=product["id"],
            qty=30,
            under_tol=25,
            over_tol=60,
        )
        self.send_po(po["id"])

        mfg = (date.today() - timedelta(days=150)).isoformat()
        exp = (date.today() + timedelta(days=150)).isoformat()

        grn1 = self.create_grn(
            supplier_id=supplier["id"],
            product_id=product["id"],
            qty=10,
            po_id=po["id"],
            mfg_date=mfg,
            exp_date=exp,
            batch_no=self._unique("B1"),
        )
        self.confirm_grn(grn1["id"])

        grn2 = self.create_grn(
            supplier_id=supplier["id"],
            product_id=product["id"],
            qty=8,
            po_id=po["id"],
            mfg_date=mfg,
            exp_date=exp,
            batch_no=self._unique("B2"),
        )
        self.confirm_grn(grn2["id"])

        stock_report = self.api.request("GET", "/api/v1/reports/stock")
        rows = [r for r in (stock_report.get("items") or []) if r.get("product_code") == product.get("product_code")]
        batch_values = {r.get("batch_no") for r in rows if r.get("batch_no")}
        if len(batch_values) < 1:
            raise AssertionError("Stock report did not return batch-wise rows for the product")

        reports_router = _read_text(BACKEND_DIR / "app/routers/reports.py")
        _contains_all(
            reports_router,
            [
                "for batch_no, manufacture_date, expiry_date, batch_qty in product_batches:",
                '"batch_no": None if batch_no == NO_BATCH_TOKEN else batch_no',
            ],
        )

        # Inventory count module and difference admin endpoint.
        preview = self.api.request("GET", "/api/v1/stock/inventory-counts/next-number")
        if not re.match(r"^INV-[A-Z]{3}-\d{3}$", preview.get("count_number", "")):
            raise AssertionError(f"Inventory count number format invalid: {preview}")

        inv_count = self.api.request(
            "POST",
            "/api/v1/stock/inventory-counts",
            expected=(201,),
            json_body={
                "count_date": date.today().isoformat(),
                "count_performed_by": "Admin QA",
                "items": [
                    {
                        "serial_number": 1,
                        "product_id": product["id"],
                        "product_description": "Cycle count",
                        "quantity": 5,
                        "batch_no": next(iter(batch_values)),
                        "manufacture_date": mfg,
                        "expiry_date": exp,
                    }
                ],
            },
        )
        diff = self.api.request(
            "GET",
            f"/api/v1/stock/inventory-counts/{inv_count['count_number']}/difference",
            expected=(200,),
        )
        if diff.get("total_items", 0) < 1:
            raise AssertionError("Inventory count difference endpoint returned no items")

    def check_payables_features(self) -> None:
        # PAY-001/PAY-002/PAY-006
        supplier = self.create_supplier(payment_terms_days=20)
        product = self.create_product(opening_stock=0)

        po = self.create_po(
            supplier_id=supplier["id"],
            product_id=product["id"],
            qty=12,
            under_tol=5,
            over_tol=20,
        )
        self.send_po(po["id"])

        mfg = (date.today() - timedelta(days=90)).isoformat()
        exp = (date.today() + timedelta(days=240)).isoformat()
        grn = self.create_grn(
            supplier_id=supplier["id"],
            product_id=product["id"],
            qty=10,
            po_id=po["id"],
            mfg_date=mfg,
            exp_date=exp,
            batch_no=self._unique("PAYB"),
        )
        self.confirm_grn(grn["id"])

        # Advance payment requires PO number metadata and should be reflected in list.
        advance = self.record_payment(
            {
                "payment_type": "payment",
                "party_type": "supplier",
                "supplier_id": supplier["id"],
                "purchase_order_id": po["id"],
                "payment_date": date.today().isoformat(),
                "amount": 300,
                "payment_mode": "bank_transfer",
                "notes": "Advance against PO",
                "allocations": [],
            }
        )
        self.update_payment_status(advance["id"], "cleared")

        # PAY-006: block payment exceeding GRN value/remaining.
        over_alloc = self.record_payment(
            {
                "payment_type": "payment",
                "party_type": "supplier",
                "supplier_id": supplier["id"],
                "purchase_order_id": po["id"],
                "payment_date": date.today().isoformat(),
                "amount": 999999,
                "payment_mode": "bank_transfer",
                "notes": "Over allocation test",
                "allocations": [
                    {
                        "purchase_grn_id": grn["id"],
                        "allocated_amount": 999999,
                    }
                ],
            },
            expected=(400,),
        )
        if "exceeds remaining payable" not in json.dumps(over_alloc):
            raise AssertionError(f"Expected PAY-006 validation error missing: {over_alloc}")

        # Valid GRN payment for list field checks.
        valid = self.record_payment(
            {
                "payment_type": "payment",
                "party_type": "supplier",
                "supplier_id": supplier["id"],
                "purchase_order_id": po["id"],
                "payment_date": date.today().isoformat(),
                "amount": 200,
                "payment_mode": "bank_transfer",
                "notes": "Valid GRN allocation",
                "allocations": [
                    {
                        "purchase_grn_id": grn["id"],
                        "allocated_amount": 200,
                    }
                ],
            }
        )
        self.update_payment_status(valid["id"], "cleared")

        payments = self.api.request("GET", "/api/v1/payments", params={"party_type": "supplier", "supplier_id": supplier["id"]})
        rows = payments.get("items") or []
        if not rows:
            raise AssertionError("No payables rows returned for supplier")

        found_po = False
        found_grn_value = False
        found_status_display = False
        for row in rows:
            if row.get("po_number"):
                found_po = True
            if row.get("grn_value") is not None:
                found_grn_value = True
            if row.get("status_display") in {"Advance Payment Cleared", "Full Payment Cleared", "Cleared"}:
                found_status_display = True

        if not found_po:
            raise AssertionError("PAY-001 failed: PO Number not shown in payables list")
        if not found_grn_value:
            raise AssertionError("PAY-002 failed: GRN Value not shown in payables list")
        if not found_status_display:
            raise AssertionError("Payables status display tokens not returned")


def run_suite() -> int:
    suite = ClosureSuite()
    tc_ids = suite.load_non_pass_ids()
    result = SuiteResult(tc_ids=tc_ids)

    suite.bootstrap()

    checks: list[tuple[str, list[str], Any]] = [
        (
            "company-invoice-types-export",
            ["COM-001", "SAL-029", "SAL-030", "SAL-031", "SAL-037", "SAL-038", "SAL-039"],
            suite.check_company_invoice_types_export,
        ),
        (
            "dashboard-cashflow-filters",
            ["DAS-002", "DAS-003", "DAS-004"],
            suite.check_dashboard_cashflow_filters,
        ),
        (
            "customer-features",
            [
                "CUS-005", "CUS-006", "CUS-010", "CUS-012", "CUS-013", "CUS-014", "CUS-015", "CUS-016",
                "CUS-017", "CUS-018", "CUS-019", "CUS-020", "CUS-021", "CUS-022", "CUS-023", "CUS-024", "CUS-025",
            ],
            suite.check_customer_features,
        ),
        (
            "supplier-features",
            ["SUP-005", "SUP-010", "SUP-011", "SUP-012", "SUP-013"],
            suite.check_supplier_features,
        ),
        (
            "product-features",
            ["PRO-001", "PRO-002", "PRO-004", "PRO-005", "PRO-014", "PRO-015"],
            suite.check_product_features,
        ),
        (
            "purchase-grn-features",
            [
                "PUR-003", "PUR-004", "PUR-005", "PUR-006", "PUR-007", "PUR-008", "PUR-009", "PUR-010",
                "GRN-002", "GRN-003", "GRN-004", "GRN-005", "GRN-007", "GRN-012", "GRN-013", "GRN-014", "GRN-015",
            ],
            suite.check_purchase_grn_features,
        ),
        (
            "sales-features",
            [
                "GRN-001",
                "SAL-010", "SAL-017", "SAL-018", "SAL-020", "SAL-026", "SAL-032", "SAL-033", "SAL-034", "SAL-035",
                "SAL-036", "SAL-040", "SAL-041", "SAL-042", "SAL-043", "SAL-044", "SI-001", "SI-002",
            ],
            suite.check_sales_features,
        ),
        (
            "stock-features",
            ["STO-001", "STO-002", "STO-004", "STO-005", "STO-006", "STO-007", "STO-008", "STO-009", "STO-010"],
            suite.check_stock_features,
        ),
        (
            "payables-features",
            ["PAY-001", "PAY-002", "PAY-006"],
            suite.check_payables_features,
        ),
    ]

    for check_name, ids, fn in checks:
        try:
            fn()
            result.mark(ids, True, check_name, "Validated")
            print(f"[PASS] {check_name} -> {', '.join(ids)}")
        except Exception as exc:
            detail = str(exc)
            result.mark(ids, False, check_name, detail)
            print(f"[FAIL] {check_name} -> {detail}")

    result.finalize_uncovered()

    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "summary": result.summary(),
        "results": {
            tc_id: {
                "status": r.status,
                "check_name": r.check_name,
                "detail": r.detail,
            }
            for tc_id, r in sorted(result.results.items())
        },
    }

    REPORT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        "# Full Non-Pass Closure Report",
        "",
        f"Generated At: {payload['generated_at']}",
        "",
        "## Summary",
        "",
        f"- Total TC IDs: {payload['summary']['total']}",
        f"- Passed: {payload['summary']['passed']}",
        f"- Failed: {payload['summary']['failed']}",
        f"- Pass Rate: {payload['summary']['pass_rate']}%",
        "",
        "## TC Results",
        "",
        "| TC ID | Status | Check | Detail |",
        "|---|---|---|---|",
    ]
    for tc_id, r in sorted(result.results.items()):
        detail = (r.detail or "").replace("|", "\\|")
        lines.append(f"| {tc_id} | {r.status} | {r.check_name} | {detail} |")

    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"\nWrote: {REPORT_JSON}")
    print(f"Wrote: {REPORT_MD}")
    print(f"Summary: {payload['summary']}")

    return 0 if payload["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(run_suite())
