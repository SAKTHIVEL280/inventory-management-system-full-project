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
- **BE-152**: Fixed RDN stock: added "returned" to sales status filter to prevent dropped deductions.
- **BE-153**: Fixed negative stock in Inventory: restored RDN batch accumulation, clamped negative qty/MRP to zero.
