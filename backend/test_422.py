from fastapi.testclient import TestClient
from app.main import app
from app.dependencies import get_current_user
from app.models.user import User

from app.database import SessionLocal

def override_get_current_user():
    db = SessionLocal()
    db_user = db.query(User).first()
    db.close()
    
    if not db_user:
        raise Exception("No users found in database")
        
    user = User(
        id=db_user.id,
        email=db_user.email,
        is_active=True,
        role="admin"
    )
    user.effective_access = {
        "customers_write": True,
        "purchase_orders_write": True
    }
    return user

app.dependency_overrides[get_current_user] = override_get_current_user
client = TestClient(app)

# Test Customer Creation
def test_create_customer():
    print("Testing Customer Creation...")
    payload = {
        "company_name": "Test Company",
        "customer_type": "regular",
        "phone": "9000000001",
        "alternate_phone": "",
        "email": "",
        "gstin": "",
        "pan": "",
        "billing_address_line1": "123 Test St",
        "billing_address_line2": "",
        "billing_city": "Test",
        "billing_state": "Test",
        "billing_state_code": "29",
        "billing_pincode": "560001",
        "shipping_address_line1": "",
        "shipping_address_line2": "",
        "shipping_city": "",
        "shipping_state": "",
        "shipping_state_code": "",
        "shipping_pincode": "",
        "same_as_billing": True,
        "credit_limit": 10000,
        "payment_terms_days": 30,
        "opening_balance": 0,
        "opening_balance_type": "dr",
        "is_active": True
    }
    
    res = client.post("/api/v1/customers", json=payload)
    print("Customer Creation Status:", res.status_code)
    print("Response:", res.json())

# Test PO Creation
def test_create_po():
    print("\nTesting PO Creation...")
    payload = {
        "supplier_id": "00000000-0000-0000-0000-000000000000",
        "order_date": "2024-03-27",
        "expected_delivery_date": "",
        "notes": "",
        "status": "draft",
        "items": [
            {
                "product_id": "00000000-0000-0000-0000-000000000000",
                "description": "",
                "quantity": 10,
                "unit_price": 5000,
                "discount_percent": 0,
                "gst_rate": 18
            }
        ]
    }
    
    res = client.post("/api/v1/purchase-orders", json=payload)
    print("PO Creation Status:", res.status_code)
    print("Response:", res.json())

if __name__ == "__main__":
    test_create_customer()
    test_create_po()
