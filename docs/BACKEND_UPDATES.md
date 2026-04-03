# Backend Updates - Company Module Enhancements

**Date**: April 3, 2026

## Changes Made

### 1. Company Model (`backend/app/models/company.py`)
**Location**: Lines after `gstin` field

**Changes**:
- Added `company_director_name`: String(255), nullable
- Added `company_director_contact`: String(255), nullable
- Added `gstin_status`: String(20), default='non-registered'

**Code Added**:
```python
company_director_name = Column(String(255), nullable=True)
company_director_contact = Column(String(255), nullable=True)
gstin_status = Column(String(20), nullable=False, default='non-registered')
```

---

### 2. Company Schema (`backend/app/schemas/company.py`)
**Location**: CompanyBase class

**Changes**:
- Added `company_director_name`: Optional[str] = None
- Added `company_director_contact`: Optional[str] = None
- Added `gstin_status`: str = 'non-registered'

**Fields Added**:
```python
company_director_name: Optional[str] = None
company_director_contact: Optional[str] = None
gstin_status: str = 'non-registered'
```

---

## API Behavior

### Endpoints Affected
- `GET /api/company` - Returns new fields
- `PUT /api/company` - Accepts new fields

### Request/Response Example

**Request Body**:
```json
{
  "name": "Acme Corp",
  "company_director_name": "John Doe",
  "company_director_contact": "+91-9876543210",
  "gstin_status": "registered",
  "gstin": "18AABCT1234H1Z0"
}
```

**Response**:
```json
{
  "id": "uuid...",
  "name": "Acme Corp",
  "company_director_name": "John Doe",
  "company_director_contact": "+91-9876543210",
  "gstin_status": "registered",
  "gstin": "18AABCT1234H1Z0",
  ...
}
```

---

## Testing Notes

### Backend Tests to Run
- [ ] GET /api/company returns new fields
- [ ] PUT /api/company accepts and saves new fields
- [ ] GSTIN_status defaults to 'non-registered' when not provided
- [ ] GSTIN validation still works with toggle

---

## Dashboard Module - Cash In Flow Graph (Section Updated)

### 3. Dashboard Report API (`backend/app/routers/reports.py`)
**Location**: `dashboard_report` endpoint

**Changes**:
- Added `cash_in_flow` payload with period buckets:
  - `daily`
  - `weekly`
  - `monthly`
- Added helper `_build_cash_in_flow(start_date)` to aggregate receivables by customer

**Response Added**:
```python
"cash_in_flow": {
    "daily": [...],
    "weekly": [...],
    "monthly": [...],
}
```

**Data Shape**:
- `customer_id`: string
- `customer_name`: string
- `receivables_amount`: integer (paise)

**Aggregation Rules**:
- Source: `SalesInvoice.amount_due`
- Group by: customer
- Filters:
  - invoice date within selected period
  - status in `issued`, `partial_paid`
  - `amount_due > 0`
  - non-deleted customer and invoice rows

**Backward Compatibility**:
- Existing dashboard keys are unchanged
- `top_products` still returned
