-- ════════════════════════════════════════════════════════════════════════════
-- ROLLBACK for 0019_multitenant_m7_users_company_nullable.sql
-- Date: June 25, 2026 | Task: DB-214
--
-- Drops the tenant-membership CHECK. NOT NULL is NOT re-applied automatically:
-- doing so would break Super Admin accounts (tenant-less). Re-apply NOT NULL only
-- if you have removed all super admins and want the stricter 0017 behaviour.
-- Idempotent. Back up before running.
-- ════════════════════════════════════════════════════════════════════════════

BEGIN;

ALTER TABLE users DROP CONSTRAINT IF EXISTS chk_users_company_or_super;

COMMIT;
