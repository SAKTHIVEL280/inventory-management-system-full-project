-- ════════════════════════════════════════════════════════════════════════════
-- Per-tenant uniqueness for master document codes
-- File: 0024_per_tenant_master_codes.sql
-- Date: June 27, 2026
-- BRD: docs/requirements/Mecandria_ERP_MultiTenant_BRD_v1.md §10 (Data Isolation)
-- Task: DB-220 (BE-243)
--
-- PROBLEM
--   customers.customer_code, suppliers.supplier_code and products.product_code
--   carried a GLOBAL unique constraint. A brand-new tenant generating its first
--   code (e.g. CUST-TN-00001) collided with another tenant's identical code →
--   "value already exists" even with zero rows of its own. Cross-tenant leak.
--
-- FIX
--   Convert each global single-column unique into a PER-TENANT composite unique
--   (company_id, <code>) so codes are unique within a tenant and may repeat across
--   tenants. Dynamic drop-by-shape handles PG's auto-named <tbl>_<col>_key.
--
-- SAFETY: idempotent; additive; no rows changed. (units_of_measure is shared
--   reference data with no company_id, so its global abbreviation unique is kept.)
-- ROLLBACK: 0024_per_tenant_master_codes_rollback.sql
-- ════════════════════════════════════════════════════════════════════════════

BEGIN;

DO $$
DECLARE
    spec RECORD;
    con_name TEXT;
    idx_name TEXT;
BEGIN
    FOR spec IN
        SELECT * FROM (VALUES
            ('customers', 'customer_code', 'ux_customers_company_code'),
            ('suppliers', 'supplier_code', 'ux_suppliers_company_code'),
            ('products',  'product_code',  'ux_products_company_code')
        ) AS t(tbl, col, newidx)
    LOOP
        -- skip if company_id column is missing
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = spec.tbl AND column_name = 'company_id'
        ) THEN
            CONTINUE;
        END IF;

        -- drop the global single-column UNIQUE *constraint* (by shape)
        FOR con_name IN
            SELECT tc.constraint_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
            WHERE tc.table_schema = current_schema()
              AND tc.table_name = spec.tbl
              AND tc.constraint_type = 'UNIQUE'
            GROUP BY tc.constraint_name
            HAVING COUNT(*) = 1 AND MAX(kcu.column_name) = spec.col
        LOOP
            EXECUTE format('ALTER TABLE %I DROP CONSTRAINT %I', spec.tbl, con_name);
        END LOOP;

        -- drop any standalone single-column UNIQUE *index* on the code
        FOR idx_name IN
            SELECT i.relname FROM pg_index x
            JOIN pg_class i ON i.oid = x.indexrelid
            JOIN pg_class t ON t.oid = x.indrelid
            JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(x.indkey)
            WHERE t.relname = spec.tbl AND x.indisunique = TRUE
              AND x.indnatts = 1 AND a.attname = spec.col AND NOT x.indisprimary
        LOOP
            EXECUTE format('DROP INDEX IF EXISTS %I', idx_name);
        END LOOP;

        -- create the per-tenant composite unique
        EXECUTE format(
            'CREATE UNIQUE INDEX IF NOT EXISTS %I ON %I (company_id, %I)',
            spec.newidx, spec.tbl, spec.col
        );
    END LOOP;
END $$;

COMMIT;
