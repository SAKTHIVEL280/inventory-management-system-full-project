# Production Deployment Runbook — Multi‑Tenant + Feature Rollout

> **Use this for the FIRST production deploy since the multi‑tenant conversion.**
> It adds `company_id` tenant isolation across the schema plus every feature/fix
> merged since (subscription plans, audit/action logs, receivables model, HR employee
> master column set, per‑invoice exchange rate, etc.).
>
>> **Production has NO CI/CD — it is deployed 100% MANUALLY using this runbook.**
> The GitHub Actions workflow `.github/workflows/deploy.yml` deploys the **stage**
> server only (on push to `version-1` / `stage`); it does not touch production and it
> does not run database migrations. For production you perform every step below by
> hand over SSH. This is true for this release **and every future release** until a
> production pipeline is set up.

---

## 0. Fill in your PRODUCTION values first

The values below are the **stage** server's layout (from `deploy.yml`) shown as a
reference. Production may use the same layout or a different host/DB/paths — confirm
each and substitute your production values before running any command.

| Thing | Stage reference | **Your production value** |
|---|---|---|
| SSH host / user | `hmsadmin@<stage-host>` | `______@______` |
| App directory | `~/projects/Billing_Software` | `______` |
| Backend service (systemd) | `billing-backend` | `______` |
| Backend venv | `backend/venv` (deps via `uv pip install -r backend/requirements.txt`) | `______` |
| Frontend serving | nginx from `frontend/dist` | `______` |
| Database | PostgreSQL; URL in `backend/.env` `DATABASE_URL` (must be `postgresql://…`) | `______` |
| Code branch to deploy | `version-1` | `______` |
| Migration runner | `backend/run_migration.py` (idempotent; safe to re‑run) | same |
| App URL | `http://139.59.62.156:8080` (stage) | `______` |

> Throughout this doc, wherever you see `billing-backend`, `~/projects/Billing_Software`,
> or `hmsadmin`, replace them with your production equivalents.

> ⚠️ **Do NOT change `SECRET_KEY`.** The field‑level encryption key (customer/supplier
> PAN, bank account no.) is derived from `SECRET_KEY`. Rotating it makes existing
> encrypted values undecryptable. Keep the current value.

---

## 1. Pre‑deploy checklist

- [ ] Announce a short **maintenance window** (schema migration + restart).
- [ ] Confirm you can SSH to the server as `hmsadmin`.
- [ ] Confirm `backend/.env` on the server has the correct production values (see §6).
- [ ] **Take a full database backup** (non‑negotiable — this is a schema migration).
- [ ] Note the current commit so you can roll back: `git -C ~/projects/Billing_Software rev-parse HEAD`.

### 1a. Backup the database (run ON the server)

```bash
cd ~/projects/Billing_Software/backend
# Pull DB name/creds from .env; adjust if your DATABASE_URL differs
export $(grep -E '^DATABASE_URL=' .env | xargs)   # loads DATABASE_URL into the shell
TS=$(date +%Y%m%d_%H%M%S)
pg_dump "$DATABASE_URL" -Fc -f ~/backup_ims_${TS}.dump
ls -lh ~/backup_ims_${TS}.dump          # verify the file exists and is non‑empty
```

Keep this file until you have verified the deploy is healthy.

---

## 2. Manual runbook (this release)

Run every step **on the server** unless noted.

### Step 1 — Put the app in maintenance (optional but recommended)
Either stop the backend or show a maintenance page in nginx. Simplest:
```bash
sudo systemctl stop billing-backend
```

### Step 2 — Pull the new code
```bash
cd ~/projects/Billing_Software
git fetch origin
git checkout version-1
git pull origin version-1
git log -1 --oneline        # confirm you're on the intended commit
```

### Step 3 — Install/upgrade backend dependencies
```bash
source backend/venv/bin/activate
export PATH="$HOME/.local/bin:$PATH"          # so `uv` is found
uv pip install -r backend/requirements.txt
```

### Step 4 — Run the database migration  ⭐ (the critical step)
`run_migration.py` is **idempotent** (all `ADD COLUMN IF NOT EXISTS`, `CREATE TABLE
IF NOT EXISTS`, guarded backfills). It brings a legacy single‑tenant DB fully up to
date: adds `company_id` everywhere, FKs, per‑tenant unique codes, subscription plans,
audit‑logs table, and the new `sales_invoices.currency_code` / `exchange_rate`
columns (migration 0029).

```bash
cd ~/projects/Billing_Software/backend
python run_migration.py            # reads DATABASE_URL from backend/.env
```
Expected: it prints the statements it runs and ends without a traceback. Re‑running
it is safe if anything is interrupted.

### Step 5 — Multi‑tenant backfill verification  ⭐
The migration assigns all pre‑existing rows to the **earliest `company` row**. Confirm
a tenant company exists and nothing is left unassigned:

```bash
psql "$DATABASE_URL" -c "SELECT count(*) AS companies FROM company;"
psql "$DATABASE_URL" -c "SELECT count(*) AS users_without_company FROM users WHERE company_id IS NULL;"
psql "$DATABASE_URL" -c "SELECT count(*) AS invoices_without_company FROM sales_invoices WHERE company_id IS NULL;"
```

- `companies` must be **≥ 1**.
- The two `*_without_company` counts must be **0**.

**If `companies = 0`** (a truly bare single‑tenant DB with no company row), create one
tenant and re‑run the migration so the backfill can attach existing data:

```bash
# Create a tenant company (adjust name/GSTIN), then backfill by re-running the migration.
psql "$DATABASE_URL" -c "INSERT INTO company (id, name) VALUES (gen_random_uuid(), 'Your Company Pvt Ltd') ON CONFLICT DO NOTHING;"
python run_migration.py
# re-run the verification queries above — the *_without_company counts must now be 0
```

**If any `*_without_company > 0`** after that, attach them to the first company:
```bash
psql "$DATABASE_URL" <<'SQL'
DO $$
DECLARE cid uuid;
BEGIN
  SELECT id INTO cid FROM company ORDER BY created_at ASC LIMIT 1;
  UPDATE users            SET company_id = cid WHERE company_id IS NULL;
  UPDATE sales_invoices   SET company_id = cid WHERE company_id IS NULL;
  -- (run_migration.py already covers the full table list; this is a safety net)
END $$;
SQL
```

### Step 6 — Build & deploy the frontend (manual)
The frontend must be built with the production API base URL and placed in
`frontend/dist`. Production has no pipeline, so build it yourself.

**Option A — build on the production server** (needs Node 20+ installed there):
```bash
cd ~/projects/Billing_Software/frontend
npm ci
VITE_API_BASE_URL="<your production API base, e.g. https://your-domain>" npm run build
chmod -R 755 dist
```

**Option B — build on your laptop and copy up** (if the server has no Node):
```bash
# on your machine, in the repo:
cd frontend
npm ci
VITE_API_BASE_URL="<your production API base>" npm run build
scp -r dist/* <prod_user>@<prod_host>:~/projects/Billing_Software/frontend/dist/
```
Then on the server: `chmod -R 755 ~/projects/Billing_Software/frontend/dist`.

### Step 7 — Restart services
```bash
sudo systemctl restart billing-backend
sleep 3
sudo systemctl reload nginx
sudo systemctl status billing-backend --no-pager | head -8   # must be "active (running)"
```

### Step 8 — Smoke test (see §3). Then end the maintenance window.

---

## 3. Post‑deploy smoke test

```bash
# Backend health (from the server)
curl -fsS http://127.0.0.1:8000/health   # adjust port to your uvicorn bind; expect {"status":"ok",...}
```
Then in the browser (`http://139.59.62.156:8080`):

- [ ] Log in as a tenant admin.
- [ ] **Tenant isolation:** each list (Customers, Suppliers, Invoices, Products, Payments) shows only that tenant's data.
- [ ] Create a **Customer** and a **Supplier** → they appear in **Action Logs** (Module = Customers/Suppliers) with a version on edit.
- [ ] Create an **INR Sales Invoice** → totals/GST unchanged; PDF downloads.
- [ ] Create a **foreign‑currency invoice** (customer currency ≠ INR) → Exchange Rate field appears, line price converts from the product's INR price, total is exact, PDF shows the rate + INR equivalent.
- [ ] **Receivables/Payables**: record a receipt, allocate to an invoice; historical rows show the party name.
- [ ] Subscription/plan gating works for a non‑admin role.

If anything is broken, go to §4 (Rollback).

---

## 4. Rollback

Because this is a schema migration, rollback = **restore the DB backup + previous code**.

```bash
# 1) Stop backend
sudo systemctl stop billing-backend

# 2) Restore the database (DROPS current data — only if the deploy is unhealthy)
export $(grep -E '^DATABASE_URL=' ~/projects/Billing_Software/backend/.env | xargs)
pg_restore --clean --if-exists -d "$DATABASE_URL" ~/backup_ims_<TS>.dump

# 3) Check out the previous commit
cd ~/projects/Billing_Software
git checkout <previous_commit_sha>
source backend/venv/bin/activate && uv pip install -r backend/requirements.txt

# 4) Restart
sudo systemctl start billing-backend && sudo systemctl reload nginx
```

> The per‑migration `*_rollback.sql` files (e.g. `database/migrations/0029_*_rollback.sql`)
> only drop *that* migration's columns and cannot undo the multi‑tenant backfill — for a
> full revert, use the DB backup.

---

## 5. Subsequent production deploys (still manual)

Production has no pipeline, so **every** future release repeats the same manual flow —
just lighter once the schema is current:

1. Backup the DB (§1a).
2. `git pull` the new code (Step 2) + `uv pip install` (Step 3).
3. Run `python run_migration.py` **if the release adds any migration** (it's idempotent,
   so running it every time is harmless and is the safe default).
4. Rebuild & copy the frontend (Step 6).
5. Restart `billing-backend` + reload nginx (Step 7); smoke‑test (§3).

To reduce toil, save the **Quick reference** block at the bottom as a script on the
server (e.g. `~/deploy.sh`) and run it per release.

---

## 6. Required `backend/.env` (production)

Minimum keys the app validates at boot (see `backend/app/config.py`):

```dotenv
DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DBNAME
SECRET_KEY=<KEEP THE EXISTING VALUE — ≥32 chars, no placeholder; encryption key derives from this>
ENVIRONMENT=production
FRONTEND_URL=http://139.59.62.156:8080        # used for CORS + cookie domain
COOKIE_SECURE=false                            # true ONLY if served over HTTPS, else cookies won't set
# Mail (invoice email / notifications)
MAIL_USERNAME=...
MAIL_PASSWORD=...
MAIL_FROM=...
```

Validation rules enforced on startup:
- `DATABASE_URL` must start with `postgresql://`.
- `SECRET_KEY` ≥ 32 chars and not a placeholder (`your-`, `dev-secret`, `change-this-secret`).
- `ENVIRONMENT` ∈ `development | staging | production`.

---

## 7. Note on the stage pipeline (NOT production)

`.github/workflows/deploy.yml` auto‑deploys the **stage** server on push to
`version-1` / `stage`, using secrets `SSH_HOST`, `SSH_USER`, `SSH_PRIVATE_KEY`,
`VITE_API_BASE_URL`, `NOTIFY_EMAIL*`. **This does not deploy production** and never
runs migrations. Production is deployed only via the manual runbook in this document.
Do not point that workflow at production without adding a migration step and a
manual‑approval gate.

---

## Quick reference — the whole thing in order

```bash
# ON THE SERVER (hmsadmin)
cd ~/projects/Billing_Software/backend
export $(grep -E '^DATABASE_URL=' .env | xargs)
pg_dump "$DATABASE_URL" -Fc -f ~/backup_ims_$(date +%Y%m%d_%H%M%S).dump   # 1. BACKUP

sudo systemctl stop billing-backend                                       # 2. maintenance
cd ~/projects/Billing_Software && git pull origin version-1               # 3. code
source backend/venv/bin/activate && export PATH="$HOME/.local/bin:$PATH"
uv pip install -r backend/requirements.txt                                # 4. deps
cd backend && python run_migration.py                                     # 5. MIGRATE
psql "$DATABASE_URL" -c "SELECT count(*) FROM company;"                    # 6. verify (>=1)
psql "$DATABASE_URL" -c "SELECT count(*) FROM users WHERE company_id IS NULL;"   # must be 0
cd ../frontend && npm ci && VITE_API_BASE_URL="<prod>" npm run build && chmod -R 755 dist  # 7. FE
sudo systemctl start billing-backend && sleep 3 && sudo systemctl reload nginx             # 8. restart
sudo systemctl status billing-backend --no-pager | head -8                                 # 9. verify
```
