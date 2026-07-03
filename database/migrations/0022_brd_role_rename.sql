-- ════════════════════════════════════════════════════════════════════════════
-- BRD role model — rename legacy roles + tighten users.role check
-- File: 0022_brd_role_rename.sql
-- Date: June 26, 2026
-- BRD: docs/requirements/Mecandria_ERP_MultiTenant_BRD_v1.md §6
-- Task: DB-218 (BE-238 / FE-231)
--
-- PURPOSE
--   The BRD defines exactly five end-user roles (Basic, Accounts, Inventory,
--   Management, HR) plus the Tenant Admin. The legacy roles are renamed:
--     • General Manager  → Accounts
--     • Inventory Manager → Inventory
--   and the obsolete legacy values are removed from the role CHECK.
--
-- SAFETY
--   * Renames existing user rows first, then tightens the CHECK.
--   * The new CHECK is added only if no row violates it (otherwise the
--     legacy-inclusive CHECK is kept so the migration never fails). Re-run after
--     fixing any straggler rows to get the strict constraint.
--   * Idempotent; additive to data (no rows dropped).
--
-- ROLLBACK: 0022_brd_role_rename_rollback.sql
-- ════════════════════════════════════════════════════════════════════════════

BEGIN;

UPDATE users SET role = 'accounts' WHERE role = 'general manager';
UPDATE users SET role = 'inventory'  WHERE role = 'inventory manager';

ALTER TABLE users DROP CONSTRAINT IF EXISTS users_role_check;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM users
        WHERE role NOT IN ('admin','basic','accounts','inventory','management','hr')
    ) THEN
        ALTER TABLE users ADD CONSTRAINT users_role_check
            CHECK (role IN ('admin','basic','accounts','inventory','management','hr'));
        RAISE NOTICE 'users_role_check tightened to BRD roles.';
    ELSE
        ALTER TABLE users ADD CONSTRAINT users_role_check
            CHECK (role IN ('admin','inventory manager','general manager',
                            'basic','accounts','inventory','management','hr'));
        RAISE NOTICE 'users_role_check kept legacy-inclusive — un-migrated role values exist.';
    END IF;
END $$;

COMMIT;
