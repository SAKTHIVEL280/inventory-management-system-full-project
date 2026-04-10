-- DB-41: Company Country Field (Company Profile)
-- Adds optional country value for company address details.

BEGIN;

ALTER TABLE company
ADD COLUMN IF NOT EXISTS country VARCHAR(100);

COMMIT;
