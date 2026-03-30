"""Verify all prerequisites are installed before attempting project setup.

Run this FIRST on a new machine to catch missing tools early.
Usage: python verify_prerequisites.py
"""
import subprocess
import sys
import socket


def _check_command(cmd, name, min_version=None):
    """Check if command exists and optionally verify minimum version."""
    try:
        if cmd == "psql":
            result = subprocess.run([cmd, "--version"], capture_output=True, text=True, timeout=5)
        elif cmd == "npm":
            # npm sometimes doesn't work in subprocess on Windows, try PowerShell
            try:
                result = subprocess.run([cmd, "--version"], capture_output=True, text=True, timeout=5, shell=True)
            except:
                # Fallback: try through PowerShell
                result = subprocess.run(
                    ["powershell", "-NoProfile", "-Command", "npm --version"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
        else:
            result = subprocess.run([cmd, "--version"], capture_output=True, text=True, timeout=5)
        
        if result.returncode == 0:
            version_str = result.stdout.strip() or result.stderr.strip()
            print(f"✓ {name:20} {version_str}")
            return True
        else:
            print(f"✗ {name:20} FAILED to run")
            return False
    except FileNotFoundError:
        print(f"✗ {name:20} NOT FOUND (not in PATH)")
        return False
    except subprocess.TimeoutExpired:
        print(f"✗ {name:20} TIMEOUT")
        return False
    except Exception as e:
        print(f"✗ {name:20} ERROR: {e}")
        return False


def _check_postgres_running():
    """Try to connect to PostgreSQL to see if it's running."""
    try:
        # Just try a simple TCP connection check, don't actually auth
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex(('localhost', 5432))
        sock.close()
        
        if result == 0:
            print(f"✓ {'PostgreSQL Running':20} Server is listening on localhost:5432")
            return True
        else:
            print(f"✗ {'PostgreSQL Running':20} NOT RUNNING (start it in Windows Services)")
            return False
    except Exception as e:
        print(f"⚠ {'PostgreSQL Running':20} Cannot check: {str(e)[:50]}")
        return None


def main():
    print("=" * 70)
    print("IMS Prerequisites Verification")
    print("=" * 70)
    print()
    
    all_pass = True
    
    print("Checking required tools:")
    print("-" * 70)
    
    checks = [
        ("python", "Python 3.11+"),
        ("node", "Node.js 20+"),
        ("npm", "npm 10+"),
        ("git", "Git"),
        ("psql", "PostgreSQL Tools (psql)"),
        ("createdb", "PostgreSQL Tools (createdb)"),
    ]
    
    for cmd, name in checks:
        if not _check_command(cmd, name):
            all_pass = False
    
    print()
    print("Checking service status:")
    print("-" * 70)
    result = _check_postgres_running()
    if result is False:
        all_pass = False
    
    print()
    print("=" * 70)
    
    if all_pass:
        print("✓ All prerequisites are installed!")
        print()
        print("Next steps:")
        print("  1. Edit backend/.env (verify DATABASE_URL password)") 
        print("  2. Run: python setup_db.py")
        print()
        return 0
    else:
        print("✗ Some prerequisites are missing or not running!")
        print()
        print("Install missing tools:")
        print("  - Python:     https://www.python.org/downloads/")
        print("  - Node.js:    https://nodejs.org/")
        print("  - PostgreSQL: https://www.postgresql.org/download/windows/")
        print("  - Git:        https://git-scm.com/download/win")
        print()
        print("After installing, restart PowerShell and run this check again.")
        print()
        return 1


if __name__ == "__main__":
    sys.exit(main())
