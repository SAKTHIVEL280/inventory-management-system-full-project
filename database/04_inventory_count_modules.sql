-- DB-39: STO-006/STO-007 Inventory Count Modules
-- Date: April 8, 2026
-- Adds inventory count persistence tables for stock count and admin difference view.

BEGIN;

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

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

COMMIT;
