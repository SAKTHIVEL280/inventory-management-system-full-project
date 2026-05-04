# Server Quick Guide - 2026-05-04

This guide applies the DB/schema fixes and the automatic company assignment updates introduced today.

## 1) Update backend environment
Edit `backend/.env` on the server and ensure `DATABASE_URL` is correct.
Example:
```
DATABASE_URL=postgresql://ims_user:YOUR_PASSWORD@localhost:5432/ims_db
```

## 2) Apply DB migrations (required)
Run these in the repo root on the server:
```bash
psql -h localhost -U ims_user -d ims_db -f database/migrations/0002_add_company_customer_supplier_fields.sql
psql -h localhost -U ims_user -d ims_db -f database/migrations/0003_server_patch_2026_05_04.sql
```

## 3) Optional consolidated migration
If you prefer using the consolidated pack instead of individual files:
```bash
psql -h localhost -U ims_user -d ims_db -f database/ALL_UPDATES_2.sql
```

## 4) (Optional) Reset data
If you need to clear all data but keep schema:
```bash
psql -h localhost -U ims_user -d ims_db -f database/CLEAR_ALL_DATA.sql
```

## 5) Restart backend
```bash
cd backend
uvicorn app.main:app --reload --port 8001
```

## 6) Verify tenant assignment
```bash
psql -h localhost -U ims_user -d ims_db -c "SELECT id, name FROM company;"
psql -h localhost -U ims_user -d ims_db -c "SELECT id, email, company_id FROM users ORDER BY created_at DESC;"
```

## Notes
- The backend assigns `company_id` during company save and at login if it is missing (fallback to the first company row).
- The frontend refreshes the user context after company save, so the session picks up `company_id` immediately.
- If the company table is empty, create/update the company via the Company Profile screen, then log out and log back in.
