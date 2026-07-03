-- ════════════════════════════════════════════════════════════════════════════
-- ROLLBACK for 0016_multitenant_m5_service_invoice.sql  (Module M5)
-- Date: June 24, 2026 | Task: DB-211
-- WARNING: drops the service invoice tables and all their data. Back up first.
-- ════════════════════════════════════════════════════════════════════════════

BEGIN;

DROP TABLE IF EXISTS service_invoice_items;
DROP TABLE IF EXISTS service_invoices;
ALTER TABLE company DROP COLUMN IF EXISTS svc_prefix;
ALTER TABLE company DROP COLUMN IF EXISTS svc_counter;

COMMIT;
