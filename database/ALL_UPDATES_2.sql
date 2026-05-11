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

ALTER TABLE company
ADD COLUMN IF NOT EXISTS ambassador_logo_url VARCHAR(500);

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
-- 3.1 Tenant Scoping: Company Assignment Backfill
-- ============================================================================

ALTER TABLE users
ADD COLUMN IF NOT EXISTS company_id UUID;

ALTER TABLE products
ADD COLUMN IF NOT EXISTS company_id UUID;

ALTER TABLE customers
ADD COLUMN IF NOT EXISTS company_id UUID;

ALTER TABLE suppliers
ADD COLUMN IF NOT EXISTS company_id UUID;

CREATE INDEX IF NOT EXISTS ix_users_company_id
ON users (company_id);

CREATE INDEX IF NOT EXISTS ix_products_company_id
ON products (company_id);

CREATE INDEX IF NOT EXISTS ix_customers_company_id
ON customers (company_id);

CREATE INDEX IF NOT EXISTS ix_suppliers_company_id
ON suppliers (company_id);

DO $$
BEGIN
	IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_users_company') THEN
		ALTER TABLE users
			ADD CONSTRAINT fk_users_company
			FOREIGN KEY (company_id) REFERENCES company(id);
	END IF;
END $$;

DO $$
BEGIN
	IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_products_company') THEN
		ALTER TABLE products
			ADD CONSTRAINT fk_products_company
			FOREIGN KEY (company_id) REFERENCES company(id);
	END IF;
END $$;

DO $$
BEGIN
	IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_customers_company') THEN
		ALTER TABLE customers
			ADD CONSTRAINT fk_customers_company
			FOREIGN KEY (company_id) REFERENCES company(id);
	END IF;
END $$;

DO $$
BEGIN
	IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_suppliers_company') THEN
		ALTER TABLE suppliers
			ADD CONSTRAINT fk_suppliers_company
			FOREIGN KEY (company_id) REFERENCES company(id);
	END IF;
END $$;

DO $$
DECLARE company_uuid UUID;
BEGIN
	SELECT id INTO company_uuid
	FROM company
	ORDER BY created_at ASC
	LIMIT 1;

	IF company_uuid IS NOT NULL THEN
		UPDATE users
		SET company_id = company_uuid
		WHERE company_id IS NULL;

		UPDATE products p
		SET company_id = COALESCE(
			(SELECT u.company_id FROM users u WHERE u.id = p.created_by),
			company_uuid
		)
		WHERE p.company_id IS NULL;

		UPDATE customers c
		SET company_id = COALESCE(
			(SELECT u.company_id FROM users u WHERE u.id = c.created_by),
			company_uuid
		)
		WHERE c.company_id IS NULL;

		UPDATE suppliers s
		SET company_id = COALESCE(
			(SELECT u.company_id FROM users u WHERE u.id = s.created_by),
			company_uuid
		)
		WHERE s.company_id IS NULL;
	END IF;
END $$;

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
-- 16. Inventory Count Difference Acceptance Audit (DB-44)
-- ============================================================================

CREATE TABLE IF NOT EXISTS inventory_count_difference_audits (
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

CREATE INDEX IF NOT EXISTS ix_inventory_count_difference_audits_count_id
ON inventory_count_difference_audits (inventory_count_id);

CREATE INDEX IF NOT EXISTS ix_inventory_count_difference_audits_accepted_at
ON inventory_count_difference_audits (accepted_at);

-- ============================================================================
-- 17. Customer Payment Terms Optional (DB-40)
-- ============================================================================

ALTER TABLE customers
ALTER COLUMN payment_terms_days DROP DEFAULT;

ALTER TABLE customers
ALTER COLUMN payment_terms_days DROP NOT NULL;

-- ============================================================================
-- 18. GST Report Audit Logs (DB-45)
-- ============================================================================

CREATE TABLE IF NOT EXISTS gst_report_audit_logs (
	id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
	user_id UUID REFERENCES users(id),
	action VARCHAR(120) NOT NULL,
	report_type VARCHAR(40) NOT NULL,
	start_date DATE NOT NULL,
	end_date DATE NOT NULL,
	frequency VARCHAR(20) NOT NULL,
	"timestamp" TIMESTAMPTZ NOT NULL DEFAULT NOW(),
	status VARCHAR(20) NOT NULL,
	details JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS ix_gst_report_audit_logs_timestamp
ON gst_report_audit_logs ("timestamp");

CREATE INDEX IF NOT EXISTS ix_gst_report_audit_logs_report_type
ON gst_report_audit_logs (report_type);

CREATE INDEX IF NOT EXISTS ix_gst_report_audit_logs_user_id
ON gst_report_audit_logs (user_id);

-- ============================================================================
-- 19. Action Logs With Rotation-Friendly Retention (DB-46)
-- ============================================================================

CREATE TABLE IF NOT EXISTS audit_logs (
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
	created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE audit_logs
ADD COLUMN IF NOT EXISTS username VARCHAR(255);

ALTER TABLE audit_logs
ADD COLUMN IF NOT EXISTS action_type VARCHAR(40);

ALTER TABLE audit_logs
ADD COLUMN IF NOT EXISTS module_name VARCHAR(80);

ALTER TABLE audit_logs
ADD COLUMN IF NOT EXISTS record_reference VARCHAR(255);

ALTER TABLE audit_logs
ADD COLUMN IF NOT EXISTS description TEXT;

ALTER TABLE audit_logs
ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

CREATE INDEX IF NOT EXISTS ix_audit_logs_created_at
ON audit_logs (created_at);

CREATE INDEX IF NOT EXISTS ix_audit_logs_user_id
ON audit_logs (user_id);

CREATE INDEX IF NOT EXISTS ix_audit_logs_module_name
ON audit_logs (module_name);

CREATE INDEX IF NOT EXISTS ix_audit_logs_action_type
ON audit_logs (action_type);

CREATE INDEX IF NOT EXISTS ix_audit_logs_record_reference
ON audit_logs (record_reference);

-- ============================================================================
-- 20. Role Cleanup For Access Control (DB-49)
-- ============================================================================

ALTER TABLE users
DROP CONSTRAINT IF EXISTS users_role_check;

ALTER TABLE users
ADD CONSTRAINT users_role_check
CHECK (role IN ('admin', 'inventory manager', 'general manager'));

UPDATE users
SET role = 'admin'
WHERE LOWER(role) IN ('doctor');

UPDATE users
SET role = 'general manager'
WHERE LOWER(role) IN ('accounts', 'billing', 'accounting', 'sales');

UPDATE users
SET role = 'inventory manager'
WHERE LOWER(role) IN ('inventory', 'inventory_manager');

-- ============================================================================
-- 21. Invoice Round-Off Backfill (DB-51)
-- ============================================================================

WITH rounded AS (
	SELECT
		id,
		COALESCE(total_taxable_amount, 0) + COALESCE(total_gst, 0) AS exact_total,
		COALESCE(amount_paid, 0) AS amount_paid,
		status,
		(FLOOR(((COALESCE(total_taxable_amount, 0) + COALESCE(total_gst, 0))::numeric) / 500) * 500)::int AS rounded_total
	FROM sales_invoices
	WHERE is_deleted = FALSE
)
UPDATE sales_invoices s
SET
	total_amount = r.rounded_total,
	amount_due = GREATEST(r.rounded_total - r.amount_paid, 0),
	status = CASE
		WHEN s.status IN ('draft', 'cancelled') THEN s.status
		WHEN r.amount_paid <= 0 THEN 'issued'
		WHEN r.amount_paid >= r.rounded_total THEN 'paid'
		ELSE 'partial_paid'
	END
FROM rounded r
WHERE s.id = r.id;

-- ============================================================================
-- 22. Return Delivery Notes (RDN) + Reason Options (DB-52)
-- ============================================================================

ALTER TABLE company
ADD COLUMN IF NOT EXISTS rdn_prefix VARCHAR(10) NOT NULL DEFAULT 'RDN';

ALTER TABLE company
ADD COLUMN IF NOT EXISTS rdn_counter INTEGER NOT NULL DEFAULT 1;

CREATE TABLE IF NOT EXISTS return_delivery_notes (
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

CREATE TABLE IF NOT EXISTS return_delivery_note_items (
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

INSERT INTO customization_options (module, field_name, option_value, display_label, sort_order, is_active)
VALUES
	('rdn', 'return_reason', 'wrong_supply', 'Wrong Supply', 1, TRUE),
	('rdn', 'return_reason', 'expiry_date_passed', 'Expiry Date Passed', 2, TRUE),
	('rdn', 'return_reason', 'non_sold', 'Non Sold', 3, TRUE),
	('rdn', 'return_reason', 'damaged', 'Damaged', 4, TRUE)
ON CONFLICT (module, field_name, option_value) DO NOTHING;

-- ============================================================================
COMMIT;
