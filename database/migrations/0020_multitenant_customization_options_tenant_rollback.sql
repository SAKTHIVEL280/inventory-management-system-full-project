-- ════════════════════════════════════════════════════════════════════════════
-- ROLLBACK for 0020_multitenant_customization_options_tenant.sql
-- Date: June 25, 2026 | Task: DB-215
--
-- Restores the global unique and drops the per-tenant scoping. The company_id
-- column is left in place (dropping it would lose the tenant attribution); remove
-- it manually only if you are certain it is unused. Idempotent. Back up first.
-- ════════════════════════════════════════════════════════════════════════════

BEGIN;

DROP INDEX IF EXISTS ux_customization_options_company_scope;

-- Recreate the original global unique only if no cross-tenant duplicates exist.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT module, field_name, option_value
        FROM customization_options
        WHERE is_deleted = FALSE
        GROUP BY module, field_name, option_value
        HAVING COUNT(*) > 1
    ) THEN
        ALTER TABLE customization_options
            ADD CONSTRAINT uq_customization_option_scope
            UNIQUE (module, field_name, option_value);
    ELSE
        RAISE NOTICE 'Rollback: global unique NOT restored — cross-tenant duplicate option values exist.';
    END IF;
END $$;

COMMIT;
