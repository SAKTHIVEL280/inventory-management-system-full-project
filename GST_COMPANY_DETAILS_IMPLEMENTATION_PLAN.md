# GST Reports Company Details Implementation Plan

## Overview
Add company details (logo, name, address, GSTIN, phone) to all GST reports (PDF & Excel) following the same pattern as invoice PDFs.

## Implementation Steps

### 1. Backend Changes

#### A. Helper Functions (Add to reports.py)
```python
def _get_company_details(db: Session) -> dict:
    """Fetch company details for GST reports."""
    from app.models.company import Company
    company = db.query(Company).first()
    
    if not company:
        return {
            "name": "N/A",
            "address": "N/A",
            "gstin": "N/A",
            "phone": "N/A",
            "logo_src": None,
            "ambassador_logo_src": None,
        }
    
    # Build address
    address_parts = [
        getattr(company, "address_line1", ""),
        getattr(company, "address_line2", ""),
        getattr(company, "city", ""),
        getattr(company, "state", ""),
        getattr(company, "country", ""),
        getattr(company, "pincode", ""),
    ]
    address = ", ".join([p.strip() for p in address_parts if p and p.strip()])
    
    return {
        "name": getattr(company, "name", "N/A") or "N/A",
        "address": address or "N/A",
        "gstin": getattr(company, "gstin", "N/A") or "N/A",
        "phone": getattr(company, "phone", "N/A") or "N/A",
        "logo_src": _resolve_company_logo_for_pdf(company),
        "ambassador_logo_src": _resolve_ambassador_logo_for_pdf(company),
    }

def _resolve_company_logo_for_pdf(company) -> str | None:
    """Resolve company logo to data URI for PDF embedding."""
    # Use same logic as pdf_service.py
    pass

def _resolve_ambassador_logo_for_pdf(company) -> str | None:
    """Resolve ambassador logo to data URI for PDF embedding."""
    # Use same logic as pdf_service.py
    pass
```

#### B. GSTR-1 Export Enhancement

**Excel Changes:**
- Add company details at the top (rows 1-5)
- Add company name, address, GSTIN, phone
- Shift existing content down

**PDF Changes:**
- Add company logo in header
- Add company details block
- Add ambassador logo as watermark (low opacity background)

#### C. GSTR-2 Export Enhancement
Same as GSTR-1

#### D. GST Reconciliation Export Enhancement
Same as GSTR-1

### 2. Files to Modify

1. `backend/app/routers/reports.py`
   - Add helper functions for company details
   - Modify `gstr1_export()` - Excel section
   - Modify `gstr1_export()` - PDF section
   - Modify `gstr2_export()` - Excel section
   - Modify `gstr2_export()` - PDF section
   - Modify `gst_reconciliation_export()` - Excel section
   - Modify `gst_reconciliation_export()` - PDF section

2. `backend/app/services/pdf_service.py`
   - Export helper functions if needed (or keep in reports.py)

### 3. Excel Format

```
Row 1: [Company Name]
Row 2: [Address]
Row 3: GSTIN: [GSTIN Number]
Row 4: Phone: [Phone Number]
Row 5: [Empty]
Row 6: [Report Title]
Row 7: [Period Info]
Row 8: [Empty]
Row 9: [Headers]
Row 10+: [Data rows]
```

### 4. PDF Format

```
┌─────────────────────────────────────────┐
│ [Logo]  Company Name                    │
│         Address                         │
│         GSTIN: XXXXX                    │
│         Phone: XXXXX                    │
├─────────────────────────────────────────┤
│ Report Title                            │
│ Period: XXX to XXX | Frequency: XXX    │
├─────────────────────────────────────────┤
│ [Table with data]                       │
└─────────────────────────────────────────┘

Background: [Ambassador Logo - Low Opacity]
```

### 5. Testing Checklist

- [ ] GSTR-1 Excel shows company details
- [ ] GSTR-1 PDF shows company logo and details
- [ ] GSTR-1 PDF has ambassador watermark
- [ ] GSTR-2 Excel shows company details
- [ ] GSTR-2 PDF shows company logo and details
- [ ] GSTR-2 PDF has ambassador watermark
- [ ] GST Reconciliation Excel shows company details
- [ ] GST Reconciliation PDF shows company logo and details
- [ ] GST Reconciliation PDF has ambassador watermark
- [ ] Company details match invoice format
- [ ] Logo resolution is good
- [ ] Watermark opacity is subtle

### 6. Task Tracking

**Task**: BE-127  
**Description**: Add company details to GST reports (PDF & Excel)  
**Priority**: MEDIUM  
**Impact**: Improves GST report branding and professionalism

