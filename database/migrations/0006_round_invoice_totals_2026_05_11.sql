-- DB-51: Round sales invoice totals to nearest 0/5 rupees and realign amount_due/status.

WITH rounded AS (
    SELECT
        id,
        COALESCE(total_taxable_amount, 0) + COALESCE(total_gst, 0) AS exact_total,
        COALESCE(amount_paid, 0) AS amount_paid,
        status,
        (FLOOR(((COALESCE(total_taxable_amount, 0) + COALESCE(total_gst, 0))::numeric) / 500) * 500)::int AS rounded_total
    FROM sales_invoices
    WHERE is_deleted = FALSE
)
UPDATE sales_invoices s
SET
    total_amount = r.rounded_total,
    amount_due = GREATEST(r.rounded_total - r.amount_paid, 0),
    status = CASE
        WHEN s.status IN ('draft', 'cancelled') THEN s.status
        WHEN r.amount_paid <= 0 THEN 'issued'
        WHEN r.amount_paid >= r.rounded_total THEN 'paid'
        ELSE 'partial_paid'
    END
FROM rounded r
WHERE s.id = r.id;
