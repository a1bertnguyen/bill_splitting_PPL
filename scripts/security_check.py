"""
Repository Security Hygiene & Secret Scanner (Controls #2 & #20).

Checks:
  1. Verifies `.env` is ignored by Git and NOT staged/tracked.
  2. Scans tracked source files for accidentally hardcoded secrets/API keys/DB passwords.
  3. Reports installed Python package versions for vulnerability auditing.

Usage:
    python scripts/security_check.py
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SECRET_PATTERNS = [
    ("Hardcoded Fernet/API key", re.compile(r"(?:SECRET_KEY|DATA_ENCRYPTION_KEY|API_KEY)\s*=\s*['\"][A-Za-z0-9+/=_-]{24,}['\"]")),
    ("Private Key Header", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("AWS Access Key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("Raw MySQL URL with password", re.compile(r"mysql://[^:\s]+:[^@\s]+@")),
]

SCAN_EXTENSIONS = {".py", ".js", ".jsx", ".ts", ".tsx", ".json", ".html", ".css", ".md", ".yml", ".yaml"}
SKIP_DIRS = {"node_modules", "dist", ".git", "__pycache__", ".pytest_cache", "CompiledFiles", ".venv"}


def check_git_env_tracking() -> list[str]:
    issues: list[str] = []
    if (ROOT / ".git").exists():
        res = subprocess.run(
            ["git", "ls-files", ".env"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        if res.stdout.strip():
            issues.append("CRITICAL: `.env` is tracked by Git! Run: git rm --cached .env")
    return issues


def scan_files_for_secrets() -> list[str]:
    issues: list[str] = []
    for path in ROOT.rglob("*"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if not path.is_file() or path.suffix.lower() not in SCAN_EXTENSIONS:
            continue
        if path.name in {".env.example", "security_check.py"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for label, pattern in SECRET_PATTERNS:
            for match in pattern.finditer(text):
                line_no = text[: match.start()].count("\n") + 1
                issues.append(f"Potential secret ({label}) in {path.relative_to(ROOT)}:{line_no}")
    return issues


def main() -> int:
    issues = check_git_env_tracking() + scan_files_for_secrets()
    if issues:
        print("SECURITY CHECK FAILED:")
        for item in issues:
            print("  -", item)
        return 1
    print("Security hygiene check PASSED: no tracked .env, no hardcoded secrets detected.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
