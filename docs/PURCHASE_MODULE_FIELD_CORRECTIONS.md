# Purchase Module - Actual Fields vs Test Data Discrepancies

**Date:** March 29, 2026  
**Purpose:** Identify field discrepancies between test documentation and actual application implementation  
**Status:** Critical for accurate testing

---

## [SEARCH] Executive Summary

The test data provided earlier included some fields that **DO NOT EXIST** in the current application. This document identifies all discrepancies and provides **CORRECTED test data** based on the actual database schema and frontend forms.

---

## [LIST] Field Discrepancies Analysis

### **Purchase Order (PO) Module**

#### [FAIL] Fields Mentioned in Test Data (DO NOT EXIST):
```
1. PO Items → "Line Total" field
   - Test data showed: "Line Total: ₹4,20,000 + ₹75,600 (IGST) = ₹4,95,600"
   - Reality: Line totals are AUTO-CALCULATED, not manually entered
   
2. PO Header → "Notes" field shown as required
   - Reality: Notes is OPTIONAL (nullable)
```

#### [OK] Actual PO Fields (Frontend Form):
```typescript
// Header Fields (from PurchaseOrderPage.tsx)
{
  supplier_id: string (required)           // Dropdown: Select supplier
  order_date: string (required)            // Date picker
  expected_delivery_date: string (optional) // Date picker
  notes: string (optional)                 // Textarea
  status: 'draft' | 'sent'                 // Auto-set by save button
}

// Line Item Fields (from PurchaseOrderPage.tsx)
{
  product_id: string (required)            // Dropdown: Select product
  quantity: number (required)              // Number input
  unit_price: number (required)            // Number input (₹ rupees, converted to paise)
  discount_percent: number (default: 0)    // Number input (percentage)
  gst_rate: 0|5|12|18|28 (required)       // Dropdown: GST %
}

// Auto-calculated fields (NOT in form, calculated by backend)
{
  subtotal: number (auto)
  total_discount: number (auto)
  total_taxable_amount: number (auto)
  total_cgst: number (auto)
  total_sgst: number (auto)
  total_igst: number (auto)
  total_gst: number (auto)
  total_amount: number (auto)
  description: string (auto from product name)
  discount_amount: number (auto)
  cgst_amount: number (auto)
  sgst_amount: number (auto)
  igst_amount: number (auto)
  received_quantity: number (auto, default: 0)
}
```

---

### **GRN (Goods Receipt Note) Module**

#### [FAIL] Fields Mentioned in Test Data (DO NOT EXIST):
```
1. GRN Items → "PO Quantity" as separate field
   - Reality: PO quantity is shown as REFERENCE ONLY (received_quantity vs quantity)
   
2. GRN Header → "Supplier Invoice Date" shown as required
   - Reality: supplier_invoice_date is OPTIONAL
```

#### [OK] Actual GRN Fields (Frontend Form - GRNPage.tsx):
```typescript
// Header Fields
{
  supplier_id: string (required)                    // Dropdown: Select supplier
  purchase_order_id: string (optional)              // Dropdown: Linked PO (or standalone)
  receipt_date: string (required)                   // Date picker
  supplier_invoice_number: string (optional)        // Text input
  supplier_invoice_date: string (optional)          // Date input
  notes: string (optional)                          // Textarea
}

// Line Item Fields
{
  product_id: string (required)                     // Dropdown: Select product
  purchase_order_item_id: string (optional)         // Auto-filled if from PO
  quantity: number (required)                       // Number input (actual received qty)
  unit_price: number (required)                     // Number input (₹ rupees, auto-filled from PO/product)
  discount_percent: number (default: 0)             // Number input
  gst_rate: 0|5|12|18|28 (required)                // Dropdown: GST % (auto-filled from product)
}

// Reference-only fields (shown in UI when linked to PO, NOT editable)
{
  po_ordered_qty: number (read-only reference)      // Shows how much was ordered
  po_received_qty: number (read-only reference)     // Shows how much already received
  po_pending_qty: number (read-only reference)      // Auto-calculated pending
}

// Auto-calculated fields (backend)
{
  subtotal: number (auto)
  total_discount: number (auto)
  total_taxable_amount: number (auto)
  total_cgst: number (auto)
  total_sgst: number (auto)
  total_igst: number (auto)
  total_gst: number (auto)
  total_amount: number (auto)
  discount_amount: number (auto)
  cgst_amount: number (auto)
  sgst_amount: number (auto)
  igst_amount: number (auto)
}
```

---

## [OK] CORRECTED Test Data (Matching Actual Application)

### **PHASE 1: Master Data Setup** (UNCHANGED - These are correct)

#### **1.1 Create Product**
```
Navigate to: Products → Add Product

Product Details:
├─ Product Name: Dell Inspiron 15 Laptop
├─ Description: 15.6" FHD, Intel i5 12th Gen, 8GB RAM, 512GB SSD
├─ SKU: DELL-INS15-I5-BLK
├─ HSN Code: 84713010
├─ GST Rate: 18%
├─ Category: Electronics
├─ Unit of Measure: PCS (Pieces)
├─ Purchase Price: ₹42,000.00
├─ Selling Price: ₹52,000.00
├─ MRP: ₹57,990.00
├─ Minimum Stock: 5
└─ Opening Stock: 0

[OK] This is CORRECT - all fields exist in application
```

#### **1.2 Create Supplier**
```
Navigate to: Suppliers → New Supplier

Supplier Details:
├─ Company Name: Dell India Pvt Ltd
├─ Contact Person: Rajesh Kumar
├─ Phone: 9876543210
├─ Email: sales@dell-india.example.com
├─ GSTIN: 27AAACD1234F1Z5
├─ PAN: AAACD1234F
├─ Address Line 1: Plot No 123, MIDC Industrial Area
├─ Address Line 2: Andheri East
├─ City: Mumbai
├─ State: Maharashtra
├─ State Code: 27
├─ Pincode: 400093
├─ Bank Name: HDFC Bank
├─ Bank Account No: 50200012345678
├─ Bank IFSC: HDFC0001234
├─ Payment Terms: 30 days
└─ Opening Balance: ₹0

[OK] This is CORRECT - all fields exist in application
```

---

### **PHASE 2: Purchase Order Creation** (CORRECTED)

#### **2.1 Create Purchase Order**
```
Navigate to: Purchase → Purchase Orders → New PO

STEP 1: Fill Header Fields
┌─────────────────────────────────────────────────────────────┐
│ Field                      │ Value to Enter                 │
├─────────────────────────────────────────────────────────────┤
│ Supplier                   │ Dell India Pvt Ltd (select)    │
│ Order Date                 │ 29/03/2026 (today)             │
│ Expected Delivery Date     │ 05/04/2026 (optional)          │
│ Notes                      │ Urgent requirement for Q1      │
│                            │ sales (optional)               │
└─────────────────────────────────────────────────────────────┘

STEP 2: Add Line Items
┌─────────────────────────────────────────────────────────────┐
│ Line Item 1: Dell Inspiron 15 Laptop                        │
├─────────────────────────────────────────────────────────────┤
│ Field                      │ Value to Enter                 │
├─────────────────────────────────────────────────────────────┤
│ Product                    │ Dell Inspiron 15 Laptop        │
│ Quantity                   │ 10                             │
│ Unit Price                 │ ₹42,000.00                     │
│ Discount %                 │ 0                              │
│ GST %                      │ 18%                            │
│                            │                                │
│ Click "Add Item" button    │                                │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Line Item 2: Logitech Wireless Mouse M170                   │
├─────────────────────────────────────────────────────────────┤
│ Field                      │ Value to Enter                 │
├─────────────────────────────────────────────────────────────┤
│ Product                    │ Logitech Wireless Mouse M170   │
│ Quantity                   │ 50                             │
│ Unit Price                 │ ₹350.00                        │
│ Discount %                 │ 0                              │
│ GST %                      │ 18%                            │
│                            │                                │
│ Click "Add Item" button    │                                │
└─────────────────────────────────────────────────────────────┘

STEP 3: Review Line Items (Auto-calculated, read-only display)
┌─────────────────────────────────────────────────────────────┐
│ Item 1: Dell Inspiron 15 Laptop                             │
│ - Gross Amount: 10 × ₹42,000 = ₹4,20,000                   │
│ - Discount: 0% = ₹0                                         │
│ - Taxable Amount: ₹4,20,000                                 │
│ - IGST (18%): ₹75,600                                       │
│ - Total: ₹4,95,600                                          │
├─────────────────────────────────────────────────────────────┤
│ Item 2: Logitech Mouse M170                                 │
│ - Gross Amount: 50 × ₹350 = ₹17,500                        │
│ - Discount: 0% = ₹0                                         │
│ - Taxable Amount: ₹17,500                                   │
│ - IGST (18%): ₹3,150                                        │
│ - Total: ₹20,650                                            │
└─────────────────────────────────────────────────────────────┘

STEP 4: Save PO
┌─────────────────────────────────────────────────────────────┐
│ Click "Save as Draft" OR "Save and Send"                    │
│                                                             │
│ - "Save as Draft": status = draft                          │
│ - "Save and Send": status = sent                           │
└─────────────────────────────────────────────────────────────┘

Expected Result:
[OK] PO Number auto-generated: PO-00001
[OK] Status: draft OR sent
[OK] Total Amount: ₹5,16,250 (auto-calculated)
[OK] IGST applied (Karnataka company → Maharashtra supplier)
```

---

### **PHASE 3: GRN Creation** (CORRECTED)

#### **3.1 Create GRN from Purchase Order**
```
Navigate to: Purchase → GRN → New GRN

METHOD A: From PO Detail Page (Recommended)
┌─────────────────────────────────────────────────────────────┐
│ 1. Go to Purchase Orders list                               │
│ 2. Click on PO-00001 to view details                        │
│ 3. Click "Create GRN" button (if available)                 │
│    OR                                                       │
│    Note: If no button, use Method B below                   │
└─────────────────────────────────────────────────────────────┘

METHOD B: From GRN List Page
┌─────────────────────────────────────────────────────────────┐
│ STEP 1: Fill Header Fields                                  │
│                                                             │
│ Field                      │ Value to Enter                 │
│ ─────────────────────────────────────────────────────────── │
│ Supplier                   │ Dell India Pvt Ltd (select)    │
│                            │                                │
│ Linked PO                  │ PO-00001 (sent/partial)        │
│                            │ (Select from dropdown - this   │
│                            │  will auto-fill items)         │
│                            │                                │
│ Receipt Date               │ 02/04/2026                     │
│                            │                                │
│ Supplier Invoice Number    │ DELL-INV-2026-0345             │
│                            │ (optional but recommended)     │
│                            │                                │
│ Supplier Invoice Date      │ 01/04/2026                     │
│                            │ (optional)                     │
│                            │                                │
│ Notes                      │ Material received in good      │
│                            │ condition (optional)           │
└─────────────────────────────────────────────────────────────┘

STEP 2: Verify/Auto-filled Line Items (from PO)
┌─────────────────────────────────────────────────────────────┐
│ Item 1: Dell Inspiron 15 Laptop                             │
│ ├─ Product: Dell Inspiron 15 Laptop (auto-selected)         │
│ ├─ Quantity: 10 (pre-filled, EDITABLE - actual received)    │
│ ├─ Unit Price: ₹42,000.00 (auto-filled from PO)             │
│ ├─ Discount %: 0% (pre-filled)                              │
│ ├─ GST %: 18% (pre-filled)                                  │
│ └─ Reference (read-only):                                   │
│    - PO Ordered: 10 units                                   │
│    - PO Received: 0 units (first GRN)                       │
│    - Pending: 10 units                                      │
├─────────────────────────────────────────────────────────────┤
│ Item 2: Logitech Mouse M170                                 │
│ ├─ Product: Logitech Mouse M170 (auto-selected)             │
│ ├─ Quantity: 50 (pre-filled, EDITABLE)                      │
│ ├─ Unit Price: ₹350.00 (auto-filled from PO)                │
│ ├─ Discount %: 0% (pre-filled)                              │
│ ├─ GST %: 18% (pre-filled)                                  │
│ └─ Reference (read-only):                                   │
│    - PO Ordered: 50 units                                   │
│    - PO Received: 0 units                                   │
│    - Pending: 50 units                                      │
└─────────────────────────────────────────────────────────────┘

IMPORTANT: Quantity Field Behavior
┌─────────────────────────────────────────────────────────────┐
│ - Quantity is PRE-FILLED with PO pending quantity           │
│ - You CAN EDIT it to match ACTUAL received quantity         │
│ - Example: If PO ordered 10 but only 8 arrived, change to 8 │
│ - PO status will update:                                    │
│   - Full qty received → status = "received"                │
│   - Partial qty received → status = "partial"              │
└─────────────────────────────────────────────────────────────┘

STEP 3: Save GRN
┌─────────────────────────────────────────────────────────────┐
│ Click "Create GRN" button                                   │
│                                                             │
│ Backend auto-calculates:                                    │
│ - Subtotal: ₹4,37,500                                       │
│ - IGST (18%): ₹78,750                                       │
│ - Total Amount: ₹5,16,250                                   │
└─────────────────────────────────────────────────────────────┘

Expected Result:
[OK] GRN Number auto-generated: GRN-00001
[OK] Status: draft
[OK] Items auto-filled from PO
[OK] Supplier invoice number saved
```

#### **3.2 Confirm GRN (Stock Update)**
```
Navigate to: Purchase → GRN

STEP 1: Find GRN-00001 in list

STEP 2: Click "View" button to open detail modal
┌─────────────────────────────────────────────────────────────┐
│ GRN Detail Modal Shows:                                     │
│                                                             │
│ Header Information:                                         │
│ - GRN Number: GRN-00001                                    │
│ - Supplier: Dell India Pvt Ltd                             │
│ - Receipt Date: 02/04/2026                                 │
│ - Supplier Invoice: DELL-INV-2026-0345                     │
│ - Status: draft                                            │
│ - Total Amount: ₹5,16,250                                  │
│                                                             │
│ Tax Breakdown:                                              │
│ - Taxable Amount: ₹4,37,500                                │
│ - GST: ₹78,750                                             │
│ - IGST: ₹78,750 (inter-state)                              │
│                                                             │
│ Line Items Table:                                           │
│ ┌──────────────────────────────────────────────────────┐   │
│ │ Product     │ Qty │ Price   │ Disc │ GST │ Total    │   │
│ ├──────────────────────────────────────────────────────┤   │
│ │ Dell Laptop │ 10  │ ₹42,000 │ 0%   │ 18% │ ₹4,95,600│   │
│ │ Logi Mouse  │ 50  │ ₹350    │ 0%   │ 18% │ ₹20,650  │   │
│ └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘

STEP 3: Click "[OK] Confirm & Add Stock" button
┌─────────────────────────────────────────────────────────────┐
│ Confirmation dialog:                                        │
│ "Confirm this GRN? Stock will be added to inventory."       │
│                                                             │
│ Click OK                                                    │
└─────────────────────────────────────────────────────────────┘

Expected Results:
[OK] GRN Status: draft → confirmed
[OK] PO Status: sent → received (if full qty)
[OK] Stock Ledger Entries Created:
   - Dell Laptop: +10 units @ ₹42,000
   - Logitech Mouse: +50 units @ ₹350
[OK] Current Stock Updated:
   - Dell Laptop: 10 units
   - Logitech Mouse: 50 units
```

---

## [METRICS] Complete Field Reference Table

### **Purchase Order Fields**

| Field | Type | Required | User Input | Auto | Notes |
|-------|------|----------|------------|------|-------|
| **Header** |
| supplier_id | UUID | [OK] | Dropdown | | Select from suppliers |
| order_date | Date | [OK] | Date picker | Default: today | |
| expected_delivery_date | Date | [FAIL] | Date picker | | Optional |
| notes | Text | [FAIL] | Textarea | | Optional |
| status | String | - | Button click | Auto | draft/sent via button |
| po_number | String | - | | [OK] Auto | Generated on save |
| total_amount | Integer | - | | [OK] Auto | Calculated from items |
| **Line Items** |
| product_id | UUID | [OK] | Dropdown | | Select from products |
| quantity | Number | [OK] | Number input | | Positive integer/decimal |
| unit_price | Integer | [OK] | Number (₹) | Convert to paise | User enters rupees |
| discount_percent | Float | [FAIL] | Number (0-100) | Default: 0 | Percentage |
| gst_rate | Integer | [OK] | Dropdown | | 0/5/12/18/28 |
| description | String | - | | [OK] Auto | From product name |
| received_quantity | Number | - | | [OK] Auto | Default: 0, updated on GRN |

---

### **GRN Fields**

| Field | Type | Required | User Input | Auto | Notes |
|-------|------|----------|------------|------|-------|
| **Header** |
| supplier_id | UUID | [OK] | Dropdown | | Select from suppliers |
| purchase_order_id | UUID | [FAIL] | Dropdown | | Link to PO (optional) |
| receipt_date | Date | [OK] | Date picker | Default: today | |
| supplier_invoice_number | String | [FAIL] | Text input | | Optional but recommended |
| supplier_invoice_date | Date | [FAIL] | Date input | | Optional |
| notes | Text | [FAIL] | Textarea | | Optional |
| grn_number | String | - | | [OK] Auto | Generated on save |
| status | String | - | | [OK] Auto | Default: draft |
| total_amount | Integer | - | | [OK] Auto | Calculated from items |
| **Line Items** |
| product_id | UUID | [OK] | Dropdown | | Select from products |
| purchase_order_item_id | UUID | [FAIL] | | [OK] Auto | If linked to PO |
| quantity | Number | [OK] | Number input | | Actual received qty |
| unit_price | Integer | [OK] | Number (₹) | Auto-fill from PO/product | Convert to paise |
| discount_percent | Float | [FAIL] | Number (0-100) | Default: 0 | |
| gst_rate | Integer | [OK] | Dropdown | Auto-fill from product | 0/5/12/18/28 |

---

## [TARGET] Key Differences Summary

### **What Users DO:**
1. Select supplier from dropdown
2. Enter dates (order date, delivery date, receipt date)
3. Add line items with:
   - Product selection
   - Quantity
   - Unit price (in rupees)
   - Discount percentage
   - GST rate
4. Click save/create button
5. Click confirm button (for GRN)

### **What Backend AUTO-CALCULATES:**
1. All monetary totals (subtotal, discount amount, taxable amount, GST amounts, total)
2. Tax type (IGST vs CGST/SGST) based on state codes
3. Line item totals
4. PO status updates (draft → sent → partial → received)
5. Stock ledger entries on GRN confirmation
6. Current stock materialized view refresh

---

## [OK] Updated Test Checklist

### **PO Creation Test**
- [ ] Select supplier: Dell India Pvt Ltd
- [ ] Enter order date: 29/03/2026
- [ ] Enter expected delivery: 05/04/2026
- [ ] Enter notes (optional): "Urgent requirement"
- [ ] Add line item 1: Dell Laptop, Qty: 10, Price: ₹42,000, Discount: 0%, GST: 18%
- [ ] Add line item 2: Logitech Mouse, Qty: 50, Price: ₹350, Discount: 0%, GST: 18%
- [ ] Click "Save and Send"
- [ ] Verify PO number generated: PO-00001
- [ ] Verify status: sent
- [ ] Verify total amount: ₹5,16,250 (auto-calculated)

### **GRN Creation Test**
- [ ] Select supplier: Dell India Pvt Ltd
- [ ] Select linked PO: PO-00001
- [ ] Verify items auto-filled from PO
- [ ] Enter receipt date: 02/04/2026
- [ ] Enter supplier invoice number: DELL-INV-2026-0345
- [ ] Enter supplier invoice date: 01/04/2026
- [ ] Verify quantities match PO (editable if partial receipt)
- [ ] Click "Create GRN"
- [ ] Verify GRN number generated: GRN-00001
- [ ] Verify status: draft

### **GRN Confirmation Test**
- [ ] Open GRN-00001 detail modal
- [ ] Verify all items and amounts
- [ ] Click "[OK] Confirm & Add Stock"
- [ ] Verify status: draft → confirmed
- [ ] Navigate to Inventory → Stock
- [ ] Verify Dell Laptop stock: 10 units
- [ ] Verify Logitech Mouse stock: 50 units
- [ ] Verify stock ledger entries created

---

## [NOTES] Notes for Testing

1. **Price Handling:**
   - Frontend: User enters prices in RUPEES (₹42,000)
   - Backend: Stores in PAISE (4200000)
   - Frontend displays: Converts back to RUPEES

2. **Auto-calculated Fields:**
   - Users NEVER enter: subtotal, discount_amount, taxable_amount, cgst, sgst, igst, total_amount
   - All these are calculated by backend on save

3. **PO to GRN Flow:**
   - When creating GRN from PO, items are PRE-FILLED
   - Quantities are EDITABLE (for partial receipts)
   - Prices are AUTO-FILLED from PO (read-only in practice)

4. **State Code Logic:**
   - Company state code: 29 (Karnataka)
   - Supplier state code: 27 (Maharashtra)
   - Different states → IGST applies
   - Same state → CGST + SGST applies

---

**Document Version:** 1.0  
**Last Updated:** March 29, 2026  
**Next Step:** Use this corrected test data for actual testing


