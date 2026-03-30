# IMS Database — Setup & Run Guide

These SQL files are reference artifacts. The active project setup path uses `setup_db.py` + SQLAlchemy models + `backend/run_migration.py`.

## Files

- `01_schema.sql` — Legacy reference schema
- `02_seed_data.sql` — Legacy reference seed
- `03_queries.sql` — Reference queries (do not run automatically)

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

