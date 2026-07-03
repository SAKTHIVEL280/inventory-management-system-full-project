-- ROLLBACK for 0025_users_email_partial_unique.sql (DB-221)
-- Restores the global UNIQUE(email) if no cross-tenant/deleted duplicates exist.
BEGIN;
DROP INDEX IF EXISTS ux_users_email_active;
DO $$
BEGIN
    IF NOT EXISTS (SELECT email FROM users GROUP BY email HAVING COUNT(*) > 1) THEN
        ALTER TABLE users ADD CONSTRAINT users_email_key UNIQUE (email);
    ELSE
        RAISE NOTICE 'Global UNIQUE(email) not restored — duplicate emails exist.';
    END IF;
END $$;
COMMIT;
