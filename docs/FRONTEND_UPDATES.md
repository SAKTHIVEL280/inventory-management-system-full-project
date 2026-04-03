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
