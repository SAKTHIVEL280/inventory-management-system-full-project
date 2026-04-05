# Database Updates Log

---

## DB-24: Branding Inline Logo Fallback - No Database Changes Required
**Date**: April 5, 2026
**Status**: ✅ Verified - No Changes Needed
**Test Case**: Sidebar Top-Left Logo Still Missing on Ubuntu
**Module**: Company / Branding API
**Type**: Bug Fix - Backend/Frontend Logic Only

### Overview
Validated schema impact for branding inline logo fallback implementation.

### Findings
- Change is API response and frontend rendering behavior only.
- Existing company/logo fields are unchanged.

### Conclusion
No database changes required.

---

## DB-23: Ubuntu Frontend Load Fix - No Database Changes Required
**Date**: April 5, 2026
**Status**: ✅ Verified - No Changes Needed
**Test Case**: Frontend Not Loading After Server Upload
**Module**: Deployment / Frontend Runtime
**Type**: Bug Fix - Frontend Logic Only

### Overview
Validated schema impact for Ubuntu frontend load fix.

### Findings
- Fix modifies frontend API base/proxy behavior only.
- No table/column/data migration required.

### Conclusion
No database changes required.

---

## DB-22: Sidebar Logo Shape Update - No Database Changes Required
**Date**: April 5, 2026
**Status**: ✅ Verified - No Changes Needed
**Test Case**: Sidebar Top-Left Logo Shape
**Module**: Company / Branding
**Type**: UI Enhancement - Frontend Only

### Overview
Validated schema impact for sidebar logo outer-shape update.

### Findings
- Change is presentation-only (CSS class update).
- No table/column/data changes required.

### Conclusion
No database changes required.

---

## DB-21: Sidebar Logo Endpoint Auth Fix - No Database Changes Required
**Date**: April 5, 2026
**Status**: ✅ Verified - No Changes Needed
**Test Case**: Sidebar Top-Left Logo Visibility After Refresh
**Module**: Company / Branding API
**Type**: Bug Fix - Backend/Frontend Logic Only

### Overview
Validated schema impact for final sidebar logo auth fix.

### Findings
- Change is API endpoint auth behavior only.
- Existing company/logo fields are unchanged and sufficient.

### Conclusion
No database changes required.

---

## DB-20: Sidebar Logo Visibility Fix - No Database Changes Required
**Date**: April 5, 2026
**Status**: ✅ Verified - No Changes Needed
**Test Case**: Sidebar Top-Left Logo Visibility
**Module**: Company / Branding API
**Type**: Bug Fix - Backend/Frontend Logic Only

### Overview
Validated schema impact for sidebar logo visibility fix.

### Findings
- Fix uses new API endpoints and frontend query update only.
- Existing company logo columns/data are sufficient.

### Conclusion
No database changes required.

---

## DB-19: Logo Visibility Fix - No Database Changes Required
**Date**: April 5, 2026
**Status**: ✅ Verified - No Changes Needed
**Test Case**: Company Logo Visibility in App
**Module**: Company / Static Assets
**Type**: Bug Fix - Backend/Frontend Logic Only

### Overview
Validated schema impact for company logo visibility fix.

### Findings
- Issue was caused by static path/url handling, not database data model.
- No table/column/migration changes required.

### Conclusion
No database changes required.

---

## DB-18: Consolidated SQL Update File Synced with Migration Runner Alterations
**Date**: April 5, 2026
**Status**: ✅ Completed
**Test Case**: Migration Consistency Audit
**Module**: Database Migration Scripts
**Type**: Script Alignment

### Overview
Synchronized consolidated SQL update script with alteration statements already present in migration runner.

### Changes Made
- Updated `database/ALL_UPDATES_2.sql` header to reflect consolidated compatibility updates.
- Added missing idempotent ALTER statements for:
	- Users auth-hardening columns
	- Product compatibility columns
	- Supplier/company/customer compatibility columns
	- Purchase/Sales order currency columns
	- GRN batch tracking columns
- Kept existing GRN, sales invoice item extension, and SKU non-unique migration sections intact.

### Files Modified
- `database/ALL_UPDATES_2.sql`

### Verification
- Confirmed key alterations now exist in both:
	- `database/ALL_UPDATES_2.sql`
	- `backend/run_migration.py`

---

## DB-17: Seed 10 Additional Medicine Products in Product Master
**Date**: April 5, 2026
**Status**: ✅ Completed
**Test Case**: Product Master Data Additions
**Module**: Products
**Type**: Data Update

### Overview
Inserted ten additional medicine products into `products` table.

### Data Mapping Used
- Category: `Medicine`
- Base Unit (`sku`): `PCS`
- Primary UOM: `PCS`
- Order Unit (`alt_uom_id`): `BOX`
- Conversion: `1 BOX = 10 PCS`

### Inserted Records
- `PRD-00029` - Paracetamol 650 Tablet Strip
- `PRD-00030` - Azithromycin 500 Tablet Strip
- `PRD-00031` - Cetirizine 10 Tablet Strip
- `PRD-00032` - Omeprazole 20 Capsule Strip
- `PRD-00033` - Vitamin C 500 Tablet Strip
- `PRD-00034` - Iron Folic Acid Syrup 200ml
- `PRD-00035` - Zinc Plus Syrup 200ml
- `PRD-00036` - Probiotic Capsule Strip
- `PRD-00037` - Pain Relief Gel 30g
- `PRD-00038` - Antacid Suspension 170ml

### Verification
- Inserted count: 10
- Verified all inserted rows have `base_unit=PCS` and `order_unit=BOX`.

### Files Modified
- `docs/DATABASE_UPDATES_2.md`

---

## DB-16: Quotation PDF Column Removal - No Database Changes Required
**Date**: April 5, 2026
**Status**: ✅ Verified - No Changes Needed
**Test Case**: Quotation PDF Table Simplification
**Module**: Quotations PDF
**Type**: Feature - Backend Rendering Only

### Overview
Validated schema impact before removing quotation PDF columns.

### Findings
- Removed fields are presentation-only columns in PDF template.
- No table or column changes required in database.

### Conclusion
No database changes required.

---

## DB-15: Invoice Due Date Enforcement Refinement - No Database Changes Required
**Date**: April 5, 2026
**Status**: ✅ Verified - No Changes Needed
**Test Case**: Invoice Due Date Auto-Calculate (No Manual Input)
**Module**: Sales Invoices
**Type**: Enhancement - Backend/Frontend Logic Only

### Overview
Validated schema impact for due-date enforcement refinement.

### Findings
- Existing `customers.payment_terms_days` and `sales_invoices.due_date` fields are sufficient.
- No new columns, constraints, or migration scripts required.

### Conclusion
No database changes required.

---

## DB-14: Invoice Due Date Auto-Calculation - No Database Changes Required
**Date**: April 5, 2026
**Status**: ✅ Verified - No Changes Needed
**Test Case**: Invoice Due Date Auto-Calculate
**Module**: Sales Invoices
**Type**: Feature - Backend/Frontend Logic Only

### Overview
Validated schema requirements before implementing invoice due date auto-calculation.

### Findings
- Invoice due date already exists as `sales_invoices.due_date`.
- Customer payment terms already exist as `customers.payment_terms_days`.
- Feature is computation logic only and does not require new fields/tables.

### Conclusion
No database schema or migration changes required.

---

## DB-13: Invoice/Quotation Date Label Update - No Database Changes Required
**Date**: April 5, 2026
**Status**: ✅ Verified - No Changes Needed
**Test Case**: PDF Header Label Update
**Module**: Tax Invoices, Quotations
**Type**: Feature - Backend Rendering Only

### Overview
Validated schema requirements for invoice/quotation date label update in PDFs.

### Findings
- Label change is template/context only.
- No field/table/migration changes required.

### Conclusion
No database changes required for this update.

---

## DB-12: Invoice/Quotation PDF Layout Update - No Database Changes Required
**Date**: April 5, 2026
**Status**: ✅ Verified - No Changes Needed
**Test Case**: Layout Change - Tax Invoice & Quotation PDF
**Module**: Tax Invoices, Quotations
**Type**: Feature - Backend Rendering Only

### Overview
Validated schema requirements before implementing invoice/quotation PDF header/table updates.

### Findings
- No new database field was required for requested PDF-only layout changes.
- Existing invoice item fields already store batch, MFG, EXP, and free quantity data.
- Quotation table structure remained unchanged as requested.

### Conclusion
No database schema/migration changes required for this update.

---

## DB-11: Billing PDF Packing/Order Unit Fix - No Database Changes Required
**Date**: April 5, 2026
**Status**: ✅ Verified - No Changes Needed
**Test Case**: Billing PDF Packing/Order Unit Display
**Module**: POs, Tax Invoices, Quotations
**Type**: Bug Fix - Backend Rendering Only

### Overview
Validated schema requirements for packing/order unit display correction in billing PDFs.

### Findings
- Required order unit data already exists in `products.alt_uom_id`.
- No new fields, constraints, or migration scripts were needed.
- Issue was strictly formatting logic in backend PDF helper.

### Conclusion
No database changes required for this fix.

---

## DB-10: Seed 5 Tonic Products in Product Master
**Date**: April 5, 2026
**Status**: ✅ Completed
**Test Case**: Data Setup - Product Master
**Module**: Products
**Type**: Data Update

### Overview
Inserted five tonic medicine products into the `products` table for IMS master data.

### Inserted Records
- `PRD-00024` - Liv-52 Tonic 200ml
- `PRD-00025` - B-Complex Tonic 200ml
- `PRD-00026` - Hemoglobin Plus Tonic 300ml
- `PRD-00027` - Calcium D3 Tonic 200ml
- `PRD-00028` - Multivitamin Tonic 200ml

### Data Mapping Used
- Category: `Medicine`
- Base Unit (`sku`): `PCS`
- Primary UOM: `PCS`
- Order Unit/Packing: `BOX`
- Conversion: `1 BOX = 10 PCS`
- GST rate: `12%`

### Files Modified
- `docs/DATABASE_UPDATES_2.md`

---

## DB-9: Billing PDF Pagination (15 Items) - No Database Changes Required
**Date**: April 5, 2026
**Status**: ✅ Verified - No Changes Needed
**Test Case**: Bill-03
**Module**: POs, Tax Invoices, Quotations
**Type**: Feature - Backend Rendering Only

### Overview
Validated database requirements for billing PDF pagination update.

### Findings
- Pagination uses existing transactional rows and does not require new columns/tables.
- Existing PO/Invoice/Quotation line-item fields already provide required rendering data.
- No schema alteration needed.

### Conclusion
No database changes or migration scripts required for Bill-03.

---

## DB-8: Products - Remove Unique Constraint from Base Unit Field (SKU)
**Date**: April 5, 2026
**Status**: ✅ Completed
**Test Case**: Product Update (Modify/Change Product)
**Module**: Products
**Type**: Bug Fix

### Overview
Fixed database constraint mismatch where product Base Unit values (stored in `products.sku`) were incorrectly enforced as unique.

### Changes
- Dropped legacy unique constraint `products_sku_key` from `products` table.
- Added idempotent SQL block to remove any remaining unique indexes involving `products.sku`.
- Added dedicated migration script for this fix.
- Added the same statements in consolidated updates script.
- Updated compatibility migration runner to apply the fix on existing databases.

### Files Modified
- `database/PRODUCT_BASE_UNIT_NON_UNIQUE.sql` - Migration script (NEW)
- `database/ALL_UPDATES_2.sql` - Added non-unique SKU migration section
- `backend/run_migration.py` - Added idempotent migration statements
- `database/01_schema.sql` - Removed `UNIQUE` from `sku` in schema reference

### Execution
- Applied successfully using `backend/run_migration.py`.

---

## DB-7: Purchase Order PDF Labels - No Database Changes Required
**Date**: April 5, 2026
**Status**: ✅ Verified - No Changes Needed
**Test Case**: Bill-02
**Module**: POs, Tax Invoices, Quotations
**Type**: Feature - Existing Schema Reuse

### Overview
Validated product and supplier schema before implementation to determine if new fields were required for Purchase Order PDF label/data update.

### Findings
- Product order-unit data already exists through `products.alt_uom_id` and `products.alt_uom_conversion`.
- Product base-unit data already exists in `products.sku` (current project mapping).
- Supplier payment terms already exists in `suppliers.payment_terms_days`.
- No missing fields for Bill-02, so no migration SQL was required.

### Conclusion
No database schema changes or SQL migration files required for Bill-02.

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
