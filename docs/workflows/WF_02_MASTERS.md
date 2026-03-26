# WF-02: Masters Workflow

## Overview
Masters are the reference data that all transactions depend on. They must be set up before any transactional module is used. Order of setup: Company → Users → Products (with Categories and UoM) → Customers → Suppliers.

---

## 2.1 Company Profile

### Who Can Access
Admin only.

### Fields Required
- Company name (required)
- Legal name
- GSTIN (15 characters, validated format: `\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]`)
- PAN
- Address line 1, line 2, city, state, state code, pincode
- Phone, email, website
- Logo upload (PNG/JPG, max 2MB, stored as file, URL saved in DB)
- Bank name, account number, IFSC, branch
- Invoice prefix and counter (default: INV, 1)
- PO prefix and counter (default: PO, 1)
- SO prefix and counter (default: SO, 1)
- QTN prefix and counter (default: QTN, 1)
- GRN prefix and counter (default: GRN, 1)

### State Code Importance
The company's `state_code` is compared against customer/supplier `state_code` to determine IGST vs CGST+SGST. This must be set correctly before creating any transactions.

### UI
- Single full-width form with sections: Basic Info, Address, Bank Details, Document Numbering
- Save button at bottom right
- Logo shows a preview thumbnail after upload
- State code is a dropdown of all 37 Indian state codes

---

## 2.2 User Management

### Who Can Access
Admin only.

### Fields
- Full name (required)
- Email (required, unique)
- Password (required on create, optional on edit — blank means no change)
- Role: admin / accounting / sales / inventory (required)
- Module access overrides (optional, admin-configured allow/deny list)
- Is Active toggle

### Rules
- Admin cannot delete or deactivate their own account.
- Password must be minimum 8 characters.
- On create, the user receives a temporary password. They are prompted to change it on first login.
- Admin can grant/restrict module access for non-admin users beyond role defaults.
- Admin can revert any user to role-default module access by clearing overrides.
- Admin-only modules (`Company`, `Users`) cannot be granted unless the user role is `admin`.

### UI
- Table of users with columns: Name, Email, Role badge, Status badge, Actions (Edit, Deactivate)
- "New User" button opens a modal form (not a separate page)
- Role badges must use design tokens from `tailwind.config.ts` (`colors.role.admin`, `colors.role.accounting`, `colors.role.sales`, `colors.role.inventory`).
- User form includes a "Module Access" section with role defaults and allow/deny overrides.
- User form includes a "Reset to Role Defaults" action to remove all module overrides.

---

## 2.3 Customer Master

### Who Can Access
Admin, Sales (full). Accounting, Inventory (read only).

### Fields
- Customer code (auto-generated: CUST-00001, editable before save)
- Company name (required)
- Contact person name
- Email
- Phone (required)
- Alternate phone
- GSTIN (validated format if provided)
- PAN
- Customer type: regular / dealer / distributor / retail
- Billing address: line1, line2, city, state, state_code, pincode
- Shipping address: same toggle, or separate fields
- Credit limit (in rupees, stored as paise — 0 means no limit)
- Payment terms (days): default 30
- Opening balance (in rupees, Dr/Cr)

### Auto-Generated Code Logic
```
CUST-{5-digit-padded-sequential-number}
e.g., CUST-00001, CUST-00002
```
This is separate from the company counter. Maintain a separate customer_counter in the company table or use `SELECT COUNT(*) + 1`.

### Important: Same-as-Billing Toggle
When `same_as_billing` is true, the shipping address fields are hidden and the billing address is used for shipping in all transactions.

### GSTIN Auto-Fill
When GSTIN is entered (15 chars), auto-extract the state code from characters 1-2 (e.g., GSTIN starting with "29" = Karnataka, state_code = "29"). Pre-fill the state code field.

### Balance Display
On the customer detail/edit page, show a read-only balance card:
- Total Invoiced
- Total Paid
- Balance Due

These are calculated live from sales_invoices and payments tables.

### UI
- List page: table with search, filter by type and status
- Form page: two-column layout, separate sections for Basic, Address, Financial
- Delete is blocked if customer has any active invoice with outstanding balance

---

## 2.4 Supplier Master

### Who Can Access
Admin, Inventory (full). Accounting (read only).

### Fields
- Supplier code (auto-generated: SUPP-00001)
- Company name (required)
- Contact person
- Email
- Phone (required)
- Alternate phone
- GSTIN
- PAN
- Address: line1, line2, city, state, state_code, pincode
- Bank: bank name, account number, IFSC
- Payment terms (days): default 30
- Opening balance (Dr/Cr)

### Balance Display
On detail page, show:
- Total Purchased
- Total Paid
- Balance Due

---

## 2.5 Product Master

### Who Can Access
Admin, Inventory (full). Sales (read only).

### Fields
- Product code (auto-generated: PRD-00001)
- SKU (optional, unique if provided)
- Product name (required)
- Description
- Category (required, from product_categories table)
- Primary UoM (required, from units_of_measure table)
- Alternate UoM + conversion factor (optional)
  - e.g., Primary = PCS, Alt = BOX, Conversion = 12 (1 BOX = 12 PCS)
- HSN code (required, 6-8 digit string)
- GST rate (required, dropdown: 0%, 5%, 12%, 18%, 28%)
- Purchase price (in rupees, stored as paise)
- Selling price (in rupees, stored as paise)
- MRP (in rupees, stored as paise)
- Minimum stock level (for low stock alert)
- Opening stock (quantity)

### Opening Stock Logic
When opening stock > 0 and product is saved for the first time, create a stock_ledger entry:
```
transaction_type = 'opening'
quantity = opening_stock (positive)
rate = purchase_price
transaction_date = today
```
Then refresh materialized view.

### Low Stock Indicator
In the product list, show a red badge "Low Stock" if current_quantity <= minimum_stock.

### Product Categories
Managed from the Products page (tab or section). Simple CRUD: name + description. Cannot delete a category that has products.

### Units of Measure
Pre-seeded. Admin can add custom UoMs. Cannot delete a UoM that is in use.

---

## Failure Scenarios

| Scenario | Handling |
|---|---|
| Duplicate GSTIN on customer/supplier | Backend returns 400 with error_code DUPLICATE_GSTIN. Show inline error. |
| Delete customer with outstanding | Backend returns 400 with OUTSTANDING_EXISTS. Show toast error. |
| Delete product with stock > 0 | Backend returns 400. Show toast: "Cannot delete product with existing stock." |
| Invalid GSTIN format | Frontend validates with regex before submit. Show inline error. |
| Logo file too large | Frontend validates max 2MB before upload. Show inline error. |
