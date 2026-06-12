-- ============================================================================
-- MCN-BUGFIX-v1.5: Audit log company scoping + Sales Invoice edit versioning
-- ----------------------------------------------------------------------------
-- Covers two DB changes required by BRD_Bugfix_v1.5.md:
--
--   1) audit_logs.company_id  (Action Logs 500 fix)
--      The action-logs report and log_audit_event reference a.company_id.
--      Deployments that predate the multi-tenant migration are missing this
--      column, which made every Action Logs request 500 (UndefinedColumn).
--
--   2) audit_logs.version     (MCN-BUG-006)
--      Chronological, immutable edit version for Sales Invoice ("Sales Order")
--      edits. NULL on creation / non-edit entries; populated 1, 2, 3 ... from
--      the first edit onwards. Rendered as Roman numerals (Version I, II ...).
--
-- Idempotent and safe to run multiple times.
-- Mirrored in database/01_schema.sql and self-healed at runtime by
-- backend/app/services/audit_service.py (_ensure_audit_logs_table).
-- ============================================================================

ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS company_id UUID;
CREATE INDEX IF NOT EXISTS ix_audit_logs_company_id ON audit_logs (company_id);

ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS version INTEGER;
