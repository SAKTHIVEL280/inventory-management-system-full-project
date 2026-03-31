# Database Setup & Management Guide

This guide covers database configuration, initialization, migration, and troubleshooting.

---

## [LIST] Quick Reference

- **Development**: PostgreSQL 15+ (Docker or local install)
- **Production**: PostgreSQL 15+ (required)
- **Schema management**: SQLAlchemy models + compatibility migration (`backend/run_migration.py`)

---

## [POSTGRES] PostgreSQL Setup (Docker)

### Prerequisites
- Docker installed
- Docker Compose (optional, for multi-container setup)

### Quick Start (One Command)
```bash
# Start PostgreSQL 15 container
docker run -d \
  --name ims-postgres \
  -e POSTGRES_USER=ims_admin \
  -e POSTGRES_PASSWORD=SecureP@ss123 \
  -e POSTGRES_DB=ims_db \
  -p 5432:5432 \
  -v postgres_data:/var/lib/postgresql/data \
  postgres:15-alpine
```

### Environment Configuration
Create or update `backend/.env`:
```env
DATABASE_URL=postgresql://ims_admin:SecureP@ss123@localhost:5432/ims_db
SQLALCHEMY_ECHO=false
```

### Initialize Database Schema
```bash
cd backend

# Create Python virtual environment (if not exists)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Initialize schema + seed data (recommended)
python ../setup_db.py
```

### Verify Connection
```bash
# Connect to PostgreSQL container
docker exec -it ims-postgres psql -U ims_admin -d ims_db

# See all tables
\dt

# Check row counts
SELECT 'users' as table_name, COUNT(*) as count FROM users
UNION ALL
SELECT 'products', COUNT(*) FROM products
UNION ALL
SELECT 'customers', COUNT(*) FROM customers
UNION ALL
SELECT 'suppliers', COUNT(*) FROM suppliers;

# Exit
\q
```

---

## [PACKAGE] Database Schema Overview

### Core Tables

#### Users & Auth
- `users` — Login accounts with JWT tokens
- `roles` — Permission definitions (admin, accounting, etc.)
- `role_permissions` — Role ↔ Permission mapping

#### Masters (Setup Data)
- `companies` — Organization info
- `customers` — Customer records
- `suppliers` — Vendor records
- `products` — Inventory items
- `product_units` — Units of measure (PCS, KG, LTR, etc.)

#### Transactions
- `purchases` — Purchase orders
- `purchase_lines` — PO line items
- `purchase_receipts` — Goods receipt notes
- `sales_orders` — Sale orders
- `sales_lines` — SO line items
- `receipts` — Cash received
- `payments` — Cash paid

#### Reports
- `stock_history` — Inventory movements

### Key Design Patterns

**UUID Primary Keys**
```python
id: UUID = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
```

**Timestamps**
```python
created_at: DateTime = Column(DateTime(timezone=True), default=datetime.utcnow)
updated_at: DateTime = Column(DateTime(timezone=True), onupdate=datetime.utcnow)
```

**JSON Columns (Flexible Storage)**
```python
permission_overrides: dict = Column(JSON, nullable=True)
```

---

## [SYNC] Database Migrations

Use the compatibility migration script whenever new columns are introduced.

```bash
cd backend
python run_migration.py
```

This is idempotent and safe to run multiple times.

---

## [METRICS] Database Initialization Scripts

### setup_db.py (Full Setup)
```bash
cd <repo-root>
python setup_db.py
```

**What it does:**
1. [OK] Connects to the PostgreSQL database
2. [OK] Creates all tables (via SQLAlchemy metadata)
3. [OK] Seeds admin user: `admin@company.com` / `Admin@123`
4. [OK] Seeds product units: PCS, KG, LTR, BOX, etc.
5. [OK] Creates default company record

**Main script location:** `setup_db.py` (wrapper also available at `backend/setup_db.py`)

### seed_db.py (Sample Data)
```bash
cd backend
python seed_db.py
```

**What it does:**
- Generates sample customers, suppliers, products
- Creates test purchase orders and sales orders
- Useful for development and testing

---

## [SECURITY] Security Best Practices

### Development
```env
DATABASE_URL=postgresql://dev_user:dev_pass@localhost:5432/ims_dev
SQLALCHEMY_ECHO=true  # Log SQL queries
```

### Production
```env
DATABASE_URL=postgresql://prod_user:VERY_STRONG_PASSWORD@prod-host:5432/ims_production
SQLALCHEMY_ECHO=false
# Use environment variables from secrets manager (AWS Secrets, Azure Key Vault, etc.)
```

### Never Commit
- `.env` files with real credentials
- Database dumps with sensitive data
- Use `.env.example` template for reference only

---

## 🆘 Troubleshooting

### "Connection refused" Error
```
Error: could not translate host name "localhost" to address

Solutions:
1. Check Docker container is running: docker ps
2. Verify DATABASE_URL is correct
3. Ensure PostgreSQL port 5432 is not blocked
4. Check firewall settings
```

### "Database does not exist" Error
```
Error: database "ims_db" does not exist

Solution:
docker exec -it ims-postgres psql -U ims_admin -c "CREATE DATABASE ims_db;"
```

### "Table does not exist" Error
```
Error: relation "users" does not exist

Solution:
# Re-run initialization:
cd backend && python setup_db.py
```

### Check Database Size
```bash
# PostgreSQL
docker exec -it ims-postgres psql -U ims_admin -d ims_db -c "SELECT pg_size_pretty(pg_database_size('ims_db'));"
```

---

## [GROWTH] Performance Optimization

### Add Indexes (After Heavy Usage)
```python
# In model:
__table_args__ = (
    Index('idx_created_at', 'created_at'),
    Index('idx_user_email', 'email', unique=True),
)
```

### Monitor Slow Queries
```python
# In database.py, enable query logging:
SQLALCHEMY_ECHO = True
```

### Connection Pooling (Production)
```python
from sqlalchemy.pool import QueuePool

engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=20,
    max_overflow=40,
)
```

---

## [SYNC] Backup & Restore

### PostgreSQL Backup
```bash
# Backup entire database
docker exec -it ims-postgres pg_dump -U ims_admin ims_db > backup.sql

# Backup with compression
docker exec -it ims-postgres pg_dump -U ims_admin -F c ims_db > backup.dump

# List backups
ls -lh backup*
```

### PostgreSQL Restore
```bash
# Restore from SQL file
docker exec -i ims-postgres psql -U ims_admin ims_db < backup.sql

# Restore from compressed dump
docker exec -i ims-postgres pg_restore -U ims_admin -d ims_db backup.dump
```

---

## [LIST] Checklist for New Developers

- [ ] Read this guide completely
- [ ] Run database initialization: `python setup_db.py`
- [ ] Verify tables exist in database
- [ ] Test API connection: `GET /api/users/me`
- [ ] Review schema in `backend/app/models/`
- [ ] Understand workflow in [WF_03_PURCHASE.md](../workflows/WF_03_PURCHASE.md)
- [ ] Subscribe to workflow changes in Git

---

## [SUPPORT] Common Questions

**Q: Can I use MySQL instead of PostgreSQL?**  
A: Not supported. This repository is PostgreSQL-only.

**Q: Can I use a different database for development?**  
A: No. Use PostgreSQL locally or via Docker.

**Q: How often should I backup data?**  
A: Daily in production. See Backup & Restore section above.

**Q: Can I modify schema in production?**  
A: Yes, but only via Alembic migrations. Never use raw ALTER TABLE in production.

**Q: What's the maximum number of records?**  
A: PostgreSQL handles billions of rows. No practical limit for this application.

---

**Last Updated:** March 25, 2026  
**Database Version:** PostgreSQL 15+


