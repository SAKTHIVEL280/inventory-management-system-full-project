"""Create database and tables."""
import subprocess
import sys
import os

print("=== IMS Database Setup ===\n")

# Step 1: Ensure database exists
print("[1/3] Setting up PostgreSQL database...")
try:
    # Use createdb command
    result =subprocess.run(
        ["createdb", "-U", "postgres", "inventory_db"],
        capture_output=True,
        text=True,
        timeout=10
    )
    
    if "already exists" in result.stderr:
        print("  ✓ Database 'inventory_db' already exists")
    elif result.returncode == 0:
        print("  ✓ Created database 'inventory_db'")
    else:
        if result.stderr:
            print(f"  Warning: {result.stderr[:100]}")
except Exception as e:
    print(f"  Note: Could not use createdb command: {e}")
    print("  Proceeding with existing database...")

# Step 2: Install Python packages if needed
print("\n[2/3] Ensuring Python dependencies are installed...")
backend_path = os.path.join(os.path.dirname(__file__), "backend")
venv_path = os.path.join(backend_path, "venv")

if not os.path.exists(venv_path):
    print("  Creating virtual environment...")
    subprocess.run([sys.executable, "-m", "venv", venv_path], check=True)

pip_cmd = os.path.join(venv_path, "Scripts", "pip") if os.name == "nt" else os.path.join(venv_path, "bin", "pip")
subprocess.run([pip_cmd, "install", "-q", "-r", os.path.join(backend_path, "requirements.txt")], check=False)
print("  ✓ Dependencies ready")

# Step 3: Initialize database
print("\n[3/3] Creating database tables...")
os.chdir(backend_path)

sys.path.insert(0, backend_path)

try:
    from app.database import engine, Base
    from app.models import (
        User,
        UnitOfMeasure,
    )
    from sqlalchemy.orm import sessionmaker
    from app.services.auth_service import hash_password
    
    Base.metadata.create_all(bind=engine)
    print("  ✓ Tables created")
    
    # Seed admin user
    Session = sessionmaker(bind=engine)
    db = Session()
    
    existing = db.query(User).filter(User.email == "admin@company.com").first()
    if not existing:
        admin = User(
            full_name="System Administrator",
            email="admin@company.com",
            hashed_password=hash_password("Admin@123"),
            role="admin",
            is_active=True,
            force_password_change=True,
        )
        db.add(admin)
        db.commit()
        print("  ✓ Admin user created: admin@company.com / Admin@123")
    else:
        print("  ✓ Admin user already exists")

    uom_seed_data = [
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
    for name, abbreviation in uom_seed_data:
        exists = db.query(UnitOfMeasure).filter(UnitOfMeasure.abbreviation == abbreviation).first()
        if not exists:
            db.add(UnitOfMeasure(name=name, abbreviation=abbreviation, is_active=True))
    db.commit()
    print("  ✓ Units of measure seeded")
    
    db.close()

except Exception as e:
    print(f"  ✗ Error: {e}")
    exit(1)

print("\n✓ Database setup completed!\n")
print("Next steps:")
print("  1. Start backend:  cd backend && uvicorn app.main:app --reload")
print("  2. Start frontend: cd frontend && npm install && npm run dev")
