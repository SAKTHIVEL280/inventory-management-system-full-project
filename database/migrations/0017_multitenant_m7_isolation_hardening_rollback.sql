-- ════════════════════════════════════════════════════════════════════════════
-- ROLLBACK for 0017_multitenant_m7_isolation_hardening.sql  (Module M7)
-- Date: June 24, 2026 | Task: DB-212
-- Drops the NOT NULL constraint on company_id for the hardened tables.
-- Idempotent. Back up before running.
-- ════════════════════════════════════════════════════════════════════════════

BEGIN;

DO $$
DECLARE
    t TEXT;
    tables TEXT[] := ARRAY[
        'users', 'products', 'customers', 'suppliers',
        'stockists', 'sales_managers',
        'purchase_orders', 'goods_receipt_notes', 'purchase_returns',
        'quotations', 'sales_orders', 'sales_invoices', 'sales_returns',
        'proforma_invoices', 'return_delivery_notes', 'rdn_credit_notes',
        'payments', 'stock_ledger', 'service_invoices'
    ];
BEGIN
    FOREACH t IN ARRAY tables LOOP
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = t AND column_name = 'company_id'
        ) THEN
            EXECUTE format('ALTER TABLE %I ALTER COLUMN company_id DROP NOT NULL', t);
        END IF;
    END LOOP;
END $$;

-- Drop the users tenant-membership CHECK added by the forward migration.
ALTER TABLE users DROP CONSTRAINT IF EXISTS chk_users_company_or_super;

COMMIT;
