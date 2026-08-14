-- IMS Database Schema (psql-run)
-- Source of truth: MASTER_SPEC.md -> "Database Schema — Complete"
--
-- IMPORTANT:
-- - Run this file using psql, as shown in database/README.md
-- - Requires: PostgreSQL 15+, pgcrypto (gen_random_uuid)

BEGIN;

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 5.1 Users
CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  full_name VARCHAR(150) NOT NULL,
  email VARCHAR(255) NOT NULL,  -- unique among active users only (partial index below)
  hashed_password VARCHAR(255) NOT NULL,
  role VARCHAR(20) NOT NULL CHECK (role IN ('admin','basic','accounts','inventory','management','hr')),
  permission_overrides JSON,
  force_password_change BOOLEAN DEFAULT FALSE,
  failed_login_attempts INTEGER NOT NULL DEFAULT 0,
  locked_until TIMESTAMPTZ,
  is_active BOOLEAN DEFAULT TRUE,
  is_super_admin BOOLEAN NOT NULL DEFAULT FALSE,
  is_deleted BOOLEAN DEFAULT FALSE,
  deleted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  company_id UUID,
  created_by UUID REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS ix_users_is_super_admin ON users (is_super_admin) WHERE is_super_admin = TRUE;
-- Email unique among active users only, so a deleted user's email can be reused.
CREATE UNIQUE INDEX IF NOT EXISTS ux_users_email_active ON users (email) WHERE is_deleted = false;

CREATE INDEX IF NOT EXISTS ix_users_email ON users (email);

-- 5.1.a GST Report Audit Logs
CREATE TABLE gst_report_audit_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id),
  action VARCHAR(120) NOT NULL,
  report_type VARCHAR(40) NOT NULL,
  start_date DATE NOT NULL,
  end_date DATE NOT NULL,
  frequency VARCHAR(20) NOT NULL,
  "timestamp" TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  status VARCHAR(20) NOT NULL,
  details JSONB NOT NULL DEFAULT '{}'::jsonb,
  company_id UUID
);

CREATE INDEX IF NOT EXISTS ix_gst_report_audit_logs_timestamp ON gst_report_audit_logs ("timestamp");
CREATE INDEX IF NOT EXISTS ix_gst_report_audit_logs_report_type ON gst_report_audit_logs (report_type);
CREATE INDEX IF NOT EXISTS ix_gst_report_audit_logs_user_id ON gst_report_audit_logs (user_id);
CREATE INDEX IF NOT EXISTS ix_gst_report_audit_logs_company_id ON gst_report_audit_logs (company_id);

-- 5.1.b System Action Logs
CREATE TABLE audit_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id),
  username VARCHAR(255),
  action VARCHAR(120) NOT NULL,
  action_type VARCHAR(40) NOT NULL DEFAULT 'UNKNOWN',
  module_name VARCHAR(80) NOT NULL DEFAULT 'system',
  resource_type VARCHAR(80),
  resource_id UUID,
  record_reference VARCHAR(255),
  description TEXT,
  status VARCHAR(20) NOT NULL,
  details JSONB NOT NULL DEFAULT '{}'::jsonb,
  ip_address VARCHAR(64),
  company_id UUID,
  version INTEGER,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_audit_logs_company_id ON audit_logs (company_id);
CREATE INDEX IF NOT EXISTS ix_audit_logs_created_at ON audit_logs (created_at);
CREATE INDEX IF NOT EXISTS ix_audit_logs_user_id ON audit_logs (user_id);
CREATE INDEX IF NOT EXISTS ix_audit_logs_module_name ON audit_logs (module_name);
CREATE INDEX IF NOT EXISTS ix_audit_logs_action_type ON audit_logs (action_type);
CREATE INDEX IF NOT EXISTS ix_audit_logs_record_reference ON audit_logs (record_reference);

-- 5.2 Company (single-row)
CREATE TABLE company (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name VARCHAR(255) NOT NULL,
  legal_name VARCHAR(255),
  gstin VARCHAR(15) UNIQUE,
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
  invoice_prefix VARCHAR(10) NOT NULL DEFAULT 'INV',
  invoice_counter INTEGER NOT NULL DEFAULT 1,
  po_prefix VARCHAR(10) NOT NULL DEFAULT 'PO',
  po_counter INTEGER NOT NULL DEFAULT 1,
  so_prefix VARCHAR(10) NOT NULL DEFAULT 'SO',
  so_counter INTEGER NOT NULL DEFAULT 1,
  qtn_prefix VARCHAR(10) NOT NULL DEFAULT 'QTN',
  qtn_counter INTEGER NOT NULL DEFAULT 1,
  pfi_prefix VARCHAR(10) NOT NULL DEFAULT 'PFI',
  pfi_counter INTEGER NOT NULL DEFAULT 1,
  grn_prefix VARCHAR(10) NOT NULL DEFAULT 'GRN',
  grn_counter INTEGER NOT NULL DEFAULT 1,
  rdn_prefix VARCHAR(10) NOT NULL DEFAULT 'RDN',
  rdn_counter INTEGER NOT NULL DEFAULT 1,
  svc_prefix VARCHAR(10) NOT NULL DEFAULT 'SINV',
  svc_counter INTEGER NOT NULL DEFAULT 1,
  -- Multi-tenant registry fields (M0 / DB-206). Each company row is one tenant.
  subscription_plan VARCHAR(20) NOT NULL DEFAULT 'PLATINUM'
    CHECK (subscription_plan IN ('FREE','SILVER','GOLD','PLATINUM')),
  account_status VARCHAR(20) NOT NULL DEFAULT 'active'
    CHECK (account_status IN ('active','inactive','suspended','trial')),
  payment_status VARCHAR(20) NOT NULL DEFAULT 'paid'
    CHECK (payment_status IN ('paid','pending','overdue')),
  onboarding_date DATE DEFAULT CURRENT_DATE,
  subscription_start_date DATE,
  subscription_expiry_date DATE,
  business_category VARCHAR(100),
  contact_person_name VARCHAR(255),
  contact_number VARCHAR(20),
  tenant_code VARCHAR(50),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_company_tenant_code
  ON company (tenant_code) WHERE tenant_code IS NOT NULL;

ALTER TABLE users
  ADD CONSTRAINT fk_users_company
  FOREIGN KEY (company_id) REFERENCES company(id);

-- Tenant membership (M7/DB-214): every user belongs to a tenant OR is a platform
-- Super Admin (super admins are tenant-less, so company_id stays NULLable).
ALTER TABLE users
  ADD CONSTRAINT chk_users_company_or_super
  CHECK (company_id IS NOT NULL OR is_super_admin = TRUE);

CREATE INDEX IF NOT EXISTS ix_users_company_id ON users (company_id);

-- 5.6 Units of Measure
CREATE TABLE units_of_measure (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name VARCHAR(50) NOT NULL,
  abbreviation VARCHAR(10) UNIQUE NOT NULL,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  deleted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Customization options (centralized configurable values)
CREATE TABLE customization_options (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  -- Multi-tenant (DB-215): each tenant owns its own dropdown option set.
  company_id UUID REFERENCES company(id),
  module VARCHAR(50) NOT NULL,
  field_name VARCHAR(50) NOT NULL,
  option_value VARCHAR(120) NOT NULL,
  display_label VARCHAR(150),
  sort_order INTEGER NOT NULL DEFAULT 0,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  deleted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  created_by UUID REFERENCES users(id)
);

-- Per-tenant uniqueness: the same option value may exist for different tenants.
CREATE UNIQUE INDEX IF NOT EXISTS ux_customization_options_company_scope
  ON customization_options (company_id, module, field_name, option_value);
CREATE INDEX IF NOT EXISTS ix_customization_options_company_id ON customization_options (company_id);
CREATE INDEX IF NOT EXISTS ix_customization_options_module ON customization_options (module);
CREATE INDEX IF NOT EXISTS ix_customization_options_field_name ON customization_options (field_name);

INSERT INTO customization_options (module, field_name, option_value, display_label, sort_order, is_active)
VALUES
  ('customer', 'currency', 'INR', 'INR', 1, TRUE),
  ('customer', 'currency', 'USD', 'USD', 2, TRUE),
  ('customer', 'currency', 'EUR', 'EUR', 3, TRUE),
  ('customer', 'currency', 'GBP', 'GBP', 4, TRUE),
  ('customer', 'country', 'India', 'India', 1, TRUE),
  ('customer', 'country', 'United States', 'United States', 2, TRUE),
  ('customer', 'country', 'United Arab Emirates', 'United Arab Emirates', 3, TRUE),
  ('customer', 'country', 'United Kingdom', 'United Kingdom', 4, TRUE),
  ('customer', 'country', 'Singapore', 'Singapore', 5, TRUE),
  ('customer', 'country', 'Australia', 'Australia', 6, TRUE),
  ('customer', 'state', 'Andhra Pradesh', 'Andhra Pradesh', 1, TRUE),
  ('customer', 'state', 'Arunachal Pradesh', 'Arunachal Pradesh', 2, TRUE),
  ('customer', 'state', 'Assam', 'Assam', 3, TRUE),
  ('customer', 'state', 'Bihar', 'Bihar', 4, TRUE),
  ('customer', 'state', 'Chhattisgarh', 'Chhattisgarh', 5, TRUE),
  ('customer', 'state', 'Goa', 'Goa', 6, TRUE),
  ('customer', 'state', 'Gujarat', 'Gujarat', 7, TRUE),
  ('customer', 'state', 'Haryana', 'Haryana', 8, TRUE),
  ('customer', 'state', 'Himachal Pradesh', 'Himachal Pradesh', 9, TRUE),
  ('customer', 'state', 'Jharkhand', 'Jharkhand', 10, TRUE),
  ('customer', 'state', 'Karnataka', 'Karnataka', 11, TRUE),
  ('customer', 'state', 'Kerala', 'Kerala', 12, TRUE),
  ('customer', 'state', 'Madhya Pradesh', 'Madhya Pradesh', 13, TRUE),
  ('customer', 'state', 'Maharashtra', 'Maharashtra', 14, TRUE),
  ('customer', 'state', 'Manipur', 'Manipur', 15, TRUE),
  ('customer', 'state', 'Meghalaya', 'Meghalaya', 16, TRUE),
  ('customer', 'state', 'Mizoram', 'Mizoram', 17, TRUE),
  ('customer', 'state', 'Nagaland', 'Nagaland', 18, TRUE),
  ('customer', 'state', 'Odisha', 'Odisha', 19, TRUE),
  ('customer', 'state', 'Punjab', 'Punjab', 20, TRUE),
  ('customer', 'state', 'Rajasthan', 'Rajasthan', 21, TRUE),
  ('customer', 'state', 'Sikkim', 'Sikkim', 22, TRUE),
  ('customer', 'state', 'Tamil Nadu', 'Tamil Nadu', 23, TRUE),
  ('customer', 'state', 'Telangana', 'Telangana', 24, TRUE),
  ('customer', 'state', 'Tripura', 'Tripura', 25, TRUE),
  ('customer', 'state', 'Uttar Pradesh', 'Uttar Pradesh', 26, TRUE),
  ('customer', 'state', 'Uttarakhand', 'Uttarakhand', 27, TRUE),
  ('customer', 'state', 'West Bengal', 'West Bengal', 28, TRUE),
  ('customer', 'state', 'Delhi', 'Delhi', 29, TRUE),
  ('rdn', 'return_reason', 'wrong_supply', 'Wrong Supply', 1, TRUE),
  ('rdn', 'return_reason', 'expiry_date_passed', 'Expiry Date Passed', 2, TRUE),
  ('rdn', 'return_reason', 'non_sold', 'Non Sold', 3, TRUE),
  ('rdn', 'return_reason', 'damaged', 'Damaged', 4, TRUE)
ON CONFLICT (company_id, module, field_name, option_value) DO NOTHING;

-- Enhancement 3: Stockist & Sales Manager master tables (managed in Customization)
CREATE TABLE stockists (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name VARCHAR(150) NOT NULL,
  city VARCHAR(120),
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  deleted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  company_id UUID REFERENCES company(id),
  created_by UUID REFERENCES users(id)
);
CREATE INDEX IF NOT EXISTS ix_stockists_name ON stockists (name);
CREATE INDEX IF NOT EXISTS ix_stockists_company_id ON stockists (company_id);

CREATE TABLE sales_managers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name VARCHAR(150) NOT NULL,
  employee_id VARCHAR(50),
  region VARCHAR(120),
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  deleted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  company_id UUID REFERENCES company(id),
  created_by UUID REFERENCES users(id)
);
CREATE INDEX IF NOT EXISTS ix_sales_managers_name ON sales_managers (name);
CREATE INDEX IF NOT EXISTS ix_sales_managers_company_id ON sales_managers (company_id);

-- 5.5 Product Categories
CREATE TABLE product_categories (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name VARCHAR(150) NOT NULL,
  description TEXT,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  deleted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  company_id UUID REFERENCES company(id),
  created_by UUID REFERENCES users(id)
);

-- Category name is unique per tenant (DB-213).
CREATE UNIQUE INDEX IF NOT EXISTS ux_product_categories_company_name
  ON product_categories (company_id, name);

-- 5.7 Products
CREATE TABLE products (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  product_code VARCHAR(30) NOT NULL,
  sku VARCHAR(50),
  name VARCHAR(255) NOT NULL,
  description TEXT,
  category_id UUID REFERENCES product_categories(id),
  uom_id UUID NOT NULL REFERENCES units_of_measure(id),
  alt_uom_id UUID REFERENCES units_of_measure(id),
  alt_uom_conversion NUMERIC(10,4),
  hsn_code VARCHAR(10) NOT NULL,
  gst_rate INTEGER NOT NULL CHECK (gst_rate IN (0,5,12,18,28)),
  purchase_price INTEGER NOT NULL DEFAULT 0,
  selling_price INTEGER NOT NULL DEFAULT 0,
  mrp INTEGER NOT NULL DEFAULT 0,
  minimum_stock INTEGER NOT NULL DEFAULT 0,
  safety_stock INTEGER NOT NULL DEFAULT 0,
  opening_stock INTEGER NOT NULL DEFAULT 0,
  status VARCHAR(30) NOT NULL DEFAULT 'active',
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  deleted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  company_id UUID REFERENCES company(id),
  created_by UUID REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS ix_products_company_id ON products (company_id);
CREATE UNIQUE INDEX IF NOT EXISTS ux_products_company_code ON products (company_id, product_code);

-- 5.3 Customers
CREATE TABLE customers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  customer_code VARCHAR(20) NOT NULL,
  company_name VARCHAR(255) NOT NULL,
  contact_person VARCHAR(150),
  email VARCHAR(255),
  phone VARCHAR(20) NOT NULL,
  alternate_phone VARCHAR(20),
  gstin VARCHAR(15),
  gstin_status VARCHAR(20) NOT NULL DEFAULT 'non-registered',
  pan VARCHAR(10),
  customer_type VARCHAR(20) NOT NULL DEFAULT 'regular' CHECK (customer_type IN ('regular','dealer','distributor','retail')),
  business_type VARCHAR(20) NOT NULL DEFAULT 'domestic' CHECK (business_type IN ('domestic','international')),
  company_director_name VARCHAR(255),
  company_director_contact VARCHAR(255),
  billing_address_line1 VARCHAR(255),
  billing_address_line2 VARCHAR(255),
  billing_city VARCHAR(100),
  billing_state VARCHAR(100),
  billing_state_code VARCHAR(5),
  billing_country VARCHAR(100),
  billing_pincode VARCHAR(10),
  shipping_address_line1 VARCHAR(255),
  shipping_address_line2 VARCHAR(255),
  shipping_city VARCHAR(100),
  shipping_state VARCHAR(100),
  shipping_state_code VARCHAR(5),
  shipping_country VARCHAR(100),
  shipping_pincode VARCHAR(10),
  same_as_billing BOOLEAN NOT NULL DEFAULT TRUE,
  credit_limit INTEGER NOT NULL DEFAULT 0,
  payment_terms_days INTEGER,
  opening_balance_type VARCHAR(2) NOT NULL DEFAULT 'dr' CHECK (opening_balance_type IN ('dr','cr')),
  currency_code VARCHAR(10) NOT NULL DEFAULT 'INR',
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  deleted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  company_id UUID REFERENCES company(id),
  created_by UUID REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS ix_customers_company_id ON customers (company_id);
CREATE UNIQUE INDEX IF NOT EXISTS ux_customers_company_code ON customers (company_id, customer_code);

-- 5.4 Suppliers
CREATE TABLE suppliers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  supplier_code VARCHAR(20) NOT NULL,
  company_name VARCHAR(255) NOT NULL,
  contact_person VARCHAR(150),
  email VARCHAR(255),
  phone VARCHAR(15) NOT NULL,
  alternate_phone VARCHAR(15),
  gstin_status VARCHAR(20) NOT NULL DEFAULT 'non-registered',
  gstin VARCHAR(15),
  pan VARCHAR(10),
  business_type VARCHAR(20) NOT NULL DEFAULT 'domestic' CHECK (business_type IN ('domestic','international')),
  company_director_name VARCHAR(255),
  company_director_contact VARCHAR(255),
  address_line1 VARCHAR(255),
  address_line2 VARCHAR(255),
  city VARCHAR(100),
  state VARCHAR(100),
  state_code VARCHAR(5),
  billing_country VARCHAR(100),
  pincode VARCHAR(10),
  place_of_supply VARCHAR(255),
  bank_name VARCHAR(150),
  bank_account_no VARCHAR(50),
  bank_ifsc VARCHAR(20),
  payment_terms_days INTEGER NOT NULL DEFAULT 30,
  currency_code VARCHAR(10) NOT NULL DEFAULT 'INR',
  opening_balance INTEGER NOT NULL DEFAULT 0,
  opening_balance_type VARCHAR(2) NOT NULL DEFAULT 'cr' CHECK (opening_balance_type IN ('dr','cr')),
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  deleted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  company_id UUID REFERENCES company(id),
  created_by UUID REFERENCES users(id)
);
CREATE INDEX IF NOT EXISTS ix_suppliers_company_id ON suppliers (company_id);
CREATE UNIQUE INDEX IF NOT EXISTS ux_suppliers_company_code ON suppliers (company_id, supplier_code);

-- Stock ledger and materialized view (needed by inventory pages)
CREATE TABLE stock_ledger (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  product_id UUID NOT NULL REFERENCES products(id),
  transaction_type VARCHAR(20) NOT NULL CHECK (transaction_type IN ('opening','purchase','sale','purchase_return','sale_return','adjustment')),
  reference_type VARCHAR(20),
  reference_id UUID,
  reference_number VARCHAR(50),
  quantity NUMERIC(12,4) NOT NULL,
  rate INTEGER NOT NULL,
  transaction_date DATE NOT NULL,
  notes TEXT,
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  deleted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  created_by UUID REFERENCES users(id)
);

DROP MATERIALIZED VIEW IF EXISTS current_stock;
CREATE MATERIALIZED VIEW current_stock AS
SELECT
  p.id AS product_id,
  p.product_code,
  p.name AS product_name,
  p.hsn_code,
  p.gst_rate,
  p.minimum_stock,
  p.mrp,
  p.selling_price,
  u.abbreviation AS uom,
  COALESCE(SUM(sl.quantity), 0) AS current_quantity
FROM products p
LEFT JOIN stock_ledger sl ON sl.product_id = p.id AND sl.is_deleted = FALSE
LEFT JOIN units_of_measure u ON u.id = p.uom_id
WHERE p.is_deleted = FALSE
GROUP BY p.id, p.product_code, p.name, p.hsn_code, p.gst_rate, p.minimum_stock, p.mrp, p.selling_price, u.abbreviation;

CREATE UNIQUE INDEX IF NOT EXISTS ux_current_stock_product_id ON current_stock (product_id);

-- Inventory Count modules (STO-006 / STO-007)
CREATE TABLE inventory_counts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  count_number VARCHAR(30) UNIQUE NOT NULL,
  count_date DATE NOT NULL,
  count_performed_by VARCHAR(150) NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'confirmed' CHECK (status IN ('draft','confirmed','cancelled')),
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  deleted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  created_by UUID REFERENCES users(id)
);

CREATE TABLE inventory_count_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  inventory_count_id UUID NOT NULL REFERENCES inventory_counts(id) ON DELETE CASCADE,
  serial_number INTEGER NOT NULL,
  product_id UUID NOT NULL REFERENCES products(id),
  product_description TEXT,
  quantity NUMERIC(12,4) NOT NULL,
  batch_no VARCHAR(100),
  manufacture_date DATE,
  expiry_date DATE,
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  deleted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_inventory_counts_count_number ON inventory_counts (count_number);
CREATE INDEX IF NOT EXISTS ix_inventory_count_items_count_id ON inventory_count_items (inventory_count_id);
CREATE INDEX IF NOT EXISTS ix_inventory_count_items_product_id ON inventory_count_items (product_id);

CREATE TABLE inventory_count_difference_audits (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  inventory_count_id UUID NOT NULL REFERENCES inventory_counts(id),
  inventory_count_item_id UUID NOT NULL REFERENCES inventory_count_items(id),
  count_number VARCHAR(30) NOT NULL,
  product_id UUID NOT NULL REFERENCES products(id),
  old_qty NUMERIC(12,4) NOT NULL,
  new_qty NUMERIC(12,4) NOT NULL,
  difference_qty NUMERIC(12,4) NOT NULL,
  reason_code VARCHAR(50) NOT NULL,
  reason_label VARCHAR(120) NOT NULL,
  accepted_by UUID NOT NULL REFERENCES users(id),
  accepted_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_inventory_count_difference_audits_count_id ON inventory_count_difference_audits (inventory_count_id);
CREATE INDEX IF NOT EXISTS ix_inventory_count_difference_audits_accepted_at ON inventory_count_difference_audits (accepted_at);

-- =========================
-- Purchase
-- =========================

CREATE TABLE purchase_orders (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  po_number VARCHAR(30) UNIQUE NOT NULL,
  supplier_id UUID NOT NULL REFERENCES suppliers(id),
  order_date DATE NOT NULL,
  expected_delivery_date DATE,
  status VARCHAR(20) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','sent','partial','received','cancelled')),
  currency_code VARCHAR(3) NOT NULL DEFAULT 'INR',
  exchange_rate NUMERIC(12,6) NOT NULL DEFAULT 1.0,
  under_delivery_tolerance NUMERIC(10,2) NOT NULL DEFAULT 0,
  over_delivery_tolerance NUMERIC(10,2) NOT NULL DEFAULT 0,
  subtotal INTEGER NOT NULL DEFAULT 0,
  total_discount INTEGER NOT NULL DEFAULT 0,
  total_taxable_amount INTEGER NOT NULL DEFAULT 0,
  total_cgst INTEGER NOT NULL DEFAULT 0,
  total_sgst INTEGER NOT NULL DEFAULT 0,
  total_igst INTEGER NOT NULL DEFAULT 0,
  total_gst INTEGER NOT NULL DEFAULT 0,
  total_amount INTEGER NOT NULL DEFAULT 0,
  notes TEXT,
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  deleted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  created_by UUID REFERENCES users(id)
);

CREATE TABLE purchase_order_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  purchase_order_id UUID NOT NULL REFERENCES purchase_orders(id) ON DELETE CASCADE,
  product_id UUID NOT NULL REFERENCES products(id),
  description VARCHAR(255),
  quantity NUMERIC(12,4) NOT NULL,
  unit_price INTEGER NOT NULL,
  discount_percent NUMERIC(5,2) NOT NULL DEFAULT 0,
  discount_amount INTEGER NOT NULL DEFAULT 0,
  taxable_amount INTEGER NOT NULL,
  gst_rate INTEGER NOT NULL,
  cgst_amount INTEGER NOT NULL DEFAULT 0,
  sgst_amount INTEGER NOT NULL DEFAULT 0,
  igst_amount INTEGER NOT NULL DEFAULT 0,
  total_amount INTEGER NOT NULL,
  received_quantity NUMERIC(12,4) NOT NULL DEFAULT 0,
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  deleted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE goods_receipt_notes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  grn_number VARCHAR(30) UNIQUE NOT NULL,
  purchase_order_id UUID REFERENCES purchase_orders(id),
  supplier_id UUID NOT NULL REFERENCES suppliers(id),
  supplier_invoice_number VARCHAR(50),
  supplier_invoice_date DATE,
  receipt_date DATE NOT NULL,
  payment_due_date DATE,
  under_delivery_tolerance NUMERIC(10,2) NOT NULL DEFAULT 0,
  over_delivery_tolerance NUMERIC(10,2) NOT NULL DEFAULT 0,
  status VARCHAR(20) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','confirmed','cancelled','reversed')),
  subtotal INTEGER NOT NULL DEFAULT 0,
  total_discount INTEGER NOT NULL DEFAULT 0,
  total_taxable_amount INTEGER NOT NULL DEFAULT 0,
  total_cgst INTEGER NOT NULL DEFAULT 0,
  total_sgst INTEGER NOT NULL DEFAULT 0,
  total_igst INTEGER NOT NULL DEFAULT 0,
  total_gst INTEGER NOT NULL DEFAULT 0,
  total_amount INTEGER NOT NULL DEFAULT 0,
  notes TEXT,
  reversal_reason TEXT,
  reversed_at TIMESTAMPTZ,
  reversed_by UUID REFERENCES users(id),
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  deleted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  created_by UUID REFERENCES users(id)
);

CREATE TABLE grn_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  grn_id UUID NOT NULL REFERENCES goods_receipt_notes(id) ON DELETE CASCADE,
  product_id UUID NOT NULL REFERENCES products(id),
  purchase_order_item_id UUID REFERENCES purchase_order_items(id),
  batch_no VARCHAR(100),
  manufacture_date DATE,
  expiry_date DATE,
  quantity NUMERIC(12,4) NOT NULL,
  free_quantity NUMERIC(12,4) NOT NULL DEFAULT 0,
  unit_price INTEGER NOT NULL,
  discount_percent NUMERIC(5,2) NOT NULL DEFAULT 0,
  discount_amount INTEGER NOT NULL DEFAULT 0,
  taxable_amount INTEGER NOT NULL,
  gst_rate INTEGER NOT NULL,
  cgst_amount INTEGER NOT NULL DEFAULT 0,
  sgst_amount INTEGER NOT NULL DEFAULT 0,
  igst_amount INTEGER NOT NULL DEFAULT 0,
  total_amount INTEGER NOT NULL,
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  deleted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE purchase_returns (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  return_number VARCHAR(30) UNIQUE NOT NULL,
  grn_id UUID NOT NULL REFERENCES goods_receipt_notes(id),
  supplier_id UUID NOT NULL REFERENCES suppliers(id),
  return_date DATE NOT NULL,
  reason TEXT NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','confirmed','cancelled')),
  subtotal INTEGER NOT NULL DEFAULT 0,
  total_gst INTEGER NOT NULL DEFAULT 0,
  total_amount INTEGER NOT NULL DEFAULT 0,
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  deleted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  created_by UUID REFERENCES users(id)
);

CREATE TABLE purchase_return_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  purchase_return_id UUID NOT NULL REFERENCES purchase_returns(id) ON DELETE CASCADE,
  product_id UUID NOT NULL REFERENCES products(id),
  grn_item_id UUID REFERENCES grn_items(id),
  quantity NUMERIC(12,4) NOT NULL,
  unit_price INTEGER NOT NULL,
  taxable_amount INTEGER NOT NULL,
  gst_rate INTEGER NOT NULL,
  cgst_amount INTEGER NOT NULL DEFAULT 0,
  sgst_amount INTEGER NOT NULL DEFAULT 0,
  igst_amount INTEGER NOT NULL DEFAULT 0,
  total_amount INTEGER NOT NULL,
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  deleted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- =========================
-- Sales
-- =========================

CREATE TABLE quotations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  quotation_number VARCHAR(30) UNIQUE NOT NULL,
  customer_id UUID NOT NULL REFERENCES customers(id),
  quotation_date DATE NOT NULL,
  valid_until DATE,
  status VARCHAR(20) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','sent','accepted','rejected','expired','converted')),
  sold_to_customer_id UUID REFERENCES customers(id),
  bill_to_customer_id UUID NOT NULL REFERENCES customers(id),
  ship_to_customer_id UUID REFERENCES customers(id),
  subtotal INTEGER NOT NULL DEFAULT 0,
  total_discount INTEGER NOT NULL DEFAULT 0,
  total_taxable_amount INTEGER NOT NULL DEFAULT 0,
  total_cgst INTEGER NOT NULL DEFAULT 0,
  total_sgst INTEGER NOT NULL DEFAULT 0,
  total_igst INTEGER NOT NULL DEFAULT 0,
  total_gst INTEGER NOT NULL DEFAULT 0,
  total_amount INTEGER NOT NULL DEFAULT 0,
  notes TEXT,
  terms_conditions TEXT,
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  deleted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  created_by UUID REFERENCES users(id)
);

CREATE TABLE quotation_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  quotation_id UUID NOT NULL REFERENCES quotations(id) ON DELETE CASCADE,
  product_id UUID NOT NULL REFERENCES products(id),
  description VARCHAR(255),
  quantity NUMERIC(12,4) NOT NULL,
  unit_price INTEGER NOT NULL,
  discount_percent NUMERIC(5,2) NOT NULL DEFAULT 0,
  discount_amount INTEGER NOT NULL DEFAULT 0,
  taxable_amount INTEGER NOT NULL,
  gst_rate INTEGER NOT NULL,
  cgst_amount INTEGER NOT NULL DEFAULT 0,
  sgst_amount INTEGER NOT NULL DEFAULT 0,
  igst_amount INTEGER NOT NULL DEFAULT 0,
  total_amount INTEGER NOT NULL,
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  deleted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Proforma Invoices (independent replica of quotations; PFI-00001 numbering)
CREATE TABLE proforma_invoices (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  proforma_number VARCHAR(30) UNIQUE NOT NULL,
  customer_id UUID NOT NULL REFERENCES customers(id),
  proforma_date DATE NOT NULL,
  valid_until DATE,
  status VARCHAR(20) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','sent','accepted','rejected','expired','converted')),
  sold_to_customer_id UUID REFERENCES customers(id),
  bill_to_customer_id UUID NOT NULL REFERENCES customers(id),
  ship_to_customer_id UUID REFERENCES customers(id),
  subtotal INTEGER NOT NULL DEFAULT 0,
  total_discount INTEGER NOT NULL DEFAULT 0,
  total_taxable_amount INTEGER NOT NULL DEFAULT 0,
  total_cgst INTEGER NOT NULL DEFAULT 0,
  total_sgst INTEGER NOT NULL DEFAULT 0,
  total_igst INTEGER NOT NULL DEFAULT 0,
  total_gst INTEGER NOT NULL DEFAULT 0,
  total_amount INTEGER NOT NULL DEFAULT 0,
  notes TEXT,
  terms_conditions TEXT,
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  deleted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  company_id UUID REFERENCES company(id),
  created_by UUID REFERENCES users(id)
);

CREATE TABLE proforma_invoice_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  proforma_invoice_id UUID NOT NULL REFERENCES proforma_invoices(id) ON DELETE CASCADE,
  product_id UUID NOT NULL REFERENCES products(id),
  description VARCHAR(255),
  quantity NUMERIC(12,4) NOT NULL,
  unit_price INTEGER NOT NULL,
  discount_percent NUMERIC(5,2) NOT NULL DEFAULT 0,
  discount_amount INTEGER NOT NULL DEFAULT 0,
  taxable_amount INTEGER NOT NULL,
  gst_rate INTEGER NOT NULL,
  cgst_amount INTEGER NOT NULL DEFAULT 0,
  sgst_amount INTEGER NOT NULL DEFAULT 0,
  igst_amount INTEGER NOT NULL DEFAULT 0,
  total_amount INTEGER NOT NULL,
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  deleted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_proforma_invoices_number ON proforma_invoices (proforma_number);
CREATE INDEX IF NOT EXISTS ix_proforma_invoices_customer_id ON proforma_invoices (customer_id);
CREATE INDEX IF NOT EXISTS ix_proforma_invoices_company_id ON proforma_invoices (company_id);
CREATE INDEX IF NOT EXISTS ix_proforma_invoice_items_proforma_id ON proforma_invoice_items (proforma_invoice_id);
CREATE INDEX IF NOT EXISTS ix_proforma_invoice_items_product_id ON proforma_invoice_items (product_id);

CREATE TABLE sales_orders (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  so_number VARCHAR(30) UNIQUE NOT NULL,
  quotation_id UUID REFERENCES quotations(id),
  customer_id UUID NOT NULL REFERENCES customers(id),
  order_date DATE NOT NULL,
  expected_delivery_date DATE,
  status VARCHAR(20) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','confirmed','partial','fulfilled','cancelled')),
  currency_code VARCHAR(3) NOT NULL DEFAULT 'INR',
  exchange_rate NUMERIC(12,6) NOT NULL DEFAULT 1.0,
  sold_to_customer_id UUID REFERENCES customers(id),
  bill_to_customer_id UUID NOT NULL REFERENCES customers(id),
  ship_to_customer_id UUID REFERENCES customers(id),
  subtotal INTEGER NOT NULL DEFAULT 0,
  total_discount INTEGER NOT NULL DEFAULT 0,
  total_taxable_amount INTEGER NOT NULL DEFAULT 0,
  total_cgst INTEGER NOT NULL DEFAULT 0,
  total_sgst INTEGER NOT NULL DEFAULT 0,
  total_igst INTEGER NOT NULL DEFAULT 0,
  total_gst INTEGER NOT NULL DEFAULT 0,
  total_amount INTEGER NOT NULL DEFAULT 0,
  notes TEXT,
  terms_conditions TEXT,
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  deleted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  created_by UUID REFERENCES users(id)
);

CREATE TABLE sales_order_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  sales_order_id UUID NOT NULL REFERENCES sales_orders(id) ON DELETE CASCADE,
  product_id UUID NOT NULL REFERENCES products(id),
  description VARCHAR(255),
  quantity NUMERIC(12,4) NOT NULL,
  unit_price INTEGER NOT NULL,
  discount_percent NUMERIC(5,2) NOT NULL DEFAULT 0,
  discount_amount INTEGER NOT NULL DEFAULT 0,
  taxable_amount INTEGER NOT NULL,
  gst_rate INTEGER NOT NULL,
  cgst_amount INTEGER NOT NULL DEFAULT 0,
  sgst_amount INTEGER NOT NULL DEFAULT 0,
  igst_amount INTEGER NOT NULL DEFAULT 0,
  total_amount INTEGER NOT NULL,
  fulfilled_quantity NUMERIC(12,4) NOT NULL DEFAULT 0,
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  deleted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE sales_invoices (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  invoice_number VARCHAR(30) UNIQUE NOT NULL,
  sales_order_id UUID REFERENCES sales_orders(id),
  quotation_id UUID REFERENCES quotations(id),
  customer_id UUID NOT NULL REFERENCES customers(id),
  invoice_date DATE NOT NULL,
  due_date DATE,
  status VARCHAR(20) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','issued','partial_paid','paid','returned','cancelled')),
  sold_to_customer_id UUID REFERENCES customers(id),
  bill_to_customer_id UUID NOT NULL REFERENCES customers(id),
  ship_to_customer_id UUID REFERENCES customers(id),
  supply_state VARCHAR(100),
  supply_state_code VARCHAR(5),
  invoice_type VARCHAR(30) NOT NULL DEFAULT 'within_state' CHECK (invoice_type IN ('export_invoice','within_state','other_states','union_territory')),
  import_export_code VARCHAR(50),
  is_igst BOOLEAN NOT NULL DEFAULT FALSE,
  subtotal INTEGER NOT NULL DEFAULT 0,
  total_discount INTEGER NOT NULL DEFAULT 0,
  total_taxable_amount INTEGER NOT NULL DEFAULT 0,
  total_cgst INTEGER NOT NULL DEFAULT 0,
  total_sgst INTEGER NOT NULL DEFAULT 0,
  total_igst INTEGER NOT NULL DEFAULT 0,
  total_gst INTEGER NOT NULL DEFAULT 0,
  total_amount INTEGER NOT NULL DEFAULT 0,
  amount_paid INTEGER NOT NULL DEFAULT 0,
  amount_due INTEGER NOT NULL DEFAULT 0,
  -- Multi-currency: transaction currency + exchange rate to base (INR), per invoice.
  -- Monetary columns are in currency_code minor units; base(INR) = amount*exchange_rate.
  currency_code VARCHAR(3) NOT NULL DEFAULT 'INR',
  exchange_rate NUMERIC(12,6) NOT NULL DEFAULT 1,
  -- Enhancement 3: internal operational fields (not printed on the PDF invoice)
  stockist_name VARCHAR(150),
  stockist_city VARCHAR(120),
  sales_manager_name VARCHAR(150),
  notes TEXT,
  terms_conditions TEXT,
  pdf_url VARCHAR(500),
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  deleted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  created_by UUID REFERENCES users(id)
);

-- Enhancement 3: filter support for Stockist / Sales Manager
CREATE INDEX IF NOT EXISTS ix_sales_invoices_stockist_name ON sales_invoices (stockist_name);
CREATE INDEX IF NOT EXISTS ix_sales_invoices_sales_manager_name ON sales_invoices (sales_manager_name);

CREATE TABLE sales_invoice_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  invoice_id UUID NOT NULL REFERENCES sales_invoices(id) ON DELETE CASCADE,
  product_id UUID NOT NULL REFERENCES products(id),
  description VARCHAR(255),
  order_unit VARCHAR(50),
  batch_no VARCHAR(50),
  manufacture_date DATE,
  expiry_date DATE,
  quantity NUMERIC(12,4) NOT NULL,
  free_quantity NUMERIC(12,4) NOT NULL DEFAULT 0,
  unit_price INTEGER NOT NULL,
  mrp INTEGER,
  discount_percent NUMERIC(5,2) NOT NULL DEFAULT 0,
  discount_amount INTEGER NOT NULL DEFAULT 0,
  taxable_amount INTEGER NOT NULL,
  gst_rate INTEGER NOT NULL,
  cgst_amount INTEGER NOT NULL DEFAULT 0,
  sgst_amount INTEGER NOT NULL DEFAULT 0,
  igst_amount INTEGER NOT NULL DEFAULT 0,
  total_amount INTEGER NOT NULL,
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  deleted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE sales_returns (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  return_number VARCHAR(30) UNIQUE NOT NULL,
  invoice_id UUID NOT NULL REFERENCES sales_invoices(id),
  customer_id UUID NOT NULL REFERENCES customers(id),
  return_date DATE NOT NULL,
  reason TEXT,
  status VARCHAR(20) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','confirmed','cancelled')),
  subtotal INTEGER NOT NULL DEFAULT 0,
  total_gst INTEGER NOT NULL DEFAULT 0,
  total_amount INTEGER NOT NULL DEFAULT 0,
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  deleted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  created_by UUID REFERENCES users(id)
);

CREATE TABLE sales_return_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  sales_return_id UUID NOT NULL REFERENCES sales_returns(id) ON DELETE CASCADE,
  product_id UUID NOT NULL REFERENCES products(id),
  invoice_item_id UUID REFERENCES sales_invoice_items(id),
  quantity NUMERIC(12,4) NOT NULL,
  unit_price INTEGER NOT NULL,
  taxable_amount INTEGER NOT NULL,
  gst_rate INTEGER NOT NULL,
  cgst_amount INTEGER NOT NULL DEFAULT 0,
  sgst_amount INTEGER NOT NULL DEFAULT 0,
  igst_amount INTEGER NOT NULL DEFAULT 0,
  total_amount INTEGER NOT NULL,
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  deleted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE return_delivery_notes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  rdn_number VARCHAR(30) UNIQUE NOT NULL,
  customer_id UUID NOT NULL REFERENCES customers(id),
  sales_invoice_id UUID NOT NULL REFERENCES sales_invoices(id),
  customer_delivery_number VARCHAR(50),
  customer_delivery_date DATE NOT NULL,
  receipt_date DATE NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','confirmed','cancelled')),
  notes TEXT,
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  deleted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  company_id UUID REFERENCES company(id),
  created_by UUID REFERENCES users(id),
  confirmed_by UUID REFERENCES users(id),
  confirmed_at TIMESTAMPTZ,
  cancelled_by UUID REFERENCES users(id),
  cancelled_at TIMESTAMPTZ
);

CREATE TABLE return_delivery_note_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  rdn_id UUID NOT NULL REFERENCES return_delivery_notes(id) ON DELETE CASCADE,
  product_id UUID NOT NULL REFERENCES products(id),
  invoice_item_id UUID REFERENCES sales_invoice_items(id),
  batch_no VARCHAR(100) NOT NULL,
  manufacture_date DATE NOT NULL,
  expiry_date DATE NOT NULL,
  invoice_quantity NUMERIC(12,4) NOT NULL,
  return_quantity NUMERIC(12,4) NOT NULL,
  mrp INTEGER,
  reason_code VARCHAR(120) NOT NULL,
  reason_label VARCHAR(150) NOT NULL,
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  deleted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_rdn_number ON return_delivery_notes (rdn_number);
CREATE INDEX IF NOT EXISTS ix_rdn_customer_id ON return_delivery_notes (customer_id);
CREATE INDEX IF NOT EXISTS ix_rdn_invoice_id ON return_delivery_notes (sales_invoice_id);
CREATE INDEX IF NOT EXISTS ix_rdn_items_rdn_id ON return_delivery_note_items (rdn_id);
CREATE INDEX IF NOT EXISTS ix_rdn_items_product_id ON return_delivery_note_items (product_id);

CREATE TABLE rdn_credit_notes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  credit_note_number VARCHAR(30) UNIQUE NOT NULL,
  rdn_id UUID NOT NULL REFERENCES return_delivery_notes(id) ON DELETE CASCADE,
  sales_invoice_id UUID NOT NULL REFERENCES sales_invoices(id),
  customer_id UUID NOT NULL REFERENCES customers(id),
  credit_note_date DATE NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'posted' CHECK (status IN ('draft','posted','cancelled')),
  subtotal INTEGER NOT NULL DEFAULT 0,
  total_discount INTEGER NOT NULL DEFAULT 0,
  total_taxable_amount INTEGER NOT NULL DEFAULT 0,
  total_cgst INTEGER NOT NULL DEFAULT 0,
  total_sgst INTEGER NOT NULL DEFAULT 0,
  total_igst INTEGER NOT NULL DEFAULT 0,
  total_gst INTEGER NOT NULL DEFAULT 0,
  total_amount INTEGER NOT NULL DEFAULT 0,
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  deleted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  company_id UUID REFERENCES company(id),
  created_by UUID REFERENCES users(id)
);

CREATE TABLE rdn_credit_note_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  credit_note_id UUID NOT NULL REFERENCES rdn_credit_notes(id) ON DELETE CASCADE,
  product_id UUID NOT NULL REFERENCES products(id),
  invoice_item_id UUID REFERENCES sales_invoice_items(id),
  return_quantity NUMERIC(12,4) NOT NULL,
  unit_price INTEGER NOT NULL,
  mrp INTEGER,
  discount_percent NUMERIC(5,2) NOT NULL DEFAULT 0,
  discount_amount INTEGER NOT NULL DEFAULT 0,
  taxable_amount INTEGER NOT NULL,
  gst_rate INTEGER NOT NULL,
  cgst_amount INTEGER NOT NULL DEFAULT 0,
  sgst_amount INTEGER NOT NULL DEFAULT 0,
  igst_amount INTEGER NOT NULL DEFAULT 0,
  total_amount INTEGER NOT NULL,
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  deleted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_rdn_credit_note_number ON rdn_credit_notes (credit_note_number);
CREATE INDEX IF NOT EXISTS ix_rdn_credit_notes_rdn_id ON rdn_credit_notes (rdn_id);
CREATE INDEX IF NOT EXISTS ix_rdn_credit_notes_invoice_id ON rdn_credit_notes (sales_invoice_id);
CREATE INDEX IF NOT EXISTS ix_rdn_credit_note_items_note_id ON rdn_credit_note_items (credit_note_id);
CREATE INDEX IF NOT EXISTS ix_rdn_credit_note_items_product_id ON rdn_credit_note_items (product_id);

-- =========================
-- Payments
-- =========================

CREATE TABLE payments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  payment_number VARCHAR(30) UNIQUE NOT NULL,
  payment_type VARCHAR(10) NOT NULL CHECK (payment_type IN ('receipt','payment')),
  party_type VARCHAR(10) NOT NULL CHECK (party_type IN ('customer','supplier')),
  customer_id UUID REFERENCES customers(id),
  supplier_id UUID REFERENCES suppliers(id),
  payment_date DATE NOT NULL,
  amount INTEGER NOT NULL,
  payment_mode VARCHAR(20) NOT NULL CHECK (payment_mode IN ('cash','bank_transfer','cheque','upi','card')),
  reference_number VARCHAR(100),
  cheque_date DATE,
  bank_name VARCHAR(150),
  notes TEXT,
  status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','cleared','bounced','cancelled')),
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  deleted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  created_by UUID REFERENCES users(id)
);

CREATE TABLE payment_allocations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  payment_id UUID NOT NULL REFERENCES payments(id),
  invoice_id UUID REFERENCES sales_invoices(id),
  purchase_grn_id UUID REFERENCES goods_receipt_notes(id),
  allocated_amount INTEGER NOT NULL,
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  deleted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Service Invoice module (M5 / DB-211). Available to all plans (FREE capped at 10/mo).
CREATE TABLE service_invoices (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  invoice_number VARCHAR(40) NOT NULL,
  invoice_date DATE NOT NULL,
  due_date DATE,
  customer_name VARCHAR(255) NOT NULL,
  customer_gstin VARCHAR(15),
  customer_email VARCHAR(255),
  customer_contact VARCHAR(20),
  billing_address TEXT,
  customer_state_code VARCHAR(5),
  supply_type VARCHAR(10) NOT NULL DEFAULT 'intra',
  subtotal INTEGER NOT NULL DEFAULT 0,
  total_discount INTEGER NOT NULL DEFAULT 0,
  total_taxable_amount INTEGER NOT NULL DEFAULT 0,
  total_cgst INTEGER NOT NULL DEFAULT 0,
  total_sgst INTEGER NOT NULL DEFAULT 0,
  total_igst INTEGER NOT NULL DEFAULT 0,
  total_gst INTEGER NOT NULL DEFAULT 0,
  grand_total INTEGER NOT NULL DEFAULT 0,
  amount_in_words VARCHAR(500),
  status VARCHAR(20) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','issued','paid','cancelled')),
  payment_status VARCHAR(20) NOT NULL DEFAULT 'unpaid' CHECK (payment_status IN ('unpaid','paid')),
  cancel_reason TEXT,
  notes TEXT,
  -- Mecandria subscription invoice raised by Super Admin to this tenant (§4.3).
  is_platform_invoice BOOLEAN NOT NULL DEFAULT FALSE,
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  deleted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  company_id UUID REFERENCES company(id),
  created_by UUID REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS ix_service_invoices_is_platform
  ON service_invoices (is_platform_invoice) WHERE is_platform_invoice = TRUE;

-- Platform (Mecandria) seller company profile (single row) — Super Admin managed.
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
INSERT INTO platform_company (name)
SELECT 'Mecandria' WHERE NOT EXISTS (SELECT 1 FROM platform_company);

CREATE TABLE service_invoice_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  service_invoice_id UUID NOT NULL REFERENCES service_invoices(id) ON DELETE CASCADE,
  sr_no INTEGER NOT NULL DEFAULT 1,
  item_name VARCHAR(255) NOT NULL,
  description TEXT,
  hsn_sac_code VARCHAR(20),
  quantity NUMERIC(12,4) NOT NULL DEFAULT 1,
  basic_price INTEGER NOT NULL DEFAULT 0,
  discount_percent NUMERIC(5,2) NOT NULL DEFAULT 0,
  discount_amount INTEGER NOT NULL DEFAULT 0,
  is_free BOOLEAN NOT NULL DEFAULT FALSE,
  taxable_amount INTEGER NOT NULL DEFAULT 0,
  gst_rate INTEGER NOT NULL DEFAULT 18,
  cgst_amount INTEGER NOT NULL DEFAULT 0,
  sgst_amount INTEGER NOT NULL DEFAULT 0,
  igst_amount INTEGER NOT NULL DEFAULT 0,
  total_amount INTEGER NOT NULL DEFAULT 0,
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_service_invoices_company_id ON service_invoices (company_id);
CREATE INDEX IF NOT EXISTS ix_service_invoices_invoice_date ON service_invoices (invoice_date);
CREATE INDEX IF NOT EXISTS ix_service_invoice_items_invoice_id ON service_invoice_items (service_invoice_id);
CREATE UNIQUE INDEX IF NOT EXISTS ux_service_invoices_company_number ON service_invoices (company_id, invoice_number);

-- ── Subscription Plan Configuration (DB-222) ─────────────────────────────────
-- DB-backed plan matrix (Super Admin → Plan Configuration). plan_service reads
-- these rows (cached) with a code fallback.
CREATE TABLE IF NOT EXISTS subscription_plans (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  plan_key VARCHAR(20) NOT NULL UNIQUE,
  name VARCHAR(80) NOT NULL,
  price_paise BIGINT NOT NULL DEFAULT 0,
  billing_period VARCHAR(20) NOT NULL DEFAULT 'monthly',
  user_limit INTEGER NOT NULL DEFAULT 1,
  modules JSONB NOT NULL DEFAULT '[]'::jsonb,
  features JSONB NOT NULL DEFAULT '[]'::jsonb,
  roles JSONB NOT NULL DEFAULT '[]'::jsonb,
  free_invoice_cap INTEGER,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  sort_order INTEGER NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_subscription_plans_plan_key ON subscription_plans (plan_key);

INSERT INTO subscription_plans
  (plan_key, name, price_paise, billing_period, user_limit, modules, features, roles, free_invoice_cap, is_active, sort_order)
VALUES
  ('FREE', 'Free', 0, 'none', 1,
   '["service_invoice"]'::jsonb, '["email_invoices"]'::jsonb, '["basic"]'::jsonb, 10, TRUE, 1),
  ('SILVER', 'Silver', 99900, 'monthly', 2,
   '["service_invoice","masters","purchase","sales","accounts","dashboard"]'::jsonb,
   '["email_invoices"]'::jsonb, '["admin","accounts"]'::jsonb, NULL, TRUE, 2),
  ('GOLD', 'Gold', 199900, 'monthly', 4,
   '["service_invoice","masters","purchase","sales","accounts","dashboard","inventory","reports","audit_logs"]'::jsonb,
   '["email_invoices","advanced_reports","gst_filing","audit_trail"]'::jsonb,
   '["admin","accounts","inventory","management"]'::jsonb, NULL, TRUE, 3),
  ('PLATINUM', 'Platinum', 499900, 'monthly', 6,
   '["service_invoice","masters","purchase","sales","accounts","dashboard","inventory","reports","audit_logs","export","pos","hr"]'::jsonb,
   '["email_invoices","advanced_reports","gst_filing","data_export","bulk_import","multi_currency","audit_trail","api_access"]'::jsonb,
   '["admin","accounts","inventory","management","hr"]'::jsonb, NULL, TRUE, 4)
ON CONFLICT (plan_key) DO NOTHING;

COMMIT;

