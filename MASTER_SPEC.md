# Inventory Management System — Master AI Specification

## Document Purpose
This file is the single source of truth for an AI coding agent to build the complete Inventory Management System from scratch. Every module, every field, every API route, every database table, every business rule, and every UI component is defined here. No assumptions. No hallucinations. Build exactly what is written.

---

## 1. Technology Stack

| Layer | Technology | Version |
|---|---|---|
| Frontend | React | 18.x |
| Language | TypeScript | 5.x |
| Styling | Tailwind CSS | 3.x |
| State Management | Zustand | 4.x |
| API Client | Axios + React Query (TanStack Query) | 5.x |
| Forms | React Hook Form + Zod | latest |
| PDF Generation | @react-pdf/renderer | 3.x |
| Table | TanStack Table | 8.x |
| Charts | Recharts | 2.x |
| Icons | Lucide React | latest |
| Toast Notifications | Sonner | latest |
| Backend | FastAPI | 0.111.x |
| Language | Python | 3.11+ |
| ORM | SQLAlchemy | 2.x |
| Migrations | Alembic | latest |
| Auth | python-jose (JWT) + passlib (bcrypt) | latest |
| Email | FastAPI-Mail | latest |
| PDF (server) | WeasyPrint | latest |
| Database | PostgreSQL | 15+ |
| Task Queue | None (synchronous for v1) | — |

---

## 2. Project Directory Structure

```
project-root/
├── database/
│   ├── alembic/
│   │   ├── versions/
│   │   └── env.py
│   ├── alembic.ini
│   ├── sql/
│   │   ├── init_extensions.sql
│   │   └── materialized_views.sql
│   └── README.md
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── dependencies.py
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── user.py
│   │   │   ├── company.py
│   │   │   ├── customer.py
│   │   │   ├── supplier.py
│   │   │   ├── product.py
│   │   │   ├── purchase.py
│   │   │   ├── sales.py
│   │   │   ├── payment.py
│   │   │   └── stock.py
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   ├── user.py
│   │   │   ├── company.py
│   │   │   ├── customer.py
│   │   │   ├── supplier.py
│   │   │   ├── product.py
│   │   │   ├── purchase.py
│   │   │   ├── sales.py
│   │   │   ├── payment.py
│   │   │   └── stock.py
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py
│   │   │   ├── company.py
│   │   │   ├── customers.py
│   │   │   ├── suppliers.py
│   │   │   ├── products.py
│   │   │   ├── purchase.py
│   │   │   ├── sales.py
│   │   │   ├── payments.py
│   │   │   ├── stock.py
│   │   │   └── reports.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── auth_service.py
│   │   │   ├── gst_service.py
│   │   │   ├── stock_service.py
│   │   │   ├── invoice_service.py
│   │   │   ├── order_number_service.py
│   │   │   └── email_service.py
│   │   └── utils/
│   │       ├── __init__.py
│   │       └── helpers.py
│   ├── .env
│   └── requirements.txt
├── frontend/
│   ├── public/
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── index.css
│   │   ├── api/
│   │   │   ├── client.ts
│   │   │   ├── auth.ts
│   │   │   ├── customers.ts
│   │   │   ├── suppliers.ts
│   │   │   ├── products.ts
│   │   │   ├── purchase.ts
│   │   │   ├── sales.ts
│   │   │   ├── payments.ts
│   │   │   ├── stock.ts
│   │   │   └── reports.ts
│   │   ├── components/
│   │   │   ├── layout/
│   │   │   │   ├── AppLayout.tsx
│   │   │   │   ├── Sidebar.tsx
│   │   │   │   ├── TopBar.tsx
│   │   │   │   └── PageHeader.tsx
│   │   │   ├── ui/
│   │   │   │   ├── Button.tsx
│   │   │   │   ├── Input.tsx
│   │   │   │   ├── Select.tsx
│   │   │   │   ├── Modal.tsx
│   │   │   │   ├── Table.tsx
│   │   │   │   ├── Badge.tsx
│   │   │   │   ├── Card.tsx
│   │   │   │   ├── Spinner.tsx
│   │   │   │   ├── EmptyState.tsx
│   │   │   │   └── ConfirmDialog.tsx
│   │   │   └── shared/
│   │   │       ├── SearchableSelect.tsx
│   │   │       ├── DatePicker.tsx
│   │   │       ├── AmountDisplay.tsx
│   │   │       ├── GSTBreakdown.tsx
│   │   │       └── StatusBadge.tsx
│   │   ├── pages/
│   │   │   ├── auth/
│   │   │   │   └── LoginPage.tsx
│   │   │   ├── dashboard/
│   │   │   │   └── DashboardPage.tsx
│   │   │   ├── masters/
│   │   │   │   ├── CompanyPage.tsx
│   │   │   │   ├── CustomersPage.tsx
│   │   │   │   ├── CustomerFormPage.tsx
│   │   │   │   ├── SuppliersPage.tsx
│   │   │   │   ├── SupplierFormPage.tsx
│   │   │   │   ├── ProductsPage.tsx
│   │   │   │   └── ProductFormPage.tsx
│   │   │   ├── inventory/
│   │   │   │   ├── StockPage.tsx
│   │   │   │   └── StockAdjustmentPage.tsx
│   │   │   ├── purchase/
│   │   │   │   ├── PurchaseOrdersPage.tsx
│   │   │   │   ├── PurchaseOrderFormPage.tsx
│   │   │   │   ├── GRNPage.tsx
│   │   │   │   ├── GRNFormPage.tsx
│   │   │   │   ├── PurchaseReturnPage.tsx
│   │   │   │   └── PurchaseReturnFormPage.tsx
│   │   │   ├── sales/
│   │   │   │   ├── QuotationsPage.tsx
│   │   │   │   ├── QuotationFormPage.tsx
│   │   │   │   ├── SalesOrdersPage.tsx
│   │   │   │   ├── SalesOrderFormPage.tsx
│   │   │   │   ├── InvoicesPage.tsx
│   │   │   │   ├── InvoiceFormPage.tsx
│   │   │   │   ├── InvoiceViewPage.tsx
│   │   │   │   └── SalesReturnPage.tsx
│   │   │   ├── payments/
│   │   │   │   ├── ReceivablesPage.tsx
│   │   │   │   └── PayablesPage.tsx
│   │   │   ├── reports/
│   │   │   │   ├── StockReportPage.tsx
│   │   │   │   ├── SalesReportPage.tsx
│   │   │   │   ├── PurchaseReportPage.tsx
│   │   │   │   ├── OutstandingReportPage.tsx
│   │   │   │   ├── GSTReportPage.tsx
│   │   │   │   └── PLReportPage.tsx
│   │   │   └── admin/
│   │   │       └── UsersPage.tsx
│   │   ├── store/
│   │   │   ├── authStore.ts
│   │   │   └── uiStore.ts
│   │   ├── hooks/
│   │   │   ├── useAuth.ts
│   │   │   └── usePermissions.ts
│   │   ├── types/
│   │   │   └── index.ts
│   │   ├── utils/
│   │   │   ├── gst.ts
│   │   │   ├── formatters.ts
│   │   │   └── validators.ts
│   │   └── routes/
│   │       ├── index.tsx
│   │       └── ProtectedRoute.tsx
│   ├── index.html
│   ├── package.json
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   └── vite.config.ts
├── docs/
│   ├── MASTER_SPEC.md          (this file)
│   ├── SETUP.md
│   ├── DATABASE_SCHEMA.md
│   ├── API_REFERENCE.md
│   ├── workflows/
│   │   ├── WF_01_AUTH.md
│   │   ├── WF_02_MASTERS.md
│   │   ├── WF_03_PURCHASE.md
│   │   ├── WF_04_SALES.md
│   │   ├── WF_05_PAYMENTS.md
│   │   └── WF_06_REPORTS.md
│   └── CODING_STANDARDS.md
└── docker-compose.yml
```

---

## 3. Coding Standards (Mandatory — No Exceptions)

### 3.1 General Rules
- No `any` type in TypeScript. Every variable, function parameter, and return type must be explicitly typed.
- No unused imports, variables, or functions anywhere.
- No commented-out code in final files.
- No console.log in production code. Use a logger utility.
- Every API call must have loading, success, and error states handled.
- Every form must validate on submit using Zod schemas.
- No hardcoded strings for labels, statuses, or roles. Use constants files.
- All monetary amounts stored as integers (paise). Display divided by 100.
- All dates stored as ISO 8601 UTC. Display in DD/MM/YYYY format for Indian locale.
- All GST percentages stored as integers: 0, 5, 12, 18, 28.

### 3.2 Backend Rules
- Every router function must have a docstring.
- Every endpoint must have explicit response_model.
- All database operations must go through service layer, not directly in routers.
- Use dependency injection for database sessions and current user.
- All exceptions must use HTTPException with appropriate status codes.
- Soft deletes only: never hard delete any record. Use is_deleted boolean + deleted_at timestamp.
- Every model must have: id (UUID), created_at, updated_at, is_deleted, created_by (user id).

### 3.3 Frontend Rules
- All API calls in /api/ files only. No fetch/axios calls inside components.
- All server state managed by React Query. No manual useState for server data.
- All client UI state managed by Zustand stores.
- Components must not exceed 200 lines. Extract sub-components if longer.
- Every page must show a loading skeleton while data fetches.
- Every destructive action (delete, cancel) must show a confirmation dialog.
- All number inputs for amounts must prevent negative values.
- Forms must disable submit button while submitting.

### 3.4 UI Standards
- Font: Inter (Google Fonts)
- Color palette: defined in tailwind.config.ts — primary blue (#1E3A5F), accent (#2E86AB), danger (#E8534A), success (#1A7341), warning (#92570A), neutral grays
- Role badge colors must come from design tokens in `tailwind.config.ts` under `colors.role`: `admin`, `accounting`, `sales`, `inventory`.
- Sidebar: white background, 240px fixed width, left-aligned navigation
- TopBar: white, 56px height, breadcrumb + user menu
- Tables: alternating row shading, sticky header, always show total row count
- Forms: two-column grid layout on desktop, single column on mobile
- Spacing: 24px page padding, 16px between form fields, 8px between inline elements
- Buttons: Primary (filled blue), Secondary (outlined), Danger (filled red), Ghost (no border)
- All status values shown as colored badges: Draft=gray, Active=green, Cancelled=red, Pending=amber
- No emojis anywhere in the UI

---

## 4. Environment Variables

### Backend (.env)
```
DATABASE_URL=postgresql://user:password@localhost:5432/inventory_db
SECRET_KEY=your-256-bit-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=480
REFRESH_TOKEN_EXPIRE_DAYS=7
MAIL_USERNAME=your@email.com
MAIL_PASSWORD=your-email-password
MAIL_FROM=noreply@yourcompany.com
MAIL_PORT=587
MAIL_SERVER=smtp.gmail.com
MAIL_STARTTLS=true
MAIL_SSL_TLS=false
FRONTEND_URL=http://localhost:5173
COMPANY_NAME=Your Company Name
```

Note: Database migrations are managed from `project-root/database/`.
Note: Alembic config in `project-root/database/alembic/` must read `DATABASE_URL` from `backend/.env` (single runtime source of truth).

### Frontend (.env)
```
VITE_API_BASE_URL=http://localhost:8000
```

---

## 5. Database Schema — Complete

### 5.1 Users Table
```sql
CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  full_name VARCHAR(150) NOT NULL,
  email VARCHAR(255) UNIQUE NOT NULL,
  hashed_password VARCHAR(255) NOT NULL,
  role VARCHAR(20) NOT NULL CHECK (role IN ('admin','accounting','sales','inventory')),
  permission_overrides JSONB,
  is_active BOOLEAN DEFAULT TRUE,
  is_deleted BOOLEAN DEFAULT FALSE,
  deleted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  created_by UUID REFERENCES users(id)
);
```
Note: `permission_overrides` stores per-user module access overrides set by admin. Role permissions remain the default baseline.

### 5.2 Company Table
```sql
CREATE TABLE company (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name VARCHAR(255) NOT NULL,
  legal_name VARCHAR(255),
  gstin VARCHAR(15) UNIQUE,
  pan VARCHAR(10),
  address_line1 VARCHAR(255),
  address_line2 VARCHAR(255),
  city VARCHAR(100),
  state VARCHAR(100),
  state_code VARCHAR(5),
  pincode VARCHAR(10),
  phone VARCHAR(15),
  email VARCHAR(255),
  website VARCHAR(255),
  logo_url VARCHAR(500),
  bank_name VARCHAR(150),
  bank_account_no VARCHAR(50),
  bank_ifsc VARCHAR(20),
  bank_branch VARCHAR(150),
  invoice_prefix VARCHAR(10) DEFAULT 'INV',
  invoice_counter INTEGER DEFAULT 1,
  po_prefix VARCHAR(10) DEFAULT 'PO',
  po_counter INTEGER DEFAULT 1,
  so_prefix VARCHAR(10) DEFAULT 'SO',
  so_counter INTEGER DEFAULT 1,
  qtn_prefix VARCHAR(10) DEFAULT 'QTN',
  qtn_counter INTEGER DEFAULT 1,
  grn_prefix VARCHAR(10) DEFAULT 'GRN',
  grn_counter INTEGER DEFAULT 1,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
```
Note: Only one row exists in this table ever. Admin manages it.

### 5.3 Customers Table
```sql
CREATE TABLE customers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  customer_code VARCHAR(20) UNIQUE NOT NULL,
  company_name VARCHAR(255) NOT NULL,
  contact_person VARCHAR(150),
  email VARCHAR(255),
  phone VARCHAR(15) NOT NULL,
  alternate_phone VARCHAR(15),
  gstin VARCHAR(15),
  pan VARCHAR(10),
  customer_type VARCHAR(20) DEFAULT 'regular' CHECK (customer_type IN ('regular','dealer','distributor','retail')),
  billing_address_line1 VARCHAR(255),
  billing_address_line2 VARCHAR(255),
  billing_city VARCHAR(100),
  billing_state VARCHAR(100),
  billing_state_code VARCHAR(5),
  billing_pincode VARCHAR(10),
  shipping_address_line1 VARCHAR(255),
  shipping_address_line2 VARCHAR(255),
  shipping_city VARCHAR(100),
  shipping_state VARCHAR(100),
  shipping_state_code VARCHAR(5),
  shipping_pincode VARCHAR(10),
  same_as_billing BOOLEAN DEFAULT TRUE,
  credit_limit INTEGER DEFAULT 0,
  payment_terms_days INTEGER DEFAULT 30,
  opening_balance INTEGER DEFAULT 0,
  opening_balance_type VARCHAR(2) DEFAULT 'dr' CHECK (opening_balance_type IN ('dr','cr')),
  is_active BOOLEAN DEFAULT TRUE,
  is_deleted BOOLEAN DEFAULT FALSE,
  deleted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  created_by UUID REFERENCES users(id)
);
```
Note: All monetary amounts in paise (1 INR = 100 paise).

### 5.4 Suppliers Table
```sql
CREATE TABLE suppliers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  supplier_code VARCHAR(20) UNIQUE NOT NULL,
  company_name VARCHAR(255) NOT NULL,
  contact_person VARCHAR(150),
  email VARCHAR(255),
  phone VARCHAR(15) NOT NULL,
  alternate_phone VARCHAR(15),
  gstin VARCHAR(15),
  pan VARCHAR(10),
  address_line1 VARCHAR(255),
  address_line2 VARCHAR(255),
  city VARCHAR(100),
  state VARCHAR(100),
  state_code VARCHAR(5),
  pincode VARCHAR(10),
  bank_name VARCHAR(150),
  bank_account_no VARCHAR(50),
  bank_ifsc VARCHAR(20),
  payment_terms_days INTEGER DEFAULT 30,
  opening_balance INTEGER DEFAULT 0,
  opening_balance_type VARCHAR(2) DEFAULT 'cr' CHECK (opening_balance_type IN ('dr','cr')),
  is_active BOOLEAN DEFAULT TRUE,
  is_deleted BOOLEAN DEFAULT FALSE,
  deleted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  created_by UUID REFERENCES users(id)
);
```

### 5.5 Product Categories Table
```sql
CREATE TABLE product_categories (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name VARCHAR(150) UNIQUE NOT NULL,
  description TEXT,
  is_active BOOLEAN DEFAULT TRUE,
  is_deleted BOOLEAN DEFAULT FALSE,
  deleted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  created_by UUID REFERENCES users(id)
);
```

### 5.6 Units of Measure Table
```sql
CREATE TABLE units_of_measure (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name VARCHAR(50) NOT NULL,
  abbreviation VARCHAR(10) UNIQUE NOT NULL,
  is_active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
-- Seed data: PCS, KG, G, LTR, ML, BOX, PACK, MTR, SQM, NOS
```

### 5.7 Products Table
```sql
CREATE TABLE products (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  product_code VARCHAR(30) UNIQUE NOT NULL,
  sku VARCHAR(50) UNIQUE,
  name VARCHAR(255) NOT NULL,
  description TEXT,
  category_id UUID REFERENCES product_categories(id),
  uom_id UUID NOT NULL REFERENCES units_of_measure(id),
  alt_uom_id UUID REFERENCES units_of_measure(id),
  alt_uom_conversion NUMERIC(10,4),
  hsn_code VARCHAR(10) NOT NULL,
  gst_rate INTEGER NOT NULL CHECK (gst_rate IN (0,5,12,18,28)),
  purchase_price INTEGER DEFAULT 0,
  selling_price INTEGER DEFAULT 0,
  mrp INTEGER DEFAULT 0,
  minimum_stock INTEGER DEFAULT 0,
  opening_stock INTEGER DEFAULT 0,
  is_active BOOLEAN DEFAULT TRUE,
  is_deleted BOOLEAN DEFAULT FALSE,
  deleted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  created_by UUID REFERENCES users(id)
);
```

### 5.8 Stock Ledger Table
```sql
CREATE TABLE stock_ledger (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  product_id UUID NOT NULL REFERENCES products(id),
  transaction_type VARCHAR(20) NOT NULL CHECK (transaction_type IN ('opening','purchase','sale','purchase_return','sale_return','adjustment')),
  reference_type VARCHAR(20),
  reference_id UUID,
  reference_number VARCHAR(50),
  quantity NUMERIC(12,4) NOT NULL,
  rate INTEGER NOT NULL,
  transaction_date DATE NOT NULL,
  notes TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  created_by UUID REFERENCES users(id)
);
```
Note: quantity is positive for inward (purchase, sale_return, opening, adjustment_in) and negative for outward (sale, purchase_return, adjustment_out).

### 5.9 Current Stock View (Materialized)
```sql
CREATE MATERIALIZED VIEW current_stock AS
SELECT
  p.id AS product_id,
  p.product_code,
  p.name AS product_name,
  p.hsn_code,
  p.gst_rate,
  p.minimum_stock,
  p.mrp,
  p.selling_price,
  u.abbreviation AS uom,
  COALESCE(SUM(sl.quantity), 0) AS current_quantity
FROM products p
LEFT JOIN stock_ledger sl ON sl.product_id = p.id
LEFT JOIN units_of_measure u ON u.id = p.uom_id
WHERE p.is_deleted = FALSE
GROUP BY p.id, p.product_code, p.name, p.hsn_code, p.gst_rate, p.minimum_stock, p.mrp, p.selling_price, u.abbreviation;

CREATE UNIQUE INDEX ON current_stock (product_id);
```
Note: Refresh this view after every stock transaction using: `REFRESH MATERIALIZED VIEW CONCURRENTLY current_stock;`

### 5.10 Purchase Orders Table
```sql
CREATE TABLE purchase_orders (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  po_number VARCHAR(30) UNIQUE NOT NULL,
  supplier_id UUID NOT NULL REFERENCES suppliers(id),
  order_date DATE NOT NULL,
  expected_delivery_date DATE,
  status VARCHAR(20) DEFAULT 'draft' CHECK (status IN ('draft','sent','partial','received','cancelled')),
  subtotal INTEGER DEFAULT 0,
  total_discount INTEGER DEFAULT 0,
  total_taxable_amount INTEGER DEFAULT 0,
  total_cgst INTEGER DEFAULT 0,
  total_sgst INTEGER DEFAULT 0,
  total_igst INTEGER DEFAULT 0,
  total_gst INTEGER DEFAULT 0,
  total_amount INTEGER DEFAULT 0,
  notes TEXT,
  is_deleted BOOLEAN DEFAULT FALSE,
  deleted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  created_by UUID REFERENCES users(id)
);
```

### 5.11 Purchase Order Items Table
```sql
CREATE TABLE purchase_order_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  purchase_order_id UUID NOT NULL REFERENCES purchase_orders(id) ON DELETE CASCADE,
  product_id UUID NOT NULL REFERENCES products(id),
  description VARCHAR(255),
  quantity NUMERIC(12,4) NOT NULL,
  unit_price INTEGER NOT NULL,
  discount_percent NUMERIC(5,2) DEFAULT 0,
  discount_amount INTEGER DEFAULT 0,
  taxable_amount INTEGER NOT NULL,
  gst_rate INTEGER NOT NULL,
  cgst_amount INTEGER DEFAULT 0,
  sgst_amount INTEGER DEFAULT 0,
  igst_amount INTEGER DEFAULT 0,
  total_amount INTEGER NOT NULL,
  received_quantity NUMERIC(12,4) DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 5.12 Goods Receipt Notes Table
```sql
CREATE TABLE goods_receipt_notes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  grn_number VARCHAR(30) UNIQUE NOT NULL,
  purchase_order_id UUID REFERENCES purchase_orders(id),
  supplier_id UUID NOT NULL REFERENCES suppliers(id),
  supplier_invoice_number VARCHAR(50),
  supplier_invoice_date DATE,
  receipt_date DATE NOT NULL,
  status VARCHAR(20) DEFAULT 'draft' CHECK (status IN ('draft','confirmed','cancelled')),
  subtotal INTEGER DEFAULT 0,
  total_discount INTEGER DEFAULT 0,
  total_taxable_amount INTEGER DEFAULT 0,
  total_cgst INTEGER DEFAULT 0,
  total_sgst INTEGER DEFAULT 0,
  total_igst INTEGER DEFAULT 0,
  total_gst INTEGER DEFAULT 0,
  total_amount INTEGER DEFAULT 0,
  notes TEXT,
  is_deleted BOOLEAN DEFAULT FALSE,
  deleted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  created_by UUID REFERENCES users(id)
);
```

### 5.13 GRN Items Table
```sql
CREATE TABLE grn_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  grn_id UUID NOT NULL REFERENCES goods_receipt_notes(id) ON DELETE CASCADE,
  product_id UUID NOT NULL REFERENCES products(id),
  purchase_order_item_id UUID REFERENCES purchase_order_items(id),
  quantity NUMERIC(12,4) NOT NULL,
  unit_price INTEGER NOT NULL,
  discount_percent NUMERIC(5,2) DEFAULT 0,
  discount_amount INTEGER DEFAULT 0,
  taxable_amount INTEGER NOT NULL,
  gst_rate INTEGER NOT NULL,
  cgst_amount INTEGER DEFAULT 0,
  sgst_amount INTEGER DEFAULT 0,
  igst_amount INTEGER DEFAULT 0,
  total_amount INTEGER NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 5.14 Purchase Returns Table
```sql
CREATE TABLE purchase_returns (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  return_number VARCHAR(30) UNIQUE NOT NULL,
  grn_id UUID REFERENCES goods_receipt_notes(id),
  supplier_id UUID NOT NULL REFERENCES suppliers(id),
  return_date DATE NOT NULL,
  reason TEXT,
  status VARCHAR(20) DEFAULT 'draft' CHECK (status IN ('draft','confirmed','cancelled')),
  subtotal INTEGER DEFAULT 0,
  total_gst INTEGER DEFAULT 0,
  total_amount INTEGER DEFAULT 0,
  is_deleted BOOLEAN DEFAULT FALSE,
  deleted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  created_by UUID REFERENCES users(id)
);
```

### 5.15 Purchase Return Items Table
```sql
CREATE TABLE purchase_return_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  purchase_return_id UUID NOT NULL REFERENCES purchase_returns(id) ON DELETE CASCADE,
  product_id UUID NOT NULL REFERENCES products(id),
  quantity NUMERIC(12,4) NOT NULL,
  unit_price INTEGER NOT NULL,
  taxable_amount INTEGER NOT NULL,
  gst_rate INTEGER NOT NULL,
  cgst_amount INTEGER DEFAULT 0,
  sgst_amount INTEGER DEFAULT 0,
  igst_amount INTEGER DEFAULT 0,
  total_amount INTEGER NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 5.16 Quotations Table
```sql
CREATE TABLE quotations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  quotation_number VARCHAR(30) UNIQUE NOT NULL,
  customer_id UUID NOT NULL REFERENCES customers(id),
  quotation_date DATE NOT NULL,
  valid_until DATE,
  status VARCHAR(20) DEFAULT 'draft' CHECK (status IN ('draft','sent','accepted','rejected','expired','converted')),
  sold_to_party_id UUID REFERENCES customers(id),
  bill_to_party_id UUID REFERENCES customers(id),
  ship_to_party_id UUID REFERENCES customers(id),
  subtotal INTEGER DEFAULT 0,
  total_discount INTEGER DEFAULT 0,
  total_taxable_amount INTEGER DEFAULT 0,
  total_cgst INTEGER DEFAULT 0,
  total_sgst INTEGER DEFAULT 0,
  total_igst INTEGER DEFAULT 0,
  total_gst INTEGER DEFAULT 0,
  total_amount INTEGER DEFAULT 0,
  notes TEXT,
  terms_conditions TEXT,
  is_deleted BOOLEAN DEFAULT FALSE,
  deleted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  created_by UUID REFERENCES users(id)
);
```

### 5.17 Quotation Items Table
```sql
CREATE TABLE quotation_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  quotation_id UUID NOT NULL REFERENCES quotations(id) ON DELETE CASCADE,
  product_id UUID NOT NULL REFERENCES products(id),
  description VARCHAR(255),
  quantity NUMERIC(12,4) NOT NULL,
  unit_price INTEGER NOT NULL,
  discount_percent NUMERIC(5,2) DEFAULT 0,
  discount_amount INTEGER DEFAULT 0,
  taxable_amount INTEGER NOT NULL,
  gst_rate INTEGER NOT NULL,
  cgst_amount INTEGER DEFAULT 0,
  sgst_amount INTEGER DEFAULT 0,
  igst_amount INTEGER DEFAULT 0,
  total_amount INTEGER NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 5.18 Sales Orders Table
```sql
CREATE TABLE sales_orders (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  so_number VARCHAR(30) UNIQUE NOT NULL,
  quotation_id UUID REFERENCES quotations(id),
  customer_id UUID NOT NULL REFERENCES customers(id),
  order_date DATE NOT NULL,
  expected_delivery_date DATE,
  status VARCHAR(20) DEFAULT 'draft' CHECK (status IN ('draft','confirmed','partial','fulfilled','cancelled')),
  sold_to_party_id UUID REFERENCES customers(id),
  bill_to_party_id UUID REFERENCES customers(id),
  ship_to_party_id UUID REFERENCES customers(id),
  subtotal INTEGER DEFAULT 0,
  total_discount INTEGER DEFAULT 0,
  total_taxable_amount INTEGER DEFAULT 0,
  total_cgst INTEGER DEFAULT 0,
  total_sgst INTEGER DEFAULT 0,
  total_igst INTEGER DEFAULT 0,
  total_gst INTEGER DEFAULT 0,
  total_amount INTEGER DEFAULT 0,
  notes TEXT,
  terms_conditions TEXT,
  is_deleted BOOLEAN DEFAULT FALSE,
  deleted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  created_by UUID REFERENCES users(id)
);
```

### 5.19 Sales Order Items Table
```sql
CREATE TABLE sales_order_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  sales_order_id UUID NOT NULL REFERENCES sales_orders(id) ON DELETE CASCADE,
  product_id UUID NOT NULL REFERENCES products(id),
  description VARCHAR(255),
  quantity NUMERIC(12,4) NOT NULL,
  unit_price INTEGER NOT NULL,
  discount_percent NUMERIC(5,2) DEFAULT 0,
  discount_amount INTEGER DEFAULT 0,
  taxable_amount INTEGER NOT NULL,
  gst_rate INTEGER NOT NULL,
  cgst_amount INTEGER DEFAULT 0,
  sgst_amount INTEGER DEFAULT 0,
  igst_amount INTEGER DEFAULT 0,
  total_amount INTEGER NOT NULL,
  fulfilled_quantity NUMERIC(12,4) DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 5.20 Sales Invoices Table
```sql
CREATE TABLE sales_invoices (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  invoice_number VARCHAR(30) UNIQUE NOT NULL,
  sales_order_id UUID REFERENCES sales_orders(id),
  quotation_id UUID REFERENCES quotations(id),
  customer_id UUID NOT NULL REFERENCES customers(id),
  invoice_date DATE NOT NULL,
  due_date DATE,
  status VARCHAR(20) DEFAULT 'draft' CHECK (status IN ('draft','issued','partial_paid','paid','cancelled')),
  sold_to_customer_id UUID REFERENCES customers(id),
  bill_to_customer_id UUID NOT NULL REFERENCES customers(id),
  ship_to_customer_id UUID REFERENCES customers(id),
  supply_state VARCHAR(100),
  supply_state_code VARCHAR(5),
  is_igst BOOLEAN DEFAULT FALSE,
  subtotal INTEGER DEFAULT 0,
  total_discount INTEGER DEFAULT 0,
  total_taxable_amount INTEGER DEFAULT 0,
  total_cgst INTEGER DEFAULT 0,
  total_sgst INTEGER DEFAULT 0,
  total_igst INTEGER DEFAULT 0,
  total_gst INTEGER DEFAULT 0,
  total_amount INTEGER DEFAULT 0,
  amount_paid INTEGER DEFAULT 0,
  amount_due INTEGER DEFAULT 0,
  notes TEXT,
  terms_conditions TEXT,
  pdf_url VARCHAR(500),
  is_deleted BOOLEAN DEFAULT FALSE,
  deleted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  created_by UUID REFERENCES users(id)
);
```

### 5.21 Sales Invoice Items Table
```sql
CREATE TABLE sales_invoice_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  invoice_id UUID NOT NULL REFERENCES sales_invoices(id) ON DELETE CASCADE,
  product_id UUID NOT NULL REFERENCES products(id),
  description VARCHAR(255),
  quantity NUMERIC(12,4) NOT NULL,
  unit_price INTEGER NOT NULL,
  mrp INTEGER,
  discount_percent NUMERIC(5,2) DEFAULT 0,
  discount_amount INTEGER DEFAULT 0,
  taxable_amount INTEGER NOT NULL,
  gst_rate INTEGER NOT NULL,
  cgst_amount INTEGER DEFAULT 0,
  sgst_amount INTEGER DEFAULT 0,
  igst_amount INTEGER DEFAULT 0,
  total_amount INTEGER NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 5.22 Sales Returns Table
```sql
CREATE TABLE sales_returns (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  return_number VARCHAR(30) UNIQUE NOT NULL,
  invoice_id UUID NOT NULL REFERENCES sales_invoices(id),
  customer_id UUID NOT NULL REFERENCES customers(id),
  return_date DATE NOT NULL,
  reason TEXT,
  status VARCHAR(20) DEFAULT 'draft' CHECK (status IN ('draft','confirmed','cancelled')),
  subtotal INTEGER DEFAULT 0,
  total_gst INTEGER DEFAULT 0,
  total_amount INTEGER DEFAULT 0,
  is_deleted BOOLEAN DEFAULT FALSE,
  deleted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  created_by UUID REFERENCES users(id)
);
```

### 5.23 Sales Return Items Table
```sql
CREATE TABLE sales_return_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  sales_return_id UUID NOT NULL REFERENCES sales_returns(id) ON DELETE CASCADE,
  product_id UUID NOT NULL REFERENCES products(id),
  invoice_item_id UUID REFERENCES sales_invoice_items(id),
  quantity NUMERIC(12,4) NOT NULL,
  unit_price INTEGER NOT NULL,
  taxable_amount INTEGER NOT NULL,
  gst_rate INTEGER NOT NULL,
  cgst_amount INTEGER DEFAULT 0,
  sgst_amount INTEGER DEFAULT 0,
  igst_amount INTEGER DEFAULT 0,
  total_amount INTEGER NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 5.24 Payments Table
```sql
CREATE TABLE payments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  payment_number VARCHAR(30) UNIQUE NOT NULL,
  payment_type VARCHAR(10) NOT NULL CHECK (payment_type IN ('receipt','payment')),
  party_type VARCHAR(10) NOT NULL CHECK (party_type IN ('customer','supplier')),
  customer_id UUID REFERENCES customers(id),
  supplier_id UUID REFERENCES suppliers(id),
  payment_date DATE NOT NULL,
  amount INTEGER NOT NULL,
  payment_mode VARCHAR(20) NOT NULL CHECK (payment_mode IN ('cash','bank_transfer','cheque','upi','card')),
  reference_number VARCHAR(100),
  cheque_date DATE,
  bank_name VARCHAR(150),
  notes TEXT,
  status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending','cleared','bounced','cancelled')),
  is_deleted BOOLEAN DEFAULT FALSE,
  deleted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  created_by UUID REFERENCES users(id)
);
```

### 5.25 Payment Allocations Table
```sql
CREATE TABLE payment_allocations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  payment_id UUID NOT NULL REFERENCES payments(id),
  invoice_id UUID REFERENCES sales_invoices(id),
  purchase_grn_id UUID REFERENCES goods_receipt_notes(id),
  allocated_amount INTEGER NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 6. Role-Based Access Control Matrix

| Permission | Admin | Accounting | Sales | Inventory |
|---|---|---|---|---|
| Company profile | Full | Read | None | None |
| User management | Full | None | None | None |
| Customer master | Full | Read | Full | Read |
| Supplier master | Full | Read | None | Full |
| Product master | Full | None | Read | Full |
| Categories & UoM | Full | None | None | Full |
| Purchase orders | Full | Read | None | Full |
| GRN | Full | Read | None | Full |
| Purchase returns | Full | Read | None | Full |
| Stock ledger | Full | Read | Read | Full |
| Stock adjustment | Full | None | None | Full |
| Quotations | Full | Read | Full | None |
| Sales orders | Full | Read | Full | Read |
| Sales invoices | Full | Read | Full | None |
| Sales returns | Full | Read | Full | None |
| Payments (receipt) | Full | Full | None | None |
| Payments (payment) | Full | Full | None | None |
| Reports — all | Full | Full | Sales only | Stock only |
| Dashboard | Full | Full | Full | Full |

### 6.1 User-Level Module Access Overrides
- Admin can allow/deny module access for any non-admin user from Users management.
- Effective permissions = role baseline + per-user overrides (`permission_overrides`).
- Admin can reset a user back to role defaults by clearing all overrides.
- Overrides cannot grant access to admin-only modules (`Company`, `Users`) unless the user role is `admin`.
- All permission checks (frontend + backend) must use effective permissions, not role alone.

---

## 7. GST Calculation Logic

This is the most critical business logic. Implement exactly as described.

### 7.1 Determine IGST vs CGST/SGST
- Compare company's state_code with customer's billing state_code (for sales) or supplier's state_code (for purchases).
- If state codes are different: apply IGST = full GST rate on taxable amount.
- If state codes are same: apply CGST = GST rate / 2, SGST = GST rate / 2, each on taxable amount.

### 7.2 Item-Level Calculation (all amounts in paise)
```
unit_price = selling price per unit (in paise)
quantity = numeric value
gross_amount = ROUND(unit_price * quantity)
discount_amount = ROUND(gross_amount * discount_percent / 100)
taxable_amount = gross_amount - discount_amount
gst_amount = ROUND(taxable_amount * gst_rate / 100)

if IGST:
  igst_amount = gst_amount
  cgst_amount = 0
  sgst_amount = 0
else:
  cgst_amount = ROUND(taxable_amount * (gst_rate / 2) / 100)
  sgst_amount = ROUND(taxable_amount * (gst_rate / 2) / 100)
  igst_amount = 0

total_amount = taxable_amount + gst_amount
```

### 7.3 Invoice-Level Totals
```
subtotal = SUM(gross_amount) for all items
total_discount = SUM(discount_amount) for all items
total_taxable_amount = SUM(taxable_amount) for all items
total_cgst = SUM(cgst_amount) for all items
total_sgst = SUM(sgst_amount) for all items
total_igst = SUM(igst_amount) for all items
total_gst = total_cgst + total_sgst + total_igst
total_amount = total_taxable_amount + total_gst
```

### 7.4 Rounding Rule
Always use Python's `round()` or JS's `Math.round()`. Never use floor or ceil for GST calculations. Store in paise. Display as rupees with 2 decimal places.

---

## 8. Order Number Generation Logic

All order numbers are generated by order_number_service.py using a database transaction to prevent duplicates.

```python
def generate_number(db, entity: str) -> str:
    # entity: 'invoice' | 'po' | 'so' | 'qtn' | 'grn' | 'payment' | 'return'
    company = db.query(Company).with_for_update().first()
    prefix_map = {
        'invoice': (company.invoice_prefix, 'invoice_counter'),
        'po': (company.po_prefix, 'po_counter'),
        'so': (company.so_prefix, 'so_counter'),
        'qtn': (company.qtn_prefix, 'qtn_counter'),
        'grn': (company.grn_prefix, 'grn_counter'),
    }
    prefix, counter_field = prefix_map[entity]
    counter = getattr(company, counter_field)
    number = f"{prefix}-{str(counter).zfill(5)}"  # e.g. INV-00001
    setattr(company, counter_field, counter + 1)
    db.commit()
    return number
```

---

## 9. Stock Service Logic

### 9.1 Adding Stock (GRN Confirmation)
```python
def add_stock(db, grn_id, items):
    for item in items:
        ledger_entry = StockLedger(
            product_id=item.product_id,
            transaction_type='purchase',
            reference_type='grn',
            reference_id=grn_id,
            reference_number=grn_number,
            quantity=item.quantity,  # positive
            rate=item.unit_price,
            transaction_date=grn.receipt_date,
        )
        db.add(ledger_entry)
    db.commit()
    db.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY current_stock")
```

### 9.2 Deducting Stock (Invoice Confirmation)
```python
def deduct_stock(db, invoice_id, items):
    for item in items:
        current = db.execute(
            "SELECT current_quantity FROM current_stock WHERE product_id = :pid",
            {"pid": item.product_id}
        ).fetchone()
        if current.current_quantity < item.quantity:
            raise HTTPException(400, f"Insufficient stock for product {item.product_id}")
        ledger_entry = StockLedger(
            product_id=item.product_id,
            transaction_type='sale',
            reference_type='invoice',
            reference_id=invoice_id,
            quantity=-item.quantity,  # negative for outward
            rate=item.unit_price,
            transaction_date=invoice.invoice_date,
        )
        db.add(ledger_entry)
    db.commit()
    db.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY current_stock")
```

### 9.3 Stock Check Before Sales Order Confirmation
- When a sales order is confirmed (status changes to 'confirmed'), check each item's current_quantity >= item.quantity.
- If any item fails, reject the entire confirmation and return which products are short.

---

## 10. API Routes — Complete Reference

### Authentication
```
POST   /api/v1/auth/login              Body: {email, password} → {access_token, refresh_token, user}
POST   /api/v1/auth/refresh            Body: {refresh_token} → {access_token}
POST   /api/v1/auth/logout             Header: Bearer token
GET    /api/v1/auth/me                 → current user object with effective access
```

`user` response shape for `/auth/login` and `/auth/me`:
```json
{
  "id": "uuid",
  "full_name": "",
  "email": "",
  "role": "admin|accounting|sales|inventory",
  "permission_overrides": { "allow": [], "deny": [] },
  "effective_access": [],
  "force_password_change": false
}
```

### Company
```
GET    /api/v1/company                 → company object
PUT    /api/v1/company                 Admin only → updated company
POST   /api/v1/company/logo            Admin only, multipart → {logo_url}
```

### Users (Admin only)
```
GET    /api/v1/users                   → list of users
POST   /api/v1/users                   → created user
GET    /api/v1/users/{id}              → user
PUT    /api/v1/users/{id}              → updated user
PATCH  /api/v1/users/{id}/permissions  Body: {allow: string[], deny: string[]} → updated effective access
DELETE /api/v1/users/{id}/permissions  → clears overrides and reverts user to role-default access
DELETE /api/v1/users/{id}              Soft delete
```

### Customers
```
GET    /api/v1/customers               Query: search, is_active, page, page_size → paginated list
POST   /api/v1/customers               → created customer
GET    /api/v1/customers/{id}          → customer with balance summary
PUT    /api/v1/customers/{id}          → updated customer
DELETE /api/v1/customers/{id}          Soft delete (block if outstanding > 0)
GET    /api/v1/customers/{id}/ledger   → list of transactions
GET    /api/v1/customers/{id}/balance  → {total_invoiced, total_paid, balance_due}
```

### Suppliers
```
GET    /api/v1/suppliers               Query: search, is_active, page, page_size → paginated list
POST   /api/v1/suppliers               → created supplier
GET    /api/v1/suppliers/{id}          → supplier
PUT    /api/v1/suppliers/{id}          → updated supplier
DELETE /api/v1/suppliers/{id}          Soft delete
GET    /api/v1/suppliers/{id}/ledger   → list of transactions
GET    /api/v1/suppliers/{id}/balance  → {total_purchased, total_paid, balance_due}
```

### Products
```
GET    /api/v1/products                Query: search, category_id, is_active, page, page_size → paginated list with current_stock
POST   /api/v1/products                → created product
GET    /api/v1/products/{id}           → product with current_stock
PUT    /api/v1/products/{id}           → updated product
DELETE /api/v1/products/{id}           Soft delete (block if current_stock > 0)
GET    /api/v1/products/categories     → list of categories
POST   /api/v1/products/categories     → created category
GET    /api/v1/products/uom            → list of units of measure
```

### Purchase Orders
```
GET    /api/v1/purchase-orders         Query: supplier_id, status, from_date, to_date, page, page_size
POST   /api/v1/purchase-orders         → created PO (status=draft)
GET    /api/v1/purchase-orders/{id}    → PO with items
PUT    /api/v1/purchase-orders/{id}    Only if status=draft
PATCH  /api/v1/purchase-orders/{id}/status   Body: {status} → updated (draft→sent, sent→cancelled)
```

### Goods Receipt Notes
```
GET    /api/v1/grn                     Query: supplier_id, po_id, status, from_date, to_date, page, page_size
POST   /api/v1/grn                     → created GRN (status=draft), can reference PO
GET    /api/v1/grn/{id}                → GRN with items
PUT    /api/v1/grn/{id}                Only if status=draft
POST   /api/v1/grn/{id}/confirm        Confirms GRN → adds stock → refreshes materialized view → updates PO status
POST   /api/v1/grn/{id}/cancel         Only if status=draft
```

### Purchase Returns
```
GET    /api/v1/purchase-returns        Query: supplier_id, from_date, to_date, page, page_size
POST   /api/v1/purchase-returns        Body includes grn_id and items → created return (status=draft)
GET    /api/v1/purchase-returns/{id}   → return with items
POST   /api/v1/purchase-returns/{id}/confirm   Confirms → deducts stock → refreshes view
POST   /api/v1/purchase-returns/{id}/cancel    Only if status=draft
```

### Quotations
```
GET    /api/v1/quotations              Query: customer_id, status, from_date, to_date, page, page_size
POST   /api/v1/quotations              → created quotation (status=draft)
GET    /api/v1/quotations/{id}         → quotation with items
PUT    /api/v1/quotations/{id}         Only if status in (draft, sent)
POST   /api/v1/quotations/{id}/convert-to-so   → creates sales order, sets quotation status=converted
PATCH  /api/v1/quotations/{id}/status  Body: {status}
```

### Sales Orders
```
GET    /api/v1/sales-orders            Query: customer_id, status, from_date, to_date, page, page_size
POST   /api/v1/sales-orders            → created SO (status=draft)
GET    /api/v1/sales-orders/{id}       → SO with items
PUT    /api/v1/sales-orders/{id}       Only if status=draft
POST   /api/v1/sales-orders/{id}/confirm   Validates stock → confirms SO
POST   /api/v1/sales-orders/{id}/convert-to-invoice → creates invoice (full/partial); sets SO status=partial or fulfilled based on fulfilled quantities
POST   /api/v1/sales-orders/{id}/cancel   Only if status in (draft, confirmed)
```

### Sales Invoices
```
GET    /api/v1/invoices                Query: customer_id, status, from_date, to_date, page, page_size
POST   /api/v1/invoices                → created invoice (status=draft)
GET    /api/v1/invoices/{id}           → invoice with items and payment history
PUT    /api/v1/invoices/{id}           Only if status=draft
POST   /api/v1/invoices/{id}/issue     Issues invoice → deducts stock → refreshes view → generates PDF
POST   /api/v1/invoices/{id}/cancel    Only if status in (draft, issued) and no payments
GET    /api/v1/invoices/{id}/pdf       Returns PDF file
POST   /api/v1/invoices/{id}/send-email   Body: {to_email, cc_email} → sends invoice PDF by email
```

### Sales Returns
```
GET    /api/v1/sales-returns           Query: customer_id, invoice_id, from_date, to_date, page, page_size
POST   /api/v1/sales-returns           Body includes invoice_id and items → status=draft
GET    /api/v1/sales-returns/{id}      → return with items
POST   /api/v1/sales-returns/{id}/confirm   Confirms → adds stock back → refreshes view
POST   /api/v1/sales-returns/{id}/cancel    Only if status=draft
```

### Payments
```
GET    /api/v1/payments                Query: party_type, customer_id, supplier_id, status, from_date, to_date, page, page_size
POST   /api/v1/payments                Body: {payment_type, party_type, party_id, amount, payment_mode, allocations[]}
GET    /api/v1/payments/{id}           → payment with allocations
PATCH  /api/v1/payments/{id}/status    Body: {status} → cleared, bounced, cancelled
```

### Stock
```
GET    /api/v1/stock                   Query: search, category_id, low_stock_only → current stock list
GET    /api/v1/stock/{product_id}/ledger   Query: from_date, to_date → transaction history
POST   /api/v1/stock/adjust            Body: {product_id, quantity, type(in/out), reason} → stock adjustment
```

### Reports
```
GET    /api/v1/reports/stock           Query: as_of_date, category_id, low_stock_only
GET    /api/v1/reports/sales           Query: from_date, to_date, customer_id, group_by(day/month/customer/product)
GET    /api/v1/reports/purchase        Query: from_date, to_date, supplier_id, group_by
GET    /api/v1/reports/outstanding-receivables   Query: as_of_date, customer_id
GET    /api/v1/reports/outstanding-payables      Query: as_of_date, supplier_id
GET    /api/v1/reports/gstr1           Query: from_date, to_date → GSTR-1 formatted data
GET    /api/v1/reports/gstr3b          Query: from_date, to_date → GSTR-3B summary
GET    /api/v1/reports/pl              Query: from_date, to_date → Profit & Loss
GET    /api/v1/reports/dashboard       → dashboard summary object
```

---

## 11. Dashboard API Response Shape

```json
{
  "today_sales": 0,
  "month_sales": 0,
  "outstanding_receivables": 0,
  "outstanding_payables": 0,
  "low_stock_count": 0,
  "overdue_invoices_count": 0,
  "sales_trend": [
    { "date": "2024-01-01", "amount": 0 }
  ],
  "top_products": [
    { "product_name": "", "quantity_sold": 0, "amount": 0 }
  ],
  "recent_invoices": [
    { "invoice_number": "", "customer_name": "", "amount": 0, "status": "", "date": "" }
  ]
}
```

---

## 12. PDF Invoice Structure

The PDF invoice must include all of the following sections in order:

1. Header: Company logo (left), Company name + address + GSTIN (center/right)
2. Invoice title: "TAX INVOICE" in large font, Invoice Number, Invoice Date, Due Date
3. Party details (two columns): Bill To (left), Ship To (right) — each with name, address, GSTIN
4. Items table: Sr, Description, HSN, Qty, Unit, Rate, Disc%, Taxable, GST%, GST Amt, Total
5. Totals section: Subtotal, Total Discount, Total Taxable, CGST/SGST or IGST breakdown per rate, Grand Total
6. Amount in words: "Rupees [amount in words] Only"
7. Bank details: Bank Name, Account No, IFSC, Branch
8. Notes and Terms & Conditions
9. Footer: "This is a computer-generated invoice. No signature required."

---

## 13. Frontend Route Map

```
/login                          → LoginPage (public)
/                               → redirect to /dashboard
/dashboard                      → DashboardPage

/masters/company                → CompanyPage (admin only)
/masters/users                  → UsersPage (admin only)
/masters/customers              → CustomersPage
/masters/customers/new          → CustomerFormPage
/masters/customers/:id/edit     → CustomerFormPage
/masters/suppliers              → SuppliersPage
/masters/suppliers/new          → SupplierFormPage
/masters/suppliers/:id/edit     → SupplierFormPage
/masters/products               → ProductsPage
/masters/products/new           → ProductFormPage
/masters/products/:id/edit      → ProductFormPage

/inventory/stock                → StockPage
/inventory/adjust               → StockAdjustmentPage

/purchase/orders                → PurchaseOrdersPage
/purchase/orders/new            → PurchaseOrderFormPage
/purchase/orders/:id            → PurchaseOrderFormPage (view/edit)
/purchase/grn                   → GRNPage
/purchase/grn/new               → GRNFormPage
/purchase/grn/:id               → GRNFormPage (view/edit)
/purchase/returns               → PurchaseReturnPage
/purchase/returns/new           → PurchaseReturnFormPage

/sales/quotations               → QuotationsPage
/sales/quotations/new           → QuotationFormPage
/sales/quotations/:id           → QuotationFormPage (view/edit)
/sales/orders                   → SalesOrdersPage
/sales/orders/new               → SalesOrderFormPage
/sales/orders/:id               → SalesOrderFormPage (view/edit)
/sales/invoices                 → InvoicesPage
/sales/invoices/new             → InvoiceFormPage
/sales/invoices/:id             → InvoiceViewPage
/sales/invoices/:id/edit        → InvoiceFormPage
/sales/returns                  → SalesReturnPage

/payments/receivables           → ReceivablesPage
/payments/payables              → PayablesPage

/reports/stock                  → StockReportPage
/reports/sales                  → SalesReportPage
/reports/purchase               → PurchaseReportPage
/reports/outstanding            → OutstandingReportPage
/reports/gst                    → GSTReportPage
/reports/pl                     → PLReportPage
```

---

## 14. Sidebar Navigation by Role

```
Dashboard          — all roles

Masters
  Company          — admin only
  Users            — admin only
  Customers        — admin, accounting, sales
  Suppliers        — admin, accounting, inventory
  Products         — admin, inventory

Inventory
  Current Stock    — admin, inventory, sales (read)
  Adjust Stock     — admin, inventory

Purchase
  Purchase Orders  — admin, inventory
  Goods Receipt    — admin, inventory
  Purchase Returns — admin, inventory

Sales
  Quotations       — admin, sales
  Sales Orders     — admin, sales
  Invoices         — admin, sales
  Sales Returns    — admin, sales

Payments
  Receivables      — admin, accounting
  Payables         — admin, accounting

Reports
  Stock Report     — admin, inventory
  Sales Report     — admin, accounting, sales
  Purchase Report  — admin, accounting
  Outstanding      — admin, accounting
  GST Report       — admin, accounting
  P & L            — admin, accounting

Note: Sidebar visibility must use effective permissions (role + admin overrides).
```

---

## 15. Error Handling

### Backend Error Response Format
```json
{
  "detail": "Human readable error message",
  "error_code": "MACHINE_READABLE_CODE",
  "field_errors": {
    "field_name": ["error message"]
  }
}
```

### Standard Error Codes
- INSUFFICIENT_STOCK — stock quantity too low
- INVALID_GST_RATE — GST rate not in allowed list
- DUPLICATE_GSTIN — GSTIN already registered
- INVOICE_ALREADY_PAID — cannot cancel paid invoice
- INVALID_STATE_TRANSITION — e.g., trying to confirm already-cancelled order
- OUTSTANDING_EXISTS — cannot delete customer/supplier with outstanding balance

### Frontend Error Handling
- 401: clear auth store, redirect to /login
- 403: show "You do not have permission" toast, do not redirect
- 404: show EmptyState component
- 400: show field errors on form fields using React Hook Form setError()
- 500: show generic "Something went wrong" toast with support message

---

## 16. State Transitions

### Sales Invoice
```
draft → issued (on /issue endpoint, deducts stock)
draft → cancelled
issued → partial_paid (when partial payment received)
issued → paid (when full payment received)
partial_paid → paid (when remaining payment received)
issued → cancelled (only if amount_paid = 0)
```

### Sales Order
```
draft → confirmed (validates stock)
confirmed → partial (first invoice created from SO)
confirmed → fulfilled (if first invoice fully covers all items)
partial → fulfilled (when remaining items are fully invoiced)
draft → cancelled
confirmed → cancelled (restores no stock, just status change)
```

### Quotation
```
draft → sent
sent → accepted
sent → rejected
accepted → converted (when SO created from it)
draft/sent → expired (if valid_until date passes)
```

### GRN
```
draft → confirmed (adds stock)
draft → cancelled
```

### Purchase Order
```
draft → sent
sent → partial (first GRN received)
partial → received (all items GRN'd)
sent → cancelled
draft → cancelled
```

---

## 17. Seed Data Required

On first run (empty database), the system must seed:

1. One default admin user: email=admin@company.com, password=Admin@123 (force change on first login)
2. Units of measure: PCS, KG, G, LTR, ML, BOX, PACK, MTR, NOS
3. Default product category: General
4. One company row with placeholder data (admin fills in via Company settings)

---

## 18. Important Implementation Notes

1. The `current_stock` materialized view must be refreshed (CONCURRENTLY) after every stock transaction. Do this inside the service function after committing the stock_ledger rows.
2. All order number generation must use `SELECT ... FOR UPDATE` on the company table to prevent race conditions.
3. A sales invoice cannot be issued if any line item has quantity > current available stock at time of issue.
4. When converting a quotation to a sales order, copy all line items exactly. Do not modify the quotation.
5. When converting a sales order to an invoice, copy selected quantities and update `fulfilled_quantity` at item level. Set SO status to `partial` or `fulfilled` based on completion.
6. `effective_access` returned from auth APIs is authoritative for frontend route guards and sidebar visibility.
7. Role overrides can be reset by clearing `permission_overrides`; access reverts to role defaults.
8. Alembic commands run from `project-root/database/`; backend runtime continues to own DB session configuration.
9. A GRN can be created with or without a purchase order reference.
10. GST IGST/CGST+SGST split is determined at invoice creation time by comparing the company's state_code with the bill_to customer's state_code.
11. All paginated list endpoints return: `{ items: [...], total: int, page: int, page_size: int, pages: int }`.
12. The PDF is generated server-side on invoice issue and stored. GET /pdf returns the stored file. Do not regenerate on every request.
13. Email delivery is fire-and-forget. A failure to send email must not fail the invoice issue operation. Log the error.
14. The frontend must show a low-stock warning banner on the stock page for any product where current_quantity <= minimum_stock.
15. Reports must support CSV export in addition to screen display.
