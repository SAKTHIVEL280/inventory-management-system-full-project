"""Guard tests: the archive/retention flow must never hard-delete business data.
Everything stays soft-archived (is_deleted=True) and is retained indefinitely."""
import inspect

from app.routers import archive
from app.services import retention_cleanup


def test_no_archive_policy_allows_purge():
    # No module may ever be hard-deleted.
    assert archive.ARCHIVE_POLICIES, "policies should be defined"
    assert all(p.purge_allowed is False for p in archive.ARCHIVE_POLICIES)


def test_purge_confirm_has_no_hard_delete_path():
    src = inspect.getsource(archive.purge_confirm)
    assert "db.delete" not in src
    assert ".delete()" not in src


def test_login_alerts_requires_no_review():
    # The Dashboard retention warning is driven by requires_attention — now always False.
    src = inspect.getsource(archive.login_alerts)
    assert '"requires_attention": False' in src


def test_audit_log_retention_cleanup_deletes_nothing():
    src = inspect.getsource(retention_cleanup.cleanup_old_audit_logs)
    assert "DELETE FROM" not in src.upper()
