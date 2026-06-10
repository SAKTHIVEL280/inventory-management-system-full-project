# Frontend Updates Log (New Session)

**Started**: May 9, 2026

---

- **FE-1**: Invoice form shows 0/5 round-off and rounded grand total.
- **FE-160** (Proforma Invoice): New `api/proforma.ts` client targeting `/api/v2/proforma-invoices`.
- **FE-161** (Proforma Invoice): New `ProformaInvoicesPage.tsx` — replica of Quotations page with Proforma Invoice labels (Number/Date/PDF), PFI numbering, status/search/date filters, create/edit/approve/archive/PDF/email.
- **FE-162** (Proforma Invoice): Route `/sales/proforma-invoices` (+ `/proforma-invoices` redirect) in `App.tsx`; Sales menu item in `AppLayout.tsx`; `PROFORMA_READ`/`PROFORMA_WRITE` scopes in `types/index.ts`.

