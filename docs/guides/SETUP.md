# Setup Guide

## Prerequisites

| Tool | Minimum Version |
|---|---|
| Node.js | 20.19+ (or 22.12+) |
| Python | 3.11+ |
| PostgreSQL | 15+ |
| Git | 2.x |

---

## 1. Clone the Repository

```bash
git clone <repository-url>
cd inventory-management-system-full-project
```

Expected top-level folders:
- `backend/` (FastAPI app)
- `frontend/` (React app)
- `database/` (reference/manual SQL scripts)
- `docs/` (project documentation)

---

## 2. Setup Options

Choose one path.

### [A] Path A: Automated Setup (Recommended)

Runs environment prep, dependency install, DB create/reuse, seed, and compatibility migration.

Windows (PowerShell):
```powershell
python setup_db.py
```

Linux/macOS:
```bash
python3 setup_db.py
```

### [B] Path B: Manual Setup

Use this if you need full manual control.

#### B.1 Create Database
1. Create PostgreSQL database `ims_db`.
2. Ensure the DB user/password match your `DATABASE_URL`.

#### B.2 Backend Environment
```bash
cd backend
python -m venv .venv
```

Activate venv:

Windows (PowerShell):
```powershell
.venv\Scripts\activate
```

Linux/macOS:
```bash
source .venv/bin/activate
```

Install dependencies:
```bash
pip install -r requirements.txt
```

#### B.3 Configure Backend Env

In `backend/`, copy `.env.example` to `.env` and set values.

Windows (PowerShell):
```powershell
Copy-Item .env.example .env
```

Linux/macOS:
```bash
cp .env.example .env
```

Required values:
- `DATABASE_URL` (must be PostgreSQL)
- `SECRET_KEY`
- `FRONTEND_URL` (usually `http://localhost:3001`)

#### B.4 Initialize Schema + Seed + Compatibility Migration

Important order:
```bash
python -m app.utils.seed
python run_migration.py
```

---

## 3. Frontend Environment

In `frontend/`, copy `.env.example` to `.env`.

Windows (PowerShell):
```powershell
cd frontend
Copy-Item .env.example .env
```

Linux/macOS:
```bash
cd frontend
cp .env.example .env
```

Default value:
- `VITE_API_BASE_URL=http://localhost:8001`

---

## 4. Start the Application

### 4.1 Backend
```powershell
cd backend
.venv\Scripts\activate
uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

### 4.2 Frontend
```powershell
cd frontend
npm install
npm run dev
```

Runtime URLs:
- API: http://127.0.0.1:8001
- API docs: http://127.0.0.1:8001/docs
- Health: http://127.0.0.1:8001/health
- Frontend: http://localhost:3001

If upgrading older DBs, run:
```powershell
cd backend
python run_migration.py
```

---

## 5. First Login

1. Open `http://localhost:3001`.
2. Login with `admin@company.com` / `Admin@123`.
3. Change password when prompted.
4. Configure company, users, products, customers, suppliers.

---

## 6. Validation Gates

Backend:
- no automated pytest suite is currently checked in this repository
- use smoke checks:

```powershell
python verify_prerequisites.py
python setup_db.py
# with backend running
Invoke-RestMethod http://127.0.0.1:8001/health
```

Frontend:
```powershell
cd frontend
npm run lint
npm run build
```

---

## 7. Production Deployment

### 7.1 Backend (Linux)
```bash
pip install gunicorn
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8001
```

### 7.2 Frontend Build
```bash
cd frontend
npm run build
```

Serve `frontend/dist` from Nginx (or another static host) and reverse-proxy API traffic to backend.

### 7.3 Update Flow
1. Pull code
2. Update dependencies
3. Run `backend/run_migration.py`
4. Restart services

---

## 8. Common Issues

| Issue | Solution |
|---|---|
| `Dependency installation failed` in setup script | Activate backend venv and run `pip install -r requirements.txt` manually to inspect full error. |
| `Could not auto-create database` | Check PostgreSQL service is running and `DATABASE_URL` credentials in `backend/.env` are correct. |
| CORS error | Ensure backend `FRONTEND_URL` exactly matches frontend origin (`http://localhost:3001`). |
| Port 8001 already in use | Free the process using that port or run backend on another port and update frontend env accordingly. |
| PDF generation fails on Linux | Install system libs required by WeasyPrint (`libpango-1.0-0`, `libpangoft2-1.0-0`). |

---

## 9. Dependency Source of Truth

- Backend dependencies: `backend/requirements.txt`
- Frontend dependencies: `frontend/package.json`

Keep dependencies updated in those files only.

