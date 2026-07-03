"""Multi-tenant isolation verification (read-only).

Module M0 safety-net tool. Reports, for every tenant-scoped table:
  * total rows
  * rows with NULL company_id  (MUST be 0 before onboarding a second tenant)
  * distinct company_id values (number of tenants represented)

It also prints the tenant registry summary from the `company` table.

This script ONLY runs SELECTs — it never modifies data. Run it before and
after applying 0012_multitenant_m0_tenant_registry.sql to confirm existing
production data stays intact and fully attributed to a tenant.

Usage:
    python verify_tenant_isolation.py
Exit code 0 = all scoped tables clean (no NULL company_id); 1 = issues found.
"""
from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine, text


# Tables that carry a company_id discriminator in the shared-DB tenant model.
SCOPED_TABLES = [
    "users", "products", "customers", "suppliers", "product_categories",
    "purchase_orders", "goods_receipt_notes", "purchase_returns",
    "quotations", "sales_orders", "sales_invoices", "sales_returns",
    "payments", "stock_ledger", "inventory_counts",
    "inventory_count_difference_audits", "return_delivery_notes",
    "rdn_credit_notes", "proforma_invoices", "stockists", "sales_managers",
    "customization_options",
    "audit_logs", "gst_report_audit_logs",
]

# Tables where a NULL company_id is legitimate (system / pre-auth events such as
# failed logins have no tenant). NULLs here are reported but not treated as a
# problem (they are excluded from the M7 NOT NULL hardening by design).
NULLABLE_OK = {"audit_logs", "gst_report_audit_logs"}


def _load_database_url() -> str:
    env_url = os.getenv("DATABASE_URL", "").strip()
    if env_url:
        return env_url
    env_file = Path(__file__).resolve().parent / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip() == "DATABASE_URL":
                return value.strip().strip('"').strip("'")
    return "postgresql://postgres:root@localhost:5432/ims_db"


def _table_exists(conn, table: str) -> bool:
    return bool(conn.execute(
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = current_schema() "
            "AND table_name = :t AND column_name = 'company_id'"
        ),
        {"t": table},
    ).first())


def main() -> int:
    engine = create_engine(_load_database_url())
    problems = 0

    with engine.connect() as conn:
        # ── Tenant registry summary ────────────────────────────────────────────
        print("=" * 78)
        print("TENANT REGISTRY (company)")
        print("=" * 78)
        try:
            rows = conn.execute(text(
                "SELECT name, subscription_plan, account_status, payment_status, "
                "onboarding_date, subscription_expiry_date "
                "FROM company ORDER BY created_at ASC"
            )).fetchall()
            if not rows:
                print("  (no company rows)")
            for r in rows:
                print(f"  - {r[0]!r:40} plan={r[1]:9} status={r[2]:9} "
                      f"pay={r[3]:8} onboarded={r[4]} expires={r[5]}")
        except Exception as exc:  # registry columns not yet migrated
            print(f"  registry columns unavailable ({exc.__class__.__name__}); "
                  f"run migration 0012 first.")

        # ── Per-table company_id coverage ──────────────────────────────────────
        print("\n" + "=" * 78)
        print(f"{'TABLE':<38}{'ROWS':>10}{'NULL company_id':>18}{'TENANTS':>10}")
        print("=" * 78)
        for table in SCOPED_TABLES:
            if not _table_exists(conn, table):
                print(f"{table:<38}{'(no company_id / table absent)':>38}")
                continue
            total = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar() or 0
            nulls = conn.execute(
                text(f"SELECT COUNT(*) FROM {table} WHERE company_id IS NULL")
            ).scalar() or 0
            tenants = conn.execute(
                text(f"SELECT COUNT(DISTINCT company_id) FROM {table}")
            ).scalar() or 0
            flag = ""
            if nulls:
                if table in NULLABLE_OK:
                    flag = "  (system rows; allowed)"
                else:
                    flag = "  <-- FIX"
                    problems += 1
            print(f"{table:<38}{total:>10}{nulls:>18}{tenants:>10}{flag}")

    print("\n" + "=" * 78)
    if problems:
        print(f"RESULT: {problems} table(s) have rows with NULL company_id. "
              f"Backfill before onboarding a second tenant.")
        return 1
    print("RESULT: OK — every scoped table is fully attributed to a tenant.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
