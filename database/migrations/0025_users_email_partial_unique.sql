-- ════════════════════════════════════════════════════════════════════════════
-- Users email: partial unique (active users only)
-- File: 0025_users_email_partial_unique.sql
-- Date: June 27, 2026
-- Task: DB-221 (BE-247)
--
-- PURPOSE
--   Email must be globally unique across tenants, BUT a permanently/soft-deleted
--   user must not block re-using their email for a new account. Replace the global
--   UNIQUE(email) constraint with a PARTIAL unique index that applies only to
--   non-deleted users.
--
-- SAFETY: idempotent. If duplicate ACTIVE emails somehow exist the partial index
--   creation would fail — resolve those first (there should be none).
-- ROLLBACK: 0025_users_email_partial_unique_rollback.sql
-- ════════════════════════════════════════════════════════════════════════════

BEGIN;

-- Drop the global UNIQUE(email) constraint (auto-named users_email_key), by shape.
DO $$
DECLARE con TEXT;
BEGIN
    FOR con IN
        SELECT tc.constraint_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
        WHERE tc.table_schema = current_schema()
          AND tc.table_name = 'users' AND tc.constraint_type = 'UNIQUE'
        GROUP BY tc.constraint_name
        HAVING COUNT(*) = 1 AND MAX(kcu.column_name) = 'email'
    LOOP
        EXECUTE format('ALTER TABLE users DROP CONSTRAINT %I', con);
    END LOOP;
END $$;

-- Drop any standalone unique index form too.
DROP INDEX IF EXISTS users_email_key;

-- Partial unique: only non-deleted users must have a unique email.
CREATE UNIQUE INDEX IF NOT EXISTS ux_users_email_active
    ON users (email) WHERE is_deleted = false;

COMMIT;
