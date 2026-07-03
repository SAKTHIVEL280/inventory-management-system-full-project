-- ════════════════════════════════════════════════════════════════════════════
-- Multi-Tenant Migration — MODULE M4: Super Admin portal
-- File: 0015_multitenant_m4_super_admin.sql
-- Date: June 24, 2026
-- BRD: docs/requirements/Mecandria_ERP_MultiTenant_BRD_v1.md §4
-- Task: DB-210 (BE-221)
--
-- PURPOSE
--   Introduce the platform-level Super Admin authority (Mecandria's internal
--   team) that sits above all tenants. A Super Admin is a user flagged
--   `is_super_admin = TRUE` with `company_id` NULL (not bound to any tenant).
--
-- SAFETY
--   * Additive, idempotent. Default FALSE ⇒ every existing user remains a normal
--     tenant user; no behaviour change.
--   * No Super Admin is created here (provision explicitly post-deploy).
--
-- ROLLBACK: 0015_multitenant_m4_super_admin_rollback.sql
-- ════════════════════════════════════════════════════════════════════════════

BEGIN;

ALTER TABLE users ADD COLUMN IF NOT EXISTS is_super_admin BOOLEAN NOT NULL DEFAULT FALSE;
CREATE INDEX IF NOT EXISTS ix_users_is_super_admin ON users (is_super_admin) WHERE is_super_admin = TRUE;

COMMIT;
