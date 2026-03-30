# First-Time Setup Checklist (One Page)

Use this exact checklist on a new machine.

## 1. Prerequisites

- Python 3.11+ (tested on 3.12)
- Node.js 20+ and npm
- PostgreSQL running locally
- PostgreSQL tools available in PATH: psql, createdb

Quick checks:

```powershell
python --version
node --version
npm --version
psql --version
createdb --version
```

## 2. Clone and Open

```powershell
git clone <your-repo-url>
cd inventory-management-system-full-project
```

## 3. Configure Database Access

Create or update backend/.env with a valid DATABASE_URL.

Minimum working local value:

```env
DATABASE_URL=postgresql://postgres:root@localhost:5432/ims_db
```

If your password/user is different, update this string accordingly.

## 4. Run One Command Setup

From repo root:

```powershell
python setup_db.py
```

What this does:

- creates/uses backend virtual environment
- installs backend dependencies
- ensures database exists
- applies compatibility migration (including currency fields)
- creates tables and seeds defaults

## 5. Start Backend

```powershell
cd backend
.venv\Scripts\activate
uvicorn app.main:app --reload
```

Backend URLs:

- API: http://127.0.0.1:8000
- Docs: http://127.0.0.1:8000/docs

## 6. Start Frontend (new terminal)

```powershell
cd frontend
npm install
npm run dev
```

Frontend URL: shown by Vite (usually http://localhost:5173 or 5174)

## 7. Login

- Email: admin@company.com
- Password: Admin@123

## 8. Fast Troubleshooting

1. Dashboard shows CORS + 500

- This usually means backend crashed first.
- Check backend terminal traceback.
- Ensure frontend base URL points to your running backend port.

2. Setup script fails at database creation

- Verify PostgreSQL is running.
- Verify DATABASE_URL credentials in backend/.env.
- Ensure createdb/psql are available.

3. Port 8000 already in use

- Stop stale process using port 8000, then restart backend.

4. Re-run setup safely

```powershell
python setup_db.py
```

It is idempotent and safe to run multiple times.
