# Frontend Updates Log

## FE-29: Ubuntu Deployment Frontend Load Fix (Production API Base)
**Date**: April 5, 2026
**Status**: ✅ Completed
**Test Case**: Frontend Not Loading After Server Upload
**Module**: API Client / Vite Config
**Type**: Bug Fix

### Overview
Fixed production frontend load/runtime failures caused by default API base URL pointing to `:8001` in deployed environments.

### Root Cause
- Frontend default API base used `http(s)://<host>:8001`.
- In Ubuntu/Nginx deployments, backend is typically exposed via same-origin `/api` and port `8001` is not public.
- API calls failed at startup, causing app flow to break.

### Changes Made
- Updated API client default base URL:
  - Localhost/127.0.0.1: keep `:8001`
  - Non-localhost: use `/api`
- Updated static URL helper to follow the same production-safe base logic.
- Updated Vite dev proxy target to use `VITE_DEV_PROXY_TARGET` instead of `VITE_API_BASE_URL`.

### Files Modified
- `frontend/src/api/client.ts`
- `frontend/src/utils/url_utils.ts`
- `frontend/vite.config.ts`

---

## FE-28: Sidebar Logo Outer Shape Updated to Circle
**Date**: April 5, 2026
**Status**: ✅ Completed
**Test Case**: Sidebar Top-Left Logo Shape
**Module**: App Layout / Branding
**Type**: UI Enhancement

### Overview
Changed sidebar top-left logo outer shape from box style to circular style.

### Changes Made
- Updated logo container class from rounded box to full circle.
- Updated logo image class to render inside circular mask.
- Preserved existing logo source and fallback icon behavior.

### Files Modified
- `frontend/src/components/AppLayout.tsx`

---

## FE-27: Sidebar Logo Endpoint Auth Fix - No Frontend Changes Required
**Date**: April 5, 2026
**Status**: ✅ Verified - No Changes Needed
**Test Case**: Sidebar Top-Left Logo Visibility After Refresh
**Module**: App Layout / Company Branding
**Type**: Bug Fix - Backend Endpoint Behavior

### Overview
Validated frontend behavior for final sidebar logo fix.

### Findings
- Frontend already points sidebar logo to branding-provided URL.
- Final issue was backend auth behavior for image endpoint.
- No additional frontend code changes required for this step.

### Conclusion
No frontend changes required.

---

## FE-26: Sidebar Branding Fetch Update for Deployed Logo Visibility
**Date**: April 5, 2026
**Status**: ✅ Completed
**Test Case**: Sidebar Top-Left Logo Visibility
**Module**: App Layout / Company API
**Type**: Bug Fix

### Overview
Updated sidebar branding data source so logo/name are fetched through branding endpoint suitable for all authenticated users in deployed environments.

### Changes Made
- Added `companyApi.getBranding()` client method.
- Updated `AppLayout` company query to use branding endpoint.
- Removed `company_read` gate from sidebar branding query so branding can render for all logged-in users.
- Switched sidebar branding query key to `company-branding` to avoid cache collision with full company profile query.
- Synced `company-branding` cache updates after company profile save and logo upload.

### Files Modified
- `frontend/src/api/company.ts`
- `frontend/src/components/AppLayout.tsx`

---

## FE-25: Logo URL Resolution Fix for Deployed App
**Date**: April 5, 2026
**Status**: ✅ Completed
**Test Case**: Company Logo Visibility in App
**Module**: Company / App Layout
**Type**: Bug Fix

### Overview
Fixed static logo URL construction in frontend so logo displays correctly when API base URL includes path prefixes or uses relative URLs.

### Changes Made
- Updated static URL helper to derive backend origin safely from `VITE_API_BASE_URL`.
- Added support for absolute and relative API base URL configurations.
- Prevented invalid static URLs like `/api/v1/static/...` when API is configured with path prefixes.

### Files Modified
- `frontend/src/utils/url_utils.ts`

---

## FE-24: Migration Parity Audit - No Frontend Changes Required
**Date**: April 5, 2026
**Status**: ✅ Verified - No Changes Needed
**Test Case**: Migration Consistency Audit
**Module**: Database Migration Tooling
**Type**: Verification - Backend/DB Only

### Overview
Validated impact scope for migration parity task.

### Findings
- Task affects database SQL update files and backend migration runner only.
- No frontend code or API contract updates required.

### Conclusion
No frontend changes required.

---

## FE-23: Product Master Data Seeding (10 Medicines) - No Frontend Changes Required
**Date**: April 5, 2026
**Status**: ✅ Verified - No Changes Needed
**Test Case**: Product Master Data Additions
**Module**: Products
**Type**: Data Update - Backend/DB Only

### Overview
Validated frontend product listing/forms for newly seeded medicine records.

### Findings
- Frontend reads product master from existing APIs.
- No UI/API contract changes were needed for adding records.

### Conclusion
No frontend code changes required for this task.

---

## FE-22: Quotation PDF Column Removal - No Frontend Changes Required
**Date**: April 5, 2026
**Status**: ✅ Verified - No Changes Needed
**Test Case**: Quotation PDF Table Simplification
**Module**: Quotations PDF
**Type**: Feature - Backend PDF Rendering

### Overview
Validated frontend quotation PDF download flow for removal of Batch/MFG/EXP columns.

### Findings
- Frontend already downloads backend-rendered quotation PDFs.
- Column removal is handled in backend template/rendering only.
- No frontend API or UI changes required.

### Conclusion
No frontend code changes required for this update.

---

## FE-21: Invoice Due Date Display-Only with Backend-Driven Value
**Date**: April 5, 2026
**Status**: ✅ Completed
**Test Case**: Invoice Due Date Auto-Calculate (No Manual Input)
**Module**: Sales Invoices
**Type**: Enhancement

### Overview
Updated invoice form behavior to keep due date visible but non-editable, and aligned payload to avoid sending user-driven due date values.

### Changes Made
- Kept due date field read-only/disabled in invoice form.
- Added guard to avoid transient due-date clearing before customer master data is loaded.
- Removed `due_date` from invoice create/update payload from frontend.

### Files Modified
- `frontend/src/pages/InvoicesPage.tsx`

---

## FE-20: Invoice Due Date Auto-Calculation in Invoice Form
**Date**: April 5, 2026
**Status**: ✅ Completed
**Test Case**: Invoice Due Date Auto-Calculate
**Module**: Sales Invoices
**Type**: Feature

### Overview
Updated invoice form behavior so invoice due date is auto-calculated from customer payment terms and cannot be manually edited.

### Changes Made
- Added due date calculation helper based on selected customer and invoice date.
- Recalculated due date automatically when customer changes.
- Recalculated due date automatically when invoice date changes.
- Made due date input read-only/disabled to enforce auto-calculated behavior.

### Files Modified
- `frontend/src/pages/InvoicesPage.tsx`

---

## FE-19: Invoice/Quotation Date Label Update - No Frontend Changes Required
**Date**: April 5, 2026
**Status**: ✅ Verified - No Changes Needed
**Test Case**: PDF Header Label Update
**Module**: Tax Invoices, Quotations
**Type**: Feature - Backend PDF Rendering

### Overview
Validated frontend PDF download flow for invoice/quotation date label update.

### Findings
- Frontend download flow remains unchanged.
- Date label rendering is controlled by backend PDF template context.
- No frontend code changes required.

### Conclusion
No frontend code changes required for this update.

---

## FE-18: Invoice/Quotation PDF Layout Update - No Frontend Changes Required
**Date**: April 5, 2026
**Status**: ✅ Verified - No Changes Needed
**Test Case**: Layout Change - Tax Invoice & Quotation PDF
**Module**: Tax Invoices, Quotations
**Type**: Feature - Backend PDF Rendering

### Overview
Validated frontend invoice/quotation PDF download flow for header/table layout update.

### Findings
- Frontend already downloads backend-generated PDFs for invoice and quotation.
- Requested header/table changes are render-template updates on backend only.
- No frontend API or UI changes required.

### Conclusion
No frontend code changes required for this update.

---

## FE-17: Billing PDF Packing/Order Unit Fix - No Frontend Changes Required
**Date**: April 5, 2026
**Status**: ✅ Verified - No Changes Needed
**Test Case**: Billing PDF Packing/Order Unit Display
**Module**: POs, Tax Invoices, Quotations
**Type**: Bug Fix - Backend PDF Rendering

### Overview
Validated frontend billing PDF flow for packing/order unit display correction.

### Findings
- Frontend download flow is unchanged and already correct.
- Incorrect value formatting came from backend PDF render logic.
- No frontend code changes required.

### Conclusion
No frontend code changes required for this fix.

---

## FE-16: Billing PDF Pagination (15 Items) - No Frontend Changes Required
**Date**: April 5, 2026
**Status**: ✅ Verified - No Changes Needed
**Test Case**: Bill-03
**Module**: POs, Tax Invoices, Quotations
**Type**: Feature - Backend PDF Rendering

### Overview
Validated frontend billing PDF download flow for PO, Tax Invoice, and Quotation modules.

### Findings
- Frontend already triggers backend PDF endpoints for PO, Invoice, and Quotation downloads.
- Pagination behavior is generated server-side during PDF rendering.
- No frontend API/UI/state changes required.

### Conclusion
No frontend code changes required for Bill-03.

---

## FE-15: Products Base Unit Duplicate Error - No Frontend Changes Required
**Date**: April 5, 2026
**Status**: ✅ Verified - No Changes Needed
**Test Case**: Product Update (Modify/Change Product)
**Module**: Products
**Type**: Bug Fix - Backend/DB Only

### Overview
Validated product modify form behavior for Base Unit update failure.

### Findings
- Frontend correctly sends the product update payload.
- Error was raised by backend/DB SKU uniqueness enforcement, not frontend validation.
- No frontend form, API client, or state changes were required.

### Conclusion
No frontend code changes required for this fix.

---

## FE-14: Purchase Order PDF Labels - No Frontend Changes Required
**Date**: April 5, 2026
**Status**: ✅ Verified - No Changes Needed
**Test Case**: Bill-02
**Module**: POs, Tax Invoices, Quotations
**Type**: Feature - Backend PDF Rendering

### Overview
Validated frontend flow for Purchase Order PDF generation and download.

### Findings
- Frontend already calls backend PO PDF endpoint (`GET /api/v1/purchase-orders/{id}/pdf`).
- Requested label and data changes are rendered by backend PDF template/service.
- No frontend API contract, UI form, or download logic changes were needed.

### Conclusion
No frontend code changes required for Bill-02.

---

## FE-13: Billing PDFs - No Frontend Changes Required
**Date**: April 5, 2026
**Status**: ✅ Verified - No Changes Needed
**Test Case**: Bill-001
**Module**: POs, Tax Invoices, Quotations
**Type**: Feature - Backend Only

### Overview
Billing PDF pagination is handled entirely by the backend PDF generation service.

### Findings
- Frontend already has PDF download buttons in place (POs, Invoices, Quotations pages)
- Frontend calls backend PDF endpoints which generate the paginated PDFs
- No frontend changes needed - pagination is handled during PDF generation

### Conclusion
No frontend changes required. PDF pagination is a backend-only implementation.

---

## FE-12: Product Module - Add Pagination and Search to Products Table
**Date**: April 5, 2026
**Status**: ✅ Completed
**Test Case**: Prod-01
**Module**: Product
**Type**: Feature/Improvement

### Issue
Product table was only showing the first 20 recently added products instead of all products from the database. No search or pagination functionality existed.

### Changes Made

#### 1. Products API Client (`frontend/src/api/products.ts`)
- **Reusing existing `listAll` method** (added in FE-11) to fetch all products without pagination
- All products are now fetched from backend sorted alphabetically by name

#### 2. Products Page (`frontend/src/pages/ProductsPage.tsx`)
- **Added search state**: `searchQuery` state to track user search input
- **Added pagination state**: `currentPage` state (default: 1), `itemsPerPage` constant (10)
- **Implemented search filtering**: Filters products by name, product_code, SKU, and description
- **Implemented client-side pagination**: 
  - Shows 10 products per page
  - Calculates total pages based on filtered results
  - Slices products array based on current page
- **Added search input UI**: 
  - Search bar with icon in products table header
  - Placeholder: "Search by name, code, SKU..."
  - Real-time filtering as user types
- **Added pagination controls**:
  - "Previous" and "Next" buttons (disabled when at first/last page)
  - "Page X of Y" indicator
  - Shows "Showing X to Y of Z products" with filter info when searching
- **Auto-reset behaviors**:
  - Resets to page 1 when search query changes
  - Resets to page 1 and clears search when products are updated (after create/edit)

### Technical Details
- Backend returns all products sorted by name (A-Z)
- Frontend applies additional client-side filtering based on search query
- Pagination works seamlessly with search (search results are also paginated if > 10)
- Search is case-insensitive and searches across multiple fields
- No database changes required

### Files Modified
- `frontend/src/pages/ProductsPage.tsx` - Added search, pagination logic, and UI controls

### Testing Checklist
- [x] All products from database appear in table (not just recent 20)
- [x] Products sorted alphabetically (A-Z) by name
- [x] Search bar filters products by name, code, SKU, description
- [x] Table shows 10 products per page
- [x] Previous/Next buttons work correctly
- [x] Page indicator shows current page and total pages
- [x] Search results are paginated if more than 10 matches
- [x] Page resets to 1 when search changes
- [x] Page resets to 1 after product create/edit
- [x] Build passes without TypeScript errors

---

## FE-11: Purchase Order Module - Show All Products in Product Dropdown
**Date**: April 5, 2026
**Status**: ✅ Completed
**Test Case**: PO-01
**Module**: Purchase Order
**Type**: Bug Fix

### Issue
Product dropdown in Purchase Order creation page was only showing recently added products instead of complete inventory.

### Changes Made

#### 1. Products API Client (`frontend/src/api/products.ts`)
- **Added `listAll` method** to fetch all products without pagination
- Calls `/api/v1/products?all_products=true` to get complete product list
- Returns all products sorted alphabetically by name from backend

#### 2. Purchase Order Page (`frontend/src/pages/PurchaseOrderPage.tsx`)
- **Changed product query** from `productsApi.list` to `productsApi.listAll`
- Products are now fetched in complete list (not paginated)
- Added client-side alphabetical sorting in dropdown: `.sort((a, b) => a.name.localeCompare(b.name))`
- Dropdown now displays all products with name, price, and GST rate

### Technical Details
- Backend returns all products when `all_products=true` parameter is set
- Frontend applies additional sorting using `localeCompare` for proper A-Z ordering
- Maintains backward compatibility: other pages still use paginated `list` method
- No database changes required (existing products table structure is correct)

### Files Modified
- `frontend/src/api/products.ts` - Added `listAll` method
- `frontend/src/pages/PurchaseOrderPage.tsx` - Updated to use `listAll` and sort products

### Testing Checklist
- [x] All products from inventory appear in dropdown
- [x] Products sorted alphabetically (A-Z) by name
- [x] No duplicate products in dropdown
- [x] Product selection auto-fills unit price and GST rate
- [x] Recent products no longer limited to first 20
- [x] Build passes without TypeScript errors

---

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
