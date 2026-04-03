# Frontend Updates - Company Module Enhancements

**Date**: April 3, 2026

## Changes Made

### 1. Frontend Types (`frontend/src/types/index.ts`)
**Changes**:
- Added `company_director_name?: string` to Company type
- Added `company_director_contact?: string` to Company type
- Added `gstin_status: string` to Company type

---

### 2. CompanyPage Form Schema (`frontend/src/pages/CompanyPage.tsx`)
**Location**: Zod schema object

**Changes**:
- Added `company_director_name: z.string().optional()`
- Added `company_director_contact: z.string().optional()`
- Added `gstin_status: z.string().optional()`

---

### 3. CompanyPage Form Values (`frontend/src/pages/CompanyPage.tsx`)
**Location**: useForm initialization

**Changes** to form values:
```typescript
company_director_name: data?.company_director_name ?? '',
company_director_contact: data?.company_director_contact ?? '',
gstin_status: data?.gstin_status ?? 'non-registered',
```

---

### 4. CompanyPage Form Fields (`frontend/src/pages/CompanyPage.tsx`)
**New Form Fields Added**:

#### Field 1: Company Director Name
- Label: "Company Director Name"
- Type: text input
- Required: No (optional)
- Placeholder: "e.g., John Doe"

#### Field 2: Company Director Contact
- Label: "Company Director Contact"
- Type: text input
- Required: No (optional)
- Placeholder: "e.g., +91-9876543210"

#### Field 3: GSTIN Status Toggle
- Label: "GSTIN Registration Status"
- Type: Toggle/Radio buttons
- Options: "Registered" / "Non-Registered"
- Default: "Non-Registered"

---

### 5. Conditional GSTIN Field (`frontend/src/pages/CompanyPage.tsx`)
**Logic**:
```typescript
if (gstin_status === 'registered') {
  // Show GSTIN input field (required)
} else {
  // Show "NA" placeholder
}
```

**Display Rules**:
- If `gstin_status` = "registered": Show required GSTIN input
- If `gstin_status` = "non-registered": Show "NA" as read-only text

---

## UI Layout Changes

### Form Section Order
1. Company Name (existing)
2. Legal Name (existing)
3. **Company Director Name (NEW)**
4. **Company Director Contact (NEW)**
5. **GSTIN Status Toggle (NEW)**
6. GSTIN Field (modified with conditional display)
7. PAN, Email, Phone, etc. (existing)

---

## Testing Checklist

- [ ] Director Name field displays and accepts input
- [ ] Director Contact field displays and accepts input
- [ ] GSTIN Status toggle displays correctly
- [ ] Toggle between "Registered" and "Non-Registered" works
- [ ] GSTIN field appears when "Registered" is selected
- [ ] GSTIN field is required when "Registered" is selected
- [ ] "NA" displays when "Non-Registered" is selected
- [ ] Form submission includes all new fields
- [ ] Data persists on page reload

---

## Dashboard Module - Cash In Flow Graph (Section Updated)

### 6. Dashboard API Types (`frontend/src/api/reports.ts`)
**Changes**:
- Added `cash_in_flow` type in `DashboardStats`:
  - `daily`
  - `weekly`
  - `monthly`

Each item contains:
- `customer_id`
- `customer_name`
- `receivables_amount`

### 7. Dashboard Graph Widget (`frontend/src/pages/DashboardPage.tsx`)
**Changes**:
- Replaced "Top Selling Products" widget with "Cash In Flow Graph"
- Added period selector buttons:
  - Daily
  - Weekly
  - Monthly
- Bound graph data to `stats.cash_in_flow[selectedView]`

### 8. Dashboard Axes (Updated)
**Y-Axis**:
- Label: `Receivables Amount`

**X-Axis**:
- Label: `Customers`
- Values: customer name (fallback to customer ID prefix)

### 9. Dashboard Feature Validation
- [ ] Cash In Flow graph is displayed instead of Top Selling Products
- [ ] Daily selection shows daily data
- [ ] Weekly selection shows weekly data
- [ ] Monthly selection shows monthly data
- [ ] Y-axis label is `Receivables Amount`
- [ ] X-axis label is `Customers`

---

## Customer Module - Requested Features (Section Updated)

### 10. Customer Form Fields (`frontend/src/pages/CustomersPage.tsx`)
- Added optional fields:
  - Company Director Name
  - Company Director Contact
- Added GSTIN status toggle:
  - Registered
  - Non-Registered
- GSTIN behavior:
  - Registered: GSTIN input shown and validated
  - Non-Registered: GSTIN shows `NA`
- Added `Country` field in Billing Address section.
- Added `Business Type` dropdown with `Domestic` and `International` options.

### 11. Customer ID Prefix Auto-Fill
- Added read-only Customer ID preview that auto-updates based on selected state/country/business type.
- Preview format:
  - Domestic: `CUST-[STATE CODE]-XXXXX`
  - International: `CUST-INT-XXXXX`

### 12. Company Profile Address Defaults
- New customer form auto-prefills billing address from Company Profile data when available.

### 13. Frontend API/Type Updates
- `frontend/src/types/index.ts`: customer type expanded with new fields.
- `frontend/src/api/customers.ts`: payload types updated for new customer fields.

### 14. Validation Checklist
- [ ] Director Name field is optional
- [ ] Director Contact field is optional
- [ ] GSTIN toggle works for Registered/Non-Registered
- [ ] Country field is selectable
- [ ] Customer ID preview prefix updates from state/country
- [ ] Business Type dropdown shows Domestic/International

---

## Supplier Module - Requested Features (Section Updated)

### 15. Supplier Form Fields (`frontend/src/pages/SuppliersPage.tsx`)
- Added optional fields:
  - Company Director Name
  - Company Director Contact
- Added GSTIN status toggle:
  - Registered
  - Non-Registered
- GSTIN behavior:
  - Registered: GSTIN input shown and validated
  - Non-Registered: GSTIN shows `NA`
- Added `Business Type` dropdown with `Domestic` and `International` options.

### 16. Billing Address Section
- Added billing address block with customer-like structure:
  - Address line 1
  - Address line 2
  - City
  - State (controlled dropdown)
  - State Code
  - Pincode
  - Country

### 17. Supplier Code Prefix Auto-Fill
- Added read-only Supplier Code preview that auto-updates based on selected state/country/business type.
- Preview format:
  - Domestic: `SUPP-[STATE CODE]-XXXXX`
  - International: `SUPP-INT-XXXXX`

### 18. Frontend API/Type Updates
- `frontend/src/types/index.ts`: supplier type expanded with new fields.
- `frontend/src/api/suppliers.ts`: payload types updated for new supplier fields.

### 19. Validation Checklist
- [ ] Director Name field is optional
- [ ] Director Contact field is optional
- [ ] GSTIN toggle works for Registered/Non-Registered
- [ ] Billing address structure matches customer module pattern
- [ ] Supplier Code preview prefix updates from state/country
- [ ] Business Type dropdown shows Domestic/International

---

## Products Master - Requested Features (Section Updated)

### 20. Product Form UI Changes (`frontend/src/pages/ProductsPage.tsx`)
- Removed `Minimum Stock` field from product form.
- Renamed `Safety Stock` label to `Min Safety Stock`.
- Renamed `SKU` label to `Base Unit` and made it mandatory.
- Renamed `Unit of Measure` label to `Order Unit/Packing` (optional).

### 21. Mapping and Calculation
- Added order-unit to base-unit conversion capture via `Base Unit Qty`.
- Purchase price is now auto-calculated as:
  - `Price × Base Unit Qty`
- Purchase Price is shown as read-only computed value.

### 22. Form Validations
- Enforced:
  - Purchase Price < Selling Price
  - Selling Price < MRP

### 23. Product Status and Messages
- Product status chips now show `In Stock` and `Low Stock` (instead of `OK`).
- Create/modify success now uses toast notifications:
  - `Product created successfully`
  - `Product modified successfully`
- Removed duplicate inline success rendering to avoid repeated success popup messages.
