"""Database seeding script - creates initial data."""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.database import SessionLocal, engine, Base
from app.models.user import User
from app.models.supplier import Supplier
from app.models.product import Product, UnitOfMeasure
from app.models.company import Company
from app.services.auth_service import hash_password
from datetime import datetime

def seed_database():
    """Create initial database records."""

    # Create all tables
    Base.metadata.create_all(bind=engine)
    print("✓ Database tables created")

    db = SessionLocal()

    try:
        # Check if admin user already exists
        existing_admin = db.query(User).filter(User.email == "admin@company.com").first()
        if existing_admin:
            print("✓ Admin user already exists - skipping seed")
            return

        # Create default admin user
        admin_user = User(
            full_name="System Administrator",
            email="admin@company.com",
            hashed_password=hash_password("Admin@123"),
            role="admin",
            is_active=True,
            force_password_change=True,  # Force admin to change password on first login
        )
        db.add(admin_user)
        db.commit()
        print("✓ Created admin user: admin@company.com / Admin@123")
        print("  Note: Admin will be prompted to change password on first login")

        # Create sample suppliers
        sample_suppliers = [
            Supplier(
                supplier_code="SUPP-00001",
                company_name="Tech Electronics Pvt Ltd",
                contact_person="Rajesh Kumar",
                phone="9876543210",
                email="sales@techelectronics.com",
                gstin="27AABCT1234A1Z5",
                address_line1="123 Electronics Market",
                address_line2="Lamington Road",
                city="Mumbai",
                state="Maharashtra",
                state_code="27",
                pincode="400008",
                payment_terms_days=30,
                is_active=True,
                created_by=admin_user.id,
            ),
            Supplier(
                supplier_code="SUPP-00002",
                company_name="Digital Solutions Inc",
                contact_person="Priya Sharma",
                phone="9123456789",
                email="info@digitalsolutions.in",
                gstin="29AABCD5678B1Z3",
                address_line1="45 Tech Park",
                city="Bangalore",
                state="Karnataka",
                state_code="29",
                pincode="560001",
                payment_terms_days=15,
                is_active=True,
                created_by=admin_user.id,
            ),
        ]
        for supplier in sample_suppliers:
            existing = db.query(Supplier).filter(Supplier.supplier_code == supplier.supplier_code).first()
            if not existing:
                db.add(supplier)
        db.commit()
        print(f"✓ Created {len(sample_suppliers)} sample suppliers")

        # Create units of measure
        uom_data = [
            ("Piece", "PCS"),
            ("Kilogram", "KG"),
            ("Gram", "G"),
            ("Litre", "LTR"),
            ("Millilitre", "ML"),
            ("Box", "BOX"),
            ("Pack", "PACK"),
            ("Meter", "MTR"),
            ("Square Meter", "SQM"),
            ("Numbers", "NOS"),
        ]
        for name, abbreviation in uom_data:
            existing = db.query(UnitOfMeasure).filter(UnitOfMeasure.abbreviation == abbreviation).first()
            if not existing:
                db.add(UnitOfMeasure(name=name, abbreviation=abbreviation, is_active=True))
        db.commit()

        # Create sample products
        pcs_uom = db.query(UnitOfMeasure).filter(UnitOfMeasure.abbreviation == "PCS").first()
        sample_products = [
            Product(
                name="LED Monitor 24 inch",
                product_code="PROD-00001",
                description="24 inch Full HD LED Monitor",
                category="Electronics",
                unit_of_measure_id=pcs_uom.id if pcs_uom else None,
                purchase_price=850000,  # in paise (₹8,500)
                mrp_price=1200000,  # in paise (₹12,000)
                sale_price=1100000,  # in paise (₹11,000)
                gst_rate=18,
                is_active=True,
                created_by=admin_user.id,
            ),
            Product(
                name="Wireless Keyboard",
                product_code="PROD-00002",
                description="Wireless USB Keyboard",
                category="Electronics",
                unit_of_measure_id=pcs_uom.id if pcs_uom else None,
                purchase_price=45000,  # in paise (₹450)
                mrp_price=75000,  # in paise (₹750)
                sale_price=65000,  # in paise (₹650)
                gst_rate=18,
                is_active=True,
                created_by=admin_user.id,
            ),
            Product(
                name="USB Mouse",
                product_code="PROD-00003",
                description="Optical USB Mouse",
                category="Electronics",
                unit_of_measure_id=pcs_uom.id if pcs_uom else None,
                purchase_price=25000,  # in paise (₹250)
                mrp_price=45000,  # in paise (₹450)
                sale_price=40000,  # in paise (₹400)
                gst_rate=18,
                is_active=True,
                created_by=admin_user.id,
            ),
        ]
        for product in sample_products:
            existing = db.query(Product).filter(Product.product_code == product.product_code).first()
            if not existing:
                db.add(product)
        db.commit()
        print(f"✓ Created {len(sample_products)} sample products")

        # Create default company
        company = db.query(Company).first()
        if not company:
            company = Company(
                name="My Company",
                gstin="27AABCM1234A1Z1",
                pan="AABCM1234A",
                address_line1="123 Business Street",
                city="Mumbai",
                state="Maharashtra",
                pincode="400001",
                phone="02212345678",
                email="info@mycompany.com",
                po_prefix="PO",
                po_counter=1,
                grn_prefix="GRN",
                grn_counter=1,
            )
            db.add(company)
            db.commit()
            print("✓ Created default company")

    except Exception as e:
        db.rollback()
        print(f"✗ Error seeding database: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
    print("\n✓ Database seeding completed successfully!")
    print("\nSample data created:")
    print("  - Admin user: admin@company.com / Admin@123")
    print("  - Suppliers: Tech Electronics, Digital Solutions")
    print("  - Products: LED Monitor, Wireless Keyboard, USB Mouse")
    print("\nYou can now create Purchase Orders and GRNs!")
