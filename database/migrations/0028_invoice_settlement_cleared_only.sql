-- ════════════════════════════════════════════════════════════════════════════
-- Recompute Sales-Invoice settlement from CLEARED receipts only
-- File: 0028_invoice_settlement_cleared_only.sql
-- Task: BE-261 (Accounts Receivable — pending receipts no longer settle invoices)
--
-- PURPOSE
--   Previously a receipt reduced an invoice's outstanding as soon as it was
--   recorded, even while the payment was still "pending" (uncleared). This made
--   an invoice look "Fully Received" while part of it was covered by a pending
--   cheque, disagreeing with the customer-balance view (which counts cleared
--   receipts only). The application now settles an invoice only from CLEARED
--   allocations. This migration re-derives every existing invoice's amount_paid /
--   amount_due / status from its cleared allocations so historical data matches.
--
-- SAFETY: data-only, idempotent (recomputed from source each run). No schema
--   change. Does NOT touch cancelled / returned / draft invoices' status.
-- ROLLBACK: 0028_invoice_settlement_cleared_only_rollback.sql (best-effort note —
--   the prior "pending-inclusive" values cannot be reconstructed once corrected).
-- ════════════════════════════════════════════════════════════════════════════

BEGIN;

UPDATE sales_invoices si
SET amount_paid = sub.paid,
    amount_due  = si.total_amount - sub.paid,
    status = CASE
        WHEN lower(trim(si.status)) NOT IN ('issued','partial_paid','paid') THEN si.status
        WHEN si.total_amount > 0 AND si.total_amount - sub.paid = 0 THEN 'paid'
        WHEN sub.paid > 0 THEN 'partial_paid'
        ELSE 'issued'
    END
FROM (
    SELECT si2.id,
           LEAST(si2.total_amount, COALESCE((
               SELECT SUM(pa.allocated_amount)
               FROM payment_allocations pa
               JOIN payments p ON p.id = pa.payment_id
               WHERE pa.invoice_id = si2.id
                 AND pa.is_deleted = false
                 AND p.is_deleted = false
                 AND lower(trim(p.status)) IN ('cleared','advance_payment_cleared','advance_cleared','full_payment_cleared')
           ), 0)) AS paid
    FROM sales_invoices si2
    WHERE si2.is_deleted = false
) sub
WHERE si.id = sub.id
  AND si.is_deleted = false;

COMMIT;
