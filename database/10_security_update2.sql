-- DB-46: Tenant Company Scope Backfill, Constraints, and Indexes
-- Date: April 21, 2026
-- Backfills company_id for existing rows and adds FK/index coverage in an idempotent way.

BEGIN;

DO $$
DECLARE
  company_uuid UUID;
BEGIN
  SELECT id
  INTO company_uuid
  FROM company
  ORDER BY created_at ASC NULLS LAST, id ASC
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

    UPDATE product_categories pc
    SET company_id = COALESCE(
      (SELECT u.company_id FROM users u WHERE u.id = pc.created_by),
      company_uuid
    )
    WHERE pc.company_id IS NULL;
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint c
    WHERE c.contype = 'f'
      AND c.conrelid = 'users'::regclass
      AND c.confrelid = 'company'::regclass
      AND pg_get_constraintdef(c.oid) ILIKE 'FOREIGN KEY (company_id)%'
  ) THEN
    ALTER TABLE users
      ADD CONSTRAINT fk_users_company
      FOREIGN KEY (company_id) REFERENCES company(id);
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint c
    WHERE c.contype = 'f'
      AND c.conrelid = 'products'::regclass
      AND c.confrelid = 'company'::regclass
      AND pg_get_constraintdef(c.oid) ILIKE 'FOREIGN KEY (company_id)%'
  ) THEN
    ALTER TABLE products
      ADD CONSTRAINT fk_products_company
      FOREIGN KEY (company_id) REFERENCES company(id);
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint c
    WHERE c.contype = 'f'
      AND c.conrelid = 'customers'::regclass
      AND c.confrelid = 'company'::regclass
      AND pg_get_constraintdef(c.oid) ILIKE 'FOREIGN KEY (company_id)%'
  ) THEN
    ALTER TABLE customers
      ADD CONSTRAINT fk_customers_company
      FOREIGN KEY (company_id) REFERENCES company(id);
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint c
    WHERE c.contype = 'f'
      AND c.conrelid = 'product_categories'::regclass
      AND c.confrelid = 'company'::regclass
      AND pg_get_constraintdef(c.oid) ILIKE 'FOREIGN KEY (company_id)%'
  ) THEN
    ALTER TABLE product_categories
      ADD CONSTRAINT fk_product_categories_company
      FOREIGN KEY (company_id) REFERENCES company(id);
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS ix_users_company_id
ON users (company_id);

CREATE INDEX IF NOT EXISTS ix_products_company_id
ON products (company_id);

CREATE INDEX IF NOT EXISTS ix_customers_company_id
ON customers (company_id);

COMMIT;
