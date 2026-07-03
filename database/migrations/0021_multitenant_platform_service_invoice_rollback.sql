-- ════════════════════════════════════════════════════════════════════════════
-- ROLLBACK for 0021_multitenant_platform_service_invoice.sql
-- Date: June 25, 2026 | Task: DB-217
-- Drops the platform-invoice flag (and its index). Any platform invoices revert
-- to ordinary tenant rows; remove them first if that is not desired. Idempotent.
-- ════════════════════════════════════════════════════════════════════════════

BEGIN;

DROP INDEX IF EXISTS ix_service_invoices_is_platform;
ALTER TABLE service_invoices DROP COLUMN IF EXISTS is_platform_invoice;

COMMIT;
