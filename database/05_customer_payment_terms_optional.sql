-- DB-40: Customer payment terms should be optional (no auto default 30)
-- Date: April 8, 2026

BEGIN;

ALTER TABLE customers
ALTER COLUMN payment_terms_days DROP DEFAULT;

ALTER TABLE customers
ALTER COLUMN payment_terms_days DROP NOT NULL;

COMMIT;
