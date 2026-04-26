-- 08_action_logs_rotation.sql
-- Action log storage updates with query-friendly columns and indexes.

BEGIN;

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    username VARCHAR(255),
    action VARCHAR(120) NOT NULL,
    action_type VARCHAR(40) NOT NULL DEFAULT 'UNKNOWN',
    module_name VARCHAR(80) NOT NULL DEFAULT 'system',
    resource_type VARCHAR(80),
    resource_id UUID,
    record_reference VARCHAR(255),
    description TEXT,
    status VARCHAR(20) NOT NULL,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    ip_address VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS username VARCHAR(255);
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS action_type VARCHAR(40);
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS module_name VARCHAR(80);
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS record_reference VARCHAR(255);
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS description TEXT;
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

CREATE INDEX IF NOT EXISTS ix_audit_logs_created_at ON audit_logs (created_at);
CREATE INDEX IF NOT EXISTS ix_audit_logs_user_id ON audit_logs (user_id);
CREATE INDEX IF NOT EXISTS ix_audit_logs_module_name ON audit_logs (module_name);
CREATE INDEX IF NOT EXISTS ix_audit_logs_action_type ON audit_logs (action_type);
CREATE INDEX IF NOT EXISTS ix_audit_logs_record_reference ON audit_logs (record_reference);

COMMIT;
