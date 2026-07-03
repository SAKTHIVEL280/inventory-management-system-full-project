-- ════════════════════════════════════════════════════════════════════════════
-- Subscription Plan Configuration — DB-backed plan definitions
-- File: 0026_subscription_plans.sql
-- Date: July 3, 2026
-- Task: DB-222 (BE-248 / FE-240) — Super Admin → Plan Configuration
--
-- PURPOSE
--   Move the previously HARDCODED subscription plan matrix (FREE/SILVER/GOLD/
--   PLATINUM) into the database so the Super Admin can configure, per plan:
--   name, pricing, billing period, user limit, module access, feature access,
--   assignable roles, FREE-tier invoice cap and active/inactive status. The
--   plan_service reads these rows (cached) and falls back to code defaults when a
--   row is missing, so behaviour is unchanged until a Super Admin edits a plan.
--
-- SAFETY: idempotent + additive. Seed rows use ON CONFLICT (plan_key) DO NOTHING
--   so existing/edited rows are never overwritten. No existing table is altered.
-- ROLLBACK: 0026_subscription_plans_rollback.sql
-- ════════════════════════════════════════════════════════════════════════════

BEGIN;

CREATE TABLE IF NOT EXISTS subscription_plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_key VARCHAR(20) NOT NULL UNIQUE,
    name VARCHAR(80) NOT NULL,
    price_paise BIGINT NOT NULL DEFAULT 0,
    billing_period VARCHAR(20) NOT NULL DEFAULT 'monthly',
    user_limit INTEGER NOT NULL DEFAULT 1,
    modules JSONB NOT NULL DEFAULT '[]'::jsonb,
    features JSONB NOT NULL DEFAULT '[]'::jsonb,
    roles JSONB NOT NULL DEFAULT '[]'::jsonb,
    free_invoice_cap INTEGER,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_subscription_plans_plan_key ON subscription_plans (plan_key);

-- Seed the four canonical plans from the current (code) defaults. Existing rows
-- are preserved (DO NOTHING), so re-running never clobbers Super Admin edits.
INSERT INTO subscription_plans
    (plan_key, name, price_paise, billing_period, user_limit, modules, features, roles, free_invoice_cap, is_active, sort_order)
VALUES
    ('FREE', 'Free', 0, 'none', 1,
     '["service_invoice"]'::jsonb,
     '["email_invoices"]'::jsonb,
     '["basic"]'::jsonb,
     10, TRUE, 1),
    ('SILVER', 'Silver', 99900, 'monthly', 2,
     '["service_invoice","masters","purchase","sales","accounts","dashboard"]'::jsonb,
     '["email_invoices"]'::jsonb,
     '["admin","accounts"]'::jsonb,
     NULL, TRUE, 2),
    ('GOLD', 'Gold', 199900, 'monthly', 4,
     '["service_invoice","masters","purchase","sales","accounts","dashboard","inventory","reports","audit_logs"]'::jsonb,
     '["email_invoices","advanced_reports","gst_filing","audit_trail"]'::jsonb,
     '["admin","accounts","inventory","management"]'::jsonb,
     NULL, TRUE, 3),
    ('PLATINUM', 'Platinum', 499900, 'monthly', 6,
     '["service_invoice","masters","purchase","sales","accounts","dashboard","inventory","reports","audit_logs","export","pos","hr"]'::jsonb,
     '["email_invoices","advanced_reports","gst_filing","data_export","bulk_import","multi_currency","audit_trail","api_access"]'::jsonb,
     '["admin","accounts","inventory","management","hr"]'::jsonb,
     NULL, TRUE, 4)
ON CONFLICT (plan_key) DO NOTHING;

COMMIT;
