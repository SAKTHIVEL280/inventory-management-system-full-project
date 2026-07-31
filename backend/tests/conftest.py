"""Pytest configuration for CI.

The application's `Settings` (app/config.py) validates its environment strictly:
  * DATABASE_URL must be a PostgreSQL URL,
  * SECRET_KEY must be >= 32 chars and not a placeholder,
  * ENVIRONMENT must be one of development/staging/production.

CI provides sqlite / a short secret / ENVIRONMENT=test, which the app would reject
at import time. We therefore set safe, valid values HERE — at module import, before
any `app.*` import happens (pytest loads conftest.py before collecting tests) — so
the app boots for the tests. The DATABASE_URL is only validated by prefix and is
never connected to (these tests exercise pure logic + a DB-free health endpoint).
"""
import os

os.environ["DATABASE_URL"] = "postgresql://ci:ci@localhost:5432/ci_testdb"
os.environ["SECRET_KEY"] = "ci-testing-secret-key-0123456789-abcdefghij"  # >=32, no placeholder
os.environ["ENVIRONMENT"] = "development"
os.environ.setdefault("COOKIE_SECURE", "false")
