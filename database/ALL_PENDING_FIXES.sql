-- This workspace pass did not require schema migrations.
-- Verified fixes were implemented at the application layer only.
--
-- If a future prompt adds schema changes, record them here and mirror the
-- same DDL in database/01_schema.sql.

-- NOTE: The legacy role purge migrations (admin, accounts, doctor, billing)
-- have been successfully merged into backend/run_migration.py and applied
-- to the database.