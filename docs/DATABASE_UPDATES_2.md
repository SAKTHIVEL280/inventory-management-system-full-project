# Database Updates Log — BRD Bugfix Sprint

**Started**: June 9, 2026
**Reference**: docs/requirements/BRD_Bugfix.md (MCN-BUG-001 → MCN-BUG-004)

---

- **DB-201** (MCN-BUG-004): `0010_grn_reverse_2026_06_09.sql` — adds `reversed` to GRN status CHECK; adds `reversal_reason`, `reversed_at`, `reversed_by` columns. Mirrored in `01_schema.sql` and `run_migration.py`; executed on DB (columns + CHECK verified).

### BRD Bugfix v1.5 (docs/requirements/BRD_Bugfix_v1.5.md)

- **DB-202** (MCN-BUG-006 + Action Logs 500): `migrations/MCN-BUGFIX-v1.5.sql` — idempotent `ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS company_id UUID` (+ `ix_audit_logs_company_id`) and `ADD COLUMN IF NOT EXISTS version INTEGER`. `company_id` fixes the Action Logs 500 (`UndefinedColumn` on deployments predating multi-tenant scoping); `version` stores the immutable Sales Invoice edit version (Roman-numeral I/II/... derived in the report layer). Mirrored in `01_schema.sql` (`audit_logs` CREATE now declares both columns + the company_id index). Also self-healed at runtime by `_ensure_audit_logs_table` (`audit_service.py`) so the columns exist even if the migration has not been run.
- **DB-203** (Human-readable audit descriptions / BE-209): No schema change. Audit descriptions are composed at write time and re-composed at read time from the existing `audit_logs.description` / `details` (JSONB) columns; field-level changes ride in `details.changes`. Listed here only to record that the readability enhancement required no migration.

### BRD Bugfix — GRN Batch / Invoice Edit-After-Issue / Country Master

- **DB-204** (GRN Batch mandatory / Invoice edit-after-issue / Country master — BE-210/211/212, FE-210/211/212): **No schema change and no migration.** (1) GRN batch is enforced in application validation; `grn_items.batch_no` already exists. (2) Invoice edit-after-issue reuses the existing `stock_ledger` (reversal entries use `transaction_type='adjustment'`, `reference_type='inv_edit_reversal'` (≤ the `stock_ledger.reference_type` 20-char limit); corrected sales re-use `transaction_type='sale'`, `reference_type='invoice'` — both already permitted by the ledger's existing type set) and the existing `audit_logs` columns; invoice totals/`amount_due`/`status` are existing columns. (3) The country master is served from the existing `customization_options` table unioned with an application-level constant list — no new table or column. `01_schema.sql` is therefore unchanged.

### Enhancement 3 — Sales Invoice: Mandatory Fields & Filters (docs/requirements/Enhancement-requirement-1.md, FR-15 → FR-24)

- **DB-205** (Enhancement 3 — Stockist & Sales Manager masters + invoice fields): `migrations/0011_stockist_sales_manager_masters.sql` (idempotent). (1) New `stockists` table (`id` UUID PK, `name` VARCHAR(150) NOT NULL, `city` VARCHAR(120), `is_active`/`is_deleted` BOOL, `deleted_at`, `created_at`, `updated_at`, `company_id` FK→company, `created_by` FK→users) + index on `name`. (2) New `sales_managers` table (same shape plus `employee_id` VARCHAR(50) and `region` VARCHAR(120)) + index on `name`. (3) `ALTER TABLE sales_invoices ADD COLUMN IF NOT EXISTS` for `stockist_name` VARCHAR(150), `stockist_city` VARCHAR(120), `sales_manager_name` VARCHAR(150) — all nullable so existing invoices remain valid (mandatory enforcement is at the application layer, BE-214) — plus indexes `ix_sales_invoices_stockist_name` and `ix_sales_invoices_sales_manager_name` for the list filters. Mirrored in `01_schema.sql` (the two new `CREATE TABLE` blocks + the three columns/indexes on `sales_invoices`) and in `run_migration.py` (idempotent `ADD COLUMN IF NOT EXISTS` / `CREATE TABLE IF NOT EXISTS`). Not executed against the user's database (run on deploy).
