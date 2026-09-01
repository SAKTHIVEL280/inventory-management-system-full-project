"""Data retention cleanup service for audit logs and GST audit trail."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Retention policy: Keep records for 15 days only
RETENTION_DAYS = 15


def cleanup_old_audit_logs(db: Session) -> dict[str, int]:
    """
    Delete audit log records older than RETENTION_DAYS.
    
    Args:
        db: Database session
        
    Returns:
        Dictionary with cleanup statistics:
        - action_logs_deleted: Number of action logs deleted
        - gst_audit_logs_deleted: Number of GST audit logs deleted
        - cutoff_date: The cutoff date used for deletion
    """
    # Retention cleanup is DISABLED. Audit logs and the GST audit trail are historical
    # records that must remain available for reports, accounting, audit and references,
    # so the ERP never hard-deletes them. This is now a safe no-op (nothing is deleted).
    logger.info("Audit-log retention cleanup is disabled — logs are retained indefinitely (no hard delete).")
    return {
        "action_logs_deleted": 0,
        "gst_audit_logs_deleted": 0,
        "cutoff_date": None,
        "retention_disabled": True,
    }


def run_retention_cleanup(db: Session) -> dict[str, int]:
    """
    Run the retention cleanup process.
    
    This is the main entry point for the scheduled cleanup job.
    
    Args:
        db: Database session
        
    Returns:
        Dictionary with cleanup statistics
    """
    logger.info(f"Starting retention cleanup (keeping last {RETENTION_DAYS} days)")
    
    try:
        stats = cleanup_old_audit_logs(db)
        
        total_deleted = stats["action_logs_deleted"] + stats["gst_audit_logs_deleted"]
        
        if total_deleted > 0:
            logger.info(
                f"Retention cleanup successful: {total_deleted} total records deleted "
                f"(Action Logs: {stats['action_logs_deleted']}, "
                f"GST Audit Logs: {stats['gst_audit_logs_deleted']})"
            )
        else:
            logger.info("Retention cleanup completed: No old records to delete")
        
        return stats
        
    except Exception as e:
        logger.error(f"Retention cleanup failed: {e}")
        raise


def get_retention_status(db: Session) -> dict[str, Any]:
    """
    Get current retention status and statistics.
    
    Args:
        db: Database session
        
    Returns:
        Dictionary with retention status information
    """
    cutoff_date = datetime.utcnow() - timedelta(days=RETENTION_DAYS)
    
    try:
        # Count action logs
        action_logs_total = db.execute(
            text("SELECT COUNT(*) FROM audit_logs")
        ).scalar() or 0
        
        action_logs_old = db.execute(
            text("SELECT COUNT(*) FROM audit_logs WHERE created_at < :cutoff_date"),
            {"cutoff_date": cutoff_date}
        ).scalar() or 0
        
        # Get oldest action log date
        oldest_action_log = db.execute(
            text("SELECT MIN(created_at) FROM audit_logs")
        ).scalar()
        
        # Count GST audit logs
        gst_logs_total = db.execute(
            text("SELECT COUNT(*) FROM gst_report_audit_logs")
        ).scalar() or 0
        
        gst_logs_old = db.execute(
            text('SELECT COUNT(*) FROM gst_report_audit_logs WHERE "timestamp" < :cutoff_date'),
            {"cutoff_date": cutoff_date}
        ).scalar() or 0
        
        # Get oldest GST audit log date
        oldest_gst_log = db.execute(
            text('SELECT MIN("timestamp") FROM gst_report_audit_logs')
        ).scalar()
        
        return {
            "retention_days": RETENTION_DAYS,
            "cutoff_date": cutoff_date.isoformat(),
            "action_logs": {
                "total": action_logs_total,
                "old_records": action_logs_old,
                "oldest_record": oldest_action_log.isoformat() if oldest_action_log else None,
            },
            "gst_audit_logs": {
                "total": gst_logs_total,
                "old_records": gst_logs_old,
                "oldest_record": oldest_gst_log.isoformat() if oldest_gst_log else None,
            },
        }
        
    except Exception as e:
        logger.error(f"Error getting retention status: {e}")
        return {
            "error": str(e),
            "retention_days": RETENTION_DAYS,
        }
