-- ════════════════════════════════════════════════════════════════════════════
-- Multi-Tenant Migration — MODULE M7: Isolation hardening
-- File: 0017_multitenant_m7_isolation_hardening.sql
-- Date: June 24, 2026
-- BRD: docs/requirements/Mecandria_ERP_MultiTenant_BRD_v1.md §10 (Data Isolation)
-- Task: DB-212 (BE-223)
--
-- PURPOSE
--   Defence-in-depth: enforce NOT NULL on company_id for tables whose every
--   application insert path is confirmed to set it, so no future row can be
--   written without a tenant (a NULL company_id would silently escape tenant
--   scoping). The stock_ledger gap (service inserts that omitted company_id) was
--   fixed in code (BE-223) before this constraint is applied.
--
-- SAFETY
--   * GUARDED: each table is set NOT NULL ONLY if it currently has zero NULL
--     company_id rows — so this migration can never fail on legacy data. Tables
--     with stragglers are skipped with a NOTICE (re-run after backfilling).
--   * Idempotent (SET NOT NULL on an already-NOT NULL column is a no-op).
--   * Excludes tables with legitimately nullable company_id (audit_logs and
--     gst_report_audit_logs may log system/pre-auth events; inventory_counts and
--     product_categories are not yet exhaustively audited and stay nullable).
--   * `users` is EXCLUDED from NOT NULL: platform Super Admins are tenant-less
--     (company_id IS NULL). Instead a guarded CHECK enforces that every user
--     either belongs to a tenant OR is a super admin.
--
-- ROLLBACK: 0017_multitenant_m7_isolation_hardening_rollback.sql
-- ════════════════════════════════════════════════════════════════════════════

BEGIN;

DO $$
DECLARE
    t TEXT;
    null_count BIGINT;
    tables TEXT[] := ARRAY[
        'products', 'customers', 'suppliers',
        'stockists', 'sales_managers',
        'purchase_orders', 'goods_receipt_notes', 'purchase_returns',
        'quotations', 'sales_orders', 'sales_invoices', 'sales_returns',
        'proforma_invoices', 'return_delivery_notes', 'rdn_credit_notes',
        'payments', 'stock_ledger', 'service_invoices'
    ];
BEGIN
    FOREACH t IN ARRAY tables LOOP
        -- skip if table or column missing
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = t AND column_name = 'company_id'
        ) THEN
            CONTINUE;
        END IF;

        EXECUTE format('SELECT COUNT(*) FROM %I WHERE company_id IS NULL', t)
            INTO null_count;

        IF null_count = 0 THEN
            EXECUTE format('ALTER TABLE %I ALTER COLUMN company_id SET NOT NULL', t);
            RAISE NOTICE 'M7: % .company_id set NOT NULL', t;
        ELSE
            RAISE NOTICE 'M7: SKIP % — % row(s) with NULL company_id (backfill then re-run)', t, null_count;
        END IF;
    END LOOP;
END $$;

-- users.company_id stays NULLable (Super Admins are tenant-less). Enforce tenant
-- membership for everyone else via a guarded CHECK instead of NOT NULL.
DO $$
BEGIN
    ALTER TABLE users DROP CONSTRAINT IF EXISTS chk_users_company_or_super;
    IF NOT EXISTS (
        SELECT 1 FROM users WHERE company_id IS NULL AND is_super_admin = FALSE
    ) THEN
        ALTER TABLE users ADD CONSTRAINT chk_users_company_or_super
            CHECK (company_id IS NOT NULL OR is_super_admin = TRUE);
        RAISE NOTICE 'M7: users CHECK (company_id OR super_admin) added';
    ELSE
        RAISE NOTICE 'M7: SKIP users CHECK — tenant-less non-super-admin user(s) exist';
    END IF;
END $$;

COMMIT;
