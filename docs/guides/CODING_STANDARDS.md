# Coding Standards

These rules are non-negotiable. Every file in this codebase must comply.

---

## 1. TypeScript Rules

### No `any` Type
```typescript
// Wrong
const data: any = response.data;

// Correct
const data: InvoiceResponse = response.data;
```

### Explicit Return Types on All Functions
```typescript
// Wrong
function calculateGST(amount, rate) {
  return Math.round(amount * rate / 100);
}

// Correct
function calculateGST(amount: number, rate: number): number {
  return Math.round(amount * rate / 100);
}
```

### Interfaces for All API Shapes
All request and response shapes must be defined in `/src/types/index.ts`.

---

## 2. React Component Rules

### File Naming
- Pages: `PascalCase` ending in `Page.tsx` — e.g., `InvoiceFormPage.tsx`
- Components: `PascalCase` — e.g., `GSTBreakdown.tsx`
- Hooks: `camelCase` starting with `use` — e.g., `usePermissions.ts`
- API files: `camelCase` — e.g., `invoices.ts`

### Component Size
- Maximum 200 lines per component file.
- If a component grows beyond 200 lines, extract sub-components.

### No Direct API Calls in Components
```typescript
// Wrong — fetch inside component
const MyPage = () => {
  useEffect(() => {
    axios.get('/api/v1/products').then(setProducts);
  }, []);
};

// Correct — use React Query with API layer
const MyPage = () => {
  const { data, isLoading } = useProducts();
};
```

### Every Page Needs Loading and Error States
```typescript
const InvoicesPage = () => {
  const { data, isLoading, isError } = useInvoices();

  if (isLoading) return <PageSkeleton />;
  if (isError) return <ErrorState message="Failed to load invoices" />;
  if (!data?.items.length) return <EmptyState message="No invoices yet" />;

  return <InvoiceTable data={data.items} />;
};
```

---

## 3. Form Rules

### Always Use React Hook Form + Zod
```typescript
const schema = z.object({
  customer_id: z.string().uuid('Select a customer'),
  invoice_date: z.string().min(1, 'Invoice date is required'),
  items: z.array(z.object({
    product_id: z.string().uuid(),
    quantity: z.number().positive('Quantity must be greater than 0'),
  })).min(1, 'Add at least one item'),
});

type InvoiceFormData = z.infer<typeof schema>;
```

### Disable Submit While Submitting
```typescript
<Button type="submit" disabled={isSubmitting}>
  {isSubmitting ? 'Saving...' : 'Save Invoice'}
</Button>
```

### Show Validation Errors Inline
```typescript
<Input
  {...register('phone')}
  error={errors.phone?.message}
/>
```

---

## 4. Amount Handling Rules

All amounts are stored in the database as paise (integers). The UI must always divide by 100 for display and multiply by 100 before sending to the API.

```typescript
// Display
const displayAmount = (paise: number): string => {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
  }).format(paise / 100);
};

// Before API call (when user types in rupees)
const toApi = (rupees: number): number => Math.round(rupees * 100);

// After API response (for form pre-fill)
const fromApi = (paise: number): number => paise / 100;
```

---

## 5. Date Handling Rules

All dates from the API are ISO 8601 strings. Display using DD/MM/YYYY format.

```typescript
const formatDate = (isoDate: string): string => {
  const d = new Date(isoDate);
  return d.toLocaleDateString('en-IN', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  });
};

// HTML input type="date" expects YYYY-MM-DD
const toInputDate = (isoDate: string): string => isoDate.split('T')[0];
```

---

## 6. API Client Pattern

All API functions return typed promises. Errors are thrown to be caught by React Query.

```typescript
// api/invoices.ts
import { apiClient } from './client';
import type { Invoice, CreateInvoiceRequest, PaginatedResponse } from '../types';

export const invoicesApi = {
  list: (params: InvoiceListParams): Promise<PaginatedResponse<Invoice>> =>
    apiClient.get('/invoices', { params }).then(r => r.data),

  get: (id: string): Promise<Invoice> =>
    apiClient.get(`/invoices/${id}`).then(r => r.data),

  create: (data: CreateInvoiceRequest): Promise<Invoice> =>
    apiClient.post('/invoices', data).then(r => r.data),

  issue: (id: string): Promise<Invoice> =>
    apiClient.post(`/invoices/${id}/issue`).then(r => r.data),
};
```

---

## 7. Backend Rules

### Service Layer Pattern
```python
# routers/invoices.py — only calls service, no business logic
@router.post("/", response_model=InvoiceResponse)
async def create_invoice(
    payload: CreateInvoiceRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new draft invoice."""
    return invoice_service.create_invoice(db, payload, current_user.id)

# services/invoice_service.py — all business logic here
def create_invoice(db: Session, payload: CreateInvoiceRequest, user_id: UUID) -> Invoice:
    invoice_number = order_number_service.generate_number(db, 'invoice')
    # ... rest of logic
```

### Soft Delete Pattern
```python
# NEVER hard-delete. Always use soft delete:
user.is_deleted = True
user.deleted_at = datetime.utcnow()
db.commit()

# Always filter in queries:
users = db.query(User).filter(User.is_deleted == False).all()
```

### Every Model Field Correctly Typed
- Booleans: `Column(Boolean, default=True)`
- Money: `Column(Integer)` (paise/cents)
- Decimals: `Column(Numeric(12, 4))` (for quantities)
- Dates: `Column(Date)` or `Column(DateTime(timezone=True))`
- UUIDs: `Column(UUID(as_uuid=True), primary_key=True, default=uuid4)`
- Enums: `Column(Enum(...))` NOT strings

---

## 8. Error Handling Pattern

```python
# routers/any_router.py
from fastapi import HTTPException

@router.post("/")
def create_item(payload: CreateRequest, db: Session = Depends(get_db)):
    # Validation
    if not payload.customer_id:
        raise HTTPException(400, "Customer ID is required")
    
    # Business logic
    customer = db.query(Customer).filter_by(id=payload.customer_id).first()
    if not customer:
        raise HTTPException(404, "Customer not found")
    
    if customer.is_deleted:
        raise HTTPException(400, "Customer has been deleted")
    
    # Success
    item = ...
    db.add(item)
    db.commit()
    db.refresh(item)
    return item
```

---

## 9. Import Organization

### Frontend Imports (Alphabetic, Grouped)
```typescript
// External packages
import axios from 'axios';
import { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';

// Internal modules
import { usePermissions } from '@/hooks/usePermissions';
import { authStore } from '@/store/auth';
import type { Invoice } from '@/types';
```

### Backend Imports (Alphabetic, Grouped)
```python
from datetime import datetime
from uuid import UUID
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.invoice import Invoice
from app.services.invoice_service import create_invoice
```

---

## 10. Testing Requirements

### Unit Tests Required For:
- All service functions
- Utility/helper functions
- Complex business logic

### Integration Tests Required For:
- All API endpoints (success + error cases)
- Database state transitions
- Payment allocation logic

### Example (Backend)
```python
# tests/test_create_invoice.py
def test_create_invoice_success(db):
    customer = create_test_customer(db)
    payload = CreateInvoiceRequest(customer_id=customer.id, items=[...])
    invoice = invoice_service.create_invoice(db, payload, admin_user_id)
    assert invoice.status == "draft"
    assert invoice.invoice_number.startswith("INV-")

def test_create_invoice_insufficient_stock(db):
    customer = create_test_customer(db)
    payload = CreateInvoiceRequest(customer_id=customer.id, items=[...])
    with pytest.raises(HTTPException) as exc:
        invoice_service.create_invoice(db, payload, admin_user_id)
    assert exc.value.status_code == 400
```

---

## 11. Documentation Requirements

### Every API Endpoint Must Have a Docstring
```python
@router.post("/", response_model=InvoiceResponse)
def create_invoice(
    payload: CreateInvoiceRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new draft invoice for a customer.
    
    - Only users with 'create_invoice' permission can call this.
    - Items are required; each must have valid product_id, quantity > 0.
    - Returns invoice in draft status with no stock deducted.
    - To issue invoice (deduct stock, generate PDF), use /invoices/{id}/issue.
    
    Args:
        payload: Invoice creation request with items
        db: Database session
        current_user: Currently authenticated user
    
    Returns:
        Invoice object with invoice_number and all line items
    
    Raises:
        HTTPException 404: Customer not found
        HTTPException 400: Insufficient data or invalid items
    """
    ...
```

### Every Complex Function Must Have Comments
```python
def allocate_payment(db: Session, payment: Payment, invoices: list[Invoice]):
    """Allocate payment amount to invoices in order (oldest first priority)."""
    remaining = payment.amount
    
    # Sort by invoice_date ascending (oldest first)
    sorted_invoices = sorted(invoices, key=lambda x: x.invoice_date)
    
    for invoice in sorted_invoices:
        if remaining <= 0:
            break
        
        # Calculate how much to allocate to this invoice
        due = invoice.amount_due
        allocated = min(remaining, due)
        
        # Create allocation record
        allocation = PaymentAllocation(
            payment_id=payment.id,
            invoice_id=invoice.id,
            allocated_amount=allocated
        )
        db.add(allocation)
        remaining -= allocated
    
    db.commit()
```

---

## 12. Naming Conventions

### Functions and Variables
```typescript
// Functions: camelCase, verb-first
function calculateGST() {}
function formatCurrency() {}
function isValidEmail() {}
const isLoading = true;
const hasPermission = false;
```

### Constants
```typescript
// SCREAMING_SNAKE_CASE for constants
const GST_RATES = [0, 5, 12, 18, 28];
const DEFAULT_PAGE_SIZE = 25;
const ROLES = ['admin', 'accounting', 'sales', 'inventory'];
```

### Database & API
```python
# Database tables: snake_case (already in schema)
# API endpoints: lowercase with hyphens
GET /api/v1/customers
POST /api/v1/purchase-orders
GET /api/v1/sales-invoices?status=draft
```

---

## 13. Commit Message Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:** feat, fix, docs, style, refactor, test, chore

**Example:**
```
feat(invoices): Add GST breakdown display on invoice form

- Calculate IGST vs CGST+SGST based on state codes
- Show tax breakdown in real-time as items are added
- Store tax amounts separately in invoice_items table

Fixes #123
```

---

## 14. Branch Naming

```
feature/invoice-pdf-generation
fix/payment-allocation-bug
docs/update-api-reference
chore/upgrade-dependencies
```

---

## 15. Code Review Checklist

Before submitting a PR, ensure:

- [ ] No `any` types anywhere
- [ ] All functions have explicit return types
- [ ] No console.log or debug code
- [ ] No unused imports or variables
- [ ] Components under 200 lines
- [ ] All API calls go through `/api` layer
- [ ] Forms use React Hook Form + Zod
- [ ] Service layer used for all business logic
- [ ] Soft deletes used (never hard delete)
- [ ] Tests written and passing
- [ ] Documentation updated
- [ ] Commit messages follow format
- [ ] No secrets or credentials in code

---

**Last Updated:** March 25, 2026  
**Version:** 1.0
