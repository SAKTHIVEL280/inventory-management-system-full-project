-- ════════════════════════════════════════════════════════════════════════════
-- ROLLBACK for 0012_multitenant_m0_tenant_registry.sql  (Module M0)
-- Date: June 24, 2026
-- Task: DB-206
--
-- Reverts ONLY the additive tenant-registry columns/constraints introduced by M0.
-- It does NOT undo the company_id backfill (step 4 of the forward migration):
-- setting historical rows back to NULL would REMOVE data visibility and serves no
-- purpose — the backfill is a data-integrity correction, not a feature.
--
-- Safe / idempotent: uses IF EXISTS everywhere. Run only if you must remove the
-- registry columns (e.g. abandoning the multi-tenant migration).
--
-- WARNING: take a database backup before running any rollback.
-- ════════════════════════════════════════════════════════════════════════════

BEGIN;

ALTER TABLE company DROP CONSTRAINT IF EXISTS company_subscription_plan_check;
ALTER TABLE company DROP CONSTRAINT IF EXISTS company_account_status_check;
ALTER TABLE company DROP CONSTRAINT IF EXISTS company_payment_status_check;

DROP INDEX IF EXISTS ux_company_tenant_code;

ALTER TABLE company DROP COLUMN IF EXISTS subscription_plan;
ALTER TABLE company DROP COLUMN IF EXISTS account_status;
ALTER TABLE company DROP COLUMN IF EXISTS payment_status;
ALTER TABLE company DROP COLUMN IF EXISTS onboarding_date;
ALTER TABLE company DROP COLUMN IF EXISTS subscription_start_date;
ALTER TABLE company DROP COLUMN IF EXISTS subscription_expiry_date;
ALTER TABLE company DROP COLUMN IF EXISTS business_category;
ALTER TABLE company DROP COLUMN IF EXISTS contact_person_name;
ALTER TABLE company DROP COLUMN IF EXISTS contact_number;
ALTER TABLE company DROP COLUMN IF EXISTS tenant_code;

COMMIT;
