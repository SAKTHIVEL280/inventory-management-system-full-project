-- ════════════════════════════════════════════════════════════════════════════
-- Multi-Tenant Migration — Scope customization_options to the tenant
-- File: 0020_multitenant_customization_options_tenant.sql
-- Date: June 25, 2026
-- BRD: docs/requirements/Mecandria_ERP_MultiTenant_BRD_v1.md §10 (Data Isolation)
-- Task: DB-215 (BE-228)
--
-- PROBLEM
--   `customization_options` (dropdown values for customer/supplier/rdn etc.) had
--   NO company_id — it was a single global table shared by every tenant. One
--   tenant's custom country/state/currency/return-reason values appeared in another
--   tenant's dropdowns: a cross-tenant data leak.
--
-- FIX
--   * Add company_id (FK company) + index.
--   * Backfill existing rows to the legacy (oldest) tenant.
--   * Replace the GLOBAL unique (module, field_name, option_value) with a
--     PER-TENANT unique (company_id, module, field_name, option_value) so each
--     tenant keeps its own option set and may reuse values another tenant has.
--
-- SAFETY: idempotent; additive; only touches NULL rows; single transaction.
-- ROLLBACK: 0020_multitenant_customization_options_tenant_rollback.sql
-- ════════════════════════════════════════════════════════════════════════════

BEGIN;

ALTER TABLE customization_options ADD COLUMN IF NOT EXISTS company_id UUID;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_customization_options_company') THEN
        ALTER TABLE customization_options
            ADD CONSTRAINT fk_customization_options_company
            FOREIGN KEY (company_id) REFERENCES company(id);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS ix_customization_options_company_id
    ON customization_options (company_id);

-- Backfill existing rows to the legacy (oldest) tenant.
DO $$
DECLARE _legacy_company_id UUID;
BEGIN
    SELECT id INTO _legacy_company_id FROM company ORDER BY created_at ASC LIMIT 1;
    IF _legacy_company_id IS NOT NULL THEN
        UPDATE customization_options
        SET company_id = _legacy_company_id
        WHERE company_id IS NULL;
        RAISE NOTICE 'customization_options backfilled to legacy company %', _legacy_company_id;
    ELSE
        RAISE NOTICE 'customization_options backfill skipped — no company row.';
    END IF;
END $$;

-- Drop the global UNIQUE(module, field_name, option_value) and create a
-- per-tenant unique that additionally keys on company_id.
DO $$
BEGIN
    ALTER TABLE customization_options
        DROP CONSTRAINT IF EXISTS uq_customization_option_scope;
END $$;
-- The old global unique may exist as a standalone INDEX (not a constraint), which
-- DROP CONSTRAINT does not remove. Drop the index form too so it stops enforcing
-- cross-tenant uniqueness on (module, field_name, option_value).
DROP INDEX IF EXISTS uq_customization_option_scope;

CREATE UNIQUE INDEX IF NOT EXISTS ux_customization_options_company_scope
    ON customization_options (company_id, module, field_name, option_value);

COMMIT;
