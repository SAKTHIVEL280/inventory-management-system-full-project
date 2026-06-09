-- ============================================================================
-- MCN-BUG-004: Reverse GRN support
-- Adds a 'reversed' GRN status and reversal audit columns.
-- created_at / created_by already exist on goods_receipt_notes (no change needed).
-- Safe to run multiple times.
-- ============================================================================

-- 1) Allow 'reversed' status on goods_receipt_notes
ALTER TABLE goods_receipt_notes DROP CONSTRAINT IF EXISTS goods_receipt_notes_status_check;
ALTER TABLE goods_receipt_notes
    ADD CONSTRAINT goods_receipt_notes_status_check
    CHECK (status IN ('draft', 'confirmed', 'cancelled', 'reversed'));

-- 2) Reversal audit columns
ALTER TABLE goods_receipt_notes ADD COLUMN IF NOT EXISTS reversal_reason TEXT;
ALTER TABLE goods_receipt_notes ADD COLUMN IF NOT EXISTS reversed_at TIMESTAMPTZ;
ALTER TABLE goods_receipt_notes ADD COLUMN IF NOT EXISTS reversed_by UUID REFERENCES users(id);
