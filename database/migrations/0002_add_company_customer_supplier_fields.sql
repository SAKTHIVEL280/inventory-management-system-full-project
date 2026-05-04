-- Migration: add missing company/customer/supplier fields used by models
-- Safe to run multiple times (idempotent)

BEGIN;

-- Company fields
ALTER TABLE company ADD COLUMN IF NOT EXISTS gstin_status VARCHAR(20) NOT NULL DEFAULT 'non-registered';
ALTER TABLE company ADD COLUMN IF NOT EXISTS company_director_name VARCHAR(255);
ALTER TABLE company ADD COLUMN IF NOT EXISTS company_director_contact VARCHAR(255);

-- Customer fields
ALTER TABLE customers ADD COLUMN IF NOT EXISTS gstin_status VARCHAR(20) NOT NULL DEFAULT 'non-registered';
ALTER TABLE customers ADD COLUMN IF NOT EXISTS business_type VARCHAR(20) NOT NULL DEFAULT 'domestic';
ALTER TABLE customers ADD COLUMN IF NOT EXISTS company_director_name VARCHAR(255);
ALTER TABLE customers ADD COLUMN IF NOT EXISTS company_director_contact VARCHAR(255);
ALTER TABLE customers ADD COLUMN IF NOT EXISTS billing_country VARCHAR(100);
ALTER TABLE customers ADD COLUMN IF NOT EXISTS shipping_country VARCHAR(100);

-- Supplier fields
ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS gstin_status VARCHAR(20) NOT NULL DEFAULT 'non-registered';
ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS business_type VARCHAR(20) NOT NULL DEFAULT 'domestic';
ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS company_director_name VARCHAR(255);
ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS company_director_contact VARCHAR(255);
ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS billing_country VARCHAR(100);

COMMIT;
