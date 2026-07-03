-- ════════════════════════════════════════════════════════════════════════════
-- ROLLBACK for 0024_per_tenant_master_codes.sql
-- Date: June 27, 2026 | Task: DB-220
--
-- Drops the per-tenant composite uniques. The original GLOBAL uniques are only
-- restored if no cross-tenant duplicate codes exist (they may, once tenants reuse
-- codes), otherwise the restore is skipped to avoid failure. Idempotent. Back up.
-- ════════════════════════════════════════════════════════════════════════════

BEGIN;

DROP INDEX IF EXISTS ux_customers_company_code;
DROP INDEX IF EXISTS ux_suppliers_company_code;
DROP INDEX IF EXISTS ux_products_company_code;

DO $$
DECLARE spec RECORD;
BEGIN
    FOR spec IN
        SELECT * FROM (VALUES
            ('customers', 'customer_code'),
            ('suppliers', 'supplier_code'),
            ('products',  'product_code')
        ) AS t(tbl, col)
    LOOP
        EXECUTE format(
            'SELECT 1 FROM %I GROUP BY %I HAVING COUNT(*) > 1 LIMIT 1', spec.tbl, spec.col
        );
        IF NOT FOUND THEN
            EXECUTE format('CREATE UNIQUE INDEX IF NOT EXISTS %I ON %I (%I)',
                spec.tbl || '_' || spec.col || '_key', spec.tbl, spec.col);
        END IF;
    END LOOP;
END $$;

COMMIT;
