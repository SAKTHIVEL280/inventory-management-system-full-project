-- Enhancement 3 — Sales Invoice mandatory fields & filters
-- (docs/requirements/Enhancement-requirement-1.md, FR-15..FR-24)
--
-- Adds two Customization master tables (Stockist, Sales Manager) and three
-- internal operational columns on sales_invoices. The invoice columns are
-- nullable so existing invoices keep working; the mandatory rule is enforced
-- in the application layer for new/edited invoices.
--
-- Idempotent. Safe to run multiple times.

-- ── Stockist master (FR-15) ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS stockists (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(150) NOT NULL,
    city VARCHAR(120),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    company_id UUID REFERENCES company(id),
    created_by UUID REFERENCES users(id)
);
CREATE INDEX IF NOT EXISTS ix_stockists_name ON stockists (name);
CREATE INDEX IF NOT EXISTS ix_stockists_company_id ON stockists (company_id);

-- ── Sales Manager master (FR-16) ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS sales_managers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(150) NOT NULL,
    employee_id VARCHAR(50),
    region VARCHAR(120),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    company_id UUID REFERENCES company(id),
    created_by UUID REFERENCES users(id)
);
CREATE INDEX IF NOT EXISTS ix_sales_managers_name ON sales_managers (name);
CREATE INDEX IF NOT EXISTS ix_sales_managers_company_id ON sales_managers (company_id);

-- ── Sales Invoice internal fields (7.2 / FR-21 / FR-22 filters) ───────────────
ALTER TABLE sales_invoices ADD COLUMN IF NOT EXISTS stockist_name VARCHAR(150);
ALTER TABLE sales_invoices ADD COLUMN IF NOT EXISTS stockist_city VARCHAR(120);
ALTER TABLE sales_invoices ADD COLUMN IF NOT EXISTS sales_manager_name VARCHAR(150);
CREATE INDEX IF NOT EXISTS ix_sales_invoices_stockist_name ON sales_invoices (stockist_name);
CREATE INDEX IF NOT EXISTS ix_sales_invoices_sales_manager_name ON sales_invoices (sales_manager_name);
