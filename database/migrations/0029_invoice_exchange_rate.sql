-- ════════════════════════════════════════════════════════════════════════════
-- Per-invoice transaction currency + exchange rate (foreign-currency invoices)
-- File: 0029_invoice_exchange_rate.sql
-- Feature: SAL-CUR-01 (Exchange rate captured per Sales Invoice)
--
-- PURPOSE
--   Support foreign-currency Sales Invoices. Each invoice now records its own
--   transaction currency (currency_code) and the exchange rate to the tenant's
--   base currency (INR), captured PER INVOICE so historical invoices keep their
--   original rate regardless of later rate changes. All existing monetary columns
--   on sales_invoices are stored in currency_code's minor units; the base-currency
--   (INR) equivalent of any amount = amount * exchange_rate. Base-currency (INR)
--   invoices use currency_code='INR' and exchange_rate=1.0 (no conversion applied).
--
-- SAFETY: additive + idempotent. Defaults ('INR', 1.0) mean every existing invoice
--   is treated as base currency, so amounts and reports are numerically unchanged.
-- ROLLBACK: 0029_invoice_exchange_rate_rollback.sql (drops the two columns).
-- ════════════════════════════════════════════════════════════════════════════

BEGIN;

ALTER TABLE sales_invoices ADD COLUMN IF NOT EXISTS currency_code VARCHAR(3) NOT NULL DEFAULT 'INR';
ALTER TABLE sales_invoices ADD COLUMN IF NOT EXISTS exchange_rate NUMERIC(12,6) NOT NULL DEFAULT 1;

-- Backfill any pre-existing NULL/blank values to safe base-currency defaults.
UPDATE sales_invoices SET currency_code = 'INR' WHERE currency_code IS NULL OR TRIM(currency_code) = '';
UPDATE sales_invoices SET exchange_rate = 1 WHERE exchange_rate IS NULL OR exchange_rate <= 0;

COMMIT;
