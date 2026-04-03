# Application Updates Tracker

## How to Use This File

This is the master tracker for feature-level updates across the application.

Use `CHANGES.md` for:
- Feature title and date
- Completion status
- Short summary of what changed
- Links to detailed layer-specific updates in:
   - `docs/BACKEND_UPDATES.md`
   - `docs/FRONTEND_UPDATES.md`
   - `docs/DATABASE_UPDATES.md`

Do not put deep implementation details here. Keep those in docs files.

## Maintenance Rules

For each new feature or bug fix:
1. Add one new section in `CHANGES.md` with status and summary.
2. Update the relevant section inside docs files (backend/frontend/database).
3. In `CHANGES.md`, link to the exact docs sections you updated.
4. Do not duplicate large code snippets in `CHANGES.md`.

---

## Company Module - Director & GSTIN Features
**Date**: April 3, 2026
**Status**: ✅ Completed

### Overview
Implementation of Company module enhancements:
1. ✅ Add Company Director Name field (optional)
2. ✅ Add Company Director Contact field (optional)
3. ✅ Add GSTIN Registration Status toggle (Registered/Non-Registered)

---

## Backend Changes
See [BACKEND_UPDATES.md](./docs/BACKEND_UPDATES.md)

**Status**: ✅ COMPLETED

### Changes Made:
1. **Model** (`backend/app/models/company.py`):
   - Added `gstin_status` field (String, default='non-registered')
   - Added `company_director_name` field (String, nullable)
   - Added `company_director_contact` field (String, nullable)

2. **Schema** (`backend/app/schemas/company.py`):
   - Added `gstin_status: str = 'non-registered'`
   - Added `company_director_name: Optional[str] = None`
   - Added `company_director_contact: Optional[str] = None`

---

## Frontend Changes
See [FRONTEND_UPDATES.md](./docs/FRONTEND_UPDATES.md)

**Status**: ✅ COMPLETED

### Changes Made:
1. **Types** (`frontend/src/types/index.ts`):
   - Added `gstin_status?: string` to Company interface
   - Added `company_director_name?: string | null` to Company interface
   - Added `company_director_contact?: string | null` to Company interface

2. **CompanyPage Component** (`frontend/src/pages/CompanyPage.tsx`):
   - Updated form schema to include 3 new fields
   - Added form initialization for new fields
   - Added watch hook to track `gstin_status` changes
   - Added UI form fields for Director Name and Contact
   - Added GSTIN Status toggle (Registered/Non-Registered)
   - Added conditional display for GSTIN field:
     - Shows input when "Registered" is selected
     - Shows "NA" when "Non-Registered" is selected
   - Updated payload preparation in onSubmit

---

## Database Changes
See [DATABASE_UPDATES.md](./docs/DATABASE_UPDATES.md)

**Status**: ✅ Migration Created (Pending Execution)

### SQL Script Created:
- **File**: `database/ALL_UPDATES.sql`
- **Contains**: ALTER TABLE statements to add 3 new columns
- **Backward Compatible**: Yes - all new columns are nullable/have defaults

---

## Testing Checklist

### Company Module Features
- [ ] Company Director Name field displays and saves
- [ ] Company Director Contact field displays and saves
- [ ] GSTIN toggle appears in Company settings
- [ ] Registered mode: GSTIN input field appears
- [ ] Non-Registered mode: GSTIN field shows "NA"
- [ ] GSTIN value persists on save
- [ ] Form validation works correctly
- [ ] Data persists on page reload
- [ ] API endpoints return new fields

---

## Implementation Timeline
- Database Migration: ✅ Created (`database/ALL_UPDATES.sql`)
- Backend Model Update: ✅ Completed
- Backend Schema Update: ✅ Completed
- Frontend Form Update: ✅ Completed
- Frontend Types Update: ✅ Completed
- Testing: ⏳ Pending

---

## Files Modified

### Backend
- `backend/app/models/company.py` - Added 3 new columns
- `backend/app/schemas/company.py` - Added 3 new fields

### Frontend
- `frontend/src/types/index.ts` - Added 3 new properties to Company interface
- `frontend/src/pages/CompanyPage.tsx` - Added form fields and conditional logic

### Database
- `database/ALL_UPDATES.sql` - Migration script (NEW)

### Documentation
- `docs/BACKEND_UPDATES.md` - Backend implementation docs (NEW)
- `docs/FRONTEND_UPDATES.md` - Frontend implementation docs (NEW)
- `docs/DATABASE_UPDATES.md` - Database migration docs (NEW)
- `CHANGES.md` - This file (tracking all changes)

---

## Dashboard Module - Cash In Flow Graph
**Date**: April 3, 2026
**Status**: ✅ Completed

### Overview
Implemented dashboard chart replacement and period-based cash in flow graph:
1. ✅ Replaced Top Selling Products graph with Cash In Flow Graph
2. ✅ Added Daily view for cash in flow
3. ✅ Added Weekly view for cash in flow
4. ✅ Added Monthly view for cash in flow
5. ✅ Set Y-axis label to Receivables Amount
6. ✅ Set X-axis label to Customers

### Backend Changes
See [BACKEND_UPDATES.md](./docs/BACKEND_UPDATES.md) - section: Dashboard Module - Cash In Flow Graph

### Frontend Changes
See [FRONTEND_UPDATES.md](./docs/FRONTEND_UPDATES.md) - section: Dashboard Module - Cash In Flow Graph

### Database Changes
See [DATABASE_UPDATES.md](./docs/DATABASE_UPDATES.md) - section: Dashboard Module - Cash In Flow Graph

### Files Modified for Dashboard Feature

#### Backend
- `backend/app/routers/reports.py` - Added `cash_in_flow` response data (daily/weekly/monthly)

#### Frontend
- `frontend/src/pages/DashboardPage.tsx` - Replaced chart widget and added view selector
- `frontend/src/api/reports.ts` - Added `cash_in_flow` typing in DashboardStats

#### Database
- No schema/table changes required

#### Documentation
- `docs/BACKEND_UPDATES.md` - Added Dashboard section: Cash In Flow Graph
- `docs/FRONTEND_UPDATES.md` - Added Dashboard section: Cash In Flow Graph
- `docs/DATABASE_UPDATES.md` - Added Dashboard section: Cash In Flow Graph

