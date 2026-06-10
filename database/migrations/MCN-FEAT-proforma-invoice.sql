-- ============================================================================
-- MCN-FEAT-PROFORMA: Proforma Invoice module
-- ----------------------------------------------------------------------------
-- Independent replica of the Quotation module. Adds:
--   * company.pfi_prefix / company.pfi_counter  (separate PFI-00001 numbering)
--   * proforma_invoices            (mirror of quotations)
--   * proforma_invoice_items       (mirror of quotation_items)
-- The existing Quotation tables (quotations / quotation_items) are untouched.
--
-- Idempotent and safe to run on existing databases.
-- Mirrored in database/01_schema.sql and backend/run_migration.py.
-- ============================================================================

-- 1) Separate numbering sequence for Proforma Invoices
ALTER TABLE company ADD COLUMN IF NOT EXISTS pfi_prefix VARCHAR(10) NOT NULL DEFAULT 'PFI';
ALTER TABLE company ADD COLUMN IF NOT EXISTS pfi_counter INTEGER NOT NULL DEFAULT 1;

-- 2) Proforma Invoice header table
CREATE TABLE IF NOT EXISTS proforma_invoices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proforma_number VARCHAR(30) UNIQUE NOT NULL,
    customer_id UUID NOT NULL REFERENCES customers(id),
    proforma_date DATE NOT NULL,
    valid_until DATE,
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    sold_to_customer_id UUID REFERENCES customers(id),
    bill_to_customer_id UUID NOT NULL REFERENCES customers(id),
    ship_to_customer_id UUID REFERENCES customers(id),
    subtotal INTEGER NOT NULL DEFAULT 0,
    total_discount INTEGER NOT NULL DEFAULT 0,
    total_taxable_amount INTEGER NOT NULL DEFAULT 0,
    total_cgst INTEGER NOT NULL DEFAULT 0,
    total_sgst INTEGER NOT NULL DEFAULT 0,
    total_igst INTEGER NOT NULL DEFAULT 0,
    total_gst INTEGER NOT NULL DEFAULT 0,
    total_amount INTEGER NOT NULL DEFAULT 0,
    notes TEXT,
    terms_conditions TEXT,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    company_id UUID REFERENCES company(id),
    created_by UUID REFERENCES users(id)
);

-- 3) Proforma Invoice line items
CREATE TABLE IF NOT EXISTS proforma_invoice_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proforma_invoice_id UUID NOT NULL REFERENCES proforma_invoices(id) ON DELETE CASCADE,
    product_id UUID NOT NULL REFERENCES products(id),
    description VARCHAR(255),
    quantity NUMERIC(12,4) NOT NULL,
    unit_price INTEGER NOT NULL,
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

-- 4) Indexes
CREATE INDEX IF NOT EXISTS ix_proforma_invoices_number ON proforma_invoices (proforma_number);
CREATE INDEX IF NOT EXISTS ix_proforma_invoices_customer_id ON proforma_invoices (customer_id);
CREATE INDEX IF NOT EXISTS ix_proforma_invoices_company_id ON proforma_invoices (company_id);
CREATE INDEX IF NOT EXISTS ix_proforma_invoice_items_proforma_id ON proforma_invoice_items (proforma_invoice_id);
CREATE INDEX IF NOT EXISTS ix_proforma_invoice_items_product_id ON proforma_invoice_items (product_id);
