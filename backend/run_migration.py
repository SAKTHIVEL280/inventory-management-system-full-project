"""Idempotent compatibility migration for existing databases.

This script keeps older DBs compatible with current SQLAlchemy models.
Run safely multiple times.
"""
from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine, text


def _load_database_url() -> str:
    # Prefer environment first
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

    # Last resort for local development compatibility
    return "postgresql://postgres:root@localhost:5432/ims_db"


def main() -> int:
    database_url = _load_database_url()
    engine = create_engine(database_url)

    statements = [
        # Auth hardening fields
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS failed_login_attempts INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS locked_until TIMESTAMPTZ NULL",

        # Inventory/model compatibility
        "ALTER TABLE products ADD COLUMN IF NOT EXISTS safety_stock INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE products ADD COLUMN IF NOT EXISTS status VARCHAR(30) NOT NULL DEFAULT 'active'",
        "ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS place_of_supply VARCHAR(255)",
        "ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS company_director_name VARCHAR(255)",
        "ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS company_director_contact VARCHAR(255)",
        "ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS gstin_status VARCHAR(20) NOT NULL DEFAULT 'non-registered'",
        "ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS business_type VARCHAR(20) NOT NULL DEFAULT 'domestic'",
        "ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS billing_country VARCHAR(100)",
        "ALTER TABLE company ADD COLUMN IF NOT EXISTS gstin_status VARCHAR(20) NOT NULL DEFAULT 'non-registered'",
        "ALTER TABLE company ADD COLUMN IF NOT EXISTS company_director_name VARCHAR(255)",
        "ALTER TABLE company ADD COLUMN IF NOT EXISTS company_director_contact VARCHAR(255)",

        # Currency support
        "ALTER TABLE customers ADD COLUMN IF NOT EXISTS currency_code VARCHAR(10) NOT NULL DEFAULT 'INR'",
        "ALTER TABLE customers ADD COLUMN IF NOT EXISTS company_director_name VARCHAR(255)",
        "ALTER TABLE customers ADD COLUMN IF NOT EXISTS company_director_contact VARCHAR(255)",
        "ALTER TABLE customers ADD COLUMN IF NOT EXISTS gstin_status VARCHAR(20) NOT NULL DEFAULT 'non-registered'",
        "ALTER TABLE customers ADD COLUMN IF NOT EXISTS business_type VARCHAR(20) NOT NULL DEFAULT 'domestic'",
        "ALTER TABLE customers ADD COLUMN IF NOT EXISTS billing_country VARCHAR(100)",
        "ALTER TABLE customers ADD COLUMN IF NOT EXISTS shipping_country VARCHAR(100)",
        "ALTER TABLE purchase_orders ADD COLUMN IF NOT EXISTS currency_code VARCHAR(3) NOT NULL DEFAULT 'INR'",
        "ALTER TABLE purchase_orders ADD COLUMN IF NOT EXISTS exchange_rate NUMERIC(12, 6) NOT NULL DEFAULT 1.0",
        "ALTER TABLE sales_orders ADD COLUMN IF NOT EXISTS currency_code VARCHAR(3) NOT NULL DEFAULT 'INR'",
        "ALTER TABLE sales_orders ADD COLUMN IF NOT EXISTS exchange_rate NUMERIC(12, 6) NOT NULL DEFAULT 1.0",

        # GRN batch tracking fields
        "ALTER TABLE goods_receipt_notes ADD COLUMN IF NOT EXISTS payment_due_date DATE",
        "ALTER TABLE grn_items ADD COLUMN IF NOT EXISTS batch_no VARCHAR(100)",
        "ALTER TABLE grn_items ADD COLUMN IF NOT EXISTS manufacture_date DATE",
        "ALTER TABLE grn_items ADD COLUMN IF NOT EXISTS expiry_date DATE",

        # Sales invoice item extended fields
        "ALTER TABLE sales_invoice_items ADD COLUMN IF NOT EXISTS order_unit VARCHAR(100)",
        "ALTER TABLE sales_invoice_items ADD COLUMN IF NOT EXISTS batch_no VARCHAR(100)",
        "ALTER TABLE sales_invoice_items ADD COLUMN IF NOT EXISTS manufacture_date DATE",
        "ALTER TABLE sales_invoice_items ADD COLUMN IF NOT EXISTS expiry_date DATE",
        "ALTER TABLE sales_invoice_items ADD COLUMN IF NOT EXISTS free_quantity NUMERIC(14, 3) NOT NULL DEFAULT 0",
    ]

    with engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))

    print("Compatibility migration successful.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
