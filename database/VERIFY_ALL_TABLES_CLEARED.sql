-- Utility: Verify all tables in the public schema are empty.
-- Output 1: per-table row count with status.
-- Output 2: summary verdict.

BEGIN;

CREATE TEMP TABLE tmp_table_row_counts (
    schema_name TEXT,
    table_name TEXT,
    row_count BIGINT
) ON COMMIT DROP;

DO $$
DECLARE
    rec RECORD;
    cnt BIGINT;
BEGIN
    FOR rec IN
        SELECT schemaname, tablename
        FROM pg_tables
        WHERE schemaname = 'public'
        ORDER BY tablename
    LOOP
        EXECUTE format('SELECT count(*) FROM %I.%I', rec.schemaname, rec.tablename)
        INTO cnt;

        INSERT INTO tmp_table_row_counts (schema_name, table_name, row_count)
        VALUES (rec.schemaname, rec.tablename, cnt);
    END LOOP;
END $$;

SELECT
    schema_name,
    table_name,
    row_count,
    CASE
        WHEN row_count = 0 THEN 'OK'
        ELSE 'NOT EMPTY'
    END AS status
FROM tmp_table_row_counts
ORDER BY table_name;

SELECT
    COUNT(*) AS total_tables,
    COUNT(*) FILTER (WHERE row_count = 0) AS empty_tables,
    COUNT(*) FILTER (WHERE row_count > 0) AS non_empty_tables,
    CASE
        WHEN COUNT(*) FILTER (WHERE row_count > 0) = 0 THEN 'PASS - all tables are empty'
        ELSE 'FAIL - some tables still contain data'
    END AS verification_result
FROM tmp_table_row_counts;

COMMIT;
