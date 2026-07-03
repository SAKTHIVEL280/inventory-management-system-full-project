-- ════════════════════════════════════════════════════════════════════════════
-- ROLLBACK for 0013_multitenant_m1_per_tenant_doc_numbers.sql  (Module M1)
-- Date: June 24, 2026 | Task: DB-207
--
-- Reverts the composite per-tenant unique indexes back to global single-column
-- UNIQUE constraints. SAFE ONLY while a single tenant exists — if two tenants
-- share a document number, re-adding the global UNIQUE will fail (by design).
--
-- WARNING: take a database backup before running any rollback.
-- ════════════════════════════════════════════════════════════════════════════

BEGIN;

DO $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN
        SELECT * FROM (VALUES
            ('purchase_orders',       'po_number'),
            ('goods_receipt_notes',   'grn_number'),
            ('purchase_returns',      'return_number'),
            ('quotations',            'quotation_number'),
            ('proforma_invoices',     'proforma_number'),
            ('sales_orders',          'so_number'),
            ('sales_invoices',        'invoice_number'),
            ('sales_returns',         'return_number'),
            ('return_delivery_notes', 'rdn_number'),
            ('rdn_credit_notes',      'credit_note_number'),
            ('payments',              'payment_number'),
            ('inventory_counts',      'count_number')
        ) AS t(tbl, col)
    LOOP
        EXECUTE format('DROP INDEX IF EXISTS ux_%s_company_number', r.tbl);
        -- Restore a global single-column UNIQUE (named like the PG default).
        BEGIN
            EXECUTE format(
                'ALTER TABLE %I ADD CONSTRAINT %s_%s_key UNIQUE (%I)',
                r.tbl, r.tbl, r.col, r.col
            );
        EXCEPTION WHEN duplicate_table OR duplicate_object THEN
            -- constraint already present; ignore
            NULL;
        END;
    END LOOP;
END $$;

COMMIT;
