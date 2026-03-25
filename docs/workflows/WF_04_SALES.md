# WF-04: Sales Workflow

## Overview
The sales workflow covers the full lifecycle from quoting to payment. The flow is:

Quotation (optional) → Sales Order → Tax Invoice → Payment

Each step is optional: you can create a Sales Order directly, or create an Invoice directly without a prior Sales Order. Stock is only deducted when an Invoice is issued — never before.

---

## 4.1 Quotation

### Who Can Access
Admin, Sales (full). Accounting (read only).

### Purpose
A quotation is a non-binding pricing proposal to a customer. It has no accounting or inventory impact. It can be converted to a Sales Order.

### Status Flow
```
draft → sent
sent → accepted
sent → rejected
accepted → converted (when converted to SO)
draft/sent → expired (if valid_until date passes — checked daily or on load)
```

### Creating a Quotation
1. Select customer (required).
2. Quotation date (default today).
3. Valid until date.
4. Party details (optional): sold_to, bill_to, ship_to — defaults to the selected customer for all.
5. Add line items:
   - Select product (shows name, current stock, selling price).
   - Description (pre-filled from product name, editable).
   - Quantity.
   - Unit price (pre-filled from product.selling_price, editable).
   - Discount %.
   - GST rate (from product, shown read-only).
   - Line totals auto-calculated.
6. Notes, Terms & Conditions.
7. Save draft or mark as Sent.

### Party Types
- Sold To Party: the company placing the order
- Bill To Party: the company to be billed (may be different HQ)
- Ship To Party: the delivery address

All three default to the selected customer. The user can override each to a different customer record. This allows B2B scenarios where a branch orders, HQ gets billed, and warehouse receives.

### Convert to Sales Order
1. From the Quotation detail page, click "Convert to Sales Order".
2. Backend creates a new Sales Order copying all line items exactly.
3. Quotation status changes to 'converted'.
4. User is redirected to the new Sales Order.
5. The Sales Order shows `quotation_id` reference.

---

## 4.2 Sales Order

### Who Can Access
Admin, Sales (full). Accounting, Inventory (read only).

### Purpose
A sales order is a confirmed order from a customer. It checks stock availability before confirmation. It becomes the basis for the invoice.

### Status Flow
```
draft → confirmed (stock check passes)
confirmed → partial (first invoice created from this SO)
confirmed → fulfilled (if first invoice fully covers all items)
partial → fulfilled (when remaining items are fully invoiced)
draft → cancelled
confirmed → cancelled (no stock change — stock was not yet reserved)
```

### Creating a Sales Order
1. Select customer (required).
2. Order date (default today). Expected delivery date.
3. Party details: sold_to, bill_to, ship_to.
4. Add line items (same as Quotation).
5. Save draft.
6. Confirm SO (triggers stock check).

### Stock Check on Confirmation (Backend — Critical)
```python
def confirm_sales_order(db, so_id):
    so = get_so_or_404(db, so_id)
    if so.status != 'draft':
        raise HTTPException(400, "Only draft sales orders can be confirmed")

    # Check stock for every item
    shortages = []
    for item in so.items:
        stock = db.execute(
            "SELECT current_quantity FROM current_stock WHERE product_id = :pid",
            {"pid": item.product_id}
        ).fetchone()
        if not stock or stock.current_quantity < item.quantity:
            shortages.append({
                "product_id": str(item.product_id),
                "product_name": item.product.name,
                "required": float(item.quantity),
                "available": float(stock.current_quantity) if stock else 0
            })

    if shortages:
        raise HTTPException(400, detail={
            "message": "Insufficient stock for one or more items",
            "error_code": "INSUFFICIENT_STOCK",
            "shortages": shortages
        })

    so.status = 'confirmed'
    db.commit()
    return so
```

### Convert to Invoice
1. From the SO detail page, click "Create Invoice".
2. Backend creates invoice from selected quantities (full or partial).
3. Backend updates SO item `fulfilled_quantity` per line.
4. SO status becomes `partial` or `fulfilled` based on completion.
5. Invoice shows `sales_order_id` reference.
6. User is redirected to the new Invoice.

---

## 4.3 Tax Invoice

### Who Can Access
Admin, Sales (full). Accounting (read only).

### Purpose
The tax invoice is the legally binding GST-compliant billing document. Issuing an invoice deducts stock and triggers PDF generation.

### Status Flow
```
draft → issued (deducts stock, generates PDF)
issued → partial_paid (partial payment received)
issued → paid (full payment received — auto-triggered by payment service)
partial_paid → paid (remaining payment received)
issued → cancelled (only if amount_paid = 0 and no returns)
draft → cancelled
```

### Creating an Invoice

#### Option A: From Sales Order
- Click "Create Invoice" on a confirmed SO. Items are pre-filled.

#### Option B: Direct Invoice
1. Select customer.
2. Invoice date (default today), due date (default today + customer.payment_terms_days).
3. Party details: bill_to (required), ship_to, sold_to.
4. Supply state: the state where goods are delivered.
5. System auto-determines IGST vs CGST/SGST: compare company.state_code vs bill_to customer.state_code.
6. Add line items.
7. Save as draft.
8. Issue invoice.

### Issue Invoice Logic (Backend — Critical)
When `POST /api/v1/invoices/{id}/issue` is called:

```python
def issue_invoice(db, invoice_id, user_id):
    invoice = get_invoice_or_404(db, invoice_id)
    if invoice.status != 'draft':
        raise HTTPException(400, "Only draft invoices can be issued")

    # 1. Stock check and deduction (same as SO confirm but also deducts)
    for item in invoice.items:
        stock = get_current_stock(db, item.product_id)
        if stock.current_quantity < item.quantity:
            raise HTTPException(400, f"Insufficient stock: {item.product.name}")

        ledger = StockLedger(
            product_id=item.product_id,
            transaction_type='sale',
            reference_type='invoice',
            reference_id=invoice.id,
            reference_number=invoice.invoice_number,
            quantity=-item.quantity,    # negative (outward)
            rate=item.unit_price,
            transaction_date=invoice.invoice_date,
            created_by=user_id,
        )
        db.add(ledger)

    # 2. Set invoice status
    invoice.status = 'issued'
    invoice.amount_due = invoice.total_amount  # no payment yet

    db.commit()

    # 3. Refresh stock view
    db.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY current_stock"))
    db.commit()

    # 4. Generate PDF (synchronous in v1)
    pdf_url = invoice_service.generate_pdf(invoice)
    invoice.pdf_url = pdf_url
    db.commit()

    return invoice
```

### Invoice Item Auto-Fill
When a product is selected in the invoice form:
- Unit price: pre-filled from product.selling_price (editable)
- MRP: pre-filled from product.mrp (shown read-only)
- GST rate: pre-filled from product.gst_rate (shown, not editable on item level)
- Description: pre-filled from product.name (editable)

### IGST vs CGST/SGST Logic (Frontend + Backend)
- When the invoice form loads or bill_to customer changes, compare company.state_code with customer.billing_state_code.
- If different: label columns as "IGST". is_igst = true.
- If same: label columns as "CGST" and "SGST". is_igst = false.
- Recalculate all items when this flag changes.

### Discount Rules
- Discount is applied at item level only (no invoice-level discount).
- Discount % is editable per line item.
- Discount applies before GST calculation.

### PDF Invoice
The PDF is generated server-side using WeasyPrint. See MASTER_SPEC.md Section 12 for the required structure. The PDF is saved to a static files folder and the URL stored in invoice.pdf_url. `GET /api/v1/invoices/{id}/pdf` returns the file directly.

### Email Invoice
`POST /api/v1/invoices/{id}/send-email` with body `{ to_email, cc_email }`:
1. Backend fetches the stored PDF.
2. Sends email with PDF as attachment.
3. Subject: "Invoice {invoice_number} from {company_name}"
4. Email failure does NOT fail the API call. Log the error, return success.

---

## 4.4 Sales Return

### Who Can Access
Admin, Sales (full). Accounting (read only).

### Purpose
Handle goods returned by a customer. Adds stock back. Creates a credit note reference.

### Status Flow
```
draft → confirmed (adds stock back)
draft → cancelled
```

### Creating a Sales Return
1. Select the original sales invoice (mandatory).
2. Invoice items auto-load.
3. User selects which items to return and quantities.
4. Return quantity per item cannot exceed original invoiced quantity minus already-returned quantity.
5. Return date. Reason (required).
6. Confirm.

### Return Confirmation (Backend)
```python
for item in return_items:
    # Validate return quantity
    invoice_item = get_invoice_item(db, invoice_id, item.product_id)
    already_returned = get_already_returned_qty_for_invoice(db, invoice_id, item.product_id)
    max_returnable = invoice_item.quantity - already_returned
    if item.quantity > max_returnable:
        raise HTTPException(400, "Return quantity exceeds original invoiced quantity")

    # Add stock back
    ledger = StockLedger(
        transaction_type='sale_return',
        quantity=item.quantity,  # positive (inward)
        ...
    )
    db.add(ledger)

db.commit()
db.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY current_stock"))
```

---

## Failure Scenarios

| Scenario | Handling |
|---|---|
| Confirm SO with insufficient stock | Return list of shortfall items with amounts. Show in a modal. |
| Issue invoice with insufficient stock | 400 with product name. Show toast error. |
| Cancel issued invoice with payments | 400: "Cannot cancel invoice with recorded payments." |
| Return more than invoiced | 400: "Return quantity exceeds invoiced quantity." |
| Convert already-converted quotation | 400. "Convert" button hidden for non-accepted quotations. |
| Create invoice for cancelled SO | Block in UI. SO must be in 'confirmed' status to create invoice. |
