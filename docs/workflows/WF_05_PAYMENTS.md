# WF-05: Payments Workflow

## Overview
Payments covers two directions:
- Receipt: money received from customers against sales invoices (Accounts Receivable)
- Payment: money paid to suppliers against GRN/purchase bills (Accounts Payable)

---

## 5.1 Accounts Receivable (Customer Payments)

### Who Can Access
Admin, Accounting (full).

### Purpose
Record payments received from customers. Allocate the payment to specific invoices to clear outstanding balances.

### Payment Modes
- Cash
- Bank Transfer (NEFT/RTGS/IMPS)
- Cheque
- UPI
- Card

### Creating a Receipt
1. Navigate to Payments > Receivables.
2. Click "Record Payment".
3. Select customer (required).
4. On customer selection, the system loads all unpaid/partial-paid invoices for that customer.
5. Payment date (default today).
6. Amount received (in rupees).
7. Payment mode.
8. Reference number (optional — UTR for bank transfer, UPI ID, cheque number).
9. Cheque date (shown only if payment mode = cheque).
10. Bank name (shown only if payment mode = cheque or bank transfer).
11. Allocate amount to invoices:
    - Show list of outstanding invoices: Invoice No, Date, Total Amount, Amount Due.
    - User enters amount to allocate against each invoice.
    - Running total of allocated vs received amount shown.
    - Unallocated amount can exist (advance payment / excess payment).
    - Validation: sum of allocations cannot exceed payment amount.
12. Save payment.

### Payment Allocation Logic (Backend)
```python
def create_receipt(db, payload, user_id):
    # 1. Validate total allocations <= payment amount
    total_allocated = sum(a.allocated_amount for a in payload.allocations)
    if total_allocated > payload.amount:
        raise HTTPException(400, "Total allocations exceed payment amount")

    # 2. Create payment record
    payment = Payment(
        payment_type='receipt',
        party_type='customer',
        customer_id=payload.customer_id,
        amount=payload.amount,
        ...
    )
    db.add(payment)
    db.flush()

    # 3. Create allocation records and update invoices
    for alloc in payload.allocations:
        pa = PaymentAllocation(
            payment_id=payment.id,
            invoice_id=alloc.invoice_id,
            allocated_amount=alloc.allocated_amount,
        )
        db.add(pa)

        # Update invoice amount_paid and amount_due
        invoice = db.query(SalesInvoice).get(alloc.invoice_id)
        invoice.amount_paid += alloc.allocated_amount
        invoice.amount_due = invoice.total_amount - invoice.amount_paid

        # Update invoice status
        if invoice.amount_due <= 0:
            invoice.status = 'paid'
        elif invoice.amount_paid > 0:
            invoice.status = 'partial_paid'

    db.commit()
    return payment
```

### Receivables List Page
Show all customers with outstanding balances:

| Customer | Total Outstanding | Overdue Amount | Overdue Days |
|---|---|---|---|

Click a customer to see their outstanding invoice list.

### Outstanding Invoice List Per Customer
Show each unpaid/partial-paid invoice:
- Invoice number (link to view)
- Invoice date
- Due date
- Total amount
- Amount paid
- Balance due
- Days overdue (if due_date < today, highlight in red)

### Overdue Calculation
```
days_overdue = today - due_date (if due_date < today and status != 'paid')
```
Invoices overdue > 0 days shown with red "Overdue" badge.

---

## 5.2 Accounts Payable (Supplier Payments)

### Who Can Access
Admin, Accounting (full).

### Purpose
Record payments made to suppliers. Allocate payment to specific GRNs/bills.

### Creating a Payment (Outward)
Same structure as receipt but:
- Party type = supplier
- Shows unpaid GRNs from that supplier (total_amount from grn)
- Allocate against GRNs

### Payables List Page
Same structure as receivables but for suppliers.

---

## 5.3 Payment Status Management

Payments can have their status changed by accounting:

| From | To | Condition |
|---|---|---|
| pending | cleared | Bank transfer confirmed |
| pending | bounced | Cheque bounced |
| pending | cancelled | Error entry |
| cleared | — | Cannot revert |
| bounced | — | Cannot revert (create new payment) |

When a payment is cancelled or marked bounced:
1. Reverse all allocation effects: reduce invoice.amount_paid, increase invoice.amount_due.
2. Update invoice status back appropriately.
3. The payment record remains (soft-not-deleted), status = cancelled/bounced.

---

## 5.4 Customer Ledger

Available at `GET /api/v1/customers/{id}/ledger`. Shows every transaction:

| Date | Type | Reference | Debit | Credit | Balance |
|---|---|---|---|---|---|

Transaction types that appear:
- Opening Balance (Dr or Cr)
- Invoice issued (Dr — customer owes us)
- Payment received (Cr — customer paid us)
- Sales Return confirmed (Cr — we owe them)

Balance is running: positive = customer owes us (Dr), negative = we owe customer (Cr).

### Balance Calculation
```
opening_balance (Dr = positive, Cr = negative)
+ SUM of issued invoices (positive, Dr)
- SUM of confirmed sales returns (negative, Cr)
- SUM of cleared/pending payments received (negative, Cr)
= current_balance
```

---

## 5.5 Supplier Ledger

Same structure as customer ledger but:
- GRN confirmed = Cr (we owe supplier)
- Payment made = Dr (we paid supplier)
- Purchase return confirmed = Dr (supplier owes us)

---

## Failure Scenarios

| Scenario | Handling |
|---|---|
| Allocate more than payment amount | Frontend validates in real-time. Shows remaining unallocated amount. |
| Cancel a cleared payment | 400: "Cleared payments cannot be cancelled." |
| Record payment for inactive customer | 400. Customer dropdown only shows active customers. |
| Allocate to already-paid invoice | Backend validates invoice.amount_due > 0 for each allocation. |
