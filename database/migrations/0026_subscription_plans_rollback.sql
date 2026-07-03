-- ════════════════════════════════════════════════════════════════════════════
-- ROLLBACK — Subscription Plan Configuration
-- File: 0026_subscription_plans_rollback.sql
-- Task: DB-222
--
-- Drops the DB-backed plan configuration table. plan_service then falls back to
-- the hardcoded code defaults, so plan behaviour reverts to the original matrix.
-- ════════════════════════════════════════════════════════════════════════════

BEGIN;

DROP TABLE IF EXISTS subscription_plans;

COMMIT;
