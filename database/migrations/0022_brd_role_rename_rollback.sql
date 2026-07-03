-- ════════════════════════════════════════════════════════════════════════════
-- ROLLBACK for 0022_brd_role_rename.sql
-- Date: June 26, 2026 | Task: DB-218
--
-- Restores the legacy-inclusive role CHECK. Role VALUES are NOT reverted
-- (management/inventory are valid under the legacy-inclusive check); revert the
-- UPDATEs manually only if you specifically need the old labels back.
-- Idempotent. Back up first.
-- ════════════════════════════════════════════════════════════════════════════

BEGIN;

ALTER TABLE users DROP CONSTRAINT IF EXISTS users_role_check;
ALTER TABLE users ADD CONSTRAINT users_role_check
    CHECK (role IN ('admin','inventory manager','general manager',
                    'basic','accounts','inventory','management','hr'));

COMMIT;
