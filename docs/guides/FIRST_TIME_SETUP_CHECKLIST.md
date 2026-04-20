# First-Time Setup Checklist (One Page)

Use this exact checklist on a new machine.

## 1. Prerequisites - MUST INSTALL

### Install in this order:

1. **PostgreSQL** (most important for setup)
   - Windows: Download from https://www.postgresql.org/download/windows/
   - During install: remember the password you set for `postgres` user
   - Default: port 5432
   - Check: Open PowerShell and run `psql --version`

2. **Python 3.11 or 3.12**
   - Download from https://www.python.org/downloads/
   - IMPORTANT: Check "Add Python to PATH" during install
   - Check: `python --version`

3. **Node.js 20+**
   - Download from https://nodejs.org/
   - This also installs npm
   - Check: `npm --version`

### Quick verification (run all, must show versions):

```powershell
python --version        # Should show 3.11+
node --version          # Should show 20+
npm --version           # Should show 10+
psql --version          # Should show PostgreSQL 15+
createdb --version      # Should show createdb version
```

**If any command fails:** Re-install that tool, make sure to add it to PATH.

---

## 1b. (Recommended) Run Automatic Prerequisite Check

From repo root, run this to catch any missing tools BEFORE starting setup:

```powershell
python verify_prerequisites.py
```

Should show green checkmarks ([OK]) for all items. If any show red ([FAIL]), install that tool before proceeding.

## 2. Ensure PostgreSQL is Running

**Windows**: PostgreSQL service should auto-start. Check:
- Open Windows Services and search for "postgres"
- Should show "PostgreSQL Server" with status "Running"
- If not running, start it

**If PostgreSQL won't start**: See Troubleshooting #4 below.

## 3. Clone and Open Project

```powershell
git clone <your-repo-url>
cd inventory-management-system-full-project
```

## 4. Configure Database Credentials (Important!)

Open `backend/.env` in any text editor.

**Find this line:**
```
DATABASE_URL=postgresql://postgres:root@localhost:5432/ims_db
```

**Adjust if needed:**
- `postgres` = PostgreSQL username (almost always "postgres")
- `root` = The password YOU set during PostgreSQL install (CHANGE THIS if different)
- `localhost:5432` = default location (don't change unless PostgreSQL is on different port/machine)
- `ims_db` = database name (can stay as-is)

**Example: If your PostgreSQL password is "MyPassword123":**
```
DATABASE_URL=postgresql://postgres:MyPassword123@localhost:5432/ims_db
```

**If unsure of password**: You can reset PostgreSQL password (Google "reset PostgreSQL password Windows" if needed).

## 5. Run One Command Setup

**Run this from repo root (where you see setup_db.py):**

```powershell
python setup_db.py
```

**What this does (AUTO):**
- [OK] Creates Python virtual environment for backend
- [OK] Installs all backend Python packages
- [OK] Connects to PostgreSQL and creates database
- [OK] Creates all required tables
- [OK] Seeds default data (admin user, etc.)

**Expected output should end with:**
```
[OK] Setup completed successfully
```

### If setup fails:

See "Troubleshooting" section at bottom.

## 6. Start Backend Server

Open first PowerShell terminal:

```powershell
cd backend
.venv\Scripts\activate
uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

**Wait for the message:**
```
Uvicorn running on http://127.0.0.1:8001
```

## 7. Start Frontend Server

Open SECOND PowerShell terminal (keep first one running):

```powershell
cd frontend
npm install
npm run dev
```

**Wait for the message showing a local URL** (usually http://localhost:3001)

## 8. Open in Browser and Login

Go to the URL from step 7 (usually http://localhost:3001)

**Use these credentials:**
- **Email:** IMS_ADMIN_EMAIL
- **Password:** IMS_ADMIN_PASSWORD

You should now see the Dashboard!

## 9. Troubleshooting

### [FAIL] "python: command not found" or "python is not recognized"

**Fix:** Python not in PATH or not installed.
- Re-install Python from https://www.python.org/downloads/
- **IMPORTANT:** Check "Add Python to PATH" during install
- Restart PowerShell after install

### [FAIL] "psql: command not found" or "createdb: command not found"

**Fix:** PostgreSQL not in PATH.
- Install PostgreSQL from https://www.postgresql.org/download/windows/
- During install: check "Command Line Tools"
- Restart PowerShell after install

### [FAIL] Setup script fails at "Dependency installation failed"

**Likely cause:** Python requirements install failed.

**Fix:**
1. Manually install: `cd backend && python -m pip install --upgrade pip`
2. Then: `pip install -r requirements.txt`
3. If still fails, show the error messages to someone technical

### [FAIL] Setup script fails at "Could not auto-create database"

**Likely cause:** PostgreSQL not running OR wrong password.

**Fix:**
1. Check Windows Services for "PostgreSQL" - should show "Running"
2. If not running: right-click and click "Start"
3. Verify DATABASE_URL in backend/.env has your correct PostgreSQL password
4. Re-run: `python setup_db.py`

### [FAIL] "Database connection failed" or "FATAL: password authentication failed"

**Likely cause:** Wrong PostgreSQL password in DATABASE_URL.

**Fix:** Edit backend/.env and update the password part:
```
# This part -> v
DATABASE_URL=postgresql://postgres:PASSWORD_HERE@localhost:5432/ims_db
```

If you forgot your PostgreSQL password, you can reset it:
- Windows: Search "Edit environment variables" in Windows Search
- Look for POSTGRES_HOME or similar
- Or reinstall PostgreSQL with a known password

### [FAIL] Backend starts but says "Port 8001 already in use"

**Fix:** Kill whatever is using port 8001:
```powershell
netstat -ano | findstr :8001
# Then kill the process ID shown
taskkill /PID XXXX /F
```

Or just use a different port: `uvicorn app.main:app --reload --host 127.0.0.1 --port 8002`

### [FAIL] Frontend shows CORS errors or won't connect to backend

**Fix:** Make sure BOTH terminals are running:
1. Backend terminal: still showing "Uvicorn running on..."
2. Frontend terminal: still showing the local URL

If backend crashed, restart it: `uvicorn app.main:app --reload --host 127.0.0.1 --port 8001`

### [FAIL] "npm: command not found"

**Fix:** Node.js not installed or not in PATH.
- Install Node.js from https://nodejs.org/
- Make sure to restart PowerShell after install
- Verify: `npm --version` should show version number

### [FAIL] "npm ERR! code ERESOLVE"

**Fix:** Node dependencies conflict (rare). Try:
```powershell
cd frontend
rm package-lock.json
npm install
```

### [FAIL] Can't login (wrong credentials)

**Default credentials are:**
- Email: IMS_ADMIN_EMAIL
- Password: IMS_ADMIN_PASSWORD

If these don't work, the database seed may have failed. Re-run from backend folder:
```powershell
cd backend
.venv\Scripts\activate
python -m app.utils.seed
```

### [FAIL] Still stuck?

1. **Copy the exact error message**
2. **Share it with a developer** - include:
   - What command you ran
   - The full error message from the terminal
   - Which step (1-9) you're on

- Stop stale process using port 8001, then restart backend.

4. Re-run setup safely

```powershell
python setup_db.py
```

It is idempotent and safe to run multiple times.




