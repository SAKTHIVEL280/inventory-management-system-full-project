-- ════════════════════════════════════════════════════════════════════════════
-- ROLLBACK for 0015_multitenant_m4_super_admin.sql  (Module M4)
-- Date: June 24, 2026 | Task: DB-210
-- WARNING: take a database backup before running any rollback. Dropping the
-- column removes the Super Admin flag from all users.
-- ════════════════════════════════════════════════════════════════════════════

BEGIN;

DROP INDEX IF EXISTS ix_users_is_super_admin;
ALTER TABLE users DROP COLUMN IF EXISTS is_super_admin;

COMMIT;
