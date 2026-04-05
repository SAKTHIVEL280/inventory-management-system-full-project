# Database Setup & Management Guide

This guide reflects the current database lifecycle used by this repository.

---

## Quick Reference

- Database engine: PostgreSQL 15+
- ORM/schema source: SQLAlchemy models in `backend/app/models/`
- Bootstrap script: `setup_db.py` (repo root)
- Compatibility migration script: `backend/run_migration.py`
- Manual SQL artifacts: `database/*.sql` (reference/manual only)

---

## 1. Current Database Lifecycle

The active setup path is:

1. Run `python setup_db.py` from repo root.
2. Script ensures backend venv + dependencies.
3. Script creates/reuses DB from `backend/.env` (`DATABASE_URL`).
4. Script runs `python -m app.utils.seed` to create tables and seed defaults.
5. Script runs `backend/run_migration.py` for compatibility columns.

This flow is idempotent and safe to rerun.

---

## 2. PostgreSQL Setup

### Option A: Local PostgreSQL (Windows/Linux/macOS)

1. Install PostgreSQL 15+.
2. Ensure tools are in PATH (`psql`, `createdb`).
3. Ensure service is running on `localhost:5432`.

### Option B: Docker

```bash
docker run -d \
  --name ims-postgres \
  -e POSTGRES_USER=ims_admin \
  -e POSTGRES_PASSWORD=SecureP@ss123 \
  -e POSTGRES_DB=ims_db \
  -p 5432:5432 \
  -v postgres_data:/var/lib/postgresql/data \
  postgres:15-alpine
```

If using Docker credentials, set matching `DATABASE_URL` in `backend/.env`.

---

## 3. Environment Configuration

Configure `backend/.env`:

```env
DATABASE_URL=postgresql://postgres:your_password@localhost:5432/ims_db
SECRET_KEY=change-this-in-production
FRONTEND_URL=http://localhost:3001
```

Notes:
- `DATABASE_URL` must be PostgreSQL.
- App config rejects non-PostgreSQL database URLs.

---

## 4. Initialize Database

From repo root:

```powershell
python setup_db.py
```

Expected successful output includes:
- `[OK] Setup completed successfully`

What gets seeded:
- admin user: `admin@company.com` / `Admin@123`
- units of measure
- default product category
- default company record

---

## 5. Compatibility Migration

Run after pulling backend updates into an existing DB:

```powershell
cd backend
python run_migration.py
```

This script adds missing columns with safe `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` statements.

---

## 6. Table Overview (Current Models)

### Core
- `users`
- `company`
- `customers`
- `suppliers`

### Product and Inventory
- `product_categories`
- `units_of_measure`
- `products`
- `stock_ledger`

### Purchase Flow
- `purchase_orders`
- `purchase_order_items`
- `goods_receipt_notes`
- `grn_items`
- `purchase_returns`
- `purchase_return_items`

### Sales Flow
- `quotations`
- `quotation_items`
- `sales_orders`
- `sales_order_items`
- `sales_invoices`
- `sales_invoice_items`
- `sales_returns`
- `sales_return_items`

### Payments
- `payments`
- `payment_allocations`

---

## 7. Verify Database State

Connect and inspect:

```bash
psql -h localhost -U postgres -d ims_db
```

Useful checks:

```sql
\dt

SELECT 'users' AS table_name, COUNT(*) FROM users
UNION ALL
SELECT 'products', COUNT(*) FROM products
UNION ALL
SELECT 'customers', COUNT(*) FROM customers
UNION ALL
SELECT 'suppliers', COUNT(*) FROM suppliers;
```

---

## 8. SQL Files in database/

The files below are kept as reference/manual artifacts:
- `01_schema.sql`
- `02_seed_data.sql`
- `03_queries.sql`
- `ALL_UPDATES.sql`
- `ALL_UPDATES_2.sql`

They are not automatically executed by app startup scripts.

---

## 9. Backup & Restore

### Backup

```bash
pg_dump -h localhost -U postgres -d ims_db > ims_db_backup.sql
```

### Restore

```bash
psql -h localhost -U postgres -d ims_db < ims_db_backup.sql
```

Use role/host values that match your environment.

---

## 10. Troubleshooting

### "password authentication failed"
- Verify `DATABASE_URL` credentials in `backend/.env`.

### "database \"ims_db\" does not exist"
- Create DB manually or rerun `python setup_db.py` after fixing credentials.

### "relation does not exist"
- Run:
  - `python setup_db.py`
  - `cd backend; python run_migration.py`

### `psql` or `createdb` not recognized
- Add PostgreSQL command-line tools to PATH and restart terminal.

---

## 11. FAQ

Q: Can I use MySQL/SQLite?
A: No. This codebase supports PostgreSQL only.

Q: Are Alembic migrations used right now?
A: No Alembic files are currently part of this repository. Compatibility updates are handled by `backend/run_migration.py`.

Q: Can `setup_db.py` be run multiple times?
A: Yes. It is designed to be idempotent.

---

Last updated: April 5, 2026


