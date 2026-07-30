-- ════════════════════════════════════════════════════════════════════════════
-- ROLLBACK — Invoice settlement cleared-only recompute
-- File: 0028_invoice_settlement_cleared_only_rollback.sql
-- Task: BE-261
--
-- NOTE: This is a data recompute, not a schema change. The prior behaviour counted
-- pending receipts toward invoice settlement; those exact pre-migration values
-- cannot be reconstructed. To revert behaviourally, restore the application code
-- that applied allocations on payment creation and re-run a recompute that also
-- counts pending payments:
--
--   UPDATE sales_invoices si SET amount_paid = <sum of ALL non-deleted allocations
--   from non-cancelled/non-bounced payments>, amount_due = total-amount_paid, ...
--
-- (No automatic SQL rollback is provided.)
-- ════════════════════════════════════════════════════════════════════════════

SELECT 1;
