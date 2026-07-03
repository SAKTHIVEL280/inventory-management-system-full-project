-- ════════════════════════════════════════════════════════════════════════════
-- Multi-Tenant Migration — Platform (Super Admin → tenant) service invoices
-- File: 0021_multitenant_platform_service_invoice.sql
-- Date: June 25, 2026
-- BRD: docs/requirements/Mecandria_ERP_MultiTenant_BRD_v1.md §4.3 / §4.1 / §8
-- Task: DB-217 (BE-236)
--
-- PURPOSE
--   Support "Raise Service Invoice" (§4.3): Mecandria's own subscription invoices
--   raised by the Super Admin to an ERP customer. These reuse the service_invoices
--   table (company_id = the billed tenant) but are flagged so they are:
--     * excluded from the tenant's own service-invoice list and FREE monthly cap,
--     * counted as platform subscription revenue on the Super Admin dashboard.
--
-- SAFETY: idempotent; additive (single boolean column, default FALSE). Existing
--   rows become non-platform (tenant) invoices — correct.
-- ROLLBACK: 0021_multitenant_platform_service_invoice_rollback.sql
-- ════════════════════════════════════════════════════════════════════════════

BEGIN;

ALTER TABLE service_invoices
    ADD COLUMN IF NOT EXISTS is_platform_invoice BOOLEAN NOT NULL DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS ix_service_invoices_is_platform
    ON service_invoices (is_platform_invoice) WHERE is_platform_invoice = TRUE;

COMMIT;
