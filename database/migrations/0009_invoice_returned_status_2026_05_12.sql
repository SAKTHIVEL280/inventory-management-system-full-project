BEGIN;

-- DB-54: Allow returned status for sales invoices
ALTER TABLE sales_invoices
DROP CONSTRAINT IF EXISTS sales_invoices_status_check;

ALTER TABLE sales_invoices
ADD CONSTRAINT sales_invoices_status_check
CHECK (status IN ('draft','issued','partial_paid','paid','returned','cancelled'));

COMMIT;
