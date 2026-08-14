-- Rollback for 0029_invoice_exchange_rate.sql
-- Drops the per-invoice currency/exchange-rate columns. Foreign-currency invoices
-- created while the feature was live will lose their stored rate (base-currency
-- amounts cannot be reconstructed afterwards), so take a backup first.

BEGIN;

ALTER TABLE sales_invoices DROP COLUMN IF EXISTS exchange_rate;
ALTER TABLE sales_invoices DROP COLUMN IF EXISTS currency_code;

COMMIT;
