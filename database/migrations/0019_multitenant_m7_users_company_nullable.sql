-- ════════════════════════════════════════════════════════════════════════════
-- Multi-Tenant Migration — MODULE M7 FIX: users.company_id stays NULLable
-- File: 0019_multitenant_m7_users_company_nullable.sql
-- Date: June 25, 2026
-- BRD: docs/requirements/Mecandria_ERP_MultiTenant_BRD_v1.md §6/§10
-- Task: DB-214 (BE-226)
--
-- PROBLEM
--   Module M7 (0017) set users.company_id NOT NULL for defence-in-depth. But a
--   platform Super Admin (Module M4) is tenant-less by design (company_id IS
--   NULL), so create_super_admin.py failed with a NotNullViolation.
--
-- FIX
--   * Drop the NOT NULL on users.company_id.
--   * Replace it with a guarded CHECK: every user must belong to a tenant OR be a
--     super admin — so tenant users are still guaranteed a company_id while
--     platform super admins remain valid.
--
-- SAFETY
--   * Idempotent (DROP NOT NULL / DROP CONSTRAINT IF EXISTS / guarded re-add).
--   * The CHECK is only added if no existing row violates it.
--
-- ROLLBACK: 0019_multitenant_m7_users_company_nullable_rollback.sql
-- ════════════════════════════════════════════════════════════════════════════

BEGIN;

-- 1. Super Admins have no tenant — company_id must be NULLable.
ALTER TABLE users ALTER COLUMN company_id DROP NOT NULL;

-- 2. Enforce tenant membership for everyone else via a guarded CHECK.
DO $$
BEGIN
    ALTER TABLE users DROP CONSTRAINT IF EXISTS chk_users_company_or_super;
    IF NOT EXISTS (
        SELECT 1 FROM users WHERE company_id IS NULL AND is_super_admin = FALSE
    ) THEN
        ALTER TABLE users ADD CONSTRAINT chk_users_company_or_super
            CHECK (company_id IS NOT NULL OR is_super_admin = TRUE);
        RAISE NOTICE 'M7 fix: users CHECK (company_id OR super_admin) added';
    ELSE
        RAISE NOTICE 'M7 fix: SKIP CHECK — tenant-less non-super-admin user(s) exist; investigate then re-run';
    END IF;
END $$;

COMMIT;
