# Database Updates Summary - Company Module Enhancements

**Date**: April 3, 2026
**Feature**: Company Director & GSTIN Registration Status

## Quick Reference

### New Columns Added
1. `company_director_name` - VARCHAR(255), NULL
2. `company_director_contact` - VARCHAR(255), NULL
3. `gstin_status` - VARCHAR(20), DEFAULT 'non-registered'

### Modified Columns
- `gstin` - Now works with `gstin_status` toggle

---

## Deployment Instructions

### For Existing Database (Production Migration)

**Run this SQL script** (`database/ALL_UPDATES.sql`):

```sql
ALTER TABLE company
ADD COLUMN company_director_name VARCHAR(255) NULL DEFAULT NULL,
ADD COLUMN company_director_contact VARCHAR(255) NULL DEFAULT NULL,
ADD COLUMN gstin_status VARCHAR(20) NOT NULL DEFAULT 'non-registered';
```

**Execution Steps**:
1. Backup `company` table before running
2. Run the ALTER statements
3. Verify column creation: `DESCRIBE company;`
4. Test with existing records - new fields will be NULL/default

### For New Deployments (Fresh Setup)

Use the complete schema provided in `ALL_UPDATES.sql` under "FOR NEW DEPLOYMENTS" section.

---

## Data Integrity Notes

✅ **Backward Compatible**: 
- Existing company records will have NULL for new optional fields
- `gstin_status` defaults to 'non-registered' for all existing records
- No data loss occurs

✅ **Non-Destructive Migration Rule**:
- Migration scripts must only add missing schema objects (for example `ADD COLUMN IF NOT EXISTS`).
- Do not include `DELETE`, `TRUNCATE`, `DROP TABLE`, or `DROP COLUMN` in feature migrations.
- Existing sample data and production rows must remain untouched.

⚠️ **Important**:
- If existing records have GSTIN values, consider updating `gstin_status` to 'registered'
- Migration script for updating existing GSTIN records:

```sql
-- Optional: Set status to 'registered' for companies with existing GSTIN
UPDATE company 
SET gstin_status = 'registered' 
WHERE gstin IS NOT NULL AND gstin != '';
```

---

## Rollback Plan

Use application-level rollback (revert code deployment) instead of destructive schema rollback.

**Note**: To protect existing data, avoid destructive rollback SQL in feature migration files.

---

## Validation Queries

**Verify new columns exist**:
```sql
SELECT COLUMN_NAME, IS_NULLABLE, COLUMN_DEFAULT 
FROM INFORMATION_SCHEMA.COLUMNS 
WHERE TABLE_NAME = 'company' 
AND COLUMN_NAME IN ('company_director_name', 'company_director_contact', 'gstin_status');
```

**Check existing data**:
```sql
SELECT id, name, gstin, company_director_name, company_director_contact, gstin_status 
FROM company;
```

---

## File References

- **Migration Script**: `database/ALL_UPDATES.sql`
- **Backend Model**: `backend/app/models/company.py`
- **Backend Schema**: `backend/app/schemas/company.py`
- **Frontend Component**: `frontend/src/pages/CompanyPage.tsx`
- **Frontend Types**: `frontend/src/types/index.ts`

---

## Dashboard Module - Cash In Flow Graph (Section Updated)

### Schema Impact
- No schema changes required
- No new table required
- No `ALTER TABLE` required
- No migration required

### Existing Tables/Columns Used
- `sales_invoices.amount_due`
- `sales_invoices.invoice_date`
- `sales_invoices.status`
- `customers.id`
- `customers.company_name`

### Operational Note
- Cash In Flow is implemented as query aggregation in backend reports API.
