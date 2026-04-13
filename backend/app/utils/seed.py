"""Database seeding script - creates initial data."""
import os
import secrets
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.database import SessionLocal, engine, Base
import app.models  # noqa: F401 - ensures all model tables are registered on Base metadata
from app.models.user import User
from app.models.product import UnitOfMeasure, ProductCategory
from app.models.company import Company
from app.services.auth_service import hash_password

def seed_database():
    """Create initial database records."""

    # Create all tables
    Base.metadata.create_all(bind=engine)
    print("[OK] Database tables created")

    db = SessionLocal()

    try:
        configured_email = (os.getenv("IMS_ADMIN_EMAIL") or "").strip().lower()
        generated_email = ""
        admin_email = configured_email
        if not admin_email:
            generated_email = f"bootstrap-admin-{secrets.token_hex(4)}@local.invalid"
            admin_email = generated_email

        configured_password = (os.getenv("IMS_ADMIN_PASSWORD") or "").strip()
        generated_password = ""
        if not configured_password:
            generated_password = secrets.token_urlsafe(12)
            configured_password = generated_password

        # Check if admin user already exists
        admin_user = db.query(User).filter(User.email == admin_email).first()
        if not admin_user:
            # Create bootstrap admin user using configured or generated password.
            admin_user = User(
                full_name="System Administrator",
                email=admin_email,
                hashed_password=hash_password(configured_password),
                role="admin",
                is_active=True,
                force_password_change=True,  # Force admin to change password on first login
            )
            db.add(admin_user)
            db.commit()
            print(f"[OK] Created admin user: {admin_email}")
            if generated_email:
                print(f"[SECURITY] Generated admin email: {generated_email}")
            else:
                print("[SECURITY] Admin email source: IMS_ADMIN_EMAIL environment variable")
            if generated_password:
                print(f"[SECURITY] Generated admin password: {generated_password}")
            else:
                print("[SECURITY] Admin password source: IMS_ADMIN_PASSWORD environment variable")
            print("  Note: Admin will be prompted to change password on first login")
        else:
            print("[OK] Admin user already exists")

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

        # Create a single default category used by product master setup
        general_cat = db.query(ProductCategory).filter(ProductCategory.name == "General").first()
        if not general_cat:
            general_cat = ProductCategory(
                name="General",
                description="Default category",
                created_by=admin_user.id,
            )
            db.add(general_cat)
            db.commit()
            print("[OK] Created default product category")
        else:
            print("[OK] Default product category already exists")

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
            print("[OK] Created default company")

    except Exception as e:
        db.rollback()
        print(f"[ERROR] Error seeding database: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
    print("\n[OK] Database seeding completed successfully!")
    print("\nBootstrap data created:")
    print("  - Admin user: from IMS_ADMIN_EMAIL or generated at runtime")
    print("  - Admin password: from IMS_ADMIN_PASSWORD or generated at runtime")
    print("  - Default company, units of measure, and General category")
