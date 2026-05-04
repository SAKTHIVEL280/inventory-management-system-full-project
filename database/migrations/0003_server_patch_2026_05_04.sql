-- Server patch: company/customer/supplier columns + company assignment backfill
-- Safe to run multiple times (idempotent)

BEGIN;

-- Company fields
ALTER TABLE company ADD COLUMN IF NOT EXISTS gstin_status VARCHAR(20) NOT NULL DEFAULT 'non-registered';
ALTER TABLE company ADD COLUMN IF NOT EXISTS company_director_name VARCHAR(255);
ALTER TABLE company ADD COLUMN IF NOT EXISTS company_director_contact VARCHAR(255);

-- Customers
ALTER TABLE customers ADD COLUMN IF NOT EXISTS company_id UUID;
ALTER TABLE customers ADD COLUMN IF NOT EXISTS gstin_status VARCHAR(20) NOT NULL DEFAULT 'non-registered';
ALTER TABLE customers ADD COLUMN IF NOT EXISTS business_type VARCHAR(20) NOT NULL DEFAULT 'domestic';
ALTER TABLE customers ADD COLUMN IF NOT EXISTS company_director_name VARCHAR(255);
ALTER TABLE customers ADD COLUMN IF NOT EXISTS company_director_contact VARCHAR(255);
ALTER TABLE customers ADD COLUMN IF NOT EXISTS billing_country VARCHAR(100);
ALTER TABLE customers ADD COLUMN IF NOT EXISTS shipping_country VARCHAR(100);

-- Suppliers
ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS company_id UUID;
ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS gstin_status VARCHAR(20) NOT NULL DEFAULT 'non-registered';
ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS business_type VARCHAR(20) NOT NULL DEFAULT 'domestic';
ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS company_director_name VARCHAR(255);
ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS company_director_contact VARCHAR(255);
ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS billing_country VARCHAR(100);

-- Indexes
CREATE INDEX IF NOT EXISTS ix_customers_company_id ON customers (company_id);
CREATE INDEX IF NOT EXISTS ix_suppliers_company_id ON suppliers (company_id);

-- Foreign keys (idempotent)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_customers_company') THEN
        ALTER TABLE customers
            ADD CONSTRAINT fk_customers_company
            FOREIGN KEY (company_id) REFERENCES company(id);
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_suppliers_company') THEN
        ALTER TABLE suppliers
            ADD CONSTRAINT fk_suppliers_company
            FOREIGN KEY (company_id) REFERENCES company(id);
    END IF;
END $$;

-- Backfill company assignment (users/customers/suppliers/products)
DO $$
DECLARE company_uuid UUID;
BEGIN
    SELECT id INTO company_uuid
    FROM company
    ORDER BY created_at ASC
    LIMIT 1;

    IF company_uuid IS NOT NULL THEN
        UPDATE users
        SET company_id = company_uuid
        WHERE company_id IS NULL;

        UPDATE products p
        SET company_id = COALESCE(
            (SELECT u.company_id FROM users u WHERE u.id = p.created_by),
            company_uuid
        )
        WHERE p.company_id IS NULL;

        UPDATE customers c
        SET company_id = COALESCE(
            (SELECT u.company_id FROM users u WHERE u.id = c.created_by),
            company_uuid
        )
        WHERE c.company_id IS NULL;

        UPDATE suppliers s
        SET company_id = COALESCE(
            (SELECT u.company_id FROM users u WHERE u.id = s.created_by),
            company_uuid
        )
        WHERE s.company_id IS NULL;
    END IF;
END $$;

COMMIT;
