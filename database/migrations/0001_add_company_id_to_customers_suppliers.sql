-- Migration: Add company_id to customers and suppliers (idempotent)
-- Run as database owner or a role with ALTER privileges (e.g. ims_user)

BEGIN;

-- Add column to customers if missing
ALTER TABLE customers ADD COLUMN IF NOT EXISTS company_id UUID;

-- Add FK constraint on customers.company_id if not exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name AND tc.constraint_schema = kcu.constraint_schema
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND tc.table_schema = current_schema()
          AND tc.table_name = 'customers'
          AND kcu.column_name = 'company_id'
    ) THEN
        ALTER TABLE customers
        ADD CONSTRAINT fk_customers_company FOREIGN KEY (company_id) REFERENCES company(id);
    END IF;
END
$$;

-- Create index for customers.company_id if not exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relkind = 'i' AND c.relname = 'ix_customers_company_id' AND n.nspname = current_schema()
    ) THEN
        CREATE INDEX ix_customers_company_id ON customers (company_id);
    END IF;
END
$$;

-- Add column to suppliers if missing
ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS company_id UUID;

-- Add FK constraint on suppliers.company_id if not exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name AND tc.constraint_schema = kcu.constraint_schema
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND tc.table_schema = current_schema()
          AND tc.table_name = 'suppliers'
          AND kcu.column_name = 'company_id'
    ) THEN
        ALTER TABLE suppliers
        ADD CONSTRAINT fk_suppliers_company FOREIGN KEY (company_id) REFERENCES company(id);
    END IF;
END
$$;

-- Create index for suppliers.company_id if not exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relkind = 'i' AND c.relname = 'ix_suppliers_company_id' AND n.nspname = current_schema()
    ) THEN
        CREATE INDEX ix_suppliers_company_id ON suppliers (company_id);
    END IF;
END
$$;

COMMIT;
