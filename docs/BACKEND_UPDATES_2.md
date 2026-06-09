# Backend Updates Log — BRD Bugfix Sprint

**Started**: June 9, 2026
**Reference**: docs/requirements/BRD_Bugfix.md (MCN-BUG-001 → MCN-BUG-004)

---

- **BE-201** (MCN-BUG-001): `list_invoices` — added server-side `search`, `date_from`, `date_to` filters; default `page_size` 20 → 50.
- **BE-202** (MCN-BUG-003): `create_payment` rejects customer receipts with no invoice allocation; `list_payments` returns `is_unallocated` flag.
- **BE-203** (MCN-BUG-004): Added `POST /grn/{id}/reverse` (admin) — reason capture, stock/PO/ledger reversal, guards, audit log; `get_grn` returns creator/reverser names; GRNReverseRequest schema; model reversal columns.
- **BE-204** (MCN-BUG-002): Dashboard `revenue_generation` (per Sales Manager = invoice creator, per Stockist = customer) for day/week/month; removed `recent_invoices`. Added reversal cols to `run_migration.py`.
