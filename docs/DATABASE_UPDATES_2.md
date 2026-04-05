# Database Updates Log

---

## DB-1: GRN Module - Payment Due Date Column
**Date**: April 3, 2026
**Status**: ✅ Completed
**Test Case**: GRN-005
**Module**: GRN
**Type**: Feature

### Changes
- Added `payment_due_date` DATE column to `goods_receipt_notes` table
- Column is nullable (auto-calculated server-side)
- Migration file: `database/GRN_PAYMENT_DUE_DATE.sql`
- Applied via direct SQL execution

### Files Modified
- `database/01_schema.sql` - (reference only, no direct edit)
- `database/GRN_PAYMENT_DUE_DATE.sql` - Migration script (NEW)

---

## DB-2: GRN Module - Free Quantity Column
**Date**: April 3, 2026
**Status**: ✅ Completed
**Test Case**: GRN-009
**Module**: GRN
**Type**: Feature

### Changes
- Added `free_quantity` NUMERIC(12,4) column to `grn_items` table
- Column is NOT NULL with DEFAULT 0
- Migration file: `database/GRN_FREE_QUANTITY.sql`
- Applied via direct SQL execution

### Files Modified
- `database/GRN_PAYMENT_DUE_DATE.sql` - Migration script (NEW)
- `database/GRN_FREE_QUANTITY.sql` - Migration script (NEW)
- `database/ALL_UPDATES_2.sql` - Combined migration script (NEW)

---

## DB-3: Execute Pending Migrations for Suppliers & Customers Tables
**Date**: April 4, 2026
**Status**: ✅ Completed
**Module**: Suppliers, Customers, Company
**Type**: Bug Fix - Missing Database Columns

### Issue
Backend was throwing `UndefinedColumn` error when accessing `/api/v1/suppliers` endpoint:
```
sqlalchemy.exc.ProgrammingError: (psycopg2.errors.UndefinedColumn) column suppliers.gstin_status does not exist
```

### Root Cause
Database migrations were created but never executed. The SQLAlchemy model had been updated with new fields, but the actual PostgreSQL database schema was missing these columns.

### Changes
Executed `backend/run_migration.py` which added the following missing columns:

**Suppliers Table:**
- `gstin_status` VARCHAR(20) DEFAULT 'non-registered'
- `business_type` VARCHAR(20) DEFAULT 'domestic'
- `billing_country` VARCHAR(100)
- `company_director_name` VARCHAR(255)
- `company_director_contact` VARCHAR(255)

**Customers Table:**
- `gstin_status` VARCHAR(20) DEFAULT 'non-registered'
- `business_type` VARCHAR(20) DEFAULT 'domestic'
- `billing_country` VARCHAR(100)
- `shipping_country` VARCHAR(100)
- `company_director_name` VARCHAR(255)
- `company_director_contact` VARCHAR(255)
- `currency_code` VARCHAR(10) DEFAULT 'INR'

**Company Table:**
- `gstin_status` VARCHAR(20) DEFAULT 'non-registered'
- `company_director_name` VARCHAR(255)
- `company_director_contact` VARCHAR(255)
- `account_holder_name` VARCHAR(255)

**Other Tables:**
- `purchase_orders`: `currency_code`, `exchange_rate`
- `sales_orders`: `currency_code`, `exchange_rate`
- `users`: `failed_login_attempts`, `locked_until`
- `products`: `safety_stock`, `status`
- `goods_receipt_notes`: `payment_due_date`
- `grn_items`: `batch_no`, `manufacture_date`, `expiry_date`, `free_quantity`
- `sales_invoice_items`: `order_unit`, `batch_no`, `manufacture_date`, `expiry_date`, `free_quantity`

### Migration Method
- Used existing `backend/run_migration.py` script
- All statements are idempotent (ADD COLUMN IF NOT EXISTS)
- Safe to run multiple times without data loss
- Verified all 5 required supplier columns exist post-migration

### Files Modified
- Database: All columns added via migration script execution
- `backend/run_migration.py` - Migration execution script (existing, utilized)
- `backend/verify_columns.py` - Verification script (NEW)

---

## DB-4: Purchase Order Module - No Database Changes Required
**Date**: April 5, 2026
**Status**: ✅ Verified - No Changes Needed
**Test Case**: PO-01
**Module**: Purchase Order
**Type**: Bug Fix - Frontend/Backend Only

### Overview
Investigated database schema for Purchase Order product dropdown issue.

### Findings
- Products table already exists with all required fields
- No new fields needed - issue was with data fetching (pagination), not schema
- Existing fields used: `id`, `name`, `purchase_price`, `gst_rate`, `is_deleted`
- All products are already stored correctly in database

### Conclusion
No database schema changes or migrations required. Fix implemented at API layer only.

---

## DB-5: Product Module - No Database Changes Required
**Date**: April 5, 2026
**Status**: ✅ Verified - No Changes Needed
**Test Case**: Prod-01
**Module**: Product
**Type**: Feature/Improvement - Frontend/Backend Only

### Overview
Investigated database schema for Product page search and pagination feature.

### Findings
- Products table already exists with all required fields for search and display
- Fields used for search: `name`, `product_code`, `sku`, `description` - all already exist
- No new fields needed - feature implemented at application layer only
- Backend sorting uses existing `name` field with alphabetical ordering

### Conclusion
No database schema changes or migrations required. Feature implemented at API and UI layers only.

---

## DB-6: Billing PDFs - No Database Changes Required
**Date**: April 5, 2026
**Status**: ✅ Verified - No Changes Needed
**Test Case**: Bill-001
**Module**: POs, Tax Invoices, Quotations
**Type**: Feature - Backend Only (PDF Generation)

### Overview
Investigated database schema for billing PDF pagination feature.

### Findings
- All required data (POs, invoices, quotations, line items) already stored correctly
- No new fields needed - pagination is purely a presentation layer concern
- PDF generation queries all existing data and applies pagination during rendering

### Conclusion
No database schema changes or migrations required. Feature implemented at PDF generation layer only.
