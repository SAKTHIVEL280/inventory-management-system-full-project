# Frontend Updates Log — BRD Bugfix Sprint

**Started**: June 9, 2026
**Reference**: docs/requirements/BRD_Bugfix.md (MCN-BUG-001 → MCN-BUG-004)

---

- **FE-201** (MCN-BUG-001): Invoices page now server-paginated — rows-per-page (20/50/100/All), Prev/Next, page indicator; search & date filters moved server-side.
- **FE-202** (MCN-BUG-003): Record Payment requires ≥1 invoice allocation — inline error, disabled Save; list flags legacy unallocated receipts with a red badge.
- **FE-203** (MCN-BUG-004): GRN — Reverse button (confirmed, admin) with mandatory-reason modal; detail view shows read-only Created Date/By + reversal info; 'reversed' status filter/badge.
- **FE-204** (MCN-BUG-002): Dashboard — removed Recent Invoices widget; added side-by-side Sales Manager & Stockist revenue bar charts with independent Day/Week/Month toggles, distinct colors, tooltips.

### BRD Bugfix v1.5 (docs/requirements/BRD_Bugfix_v1.5.md)

- **FE-205** (MCN-BUG-004-ii): GRN detail modal — "Edit" button (confirmed GRNs, `grn_write` users) unlocks in-place editing of Batch/Qty/Free/Rate/MFG/EXP per line + Remarks, with Save/Cancel and client-side validation. Save calls `PUT /grn/{id}/confirmed-details`; on success re-fetches GRN + refreshes lists. GRN number/supplier/created details stay read-only. New `purchaseApi.updateConfirmedGRN` + `ConfirmedGRNEditPayload` types.
- **FE-206** (MCN-BUG-005): Reports → Sales Report — added "Customer Name" column; added a Customer Name filter input, a sortable Customer Name header (asc/desc/none), and an "Export CSV" button (BOM-prefixed, Excel-compatible) including Customer Name.
- **FE-207** (MCN-BUG-006): Action Logs — added a sortable "Version" column rendering the Roman-numeral `version_label` (e.g. "Version I") for Sales Invoice edits; `ActionLogItem` gains `version`/`version_label`.
- **FE-208** (Company profile logos): Company profile now renders the Company Logo and Ambassador Logo via the backend-served `/api/v1/company/(logo|ambassador-logo)-file` endpoints (cache-busted by stored filename) instead of the raw `/static/*` path that 404s on the deployed origin — logos now display instead of the placeholder.
