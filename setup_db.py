"""Bootstrap IMS backend database and seed data safely.

This script is intentionally idempotent. You can run it multiple times.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
BACKEND_ENV = BACKEND / ".env"
BACKEND_ENV_EXAMPLE = BACKEND / ".env.example"


def _print_step(step: str) -> None:
    print(f"\n{step}")


def _run(cmd: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(cwd) if cwd else None, text=True, capture_output=True, check=check)


def _write_default_env_if_missing() -> None:
    if BACKEND_ENV.exists():
        print("  - backend/.env exists")
        return

    default_env = (
        "DATABASE_URL=postgresql://postgres:root@localhost:5432/ims_db\n"
        "SECRET_KEY=dev-only-change-this-secret-key\n"
        "ALGORITHM=HS256\n"
        "ACCESS_TOKEN_EXPIRE_MINUTES=480\n"
        "REFRESH_TOKEN_EXPIRE_DAYS=7\n"
        "MAIL_USERNAME=your@gmail.com\n"
        "MAIL_PASSWORD=your-gmail-app-password\n"
        "MAIL_FROM=noreply@yourcompany.com\n"
        "MAIL_PORT=587\n"
        "MAIL_SERVER=smtp.gmail.com\n"
        "MAIL_STARTTLS=true\n"
        "MAIL_SSL_TLS=false\n"
        "FRONTEND_URL=http://localhost:5173\n"
        "COMPANY_NAME=Your Company Name\n"
    )

    if BACKEND_ENV_EXAMPLE.exists():
        BACKEND_ENV.write_text(BACKEND_ENV_EXAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
        print("  - Created backend/.env from backend/.env.example")
    else:
        BACKEND_ENV.write_text(default_env, encoding="utf-8")
        print("  - Created backend/.env with development defaults")


def _load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _ensure_backend_venv() -> tuple[Path, Path]:
    preferred = BACKEND / ".venv"
    legacy = BACKEND / "venv"
    venv_path = preferred if preferred.exists() or not legacy.exists() else legacy

    if not venv_path.exists():
        print(f"  - Creating virtual environment at {venv_path}")
        subprocess.run([sys.executable, "-m", "venv", str(venv_path)], check=True)
    else:
        print(f"  - Using virtual environment: {venv_path}")

    if os.name == "nt":
        py = venv_path / "Scripts" / "python.exe"
        pip = venv_path / "Scripts" / "pip.exe"
    else:
        py = venv_path / "bin" / "python"
        pip = venv_path / "bin" / "pip"

    return py, pip


def _ensure_database_exists(database_url: str, env: dict[str, str]) -> None:
    parsed = urlparse(database_url)
    db_name = (parsed.path or "").lstrip("/")
    if not db_name:
        raise RuntimeError("DATABASE_URL is invalid (missing database name)")

    pg_password = env.get("PGPASSWORD")
    if not pg_password and parsed.password:
        pg_password = parsed.password

    create_cmd = ["createdb", "-h", parsed.hostname or "localhost"]
    if parsed.port:
        create_cmd.extend(["-p", str(parsed.port)])
    if parsed.username:
        create_cmd.extend(["-U", parsed.username])
    create_cmd.append(db_name)

    proc_env = os.environ.copy()
    if pg_password:
        proc_env["PGPASSWORD"] = pg_password

    result = subprocess.run(create_cmd, text=True, capture_output=True, env=proc_env)
    stderr = (result.stderr or "").lower()

    if result.returncode == 0:
        print(f"  - Created database '{db_name}'")
    elif "already exists" in stderr:
        print(f"  - Database '{db_name}' already exists")
    else:
        print("  - Could not auto-create database via createdb (continuing)")
        if result.stderr:
            print(f"    createdb stderr: {result.stderr.strip()[:200]}")


def main() -> int:
    print("=== IMS Setup Bootstrap ===")

    _print_step("[1/5] Preparing backend environment file")
    _write_default_env_if_missing()
    env_values = _load_env_file(BACKEND_ENV)
    database_url = env_values.get("DATABASE_URL", "").strip()
    if not database_url:
        print("  ✗ DATABASE_URL is missing in backend/.env")
        return 1

    _print_step("[2/5] Ensuring Python virtual environment + dependencies")
    py_cmd, pip_cmd = _ensure_backend_venv()
    venv_dir_name = py_cmd.parent.parent.name
    req_file = BACKEND / "requirements.txt"
    install = subprocess.run([str(pip_cmd), "install", "-r", str(req_file)], text=True, capture_output=True)
    if install.returncode != 0:
        print("  ✗ Dependency installation failed")
        print((install.stderr or install.stdout or "")[:400])
        return 1
    print("  - Dependencies installed")

    _print_step("[3/5] Ensuring PostgreSQL database exists")
    _ensure_database_exists(database_url, env_values)

    _print_step("[4/5] Applying compatibility migrations (including currency fields)")
    migrate = subprocess.run([str(py_cmd), "run_migration.py"], cwd=str(BACKEND), text=True, capture_output=True)
    if migrate.returncode != 0:
        print("  ✗ Migration failed")
        print((migrate.stderr or migrate.stdout or "")[:500])
        return 1
    print("  - Compatibility migration applied")

    _print_step("[5/5] Creating tables + seeding defaults")
    seed = subprocess.run([str(py_cmd), "-m", "app.utils.seed"], cwd=str(BACKEND), text=True, capture_output=True)
    if seed.returncode != 0:
        print("  ✗ Seeding failed")
        print((seed.stderr or seed.stdout or "")[:700])
        return 1
    print("  - Seed complete")

    print("\n✓ Setup completed successfully")
    print("\nNext steps:")
    print(f"  1. Backend:  cd backend && {venv_dir_name}\\Scripts\\activate && uvicorn app.main:app --reload")
    print("  2. Frontend: cd frontend && npm install && npm run dev")
    print("\nDefault login:")
    print("  Email: admin@company.com")
    print("  Password: Admin@123")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
