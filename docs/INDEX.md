# Mecandria ERP - Documentation Index

Welcome to the project documentation. This index points to current guides and reflects the repository structure as of April 2026.

---

## Quick Navigation

### Getting Started
- [Setup Guide](./guides/SETUP.md) - full installation and startup flow
- [First-Time Setup Checklist](./guides/FIRST_TIME_SETUP_CHECKLIST.md) - one-page onboarding
- [Database Guide](./guides/DATABASE.md) - DB setup, migration, and troubleshooting
- [Coding Standards](./guides/CODING_STANDARDS.md) - engineering quality rules

### Specifications and Design
- [Master Specification](../MASTER_SPEC.md) - full feature and architecture spec
- [Design System](./design/DESIGN_SYSTEM_MASTER.md) - UI system and patterns

### Workflow Docs
- [WF-01: Authentication](./workflows/WF_01_AUTH.md)
- [WF-02: Masters](./workflows/WF_02_MASTERS.md)
- [WF-03: Purchase](./workflows/WF_03_PURCHASE.md)
- [WF-04: Sales](./workflows/WF_04_SALES.md)
- [WF-05: Payments](./workflows/WF_05_PAYMENTS.md)
- [WF-06: Reports](./workflows/WF_06_REPORTS.md)

---

## Project Structure (Current)

```text
inventory-management-system-full-project/
|-- setup_db.py
|-- verify_prerequisites.py
|-- MASTER_SPEC.md
|-- README.md
|-- backend/
|   |-- .env.example
|   |-- requirements.txt
|   |-- setup_db.py
|   |-- run_migration.py
|   `-- app/
|       |-- main.py
|       |-- config.py
|       |-- database.py
|       |-- dependencies.py
|       |-- models/
|       |-- routers/
|       |-- schemas/
|       |-- services/
|       `-- utils/
|-- frontend/
|   |-- .env.example
|   |-- package.json
|   |-- vite.config.ts
|   `-- src/
|       |-- api/
|       |-- components/
|       |-- hooks/
|       |-- pages/
|       |-- routes/
|       |-- store/
|       |-- types/
|       `-- utils/
|-- database/
|   |-- 01_schema.sql
|   |-- 02_seed_data.sql
|   |-- 03_queries.sql
|   |-- ALL_UPDATES.sql
|   |-- ALL_UPDATES_2.sql
|   `-- README.md
`-- docs/
	 |-- INDEX.md
	 |-- guides/
	 |-- workflows/
	 `-- design/
```

Notes:
- `database/` SQL files are reference/manual artifacts.
- Active runtime setup path is `setup_db.py` + `backend/run_migration.py`.

---

## Quick Start

1. Run prerequisite check:
	- `python verify_prerequisites.py`
2. Bootstrap backend + DB + seed + migration:
	- `python setup_db.py`
3. Start backend:
	- `cd backend`
	- `.venv\Scripts\activate`
	- `uvicorn app.main:app --reload --host 127.0.0.1 --port 8001`
4. Start frontend in a new terminal:
	- `cd frontend`
	- `npm install`
	- `npm run dev`
5. Login:
	- `admin@company.com` / `Admin@123`

---

## Common Tasks

### Add a New Feature
1. Read the relevant workflow document in `docs/workflows/`.
2. Confirm constraints in [Master Specification](../MASTER_SPEC.md).
3. Implement using [Coding Standards](./guides/CODING_STANDARDS.md).
4. Validate UI against [Design System](./design/DESIGN_SYSTEM_MASTER.md).

### Set Up a New Machine
1. Follow [First-Time Setup Checklist](./guides/FIRST_TIME_SETUP_CHECKLIST.md).
2. Follow [Setup Guide](./guides/SETUP.md) for complete details.
3. Use [Database Guide](./guides/DATABASE.md) for DB-specific issues.

### Production Update Flow
1. Pull latest code.
2. Install/update dependencies.
3. Run `backend/run_migration.py`.
4. Restart backend and frontend services.

---

## Support

- Architecture and feature rules: [Master Specification](../MASTER_SPEC.md)
- Setup and environment issues: [Setup Guide](./guides/SETUP.md)
- Database issues: [Database Guide](./guides/DATABASE.md)
- UI/UX guidance: [Design System](./design/DESIGN_SYSTEM_MASTER.md)

---

Last updated: April 5, 2026

