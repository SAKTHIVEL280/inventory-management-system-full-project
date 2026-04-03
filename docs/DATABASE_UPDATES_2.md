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
