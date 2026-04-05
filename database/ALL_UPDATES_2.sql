-- ALL DATABASE UPDATES - Consolidated Compatibility Updates
-- Date: April 5, 2026
-- Features: Auth hardening, master/currency compatibility, GRN/Sales item extensions, SKU non-unique base unit

BEGIN;

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
COMMIT;
