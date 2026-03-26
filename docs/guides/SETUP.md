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
- `database_hole/` (SQL schema + seed, run via psql)
- `backend/` (FastAPI app)
- `frontend/` (React app)

---

## 2. Database Setup

### 2.1 Create PostgreSQL Database

```bash
psql -U postgres
```

```sql
CREATE USER inventory_user WITH PASSWORD 'your_secure_password';
CREATE DATABASE inventory_db OWNER inventory_user;
GRANT ALL PRIVILEGES ON DATABASE inventory_db TO inventory_user;
\q
```

### 2.2 Enable Required Extensions

```bash
psql -U inventory_user -d inventory_db
```

```sql
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
\q
```

### 2.3 Initialize Schema + Seed (psql-only)

Run the SQL files in `database_hole/` (same pattern as HMS):

```bash
psql -U inventory_user -d inventory_db -f database_hole/01_schema.sql
psql -U inventory_user -d inventory_db -f database_hole/02_seed_data.sql
```

---

## 3. Backend Setup

### 3.1 Create Virtual Environment

```bash
cd backend
python -m venv venv
source venv/bin/activate      # Linux / macOS
venv\Scripts\activate         # Windows
```

### 3.2 Install Dependencies

```bash
pip install -r requirements.txt
```

### 3.3 Configure Environment

```bash
cp .env.example .env
```

Open `.env` and fill in every value:

```
DATABASE_URL=postgresql://inventory_user:your_secure_password@localhost:5432/inventory_db
SECRET_KEY=generate-a-256-bit-random-string-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=480
REFRESH_TOKEN_EXPIRE_DAYS=7
MAIL_USERNAME=your@gmail.com
MAIL_PASSWORD=your-gmail-app-password
MAIL_FROM=noreply@yourcompany.com
MAIL_PORT=587
MAIL_SERVER=smtp.gmail.com
MAIL_STARTTLS=true
MAIL_SSL_TLS=false
FRONTEND_URL=http://localhost:5173
COMPANY_NAME=Your Company Name
```

To generate a secure SECRET_KEY:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### 3.4 Seed Initial Data

Seed is handled by `database_hole/02_seed_data.sql` (psql-only).
No Alembic migrations are required for the normal setup flow.

This creates:
- Default admin user (email: admin@company.com, password: Admin@123)
- Units of measure: PCS, KG, G, LTR, ML, BOX, PACK, MTR, NOS
- Default product category: General
- Placeholder company row

### 3.5 Start Backend Server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API is available at: http://localhost:8000
API documentation: http://localhost:8000/docs

---

## 4. Frontend Setup

### 4.1 Install Dependencies

```bash
cd frontend
npm install
```

### 4.2 Configure Environment

```bash
cp .env.example .env
```

Open `.env`:

```
VITE_API_BASE_URL=http://localhost:8000
```

### 4.3 Start Development Server

```bash
npm run dev
```

Frontend is available at: http://localhost:5173

---

## 5. First Login

1. Open http://localhost:5173
2. Login with: admin@company.com / Admin@123
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
