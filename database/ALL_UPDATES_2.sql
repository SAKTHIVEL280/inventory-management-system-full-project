-- ALL DATABASE UPDATES - GRN Module Enhancements
-- Date: April 3, 2026
-- Features: Payment Due Date, Free Quantity Tracking

BEGIN;

-- ============================================================================
-- 1. Payment Due Date Column (GRN-005)
-- ============================================================================

-- Add payment_due_date column to goods_receipt_notes table
ALTER TABLE goods_receipt_notes
ADD COLUMN IF NOT EXISTS payment_due_date DATE;

COMMENT ON COLUMN goods_receipt_notes.payment_due_date IS 'Auto-calculated: Receipt Date + Supplier Payment Terms (Days)';

-- ============================================================================
-- 2. Free Quantity Column (GRN-009)
-- ============================================================================

-- Add free_quantity column to grn_items table
ALTER TABLE grn_items
ADD COLUMN IF NOT EXISTS free_quantity NUMERIC(12,4) NOT NULL DEFAULT 0;

COMMENT ON COLUMN grn_items.free_quantity IS 'Free quantity received (not charged)';

-- ============================================================================
COMMIT;
