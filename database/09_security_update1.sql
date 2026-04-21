-- DB-45: Tenant Company Scope Columns
-- Date: April 21, 2026
-- Adds nullable company scope columns introduced in v4 for tenant-safe filtering.

BEGIN;

ALTER TABLE users
ADD COLUMN IF NOT EXISTS company_id UUID;

ALTER TABLE product_categories
ADD COLUMN IF NOT EXISTS company_id UUID;

ALTER TABLE products
ADD COLUMN IF NOT EXISTS company_id UUID;

ALTER TABLE customers
ADD COLUMN IF NOT EXISTS company_id UUID;

COMMIT;
