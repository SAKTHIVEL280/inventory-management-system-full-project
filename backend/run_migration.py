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

        # Currency support
        "ALTER TABLE customers ADD COLUMN IF NOT EXISTS currency_code VARCHAR(10) NOT NULL DEFAULT 'INR'",
        "ALTER TABLE purchase_orders ADD COLUMN IF NOT EXISTS currency_code VARCHAR(3) NOT NULL DEFAULT 'INR'",
        "ALTER TABLE purchase_orders ADD COLUMN IF NOT EXISTS exchange_rate NUMERIC(12, 6) NOT NULL DEFAULT 1.0",
        "ALTER TABLE sales_orders ADD COLUMN IF NOT EXISTS currency_code VARCHAR(3) NOT NULL DEFAULT 'INR'",
        "ALTER TABLE sales_orders ADD COLUMN IF NOT EXISTS exchange_rate NUMERIC(12, 6) NOT NULL DEFAULT 1.0",
    ]

    with engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))

    print("Compatibility migration successful.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
