# Database Updates Log (New Session)

**Started**: May 9, 2026

---

- **DB-50**: Created `005_multi_tenant_company_id.sql` — adds `company_id` FK+index to 14 tables, backfills data, rebuilds materialized view.
- **DB-51**: Added one-time invoice round-off backfill for totals/dues (0/5 rule).
- **DB-52** (Proforma Invoice): Created `MCN-FEAT-proforma-invoice.sql` — adds `company.pfi_prefix`/`pfi_counter` (PFI-00001 sequence) and new `proforma_invoices` + `proforma_invoice_items` tables (mirror of quotations). Idempotent; mirrored in `01_schema.sql` and `run_migration.py`; executed on DB (tables + columns verified). Quotation tables untouched.
- **DB-53** (Schema sync fix): `run_migration.py` previously added `company_id` to only `users`/`products`/`customers`/`suppliers`, but the models scope 14 tables. Added idempotent `ADD COLUMN IF NOT EXISTS company_id` + index for `purchase_orders`, `goods_receipt_notes`, `purchase_returns`, `quotations`, `sales_orders`, `sales_invoices`, `sales_returns`, `payments`, `stock_ledger`, `inventory_counts`, `inventory_count_difference_audits`, `return_delivery_notes`, `rdn_credit_notes`, `proforma_invoices`, plus a backfill to the single company. Fixes production `column purchase_orders.company_id does not exist` (and the same latent crash on every other scoped module). Re-runnable.
