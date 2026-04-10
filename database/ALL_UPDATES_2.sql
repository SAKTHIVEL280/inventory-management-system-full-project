-- ALL DATABASE UPDATES - Consolidated Compatibility Updates
-- Date: April 5, 2026
-- Features: Auth hardening, master/currency compatibility, GRN/Sales item extensions, SKU non-unique base unit

BEGIN;

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================================
-- 1. Auth Hardening Fields
-- ============================================================================

ALTER TABLE users
ADD COLUMN IF NOT EXISTS failed_login_attempts INTEGER NOT NULL DEFAULT 0;

ALTER TABLE users
ADD COLUMN IF NOT EXISTS locked_until TIMESTAMPTZ NULL;

-- ============================================================================
-- 2. Product Compatibility Fields
-- ============================================================================

ALTER TABLE products
ADD COLUMN IF NOT EXISTS safety_stock INTEGER NOT NULL DEFAULT 0;

ALTER TABLE products
ADD COLUMN IF NOT EXISTS status VARCHAR(30) NOT NULL DEFAULT 'active';

-- ============================================================================
-- 3. Supplier / Company / Customer Compatibility Fields
-- ============================================================================

ALTER TABLE suppliers
ADD COLUMN IF NOT EXISTS place_of_supply VARCHAR(255);

ALTER TABLE suppliers
ADD COLUMN IF NOT EXISTS company_director_name VARCHAR(255);

ALTER TABLE suppliers
ADD COLUMN IF NOT EXISTS company_director_contact VARCHAR(255);

ALTER TABLE suppliers
ADD COLUMN IF NOT EXISTS gstin_status VARCHAR(20) NOT NULL DEFAULT 'non-registered';

ALTER TABLE suppliers
ADD COLUMN IF NOT EXISTS business_type VARCHAR(20) NOT NULL DEFAULT 'domestic';

ALTER TABLE suppliers
ADD COLUMN IF NOT EXISTS billing_country VARCHAR(100);

ALTER TABLE company
ADD COLUMN IF NOT EXISTS gstin_status VARCHAR(20) NOT NULL DEFAULT 'non-registered';

ALTER TABLE company
ADD COLUMN IF NOT EXISTS company_director_name VARCHAR(255);

ALTER TABLE company
ADD COLUMN IF NOT EXISTS company_director_contact VARCHAR(255);

ALTER TABLE company
ADD COLUMN IF NOT EXISTS account_holder_name VARCHAR(255);

ALTER TABLE company
ADD COLUMN IF NOT EXISTS country VARCHAR(100);

ALTER TABLE customers
ADD COLUMN IF NOT EXISTS currency_code VARCHAR(10) NOT NULL DEFAULT 'INR';

ALTER TABLE customers
ADD COLUMN IF NOT EXISTS company_director_name VARCHAR(255);

ALTER TABLE customers
ADD COLUMN IF NOT EXISTS company_director_contact VARCHAR(255);

ALTER TABLE customers
ADD COLUMN IF NOT EXISTS gstin_status VARCHAR(20) NOT NULL DEFAULT 'non-registered';

ALTER TABLE customers
ADD COLUMN IF NOT EXISTS business_type VARCHAR(20) NOT NULL DEFAULT 'domestic';

ALTER TABLE customers
ADD COLUMN IF NOT EXISTS billing_country VARCHAR(100);

ALTER TABLE customers
ADD COLUMN IF NOT EXISTS shipping_country VARCHAR(100);

-- ============================================================================
-- 4. Currency Support Fields
-- ============================================================================

ALTER TABLE purchase_orders
ADD COLUMN IF NOT EXISTS currency_code VARCHAR(3) NOT NULL DEFAULT 'INR';

ALTER TABLE purchase_orders
ADD COLUMN IF NOT EXISTS exchange_rate NUMERIC(12, 6) NOT NULL DEFAULT 1.0;

ALTER TABLE purchase_orders
ADD COLUMN IF NOT EXISTS under_delivery_tolerance NUMERIC(10, 2) NOT NULL DEFAULT 0;

ALTER TABLE purchase_orders
ADD COLUMN IF NOT EXISTS over_delivery_tolerance NUMERIC(10, 2) NOT NULL DEFAULT 0;

ALTER TABLE sales_orders
ADD COLUMN IF NOT EXISTS currency_code VARCHAR(3) NOT NULL DEFAULT 'INR';

ALTER TABLE sales_orders
ADD COLUMN IF NOT EXISTS exchange_rate NUMERIC(12, 6) NOT NULL DEFAULT 1.0;

-- ============================================================================
-- 5. GRN Batch Tracking Fields
-- ============================================================================

ALTER TABLE grn_items
ADD COLUMN IF NOT EXISTS batch_no VARCHAR(100);

ALTER TABLE grn_items
ADD COLUMN IF NOT EXISTS manufacture_date DATE;

ALTER TABLE grn_items
ADD COLUMN IF NOT EXISTS expiry_date DATE;

-- ============================================================================
-- 6. Payment Due Date Column (GRN-005)
-- ============================================================================

-- Add payment_due_date column to goods_receipt_notes table
ALTER TABLE goods_receipt_notes
ADD COLUMN IF NOT EXISTS payment_due_date DATE;

ALTER TABLE goods_receipt_notes
ADD COLUMN IF NOT EXISTS under_delivery_tolerance NUMERIC(10, 2) NOT NULL DEFAULT 0;

ALTER TABLE goods_receipt_notes
ADD COLUMN IF NOT EXISTS over_delivery_tolerance NUMERIC(10, 2) NOT NULL DEFAULT 0;

COMMENT ON COLUMN goods_receipt_notes.payment_due_date IS 'Auto-calculated: Receipt Date + Supplier Payment Terms (Days)';

-- ============================================================================
-- 7. Free Quantity Column (GRN-009)
-- ============================================================================

-- Add free_quantity column to grn_items table
ALTER TABLE grn_items
ADD COLUMN IF NOT EXISTS free_quantity NUMERIC(12,4) NOT NULL DEFAULT 0;

COMMENT ON COLUMN grn_items.free_quantity IS 'Free quantity received (not charged)';

-- ============================================================================
-- 8. Sales Invoice Item Extended Fields
-- ============================================================================

ALTER TABLE sales_invoice_items
ADD COLUMN IF NOT EXISTS order_unit VARCHAR(50);

ALTER TABLE sales_invoice_items
ADD COLUMN IF NOT EXISTS batch_no VARCHAR(50);

ALTER TABLE sales_invoice_items
ADD COLUMN IF NOT EXISTS manufacture_date DATE;

ALTER TABLE sales_invoice_items
ADD COLUMN IF NOT EXISTS expiry_date DATE;

ALTER TABLE sales_invoice_items
ADD COLUMN IF NOT EXISTS free_quantity NUMERIC(12,4) NOT NULL DEFAULT 0;

COMMENT ON COLUMN sales_invoice_items.free_quantity IS 'Free quantity sold (not billed)';

-- ============================================================================
-- 9. Product Base Unit (SKU) Should Not Be Unique
-- ============================================================================

ALTER TABLE products
DROP CONSTRAINT IF EXISTS products_sku_key;

DO $$
DECLARE idx_name TEXT;
BEGIN
	FOR idx_name IN
		SELECT i.relname
		FROM pg_class t
		JOIN pg_index x ON t.oid = x.indrelid
		JOIN pg_class i ON i.oid = x.indexrelid
		JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(x.indkey)
		WHERE t.relname = 'products'
		  AND x.indisunique = TRUE
		  AND a.attname = 'sku'
	LOOP
		EXECUTE format('DROP INDEX IF EXISTS %I', idx_name);
	END LOOP;
END $$;

-- ============================================================================
-- 10. Customer Country/Currency/State Customization Options
-- ============================================================================

CREATE TABLE IF NOT EXISTS customization_options (
	id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
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

CREATE UNIQUE INDEX IF NOT EXISTS uq_customization_option_scope
ON customization_options (module, field_name, option_value);

CREATE INDEX IF NOT EXISTS ix_customization_options_module
ON customization_options (module);

CREATE INDEX IF NOT EXISTS ix_customization_options_field_name
ON customization_options (field_name);

ALTER TABLE customization_options
ALTER COLUMN id SET DEFAULT gen_random_uuid();

ALTER TABLE customization_options
ALTER COLUMN sort_order SET DEFAULT 0;

ALTER TABLE customization_options
ALTER COLUMN is_active SET DEFAULT TRUE;

ALTER TABLE customization_options
ALTER COLUMN is_deleted SET DEFAULT FALSE;

ALTER TABLE customization_options
ALTER COLUMN created_at SET DEFAULT NOW();

ALTER TABLE customization_options
ALTER COLUMN updated_at SET DEFAULT NOW();

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
	('customer', 'state', 'Delhi', 'Delhi', 29, TRUE)
ON CONFLICT (module, field_name, option_value) DO NOTHING;

-- ============================================================================
-- 11. Customer International Phone Length Support
-- ============================================================================

ALTER TABLE customers
ALTER COLUMN phone TYPE VARCHAR(20);

ALTER TABLE customers
ALTER COLUMN alternate_phone TYPE VARCHAR(20);

-- ============================================================================
-- 12. Supplier Currency Field Support
-- ============================================================================

ALTER TABLE suppliers
ADD COLUMN IF NOT EXISTS currency_code VARCHAR(10) NOT NULL DEFAULT 'INR';

-- ============================================================================
-- 13. Sales Invoice Type Classification (SAL-029)
-- ============================================================================

ALTER TABLE sales_invoices
ADD COLUMN IF NOT EXISTS invoice_type VARCHAR(30) NOT NULL DEFAULT 'within_state';

-- ============================================================================
-- 14. Export Invoice Enhancements (SAL-030)
-- ============================================================================

ALTER TABLE sales_invoices
ADD COLUMN IF NOT EXISTS import_export_code VARCHAR(50);

ALTER TABLE company
ADD COLUMN IF NOT EXISTS import_export_number VARCHAR(50);

-- ============================================================================
-- 15. Inventory Count Modules (STO-006 / STO-007)
-- ============================================================================

CREATE TABLE IF NOT EXISTS inventory_counts (
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

CREATE TABLE IF NOT EXISTS inventory_count_items (
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

CREATE INDEX IF NOT EXISTS ix_inventory_counts_count_number
ON inventory_counts (count_number);

CREATE INDEX IF NOT EXISTS ix_inventory_count_items_count_id
ON inventory_count_items (inventory_count_id);

CREATE INDEX IF NOT EXISTS ix_inventory_count_items_product_id
ON inventory_count_items (product_id);

-- ============================================================================
-- 16. Customer Payment Terms Optional (DB-40)
-- ============================================================================

ALTER TABLE customers
ALTER COLUMN payment_terms_days DROP DEFAULT;

ALTER TABLE customers
ALTER COLUMN payment_terms_days DROP NOT NULL;

-- ============================================================================
COMMIT;
