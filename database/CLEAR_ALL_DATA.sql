-- Utility: Clear all data from all tables in the public schema.
-- Keeps schema objects (tables, columns, constraints, indexes) unchanged.
-- Uses TRUNCATE ... RESTART IDENTITY CASCADE for FK-safe cleanup.

-- Note:
-- - Discovers base tables in the target schema from pg_class/pg_namespace.
-- - Skips extension-owned tables (deptype = 'e') to avoid breaking extensions that
--   ship their own reference tables (example: PostGIS). The app schema tables are unaffected.

BEGIN;

DO $$
DECLARE
    target_schema TEXT := 'public';
    tables_sql TEXT;
    table_count INTEGER := 0;
BEGIN
    SELECT
        string_agg(format('%I.%I', n.nspname, c.relname), ', ' ORDER BY c.relname),
        COUNT(*)::INTEGER
    INTO tables_sql, table_count
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = target_schema
      AND c.relkind IN ('r', 'p')
      AND c.relispartition = FALSE
      AND NOT EXISTS (
          SELECT 1
          FROM pg_depend d
          WHERE d.objid = c.oid
            AND d.deptype = 'e'
      );

    IF table_count = 0 OR tables_sql IS NULL THEN
        RAISE NOTICE 'No tables found in schema "%". Nothing to truncate.', target_schema;
        RETURN;
    END IF;

    RAISE NOTICE 'Truncating % tables in schema "%"...', table_count, target_schema;
    EXECUTE format('TRUNCATE TABLE %s RESTART IDENTITY CASCADE;', tables_sql);

    IF EXISTS (
        SELECT 1
        FROM pg_matviews
        WHERE schemaname = target_schema
          AND matviewname = 'current_stock'
    ) THEN
        EXECUTE format('REFRESH MATERIALIZED VIEW %I.%I', target_schema, 'current_stock');
    END IF;

    RAISE NOTICE 'All tables in schema "%" were truncated successfully.', target_schema;
END $$;

COMMIT;
