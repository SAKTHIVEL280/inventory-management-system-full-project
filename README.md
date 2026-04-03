# Mecandria ERP

Mecandria ERP is a full-stack inventory management system for purchase, sales, stock, receivables/payables, GST-aware reporting, and PDF documents.

## Quick Start

### 1. Verify prerequisites

Run this from repository root:

```powershell
python verify_prerequisites.py
```

Expected tooling:
- Node.js 20+
- Python 3.11+
- PostgreSQL 15+

### 2. Bootstrap backend, database, and seed data

From repository root:

```powershell
python setup_db.py
```

What this does:
- creates or reuses backend virtual environment
- installs backend dependencies
- ensures the configured PostgreSQL database exists
- seeds default data
- runs compatibility migration for old databases

### 3. Start backend

```powershell
cd backend
.venv\Scripts\activate
uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

### 4. Start frontend (new terminal)

```powershell
cd frontend
npm install
npm run dev
```

### 5. Login

- URL: http://localhost:3001
- Email: admin@company.com
- Password: Admin@123

## Local URLs

- Frontend: http://localhost:3001
- Backend API: http://127.0.0.1:8001
- OpenAPI docs: http://127.0.0.1:8001/docs
- Health endpoint: http://127.0.0.1:8001/health

## Old Database Compatibility

If you are running against an older existing database schema, run this after pulling latest changes:

```powershell
cd backend
.venv\Scripts\activate
python run_migration.py
```

Notes:
- this migration is idempotent and safe to run multiple times
- do not delete compatibility files under backend and database
- keep backend/run_migration.py in your deployment/update flow

## Project Structure

```text
inventory-management-system-full-project/
|-- backend/
|   |-- app/
|   |   |-- models/
|   |   |-- routers/
|   |   |-- schemas/
|   |   |-- services/
|   |   `-- main.py
|   |-- requirements.txt
|   |-- run_migration.py
|   `-- setup_db.py
|-- frontend/
|   |-- src/
|   |   |-- api/
|   |   |-- components/
|   |   |-- pages/
|   |   `-- utils/
|   |-- package.json
|   `-- vite.config.ts
|-- database/
|   |-- 01_schema.sql
|   |-- 02_seed_data.sql
|   |-- 03_queries.sql
|   `-- ALL_UPDATES.sql
|-- docs/
|   |-- INDEX.md
|   |-- guides/
|   |-- workflows/
|   `-- design/
|-- MASTER_SPEC.md
|-- setup_db.py
|-- verify_prerequisites.py
`-- README.md
```

## Documentation

- Main spec: MASTER_SPEC.md
- Docs index: docs/INDEX.md
- Setup guide: docs/guides/SETUP.md
- First-time checklist: docs/guides/FIRST_TIME_SETUP_CHECKLIST.md
- Workflow guides: docs/workflows/
- Design system: docs/design/DESIGN_SYSTEM_MASTER.md

## Run Tests

Backend:

```powershell
cd backend
.venv\Scripts\activate
python -m pytest
```

Frontend gate (lint + build):

```powershell
cd frontend
npm test
```

## Environment Configuration

Backend env file:
- file: backend/.env
- template: backend/.env.example

Frontend env file:
- file: frontend/.env
- template: frontend/.env.example

Required values:
- backend DATABASE_URL
- backend FRONTEND_URL (default http://localhost:3001)
- frontend VITE_API_BASE_URL (default http://localhost:8001)

## Security Notes

- never commit real secrets in .env files
- change default admin password immediately in non-local environments
- use a strong SECRET_KEY in production
- set proper PostgreSQL credentials before deployment

## Production Notes

Recommended flow for updates:
1. pull code
2. install/update dependencies
3. run backend/run_migration.py
4. restart backend and frontend services

For detailed deployment guidance, use docs/guides/SETUP.md.
