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
        ["createdb", "-U", "postgres", "ims_db"],
        capture_output=True,
        text=True,
        timeout=10
    )

    if "already exists" in result.stderr:
        print("  ✓ Database 'ims_db' already exists")
    elif result.returncode == 0:
        print("  ✓ Created database 'ims_db'")
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

# Step 3: Initialize database with seed data
print("\n[3/3] Creating database tables and seeding sample data...")
os.chdir(backend_path)

sys.path.insert(0, backend_path)

try:
    from app.utils.seed import seed_database
    seed_database()
except Exception as e:
    print(f"  ✗ Error: {e}")
    exit(1)

print("\n✓ Database setup completed!\n")
print("Next steps:")
print("  1. Start backend:  cd backend && uvicorn app.main:app --reload")
print("  2. Start frontend: cd frontend && npm install && npm run dev")
print("\nLogin credentials:")
print("  Email: admin@company.com")
print("  Password: Admin@123")
