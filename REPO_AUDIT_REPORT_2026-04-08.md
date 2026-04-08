# Full Repository Audit Report

Date: 2026-04-08
Repository: inventory-management-system-full-project

## Scope Covered

- Total files scanned: 154
- Total lines scanned: about 47,708
- Areas reviewed:
  - backend (models, routers, schemas, services, config, scripts)
  - frontend (api, store, pages, routing, build config)
  - database SQL scripts
  - environment templates and setup docs
- Validation performed:
  - backend syntax compile: passed
  - frontend build: passed
  - frontend lint: failed (warnings treated as errors)
  - npm audit: 2 moderate vulnerabilities
  - frontend tests: script missing
  - backend pytest: no tests found

## Production Verdict

- Readiness rating: 5.2/10
- Go/No-Go: No-Go

## Findings (Severity Ordered)

## Critical

### 1) Payment posting occurs before clearance

Why it matters:
Pending payments are affecting receivables immediately, which can corrupt financial state.

Evidence:
- [backend/app/routers/payments.py](backend/app/routers/payments.py#L452)
- [backend/app/routers/payments.py](backend/app/routers/payments.py#L467)
- [backend/app/routers/payments.py](backend/app/routers/payments.py#L218)
- [backend/app/schemas/payment.py](backend/app/schemas/payment.py#L11)
- [backend/app/schemas/payment.py](backend/app/schemas/payment.py#L21)

Fix direction:
- Enforce positive amount and allocation values.
- Apply invoice and GRN effects only when status transitions to cleared.
- Keep pending payments as non-posting records.

### 2) Missing ownership check for invoice allocations

Why it matters:
A payment can be allocated to an invoice that belongs to a different customer.

Evidence:
- [backend/app/routers/payments.py](backend/app/routers/payments.py#L210)

Fix direction:
- Validate invoice.customer_id equals payload.customer_id for customer payments.
- Enforce strict party-type allocation rules.

### 3) Transactional quantities and prices are insufficiently constrained

Why it matters:
Negative or invalid values can produce incorrect stock and financial records.

Evidence:
- [backend/app/schemas/sales.py](backend/app/schemas/sales.py#L23)
- [backend/app/schemas/sales.py](backend/app/schemas/sales.py#L25)
- [backend/app/schemas/purchase.py](backend/app/schemas/purchase.py#L14)
- [backend/app/schemas/purchase.py](backend/app/schemas/purchase.py#L16)
- [backend/app/routers/sales.py](backend/app/routers/sales.py#L1386)
- [backend/app/routers/sales.py](backend/app/routers/sales.py#L1398)

Fix direction:
- Add gt/ge validators for all monetary and quantity fields.
- Explicitly reject non-positive quantities where business logic requires positive values.

## High

### 4) Insecure runtime defaults for secrets and email credentials

Why it matters:
If environment variables are missing, application runs with unsafe fallback values.

Evidence:
- [backend/app/config.py](backend/app/config.py#L26)
- [backend/app/config.py](backend/app/config.py#L32)
- [backend/app/config.py](backend/app/config.py#L33)

Fix direction:
- Fail startup when security-critical values are missing or placeholder-like.
- Remove insecure defaults from runtime settings.

### 5) Logo path handling can expose local files

Why it matters:
Arbitrary file paths can be used if logo_url is set unsafely.

Evidence:
- [backend/app/routers/company.py](backend/app/routers/company.py#L26)
- [backend/app/routers/company.py](backend/app/routers/company.py#L65)
- [backend/app/routers/company.py](backend/app/routers/company.py#L106)
- [backend/app/schemas/company.py](backend/app/schemas/company.py#L29)

Fix direction:
- Restrict logo resolution to backend static directory only.
- Reject absolute and parent-relative paths.

### 6) Number generation has race-condition risk in multiple modules

Why it matters:
Concurrent requests can produce duplicate codes and intermittent failures.

Evidence:
- [backend/app/services/order_number_service.py](backend/app/services/order_number_service.py#L83)
- [backend/app/services/order_number_service.py](backend/app/services/order_number_service.py#L91)
- [backend/app/services/order_number_service.py](backend/app/services/order_number_service.py#L99)
- [backend/app/routers/products.py](backend/app/routers/products.py#L35)
- [backend/app/routers/customers.py](backend/app/routers/customers.py#L126)
- [backend/app/routers/suppliers.py](backend/app/routers/suppliers.py#L126)
- [backend/app/routers/stock.py](backend/app/routers/stock.py#L32)

Fix direction:
- Use database sequences or locked counters for all identifiers.
- Avoid COUNT + 1 and max-scan patterns in write paths.

### 7) Refresh token flow does not enforce token type separation

Why it matters:
Access and refresh token boundaries are weak without explicit token type claim checks.

Evidence:
- [backend/app/dependencies.py](backend/app/dependencies.py#L92)
- [backend/app/dependencies.py](backend/app/dependencies.py#L103)
- [backend/app/routers/auth.py](backend/app/routers/auth.py#L75)
- [backend/app/routers/auth.py](backend/app/routers/auth.py#L91)

Fix direction:
- Add token_type claim and enforce it on refresh endpoint.
- Rotate refresh tokens and support revocation strategy.

## Medium

### 8) Dashboard pending PO metric uses status values inconsistent with workflow

Why it matters:
Dashboard can show incorrect pending purchase order counts.

Evidence:
- [backend/app/routers/reports.py](backend/app/routers/reports.py#L69)
- [backend/app/routers/purchase.py](backend/app/routers/purchase.py#L310)
- [database/01_schema.sql](database/01_schema.sql#L337)

Fix direction:
- Align report status filters with actual lifecycle values.

### 9) N+1 query pattern in dashboard stock metrics

Why it matters:
Performance degrades with larger product catalogs.

Evidence:
- [backend/app/routers/reports.py](backend/app/routers/reports.py#L55)
- [backend/app/routers/reports.py](backend/app/routers/reports.py#L56)
- [backend/app/routers/reports.py](backend/app/routers/reports.py#L57)

Fix direction:
- Replace looped per-product stock query with grouped aggregate query.

### 10) Documented test workflow does not match repository reality

Why it matters:
Quality gates are unclear and no reliable regression safety net exists.

Evidence:
- [README.md](README.md#L140)
- [frontend/package.json](frontend/package.json#L6)

Fix direction:
- Either add real test scripts and tests, or correct documentation immediately.

### 11) Frontend lint gate is currently failing

Why it matters:
Hook dependency warnings can cause stale state and brittle UI behavior.

Evidence:
- [frontend/src/pages/CustomersPage.tsx](frontend/src/pages/CustomersPage.tsx#L524)
- [frontend/src/pages/InventoryCountPage.tsx](frontend/src/pages/InventoryCountPage.tsx#L44)
- [frontend/src/pages/InvoicesPage.tsx](frontend/src/pages/InvoicesPage.tsx#L267)
- [frontend/src/pages/PayablesPage.tsx](frontend/src/pages/PayablesPage.tsx#L209)
- [frontend/src/pages/ProductsPage.tsx](frontend/src/pages/ProductsPage.tsx#L415)
- [frontend/src/pages/SuppliersPage.tsx](frontend/src/pages/SuppliersPage.tsx#L480)

Fix direction:
- Resolve hook dependency issues and rerun lint/build gate.

### 12) Frontend dependency advisory warnings present

Why it matters:
Known vulnerabilities are reported in the current toolchain.

Evidence:
- [frontend/package.json](frontend/package.json#L40)

Fix direction:
- Plan upgrade path for vulnerable packages and pin safe versions.

## Low

### 13) Broad exception catches reduce observability

Why it matters:
Can mask root causes and hinder debugging under production load.

Evidence:
- [backend/app/routers/company.py](backend/app/routers/company.py#L38)
- [backend/app/utils/seed.py](backend/app/utils/seed.py#L99)

Fix direction:
- Catch narrower exception types and preserve structured logging context.

### 14) Migration fallback includes hardcoded local DB credentials

Why it matters:
Unsafe as a default pattern and can be used accidentally in shared setups.

Evidence:
- [backend/run_migration.py](backend/run_migration.py#L31)

Fix direction:
- Remove credential fallback and require explicit DATABASE_URL.

## Required Actions Before Production

1. Fix payment posting integrity and allocation validation.
2. Add strict numeric validators for quantity and amount fields.
3. Remove insecure secret and credential defaults.
4. Harden logo path handling.
5. Replace race-prone numbering logic.
6. Add baseline automated tests for auth, payment posting, and stock-affecting flows.
7. Resolve lint warnings and security advisories.
