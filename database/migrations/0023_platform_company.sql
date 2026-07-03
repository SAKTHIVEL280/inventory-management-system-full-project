-- ════════════════════════════════════════════════════════════════════════════
-- Platform (Mecandria) seller company profile
-- File: 0023_platform_company.sql
-- Date: June 26, 2026
-- Task: DB-219 (BE-241 / FE-234)
--
-- PURPOSE
--   Store the application owner's own seller company details in the DB (replacing
--   env-var config) so the Super Admin can manage them and they are used as the
--   seller on platform service invoices / dashboards / PDFs. Single-row table.
--
-- SAFETY: idempotent (CREATE TABLE IF NOT EXISTS + seed one row if empty).
-- ROLLBACK: 0023_platform_company_rollback.sql
-- ════════════════════════════════════════════════════════════════════════════

BEGIN;

CREATE TABLE IF NOT EXISTS platform_company (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name VARCHAR(255) NOT NULL DEFAULT 'Mecandria',
  legal_name VARCHAR(255),
  gstin VARCHAR(15),
  gstin_status VARCHAR(20) NOT NULL DEFAULT 'non-registered',
  pan VARCHAR(10),
  import_export_number VARCHAR(50),
  company_director_name VARCHAR(255),
  company_director_contact VARCHAR(255),
  address_line1 VARCHAR(255),
  address_line2 VARCHAR(255),
  city VARCHAR(100),
  state VARCHAR(100),
  country VARCHAR(100),
  state_code VARCHAR(5),
  pincode VARCHAR(10),
  phone VARCHAR(15),
  email VARCHAR(255),
  website VARCHAR(255),
  logo_url VARCHAR(500),
  ambassador_logo_url VARCHAR(500),
  bank_name VARCHAR(150),
  account_holder_name VARCHAR(255),
  bank_account_no VARCHAR(50),
  bank_ifsc VARCHAR(20),
  bank_branch VARCHAR(150),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Seed a single empty row if none exists (the app treats row 1 as the profile).
INSERT INTO platform_company (name)
SELECT 'Mecandria'
WHERE NOT EXISTS (SELECT 1 FROM platform_company);

COMMIT;
