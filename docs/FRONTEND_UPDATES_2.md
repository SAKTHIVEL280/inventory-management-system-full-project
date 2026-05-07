# Frontend Updates Log

## FE-127: General manager GST access messaging
**Update**: Updated Reports page GST access guard to allow General Manager and refreshed restriction messaging.

## FE-128: Admin-only approve/issue/clear UI + manual batch input
**Update**: Hid approval/issue/clear actions behind admin role on Quotations, Invoices, Receivables, Payables, PO, and GRN pages. Added a manual Batch Number input alongside batch dropdowns in Inventory Count.

## FE-129: Receivables status uses backend display
**Update**: Receivables status column now prefers backend `status_display` for accurate partial/full receipt labels.

## FE-130: View modals for payments
**Update**: Added View actions and read-only modals for customer receipts and supplier payments to inspect details and allocations.

## FE-131: Payment view readability
**Update**: Normalized mode/status labels, cleaned PO meta from notes, and clarified allocation labels in the payment view modals.

## FE-132: Notes cleanup in payment views
**Update**: Stripped PO metadata tokens from notes in receivables/payables view modals for readability.

## FE-133: Invoice batch quantity validation
**Update**: Added real-time batch-quantity checks in invoice line items and blocked submit when requested quantity exceeds available batch stock.

## FE-134: Invoice validation visibility + width fixes
**Update**: Moved batch-quantity validation to a top-of-form alert, widened Batch/MFG/EXP fields on invoices, and increased GRN product column width for readability.

## FE-135: Invoice page runtime fix
**Update**: Added missing `useMemo` import to prevent the Sales Invoice page from crashing on load.

## FE-136: Invoice + GRN line-item alignment
**Update**: Standardized line-item field heights and adjusted column widths in Sales Invoice and GRN forms for consistent alignment and visibility after adding items.

## FE-137: GRN/Sales Invoice overlap + placeholder cleanup
**Update**: Resolved GRN product/received-qty overlap, widened invoice batch/MFG/EXP columns, and replaced default numeric values with placeholders for clean input.

## FE-126: Role-based navigation and gating updates
**Update**: Updated role definitions to `admin`, `inventory manager`, and `general manager`. Restricted master pages to write access, added action-log permission gating, refreshed inventory count difference controls, and aligned UI badges/colors with the new roles.

## FE-125: Company save refreshes session user
**Update**: Refreshed the authenticated user context after Company Profile save by calling `getMe()` and updating the auth store. Added `company_id` to the frontend user type so client state reflects tenant assignment immediately.

## FE-124: Action Logs Clear button removed
**Update**: Removed Clear button from Action Logs filter controls and adjusted grid layout from 6 to 5 columns for cleaner UI.

## FE-123: Action Logs real-time auto-refresh with quotations filter
**Update**: Implemented 10-second auto-refresh polling in ActionLogsPage.tsx for real-time updates without manual page refresh. Added quotations to module filter dropdown. Action Logs now automatically show new financial actions as they occur.

## FE-122: Action Logs - Reference field handling with empty string trim and fallback
**Update**: Enhanced ActionLogsPage.tsx Reference column display to properly handle empty strings by trimming whitespace before applying fallbacks: `(item.reference && item.reference.trim()) || (item.record_reference && item.record_reference.trim()) || '-'`. Now correctly displays invoice numbers, PO numbers, GRN numbers, and payment references from backend, with "-" shown when no reference is available.

## FE-121: Reports JSX parse fix + frontend dependency vulnerability remediation
**Update**: Fixed malformed JSX in GSTR-1 warning list rendering that caused Vite parser crash in Reports page, corrected required AppLayout title usage in Action Logs page, and upgraded vulnerable frontend dependencies (axios, postcss, vite, plugin-react). Frontend build passes and npm audit now reports zero vulnerabilities.

## FE-120: Calendar-aligned report date filters (Monthly/Quarterly/Annually)
**Update**: Refined Reports page filter logic to generate exact calendar windows from selected frequency and anchor date: Monthly (full month), Quarterly (full quarter), and Annually (full year). Date changes now auto-align to boundary ranges and are validated against frequency-period rules before API calls for consistent results.

## FE-119: Action Logs date-range loading fix (remove frequency mismatch)
**Update**: Removed frequency selection from Action Logs page (API is date-range based), aligned module filter options to backend-supported modules only, and added helper copy to avoid misleading Quarterly/Monthly behavior that caused empty/no-load confusion for short ranges.

## FE-118: GST tables GSTIN wrap
**Update**: Allowed GSTIN values to wrap in GSTR-1, GSTR-2, and GST Reconciliation tables to prevent truncation in the UI.

## FE-117: GST report drill-down for product details
**Update**: Kept GST report tables at one row per invoice/GRN while adding a `View Details` toggle to reveal product-level items (Item Name & Description, HSN, Quantity, and tax breakdown) for GSTR-1 and GSTR-2. Updated report typings to accept detail items from the backend.

## FE-116: Customer/Supplier Master autofill suppression (Billing + State/State Code)
**Update**: Stopped unintended autofill in Customer and Supplier Master new-entry forms. Customer Master no longer preloads Billing Address fields from Company Profile on “+ New Customer”, and both Customer/Supplier Masters now avoid re-populating State/State Code after the user clears inputs (state-code sync is guarded once the code field is manually edited). Supplier Master form also disables browser autofill for address/state fields.

## FE-115: Quotation MRP rupee display + Supplier state-code autofill
**Update**: Fixed Quotation item MRP input to display rupees with decimals while storing paise internally (prevents 100× display like 35000 instead of 350), and aligned Supplier Master state/state-code autofill to always keep `state_code` in sync with selected `state` (matching Customer Master behavior).

## FE-114: Action Logs viewer with filters and pagination
**Update**: Added GST-tab Action Logs card with module/action/user/reference filters, paginated table view, and typed API integration.

## FE-113: Reports fast-fail on backend down
**Update**: Health check added; loading exits fast.

## FE-112: Remove GSTR subtotal UI column
**Update**: Removed separate Sub Total col in GSTR1/2 tables.

## FE-111: GST Warnings Copy Aligned to Non-Exclusion Behavior
**Update**: Updated GST warning banners in Reports so messaging clearly states that all source records are included in totals/reconciliation and warnings are informational for data review.

## FE-110: Nullable Tax Percent Display for Mixed-Slab GST Reports
**Update**: Updated the Reports UI and typed GST report contracts to treat `Tax %` as optional for mixed-slab documents, rendering a blank/dash instead of forcing `0.00` so one-row GSTR-2, GSTR-1, and reconciliation tables stay visually accurate.

## FE-109: GST Audit Trail IP Column Removal
**Update**: Removed the IP Address column from the GST Audit Trail UI and aligned the frontend audit trail type with the backend response so the report shows only the fields required by the BRD.

## FE-108: Reports Loading Resilience - Timeout Guard + Lazy GST Fetching
**Update**: Fixed prolonged `Loading reports...` state by adding per-request timeout wrappers in Reports page data fetch flow and deferring GST-heavy API calls to load only when GST tab is active, so Dashboard/Sales/Stock sections render even if a GST endpoint is slow or stuck.

## FE-107: Reports Analytics Enhancement - Audit Pagination Size + Stock Batch Columns + GST Export Actions
**Update**: Added GST Audit Trail page-size selector (`10/20/50`) with filter-aware pagination refresh, upgraded Stock Report table to show batch-wise rows (`Batch No`, `MFG Date`, `EXP Date`), and added GSTR-1/GSTR-2 export actions (XLSX/PDF) with standardized report download flows.

## FE-106: GST Audit Trail UX Upgrade (Report Filter + Pagination + Empty State)
**Update**: Refactored GST Audit Trail contracts and Reports UI to remove unavailable-table fallback, add report-type filtering (`all/gstr1/gstr2/gstr3b/reconciliation`), show richer event metadata (type/range/frequency), and support page-based navigation for high-volume audit logs.

## FE-105: GST Date Validation UX Stabilization (No False Future + No Blink)
**Update**: Refactored GST report date handling to use local date-only parsing (YYYY-MM-DD), debounced validation/fetch timing, and unified date-range state updates to remove false future-date errors and reduce frequency-switch flicker/blinking while preserving manual override behavior.

## FE-104: Quarterly Auto-Range Switched to Rolling 3 Months
**Update**: Updated GST frequency auto-range behavior for Quarterly to use a rolling 3-month window ending today (e.g., Apr 15 -> Jan 15 to Apr 15), while preserving manual override and no-future date validation.

## FE-103: Quarterly Date Range Correction (Current Period, No Future)
**Update**: Corrected GST frequency auto-date behavior to avoid future windows (Monthly/Quarterly/Annually now end at current date), and added no-future client validation for manual date overrides with clear user-facing messages.

## FE-102: GST Frequency-Date Auto Window + Validation Messaging + Record Highlighting
**Update**: Added frequency-aware auto date windows (Monthly=current month, Quarterly=current quarter, Annually=current year), client-side frequency range validation with clear messages before API calls, and detailed problematic-record highlighting in GSTR-1/GSTR-2/Reconciliation warning panels.

## FE-101: GST Audit Trail UI Integration (Module 6)
**Update**: Added GST Audit Trail section in Reports GST tab with typed API integration, recent event listing (timestamp/action/status/user/ip), and graceful unavailable messaging when backend audit-log storage is not available.

## FE-100: GST Role-Gated Fetch and Access Messaging
**Update**: Added frontend role gating for GST report loading so non-Finance users do not trigger unauthorized GST API calls; GST tab now shows a clear restricted-access message for non Admin/Accounting roles while preserving existing report behavior for Finance/Tax users.

## FE-99: GST Reconciliation Export Controls (XLSX/PDF)
**Update**: Added GST Reconciliation export actions in Reports GST tab with `Export XLSX` and `Export PDF` buttons, wired to blob-download API integration for date-range + frequency aware file generation.

## FE-98: GST Reconciliation UI + API Integration (Module 3)
**Update**: Integrated GST Reconciliation report in Reports GST tab with typed API/contracts, consolidated transaction table (Input + Output rows), and dedicated subtotal/difference cards for `Input Tax`, `Output Tax`, and `Difference (Output - Input)` while preserving non-blocking validation warning display.

## FE-97: GST Report Validation Warning Banner (Non-Blocking Load)
**Update**: Enhanced GST report rendering to show validation warning counts for GSTR-1 and GSTR-2 when backend returns non-blocking validation issues, so tables continue to load while users are prompted to correct master/transaction data.

## FE-96: GSTR-2 Detailed Purchase/Input Tax UI Integration (Module 2)
**Update**: Extended Reports GST tab with a BRD-style GSTR-2 detailed table (all required columns + subtotal row), added typed GSTR-2 API contracts/fetcher, and integrated date-range + frequency driven GSTR-2 loading alongside existing GSTR-1 and GSTR-3B sections.

## FE-95: GSTR-1 Detailed Report UI with Frequency Filter (Module 1)
**Update**: Enhanced Reports GST tab to render BRD-style GSTR-1 detailed table (all required columns + subtotal row), added report frequency filter (Monthly/Quarterly/Annually), and integrated typed GSTR-1 API contract for date-range + frequency driven report generation.

## FE-94: Password Visibility Toggle in User Management and Login
**Update**: Added eye-icon show/hide password toggles for Create User and Edit User password field in User Management, and for Login + first-login Change Password fields to improve input usability while keeping default masked behavior.

## FE-93: Invoice Payment Status Labels + Dashboard Paid/Issued Wording Consistency
**Update**: Updated Sales Invoice status display to derive payment labels from actual paid-vs-total amounts (`Unpaid`, `Partially Received`, `Fully Received`) and standardized Dashboard wording/formatting to use title-case labels with consistent badge styling, including `Partially Paid` and properly rendered `Issued` status.

## FE-92: Count Difference Accept/Recount Actions with Reason Enforcement
**Update**: Enhanced Inventory Count Difference UI with mandatory reason-code dropdown for Accept Difference, admin-only accept control, permission-based Recount action, and live refresh after action completion.

## FE-91: Frontend Architecture Baseline Mapping and Validation
**Update**: Completed frontend-wide source validation of app bootstrap, protected routing, auth store, API client patterns, and page-level data-fetching paths to establish an implementation-accurate baseline for upcoming tasks; no frontend runtime behavior changes were introduced.

## FE-90: Company Ambassador Logo Upload/Preview/Remove (PDF Watermark Feature)
**Update**: Added Company Ambassador Logo controls in Company Profile with preview, replace, and remove support, wired to new ambassador-logo API endpoints.

## FE-89: GST-UT-002 Master State-Code Validation + Company Save Redirect
**Update**: Added state/state-code mismatch validation and state-code autofill across Customer, Supplier, and Company forms, and redirected to dashboard after successful Company Profile save.

## FE-88: SI-003 Invoice Type Auto-Select and Lock by Shipping Location
**Update**: Fixed UT invoice-type constraint by prioritizing shipping-location UT detection (country -> state code -> state name), including canonical state/state-code mapping, then auto-selecting and locking the single valid invoice type.

## FE-87: Invoice GST Country Gate Uses Shipping Address First
**Date**: April 10, 2026
**Status**: Completed
**Module**: Sales Invoice
**Type**: Bug Fix / Tax Logic Alignment

### Overview
Aligned invoice country-based GST type enforcement to use Shipping Country first (with Billing Country fallback), matching backend GST rules.

### Changes Made
- Updated invoice country gate effect to evaluate `shipping_country` before `billing_country`.
- Ensured export/non-export invoice-type auto-correction follows shipping-address country context.

### Files Modified
- `frontend/src/pages/InvoicesPage.tsx`

### Validation
- Verified no TypeScript/IDE errors in modified file.

## FE-86: Company Profile Country Field Added
**Date**: April 10, 2026
**Status**: Completed
**Module**: Company Profile
**Type**: Enhancement

### Overview
Added missing Country input in Company Profile and wired it into form load/save payloads.

### Changes Made
- Added `country` to Company Profile form schema and default mapping.
- Added `Country` input in Address section.
- Added `country` normalization in save payload.
- Added `country` to frontend `Company` type.

### Files Modified
- `frontend/src/pages/CompanyPage.tsx`
- `frontend/src/types/index.ts`

### Validation
- Verified no TypeScript/IDE errors in modified files.

## FE-85: Company Profile Placeholder Name Autofill Suppression
**Date**: April 10, 2026
**Status**: Completed
**Module**: Company Profile
**Type**: UX Bug Fix

### Overview
Prevented seeded/default placeholder names from appearing as real company data in Company Profile when the user has not entered company details yet.

### Changes Made
- Added company-name sanitization in Company Profile form mapping.
- Treated seeded placeholders as empty values for form binding:
  - `Your Company Name`
  - `My Company`
- Kept save validation unchanged (`Company name is required`) so users still provide an explicit real name.

### Files Modified
- `frontend/src/pages/CompanyPage.tsx`

### Validation
- Verified no TypeScript/IDE errors in modified file.
- Verified frontend build succeeds (`npm run build`).

## FE-84: GST Shipping-First Invoice Type Default + UT State Dropdown Coverage (GST-001)
**Date**: April 10, 2026
**Status**: Completed
**Module**: Sales Invoice, Customer Master, Supplier Master
**Type**: Bug Fix / Data Option Alignment

### Overview
Aligned frontend invoice GST defaulting with shipping-first customer location and added Union Territory coverage in state dropdown code maps.

### Changes Made
- Updated invoice default-tax/invoice-type derivation to use shipping-first fields with billing fallback:
  - `shipping_country` -> `billing_country`
  - `shipping_state_code` -> `billing_state_code`
  - `shipping_state` -> `billing_state`
- Kept state-code-first comparison with state-name fallback for invoice-type defaulting.
- Added missing customer field typings for shipping state/country in invoice page customer option model.
- Added Union Territory names to invoice UT name detection set.
- Expanded customer and supplier frontend state-code maps to include Union Territories for dropdown/typeahead behavior.

### Files Modified
- `frontend/src/pages/InvoicesPage.tsx`
- `frontend/src/pages/CustomersPage.tsx`
- `frontend/src/pages/SuppliersPage.tsx`

### Validation
- Verified no TypeScript/IDE errors in modified files.
- Verified frontend build succeeds (`npm run build`).

## FE-83: Payables Exact Remaining Amount Acceptance + Full History Settlement (PAY-002)
**Date**: April 10, 2026
**Status**: Completed
**Module**: Payables
**Type**: Bug Fix / Validation Consistency

### Overview
Fixed supplier payment validation mismatch where amount equal to remaining payable could be blocked due to partial frontend settlement context and paise normalization drift.

### Changes Made
- Added complete supplier payment history loading for settlement computation (paginated fetch with `has_more`).
- Updated payables remaining-by-GRN computation to use full supplier payment history instead of only list-page data.
- Aligned GRN sort order with backend settlement logic (`receipt_date`, then `created_at`).
- Added amount normalization helper for paise-safe comparisons and submission payload.
- Added guard to block submit while settlement data is refreshing for selected supplier.
- Updated payments API list response typing to include pagination metadata.

### Files Modified
- `frontend/src/pages/PayablesPage.tsx`
- `frontend/src/api/payments.ts`

### Validation
- Verified no TypeScript/IDE errors in modified files.

## FE-82: Inventory Count Batch Auto-Handling + Date Picker Restrictions (INV-COUNT-004, INV-COUNT-005)
**Date**: April 10, 2026
**Status**: Completed
**Module**: Inventory Count
**Type**: Enhancement / Validation UX Fix

### Overview
Implemented dynamic batch behavior for single vs multiple batch products and enforced MFG/EXP constraints through both picker restrictions and save-time guards.

### Changes Made
- Added Inventory Count batch options API integration on product selection.
- Implemented batch behavior:
  - single batch auto-filled and read-only,
  - multiple batches displayed in dropdown,
  - batch change auto-updates MFG/EXP.
- Added stale-data reset on product change for batch/MFG/EXP fields.
- Added real-time and save-time Inventory Count date validation logic:
  - Manufacturing date earlier than current date,
  - Expiry date later than current date,
  - Expiry date later than manufacturing date.
- Added UTC-based date helper usage for consistent validation baseline.
- Updated date input controls:
  - MFG restricted to past dates via max date,
  - EXP restricted to future dates via min date.
- Removed inline error-message rendering below MFG/EXP inputs per UI request.
- Improved API error-detail parsing in Inventory Count submit flow.

### Files Modified
- `frontend/src/pages/InventoryCountPage.tsx`
- `frontend/src/api/stock.ts`
- `frontend/src/utils/date.ts`

### Validation
- Verified no TypeScript/IDE errors in modified files.

## FE-81: Payables PO/GRN Auto-Fill + Advance-Adjusted Remaining Flow (PAY-001, PAY-002)
**Date**: April 8, 2026
**Status**: ✅ Completed
**Module**: Payables
**Type**: Enhancement / UX Logic Update

### Overview
Implemented PO-linked payables flow with GRN auto-selection/auto-fill and advance-adjusted remaining payable display/validation.

### Changes Made
- Added supplier-specific PO loading with PO search in Payables form.
- Added mandatory PO selection for supplier payment creation.
- Added PO-scoped GRN selection for non-advance payments.
- Added GRN settlement panel fields:
  - GRN Amount
  - Remaining Amount (After Advance)
- Added auto-fill behavior for non-advance flow:
  - auto-select first open GRN for selected PO,
  - auto-fill payment amount using computed remaining.
- Updated payment payload to send `purchase_order_id` and single selected GRN allocation for non-advance record.
- Updated payment list rendering:
  - top-level PO display,
  - status chip labels for `Advance Payment Cleared` and `Full Payment Cleared`.
- Updated status filter behavior to include all cleared-like variants under `Cleared` aggregate.

### Files Modified
- `frontend/src/api/payments.ts`
- `frontend/src/api/purchase.ts`
- `frontend/src/pages/PayablesPage.tsx`

### Validation
- Verified no TypeScript/IDE errors in modified files.
- Verified frontend build succeeds (`npm run build`).

## FE-80: Compact GRN Status Badge Styling
**Date**: April 8, 2026
**Status**: ✅ Completed
**Module**: GRN
**Type**: UI Polish

### Overview
Reduced visual size of GRN status chips to avoid bulky status rendering in list/detail views.

### Changes Made
- Reduced status chip padding and font size for a compact appearance.
- Added compact display text for partial statuses:
  - `Partial (Draft)`
  - `Partial (Confirmed)`
- Preserved full status meaning via tooltip (`title`) with full label text.

### Files Modified
- `frontend/src/pages/GRNPage.tsx`

### Validation
- Verified no TypeScript/IDE errors in modified file.

## FE-79: GRN Status Naming for Partial Receipt Draft/Confirmed
**Date**: April 8, 2026
**Status**: ✅ Completed
**Module**: GRN
**Type**: UX Enhancement

### Overview
Updated GRN status display to clearly distinguish partial-quantity documents in draft and confirmed stages.

### Changes Made
- Added status display rendering in GRN list and GRN detail modal using backend metadata.
- Applied improved status names:
  - `Partial Receipt (Draft)`
  - `Partial Receipt (Confirmed)`
- Kept standard statuses for non-partial rows:
  - `Draft`, `Confirmed`, `Cancelled`.
- Added badge color variations to visually distinguish partial draft vs partial confirmed.

### Files Modified
- `frontend/src/api/purchase.ts`
- `frontend/src/pages/GRNPage.tsx`

### Validation
- Verified no TypeScript/IDE errors in modified files.
- Verified frontend build succeeds (`npm run build`).

## FE-78: GRN Partial Receipt Tolerance Validation Uses Cumulative Qty
**Date**: April 8, 2026
**Status**: ✅ Completed
**Module**: GRN
**Type**: Logic / UX Fix

### Overview
Adjusted GRN linked-PO tolerance checks to evaluate cumulative received quantity, so creating remaining quantity after a partial GRN no longer triggers incorrect tolerance errors.

### Changes Made
- Updated GRN save-side tolerance logic to validate with:
  - `previously received qty + current entered qty`
  instead of current row qty alone.
- Updated tolerance popup data to show cumulative received value explicitly.

### Files Modified
- `frontend/src/pages/GRNPage.tsx`

### Validation
- Verified no TypeScript/IDE errors in modified file.
- Verified frontend build succeeds (`npm run build`).

## FE-77: GRN Expiry Date Current-Date Enablement (Past-Date Restriction)
**Date**: April 8, 2026
**Status**: ✅ Completed
**Module**: GRN
**Type**: Validation / UX Fix

### Overview
Fixed GRN expiry-date behavior so users can select from current date onward, while past dates are blocked.

### Changes Made
- Updated GRN frontend validation to block only expiry dates earlier than today.
- Updated expiry-date validation message to: `expiry date must be today or a future date`.
- Updated GRN expiry-date input `min` to today (and still respects manufacture-date consistency).

### Files Modified
- `frontend/src/pages/GRNPage.tsx`

### Validation
- Verified no TypeScript/IDE errors in modified file.
- Verified frontend build succeeds (`npm run build`).

## FE-76: GRN MFG Date Restriction + Product Code Label Standardization + PO Partial/Completed UI (GRN-002, GRN-003, GRN-004)
**Date**: April 8, 2026
**Status**: ✅ Completed
**Module**: GRN, Purchase Order, Sales Invoice, Quotation, Inventory Count
**Test Cases**: GRN-002, GRN-003, GRN-004
**Type**: Enhancement / UX Consistency Fix

### Overview
Applied requested GRN-related UX and status improvements: prevented future MFG selection in GRN with exact message, standardized user-facing naming to `Product Code`, and aligned PO fulfillment status presentation to `Partial`/`Completed` with line-level visibility.

### Changes Made
- GRN MFG Date (frontend):
  - MFG input now uses `max=today` to prevent future date picking.
  - save validation blocks only future MFG values and shows exact message:
    - `MFG Date cannot be a future date`.
- Product naming consistency (`Product ID` -> `Product Code`) in UI:
  - Quotation items grid header
  - Sales Invoice items grid header
  - Inventory Count entry label, table header, and validation toast message
  - Inventory Count Difference table header
  - where appropriate, displayed value now shows product code first instead of raw product UUID.
- Purchase Order status UI:
  - replaced `received` presentation with `completed` in status filter and badges.
  - added robust status normalization so legacy `received` records still render as `Completed`.
  - added line-item fulfillment status in PO detail modal:
    - `Pending/Draft`, `Partial`, `Completed`.

### Files Modified
- `frontend/src/pages/GRNPage.tsx`
- `frontend/src/pages/PurchaseOrderPage.tsx`
- `frontend/src/pages/QuotationsPage.tsx`
- `frontend/src/pages/InvoicesPage.tsx`
- `frontend/src/pages/InventoryCountPage.tsx`
- `frontend/src/pages/InventoryCountDifferencePage.tsx`

### Validation
- Verified no TypeScript/IDE errors in modified files.
- Verified frontend build succeeds (`npm run build`).

## FE-75: Product Basic Unit Typeahead + Order Unit Label + Stock Low-Alert Blink (PRO-001, PRO-002, STO-001)
**Date**: April 8, 2026
**Status**: ✅ Completed
**Module**: Product Master, Stock / Inventory
**Test Cases**: PRO-001, PRO-002, STO-001
**Type**: Enhancement / UI Update

### Overview
Implemented product and stock UX enhancements: Base Unit is now a searchable dropdown-style typeahead, the optional marker for Order Unit/Packing is inline in the label, and low-stock rows now have a subtle blinking visual alert.

### Changes Made
- Replaced editable Product Base Unit text input with a searchable typeahead dropdown behavior.
- Populated Base Unit suggestions from:
  - predefined standard unit tokens (PCS, KG, LTR, BOX, etc.)
  - active UOM master names/abbreviations
  - existing product Base Unit values for continuity during edits.
- Kept Base Unit binding on the same `sku` field so stored values continue working in dependent modules (PO/Invoice/PDF contexts already reading this field).
- Updated Product label text to inline optional format:
  - `Order Unit / Packing (optional)`
- Added low-stock blinking animation utility classes and applied them to:
  - Current Qty cell (low stock rows)
  - Status badge (low stock rows)
- Added reduced-motion fallback to disable blink animation when OS preference requests reduced motion.

### Files Modified
- `frontend/src/pages/ProductsPage.tsx`
- `frontend/src/pages/StockPage.tsx`
- `frontend/src/index.css`

### Validation
- Verified no TypeScript/IDE errors in modified files.
- Verified frontend build succeeds (`npm run build`).

## FE-74: Duplicate Error Toast Prevention in Sales Invoice
**Date**: April 8, 2026
**Status**: ✅ Completed
**Module**: Sales Invoice / API Client
**Type**: UX Fix

### Overview
Resolved duplicate popup error messages caused by both global API interceptor toasts and page-level invoice toasts firing for the same failed request.

### Changes Made
- Added per-request global-toast suppression support in API client interceptor (`skipErrorToast`).
- Extended Sales API invoice methods to support `suppressGlobalErrorToast` options:
  - create invoice
  - update invoice
  - issue invoice
- Updated invoice page handlers to suppress global toasts for these actions and keep only page-level detailed popup messages.

### Files Modified
- `frontend/src/api/client.ts`
- `frontend/src/api/sales.ts`
- `frontend/src/pages/InvoicesPage.tsx`

### Validation
- Verified no TypeScript/IDE errors in modified files.
- Verified frontend build succeeds (`npm run build`).

## FE-73: Sales Invoice Popup Error Handling for Multi-Validation Responses (SAL-043, SAL-044)
**Date**: April 8, 2026
**Status**: ✅ Completed
**Module**: Sales Invoice
**Type**: UX / Error Handling Fix

### Overview
Updated Sales Invoice error handling to show all backend validation messages as popup toasts instead of a single generic error.

### Changes Made
- Added API detail parser to normalize error payloads from string/list/object formats.
- On save/create/update failures:
  - shows each validation message as separate toast popup.
  - keeps combined messages in inline error block for reference.
- Applied same multi-message popup behavior for issue-invoice errors.

### Files Modified
- `frontend/src/pages/InvoicesPage.tsx`

### Validation
- Verified no TypeScript/IDE errors in modified file.
- Verified frontend build succeeds (`npm run build`).

## FE-72: Restore Base Unit Alongside Packing Unit in Sales Invoice (SAL-034)
**Date**: April 8, 2026
**Status**: ✅ Completed
**Module**: Sales Invoice
**Type**: Bug Fix / UI Enhancement

### Overview
Restored the missing Base Unit column in Sales Invoice line items while keeping the Packing Unit column added earlier.

### Changes Made
- Re-added Base Unit column in invoice line item grid.
- Kept Packing Unit column intact and read-only auto-fill behavior.
- Mapped values separately to preserve integrity:
  - Base Unit from product base unit field (with UOM fallback)
  - Packing Unit from product order/packing unit mapping.
- Updated column count, total-row colspan, table min-width, and header widths so both columns render cleanly without overlap.

### Files Modified
- `frontend/src/pages/InvoicesPage.tsx`

### Validation
- Verified no TypeScript/IDE errors in modified file.
- Verified frontend build succeeds (`npm run build`).

## FE-71: Sales Invoice Batch Auto-Fill + Packing Unit Grid Update (SAL-032/033/034)
**Date**: April 8, 2026
**Status**: ✅ Completed
**Module**: Sales Invoice
**Type**: Enhancement

### Overview
Implemented dynamic product-linked batch selection in Sales Invoice, automatic MFG/EXP fill from selected batch, and Packing Unit auto-fill from product master.

### Changes Made
- Added Sales API client support for invoice batch options endpoint.
- Updated invoice item grid behavior:
  - fetch batch options when product is selected
  - auto-select batch when exactly one is available
  - show dropdown when multiple batches are available
  - show available quantity in dropdown labels
  - auto-fill `MFG Date` and `EXP Date` from selected batch
  - keep date fields read-only (auto-driven)
- Replaced editable `Order Unit` input with `Packing Unit` display auto-filled from product UOM data.
- Added row-level batch option state handling for add/remove/edit flows.

### Files Modified
- `frontend/src/api/sales.ts`
- `frontend/src/pages/InvoicesPage.tsx`

### Validation
- Verified no TypeScript/IDE errors in modified files.
- Verified frontend build succeeds (`npm run build`).

## FE-70: Customer Payment Terms No-Preload Submit Behavior Fix
**Date**: April 8, 2026
**Status**: ✅ Completed
**Module**: Customer Master
**Type**: Bug Fix

### Overview
Fixed Customer Master form behavior so Payment Terms is not auto-filled in new customer flow and only persisted value appears on modify/change.

### Changes Made
- Updated submit payload mapping to send `payment_terms_days = null` when user leaves field blank.
- Removed fallback behavior that forced a numeric value in submit payload.
- Aligned frontend customer types/API payloads to support nullable `payment_terms_days`.

### Files Modified
- `frontend/src/pages/CustomersPage.tsx`
- `frontend/src/api/customers.ts`
- `frontend/src/types/index.ts`

### Validation
- Verified no TypeScript/IDE errors in modified files.
- Verified frontend build succeeds (`npm run build`).

## FE-69: Customer Master Currency Payload Type Alignment
**Date**: April 8, 2026
**Status**: ✅ Completed
**Module**: Customer Master
**Type**: Bug Fix / Type Safety

### Overview
Aligned Customer API payload typing so currency data used in Customer Master form is explicitly typed and maintained through save flows.

### Changes Made
- Added `currency_code` in customer create payload type definition.
- Removed type mismatch risk between Customer form payload and API layer.

### Files Modified
- `frontend/src/api/customers.ts`

### Validation
- Verified no TypeScript/IDE errors in modified file.
- Verified frontend build succeeds (`npm run build`).

## FE-68: Inventory Count Module Button Visual Affordance Fix
**Date**: April 8, 2026
**Status**: ✅ Completed
**Module**: Stock Master
**Type**: UI Fix

### Overview
Improved button visibility in Inventory Count and Inventory Count Difference modules where actions looked like plain text.

### Changes Made
- Added reusable button component classes in global styles:
  - primary button
  - outline button
  - danger outline button
- Applied clear bordered/color button styling to:
  - Add Entry
  - Confirm
  - Show Difference
  - Remove
- Improved disabled-state appearance for Confirm button.

### Files Modified
- `frontend/src/index.css`
- `frontend/src/pages/InventoryCountPage.tsx`
- `frontend/src/pages/InventoryCountDifferencePage.tsx`

### Validation
- Verified no TypeScript/IDE errors in modified files.
- Verified frontend build succeeds (`npm run build`).

## FE-67: STO-006/007 Inventory Count and Admin Difference UI
**Date**: April 8, 2026
**Status**: ✅ Completed
**Module**: Stock Master
**Test Cases**: STO-006, STO-007
**Type**: Enhancement

### Overview
Added two new Stock Master modules in frontend:
- Inventory Count entry/confirm module
- Inventory Count Difference module (admin only)

### Changes Made
- Added Inventory Count page with:
  - auto-generated count number preview (`INV-MON-001`)
  - Count Date and Count Performed By fields
  - line entry fields: Serial Number, Product ID, Product Description, Quantity, Batch Number, Mfg Date, Exp Date
  - Add Entry flow and Confirm button enabled only after valid entry data exists
- Added Inventory Count Difference page (admin only) with:
  - Inventory Count Number input
  - result grid showing counted qty vs existing stock vs difference values per line
- Added route wiring:
  - `/inventory/count`
  - `/inventory/count-difference` (admin role protected)
- Added Inventory navigation links in sidebar/mobile nav.
- Extended stock API client with inventory count preview/create/difference methods.

### Files Modified
- `frontend/src/api/stock.ts`
- `frontend/src/pages/InventoryCountPage.tsx`
- `frontend/src/pages/InventoryCountDifferencePage.tsx`
- `frontend/src/App.tsx`
- `frontend/src/components/AppLayout.tsx`

### Validation
- Verified no TypeScript/IDE errors in modified files.
- Verified frontend build succeeds (`npm run build`).

## FE-66: STO-005 Stock Master Batch-Wise Row Display
**Date**: April 8, 2026
**Status**: ✅ Completed
**Module**: Stock Master, Reports API Integration
**Type**: Enhancement / UI Data Mapping Fix

### Overview
Updated Stock Master to render separate rows for each batch of the same product instead of showing merged product rows with combined batch labels.

### Changes Made
- Updated Stock page report contract consumption to batch-wise row model.
- Added typed stock report interfaces for frontend API client with batch metadata fields.
- Updated table columns to include:
  - `Batch No`
  - `MFG Date`
  - `EXP Date`
- Removed merged `Batch(es)` text column.
- Expanded search to include batch number.
- Updated row identity and UI copy to reflect row-based display (`stock rows` instead of `products`).
- Kept status and low-stock filters compatible with backend response.

### Files Modified
- `frontend/src/api/reports.ts`
- `frontend/src/pages/StockPage.tsx`

### Validation
- Verified no TypeScript/IDE errors in modified files.
- Verified frontend build succeeds (`npm run build`).

## FE-64: GRN Item Search Non-Destructive Locate Mode (Highlight + Scroll)
**Date**: April 8, 2026
**Status**: ✅ Completed
**Module**: GRN
**Type**: Bug Fix / UX Enhancement

### Overview
Changed GRN item search behavior from filtering to locate mode so existing line items are never removed/altered while searching.

### Changes Made
- Removed search-driven filtering from item dropdown option sets.
- Kept full line-item list visible at all times (non-destructive search).
- Implemented locate behavior:
  - matches by product name or product code
  - highlights first matched row
  - auto-scrolls smoothly to matched row
- Clears row highlight when search text is cleared.
- Preserved linked-PO restrictions and normal dropdown selection behavior.

### Files Modified
- `frontend/src/pages/GRNPage.tsx`

### Validation
- Verified no TypeScript/IDE errors in modified file.
- Verified frontend build succeeds.

## FE-63: GRN Linked PO Reselection Unlock + Reset Flow
**Date**: April 8, 2026
**Status**: ✅ Completed
**Module**: GRN
**Type**: Bug Fix

### Overview
Fixed GRN linked PO dropdown lock so users can change selected PO before save, with safe reset and reload behavior.

### Changes Made
- Removed hard lock/disabled state from Linked PO dropdown after initial selection.
- Added PO-change handler with confirmation prompt:
  - `Changing the PO will reset current items. Do you want to continue?`
- On confirmation and PO change:
  - clears current items
  - clears linked PO item options
  - clears tolerance popup/error state
  - clears item search state
  - clears unsaved supplier invoice + notes
  - reloads line items/tolerance data from newly selected PO
- On switching to standalone:
  - clears linked PO state and resets PO-dependent fields.

### Files Modified
- `frontend/src/pages/GRNPage.tsx`

### Validation
- Verified no TypeScript/IDE errors in modified file.
- Verified frontend build succeeds.

## FE-62: GRN Linked-PO Item Search Visibility and Dropdown Fix
**Date**: April 8, 2026
**Status**: ✅ Completed
**Module**: GRN
**Type**: Bug Fix

### Overview
Fixed GRN item search and selection behavior when GRN is linked to a Purchase Order.

### Changes Made
- Kept item search box visible in linked PO mode.
- Enabled product field as a clickable/searchable dropdown even for linked PO rows.
- Restricted linked-PO dropdown options to selected PO items only.
- Applied dynamic filtering by product name/code (and SKU token when present) within PO items.
- Ensured unlinking PO clears linked options and item-search state cleanly.
- Preserved PO-only item selection constraints (no outside product options).

### Files Modified
- `frontend/src/pages/GRNPage.tsx`

### Validation
- Verified no TypeScript/IDE errors in modified file.
- Verified frontend build succeeds.

## FE-60: GRN-012 Line Item S.No and Dynamic Item Search
**Date**: April 8, 2026
**Status**: ✅ Completed
**Module**: GRN
**Type**: Enhancement

### Overview
Added GRN line item serial numbering and a dynamic item search box for faster product selection.

### Changes Made
- Added `S.No` column in GRN line items table with auto-increment numbering starting at 1.
- Ensured numbering updates automatically on add/remove.
- Added item search box in GRN item section.
- Implemented dynamic dropdown filtering by:
  - product name
  - product code / SKU-style token (when present)
- Updated empty/table footer column spans to match new structure.

### Files Modified
- `frontend/src/pages/GRNPage.tsx`

### Validation
- Verified no TypeScript/IDE errors in modified file.
- Verified frontend build succeeds.

## FE-61: GRN-013 Delivery Tolerance Validation Enforcement UX
**Date**: April 8, 2026
**Status**: ✅ Completed
**Module**: GRN
**Type**: Bug Fix / Validation

### Overview
Confirmed and tightened GRN linked-PO quantity validation to enforce delivery tolerance range with blocking UX.

### Changes Made
- Validation formula enforced in GRN create flow for linked PO items:
  - `minimum_allowed = ordered_qty - under_tolerance`
  - `maximum_allowed = ordered_qty + over_tolerance`
- Prevented save when received quantity is outside allowed range.
- Preserved popup error behavior with detailed context:
  - under/over tolerance message
  - item and row reference
  - received quantity and allowed range
- Preserved invalid field highlight for faster correction.
- Edge handling retained:
  - tolerance `0` enforces exact match range
  - negative values prevented via numeric input constraints and validation rules

### Files Modified
- `frontend/src/pages/GRNPage.tsx`

### Validation
- Verified no TypeScript/IDE errors in modified file.
- Verified frontend build succeeds.

## FE-59: PUR-006 PO GST Field No Longer Prefills Before Product Selection
**Date**: April 8, 2026
**Status**: ✅ Completed
**Module**: Purchase Order
**Type**: Bug Fix

### Overview
Fixed PO line-item composer behavior where GST showed `18%` before selecting a product.

### Changes Made
- Removed default `gst_rate` prefill from new line-item state.
- Updated GST dropdown to start empty with `Select GST` placeholder.
- Kept GST auto-fill from Product Master when product is selected.
- Reset line-item composer to empty GST after item add/save.

### Files Modified
- `frontend/src/pages/PurchaseOrderPage.tsx`

### Validation
- Verified no TypeScript/IDE errors in modified file.

## FE-58: GRN Received Qty Column Structure Refinement
**Date**: April 8, 2026
**Status**: ✅ Completed
**Module**: GRN
**Type**: UI Refinement

### Overview
Adjusted the visual structure of the PO-linked `Received Qty` cell to improve readability and match intended flow.

### Changes Made
- Reordered content in `Received Qty` for linked PO rows to:
  - `(Ord | Prev)` context
  - quantity input field
  - `Allowed: Min - Max` range
- Preserved existing tolerance validation and row highlight behavior.

### Files Modified
- `frontend/src/pages/GRNPage.tsx`

### Validation
- Verified no TypeScript/IDE errors in modified file.

## FE-57: GRN Delivery Tolerance Popup with Item-Level Details
**Date**: April 8, 2026
**Status**: ✅ Completed
**Module**: GRN
**Type**: Validation UX Enhancement

### Overview
Added a blocking popup for delivery tolerance validation failures in GRN creation, including clear item-level context so users can correct errors immediately.

### Changes Made
- Added popup modal when tolerance validation fails with required messages:
  - `Under delivery exceeded allowed tolerance`
  - `Over delivery exceeded allowed tolerance`
- Included detailed error context in popup:
  - item name and row number
  - received quantity
  - allowed range (min-max)
- Kept submission blocked until the issue is resolved.
- Added optional row-level visual highlight for invalid `Received Qty` field.
- Added explicit `OK`/close action (popup does not auto-dismiss).

### Files Modified
- `frontend/src/pages/GRNPage.tsx`

### Validation
- Verified no TypeScript/IDE errors in modified file.

## FE-56: Supplier Country Default + Build Cleanup for PO GST Consistency
**Date**: April 8, 2026
**Status**: ✅ Completed
**Module**: Supplier Master
**Type**: Bug Fix / Data Consistency

### Overview
Improved supplier defaults to reduce accidental GST suppression in PO flow and resolved a TypeScript build blocker.

### Changes Made
- Defaulted new supplier country to `India` in Supplier form defaults.
- For existing domestic suppliers with blank country during edit flow, prefilled country as `India`.
- Ensured domestic supplier save payload writes `India` when country is left blank.
- Removed unused `phoneValue` variable causing TypeScript compile failure.

### Files Modified
- `frontend/src/pages/SuppliersPage.tsx`

### Validation
- Verified no TypeScript/IDE errors in modified file.
- Verified frontend build succeeds.

## FE-55: Quantity-Based Delivery Tolerance UX and GRN Validation
**Date**: April 8, 2026
**Status**: ✅ Completed
**Module**: Purchase Order, GRN
**Type**: Validation + UI Enhancement

### Overview
Aligned PO/GRN tolerance behavior and UI with quantity-based delivery rules and added client-side GRN validation for allowed received range.

### Changes Made
- Updated tolerance labels to quantity units:
  - `Under Delivery Tolerance (Qty)`
  - `Over Delivery Tolerance (Qty)`
- Added GRN create-form validation for linked PO line items using:
  - `minimum_allowed = ordered_qty - under_tolerance`
  - `maximum_allowed = ordered_qty + over_tolerance`
- Added required user-facing errors:
  - `Under delivery exceeded allowed tolerance`
  - `Over delivery exceeded allowed tolerance`
- Displayed allowed quantity range inline in GRN item rows for PO-linked GRNs.
- Kept null/blank tolerance behavior safe by defaulting to `0` in form handling.

### Files Modified
- `frontend/src/pages/GRNPage.tsx`
- `frontend/src/pages/PurchaseOrderPage.tsx`

### Validation
- Verified no TypeScript/IDE errors in modified frontend files.

## FE-54: Purchase Order Line-Item Composer Alignment Fix
**Date**: April 8, 2026
**Status**: ✅ Completed
**Module**: Purchase Order
**Type**: UI Bug Fix

### Overview
Fixed broken/cramped line-item input composer layout where labels and fields were overlapping due to constrained form column span.

### Changes Made
- Expanded line-items section to full-width within PO form grid.
- Replaced mixed responsive sub-grid with explicit six-column composer layout:
  - Product | Quantity | Unit Price | Disc % | GST % | Add Item
- Added minimum composer width with horizontal scroll to prevent overlap on small viewports.
- Standardized label positioning above inputs and consistent field spacing.
- Corrected action button alignment and fixed height to align with input row.
- Expanded error and submit-action rows to full width for proper visual balance.

### Files Modified
- `frontend/src/pages/PurchaseOrderPage.tsx`

### Validation
- Verified no TypeScript/IDE errors in modified file.

## FE-53: Purchase Order Line Items UI Layout Cleanup
**Date**: April 8, 2026
**Status**: ✅ Completed
**Module**: Purchase Order
**Type**: UI Enhancement

### Overview
Refined the Purchase Order line-items section into a structured, readable, and responsive tabular layout.

### Changes Made
- Replaced card-style line-item list with a proper table layout.
- Added explicit column widths for stable alignment across rows.
- Added sticky table header for better usability while scrolling.
- Added horizontal scroll support for narrow screens (`min-width` table inside scroll container).
- Enabled wrapping/breaking in item description cells to avoid overflow.
- Right-aligned numeric and amount columns for readability.
- Kept totals block aligned and visually separated from item rows.

### Files Modified
- `frontend/src/pages/PurchaseOrderPage.tsx`

### Validation
- Verified no TypeScript/IDE errors in modified file.

## FE-52: PO/GRN Delivery Tolerance UI and Flow (PUR-003)
**Date**: April 8, 2026
**Status**: ✅ Completed
**Test Case**: PUR-003
**Module**: Purchase Order, GRN
**Type**: Enhancement

### Overview
Added Under/Over Delivery Tolerance fields in PO UI, propagated values to GRN flow, and exposed values in PO/GRN details.

### Changes Made
- Added PO form fields:
  - Under Delivery Tolerance
  - Over Delivery Tolerance
- Added frontend validation: under tolerance must be less than or equal to over tolerance.
- Included tolerance values in PO create payload.
- Displayed tolerance values in PO detail modal.
- Extended GRN form state/payload with tolerance values.
- Auto-filled and locked tolerance values when GRN is created from linked PO.
- Displayed tolerance values in GRN detail modal.

### Files Modified
- `frontend/src/pages/PurchaseOrderPage.tsx`
- `frontend/src/pages/GRNPage.tsx`
- `frontend/src/api/purchase.ts`

### Validation
- Verified no TypeScript/IDE errors in modified frontend files.

## FE-51: Remove Opening Stock Field from Products Master (PRO-014)
**Date**: April 8, 2026
**Status**: ✅ Completed
**Test Case**: PRO-014
**Module**: Products Master
**Type**: Enhancement

### Overview
Removed the Opening Stock field from Products Master form UI as it is no longer required for user input.

### Changes Made
- Removed Opening Stock form field and validation binding from Product create/modify UI.
- Kept API payload compatibility by sending `opening_stock: 0` for new product creation.
- Preserved existing `opening_stock` values when modifying existing products.

### Files Modified
- `frontend/src/pages/ProductsPage.tsx`

### Validation
- Verified no TypeScript/IDE errors in the modified frontend file.

## FE-50: Country-Based Invoice Type Dropdown Restriction (SAL-030)
**Date**: April 8, 2026
**Status**: ✅ Completed
**Test Case**: SAL-030
**Module**: Sales Invoice
**Type**: Enhancement

### Overview
Updated invoice-type dropdown behavior to enforce country-based invoice type selection in UI.

### Changes Made
- Added country-scoped invoice-type option sets:
  - India -> Within State, Other State, Union Territory
  - Non-India -> Export Invoice only
- Wired dynamic dropdown option rendering based on selected customer country.
- Added automatic invoice-type reset when customer changes to an incompatible country/type combination.
- Preserved export behavior for non-India (GST hidden/0%).

### Files Modified
- `frontend/src/pages/InvoicesPage.tsx`

### Validation
- Verified no TypeScript/IDE errors after implementation.

## FE-49: SAL-030 GST Type-Aware Invoice UI Labels
**Date**: April 8, 2026
**Status**: ✅ Completed
**Test Case**: SAL-030
**Module**: Sales Invoice
**Type**: Enhancement

### Overview
Updated Sales Invoice UI to reflect applicable GST type labels dynamically for within-state, other-state, and union-territory invoice types.

### Changes Made
- Added dynamic GST column labels:
  - `IGST %` for `other_states`
  - `GST % (CGST+UTGST)` for `union_territory`
  - `GST % (CGST+SGST)` for `within_state`
- Added inline form hint showing current applied tax type (non-export only).
- Applied same dynamic GST label in invoice detail modal item table.

### Files Modified
- `frontend/src/pages/InvoicesPage.tsx`

### Validation
- Verified no TypeScript/IDE errors after implementation.

## FE-48: SAL-030 Export Invoice Import & Export Code UI
**Date**: April 8, 2026
**Status**: ✅ Completed
**Test Case**: SAL-030
**Module**: Sales Invoice, Company Profile
**Type**: Enhancement

### Overview
Added Import & Export fields in frontend forms so export invoice data and company profile number can be captured and sent to backend/PDF.

### Changes Made
- Added optional **Import & Export Code** field in Sales Invoice form.
- Included `import_export_code` in invoice create/update payload.
- Loaded/saved Import & Export Code during invoice edit flow.
- Displayed Import & Export Code in invoice detail modal when present.
- Added optional **Import & Export Number** field in Company Profile form.

### Files Modified
- `frontend/src/pages/InvoicesPage.tsx`
- `frontend/src/api/sales.ts`
- `frontend/src/pages/CompanyPage.tsx`
- `frontend/src/types/index.ts`

### Validation
- Verified no TypeScript/IDE errors after implementation.

## FE-47: Export Invoice GST UI Suppression and Zero-Tax Calculation
**Date**: April 8, 2026
**Status**: ✅ Completed
**Module**: Sales Invoice
**Type**: Bug Fix / UX + Calculation Alignment

### Overview
Aligned Sales Invoice form and detail rendering for export invoices so GST controls are hidden and totals exclude GST.

### Changes Made
- Added export-invoice flag-driven behavior in invoice form logic.
- Forced line-item GST rate to `0` in total calculation for export invoices.
- Submitted line items with `gst_rate: 0` when invoice type is export.
- Hid GST % column/input in invoice line-item entry table for export invoices.
- Adjusted table colspans to keep totals row alignment correct when GST column is hidden.
- Hid GST % column in invoice detail modal line-item table for export invoices.

### Files Modified
- `frontend/src/pages/InvoicesPage.tsx`

### Validation
- Verified no TypeScript/IDE errors after implementation.

## FE-46: SAL-029 Sales Invoice Type Dropdown and Display
**Date**: April 8, 2026
**Status**: ✅ Completed
**Test Case**: SAL-029
**Module**: Sales Invoice
**Type**: Enhancement

### Overview
Added invoice type classification UX to Sales Invoice creation and display flows with automatic defaulting and manual override.

### Changes Made
- Added **Invoice Type** dropdown in Sales Invoice form with 4 options:
  - Export Invoice
  - Sales Invoice - Within State
  - Sales Invoice - Other States
  - Sales Invoice - Union Territory
- Added default invoice type derivation in UI based on customer country/state and company state data.
- Included selected invoice type in create/update payload submission.
- Displayed invoice type in invoice list grid.
- Displayed invoice type in invoice detail modal.
- Preserved existing invoice type during edit mode.

### Files Modified
- `frontend/src/pages/InvoicesPage.tsx`
- `frontend/src/api/sales.ts`

---

## FE-45: Phone Input Split Refinement and Supplier Prefill Removal
**Date**: April 8, 2026
**Status**: ✅ Completed
**Module**: Customer, Supplier
**Type**: Bug Fix / UX Alignment

### Overview
Adjusted phone input UX and supplier default-load behavior based on retest feedback.

### Changes Made
- Customer:
  - Kept typeahead for phone country code only.
  - Replaced phone number typeahead with standard phone input field.
  - Removed edit fallback that auto-filled missing billing/shipping country with `India`.
- Supplier:
  - Kept typeahead for phone country code only.
  - Replaced phone number typeahead with standard phone input field.
  - Removed new-form prefill for country and payment terms (`billing_country` and `payment_terms_days` now load empty).
  - Updated payment terms validation parsing to support empty initial load state.

### Files Modified
- `frontend/src/pages/CustomersPage.tsx`
- `frontend/src/pages/SuppliersPage.tsx`

### Validation
- Verified no TypeScript/IDE errors after implementation.

---

## FE-44: CUS-017/CUS-018 and SUP-011 Customer/Supplier UI Updates
**Date**: April 8, 2026
**Status**: ✅ Completed
**Test Cases**: CUS-017, CUS-018, SUP-011
**Module**: Customer, Supplier
**Type**: Bug / Error + Enhancement

### Overview
Implemented Customer Master fixes to remove unintended auto-fill behavior and enhanced Supplier Master with currency + typeahead controls consistent with Customer Master.

### Changes Made
- Customer:
  - Removed company-driven address prefill in new customer form.
  - Updated defaults so billing/shipping address fields start empty.
  - Updated Payment Terms behavior so field is empty on new customer load (no prefilled value).
- Supplier:
  - Added Currency field in Supplier Master form.
  - Added typeahead for Currency, State, and Country.
  - Added phone split UI with country-code typeahead + local number typeahead.
  - Added supplier customization-options fetch and query invalidation on create/update.

### Files Modified
- `frontend/src/pages/CustomersPage.tsx`
- `frontend/src/pages/SuppliersPage.tsx`
- `frontend/src/api/suppliers.ts`
- `frontend/src/types/index.ts`

### Validation
- Verified no TypeScript/IDE errors after implementation.

---

## FE-43: Customer State Code Allows N/A
**Date**: April 8, 2026
**Status**: ✅ Completed
**Module**: Customer
**Type**: Bug Fix / Input Rule Update

### Overview
Updated Customer Master state-code handling so `N/A` can be entered for billing/shipping state code fields.

### Changes Made
- Increased Billing State Code input limit from `2` to `5` characters.
- Increased Shipping State Code input limit from `2` to `5` characters.
- Updated placeholders to include `N/A` example.
- Added state-code payload normalization to uppercase before submit, so values like `n/a` are stored as `N/A`.

### Files Modified
- `frontend/src/pages/CustomersPage.tsx`

### Validation
- Verified no TypeScript/IDE errors after implementation.

---

## FE-42: Customer Phone Parse Fix for Non-Default Country Codes
**Date**: April 8, 2026
**Status**: ✅ Completed
**Module**: Customer
**Type**: Bug Fix

### Overview
Fixed modify/change parsing issue where saved international numbers could split into incorrect country code and local number (example: `+44 7911123456` reloaded as `+447` and `911123456`).

### Changes Made
- Added `+44` to default phone country code suggestions.
- Added known country calling-code matching list and updated phone split logic to resolve country code using longest valid known prefix.
- Updated edit-mode parsing path so saved phone values are rehydrated correctly into `country code` and `phone number` fields.

### Files Modified
- `frontend/src/pages/CustomersPage.tsx`

### Validation
- Verified no TypeScript/IDE errors after implementation.

---

## FE-41: Customer Edit UI Cleanup and Phone Code Suggestion Visibility Fix
**Date**: April 8, 2026
**Status**: ✅ Completed
**Module**: Customer
**Type**: Bug Fix / UX Improvement

### Overview
Refined Customer Master modify/change experience by removing redundant internal identifier display and fixing phone country-code suggestion visibility after updates.

### Changes Made
- Removed `Customer Record ID (Read-only)` (UUID) from customer edit UI.
- Kept only business-visible `Customer ID (Read-only)` in modify/change mode.
- Enhanced reusable `TypeaheadInput` with `showAllWhenFocused` support.
- Applied `showAllWhenFocused` to phone country-code field so all available code options are visible on focus, including newly updated/saved codes.

### Files Modified
- `frontend/src/pages/CustomersPage.tsx`

### Validation
- Verified no TypeScript/IDE errors after implementation.

---

## FE-40: Customer Phone Validation Message Alignment
**Date**: April 8, 2026
**Status**: ✅ Completed
**Module**: Customer
**Type**: Bug Fix

### Overview
Removed leftover India-specific phone validation from Customer Master form schema so it matches the new international phone flow.

### Changes Made
- Replaced old schema rule `^[6-9]\d{9}$` and message `Must be a valid 10-digit Indian mobile number`.
- Added generic validation for required phone input and digit-only local number.
- Kept international validation logic on submit (country code + total 6-15 digits) unchanged.

### Files Modified
- `frontend/src/pages/CustomersPage.tsx`

### Validation
- Verified no TypeScript/IDE errors after implementation.

---

## FE-39: Customer Phone and Country Code Typeahead in Customer Master
**Date**: April 8, 2026
**Status**: ✅ Completed
**Module**: Customer
**Type**: Enhancement / UX Improvement

### Overview
Extended Customer Master phone controls to use the same custom typeahead interaction pattern used for currency, country, and state inputs.

### Changes Made
- Replaced phone country code dropdown with the reusable `TypeaheadInput` component.
- Replaced plain phone number input with `TypeaheadInput` and retained form registration through hidden field binding.
- Added phone country code suggestions merged from defaults and existing saved customer phone prefixes.
- Added phone number suggestions derived from existing customer phone data (local-number portion).
- Added country code normalization on edit/submit paths to keep outgoing phone format consistent.

### Files Modified
- `frontend/src/pages/CustomersPage.tsx`

### Validation
- Verified no TypeScript/IDE errors after implementation.

---

## FE-38: CUS-016 Customer Phone Prefix Selector and Flexible Number Input
**Date**: April 8, 2026
**Status**: ✅ Completed
**Test Case**: CUS-016
**Module**: Customer
**Type**: Bug / Error Fix

### Overview
Updated customer phone entry UX to support international numbers and explicit country prefix selection.

### Changes Made
- Removed strict 10-digit Indian phone input restrictions in Customer form.
- Added country code prefix selector with available options: `+91`, `+66`, `+65`.
- Added phone parsing helper for edit mode to split stored value into prefix + local number.
- Updated submit logic to combine prefix + local number and validate international digit limits (6-15 digits including country code).

### Files Modified
- `frontend/src/pages/CustomersPage.tsx`

### Validation
- Verified no TypeScript/IDE errors after implementation.

---

## FE-37: Customer Customization Dropdown Refresh After Save
**Date**: April 7, 2026
**Status**: ✅ Completed
**Module**: Customer
**Type**: Bug Fix

### Overview
Fixed issue where newly added customer country/currency/state values were persisted but did not appear immediately in typeahead dropdown suggestions.

### Changes Made
- Invalidated `customer-customization-options` query after successful customer create.
- Invalidated `customer-customization-options` query after successful customer update.
- This forces immediate refetch so newly added values appear in suggestion lists.

### Files Modified
- `frontend/src/pages/CustomersPage.tsx`

### Validation
- Verified no TypeScript/IDE errors after implementation.

---

## FE-36: Customer Typeahead Dropdowns for Currency/Country/State
**Date**: April 7, 2026
**Status**: ✅ Completed
**Module**: Customer
**Type**: Enhancement / UX Fix

### Overview
Replaced browser-dependent datalist behavior with a custom typeahead dropdown component to ensure suggestions are visible while typing.

### Changes Made
- Added reusable in-page `TypeaheadInput` component with filtered suggestion list and click-to-select behavior.
- Replaced Currency input with typeahead suggestions.
- Replaced Billing/Shipping Country inputs with typeahead suggestions.
- Implemented same typeahead behavior for Billing/Shipping State fields.
- Added state options fallback and merged options handling from customization API.

### Files Modified
- `frontend/src/pages/CustomersPage.tsx`
- `frontend/src/types/index.ts`

### Validation
- Verified no TypeScript/IDE errors after implementation.

---

## FE-35: Customer Country/Currency Editable Inputs with Customization Options
**Date**: April 7, 2026
**Status**: ✅ Completed
**Module**: Customer
**Type**: Enhancement

### Overview
Updated Customer Master country and currency controls to be editable while still offering suggestions from backend customization options.

### Changes Made
- Added customer API method to fetch customization options.
- Added frontend type for customization options response.
- Replaced fixed Currency dropdown with editable input + datalist suggestions.
- Replaced fixed Billing/Shipping Country dropdowns with editable inputs + datalist suggestions.
- Added fallback defaults when customization options API is unavailable.
- Normalized submitted currency to uppercase before API submit.

### Files Modified
- `frontend/src/api/customers.ts`
- `frontend/src/types/index.ts`
- `frontend/src/pages/CustomersPage.tsx`

### Validation
- Verified no TypeScript/IDE errors after implementation.

---

## FE-34: Customer Master CUS-012 - Credit Label Rename and Conditional Shipping Address
**Date**: April 7, 2026
**Status**: ✅ Completed
**Test Case**: CUS-012
**Module**: Customer
**Type**: Enhancement

### Overview
Implemented Customer Master form updates for the requested label rename and conditional shipping-address input visibility.

### Changes Made
- Renamed form label from `Credit Limit` to `Credit Limit in Currency`.
- Added separate shipping address form inputs that render only when `Shipping same as billing` is unchecked.
- Included shipping fields in customer form schema/default values and edit-mode prefill mapping.
- Updated create/update payload mapping to:
  - send shipping fields as `null` when `same_as_billing` is true
  - send entered shipping values when `same_as_billing` is false

### Files Modified
- `frontend/src/pages/CustomersPage.tsx`

### Validation
- Verified no TypeScript/IDE errors after change.
- Confirmed expected behavior: unchecking shipping checkbox shows separate shipping address section.

---

## FE-33: Full Project Architecture Baseline Review - No Frontend Changes Required
**Date**: April 7, 2026
**Status**: ✅ Verified - No Changes Needed
**Module**: Frontend Architecture / Routing / API Layer
**Type**: Baseline Verification

### Overview
Completed a full frontend architecture and workflow alignment review before starting new implementation tasks.

### Files Reviewed
- `frontend/src/App.tsx`
- `frontend/src/main.tsx`
- `frontend/src/api/client.ts`
- `frontend/src/api/auth.ts`
- `frontend/src/store/auth.ts`
- `frontend/src/routes/ProtectedRoute.tsx`
- `docs/design/DESIGN_SYSTEM_MASTER.md`
- `docs/workflows/WF_03_PURCHASE.md`
- `docs/workflows/WF_04_SALES.md`
- `docs/guides/CODING_STANDARDS.md`

### Findings
- Frontend route protection, auth bootstrap/refresh behavior, and API error handling patterns are correctly implemented.
- No frontend code updates were required for this onboarding task.

### Conclusion
No frontend changes required.

---

## FE-32: Company Form Reinitialization Fix (Typing-Time Refresh-Like Behavior)
**Date**: April 6, 2026
**Status**: ✅ Completed
**Test Case**: Page Appears to Refresh While Typing Company Input
**Module**: Company Profile Form
**Type**: Critical UX Bug Fix

### Overview
Identified and fixed form reinitialization behavior that could reset inputs during typing and appear as auto page refresh.

### Root Cause
- Company form used React Hook Form `values` prop bound to query data object.
- `values` mode can reapply incoming values frequently, causing in-progress typing to be overridden.

### Changes Made
- Replaced `values` usage with `defaultValues` initialization.
- Added guarded reset effect to apply fetched data only when form is not dirty.
- Centralized company-to-form mapping in a helper for consistent reset behavior.

### Files Modified
- `frontend/src/pages/CompanyPage.tsx`

---

## FE-31: Auto-Refresh While Typing Fix (API Base Normalization)
**Date**: April 6, 2026
**Status**: ✅ Completed
**Test Case**: Deployed App Auto Refreshes During Data Entry
**Module**: Auth API / Global API Client
**Type**: Critical Bug Fix

### Overview
Fixed production runtime issue where API base URL composition could generate invalid paths (such as `/api/api/v1/...`) and trigger repeated auth failures during normal form usage.

### Root Cause
- Mixed API base assumptions (`/api` + hardcoded `/api/v1/...` paths) caused duplicate API prefixes.
- Refresh-token endpoint URL was also composed with the same duplication risk.
- Resulted in repeated request failures and session-flow instability perceived as automatic page refresh.

### Changes Made
- Normalized API base URL in both auth and global API clients.
- Added safe handling for these base URL variants:
  - empty/same-origin
  - `/api`
  - `/api/v1`
  - absolute URLs ending with `/api`
  - absolute URLs ending with `/api/v1`
  - standard absolute URLs
- Added explicit `AUTH_REFRESH_URL` resolver in both clients.
- Kept localhost behavior on `:8001` for local development.

### Hardening Update
- Added explicit relative-path guard (`trimmed.startsWith('/') => ''`) so any relative `VITE_API_BASE_URL` in server build cannot produce duplicated API prefixes.
- Added absolute URL parsing via `new URL(...).origin` to guarantee stable base origin.

### Files Modified
- `frontend/src/api/auth.ts`
- `frontend/src/api/client.ts`

---

## FE-30: Sidebar Uses Inline Branding Logo Fallback
**Date**: April 5, 2026
**Status**: ✅ Completed
**Test Case**: Sidebar Top-Left Logo Still Missing on Ubuntu
**Module**: App Layout / Branding
**Type**: Bug Fix

### Overview
Updated sidebar logo rendering to prefer inline branding data URL and fall back to URL path.

### Changes Made
- Added `logo_data_url` to branding API type.
- Updated sidebar image source to use `logo_data_url` first.
- Relaxed render condition to show logo when either `logo_data_url` or `logo_url` is available.

### Files Modified
- `frontend/src/api/company.ts`
- `frontend/src/components/AppLayout.tsx`

---

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
