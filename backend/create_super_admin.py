"""Provision a platform Super Admin (Module M4).

Creates a new Super Admin user, or promotes an existing user to Super Admin.
Super Admins are platform-level (company_id = NULL) and access the Super Admin
portal (/api/v1/admin/*).

Usage:
    python create_super_admin.py <email> [password] [full_name]

If the email already exists, the user is promoted (password updated only when a
password argument is supplied). Reads DATABASE_URL the same way as run_migration.
"""
from __future__ import annotations

import os
import secrets
import sys
from pathlib import Path

from sqlalchemy import create_engine, text


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


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("Usage: python create_super_admin.py <email> [password] [full_name]")
        return 2

    email = argv[1].strip().lower()
    password = argv[2] if len(argv) > 2 else secrets.token_urlsafe(10)
    full_name = argv[3] if len(argv) > 3 else "Super Admin"
    generated = len(argv) <= 2

    # Import here so the script works even if run from another cwd.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from app.services.auth_service import hash_password

    engine = create_engine(_load_database_url())
    with engine.begin() as conn:
        existing = conn.execute(
            text("SELECT id FROM users WHERE email = :e"), {"e": email}
        ).first()
        if existing:
            if len(argv) > 2:
                conn.execute(
                    text(
                        "UPDATE users SET is_super_admin = TRUE, is_active = TRUE, "
                        "is_deleted = FALSE, company_id = NULL, "
                        "hashed_password = :p WHERE email = :e"
                    ),
                    {"p": hash_password(password), "e": email},
                )
            else:
                conn.execute(
                    text(
                        "UPDATE users SET is_super_admin = TRUE, is_active = TRUE, "
                        "is_deleted = FALSE, company_id = NULL WHERE email = :e"
                    ),
                    {"e": email},
                )
            print(f"Promoted existing user '{email}' to Super Admin.")
        else:
            conn.execute(
                text(
                    "INSERT INTO users (id, full_name, email, hashed_password, role, "
                    "is_active, is_super_admin, is_deleted, force_password_change, "
                    "company_id, created_at, updated_at) "
                    "VALUES (gen_random_uuid(), :n, :e, :p, 'admin', TRUE, TRUE, FALSE, "
                    "TRUE, NULL, NOW(), NOW())"
                ),
                {"n": full_name, "e": email, "p": hash_password(password)},
            )
            print(f"Created Super Admin '{email}'.")

    if generated:
        print(f"Temporary password: {password}")
        print("Store it securely — it is not shown again.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
