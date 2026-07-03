-- ════════════════════════════════════════════════════════════════════════════
-- Multi-Tenant Migration — Residual company_id backfill (fix)
-- File: 0018_multitenant_backfill_residual.sql
-- Date: June 24, 2026
-- Task: DB-213 (BE-224)
--
-- PURPOSE
--   verify_tenant_isolation.py flagged NULL company_id on three tables that the
--   earlier backfills (run_migration.py) missed:
--     • product_categories  — real tenant data → assign to the legacy tenant.
--     • audit_logs          — backfill from the acting user where known; rows
--                             with no user (system / pre-auth events, e.g. failed
--                             logins) legitimately keep NULL company_id.
--     • gst_report_audit_logs — same user-derived backfill.
--
-- SAFETY: idempotent (only touches NULL rows); additive; single transaction.
-- ════════════════════════════════════════════════════════════════════════════

BEGIN;

DO $$
DECLARE
    _legacy_company_id UUID;
BEGIN
    SELECT id INTO _legacy_company_id FROM company ORDER BY created_at ASC LIMIT 1;
    IF _legacy_company_id IS NULL THEN
        RAISE NOTICE 'Residual backfill: no company row — skipping.';
        RETURN;
    END IF;

    -- product_categories: tenant data, assign to the single/legacy tenant.
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = 'product_categories' AND column_name = 'company_id'
    ) THEN
        UPDATE product_categories
        SET company_id = _legacy_company_id
        WHERE company_id IS NULL;
    END IF;

    -- audit_logs: derive from the acting user; leave system/pre-auth rows NULL.
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = 'audit_logs' AND column_name = 'company_id'
    ) THEN
        UPDATE audit_logs a
        SET company_id = u.company_id
        FROM users u
        WHERE a.user_id = u.id
          AND a.company_id IS NULL
          AND u.company_id IS NOT NULL;
    END IF;

    -- gst_report_audit_logs: derive from the acting user.
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = 'gst_report_audit_logs' AND column_name = 'company_id'
    ) THEN
        UPDATE gst_report_audit_logs g
        SET company_id = u.company_id
        FROM users u
        WHERE g.user_id = u.id
          AND g.company_id IS NULL
          AND u.company_id IS NOT NULL;
    END IF;

    RAISE NOTICE 'Residual backfill complete for legacy company %', _legacy_company_id;
END $$;

-- product_categories.name: convert the GLOBAL unique to per-tenant unique
-- (company_id, name) so different tenants may reuse a category name.
DO $$
DECLARE con_name TEXT; idx_name TEXT;
BEGIN
    FOR con_name IN
        SELECT tc.constraint_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
        WHERE tc.table_schema = current_schema()
          AND tc.table_name = 'product_categories'
          AND tc.constraint_type = 'UNIQUE'
        GROUP BY tc.constraint_name
        HAVING COUNT(*) = 1 AND MAX(kcu.column_name) = 'name'
    LOOP
        EXECUTE format('ALTER TABLE product_categories DROP CONSTRAINT %I', con_name);
    END LOOP;
    FOR idx_name IN
        SELECT i.relname FROM pg_index x
        JOIN pg_class i ON i.oid = x.indexrelid
        JOIN pg_class t ON t.oid = x.indrelid
        JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(x.indkey)
        WHERE t.relname = 'product_categories' AND x.indisunique = TRUE
          AND x.indnatts = 1 AND a.attname = 'name' AND NOT x.indisprimary
    LOOP
        EXECUTE format('DROP INDEX IF EXISTS %I', idx_name);
    END LOOP;
    CREATE UNIQUE INDEX IF NOT EXISTS ux_product_categories_company_name
        ON product_categories (company_id, name);
END $$;

COMMIT;
