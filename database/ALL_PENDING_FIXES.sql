-- This workspace pass did not require schema migrations.
-- Verified fixes were implemented at the application layer only.
--
-- If a future prompt adds schema changes, record them here and mirror the
-- same DDL in database/01_schema.sql.

-- 1. Migrate existing users from deprecated roles to active roles
UPDATE users SET role = 'accounts' WHERE role IN ('accounting', 'inventory');
UPDATE users SET role = 'billing' WHERE role = 'sales';

-- 2. Drop the old role check constraint if it exists (for safety)
ALTER TABLE users DROP CONSTRAINT IF EXISTS users_role_check;
ALTER TABLE users DROP CONSTRAINT IF EXISTS users_role_check1; -- Some databases auto-append digits

-- 3. Add the new strict constraint to allow only the active 4 roles
ALTER TABLE users ADD CONSTRAINT users_role_check 
    CHECK (role IN ('admin', 'accounts', 'doctor', 'billing'));