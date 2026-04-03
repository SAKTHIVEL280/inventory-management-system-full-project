# Backend Updates Log

---

## BE-1: GRN Module - Payment Due Date Calculation
**Date**: April 3, 2026
**Status**: ✅ Completed
**Test Case**: GRN-005
**Module**: GRN
**Type**: Feature

### Changes
- Added `payment_due_date` field to GoodsReceiptNote model
- Added calculation logic in create_grn: receipt_date + supplier.payment_terms_days
- Added recalculation logic in update_grn when GRN is edited
- Stored in database as DATE column (nullable)

### Files Modified
- `backend/app/models/purchase.py` - Added column to model
- `backend/app/routers/purchase.py` - Added calculation logic

---

## BE-2: GRN Module - Block Future Dates for Receipt Date
**Date**: April 3, 2026
**Status**: ✅ Completed
**Test Case**: GRN-006
**Module**: GRN
**Type**: Validation

### Changes
- Added backend validation in create_grn endpoint
- Added backend validation in update_grn endpoint
- Validates: `payload.receipt_date > date.today()` raises HTTPException 400
- Error message: "Receipt date cannot be a future date. Please select today or a past date."
- Prevents API-level bypass of frontend validation

### Files Modified
- `backend/app/routers/purchase.py` - Added date validation in create/update endpoints

---

## BE-3: GRN Module - Block Today/Future Dates for Manufacturing Date
**Date**: April 3, 2026
**Status**: ✅ Completed
**Test Case**: GRN-007
**Module**: GRN
**Type**: Validation

### Changes
- Added validation in create_grn endpoint for each line item's manufacture_date
- Added validation in update_grn endpoint for each line item's manufacture_date
- Validates: `item.manufacture_date >= date.today()` raises HTTPException 400
- Error message: "Line item X: manufacturing date must be a past date only (not today or future)"
- Prevents API-level bypass of frontend validation

### Files Modified
- `backend/app/routers/purchase.py` - Added manufacture date validation in create/update endpoints

---

## BE-4: GRN Module - Block Today/Past Dates for Expiry Date
**Date**: April 3, 2026
**Status**: ✅ Completed
**Test Case**: GRN-008
**Module**: GRN
**Type**: Validation

### Changes
- Added validation in create_grn endpoint for each line item's expiry_date
- Added validation in update_grn endpoint for each line item's expiry_date
- Validates: `item.expiry_date <= date.today()` raises HTTPException 400
- Error message: "Line item X: expiry date must be a future date only (not today or past)"
- Prevents API-level bypass of frontend validation

### Files Modified
- `backend/app/routers/purchase.py` - Added expiry date validation in create/update endpoints

---

## BE-5: GRN Module - Add Free Quantity Column
**Date**: April 3, 2026
**Status**: ✅ Completed
**Test Case**: GRN-009
**Module**: GRN
**Type**: Feature

### Changes
- Added `free_quantity` field to GRNItem model (NUMERIC, default: 0)
- Added `free_quantity` to PurchaseLineItemRequest schema (float, default: 0)
- Added field to GRNItem creation in create_grn endpoint
- Added field to GRNItem creation in update_grn endpoint

### Files Modified
- `backend/app/models/purchase.py` - Added column to model
- `backend/app/schemas/purchase.py` - Added field to schema
- `backend/app/routers/purchase.py` - Added field to item creation

---

## BE-6: GRN Module - Add Free Quantity to Stock on GRN Confirmation
**Date**: April 3, 2026
**Status**: ✅ Completed
**Test Case**: GRN-009
**Module**: GRN
**Type**: Bug Fix

### Changes
- Updated `confirm_grn` endpoint to also add `free_quantity` to stock ledger
- Free quantity is added as a separate stock entry with `rate=0` (free)
- Reference number for free items: `{GRN_NUMBER}-FREE`
- Both paid and free quantities now contribute to total inventory count

### Files Modified
- `backend/app/routers/purchase.py` - Added free quantity stock entry logic
