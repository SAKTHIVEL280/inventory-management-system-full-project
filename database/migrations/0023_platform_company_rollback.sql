-- ════════════════════════════════════════════════════════════════════════════
-- ROLLBACK for 0023_platform_company.sql
-- Date: June 26, 2026 | Task: DB-219
-- Drops the platform_company table. Back up first (logos referenced by URL remain
-- on disk under static/). Idempotent.
-- ════════════════════════════════════════════════════════════════════════════

BEGIN;
DROP TABLE IF EXISTS platform_company;
COMMIT;
