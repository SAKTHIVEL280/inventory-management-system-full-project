#!/usr/bin/env python3
"""
Retention cleanup script for audit logs and GST audit trail.

This script deletes records older than 15 days from:
- audit_logs table (Action Logs)
- gst_report_audit_logs table (GST Audit Trail)

Usage:
    python run_retention_cleanup.py [--dry-run] [--status]

Options:
    --dry-run    Show what would be deleted without actually deleting
    --status     Show current retention status without running cleanup
"""
import argparse
import sys
from datetime import datetime, timedelta

from sqlalchemy import text

from app.database import SessionLocal
from app.services.retention_cleanup import (
    RETENTION_DAYS,
    get_retention_status,
    run_retention_cleanup,
)


def dry_run_cleanup(db):
    """Show what would be deleted without actually deleting."""
    cutoff_date = datetime.utcnow() - timedelta(days=RETENTION_DAYS)
    
    print(f"\n{'='*60}")
    print(f"DRY RUN - Retention Cleanup Preview")
    print(f"{'='*60}")
    print(f"Retention Policy: Keep last {RETENTION_DAYS} days")
    print(f"Cutoff Date: {cutoff_date.date()} {cutoff_date.time().strftime('%H:%M:%S')} UTC")
    print(f"{'='*60}\n")
    
    try:
        # Count action logs to be deleted
        action_logs_count = db.execute(
            text("SELECT COUNT(*) FROM audit_logs WHERE created_at < :cutoff_date"),
            {"cutoff_date": cutoff_date}
        ).scalar() or 0
        
        # Get date range of action logs to be deleted
        if action_logs_count > 0:
            oldest_action = db.execute(
                text("SELECT MIN(created_at) FROM audit_logs WHERE created_at < :cutoff_date"),
                {"cutoff_date": cutoff_date}
            ).scalar()
            newest_action = db.execute(
                text("SELECT MAX(created_at) FROM audit_logs WHERE created_at < :cutoff_date"),
                {"cutoff_date": cutoff_date}
            ).scalar()
        else:
            oldest_action = None
            newest_action = None
        
        # Count GST audit logs to be deleted
        gst_logs_count = db.execute(
            text('SELECT COUNT(*) FROM gst_report_audit_logs WHERE "timestamp" < :cutoff_date'),
            {"cutoff_date": cutoff_date}
        ).scalar() or 0
        
        # Get date range of GST audit logs to be deleted
        if gst_logs_count > 0:
            oldest_gst = db.execute(
                text('SELECT MIN("timestamp") FROM gst_report_audit_logs WHERE "timestamp" < :cutoff_date'),
                {"cutoff_date": cutoff_date}
            ).scalar()
            newest_gst = db.execute(
                text('SELECT MAX("timestamp") FROM gst_report_audit_logs WHERE "timestamp" < :cutoff_date'),
                {"cutoff_date": cutoff_date}
            ).scalar()
        else:
            oldest_gst = None
            newest_gst = None
        
        print("📋 Action Logs (audit_logs table):")
        print(f"   Records to delete: {action_logs_count}")
        if action_logs_count > 0:
            print(f"   Date range: {oldest_action.date()} to {newest_action.date()}")
        else:
            print(f"   ✅ No old records to delete")
        
        print(f"\n📋 GST Audit Trail (gst_report_audit_logs table):")
        print(f"   Records to delete: {gst_logs_count}")
        if gst_logs_count > 0:
            print(f"   Date range: {oldest_gst.date()} to {newest_gst.date()}")
        else:
            print(f"   ✅ No old records to delete")
        
        total = action_logs_count + gst_logs_count
        print(f"\n{'='*60}")
        print(f"Total records to delete: {total}")
        print(f"{'='*60}\n")
        
        if total > 0:
            print("⚠️  This is a DRY RUN - no records were actually deleted")
            print("   Run without --dry-run to perform the actual cleanup\n")
        
    except Exception as e:
        print(f"❌ Error during dry run: {e}")
        sys.exit(1)


def show_status(db):
    """Show current retention status."""
    print(f"\n{'='*60}")
    print(f"Retention Status")
    print(f"{'='*60}\n")
    
    try:
        status = get_retention_status(db)
        
        if "error" in status:
            print(f"❌ Error: {status['error']}")
            sys.exit(1)
        
        print(f"Retention Policy: Keep last {status['retention_days']} days")
        print(f"Cutoff Date: {datetime.fromisoformat(status['cutoff_date']).date()}")
        print(f"\n{'='*60}\n")
        
        print("📋 Action Logs (audit_logs table):")
        print(f"   Total records: {status['action_logs']['total']}")
        print(f"   Old records (>15 days): {status['action_logs']['old_records']}")
        if status['action_logs']['oldest_record']:
            oldest = datetime.fromisoformat(status['action_logs']['oldest_record'])
            print(f"   Oldest record: {oldest.date()} ({(datetime.utcnow() - oldest).days} days old)")
        else:
            print(f"   Oldest record: None")
        
        print(f"\n📋 GST Audit Trail (gst_report_audit_logs table):")
        print(f"   Total records: {status['gst_audit_logs']['total']}")
        print(f"   Old records (>15 days): {status['gst_audit_logs']['old_records']}")
        if status['gst_audit_logs']['oldest_record']:
            oldest = datetime.fromisoformat(status['gst_audit_logs']['oldest_record'])
            print(f"   Oldest record: {oldest.date()} ({(datetime.utcnow() - oldest).days} days old)")
        else:
            print(f"   Oldest record: None")
        
        total_old = status['action_logs']['old_records'] + status['gst_audit_logs']['old_records']
        print(f"\n{'='*60}")
        print(f"Total old records: {total_old}")
        print(f"{'='*60}\n")
        
    except Exception as e:
        print(f"❌ Error getting status: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Retention cleanup for audit logs and GST audit trail"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting"
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show current retention status without running cleanup"
    )
    
    args = parser.parse_args()
    
    db = SessionLocal()
    
    try:
        if args.status:
            show_status(db)
        elif args.dry_run:
            dry_run_cleanup(db)
        else:
            # Run actual cleanup
            print(f"\n{'='*60}")
            print(f"Running Retention Cleanup")
            print(f"{'='*60}")
            print(f"Retention Policy: Keep last {RETENTION_DAYS} days")
            print(f"Started at: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
            print(f"{'='*60}\n")
            
            stats = run_retention_cleanup(db)
            
            print(f"\n{'='*60}")
            print(f"Cleanup Results")
            print(f"{'='*60}")
            print(f"Action Logs deleted: {stats['action_logs_deleted']}")
            print(f"GST Audit Logs deleted: {stats['gst_audit_logs_deleted']}")
            print(f"Total deleted: {stats['action_logs_deleted'] + stats['gst_audit_logs_deleted']}")
            print(f"Cutoff date: {datetime.fromisoformat(stats['cutoff_date']).date()}")
            print(f"{'='*60}\n")
            
            if stats['action_logs_deleted'] + stats['gst_audit_logs_deleted'] > 0:
                print("✅ Retention cleanup completed successfully\n")
            else:
                print("✅ No old records to delete\n")
    
    except Exception as e:
        print(f"\n❌ Error: {e}\n")
        sys.exit(1)
    
    finally:
        db.close()


if __name__ == "__main__":
    main()
