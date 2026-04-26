-- DB-45: GST Report Audit Logs
-- Purpose: Persist GST report generation/export events with filterable metadata.

BEGIN;

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS gst_report_audit_logs (
	id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
	user_id UUID REFERENCES users(id),
	action VARCHAR(120) NOT NULL,
	report_type VARCHAR(40) NOT NULL,
	start_date DATE NOT NULL,
	end_date DATE NOT NULL,
	frequency VARCHAR(20) NOT NULL,
	"timestamp" TIMESTAMPTZ NOT NULL DEFAULT NOW(),
	status VARCHAR(20) NOT NULL,
	details JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS ix_gst_report_audit_logs_timestamp
ON gst_report_audit_logs ("timestamp");

CREATE INDEX IF NOT EXISTS ix_gst_report_audit_logs_report_type
ON gst_report_audit_logs (report_type);

CREATE INDEX IF NOT EXISTS ix_gst_report_audit_logs_user_id
ON gst_report_audit_logs (user_id);

COMMIT;
