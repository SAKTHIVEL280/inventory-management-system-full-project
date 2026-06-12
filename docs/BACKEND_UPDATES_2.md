# Backend Updates Log — BRD Bugfix Sprint

**Started**: June 9, 2026
**Reference**: docs/requirements/BRD_Bugfix.md (MCN-BUG-001 → MCN-BUG-004)

---

- **BE-201** (MCN-BUG-001): `list_invoices` — added server-side `search`, `date_from`, `date_to` filters; default `page_size` 20 → 50.
- **BE-202** (MCN-BUG-003): `create_payment` rejects customer receipts with no invoice allocation; `list_payments` returns `is_unallocated` flag.
- **BE-203** (MCN-BUG-004): Added `POST /grn/{id}/reverse` (admin) — reason capture, stock/PO/ledger reversal, guards, audit log; `get_grn` returns creator/reverser names; GRNReverseRequest schema; model reversal columns.
- **BE-204** (MCN-BUG-002): Dashboard `revenue_generation` (per Sales Manager = invoice creator, per Stockist = customer) for day/week/month; removed `recent_invoices`. Added reversal cols to `run_migration.py`.

### BRD Bugfix v1.5 (docs/requirements/BRD_Bugfix_v1.5.md)

- **BE-205** (MCN-BUG-004-ii): New `PUT /api/v1/grn/{id}/confirmed-details` (`grn_write`) — edits Batch/Qty/Rate/Expiry/MFG/Remarks of a **confirmed** GRN. Reconciles stock by reversing the original ledger postings and re-posting corrected values (same mechanics as confirm/reverse), recalculates GRN totals (payables derive from these), and writes a field-level audit entry (field, old, new, user, timestamp). Guards: blocks edit when a non-cancelled payment is allocated or a confirmed purchase return exists, and when a reduction would drive on-hand stock negative. Adjusts PO `received_quantity` by the per-line delta and recomputes PO status. Draft GRN editing (`PUT /api/v1/grn/{id}`) is unchanged. New schemas `GRNConfirmedEditRequest`/`GRNConfirmedEditItem`. GRN number/supplier/created details never modified.
- **BE-206** (MCN-BUG-005): `GET /reports/sales` now joins `customers` (via `bill_to_customer_id` → `customer_id` fallback) and returns `customer_name` per invoice row.
- **BE-207** (MCN-BUG-006): Sales Invoice ("Sales Order" — the retired SO module redirects to invoices) edit versioning. `audit_logs.version` populated on each successful full-resource invoice edit (`PUT /api/vN/invoices/{id}`) via `log_audit_event`; first edit = 1, incrementing; creation/non-edit/status changes stay NULL; append-only rows make it immutable. `int_to_roman()` helper added. `/reports/action-logs` returns `version` + `version_label` ("Version I", ...).
- **BE-208** (Action Logs 500 fix): `_ensure_audit_logs_table` now self-heals `audit_logs.company_id` (+ index) and `audit_logs.version`. Root cause: the action-logs SELECT and the `log_audit_event` INSERT reference `company_id`, which was missing on deployments predating the multi-tenant migration → `UndefinedColumn` → 500. Idempotent; runs on every audit access.
