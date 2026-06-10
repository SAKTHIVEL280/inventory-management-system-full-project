# Backend Updates Log (New Session)

**Started**: May 9, 2026

---

- **BE-132**: Added `company_id` to Supplier model for multi-tenant isolation.
- **BE-133**: Added `company_id` to PurchaseOrder, GoodsReceiptNote, PurchaseReturn models.
- **BE-134**: Added `company_id` to Quotation, SalesOrder, SalesInvoice, SalesReturn models.
- **BE-135**: Added `company_id` to Payment model.
- **BE-136**: Added `company_id` to StockLedger model.
- **BE-137**: Added `company_id` to InventoryCount, InventoryCountDifferenceAudit models.
- **BE-138**: Created `get_current_company_id()` and `scope_query_to_company()` in dependencies.py.
- **BE-139**: Updated `log_audit_event()` to accept, auto-resolve, and store `company_id`.
- **BE-140**: Suppliers router — company_id scoping on queries and create.
- **BE-141**: Purchase router — company_id scoping on PO/GRN/Return queries and create.
- **BE-142**: Sales router — company_id scoping on Quotation/SO/Invoice/Return queries and create.
- **BE-143**: Payments router — company_id scoping on queries and create.
- **BE-144**: Stock router — company_id scoping on InventoryCount queries and create.
- **BE-145**: Reports router — company_id scoping on dashboard, sales, and action log queries.
- **BE-146**: Compliance router — company_id scoping on export/anonymize queries.
- **BE-147**: Archive router — company_id scoping on archive stats and purge queries.
- **BE-148**: Audit service auto-resolves company_id from user_id for all existing calls.
- **BE-151**: GST reports allow non-registered GSTIN; invoice totals round down to 0/5 with PDF round-off.
- **BE-152** (Proforma Invoice): New `ProformaInvoice`/`ProformaInvoiceItem` models + schemas; independent replica of Quotation.
- **BE-153** (Proforma Invoice): New `routers/proforma.py` — list/create/get/update/status/archive/restore/PDF/email under `/api/v1/proforma-invoices`; registered in `main.py`.
- **BE-154** (Proforma Invoice): `generate_proforma_invoice_number` (PFI sequence) and `generate_proforma_invoice_pdf` (relabeled clone of quotation PDF).
- **BE-155** (Proforma Invoice): New `proforma_read`/`proforma_write` permissions added to admin and general manager role defaults.
- **BE-156** (Auth/Deploy fix): `routers/auth.py` no longer hardcodes `secure=True`/`samesite="strict"` on auth/CSRF cookies — now honors `settings.cookie_secure`/`settings.cookie_samesite`. Fixes Linux HTTP deployment where browsers dropped `Secure` cookies over plain HTTP, causing `/auth/me`, `/auth/refresh`, `/reports/dashboard` 401s and a "Session expired" login loop. Set `COOKIE_SECURE=false` + `COOKIE_SAMESITE=lax` for HTTP, or terminate TLS and keep `COOKIE_SECURE=true`. Documented new env vars (`ENVIRONMENT`, `FRONTEND_ALLOWED_ORIGINS`, `COOKIE_SECURE`, `COOKIE_SAMESITE`) in `backend/.env.example`.
