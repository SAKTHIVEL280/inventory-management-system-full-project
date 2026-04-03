# Frontend Updates Log

## FE-1: GRN Module - Add Product Code Field in New GRN Form
**Date**: April 3, 2026  
**Status**: ✅ Completed  
**Test Case**: GRN-001  
**Module**: GRN  
**Type**: Feature

### Overview
Added visible Product Code field in the GRN (Goods Receipt Note) form to display the product code alongside the product name in line items table.

### Changes Made

#### 1. GRN Form Modal - Line Items Table (`frontend/src/pages/GRNPage.tsx`)
- **Added "Product Code" column header** in the line items table header row
- **Added Product Code display cell** showing the product_code from the product master
- Display format: Shows actual product code (e.g., `PROD-001`) in bold styling
- Applied to both standalone GRN and PO-linked GRN modes
- Updated table colspan values for:
  - Empty state message row
  - Footer total row

#### 2. GRN Detail Modal - Line Items Table (`frontend/src/pages/GRNPage.tsx`)
- **Added "Product Code" column header** in the detail view table
- **Added Product Code display cell** showing the product_code
- Consistent formatting with the form modal

### Technical Details
- Product Code is displayed from the `product_code` field of the Product master
- Styling: `text-xs font-semibold text-neutral-700` for clear visibility
- Fallback: Shows `-` if product code is not available
- No backend or database changes required (product_code already exists in products table and is fetched)
- Product Code is already included in product data from the API

### Files Modified
- `frontend/src/pages/GRNPage.tsx` - Added Product Code column to both form and detail modals

### Testing Checklist
- [x] Product Code column appears in New GRN form line items table header
- [x] Product Code displays for each line item in the form
- [x] Product Code appears in GRN Detail modal line items table
- [x] Display works for both standalone and PO-linked GRNs
- [x] Table layout and spacing remain correct
- [x] No backend changes needed (product_code already in products table)

---

## FE-2: GRN Module - Merge Ordered/Received into Single Received Qty Column
**Date**: April 3, 2026
**Status**: ✅ Completed
**Test Case**: GRN-002
**Module**: GRN
**Type**: Feature

### Overview
Merged separate "Ordered" and "Received" columns into single editable "Received Qty" column when GRN is linked to a PO.

### Changes Made

#### GRN Form Modal - Line Items Table (`frontend/src/pages/GRNPage.tsx`)
- **Removed** separate "Ordered" and "Received" display-only columns
- **Added** single "Received Qty *" editable column for PO-linked GRNs
- Shows ordered and previously received quantities as helper text below input
- Input field has tooltip showing full context (ordered, previously received)
- Standalone GRNs continue to use simple "Qty *" column
- Updated colspan values for empty state and footer rows

### Technical Details
- Helper text format: "Ordered: X | Prev: Y" in small muted text
- Tooltip on hover shows: "Ordered: X, Previously received: Y"
- Input remains fully editable for received quantity
- No backend/database changes (uses existing quantity field)

### Files Modified
- `frontend/src/pages/GRNPage.tsx` - Merged columns in PO-linked GRN form

---

## FE-3: GRN Module - Unify "Received Qty" Column Across All GRN Views
**Date**: April 3, 2026
**Status**: ✅ Completed
**Test Case**: GRN-002
**Module**: GRN
**Type**: Feature

### Changes
- Renamed "Qty *" to "Received Qty" in all GRN views (form + detail modal)
- PO-linked GRN: Shows "(Ord: X | Prev: Y)" alongside editable input
- Standalone GRN: Shows simple editable "Received Qty" input
- GRN Detail modal: Consistent "Received Qty" column header
- Removed MFG/EXP date columns from detail modal for cleaner layout
- Updated all colspan values for table consistency

### Files Modified
- `frontend/src/pages/GRNPage.tsx` - Unified column across all GRN views

---

## FE-4: GRN Module - Auto-fill Payment Terms from Supplier Master
**Date**: April 3, 2026
**Status**: ✅ Completed
**Test Case**: GRN-004
**Module**: GRN
**Type**: Feature

### Changes
- Added `payment_terms_days` field to SupplierOption interface
- Added `paymentTermsDays` state to GRN form
- Auto-fills Payment Terms when supplier is selected from dropdown
- Auto-fills Payment Terms when PO is linked (inherits from PO's supplier)
- Added read-only "Payment Terms (Days)" field in GRN form showing "X days"
- Resets to default 30 days when form is reset
- Field styled with `bg-neutral-50` to indicate read-only status

### Files Modified
- `frontend/src/pages/GRNPage.tsx` - Added Payment Terms auto-fill logic

---

## FE-5: Suppliers Module - Add Payment Terms Field to Form
**Date**: April 3, 2026
**Status**: ✅ Completed
**Test Case**: GRN-004
**Module**: Suppliers
**Type**: Feature

### Changes
- Added `payment_terms_days` to Zod validation schema (min: 0, default: 30)
- Added field to form defaultValues and resetForm
- Added setValue in startEdit for editing existing suppliers
- Added "Payment Terms (Days)" input field to Suppliers form
- Updated payload to use form value instead of editingItem fallback
- Field type: number input with min="0" validation

### Files Modified
- `frontend/src/pages/SuppliersPage.tsx` - Added Payment Terms field

---

## FE-6: GRN Module - Payment Due Date Auto-Calculation & Display
**Date**: April 3, 2026
**Status**: ✅ Completed
**Test Case**: GRN-005
**Module**: GRN
**Type**: Feature

### Changes
- Added `payment_due_date` field to GoodsReceiptNote TypeScript interface
- Added `paymentDueDate` state + `calculateDueDate` function
- Auto-calculates Due Date = Receipt Date + Payment Terms (days)
- Added read-only "Payment Due Date" field in GRN form
- Added "Due Date" column to GRN list table
- Added "Payment Due Date" to GRN detail modal (5-column grid)
- Updates automatically when Receipt Date or Payment Terms change
- Resets to empty when form is reset

### Files Modified
- `frontend/src/api/purchase.ts` - Added field to interface
- `frontend/src/pages/GRNPage.tsx` - Added calculation + UI display

---

## FE-7: GRN Module - Block Future Dates for Receipt Date
**Date**: April 3, 2026
**Status**: ✅ Completed
**Test Case**: GRN-006
**Module**: GRN
**Type**: Validation

### Changes
- Added frontend validation in handleSubmit to check receipt date
- Compares selected date against today's date (time-normalized)
- Shows error: "Receipt date cannot be a future date. Please select today or a past date."
- Blocks form submission if future date is selected

### Files Modified
- `frontend/src/pages/GRNPage.tsx` - Added date validation

---

## FE-8: GRN Module - Block Today/Future Dates for Manufacturing Date
**Date**: April 3, 2026
**Status**: ✅ Completed
**Test Case**: GRN-007
**Module**: GRN
**Type**: Validation

### Changes
- Added validation in handleSubmit to check manufacture_date for all line items
- Blocks if manufacture_date >= today (prevents today or future dates)
- Shows error: "Line item X: manufacturing date must be a past date only (not today or future)"
- Validates before checking expired items

### Files Modified
- `frontend/src/pages/GRNPage.tsx` - Added manufacture date validation

---

## FE-9: GRN Module - Block Today/Past Dates for Expiry Date
**Date**: April 3, 2026
**Status**: ✅ Completed
**Test Case**: GRN-008
**Module**: GRN
**Type**: Validation

### Changes
- Added validation in handleSubmit to check expiry_date for all line items
- Blocks if expiry_date <= today (prevents today or past dates)
- Shows error: "Line item X: expiry date must be a future date only (not today or past)"
- Validates after manufacture date check, before expired warning

### Files Modified
- `frontend/src/pages/GRNPage.tsx` - Added expiry date validation

---

## FE-10: GRN Module - Add Free Quantity Column
**Date**: April 3, 2026
**Status**: ✅ Completed
**Test Case**: GRN-009
**Module**: GRN
**Type**: Feature

### Changes
- Added "Free" column header next to Received Qty
- Added editable "Free" quantity input field for each line item
- Added `free_quantity` to GRNLineItem interface (default: 0)
- Added field to addItem, loadPOData, and handleSubmit payload
- Updated colspan values for empty state and footer rows

### Files Modified
- `frontend/src/api/purchase.ts` - Added field to interfaces
- `frontend/src/pages/GRNPage.tsx` - Added column and input field
