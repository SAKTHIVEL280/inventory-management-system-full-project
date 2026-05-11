BEGIN;

-- Return Delivery Note (RDN) support
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

COMMIT;
