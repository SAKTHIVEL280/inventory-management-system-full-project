-- Product Base Unit (SKU) should be non-unique
-- Date: April 5, 2026
-- Test Case: Product Update Base Unit duplicate handling

BEGIN;

-- Drop legacy unique constraint created when SKU was treated as unique.
ALTER TABLE products
DROP CONSTRAINT IF EXISTS products_sku_key;

-- Drop any remaining unique indexes that include sku.
DO $$
DECLARE idx_name TEXT;
BEGIN
    FOR idx_name IN
        SELECT i.relname
        FROM pg_class t
        JOIN pg_index x ON t.oid = x.indrelid
        JOIN pg_class i ON i.oid = x.indexrelid
        JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(x.indkey)
        WHERE t.relname = 'products'
          AND x.indisunique = TRUE
          AND a.attname = 'sku'
    LOOP
        EXECUTE format('DROP INDEX IF EXISTS %I', idx_name);
    END LOOP;
END $$;

COMMIT;
