BEGIN;

-- RDN Credit Notes
CREATE TABLE IF NOT EXISTS rdn_credit_notes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  credit_note_number VARCHAR(30) UNIQUE NOT NULL,
  rdn_id UUID NOT NULL REFERENCES return_delivery_notes(id) ON DELETE CASCADE,
  sales_invoice_id UUID NOT NULL REFERENCES sales_invoices(id),
  customer_id UUID NOT NULL REFERENCES customers(id),
  credit_note_date DATE NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'posted' CHECK (status IN ('draft','posted','cancelled')),
  subtotal INTEGER NOT NULL DEFAULT 0,
  total_discount INTEGER NOT NULL DEFAULT 0,
  total_taxable_amount INTEGER NOT NULL DEFAULT 0,
  total_cgst INTEGER NOT NULL DEFAULT 0,
  total_sgst INTEGER NOT NULL DEFAULT 0,
  total_igst INTEGER NOT NULL DEFAULT 0,
  total_gst INTEGER NOT NULL DEFAULT 0,
  total_amount INTEGER NOT NULL DEFAULT 0,
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  deleted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  company_id UUID REFERENCES company(id),
  created_by UUID REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS rdn_credit_note_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  credit_note_id UUID NOT NULL REFERENCES rdn_credit_notes(id) ON DELETE CASCADE,
  product_id UUID NOT NULL REFERENCES products(id),
  invoice_item_id UUID REFERENCES sales_invoice_items(id),
  return_quantity NUMERIC(12,4) NOT NULL,
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

CREATE INDEX IF NOT EXISTS ix_rdn_credit_note_number ON rdn_credit_notes (credit_note_number);
CREATE INDEX IF NOT EXISTS ix_rdn_credit_notes_rdn_id ON rdn_credit_notes (rdn_id);
CREATE INDEX IF NOT EXISTS ix_rdn_credit_notes_invoice_id ON rdn_credit_notes (sales_invoice_id);
CREATE INDEX IF NOT EXISTS ix_rdn_credit_note_items_note_id ON rdn_credit_note_items (credit_note_id);
CREATE INDEX IF NOT EXISTS ix_rdn_credit_note_items_product_id ON rdn_credit_note_items (product_id);

COMMIT;
