# Setup Guide

## Prerequisites

| Tool | Minimum Version |
|---|---|
| Node.js | 20.x LTS |
| Python | 3.11+ |
| PostgreSQL | 15+ |
| Git | 2.x |

---

## 1. Clone the Repository

```bash
git clone <repository-url>
cd inventory-management
```

Expected top-level folders after setup:
- `backend/` (FastAPI app)
- `frontend/` (React app)
- `database/` (Alembic migrations)
- `docs/` (System documentation)

---

## 2. Setup Options

Choose **ONE** of the paths below to set up your environment.

---

### 🟢 Path A: The Easy Way (Recommended)

Use the automated bootstrap to handle environment setup, dependency install, compatibility migration (including currency fields), and seeding in one go.

**Windows (PowerShell):**
```powershell
# Run from repository root
python setup_db.py
```

**Linux/macOS:**
```bash
# Run from repository root
python3 setup_db.py
```

**Next Steps after Path A:**
1. Start backend and frontend servers (see section 4).

---

### 🔵 Path B: The Manual Way (Step-by-Step)

Use this path if you want full control over your environment or if the automated script fails.

#### B.1 Database Creation
1. Open your PostgreSQL terminal or tool (pgAdmin/DBeaver).
2. Create a new database named `ims_db`.

#### B.2 Backend Environment
1. Navigate to the backend folder:
   ```bash
   cd backend
   ```
2. Create and activate a virtual environment:
   ```bash
    python -m venv .venv
   # Windows:
    .venv\Scripts\activate
   # Linux/macOS:
    source .venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Configure `.env` (see section 3.1).

#### B.3 Initialize DB Compatibility + Seed
Run compatibility migration first (adds missing columns like currency/exchange_rate/safety_stock), then seed:
```bash
python run_migration.py
python -m app.utils.seed
```

---

## 3. Configuration & Startup

### 3.1 Backend Environment (.env)

Navigate to `backend/`, copy `.env.example` to `.env`, and fill in the values:

```bash
cp .env.example .env
```

**Key Values:**
- `DATABASE_URL`: `postgresql://postgres:root@localhost:5432/ims_db`
- `SECRET_KEY`: Generate one using `python -c "import secrets; print(secrets.token_hex(32))"`
- `FRONTEND_URL`: `http://localhost:5173` (or `5174`)

### 3.2 Frontend Environment (.env)

Navigate to `frontend/`, copy `.env.example` to `.env`:

```bash
cd ../frontend
cp .env.example .env
```

Ensure `VITE_API_BASE_URL` matches your backend URL (default: `http://127.0.0.1:8000`).

---

## 4. Starting the Application

### 4.1 Backend
```bash
cd backend
.venv\Scripts\activate   # Windows
uvicorn app.main:app --reload
```

### 4.2 Frontend
```bash
cd frontend
npm install
npm run dev
```

API is available at: http://localhost:8000
API documentation: http://localhost:8000/docs

If dashboard or sales pages fail after upgrading older databases, run:

```bash
cd backend
python run_migration.py
```

---

## 5. First Login

1. Open http://localhost:5173 (or current Vite port)
2. Login with: **admin@company.com** / **Admin@123**
3. You will be prompted to change your password immediately.
4. Go to Masters > Company and fill in your company details (name, GSTIN, state, bank details).
5. Go to Masters > Users and create users for each role.
6. Go to Masters > Products and add your product catalogue.
7. Go to Masters > Customers and add your customers.
8. Go to Masters > Suppliers and add your suppliers.

---

## 6. Production Deployment

### 6.1 Backend (Linux server)

```bash
pip install gunicorn
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

Use a process manager like systemd or supervisor to keep it running.

### 6.2 Frontend Build

```bash
cd frontend
npm run build
```

Serve the `dist/` folder using Nginx or any static file server.

### 6.3 Nginx Configuration (sample)

```nginx
server {
    listen 80;
    server_name yourdomain.com;

    location / {
        root /path/to/frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### 6.4 Environment Variables in Production

Never commit `.env` to version control. Set environment variables using your server's environment manager or a secrets manager.

---

## 7. Common Issues

| Issue | Solution |
|---|---|
| `psycopg2` install fails | Run: `sudo apt install libpq-dev python3-dev` (Linux) |
| Alembic migration fails | Run from `database/` folder and check DATABASE_URL in `backend/.env` is correct |
| Email not sending | Use Gmail App Password (not account password). Enable 2FA first. |
| CORS error in browser | Verify FRONTEND_URL in backend .env matches your frontend URL exactly |
| PDF generation fails | Install WeasyPrint dependencies: `sudo apt install libpango-1.0-0 libpangoft2-1.0-0` |

---

## 8. Running Tests

```bash
# Backend
cd backend
pytest

# Frontend
cd frontend
npm run test
```

---

## 9. requirements.txt

```
fastapi==0.111.0
uvicorn[standard]==0.29.0
sqlalchemy==2.0.30
alembic==1.13.1
psycopg2-binary==2.9.9
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.9
fastapi-mail==1.4.1
weasyprint==61.2
pydantic[email]==2.7.1
pydantic-settings==2.2.1
python-dotenv==1.0.1
pillow==10.3.0
num2words==0.5.13
pytest==8.2.0
httpx==0.27.0
```
