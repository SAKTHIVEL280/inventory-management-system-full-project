"""Database seeding script - creates initial data."""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.database import SessionLocal, engine, Base
from app.models.user import User
from app.services.auth_service import hash_password

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
        
    except Exception as e:
        db.rollback()
        print(f"✗ Error seeding database: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
    print("\n✓ Database seeding completed successfully!")
