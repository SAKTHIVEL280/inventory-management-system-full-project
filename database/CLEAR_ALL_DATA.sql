-- Utility: Clear all data from all tables in the public schema.
-- Keeps schema objects (tables, columns, constraints, indexes) unchanged.
-- Uses TRUNCATE ... RESTART IDENTITY CASCADE for FK-safe cleanup.

BEGIN;

DO $$
DECLARE
    target_schema TEXT := 'public';
    tables_sql TEXT;
BEGIN
    SELECT string_agg(format('%I.%I', schemaname, tablename), ', ' ORDER BY tablename)
    INTO tables_sql
    FROM pg_tables
    WHERE schemaname = target_schema;

    IF tables_sql IS NULL THEN
        RAISE NOTICE 'No tables found in schema "%". Nothing to truncate.', target_schema;
        RETURN;
    END IF;

    EXECUTE format('TRUNCATE TABLE %s RESTART IDENTITY CASCADE;', tables_sql);
    RAISE NOTICE 'All tables in schema "%" were truncated successfully.', target_schema;
END $$;

COMMIT;
