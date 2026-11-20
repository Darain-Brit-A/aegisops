"""Installs local Git pre-commit and pre-push audit hooks for AegisOps."""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO_ROOT / ".git" / "hooks"

PRE_COMMIT_HOOK = """#!/usr/bin/env sh
# AegisOps local pre-commit safeguard (CI remains authoritative)
set -e
python scripts/audit/verify_contracts.py
python scripts/audit/check_secrets.py
"""

PRE_PUSH_HOOK = """#!/usr/bin/env sh
# AegisOps local pre-push safeguard (CI remains authoritative)
set -e
python scripts/audit/verify_contracts.py
python scripts/audit/check_secrets.py
"""


def write_hook(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8", newline="\n")
    try:
        mode = path.stat().st_mode
        path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    except OSError:
        pass


def main() -> int:
    if not HOOKS_DIR.exists():
        print(f"[BLOCKED] Git hooks directory not found: {HOOKS_DIR}. Run 'git init' first.")
        return 1
    write_hook(HOOKS_DIR / "pre-commit", PRE_COMMIT_HOOK)
    write_hook(HOOKS_DIR / "pre-push", PRE_PUSH_HOOK)
    print(f"[PASS] Installed pre-commit and pre-push hooks in {HOOKS_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
