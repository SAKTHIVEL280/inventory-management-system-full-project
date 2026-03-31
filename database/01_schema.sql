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
  email VARCHAR(255) UNIQUE NOT NULL,
  hashed_password VARCHAR(255) NOT NULL,
  role VARCHAR(20) NOT NULL CHECK (role IN ('admin','accounting','sales','inventory')),
  permission_overrides JSON,
  force_password_change BOOLEAN DEFAULT FALSE,
  failed_login_attempts INTEGER NOT NULL DEFAULT 0,
  locked_until TIMESTAMPTZ,
  is_active BOOLEAN DEFAULT TRUE,
  is_deleted BOOLEAN DEFAULT FALSE,
  deleted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  created_by UUID REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS ix_users_email ON users (email);

-- 5.2 Company (single-row)
CREATE TABLE company (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name VARCHAR(255) NOT NULL,
  legal_name VARCHAR(255),
  gstin VARCHAR(15) UNIQUE,
  pan VARCHAR(10),
  address_line1 VARCHAR(255),
  address_line2 VARCHAR(255),
  city VARCHAR(100),
  state VARCHAR(100),
  state_code VARCHAR(5),
  pincode VARCHAR(10),
  phone VARCHAR(15),
  email VARCHAR(255),
  website VARCHAR(255),
  logo_url VARCHAR(500),
  bank_name VARCHAR(150),
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
  grn_prefix VARCHAR(10) NOT NULL DEFAULT 'GRN',
  grn_counter INTEGER NOT NULL DEFAULT 1,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

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

-- 5.5 Product Categories
CREATE TABLE product_categories (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name VARCHAR(150) UNIQUE NOT NULL,
  description TEXT,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  deleted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  created_by UUID REFERENCES users(id)
);

-- 5.7 Products
CREATE TABLE products (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  product_code VARCHAR(30) UNIQUE NOT NULL,
  sku VARCHAR(50) UNIQUE,
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
  created_by UUID REFERENCES users(id)
);

-- 5.3 Customers
CREATE TABLE customers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  customer_code VARCHAR(20) UNIQUE NOT NULL,
  company_name VARCHAR(255) NOT NULL,
  contact_person VARCHAR(150),
  email VARCHAR(255),
  phone VARCHAR(15) NOT NULL,
  alternate_phone VARCHAR(15),
  gstin VARCHAR(15),
  pan VARCHAR(10),
  customer_type VARCHAR(20) NOT NULL DEFAULT 'regular' CHECK (customer_type IN ('regular','dealer','distributor','retail')),
  billing_address_line1 VARCHAR(255),
  billing_address_line2 VARCHAR(255),
  billing_city VARCHAR(100),
  billing_state VARCHAR(100),
  billing_state_code VARCHAR(5),
  billing_pincode VARCHAR(10),
  shipping_address_line1 VARCHAR(255),
  shipping_address_line2 VARCHAR(255),
  shipping_city VARCHAR(100),
  shipping_state VARCHAR(100),
  shipping_state_code VARCHAR(5),
  shipping_pincode VARCHAR(10),
  same_as_billing BOOLEAN NOT NULL DEFAULT TRUE,
  credit_limit INTEGER NOT NULL DEFAULT 0,
  payment_terms_days INTEGER NOT NULL DEFAULT 30,
  opening_balance_type VARCHAR(2) NOT NULL DEFAULT 'dr' CHECK (opening_balance_type IN ('dr','cr')),
  currency_code VARCHAR(10) NOT NULL DEFAULT 'INR',
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  deleted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  created_by UUID REFERENCES users(id)
);

-- 5.4 Suppliers
CREATE TABLE suppliers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  supplier_code VARCHAR(20) UNIQUE NOT NULL,
  company_name VARCHAR(255) NOT NULL,
  contact_person VARCHAR(150),
  email VARCHAR(255),
  phone VARCHAR(15) NOT NULL,
  alternate_phone VARCHAR(15),
  gstin VARCHAR(15),
  pan VARCHAR(10),
  address_line1 VARCHAR(255),
  address_line2 VARCHAR(255),
  city VARCHAR(100),
  state VARCHAR(100),
  state_code VARCHAR(5),
  pincode VARCHAR(10),
  place_of_supply VARCHAR(255),
  bank_name VARCHAR(150),
  bank_account_no VARCHAR(50),
  bank_ifsc VARCHAR(20),
  payment_terms_days INTEGER NOT NULL DEFAULT 30,
  opening_balance INTEGER NOT NULL DEFAULT 0,
  opening_balance_type VARCHAR(2) NOT NULL DEFAULT 'cr' CHECK (opening_balance_type IN ('dr','cr')),
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  deleted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  created_by UUID REFERENCES users(id)
);

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
  status VARCHAR(20) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','confirmed','cancelled')),
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

CREATE TABLE grn_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  grn_id UUID NOT NULL REFERENCES goods_receipt_notes(id) ON DELETE CASCADE,
  product_id UUID NOT NULL REFERENCES products(id),
  purchase_order_item_id UUID REFERENCES purchase_order_items(id),
  batch_no VARCHAR(100),
  manufacture_date DATE,
  expiry_date DATE,
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
  status VARCHAR(20) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','issued','partial_paid','paid','cancelled')),
  sold_to_customer_id UUID REFERENCES customers(id),
  bill_to_customer_id UUID NOT NULL REFERENCES customers(id),
  ship_to_customer_id UUID REFERENCES customers(id),
  supply_state VARCHAR(100),
  supply_state_code VARCHAR(5),
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
  notes TEXT,
  terms_conditions TEXT,
  pdf_url VARCHAR(500),
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  deleted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  created_by UUID REFERENCES users(id)
);

CREATE TABLE sales_invoice_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  invoice_id UUID NOT NULL REFERENCES sales_invoices(id) ON DELETE CASCADE,
  product_id UUID NOT NULL REFERENCES products(id),
  description VARCHAR(255),
  quantity NUMERIC(12,4) NOT NULL,
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

COMMIT;

