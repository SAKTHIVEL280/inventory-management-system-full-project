-- DB-49: Update user roles to new access control set
-- Maps legacy roles to the new role names and updates the role check constraint.

BEGIN;

ALTER TABLE users
DROP CONSTRAINT IF EXISTS users_role_check;

ALTER TABLE users
ADD CONSTRAINT users_role_check
CHECK (role IN ('admin', 'inventory manager', 'general manager'));

UPDATE users
SET role = 'admin'
WHERE LOWER(role) IN ('doctor');

UPDATE users
SET role = 'general manager'
WHERE LOWER(role) IN ('accounts', 'billing', 'accounting', 'sales');

UPDATE users
SET role = 'inventory manager'
WHERE LOWER(role) IN ('inventory', 'inventory_manager');

COMMIT;
