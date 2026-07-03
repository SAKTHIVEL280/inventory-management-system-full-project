-- ════════════════════════════════════════════════════════════════════════════
-- Multi-Tenant Migration — MODULE M0: Foundation & Safety Net
-- File: 0012_multitenant_m0_tenant_registry.sql
-- Date: June 24, 2026
-- BRD: docs/requirements/Mecandria_ERP_MultiTenant_BRD_v1.md (§4.2, §5, §9.1)
-- Task: DB-206 (BE-217)
--
-- PURPOSE
--   Promote the single-row `company` table into a tenant registry by adding the
--   subscription / lifecycle columns required by the BRD ERP-Customer record,
--   and guarantee every existing production row carries a company_id so future
--   tenant-scoped queries never lose data.
--
-- ISOLATION MODEL (confirmed): shared database + company_id discriminator
--   (row-level isolation, optionally hardened with RLS in a later module).
--
-- SAFETY GUARANTEES
--   * 100% ADDITIVE. No column is dropped, renamed, or retyped.
--   * Idempotent — uses ADD COLUMN IF NOT EXISTS and guarded constraint blocks;
--     safe to run multiple times.
--   * NO behaviour change: the new columns are pure data (no code enforces plan
--     gating yet — that arrives in module M2). The existing live company is
--     backfilled as an ACTIVE, PLATINUM (full-access) tenant so nothing locks.
--   * Does NOT add NOT NULL constraints on company_id (deferred to the isolation-
--     hardening module to avoid breaking inserts that don't yet set it).
--   * Wrapped in a single transaction — any failure rolls back cleanly.
--
-- ROLLBACK: see 0012_multitenant_m0_tenant_registry_rollback.sql
-- ════════════════════════════════════════════════════════════════════════════

BEGIN;

-- ─────────────────────────────────────────────────────────────────────────────
-- 1. TENANT REGISTRY COLUMNS on `company`
--    Maps BRD §4.2 "ERP Customer record" fields onto the existing company table.
--    (ERP Customer Name = name, License No./GSTR = gstin, Email = email,
--     Address = address_line*, all already present.)
-- ─────────────────────────────────────────────────────────────────────────────

-- Subscription plan: FREE | SILVER | GOLD | PLATINUM. Legacy tenant defaults to
-- PLATINUM so it retains full module access once gating is introduced (M2).
ALTER TABLE company ADD COLUMN IF NOT EXISTS subscription_plan VARCHAR(20) NOT NULL DEFAULT 'PLATINUM';

-- Account lifecycle status: active | inactive | suspended | trial.
ALTER TABLE company ADD COLUMN IF NOT EXISTS account_status VARCHAR(20) NOT NULL DEFAULT 'active';

-- Subscription billing payment status: paid | pending | overdue.
ALTER TABLE company ADD COLUMN IF NOT EXISTS payment_status VARCHAR(20) NOT NULL DEFAULT 'paid';

-- Lifecycle / subscription dates. onboarding_date defaults to today for new rows;
-- the existing row is backfilled from created_at below. Subscription window is
-- nullable — NULL expiry == no expiry (legacy tenant never lapses).
ALTER TABLE company ADD COLUMN IF NOT EXISTS onboarding_date DATE DEFAULT CURRENT_DATE;
ALTER TABLE company ADD COLUMN IF NOT EXISTS subscription_start_date DATE;
ALTER TABLE company ADD COLUMN IF NOT EXISTS subscription_expiry_date DATE;

-- BRD profile fields not previously modelled on company.
ALTER TABLE company ADD COLUMN IF NOT EXISTS business_category VARCHAR(100);
ALTER TABLE company ADD COLUMN IF NOT EXISTS contact_person_name VARCHAR(255);
ALTER TABLE company ADD COLUMN IF NOT EXISTS contact_number VARCHAR(20);

-- Tenant code for future subdomain / tenant-URL routing (BRD §9.1). Nullable now.
ALTER TABLE company ADD COLUMN IF NOT EXISTS tenant_code VARCHAR(50);

-- Unique tenant_code where present (partial unique index tolerates many NULLs).
CREATE UNIQUE INDEX IF NOT EXISTS ux_company_tenant_code
    ON company (tenant_code) WHERE tenant_code IS NOT NULL;

-- ─────────────────────────────────────────────────────────────────────────────
-- 2. VALUE-DOMAIN GUARDS (idempotent, added only if absent)
-- ─────────────────────────────────────────────────────────────────────────────

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'company_subscription_plan_check') THEN
        ALTER TABLE company ADD CONSTRAINT company_subscription_plan_check
            CHECK (subscription_plan IN ('FREE','SILVER','GOLD','PLATINUM'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'company_account_status_check') THEN
        ALTER TABLE company ADD CONSTRAINT company_account_status_check
            CHECK (account_status IN ('active','inactive','suspended','trial'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'company_payment_status_check') THEN
        ALTER TABLE company ADD CONSTRAINT company_payment_status_check
            CHECK (payment_status IN ('paid','pending','overdue'));
    END IF;
END $$;

-- ─────────────────────────────────────────────────────────────────────────────
-- 3. BACKFILL the existing (legacy) tenant row to sensible, non-locking values.
--    Only touches rows where the new fields are still at their NULL/implicit
--    state, so re-runs are no-ops.
-- ─────────────────────────────────────────────────────────────────────────────

UPDATE company
SET onboarding_date = COALESCE(onboarding_date, created_at::date, CURRENT_DATE)
WHERE onboarding_date IS NULL;

-- ─────────────────────────────────────────────────────────────────────────────
-- 4. TENANT-ID BACKFILL across every scoped business table.
--    Guarantees no historical row has a NULL company_id (which would vanish under
--    tenant-scoped queries). Assigns all existing data to the single legacy
--    tenant. Mirrors the logic already in backend/run_migration.py and is safe
--    to re-run.
-- ─────────────────────────────────────────────────────────────────────────────

DO $$
DECLARE
    _legacy_company_id UUID;
    _tbl TEXT;
    _tables TEXT[] := ARRAY[
        'users','products','customers','suppliers','product_categories',
        'purchase_orders','goods_receipt_notes','purchase_returns',
        'quotations','sales_orders','sales_invoices','sales_returns',
        'payments','stock_ledger','inventory_counts',
        'inventory_count_difference_audits','return_delivery_notes',
        'rdn_credit_notes','proforma_invoices','stockists','sales_managers',
        'audit_logs','gst_report_audit_logs'
    ];
BEGIN
    SELECT id INTO _legacy_company_id FROM company ORDER BY created_at ASC LIMIT 1;

    IF _legacy_company_id IS NULL THEN
        RAISE NOTICE 'M0: no company row found — skipping tenant-id backfill.';
        RETURN;
    END IF;

    FOREACH _tbl IN ARRAY _tables LOOP
        -- Only operate on tables that exist AND have a company_id column.
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = _tbl
              AND column_name = 'company_id'
        ) THEN
            EXECUTE format(
                'UPDATE %I SET company_id = $1 WHERE company_id IS NULL', _tbl
            ) USING _legacy_company_id;
        END IF;
    END LOOP;

    RAISE NOTICE 'M0: tenant-id backfill complete for legacy company %', _legacy_company_id;
END $$;

COMMIT;

-- ─────────────────────────────────────────────────────────────────────────────
-- 5. POST-MIGRATION VERIFICATION (read-only; run manually after COMMIT)
--    Every count below MUST be 0. If any row is returned, investigate before
--    creating a second tenant.
--
--   SELECT 'users' AS tbl, COUNT(*) AS null_company_id FROM users WHERE company_id IS NULL
--   UNION ALL SELECT 'products', COUNT(*) FROM products WHERE company_id IS NULL
--   UNION ALL SELECT 'customers', COUNT(*) FROM customers WHERE company_id IS NULL
--   UNION ALL SELECT 'suppliers', COUNT(*) FROM suppliers WHERE company_id IS NULL
--   UNION ALL SELECT 'sales_invoices', COUNT(*) FROM sales_invoices WHERE company_id IS NULL
--   UNION ALL SELECT 'purchase_orders', COUNT(*) FROM purchase_orders WHERE company_id IS NULL
--   UNION ALL SELECT 'payments', COUNT(*) FROM payments WHERE company_id IS NULL
--   UNION ALL SELECT 'stock_ledger', COUNT(*) FROM stock_ledger WHERE company_id IS NULL;
--
--   (The bundled helper backend/verify_tenant_isolation.py runs the full sweep.)
-- ─────────────────────────────────────────────────────────────────────────────
