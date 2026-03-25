# WF-03: Purchase Workflow

## Overview
The purchase workflow manages incoming goods. The full flow is:
Purchase Order (optional) → Goods Receipt Note (GRN) → Stock Updated → Supplier Invoice → Payment.

A GRN can be created with or without a Purchase Order. Stock only increases when a GRN is confirmed — never on draft.

---

## 3.1 Purchase Order (PO)

### Who Can Access
Admin, Inventory (full). Accounting (read only).

### Purpose
A PO is a formal document sent to a supplier saying "we want to buy these items at this price." It is optional — you can receive goods directly via GRN without a prior PO.

### Status Flow
```
draft → sent → partial (first GRN received) → received (all items GRN'd)
draft → cancelled
sent → cancelled
```

### Creating a PO
1. User clicks "New Purchase Order".
2. Select supplier from searchable dropdown (shows supplier name + code).
3. Order date (default today) and expected delivery date.
4. Add line items:
   - Select product (searchable dropdown showing name + code + current stock).
   - Quantity (must be > 0).
   - Unit price (pre-filled from product.purchase_price, editable).
   - Discount % (optional).
   - GST rate (pre-filled from product.gst_rate, read-only display).
   - Line totals calculated automatically.
5. Notes field (optional).
6. Save as Draft or Save and Send (status changes to 'sent').

### Item Calculation (auto-computed, shown in real-time)
```
gross_amount = unit_price * quantity
discount_amount = ROUND(gross_amount * discount_percent / 100)
taxable_amount = gross_amount - discount_amount

Determine IGST or CGST/SGST by comparing company.state_code vs supplier.state_code

if IGST:
  igst_amount = ROUND(taxable_amount * gst_rate / 100)
  cgst_amount = 0, sgst_amount = 0
else:
  cgst_amount = ROUND(taxable_amount * (gst_rate/2) / 100)
  sgst_amount = ROUND(taxable_amount * (gst_rate/2) / 100)
  igst_amount = 0

total_amount = taxable_amount + igst_amount + cgst_amount + sgst_amount
```

### PO Totals (shown in footer of items table)
- Subtotal (sum of gross amounts)
- Total Discount
- Total Taxable Amount
- CGST / SGST (if intra-state)
- IGST (if inter-state)
- Grand Total

### Editing
A PO can only be edited when status = 'draft'. Once sent, it cannot be modified.

### Rules
- A PO in 'received' or 'cancelled' status cannot be modified.
- A PO cannot be cancelled if it has confirmed GRNs against it.
- PO number is auto-generated (e.g., PO-00001) on save.

---

## 3.2 Goods Receipt Note (GRN)

### Who Can Access
Admin, Inventory (full). Accounting (read only).

### Purpose
A GRN records the actual receipt of goods. Confirming a GRN is the only action that adds stock. A GRN can reference a PO (partial or full) or can be standalone.

### Status Flow
```
draft → confirmed (triggers stock addition)
draft → cancelled
```
Once confirmed, a GRN cannot be edited or cancelled. To reverse, use Purchase Return.

### Creating a GRN

#### Option A: From Purchase Order
1. On the PO detail page, click "Create GRN".
2. GRN form pre-fills: supplier, items from PO.
3. User adjusts quantities actually received (can be less than PO quantity).
4. User enters supplier invoice number and supplier invoice date.
5. User confirms.

#### Option B: Standalone GRN
1. User clicks "New GRN" from the GRN list page.
2. Select supplier.
3. Optionally link to a PO (searchable dropdown filtered by supplier, shows open POs).
4. Receipt date (default today).
5. Supplier invoice number, supplier invoice date.
6. Add line items manually.
7. Confirm GRN.

### GRN Confirmation Logic (Backend — Critical)
When `POST /api/v1/grn/{id}/confirm` is called:

```python
def confirm_grn(db, grn_id, user_id):
    grn = get_grn_or_404(db, grn_id)
    if grn.status != 'draft':
        raise HTTPException(400, "GRN is not in draft status")

    # 1. Change GRN status to confirmed
    grn.status = 'confirmed'

    # 2. Create stock ledger entries for each item
    for item in grn.items:
        ledger = StockLedger(
            product_id=item.product_id,
            transaction_type='purchase',
            reference_type='grn',
            reference_id=grn.id,
            reference_number=grn.grn_number,
            quantity=item.quantity,     # positive (inward)
            rate=item.unit_price,
            transaction_date=grn.receipt_date,
            created_by=user_id,
        )
        db.add(ledger)

    # 3. If linked to PO, update PO item received_quantity
    if grn.purchase_order_id:
        for item in grn.items:
            if item.purchase_order_item_id:
                po_item = db.query(PurchaseOrderItem).get(item.purchase_order_item_id)
                po_item.received_quantity += item.quantity

        # Update PO status
        po = db.query(PurchaseOrder).get(grn.purchase_order_id)
        all_items = db.query(PurchaseOrderItem).filter_by(purchase_order_id=po.id).all()
        if all(i.received_quantity >= i.quantity for i in all_items):
            po.status = 'received'
        else:
            po.status = 'partial'

    db.commit()

    # 4. Refresh materialized view
    db.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY current_stock"))
    db.commit()
```

### UI
- List page shows: GRN Number, Date, Supplier, Linked PO, Status, Amount
- Detail page shows: header info + items table + totals + confirmation button (only if draft)
- Once confirmed, show "Confirmed" badge and disable all edit controls

---

## 3.3 Purchase Return

### Who Can Access
Admin, Inventory (full). Accounting (read only).

### Purpose
Return goods to a supplier after a confirmed GRN. This reduces stock.

### Status Flow
```
draft → confirmed (deducts stock)
draft → cancelled
```

### Creating a Purchase Return
1. User clicks "New Purchase Return".
2. Select supplier.
3. Link to a confirmed GRN (mandatory — can only return goods that were received).
4. GRN items auto-populate.
5. User selects which items to return and quantity to return.
   - Return quantity cannot exceed original received quantity.
6. Reason for return (required).
7. Return date (default today).
8. Save as draft.
9. Confirm when ready.

### Purchase Return Confirmation Logic (Backend)
When confirmed:
```python
for item in return_items:
    # Validate: cannot return more than received
    original = get_grn_item(db, grn_id, item.product_id)
    already_returned = get_already_returned_qty(db, grn_id, item.product_id)
    if item.quantity > (original.quantity - already_returned):
        raise HTTPException(400, "Return quantity exceeds receivable quantity")

    ledger = StockLedger(
        transaction_type='purchase_return',
        quantity=-item.quantity,   # negative (outward)
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
| Confirm GRN already confirmed | 400: "GRN is already confirmed" |
| Cancel confirmed GRN | 400: "Confirmed GRN cannot be cancelled" |
| Return more than received | 400: "Return quantity exceeds received quantity" |
| Create GRN for cancelled PO | Block in UI: PO dropdown only shows status in (sent, partial) |
| Edit sent PO | Backend returns 400. Edit button hidden in UI for non-draft POs. |
