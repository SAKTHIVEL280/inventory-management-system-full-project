# IMS Database — Setup & Run Guide (psql-only)

This folder mirrors the HMS database workflow: **PostgreSQL schema and seed are managed via `psql`-executed SQL files**, not via Alembic migrations.

## Files

- `01_schema.sql` — Database schema (tables, constraints, indexes, views)
- `02_seed_data.sql` — Required seed data (admin user, company row, UoM, default category)
- `03_queries.sql` — Reference queries (do not run automatically)

## Quick Start (Windows PowerShell)

```powershell
# 1) Create user + database (run as postgres superuser)
psql -U postgres -c "CREATE USER ims_user WITH PASSWORD 'IMS@2026';"
psql -U postgres -c "CREATE DATABASE ims_db OWNER ims_user;"
psql -U postgres -d ims_db -c "CREATE EXTENSION IF NOT EXISTS pgcrypto;"

# 2) Run schema
$env:PGPASSWORD = "IMS@2026"
psql -h localhost -U ims_user -d ims_db -f database_hole/01_schema.sql

# 3) Seed required data
psql -h localhost -U ims_user -d ims_db -f database_hole/02_seed_data.sql
```

## Notes

- The schema is based on the SQL definitions in `MASTER_SPEC.md` (section “Database Schema — Complete”).
- The backend must point at this DB using `DATABASE_URL=postgresql://ims_user:IMS%402026@localhost:5432/ims_db`

