# WF-06: Reports Workflow

## Overview
All reports are read-only. Every report supports CSV export. Reports do not modify any data. All monetary values displayed in INR (paise / 100).

---

## 6.1 Dashboard Report

Endpoint: `GET /api/v1/reports/dashboard`
Access: All roles.

### Data Points
- Today's Sales: SUM of total_amount from invoices where invoice_date = today and status in (issued, partial_paid, paid)
- Month Sales: SUM for current calendar month
- Outstanding Receivables: SUM of amount_due from sales_invoices where status in (issued, partial_paid)
- Outstanding Payables: SUM of (total_amount - payments_made) for suppliers
- Low Stock Count: COUNT of products where current_quantity <= minimum_stock
- Overdue Invoices Count: COUNT of invoices where due_date < today and status in (issued, partial_paid)
- Sales Trend: Daily sales total for last 7 days
- Top 5 Products by quantity sold this month
- 5 Most Recent Invoices

---

## 6.2 Stock Report

Endpoint: `GET /api/v1/reports/stock`
Access: Admin, Inventory, Accounting.
Parameters: `as_of_date`, `category_id`, `low_stock_only` (boolean)

### Columns
| Product Code | Product Name | HSN | Category | UoM | Opening Qty | Purchased | Sold | Returned | Adjusted | Closing Qty | Min Stock | Status |

### Status Values
- Normal: closing_qty > minimum_stock
- Low Stock: 0 < closing_qty <= minimum_stock
- Out of Stock: closing_qty = 0

### How Closing Qty is Calculated
For `as_of_date` parameter:
```sql
SELECT
  p.product_code,
  p.name,
  COALESCE(SUM(sl.quantity), 0) as closing_qty
FROM products p
LEFT JOIN stock_ledger sl ON sl.product_id = p.id
  AND sl.transaction_date <= :as_of_date
WHERE p.is_deleted = FALSE
GROUP BY p.id, p.product_code, p.name
```

If no `as_of_date`, use current_stock materialized view (faster).

### CSV Export
Button on the report page. Downloads all rows (no pagination) as a CSV file.

---

## 6.3 Sales Report

Endpoint: `GET /api/v1/reports/sales`
Access: Admin, Accounting, Sales.
Parameters: `from_date`, `to_date`, `customer_id`, `group_by` (day / month / customer / product)

### Columns (when grouped by day)
| Date | No. of Invoices | Subtotal | Discount | Taxable | CGST | SGST | IGST | Total |

### Columns (when grouped by customer)
| Customer Name | Customer Code | No. of Invoices | Total Amount | Amount Paid | Outstanding |

### Columns (when grouped by product)
| Product Name | HSN | Quantity Sold | UoM | Avg Rate | Taxable Amount | GST | Total |

### Filter
- from_date and to_date are required. Default: first day of current month to today.
- Only invoices with status in (issued, partial_paid, paid) are included in sales totals.

---

## 6.4 Purchase Report

Endpoint: `GET /api/v1/reports/purchase`
Access: Admin, Accounting.
Parameters: `from_date`, `to_date`, `supplier_id`, `group_by` (day / month / supplier / product)

Same structure as sales report but for confirmed GRNs.

---

## 6.5 Outstanding Receivables Report

Endpoint: `GET /api/v1/reports/outstanding-receivables`
Access: Admin, Accounting.
Parameters: `as_of_date`, `customer_id`

### Columns
| Customer | Invoice No | Invoice Date | Due Date | Total Amount | Amount Paid | Balance Due | Days Overdue |

### Ageing Buckets (summary at top of report)
| Bucket | Amount |
|---|---|
| Not yet due | — |
| 1-30 days | — |
| 31-60 days | — |
| 61-90 days | — |
| 91+ days | — |
| Total | — |

### Ageing Calculation
```python
days_overdue = (as_of_date - invoice.due_date).days
bucket = 'not_due' if days_overdue <= 0 else (
  '1_30' if days_overdue <= 30 else (
  '31_60' if days_overdue <= 60 else (
  '61_90' if days_overdue <= 90 else '91_plus')))
```

---

## 6.6 Outstanding Payables Report

Same structure as Outstanding Receivables but for supplier GRNs/bills.

---

## 6.7 GSTR-1 Report

Endpoint: `GET /api/v1/reports/gstr1`
Access: Admin, Accounting.
Parameters: `from_date`, `to_date` (must be within same GST period — monthly)

### GSTR-1 Sections

#### B2B Invoices (GSTIN customers)
| GSTIN of Recipient | Receiver Name | Invoice Number | Invoice Date | Invoice Value | Place of Supply | Reverse Charge | Invoice Type | E-Commerce GSTIN | Rate | Taxable Value | IGST | CGST | SGST |

Source: sales_invoices where customer.gstin IS NOT NULL and status in (issued, partial_paid, paid)

#### B2C Large (No GSTIN, invoice value > 2.5 lakh)
| Type | Place of Supply | Rate | Taxable Value | IGST | CGST/SGST |

#### B2C Small (No GSTIN, invoice value <= 2.5 lakh)
Consolidated per state per GST rate.

### Display Format
Show as tabs: B2B | B2C Large | B2C Small | Summary

Summary tab shows total tax liability breakdown by GST rate.

---

## 6.8 GSTR-3B Report

Endpoint: `GET /api/v1/reports/gstr3b`
Access: Admin, Accounting.
Parameters: `from_date`, `to_date`

### Section 3.1 — Outward Supplies
| Description | Total Taxable Value | Integrated Tax | Central Tax | State/UT Tax |
|---|---|---|---|---|
| Taxable outward supplies | | | | |
| Zero rated supplies | | | | |
| Nil rated / exempt supplies | | | | |

### Section 4 — Eligible ITC (Input Tax Credit)
| Description | Integrated Tax | Central Tax | State/UT Tax |
|---|---|---|---|
| ITC Available — Inputs | | | |

ITC = GST paid on confirmed GRNs.

### Net Tax Payable
```
Output Tax = SUM of GST collected on issued invoices
ITC = SUM of GST paid on confirmed GRNs
Net Tax Payable = Output Tax - ITC
```

---

## 6.9 Profit and Loss Report

Endpoint: `GET /api/v1/reports/pl`
Access: Admin, Accounting.
Parameters: `from_date`, `to_date`

### Structure

```
INCOME
  Sales Revenue (sum of taxable_amount from issued invoices)
  Less: Sales Returns (sum of taxable_amount from confirmed sales returns)
  Net Sales

COST OF GOODS SOLD
  Opening Stock Value
  Add: Purchases (sum of taxable_amount from confirmed GRNs)
  Less: Purchase Returns (sum from confirmed purchase returns)
  Less: Closing Stock Value
  Cost of Goods Sold

GROSS PROFIT = Net Sales - Cost of Goods Sold
GROSS PROFIT MARGIN % = (Gross Profit / Net Sales) * 100

NET PROFIT = Gross Profit (no other expenses tracked in v1)
```

### Stock Valuation Method
Weighted average cost:
```
Average Cost = Total Purchase Value / Total Purchase Quantity
Closing Stock Value = Average Cost * Closing Quantity
```

---

## Report UI Standards

### Every Report Page Must Have
1. Filter bar at top: date range pickers, dropdown filters, search.
2. "Apply Filters" button (not real-time — filter only applies on button click to avoid excessive queries).
3. Summary cards row (key totals from the report).
4. Data table with sticky header.
5. "Export CSV" button top-right of table.
6. Pagination for tables with > 50 rows.

### CSV Export Logic
The export includes all rows matching the current filter, not just the current page. The backend returns up to 50,000 rows for CSV export endpoints. File name format: `{report-name}_{from_date}_{to_date}.csv`.
