# Database Updates Log (New Session)

**Started**: May 9, 2026

---

- **DB-50**: Created `005_multi_tenant_company_id.sql` — adds `company_id` FK+index to 14 tables, backfills data, rebuilds materialized view.
- **DB-51**: Added one-time invoice round-off backfill for totals/dues (0/5 rule).
