-- DB-44: Inventory Count Difference Actions and Acceptance Audit
-- Date: April 11, 2026
-- Adds audit table for accepted inventory count differences with reason-code tracking.

BEGIN;

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

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

COMMIT;
