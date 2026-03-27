import httpx
import json
import logging
import random
from datetime import date
from fastapi.testclient import TestClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("e2e_test")

from app.main import app
from app.database import get_db, SessionLocal
from app.dependencies import get_current_user
from app.models.user import User

# Mock User
class MockUser:
    role = "admin"
    permission_overrides = []

    def __init__(self):
        db = SessionLocal()
        user = db.query(User).first()
        db.close()
        self.id = str(user.id) if user else "123e4567-e89b-12d3-a456-426614174000"

def mock_get_current_user():
    return MockUser()

app.dependency_overrides[get_current_user] = mock_get_current_user

client = TestClient(app)

def run_tests():
    logger.info("Starting E2E verification tests...")

    rand_suffix = random.randint(1000, 9999)
    phone_suffix = random.randint(10000000, 99999999)
    
    # 1. Create Supplier
    supplier_payload = {
        "company_name": f"Test Supplier Corp {rand_suffix}",
        "phone": f"99{phone_suffix}",
        "email": f"supplier{rand_suffix}@test.com",
        "gstin": f"22AAAAA{rand_suffix}A1Z5",
        "opening_balance": 0,
        "opening_balance_type": "cr",
        "is_active": True
    }
    logger.info("Creating Supplier...")
    res = client.post("/api/v1/suppliers", json=supplier_payload)
    assert res.status_code in (200, 201), f"Supplier creation failed: {res.text}"
    supplier = res.json()
    supplier_id = supplier["id"]
    logger.info(f"Supplier created: {supplier_id}")

    # 2. Create Customer
    rand_suffix2 = random.randint(1000, 9999)
    phone_suffix2 = random.randint(10000000, 99999999)
    customer_payload = {
        "company_name": f"Test Customer LLC {rand_suffix2}",
        "phone": f"98{phone_suffix2}",
        "email": f"customer{rand_suffix2}@test.com",
        "customer_type": "regular",
        "gstin": f"22BBBBB{rand_suffix2}B1Z5",
        "opening_balance": 0,
        "opening_balance_type": "dr",
        "is_active": True,
        "same_as_billing": True
    }
    logger.info("Creating Customer...")
    res = client.post("/api/v1/customers", json=customer_payload)
    assert res.status_code in (200, 201), f"Customer creation failed: {res.text}"
    customer = res.json()
    customer_id = customer["id"]
    logger.info(f"Customer created: {customer_id}")

    # 2.5 Get or Create Category
    logger.info("Fetching Categories...")
    res = client.get("/api/v1/products/categories")
    assert res.status_code in (200, 201)
    categories = res.json()
    if not categories:
        res = client.post("/api/v1/products/categories", json={"name": f"E2E Cat {rand_suffix2}"})
        assert res.status_code in (200, 201)
        category_id = res.json()["id"]
    else:
        category_id = categories[0]["id"]
        
    # 2.6 Get UOM
    logger.info("Fetching UOMs...")
    res = client.get("/api/v1/products/uom")
    assert res.status_code in (200, 201)
    uoms = res.json()
    if not uoms:
        logger.info("Seeding UOM directly into database...")
        db = SessionLocal()
        from app.models.product import UnitOfMeasure
        uom = UnitOfMeasure(name="Pieces", abbreviation="PCS")
        db.add(uom)
        db.commit()
        db.refresh(uom)
        uom_id = str(uom.id)
        db.close()
    else:
        uom_id = uoms[0]["id"]

    # 3. Create Product
    product_payload = {
        "name": f"Test Widget E2E {rand_suffix}",
        "category_id": category_id,
        "uom_id": uom_id,
        "hsn_code": "123456",
        "mrp": 10000,
        "selling_price": 9000,
        "purchase_price": 5000,
        "gst_rate": 18,
        "minimum_stock": 10,
        "is_active": True
    }
    logger.info("Creating Product...")
    res = client.post("/api/v1/products", json=product_payload)
    assert res.status_code in (200, 201), f"Product creation failed: {res.text}"
    product = res.json()
    product_id = product["id"]
    logger.info(f"Product created: {product_id}")

    # === PURCHASE CYCLE ===
    
    # 4. Create PO
    po_payload = {
        "supplier_id": supplier_id,
        "order_date": date.today().isoformat(),
        "status": "draft",
        "items": [
            {
                "product_id": product_id,
                "quantity": 50,
                "unit_price": 5000,
                "discount_percent": 0,
                "gst_rate": 18
            }
        ]
    }
    logger.info("Creating Purchase Order...")
    res = client.post("/api/v1/purchase-orders", json=po_payload)
    assert res.status_code in (200, 201), f"PO creation failed: {res.text}"
    po = res.json()
    po_id = po["id"]
    po_item_id = po["items"][0]["id"] if "items" in po and po["items"] else None
    logger.info(f"PO created: {po_id}")

    # (Optional) Update PO Status to sent
    res = client.patch(f"/api/v1/purchase-orders/{po_id}/status", json={"status": "sent"})
    assert res.status_code in (200, 201)

    # 5. Create GRN
    grn_payload = {
        "purchase_order_id": po_id,
        "supplier_id": supplier_id,
        "supplier_invoice_number": f"INV-SUP-{rand_suffix}",
        "supplier_invoice_date": date.today().isoformat(),
        "receipt_date": date.today().isoformat(),
        "notes": "E2E Test GRN",
        "items": [
            {
                "product_id": product_id,
                "purchase_order_item_id": po_item_id,
                "quantity": 50,
                "unit_price": 5000,
                "discount_percent": 0,
                "gst_rate": 18
            }
        ]
    }
    logger.info("Creating GRN...")
    res = client.post("/api/v1/grn", json=grn_payload)
    assert res.status_code in (200, 201), f"GRN creation failed: {res.text}"
    grn = res.json()
    grn_id = grn["id"]
    logger.info(f"GRN created: {grn_id}")

    # 6. Confirm GRN (should increase stock)
    logger.info("Confirming GRN...")
    res = client.post(f"/api/v1/grn/{grn_id}/confirm")
    assert res.status_code in (200, 201), f"GRN confirmation failed: {res.text}"

    # 7. Check Stock
    res = client.get("/api/v1/reports/stock")
    assert res.status_code in (200, 201)
    stock_items = res.json()["items"]
    product_stock = next((s for s in stock_items if str(s["product_name"]) == str(product_payload["name"])), None)
    assert product_stock is not None
    assert product_stock["closing_qty"] == 50, f"Expected 50 stock, got {product_stock['closing_qty']}"
    logger.info("Purchase cycle passed - stock correctly increased to 50.")

    # === SALES CYCLE ===

    # 8. Create Quotation
    q_payload = {
        "customer_id": customer_id,
        "quotation_date": date.today().isoformat(),
        "valid_until": date.today().isoformat(),
        "status": "draft",
        "items": [
            {
                "product_id": product_id,
                "quantity": 20,
                "unit_price": 9000,
                "discount_percent": 0,
                "gst_rate": 18
            }
        ]
    }
    logger.info("Creating Quotation...")
    res = client.post("/api/v1/quotations", json=q_payload)
    assert res.status_code in (200, 201), f"Quotation creation failed: {res.text}"
    q = res.json()
    q_id = q["id"]
    logger.info(f"Quotation created: {q_id}")

    # 9. Update Quotation Status to accepted
    res = client.patch(f"/api/v1/quotations/{q_id}/status", json={"status": "sent"})
    assert res.status_code in (200, 201)
    res = client.patch(f"/api/v1/quotations/{q_id}/status", json={"status": "accepted"})
    assert res.status_code in (200, 201)

    # 10. Convert to Sales Order
    logger.info("Converting Quotation to Sales Order...")
    res = client.post(f"/api/v1/quotations/{q_id}/convert-to-so")
    assert res.status_code in (200, 201), f"Conversion failed: {res.text}"
    so = res.json()
    so_id = so["id"]
    logger.info(f"Sales Order created: {so_id}")

    # 11. Create Invoice
    inv_payload = {
        "sales_order_id": so_id,
        "quotation_id": q_id,
        "customer_id": customer_id,
        "invoice_date": date.today().isoformat(),
        "due_date": date.today().isoformat(),
        "supply_state": "Tamil Nadu",
        "supply_state_code": "33",
        "is_igst": False,
        "items": [
            {
                "product_id": product_id,
                "quantity": 20,
                "unit_price": 9000,
                "discount_percent": 0,
                "gst_rate": 18
            }
        ]
    }
    logger.info("Creating Invoice...")
    res = client.post("/api/v1/invoices", json=inv_payload)
    assert res.status_code in (200, 201), f"Invoice creation failed: {res.text}"
    inv = res.json()
    inv_id = inv["id"]
    logger.info(f"Invoice created: {inv_id}")

    # 12. Issue Invoice (should decrease stock)
    logger.info("Issuing Invoice...")
    res = client.post(f"/api/v1/invoices/{inv_id}/issue")
    assert res.status_code in (200, 201), f"Invoice issuance failed: {res.text}"

    # 13. Check Stock Again
    res = client.get("/api/v1/reports/stock")
    assert res.status_code in (200, 201)
    stock_items = res.json()["items"]
    product_stock = next((s for s in stock_items if str(s["product_name"]) == str(product_payload["name"])), None)
    assert product_stock is not None
    assert product_stock["closing_qty"] == 30, f"Expected 30 stock, got {product_stock['closing_qty']}"
    logger.info("Sales cycle passed - stock correctly decreased to 30.")

    logger.info("ALL E2E TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    run_tests()
