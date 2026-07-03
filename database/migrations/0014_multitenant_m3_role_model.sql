-- ════════════════════════════════════════════════════════════════════════════
-- Multi-Tenant Migration — MODULE M3: Role model (5 BRD roles)
-- File: 0014_multitenant_m3_role_model.sql
-- Date: June 24, 2026
-- BRD: docs/requirements/Mecandria_ERP_MultiTenant_BRD_v1.md §6
-- Task: DB-209 (BE-220)
--
-- PURPOSE
--   Allow the five BRD end-user roles (Basic/Accounts/Inventory/Management/HR)
--   in addition to the existing tenant roles, by widening the users_role_check
--   constraint. The Tenant Admin keeps role 'admin'.
--
-- SAFETY / NON-BREAKING
--   * The legacy roles ('admin','inventory manager','general manager') stay
--     valid, so every existing user remains valid — no row is reassigned here.
--   * Migration 0004 already converted any literal 'accounts'/'inventory' role
--     values to legacy roles, so repurposing those strings as new BRD roles
--     collides with no existing data.
--   * Idempotent: drops + recreates the named check constraint.
--
-- ROLLBACK: 0014_multitenant_m3_role_model_rollback.sql
-- ════════════════════════════════════════════════════════════════════════════

BEGIN;

ALTER TABLE users DROP CONSTRAINT IF EXISTS users_role_check;

ALTER TABLE users
ADD CONSTRAINT users_role_check
CHECK (role IN (
    -- Legacy roles (kept for backward compatibility / existing users)
    'admin', 'inventory manager', 'general manager',
    -- New BRD role model (§6)
    'basic', 'accounts', 'inventory', 'management', 'hr'
));

COMMIT;
