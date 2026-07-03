-- ════════════════════════════════════════════════════════════════════════════
-- Multi-Tenant Migration — MODULE M5: Service Invoice module
-- File: 0016_multitenant_m5_service_invoice.sql
-- Date: June 24, 2026
-- BRD: docs/requirements/Mecandria_ERP_MultiTenant_BRD_v1.md §8
-- Task: DB-211 (BE-222)
--
-- PURPOSE
--   GST-compliant Service Invoices, available to ALL plans (FREE capped at 10/mo,
--   enforced in the application). Adds a per-tenant service-invoice counter to
--   `company` and the service_invoices / service_invoice_items tables.
--
-- SAFETY: additive + idempotent. New tables/columns only; no existing data touched.
-- Money is INTEGER, quantities NUMERIC (consistent with the rest of the schema).
-- Document number is unique per tenant (company_id + invoice_number).
--
-- ROLLBACK: 0016_multitenant_m5_service_invoice_rollback.sql
-- ════════════════════════════════════════════════════════════════════════════

BEGIN;

-- Per-tenant service invoice numbering counter.
ALTER TABLE company ADD COLUMN IF NOT EXISTS svc_prefix VARCHAR(10) NOT NULL DEFAULT 'SINV';
ALTER TABLE company ADD COLUMN IF NOT EXISTS svc_counter INTEGER NOT NULL DEFAULT 1;

CREATE TABLE IF NOT EXISTS service_invoices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_number VARCHAR(40) NOT NULL,
    invoice_date DATE NOT NULL,
    due_date DATE,
    customer_name VARCHAR(255) NOT NULL,
    customer_gstin VARCHAR(15),
    customer_email VARCHAR(255),
    customer_contact VARCHAR(20),
    billing_address TEXT,
    customer_state_code VARCHAR(5),
    supply_type VARCHAR(10) NOT NULL DEFAULT 'intra',
    subtotal INTEGER NOT NULL DEFAULT 0,
    total_discount INTEGER NOT NULL DEFAULT 0,
    total_taxable_amount INTEGER NOT NULL DEFAULT 0,
    total_cgst INTEGER NOT NULL DEFAULT 0,
    total_sgst INTEGER NOT NULL DEFAULT 0,
    total_igst INTEGER NOT NULL DEFAULT 0,
    total_gst INTEGER NOT NULL DEFAULT 0,
    grand_total INTEGER NOT NULL DEFAULT 0,
    amount_in_words VARCHAR(500),
    status VARCHAR(20) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft','issued','paid','cancelled')),
    payment_status VARCHAR(20) NOT NULL DEFAULT 'unpaid'
        CHECK (payment_status IN ('unpaid','paid')),
    cancel_reason TEXT,
    notes TEXT,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    company_id UUID REFERENCES company(id),
    created_by UUID REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS service_invoice_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    service_invoice_id UUID NOT NULL REFERENCES service_invoices(id) ON DELETE CASCADE,
    sr_no INTEGER NOT NULL DEFAULT 1,
    item_name VARCHAR(255) NOT NULL,
    description TEXT,
    hsn_sac_code VARCHAR(20),
    quantity NUMERIC(12,4) NOT NULL DEFAULT 1,
    basic_price INTEGER NOT NULL DEFAULT 0,
    discount_percent NUMERIC(5,2) NOT NULL DEFAULT 0,
    discount_amount INTEGER NOT NULL DEFAULT 0,
    is_free BOOLEAN NOT NULL DEFAULT FALSE,
    taxable_amount INTEGER NOT NULL DEFAULT 0,
    gst_rate INTEGER NOT NULL DEFAULT 18,
    cgst_amount INTEGER NOT NULL DEFAULT 0,
    sgst_amount INTEGER NOT NULL DEFAULT 0,
    igst_amount INTEGER NOT NULL DEFAULT 0,
    total_amount INTEGER NOT NULL DEFAULT 0,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_service_invoices_company_id ON service_invoices (company_id);
CREATE INDEX IF NOT EXISTS ix_service_invoices_invoice_date ON service_invoices (invoice_date);
CREATE INDEX IF NOT EXISTS ix_service_invoice_items_invoice_id ON service_invoice_items (service_invoice_id);
-- Per-tenant unique document number.
CREATE UNIQUE INDEX IF NOT EXISTS ux_service_invoices_company_number
    ON service_invoices (company_id, invoice_number);

COMMIT;
