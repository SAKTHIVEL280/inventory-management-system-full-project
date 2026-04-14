# IMS Database — Setup & Run Guide

These SQL files are reference artifacts. The active project setup path uses `setup_db.py` + SQLAlchemy models + `backend/run_migration.py`.

## Files

- `01_schema.sql` — Legacy reference schema
- `02_seed_data.sql` — Legacy reference seed
- `03_queries.sql` — Reference queries (do not run automatically)
- `CLEAR_ALL_DATA.sql` — Utility script to clear all rows from all `public` schema tables while preserving schema
- `VERIFY_ALL_TABLES_CLEARED.sql` — Utility script to report per-table row counts and verify database emptiness

## Quick Start (Windows PowerShell)

```powershell
# 1) Create user + database (run as postgres superuser)
psql -U postgres -c "CREATE USER ims_user WITH PASSWORD 'IMS@2026';"
psql -U postgres -c "CREATE DATABASE ims_db OWNER ims_user;"
psql -U postgres -d ims_db -c "CREATE EXTENSION IF NOT EXISTS pgcrypto;"

# 2) Run schema (legacy/manual path)
$env:PGPASSWORD = "IMS@2026"
psql -h localhost -U ims_user -d ims_db -f database/01_schema.sql

# 3) Seed required data
psql -h localhost -U ims_user -d ims_db -f database/02_seed_data.sql

# 4) Apply compatibility columns used by latest app code
cd backend
python run_migration.py
```

## Notes

- Preferred setup command from repo root is:
	- `python setup_db.py`
- The backend must point at this DB using:
	- `DATABASE_URL=postgresql://ims_user:IMS%402026@localhost:5432/ims_db`

## Data Reset Utilities (Admin / Delivery Use)

These are operational utilities for controlled environments (for example before client handover).

### 1) Clear all data only (preserve schema)

```powershell
$env:PGPASSWORD = "IMS@2026"
psql -h localhost -U ims_user -d ims_db -f database/CLEAR_ALL_DATA.sql
```

What it does:

- Dynamically discovers all tables in schema `public` via `pg_tables`
- Executes one `TRUNCATE TABLE ... RESTART IDENTITY CASCADE`
- Removes all rows from all tables
- Resets identity/serial-backed counters
- Preserves table definitions, columns, constraints, indexes, and keys

### 2) Verify all tables are empty

```powershell
$env:PGPASSWORD = "IMS@2026"
psql -h localhost -U ims_user -d ims_db -f database/VERIFY_ALL_TABLES_CLEARED.sql
```

Output includes:

- `schema_name`
- `table_name`
- `row_count`
- `status` (`OK` / `NOT EMPTY`)
- Final summary (`PASS - all tables are empty` or `FAIL - some tables still contain data`)

### Key / Constraint Handling

- Primary keys are preserved (no `DROP`/`ALTER` is executed).
- Foreign key dependencies are handled safely by `TRUNCATE ... CASCADE`.
- Identity/serial values are reset using `RESTART IDENTITY`.
- No columns, constraints, indexes, or table definitions are modified.

## Migration Safety Policy

- Feature migration SQL files must be non-destructive.
- Allowed: `ADD COLUMN IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`, `COMMENT ON COLUMN`.
- Not allowed in feature migrations: `DELETE`, `TRUNCATE`, `DROP TABLE`, `DROP COLUMN`.
- Rule: add new columns only, keep all existing rows and sample data unchanged.
- Exception: dedicated utility scripts such as `CLEAR_ALL_DATA.sql` are intentionally destructive and should not be used as feature migrations.

