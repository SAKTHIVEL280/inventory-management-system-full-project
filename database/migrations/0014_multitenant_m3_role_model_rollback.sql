-- ════════════════════════════════════════════════════════════════════════════
-- ROLLBACK for 0014_multitenant_m3_role_model.sql  (Module M3)
-- Date: June 24, 2026 | Task: DB-209
--
-- Restores the role check constraint to the legacy 3-role set. SAFE ONLY if no
-- user currently holds a new role ('basic'/'accounts'/'inventory'/'management'/
-- 'hr') — otherwise the ADD CONSTRAINT will fail (by design). Reassign such
-- users to a legacy role first.
--
-- WARNING: take a database backup before running any rollback.
-- ════════════════════════════════════════════════════════════════════════════

BEGIN;

ALTER TABLE users DROP CONSTRAINT IF EXISTS users_role_check;

ALTER TABLE users
ADD CONSTRAINT users_role_check
CHECK (role IN ('admin', 'inventory manager', 'general manager'));

COMMIT;
