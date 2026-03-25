"""End-to-end API smoke test for implemented workflows (WF-01 to WF-06)."""
import json
import sys
import urllib.request
import urllib.error
from datetime import date

BASE_URL = "http://localhost:8000"


def call(method: str, path: str, body=None, token: str | None = None):
    headers = {}
    data = None
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(
        url=f"{BASE_URL}{path}",
        data=data,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = response.read().decode("utf-8", errors="replace")
            return response.status, payload
    except urllib.error.HTTPError as error:
        payload = error.read().decode("utf-8", errors="replace")
        return error.code, payload


def expect(name: str, condition: bool, detail: str):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}: {detail}")
    if not condition:
        raise RuntimeError(f"{name} failed: {detail}")


try:
    # 1) Health
    code, body = call("GET", "/health")
    expect("Health endpoint", code == 200, f"status={code}")

    # 2) Login
    code, body = call("POST", "/api/v1/auth/login", {
        "email": "admin@company.com",
        "password": "Admin@123",
    })
    expect("Login endpoint", code == 200, f"status={code}")
    login_data = json.loads(body)
    token = login_data["access_token"]

    # 3) Company profile
    code, body = call("GET", "/api/v1/company", token=token)
    expect("Get company", code == 200, f"status={code}")

    update_payload = json.loads(body)
    update_payload["name"] = "IMS Demo Company"
    update_payload["state_code"] = "29"
    code, body = call("PUT", "/api/v1/company", update_payload, token=token)
    expect("Update company", code == 200, f"status={code}")

    # 4) Categories + UOM
    code, body = call("GET", "/api/v1/products/categories", token=token)
    expect("List categories", code == 200, f"status={code}")
    categories = json.loads(body)
    if not categories:
        code, body = call("POST", "/api/v1/products/categories", {
            "name": "General",
            "description": "General products",
        }, token=token)
        expect("Create category", code == 201, f"status={code}")
        category_id = json.loads(body)["id"]
    else:
        category_id = categories[0]["id"]

    code, body = call("GET", "/api/v1/products/uom", token=token)
    expect("List UOM", code == 200, f"status={code}")
    uom_items = json.loads(body)
    expect("UOM seeded", len(uom_items) > 0, f"count={len(uom_items)}")
    uom_id = uom_items[0]["id"]

    # 5) Product create
    code, body = call("POST", "/api/v1/products", {
        "name": f"E2E Product {date.today().isoformat()}",
        "category_id": category_id,
        "uom_id": uom_id,
        "hsn_code": "123456",
        "gst_rate": 18,
        "purchase_price": 10000,
        "selling_price": 12000,
        "mrp": 12500,
        "minimum_stock": 2,
        "opening_stock": 1,
        "is_active": True,
    }, token=token)
    if code == 201:
        product = json.loads(body)
    else:
        # Reuse first existing product if duplicate/validation collisions arise from repeated runs.
        code2, body2 = call("GET", "/api/v1/products", token=token)
        expect("List products fallback", code2 == 200, f"status={code2}")
        items = json.loads(body2)["items"]
        expect("Existing product available", len(items) > 0, f"count={len(items)}")
        product = items[0]
    product_id = product["id"]

    # 6) Supplier create
    supplier_payload = {
        "company_name": f"E2E Supplier {date.today().isoformat()}",
        "phone": "9000000001",
        "gstin": "29ABCDE1234F1Z6",
        "opening_balance_type": "cr",
        "is_active": True,
    }
    code, body = call("POST", "/api/v1/suppliers", supplier_payload, token=token)
    if code == 201:
        supplier = json.loads(body)
    else:
        code2, body2 = call("GET", "/api/v1/suppliers", token=token)
        expect("List suppliers fallback", code2 == 200, f"status={code2}")
        items = json.loads(body2)["items"]
        expect("Existing supplier available", len(items) > 0, f"count={len(items)}")
        supplier = items[0]
    supplier_id = supplier["id"]

    # 7) Customer create + duplicate GSTIN check
    customer_payload = {
        "company_name": f"E2E Customer {date.today().isoformat()}",
        "phone": "9000000002",
        "gstin": "29ABCDE1234F1Z5",
        "customer_type": "regular",
        "same_as_billing": True,
        "opening_balance_type": "dr",
        "is_active": True,
    }
    code, body = call("POST", "/api/v1/customers", customer_payload, token=token)
    expect("Customer duplicate GSTIN rule", code in {201, 400}, f"status={code}")

    # 8) Purchase Order create
    po_payload = {
        "supplier_id": supplier_id,
        "order_date": date.today().isoformat(),
        "status": "draft",
        "items": [
            {
                "product_id": product_id,
                "description": product["name"],
                "quantity": 2,
                "unit_price": product["purchase_price"],
                "discount_percent": 0,
                "gst_rate": product["gst_rate"],
            }
        ],
    }
    code, body = call("POST", "/api/v1/purchase-orders", po_payload, token=token)
    expect("Create purchase order", code == 200, f"status={code}")
    po = json.loads(body)
    po_id = po["id"]

    # 9) GRN create + confirm (stock increase)
    code, before_body = call("GET", f"/api/v1/products/{product_id}", token=token)
    expect("Get product before GRN", code == 200, f"status={code}")
    before_stock = float(json.loads(before_body).get("current_stock", 0))

    grn_payload = {
        "supplier_id": supplier_id,
        "purchase_order_id": po_id,
        "receipt_date": date.today().isoformat(),
        "items": [
            {
                "product_id": product_id,
                "quantity": 1,
                "unit_price": product["purchase_price"],
                "discount_percent": 0,
                "gst_rate": product["gst_rate"],
                "purchase_order_item_id": None,
            }
        ],
    }
    code, body = call("POST", "/api/v1/grn", grn_payload, token=token)
    expect("Create GRN", code == 200, f"status={code}")
    grn_id = json.loads(body)["id"]

    code, body = call("POST", f"/api/v1/grn/{grn_id}/confirm", {}, token=token)
    expect("Confirm GRN", code == 200, f"status={code}")

    code, after_body = call("GET", f"/api/v1/products/{product_id}", token=token)
    expect("Get product after GRN", code == 200, f"status={code}")
    after_stock = float(json.loads(after_body).get("current_stock", 0))
    expect("Stock increased after GRN confirm", after_stock >= before_stock + 1, f"before={before_stock}, after={after_stock}")

    # 10) Quotation -> Sales Order conversion
    code, body = call("GET", "/api/v1/customers", token=token)
    expect("List customers for sales flow", code == 200, f"status={code}")
    customer_items = json.loads(body)["items"]
    expect("Customer exists for sales flow", len(customer_items) > 0, f"count={len(customer_items)}")
    customer_id = customer_items[0]["id"]

    quotation_payload = {
        "customer_id": customer_id,
        "quotation_date": date.today().isoformat(),
        "status": "draft",
        "items": [
            {
                "product_id": product_id,
                "description": product["name"],
                "quantity": 1,
                "unit_price": product["selling_price"],
                "discount_percent": 0,
                "gst_rate": product["gst_rate"],
            }
        ],
    }
    code, body = call("POST", "/api/v1/quotations", quotation_payload, token=token)
    expect("Create quotation", code == 200, f"status={code}")
    quotation_id = json.loads(body)["id"]

    code, body = call("PATCH", f"/api/v1/quotations/{quotation_id}/status", {"status": "sent"}, token=token)
    expect("Mark quotation sent", code == 200, f"status={code}")

    code, body = call("POST", f"/api/v1/quotations/{quotation_id}/convert-to-so", {}, token=token)
    expect("Convert quotation to sales order", code == 200, f"status={code}")
    so_id = json.loads(body)["id"]

    code, body = call("PATCH", f"/api/v1/sales-orders/{so_id}/status", {"status": "confirmed"}, token=token)
    expect("Confirm sales order", code == 200, f"status={code}")

    # 11) Invoice issue should deduct stock
    code, before_invoice_stock_body = call("GET", f"/api/v1/products/{product_id}", token=token)
    expect("Get product before invoice issue", code == 200, f"status={code}")
    before_invoice_stock = float(json.loads(before_invoice_stock_body).get("current_stock", 0))

    invoice_payload = {
        "customer_id": customer_id,
        "sales_order_id": so_id,
        "invoice_date": date.today().isoformat(),
        "is_igst": False,
        "items": [
            {
                "product_id": product_id,
                "description": product["name"],
                "quantity": 1,
                "unit_price": product["selling_price"],
                "discount_percent": 0,
                "gst_rate": product["gst_rate"],
            }
        ],
    }
    code, body = call("POST", "/api/v1/invoices", invoice_payload, token=token)
    expect("Create invoice", code == 200, f"status={code}")
    invoice = json.loads(body)
    invoice_id = invoice["id"]

    code, body = call("POST", f"/api/v1/invoices/{invoice_id}/issue", {}, token=token)
    expect("Issue invoice", code == 200, f"status={code}")

    code, after_invoice_stock_body = call("GET", f"/api/v1/products/{product_id}", token=token)
    expect("Get product after invoice issue", code == 200, f"status={code}")
    after_invoice_stock = float(json.loads(after_invoice_stock_body).get("current_stock", 0))
    expect(
        "Stock decreased after invoice issue",
        after_invoice_stock <= before_invoice_stock - 1,
        f"before={before_invoice_stock}, after={after_invoice_stock}",
    )

    # 12) Payment allocation should reduce outstanding and cancellation should reverse
    code, body = call("POST", "/api/v1/payments", {
        "payment_type": "receipt",
        "party_type": "customer",
        "customer_id": customer_id,
        "payment_date": date.today().isoformat(),
        "amount": invoice["amount_due"],
        "payment_mode": "cash",
        "allocations": [
            {
                "invoice_id": invoice_id,
                "allocated_amount": invoice["amount_due"],
            }
        ],
    }, token=token)
    expect("Create payment", code == 200, f"status={code}")
    payment_id = json.loads(body)["id"]

    code, body = call("GET", f"/api/v1/invoices/{invoice_id}", token=token)
    expect("Get invoice after payment", code == 200, f"status={code}")
    invoice_after_payment = json.loads(body)["invoice"]
    expect(
        "Invoice due reduced by payment",
        int(invoice_after_payment["amount_due"]) == 0,
        f"amount_due={invoice_after_payment['amount_due']}",
    )

    code, body = call("PATCH", f"/api/v1/payments/{payment_id}/status", {"status": "cancelled"}, token=token)
    expect("Cancel payment", code == 200, f"status={code}")

    code, body = call("GET", f"/api/v1/invoices/{invoice_id}", token=token)
    expect("Get invoice after payment cancellation", code == 200, f"status={code}")
    invoice_after_cancel = json.loads(body)["invoice"]
    expect(
        "Invoice due restored after cancellation",
        int(invoice_after_cancel["amount_due"]) >= int(invoice["amount_due"]),
        f"amount_due={invoice_after_cancel['amount_due']}",
    )

    # 13) Reports should be reachable and return data shape
    code, body = call("GET", "/api/v1/reports/dashboard", token=token)
    expect("Dashboard report", code == 200, f"status={code}")
    dashboard_payload = json.loads(body)
    expect("Dashboard has key metrics", "today_sales" in dashboard_payload, "today_sales present")

    code, body = call("GET", "/api/v1/reports/stock", token=token)
    expect("Stock report", code == 200, f"status={code}")

    today_str = date.today().isoformat()
    code, body = call("GET", f"/api/v1/reports/sales?from_date={today_str}&to_date={today_str}", token=token)
    expect("Sales report", code == 200, f"status={code}")

    code, body = call("GET", f"/api/v1/reports/purchase?from_date={today_str}&to_date={today_str}", token=token)
    expect("Purchase report", code == 200, f"status={code}")

    code, body = call("GET", "/api/v1/reports/outstanding-receivables", token=token)
    expect("Outstanding receivables report", code == 200, f"status={code}")

    code, body = call("GET", "/api/v1/reports/outstanding-payables", token=token)
    expect("Outstanding payables report", code == 200, f"status={code}")

    code, body = call("GET", f"/api/v1/reports/gstr1?from_date={today_str}&to_date={today_str}", token=token)
    expect("GSTR-1 report", code == 200, f"status={code}")

    code, body = call("GET", f"/api/v1/reports/gstr3b?from_date={today_str}&to_date={today_str}", token=token)
    expect("GSTR-3B report", code == 200, f"status={code}")

    code, body = call("GET", f"/api/v1/reports/pl?from_date={today_str}&to_date={today_str}", token=token)
    expect("P&L report", code == 200, f"status={code}")

    # 14) Sales return confirm should restore stock
    code, body = call("GET", f"/api/v1/invoices/{invoice_id}", token=token)
    expect("Get invoice detail", code == 200, f"status={code}")
    invoice_items = json.loads(body)["items"]
    expect("Invoice item exists", len(invoice_items) > 0, f"count={len(invoice_items)}")
    invoice_item_id = invoice_items[0]["id"]

    return_payload = {
        "invoice_id": invoice_id,
        "customer_id": customer_id,
        "return_date": date.today().isoformat(),
        "reason": "E2E return check",
        "items": [
            {
                "product_id": product_id,
                "invoice_item_id": invoice_item_id,
                "quantity": 1,
                "unit_price": product["selling_price"],
                "gst_rate": product["gst_rate"],
            }
        ],
    }
    code, body = call("POST", "/api/v1/sales-returns", return_payload, token=token)
    expect("Create sales return", code == 200, f"status={code}")
    sales_return_id = json.loads(body)["id"]

    code, body = call("POST", f"/api/v1/sales-returns/{sales_return_id}/confirm", {}, token=token)
    expect("Confirm sales return", code == 200, f"status={code}")

    code, final_stock_body = call("GET", f"/api/v1/products/{product_id}", token=token)
    expect("Get product after sales return", code == 200, f"status={code}")
    final_stock = float(json.loads(final_stock_body).get("current_stock", 0))
    expect("Stock restored after sales return", final_stock >= after_invoice_stock + 1, f"after_invoice={after_invoice_stock}, final={final_stock}")

    print("\nEND-TO-END RESULT: PASS")
except Exception as exc:
    print(f"\nEND-TO-END RESULT: FAIL - {exc}")
    sys.exit(1)
