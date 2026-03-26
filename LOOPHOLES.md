# IMS Project — Loopholes, Bugs, and Missing Features

**Document Status:** Production Readiness Audit
**Date:** March 26, 2026
**Objective:** Identify all gaps between current implementation and MASTER_SPEC/workflow requirements, with severity ranking and fixes.

---

## Table of Contents

1. [Critical Issues (Blocking)](#critical-blocking)
2. [High Priority (Breaking Features)](#high-breaking)
3. [Medium Priority (Data Integrity)](#medium-integrity)
4. [Low Priority (Polish)](#low-polish)
5. [Backend Gaps](#backend-gaps)
6. [Frontend Gaps](#frontend-gaps)
7. [Database Schema Gaps](#database-gaps)
8. [Fix Execution Plan](#fix-plan)

---

## Critical Issues (Blocking) {#critical-blocking}

### 1. Customer Create Returns 422 (Always Fails)

**Current Issue:**
- Frontend sends empty strings for optional fields (`gstin`, `email`, `pan`, etc.)
- Backend GSTIN validator rejects `""` as invalid format
- Results in 422 Unprocessable Entity on every customer create
- User sees generic error; cannot add customers

**Files Affected:**
- `frontend/src/pages/CustomersPage.tsx` (line 47-73)
- Backend validators work correctly; frontend payload malformed

**Root Cause:**
- Form payload uses `id: ''` (should be omitted for create)
- Empty strings sent for ALL optional fields
- Backend expects `null` or valid values, not blank strings

**Fix Required:**
```typescript
// BEFORE: Sends empty strings and id
createMutation.mutate({
  ...parsed.data,
  customer_code: '',
  email: '',
  gstin: '',
  // ... etc
  id: '', // ← Problem: id should not exist on create
});

// AFTER: Omit id, normalize optionals to null
const normalizeOptional = (val?: string) => val?.trim() || null;
createMutation.mutate({
  // ... no id field
  company_name: parsed.data.company_name.trim(),
  phone: parsed.data.phone.trim(),
  gstin: normalizeOptional(parsed.data.gstin)?.toUpperCase() ?? null,
  email: null,
  // ... all optionals as null
});
```

**Severity:** 🔴 CRITICAL — Blocks master data entry

---

### 2. Purchase Workflow (WF-03) — Zero Implementation

**Current State:**
- Backend router exists: `backend/app/routers/purchase.py`
- **Zero endpoints implemented** (only helper functions)
- No PO creation, no GRN receipt, no purchase returns
- No stock ledger entries created
- No materialized view refresh

**Missing Endpoints:**
```
POST   /api/v1/purchase-orders              → Create PO
GET    /api/v1/purchase-orders              → List POs
GET    /api/v1/purchase-orders/{po_id}      → Get PO detail
PUT    /api/v1/purchase-orders/{po_id}      → Update PO (only if draft)
POST   /api/v1/purchase-orders/{po_id}/send → Change status to sent
DELETE /api/v1/purchase-orders/{po_id}      → Cancel PO

POST   /api/v1/grn                          → Create GRN
GET    /api/v1/grn                          → List GRNs
GET    /api/v1/grn/{grn_id}                 → Get GRN detail
POST   /api/v1/grn/{grn_id}/confirm         → Confirm (adds stock)
DELETE /api/v1/grn/{grn_id}                 → Cancel GRN

POST   /api/v1/purchase-returns             → Create return
GET    /api/v1/purchase-returns             → List returns
POST   /api/v1/purchase-returns/{id}/confirm → Confirm return (deducts stock)
```

**Missing Frontend:**
- Zero API client functions
- Zero pages
- Zero forms

**Business Impact:**
- Cannot track incoming goods
- Cannot manage supplier orders
- Cannot record purchase expenses
- Stock remains at 0 (no inbound receipt)

**Severity:** 🔴 CRITICAL — Entire purchase module blocked

---

### 3. Sales Workflow (WF-04) — Zero Implementation

**Current State:**
- Backend router exists: `backend/app/routers/sales.py`
- **Zero endpoints implemented** (only helper functions)
- No quotations, no sales orders, no invoices
- No stock deduction on invoice
- No PDF generation

**Missing Endpoints:**
```
POST   /api/v1/quotations                   → Create quotation
GET    /api/v1/quotations                   → List
GET    /api/v1/quotations/{qtn_id}          → Detail
PUT    /api/v1/quotations/{qtn_id}          → Update (draft only)
POST   /api/v1/quotations/{qtn_id}/send     → Change to sent
POST   /api/v1/quotations/{qtn_id}/convert  → Convert to SO

POST   /api/v1/sales-orders                 → Create SO
GET    /api/v1/sales-orders                 → List
GET    /api/v1/sales-orders/{so_id}         → Detail
PUT    /api/v1/sales-orders/{so_id}         → Update (draft only)
POST   /api/v1/sales-orders/{so_id}/confirm → Confirm (stock check)
POST   /api/v1/sales-orders/{so_id}/convert → Convert to invoice

POST   /api/v1/sales-invoices                → Create invoice
GET    /api/v1/sales-invoices                → List
GET    /api/v1/sales-invoices/{inv_id}      → Detail
PUT    /api/v1/sales-invoices/{inv_id}      → Update (draft only)
POST   /api/v1/sales-invoices/{inv_id}/issue → Issue (deducts stock, generates PDF)
GET    /api/v1/sales-invoices/{inv_id}/pdf  → Download PDF
POST   /api/v1/sales-invoices/{inv_id}/send-email → Email invoice

POST   /api/v1/sales-returns                → Create return
GET    /api/v1/sales-returns                → List
POST   /api/v1/sales-returns/{id}/confirm   → Confirm (adds stock back)
```

**Missing Frontend:**
- Zero API client functions
- Zero pages
- Zero forms

**Business Impact:**
- Cannot create customer quotes
- Cannot create sales orders
- Cannot issue invoices (most critical for accounting)
- Cannot generate tax documents
- Revenue tracking impossible

**Severity:** 🔴 CRITICAL — Entire sales module blocked

---

### 4. Payments Workflow (WF-05) — Severely Incomplete

**Current State:**
- Backend router `backend/app/routers/payments.py` exists
- Only `GET /api/v1/payments` partially implemented
- Missing: POST (create), PUT (update status), DELETE (cancel), GET detail

**Missing Endpoints:**
```
POST   /api/v1/payments                     → Create payment (receipt or outward)
GET    /api/v1/payments/{payment_id}        → Get payment detail
PUT    /api/v1/payments/{payment_id}        → Update payment status
DELETE /api/v1/payments/{payment_id}        → Cancel payment (reverse allocations)

GET    /api/v1/payments/receipts            → List customer receipts
GET    /api/v1/payments/payables            → List supplier payments
```

**Missing Frontend:**
- Zero API client functions
- Zero pages
- Zero payment recording UI

**Business Impact:**
- Cannot record customer payments
- Cannot record supplier payments
- Cannot reconcile outstanding balances
- Accounts receivable/payable tracking broken

**Severity:** 🔴 CRITICAL — Finance module blocked

---

## High Priority Issues (Breaking Features) {#high-breaking}

### 5. Missing CRUD Operations in Frontend APIs

**Customers API** (`frontend/src/api/customers.ts`):
- ✅ `list()` - implemented
- ✅ `create()` - implemented
- ❌ `get(id)` - **MISSING** → Cannot fetch for edit/view
- ❌ `update(id, payload)` - **MISSING** → Cannot edit customers
- ❌ `delete(id)` - **MISSING** → Cannot delete customers
- ❌ `getBalance(id)` - **MISSING** → Cannot show customer ledger
- ❌ `getLedger(id)` - **MISSING** → Cannot show customer ledger

**Suppliers API** (`frontend/src/api/suppliers.ts`):
- ✅ `list()` - implemented
- ✅ `create()` - implemented
- ❌ `get(id)` - **MISSING**
- ❌ `update(id, payload)` - **MISSING**
- ❌ `delete(id)` - **MISSING**
- ❌ `getBalance(id)` - **MISSING**
- ❌ `getLedger(id)` - **MISSING**

**Products API** (`frontend/src/api/products.ts`):
- ✅ `list()` - implemented
- ✅ `create()` - implemented
- ✅ `listCategories()` - implemented
- ✅ `createCategory()` - implemented
- ✅ `listUom()` - implemented
- ❌ `get(id)` - **MISSING**
- ❌ `update(id, payload)` - **MISSING**
- ❌ `delete(id)` - **MISSING**
- ❌ `updateCategory(id, payload)` - **MISSING**
- ❌ `deleteCategory(id)` - **MISSING**

**Impact:**
- Cannot edit any master records
- Cannot view full details
- Cannot delete records
- Forms cannot pre-fill data on edit

**Severity:** 🟡 HIGH

---

### 6. Missing Edit/Delete UI in Master Pages

**CustomersPage** (`frontend/src/pages/CustomersPage.tsx`):
- ✅ List customers
- ✅ Create form
- ❌ Edit buttons on rows
- ❌ Delete buttons on rows
- ❌ Detail view page
- ❌ Edit form page
- ❌ Confirmation dialog for delete

**SuppliersPage** (`frontend/src/pages/SuppliersPage.tsx`):
- Same gaps as CustomersPage

**ProductsPage** (`frontend/src/pages/ProductsPage.tsx`):
- Same gaps as CustomersPage
- Additional: No delete confirmation for products with stock

**Impact:**
- Users can only create records
- Cannot manage existing data
- No way to correct errors
- No way to deactivate old records

**Severity:** 🟡 HIGH

---

### 7. Backend Models Missing Soft Delete Fields (Potential Data Corruption)

**Files to Check:**
- `backend/app/models/customer.py`
- `backend/app/models/supplier.py`
- `backend/app/models/product.py`
- `backend/app/models/purchase.py`
- `backend/app/models/sales.py`
- `backend/app/models/payment.py`

**Issue:**
- Backend routers filter `Model.is_deleted == False`
- Database queries call `model.is_deleted = True` and `model.deleted_at = datetime.utcnow()`
- But if these fields don't exist in models, database column doesn't exist
- Result: Deletes fail or bypass soft-delete entirely

**All Models Should Have:**
```python
from datetime import datetime
from sqlalchemy import Boolean, DateTime, func

class BaseModel:
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
```

**Severity:** 🟡 HIGH (Data integrity risk)

---

### 8. Missing Authentication Endpoints

**Current:**
- ✅ POST /api/v1/auth/login
- ✅ POST /api/v1/auth/refresh

**Missing:**
- ❌ GET /api/v1/auth/me → Fetch current user (for profile, refresh UI after logout)
- ❌ POST /api/v1/auth/logout → Clear refresh tokens on server
- ❌ POST /api/v1/auth/change-password → Required by WF-01

**Severity:** 🟡 HIGH (Incomplete auth flow)

---

## Medium Priority Issues (Data Integrity) {#medium-integrity}

### 9. Stock Ledger Logic Missing

**Required Behavior (WF-03 GRN Confirm):**
```python
# When GRN is confirmed:
for item in grn.items:
    ledger = StockLedger(
        product_id=item.product_id,
        transaction_type='purchase',
        quantity=item.quantity,  # positive (inbound)
        rate=item.unit_price,
        transaction_date=grn.receipt_date
    )
    db.add(ledger)

# Refresh materialized view
db.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY current_stock"))
```

**Required Behavior (WF-04 Invoice Issue):**
```python
# When invoice is issued:
for item in invoice.items:
    ledger = StockLedger(
        product_id=item.product_id,
        transaction_type='sale',
        quantity=-item.quantity,  # negative (outbound)
        rate=item.unit_price,
        transaction_date=invoice.invoice_date
    )
    db.add(ledger)

# Refresh materialized view
db.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY current_stock"))
```

**Current State:** NOT IMPLEMENTED

**Impact:**
- Stock counts stuck at 0
- No way to track inventory movements
- Stock reports show wrong data
- Cannot fulfill orders (stock check fails)

**Severity:** 🟠 MEDIUM

---

### 10. IGST vs CGST/SGST Logic Missing

**Required (WF-02, WF-03, WF-04):**
```
IF company.state_code == customer/supplier.state_code:
    Tax Type = CGST + SGST (intra-state)
    CGST = SGST = (taxable_amount * gst_rate / 2) / 100
    IGST = 0
ELSE:
    Tax Type = IGST (inter-state)
    IGST = taxable_amount * gst_rate / 100
    CGST = SGST = 0
```

**Current State:**
- Helpers exist in `sales.py` and `purchase.py` but never called
- No logic in invoice/PO/GRN create/update endpoints

**Impact:**
- Tax calculations always wrong
- GST compliance broken
- Invoices show 0 taxes

**Severity:** 🟠 MEDIUM

---

### 11. PDF Invoice Generation Missing

**Required (WF-04):**
- POST /api/v1/sales-invoices/{id}/issue should generate PDF
- GET /api/v1/sales-invoices/{id}/pdf returns PDF file
- Email invoice integration (POST /api/v1/sales-invoices/{id}/send-email)

**Current State:** Zero implementation

**Technology Stack:**
- Backend: WeasyPrint for PDF generation
- Already in requirements.txt

**Impact:**
- Cannot create invoice documents
- Cannot download/print invoices
- Customers have no official receipt

**Severity:** 🟠 MEDIUM

---

### 12. Payment Allocation Logic Missing

**Required (WF-05):**
- When payment is created, user allocates money to specific invoices/GRNs
- Each allocation updates invoice.amount_paid and invoice.amount_due
- Invoice status changes based on due amount
- If payment is cancelled/bounced, reverse ALL allocations

**Current State:**
- Helper functions exist (`_apply_invoice_allocation`, `_reverse_invoice_allocation`)
- Create/update/delete endpoints missing
- No paymentAllocation table queries

**Impact:**
- Cannot record payments
- Invoice balances stuck at full amount
- Cannot reconcile accounts

**Severity:** 🟠 MEDIUM

---

### 13. Company Logo Upload Missing

**Required (WF-02):**
- POST /api/v1/company/logo with file upload
- Validates: PNG/JPG only, max 2MB
- Saves file, returns logo_url

**Current State:** Endpoint exists but incomplete

**Impact:** Minor (UI branding only)

**Severity:** 🟠 MEDIUM

---

## Low Priority Issues (Polish) {#low-polish}

### 14. Missing Report Pages (Frontend)

**Implemented:**
- ✅ Dashboard (WF-06)

**Missing:**
- ❌ Stock Report Page
- ❌ Sales Report Page
- ❌ Purchase Report Page
- ❌ Outstanding Receivables Page
- ❌ Outstanding Payables Page
- ❌ GSTR-1 Report Page
- ❌ GSTR-3B Report Page
- ❌ P&L Report Page

**Note:** Backend endpoints exist; frontend pages missing

**Severity:** 🔵 LOW (reports out of scope for core business flow)

---

### 15. Pagination UI Missing

**Issue:**
- Backend returns paginated data (page_size=20, has_more flag)
- Frontend doesn't render pagination controls
- Users cannot see beyond first 20 items

**Severity:** 🔵 LOW (workaround: increase page_size)

---

### 16. Search/Filter UI Not Exposed

**Issue:**
- Backend supports search and filters
- Frontend forms don't include search boxes or filter dropdowns

**Severity:** 🔵 LOW (Nice to have)

---

### 17. Form Error Detail Not Displayed

**Issue:**
- When 422 error occurs, backend returns field-specific errors
- Frontend shows generic "Failed to create customer"
- User has no idea which field is invalid

**Example Fix:**
```typescript
if (error.response?.status === 422) {
  const detail = error.response.data.detail;
  if (Array.isArray(detail)) {
    const fieldError = detail[0];
    setFormError(`${fieldError.loc[1]}: ${fieldError.msg}`);
  }
}
```

**Severity:** 🔵 LOW (UX improvement)

---

## Backend Gaps {#backend-gaps}

| Module | Status | Has Models | Has Schemas | Has Router | Has Endpoints |
|--------|--------|------------|-------------|------------|---------------|
| Auth | ⚠️ Incomplete | ✅ | ✅ | ✅ | ⚠️ Missing: logout, me, change-password |
| Company | ✅ Complete | ✅ | ✅ | ✅ | ⚠️ Missing: POST logo |
| Users | ✅ Complete | ✅ | ✅ | ✅ | ✅ |
| Customers | ✅ Complete | ✅ | ✅ | ✅ | ✅ |
| Suppliers | ✅ Complete | ✅ | ✅ | ✅ | ✅ |
| Products | ✅ Complete | ✅ | ✅ | ✅ | ✅ |
| Purchase | 🔴 MISSING | ⚠️ Exists | ⚠️ Exists | ✅ | 🔴 **ZERO ENDPOINTS** |
| Sales | 🔴 MISSING | ⚠️ Exists | ⚠️ Exists | ✅ | 🔴 **ZERO ENDPOINTS** |
| Payments | 🟡 Incomplete | ✅ | ✅ | ✅ | ⚠️ Only GET, missing POST/PUT/DELETE |
| Reports | ✅ Complete | ✅ | ✅ | ✅ | ⚠️ Missing: GSTR-3B, P&L |

---

## Frontend Gaps {#frontend-gaps}

| Module | Status | API Client | List Page | Create Form | Edit Form | Detail Page | Delete Action |
|--------|--------|-----------|-----------|-------------|------------|-------------|---------------|
| Auth | ✅ Complete | ✅ | - | ✅ | - | - | - |
| Company | ✅ Complete | ✅ | - | ✅ | ✅ | - | - |
| Users | ✅ Complete | ✅ | ✅ | ✅ | ✅ | - | ✅ |
| Customers | 🟡 Partial | ⚠️ Missing CRUD | ✅ | ✅ | 🔴 **NONE** | 🔴 **NONE** | 🔴 **NONE** |
| Suppliers | 🟡 Partial | ⚠️ Missing CRUD | ✅ | ✅ | 🔴 **NONE** | 🔴 **NONE** | 🔴 **NONE** |
| Products | 🟡 Partial | ⚠️ Missing CRUD | ✅ | ✅ | 🔴 **NONE** | 🔴 **NONE** | 🔴 **NONE** |
| Purchase | 🔴 MISSING | 🔴 **NONE** | 🔴 | 🔴 | 🔴 | 🔴 | 🔴 |
| Sales | 🔴 MISSING | 🔴 **NONE** | 🔴 | 🔴 | 🔴 | 🔴 | 🔴 |
| Payments | 🔴 MISSING | 🔴 **NONE** | 🔴 | 🔴 | 🔴 | 🔴 | 🔴 |
| Reports | 🟡 Partial | ✅ | 🟡 Dashboard Only | - | - | - | - |

---

## Database Schema Gaps {#database-gaps}

**Potential Issues:**

1. **Soft Delete Fields Missing from Some Models**
   - Check: Customer, Supplier, Product, Purchase, Sales, Payment models
   - Required: `is_deleted: Boolean`, `deleted_at: DateTime`

2. **Stock Ledger Table**
   - Likely incomplete or missing materialized view refresh logic

3. **Payment Allocation Relationships**
   - Need foreign keys: Payment ↔ PaymentAllocation ↔ SalesInvoice/GoodsReceiptNote

4. **Unique Constraints**
   - Customer email should have unique constraint
   - Supplier email should have unique constraint
   - Product SKU should have unique constraint

---

## Fix Execution Plan {#fix-plan}

### Phase 1: Critical Fixes (Today — ~2 hours)
- [ ] Fix Customer 422 payload (normalize optionals → null)
- [ ] Add soft delete fields to all models (if missing)
- [ ] Verify unique constraints on key fields

### Phase 2: High Priority CRUD (Tomorrow — ~4 hours)
- [ ] Add missing API methods for Customers/Suppliers/Products
- [ ] Create detail/edit pages for Masters
- [ ] Add edit/delete UI actions

### Phase 3: Core Business Workflows (Next 2 days — ~16 hours)
- [ ] Implement Purchase WF endpoints (backend) + Frontend
- [ ] Implement Sales WF endpoints (backend) + Frontend
- [ ] Implement Payments WF endpoints (backend) + Frontend

### Phase 4: Critical Business Logic (Next 3 days — ~12 hours)
- [ ] Stock ledger creation on GRN/Invoice
- [ ] IGST vs CGST/SGST calculation
- [ ] Payment allocation and reversal
- [ ] PDF invoice generation
- [ ] Invoice email sending

### Phase 5: Polish (Following week — ~8 hours)
- [ ] Report pages for remaining modules
- [ ] Pagination UI
- [ ] Search/filter UI
- [ ] Error detail rendering in forms
- [ ] Performance optimization

---

## Script for Testing Each Fix

After each phase, run these commands:

```bash
# Backend validation
cd backend
pytest  # Run all tests

# Frontend validation
cd ../frontend
npm run build  # Check for TS errors
npm run dev    # Start dev server

# Manual testing checklist
# 1. Create customer → should succeed (no 422)
# 2. Edit customer → should load existing data
# 3. Create PO → should generate PO number
# 4. Confirm GRN → should create stock ledger entries
# 5. Issue Invoice → should deduct stock
# 6. Record Payment → should update invoice balance
```

---

## Production Readiness Checklist

- [ ] All CRUD operations working (C, R, U, D)
- [ ] All workflows implemented (Purchase, Sales, Payments)
- [ ] No 422 errors on valid input
- [ ] Stock tracking accurate
- [ ] Tax calculations correct
- [ ] Soft deletes working
- [ ] Permissions enforced
- [ ] Error messages detailed and helpful
- [ ] Forms validated before submit
- [ ] Async operations show loading/success/error states
- [ ] Mobile responsive
- [ ] Pagination works
- [ ] Search/filter works
- [ ] PDF generation works
- [ ] Email sending works
- [ ] Database backups configured
- [ ] Logging configured
- [ ] Performance monitoring configured

---

**Last Updated:** March 26, 2026
**Document Owner:** AI Development Agent
**Next Review:** After Phase 1 completion
