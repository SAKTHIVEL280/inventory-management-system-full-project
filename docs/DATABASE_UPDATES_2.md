# Database Updates Log — BRD Bugfix Sprint

**Started**: June 9, 2026
**Reference**: docs/requirements/BRD_Bugfix.md (MCN-BUG-001 → MCN-BUG-004)

---

- **DB-201** (MCN-BUG-004): `0010_grn_reverse_2026_06_09.sql` — adds `reversed` to GRN status CHECK; adds `reversal_reason`, `reversed_at`, `reversed_by` columns. Mirrored in `01_schema.sql` and `run_migration.py`; executed on DB (columns + CHECK verified).
