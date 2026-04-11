-- DB-42: Company Ambassador Logo Field (Company Profile)
-- Adds optional company ambassador logo path used for billing PDF background watermark rendering.

BEGIN;

ALTER TABLE company
ADD COLUMN IF NOT EXISTS ambassador_logo_url VARCHAR(500);

COMMIT;
