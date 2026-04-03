-- DATABASE UPDATES - Company Module Enhancements
-- Date: April 3, 2026
-- Features: Company Director Name, Director Contact, GSTIN Status Toggle

-- SINGLE UPDATE FILE STRATEGY:
-- Keep feature updates in one file and make every statement idempotent.
-- 1) If column exists -> skip
-- 2) If row exists -> skip (use ON CONFLICT DO NOTHING)

-- IMPORTANT:
-- This migration is NON-DESTRUCTIVE.
-- It only adds missing columns and does not delete/update existing rows.
-- Existing sample and production data remain unchanged.

BEGIN;

-- ============================================================================
-- ALTER TABLE STATEMENTS (Run on existing database)
-- ============================================================================

-- Add new columns to company table (PostgreSQL-safe)
ALTER TABLE company
ADD COLUMN IF NOT EXISTS company_director_name VARCHAR(255),
ADD COLUMN IF NOT EXISTS company_director_contact VARCHAR(255),
ADD COLUMN IF NOT EXISTS gstin_status VARCHAR(20) NOT NULL DEFAULT 'non-registered';

ALTER TABLE customers
ADD COLUMN IF NOT EXISTS company_director_name VARCHAR(255),
ADD COLUMN IF NOT EXISTS company_director_contact VARCHAR(255),
ADD COLUMN IF NOT EXISTS gstin_status VARCHAR(20) NOT NULL DEFAULT 'non-registered',
ADD COLUMN IF NOT EXISTS business_type VARCHAR(20) NOT NULL DEFAULT 'domestic',
ADD COLUMN IF NOT EXISTS billing_country VARCHAR(100),
ADD COLUMN IF NOT EXISTS shipping_country VARCHAR(100);

ALTER TABLE suppliers
ADD COLUMN IF NOT EXISTS company_director_name VARCHAR(255),
ADD COLUMN IF NOT EXISTS company_director_contact VARCHAR(255),
ADD COLUMN IF NOT EXISTS gstin_status VARCHAR(20) NOT NULL DEFAULT 'non-registered',
ADD COLUMN IF NOT EXISTS business_type VARCHAR(20) NOT NULL DEFAULT 'domestic',
ADD COLUMN IF NOT EXISTS billing_country VARCHAR(100);

-- Safe data backfill (non-destructive): only fills NULL values.
UPDATE company
SET gstin_status = 'non-registered'
WHERE gstin_status IS NULL;

UPDATE customers
SET gstin_status = 'non-registered'
WHERE gstin_status IS NULL;

UPDATE customers
SET business_type = 'domestic'
WHERE business_type IS NULL;

UPDATE suppliers
SET gstin_status = 'non-registered'
WHERE gstin_status IS NULL;

UPDATE suppliers
SET business_type = 'domestic'
WHERE business_type IS NULL;

-- Add column comments (PostgreSQL)
COMMENT ON COLUMN company.company_director_name IS 'Optional: Name of company director';
COMMENT ON COLUMN company.company_director_contact IS 'Optional: Contact info of company director';
COMMENT ON COLUMN company.gstin_status IS 'GSTIN registration status: registered or non-registered';
COMMENT ON COLUMN customers.company_director_name IS 'Optional: Name of customer company director';
COMMENT ON COLUMN customers.company_director_contact IS 'Optional: Contact of customer company director';
COMMENT ON COLUMN customers.gstin_status IS 'GSTIN registration status: registered or non-registered';
COMMENT ON COLUMN customers.business_type IS 'Business type: domestic or international';
COMMENT ON COLUMN customers.billing_country IS 'Billing address country';
COMMENT ON COLUMN customers.shipping_country IS 'Shipping address country';
COMMENT ON COLUMN suppliers.company_director_name IS 'Optional: Name of supplier company director';
COMMENT ON COLUMN suppliers.company_director_contact IS 'Optional: Contact of supplier company director';
COMMENT ON COLUMN suppliers.gstin_status IS 'GSTIN registration status: registered or non-registered';
COMMENT ON COLUMN suppliers.business_type IS 'Business type: domestic or international';
COMMENT ON COLUMN suppliers.billing_country IS 'Billing address country';

-- Safe row insert pattern for future updates (kept as reference).
-- Use this style when adding reference/master rows in this file.
-- Example:
-- INSERT INTO some_master_table (id, name)
-- VALUES ('00000000-0000-0000-0000-000000000001', 'Default')
-- ON CONFLICT (id) DO NOTHING;

COMMIT;

-- ============================================================================
-- FOR NEW DEPLOYMENTS: Complete schema with new columns
-- ============================================================================

/*
CREATE TABLE company (
    id CHAR(36) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    legal_name VARCHAR(255) NULL,
    gstin VARCHAR(15) UNIQUE NULL,
    gstin_status VARCHAR(20) NOT NULL DEFAULT 'non-registered',
    pan VARCHAR(10) NULL,
    
    address_line1 VARCHAR(255) NULL,
    address_line2 VARCHAR(255) NULL,
    city VARCHAR(100) NULL,
    state VARCHAR(100) NULL,
    state_code VARCHAR(5) NULL,
    pincode VARCHAR(10) NULL,
    
    phone VARCHAR(15) NULL,
    email VARCHAR(255) NULL,
    website VARCHAR(255) NULL,
    logo_url VARCHAR(500) NULL,
    
    company_director_name VARCHAR(255) NULL,
    company_director_contact VARCHAR(255) NULL,
    
    bank_name VARCHAR(150) NULL,
    bank_account_no VARCHAR(50) NULL,
    bank_ifsc VARCHAR(20) NULL,
    bank_branch VARCHAR(150) NULL,
    
    invoice_prefix VARCHAR(10) NOT NULL DEFAULT 'INV',
    invoice_counter INT NOT NULL DEFAULT 1,
    po_prefix VARCHAR(10) NOT NULL DEFAULT 'PO',
    po_counter INT NOT NULL DEFAULT 1,
    so_prefix VARCHAR(10) NOT NULL DEFAULT 'SO',
    so_counter INT NOT NULL DEFAULT 1,
    qtn_prefix VARCHAR(10) NOT NULL DEFAULT 'QTN',
    qtn_counter INT NOT NULL DEFAULT 1,
    grn_prefix VARCHAR(10) NOT NULL DEFAULT 'GRN',
    grn_counter INT NOT NULL DEFAULT 1,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    KEY idx_email (email),
    KEY idx_gstin (gstin)
);
*/

-- NOTE:
-- Do not add DROP TABLE / DROP COLUMN / TRUNCATE / DELETE statements in this file.
-- Keep this file add-only to preserve existing data.