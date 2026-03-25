# Scripts Setup & Usage Guide

This directory contains utility scripts for IMS setup and maintenance.

---

## 📋 Available Scripts

### setup_db.py — Complete Database Initialization

**Purpose:** One-time initialization script that creates all database tables and seeds initial data.

**Usage:**
```bash
cd backend
python setup_db.py
```

**What it does:**
1. Connects to PostgreSQL (using DATABASE_URL from `.env`)
2. Creates all tables via SQLAlchemy metadata
3. Seeds default data:
   - Admin user: `admin@company.com` / `Admin@123`
   - Units of Measure: PCS, KG, G, LTR, ML, BOX, PACK, MTR, NOS
   - Default product category: "General"
   - Placeholder company row (admin fills in details later)

**Environment Required:**
- `backend/.env` must exist with valid `DATABASE_URL`
- Python 3.11+
- All dependencies from `requirements.txt` installed

**First-Time Setup Sequence:**
```bash
# 1. Create PostgreSQL database (manual or via CREATE DATABASE)
# 2. Install Python dependencies
cd backend && pip install -r requirements.txt

# 3. Run migrations (if using Alembic)
cd ../database && alembic upgrade head

# 4. Initialize database with seed data
cd ../backend && python setup_db.py

# 5. Start backend
uvicorn app.main:app --reload
```

---

### seed_db.py — Sample Data Seeding (Optional)

**Purpose:** Generates sample test data for development and demo purposes.

**Usage:**
```bash
cd backend
python seed_db.py
```

**What it does:**
- Creates sample customers (10-20 records)
- Creates sample suppliers (5-10 records)
- Creates sample products with various GST rates
- Creates sample purchase orders and GRNs
- Creates sample sales orders and invoices
- Creates sample payments and allocations

**When to Use:**
- Development environments (when you need data to test with)
- Demo/POC environments
- Load testing

**When NOT to use:**
- Production databases (remove old data first: `python clear_seed_data.py`)

---

## 🔄 Database Lifecycle

### Initial Setup (New Database)
```bash
# 1. Create PostgreSQL database
psql -U postgres
CREATE DATABASE inventory_db;

# 2. Configure backend/.env
cp backend/.env.example backend/.env
# Edit with your database credentials

# 3. Run migrations
alembic -c database/alembic.ini upgrade head

# 4. Seed initial data
python setup_db.py

# 5. (Optional) Add sample data
python seed_db.py
```

### Development Cycle
```bash
# Make changes to models...

# 1. Create migration
alembic revision --autogenerate -m "Describe your changes"

# 2. Review migration in database/alembic/versions/

# 3. Apply migration
alembic upgrade head

# 4. Refresh backend
# (uvicorn will auto-reload if running with --reload)
```

### Reset Development Database
```bash
# Rollback all migrations
alembic downgrade base

# Re-apply all migrations
alembic upgrade head

# Re-seed data
python setup_db.py
python seed_db.py
```

### Backup & Restore
```bash
# Backup
pg_dump --no-password -U inventory_user inventory_db > backup.sql

# Restore
psql -U inventory_user inventory_db < backup.sql
```

---

## 🗂️ Script Details

### setup_db.py Location
```
backend/setup_db.py
```

### seed_db.py Location
```
backend/seed_db.py
```

### Common Errors & Solutions

| Error | Solution |
|---|---|
| `DATABASE_URL environment variable not set` | Copy `backend/.env.example` to `backend/.env` and configure |
| `FATAL: database "inventory_db" does not exist` | Create database manually: `CREATE DATABASE inventory_db;` |
| `FATAL: Ident authentication failed` | Check PostgreSQL credentials in `DATABASE_URL` |
| `tables already exist` | Database already initialized; skip `setup_db.py` |
| `ModuleNotFoundError: No module named 'app'` | Ensure you're in `backend/` directory |

---

## 🚀 Quick Start Checklist

- [ ] PostgreSQL installed and running
- [ ] Repository cloned
- [ ] Python 3.11+ installed
- [ ] `backend/.env` configured with valid DATABASE_URL
- [ ] Dependencies installed: `pip install -r requirements.txt`
- [ ] Database created: `CREATE DATABASE inventory_db;`
- [ ] Migrations applied: `alembic upgrade head`
- [ ] Initial data seeded: `python setup_db.py`
- [ ] (Optional) Sample data added: `python seed_db.py`
- [ ] Backend started: `uvicorn app.main:app --reload`
- [ ] Frontend started: `cd frontend && npm run dev`
- [ ] Login with: `admin@company.com` / `Admin@123`

---

**Last Updated:** March 25, 2026
