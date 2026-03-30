"""Convenience wrapper to run the project bootstrap from backend/."""
from pathlib import Path
import subprocess
import sys


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    bootstrap = repo_root / "setup_db.py"
    result = subprocess.run([sys.executable, str(bootstrap)], cwd=str(repo_root))
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
