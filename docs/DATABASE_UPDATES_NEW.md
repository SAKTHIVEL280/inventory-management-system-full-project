# Database Updates Log (New Session)

**Started**: May 9, 2026

---

- **DB-50**: Created `005_multi_tenant_company_id.sql` — adds `company_id` FK+index to 14 tables, backfills data, rebuilds materialized view.
- **DB-51**: Added one-time invoice round-off backfill for totals/dues (0/5 rule).
- **DB-52** (Proforma Invoice): Created `MCN-FEAT-proforma-invoice.sql` — adds `company.pfi_prefix`/`pfi_counter` (PFI-00001 sequence) and new `proforma_invoices` + `proforma_invoice_items` tables (mirror of quotations). Idempotent; mirrored in `01_schema.sql` and `run_migration.py`; executed on DB (tables + columns verified). Quotation tables untouched.
