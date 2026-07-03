-- ════════════════════════════════════════════════════════════════════════════
-- Multi-Tenant Migration — MODULE M1: Per-tenant document numbering
-- File: 0013_multitenant_m1_per_tenant_doc_numbers.sql
-- Date: June 24, 2026
-- BRD: docs/requirements/Mecandria_ERP_MultiTenant_BRD_v1.md
-- Task: DB-207 (BE-218)
--
-- PURPOSE
--   Document numbers (invoice_number, po_number, grn_number, …) are generated
--   from per-tenant counters on the tenant's `company` row (see
--   order_number_service.py, M1). But every number column still carries a GLOBAL
--   single-column UNIQUE constraint from the single-tenant schema. With more than
--   one tenant, Tenant A's "INV-00001" and Tenant B's "INV-00001" would collide.
--
--   This migration converts each global UNIQUE(number) into a composite
--   UNIQUE(company_id, number): numbers stay unique WITHIN a tenant but may
--   repeat ACROSS tenants.
--
-- SAFETY
--   * Idempotent & dynamic: finds the existing single-column UNIQUE constraint by
--     shape (not by hard-coded name) and drops it; creates the composite index
--     with IF NOT EXISTS. Re-runnable.
--   * NO behaviour change for the existing single tenant: with one company_id,
--     UNIQUE(company_id, number) is equivalent to UNIQUE(number). All existing
--     numbers (globally unique, single tenant) satisfy the composite key.
--   * Skips any table lacking a company_id column (defensive).
--   * Single transaction — clean rollback on any error.
--
-- ROLLBACK: 0013_multitenant_m1_per_tenant_doc_numbers_rollback.sql
-- ════════════════════════════════════════════════════════════════════════════

BEGIN;

DO $$
DECLARE
    r RECORD;
    con_name TEXT;
    idx_name TEXT;
BEGIN
    FOR r IN
        SELECT * FROM (VALUES
            ('purchase_orders',       'po_number'),
            ('goods_receipt_notes',   'grn_number'),
            ('purchase_returns',      'return_number'),
            ('quotations',            'quotation_number'),
            ('proforma_invoices',     'proforma_number'),
            ('sales_orders',          'so_number'),
            ('sales_invoices',        'invoice_number'),
            ('sales_returns',         'return_number'),
            ('return_delivery_notes', 'rdn_number'),
            ('rdn_credit_notes',      'credit_note_number'),
            ('payments',              'payment_number'),
            ('inventory_counts',      'count_number')
        ) AS t(tbl, col)
    LOOP
        -- Only tables that actually have a company_id discriminator.
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = r.tbl AND column_name = 'company_id'
        ) THEN
            RAISE NOTICE 'M1: % has no company_id — skipping', r.tbl;
            CONTINUE;
        END IF;

        -- Drop any single-column UNIQUE *constraint* on the number column.
        FOR con_name IN
            SELECT tc.constraint_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name
             AND tc.table_schema = kcu.table_schema
            WHERE tc.table_schema = current_schema()
              AND tc.table_name = r.tbl
              AND tc.constraint_type = 'UNIQUE'
            GROUP BY tc.constraint_name
            HAVING COUNT(*) = 1 AND MAX(kcu.column_name) = r.col
        LOOP
            EXECUTE format('ALTER TABLE %I DROP CONSTRAINT %I', r.tbl, con_name);
            RAISE NOTICE 'M1: dropped global unique constraint % on %.%', con_name, r.tbl, r.col;
        END LOOP;

        -- Drop any standalone single-column UNIQUE *index* on the number column
        -- (in case uniqueness was expressed as an index rather than a constraint).
        FOR idx_name IN
            SELECT i.relname
            FROM pg_index x
            JOIN pg_class i ON i.oid = x.indexrelid
            JOIN pg_class t ON t.oid = x.indrelid
            JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(x.indkey)
            WHERE t.relname = r.tbl
              AND x.indisunique = TRUE
              AND x.indnatts = 1
              AND a.attname = r.col
              AND NOT x.indisprimary
        LOOP
            EXECUTE format('DROP INDEX IF EXISTS %I', idx_name);
            RAISE NOTICE 'M1: dropped global unique index % on %.%', idx_name, r.tbl, r.col;
        END LOOP;

        -- Create the per-tenant composite unique index.
        EXECUTE format(
            'CREATE UNIQUE INDEX IF NOT EXISTS ux_%s_company_number ON %I (company_id, %I)',
            r.tbl, r.tbl, r.col
        );
    END LOOP;
END $$;

COMMIT;
