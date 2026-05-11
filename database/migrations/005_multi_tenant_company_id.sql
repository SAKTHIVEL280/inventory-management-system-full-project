-- Multi-Tenant Migration: Add company_id to all business tables
-- Date: May 9, 2026
-- Purpose: Enable multi-tenant isolation via company_id FK on all tables
-- Safety: Uses IF NOT EXISTS / ADD COLUMN IF NOT EXISTS for idempotency

BEGIN;

-- ═══════════════════════════════════════════════════════════════════
-- 1. MASTER TABLES
-- ═══════════════════════════════════════════════════════════════════

-- 1a. suppliers (currently missing company_id)
ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS company_id UUID REFERENCES company(id);
CREATE INDEX IF NOT EXISTS ix_suppliers_company_id ON suppliers (company_id);

-- ═══════════════════════════════════════════════════════════════════
-- 2. PURCHASE TABLES
-- ═══════════════════════════════════════════════════════════════════

-- 2a. purchase_orders
ALTER TABLE purchase_orders ADD COLUMN IF NOT EXISTS company_id UUID REFERENCES company(id);
CREATE INDEX IF NOT EXISTS ix_purchase_orders_company_id ON purchase_orders (company_id);

-- 2b. goods_receipt_notes
ALTER TABLE goods_receipt_notes ADD COLUMN IF NOT EXISTS company_id UUID REFERENCES company(id);
CREATE INDEX IF NOT EXISTS ix_goods_receipt_notes_company_id ON goods_receipt_notes (company_id);

-- 2c. purchase_returns
ALTER TABLE purchase_returns ADD COLUMN IF NOT EXISTS company_id UUID REFERENCES company(id);
CREATE INDEX IF NOT EXISTS ix_purchase_returns_company_id ON purchase_returns (company_id);

-- ═══════════════════════════════════════════════════════════════════
-- 3. SALES TABLES
-- ═══════════════════════════════════════════════════════════════════

-- 3a. quotations
ALTER TABLE quotations ADD COLUMN IF NOT EXISTS company_id UUID REFERENCES company(id);
CREATE INDEX IF NOT EXISTS ix_quotations_company_id ON quotations (company_id);

-- 3b. sales_orders
ALTER TABLE sales_orders ADD COLUMN IF NOT EXISTS company_id UUID REFERENCES company(id);
CREATE INDEX IF NOT EXISTS ix_sales_orders_company_id ON sales_orders (company_id);

-- 3c. sales_invoices
ALTER TABLE sales_invoices ADD COLUMN IF NOT EXISTS company_id UUID REFERENCES company(id);
CREATE INDEX IF NOT EXISTS ix_sales_invoices_company_id ON sales_invoices (company_id);

-- 3d. sales_returns
ALTER TABLE sales_returns ADD COLUMN IF NOT EXISTS company_id UUID REFERENCES company(id);
CREATE INDEX IF NOT EXISTS ix_sales_returns_company_id ON sales_returns (company_id);

-- ═══════════════════════════════════════════════════════════════════
-- 4. PAYMENT TABLES
-- ═══════════════════════════════════════════════════════════════════

-- 4a. payments
ALTER TABLE payments ADD COLUMN IF NOT EXISTS company_id UUID REFERENCES company(id);
CREATE INDEX IF NOT EXISTS ix_payments_company_id ON payments (company_id);

-- ═══════════════════════════════════════════════════════════════════
-- 5. INVENTORY TABLES
-- ═══════════════════════════════════════════════════════════════════

-- 5a. stock_ledger
ALTER TABLE stock_ledger ADD COLUMN IF NOT EXISTS company_id UUID REFERENCES company(id);
CREATE INDEX IF NOT EXISTS ix_stock_ledger_company_id ON stock_ledger (company_id);

-- 5b. inventory_counts
ALTER TABLE inventory_counts ADD COLUMN IF NOT EXISTS company_id UUID REFERENCES company(id);
CREATE INDEX IF NOT EXISTS ix_inventory_counts_company_id ON inventory_counts (company_id);

-- 5c. inventory_count_difference_audits
ALTER TABLE inventory_count_difference_audits ADD COLUMN IF NOT EXISTS company_id UUID REFERENCES company(id);
CREATE INDEX IF NOT EXISTS ix_inventory_count_diff_audits_company_id ON inventory_count_difference_audits (company_id);

-- ═══════════════════════════════════════════════════════════════════
-- 6. AUDIT & REPORTING TABLES
-- ═══════════════════════════════════════════════════════════════════

-- 6a. audit_logs
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS company_id UUID REFERENCES company(id);
CREATE INDEX IF NOT EXISTS ix_audit_logs_company_id ON audit_logs (company_id);

-- 6b. gst_report_audit_logs
ALTER TABLE gst_report_audit_logs ADD COLUMN IF NOT EXISTS company_id UUID REFERENCES company(id);
CREATE INDEX IF NOT EXISTS ix_gst_report_audit_logs_company_id ON gst_report_audit_logs (company_id);

-- ═══════════════════════════════════════════════════════════════════
-- 7. BACKFILL: Assign existing data to the first company
-- ═══════════════════════════════════════════════════════════════════

DO $$
DECLARE
    _default_company_id UUID;
BEGIN
    -- Get the first (and likely only) company
    SELECT id INTO _default_company_id FROM company LIMIT 1;

    IF _default_company_id IS NOT NULL THEN
        -- Master tables
        UPDATE suppliers SET company_id = _default_company_id WHERE company_id IS NULL;
        UPDATE product_categories SET company_id = _default_company_id WHERE company_id IS NULL;

        -- Purchase tables
        UPDATE purchase_orders SET company_id = _default_company_id WHERE company_id IS NULL;
        UPDATE goods_receipt_notes SET company_id = _default_company_id WHERE company_id IS NULL;
        UPDATE purchase_returns SET company_id = _default_company_id WHERE company_id IS NULL;

        -- Sales tables
        UPDATE quotations SET company_id = _default_company_id WHERE company_id IS NULL;
        UPDATE sales_orders SET company_id = _default_company_id WHERE company_id IS NULL;
        UPDATE sales_invoices SET company_id = _default_company_id WHERE company_id IS NULL;
        UPDATE sales_returns SET company_id = _default_company_id WHERE company_id IS NULL;

        -- Payment tables
        UPDATE payments SET company_id = _default_company_id WHERE company_id IS NULL;

        -- Inventory tables
        UPDATE stock_ledger SET company_id = _default_company_id WHERE company_id IS NULL;
        UPDATE inventory_counts SET company_id = _default_company_id WHERE company_id IS NULL;
        UPDATE inventory_count_difference_audits SET company_id = _default_company_id WHERE company_id IS NULL;

        -- Audit tables
        UPDATE audit_logs SET company_id = _default_company_id WHERE company_id IS NULL;
        UPDATE gst_report_audit_logs SET company_id = _default_company_id WHERE company_id IS NULL;

        -- Also backfill users, customers, products that might have NULL
        UPDATE users SET company_id = _default_company_id WHERE company_id IS NULL;
        UPDATE customers SET company_id = _default_company_id WHERE company_id IS NULL;
        UPDATE products SET company_id = _default_company_id WHERE company_id IS NULL;

        RAISE NOTICE 'Multi-tenant backfill complete for company_id: %', _default_company_id;
    ELSE
        RAISE NOTICE 'No company found — skipping backfill';
    END IF;
END $$;

-- ═══════════════════════════════════════════════════════════════════
-- 8. UPDATE MATERIALIZED VIEW to include company_id
-- ═══════════════════════════════════════════════════════════════════

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
  p.company_id,
  u.abbreviation AS uom,
  COALESCE(SUM(sl.quantity), 0) AS current_quantity
FROM products p
LEFT JOIN stock_ledger sl ON sl.product_id = p.id AND sl.is_deleted = FALSE
LEFT JOIN units_of_measure u ON u.id = p.uom_id
WHERE p.is_deleted = FALSE
GROUP BY p.id, p.product_code, p.name, p.hsn_code, p.gst_rate, p.minimum_stock,
         p.mrp, p.selling_price, p.company_id, u.abbreviation;

CREATE UNIQUE INDEX IF NOT EXISTS ux_current_stock_product_id ON current_stock (product_id);
CREATE INDEX IF NOT EXISTS ix_current_stock_company_id ON current_stock (company_id);

-- ═══════════════════════════════════════════════════════════════════
-- 9. ADD INDEX on product_categories.company_id (was missing)
-- ═══════════════════════════════════════════════════════════════════

CREATE INDEX IF NOT EXISTS ix_product_categories_company_id ON product_categories (company_id);

COMMIT;
