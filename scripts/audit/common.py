"""Shared helpers for AegisOps engineering audit scripts.

All Git metadata and timestamps are derived strictly from live repository state.
Never fabricates SHAs, timestamps, or check results.
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
AUDIT_LOG_PATH = REPO_ROOT / "audit" / "activity.jsonl"

TEAM_PROFILES: dict[str, dict[str, Any]] = {
    "mishael": {
        "member_id": "member-01",
        "name": "Mishael",
        "role": "Lead Systems Architect, DevOps & Integration Engineer",
        "default_tool": "Antigravity Pro",
        "branch_prefix": "feature/mishael-",
        "allowed_prefixes": [
            "docs/",
            "contracts/",
            "scripts/",
            ".github/",
            "simulator/",
            "audit/",
        ],
        "allowed_exact": {
            "README.md",
            "AGENTS.md",
            "docker-compose.yml",
            "docker-compose.tls.yml",
            "Makefile",
            ".env.example",
            ".gitignore",
        },
    },
    "sherwin": {
        "member_id": "member-02",
        "name": "Sherwin",
        "role": "Local Collector, Security & Reliability Engineer",
        "default_tool": "Antigravity Pro",
        "branch_prefix": "feature/sherwin-",
        "allowed_prefixes": ["collector/"],
        "allowed_exact": {"docs/HANDOFF_SHERWIN.md", "audit/activity.jsonl", "audit/checkpoints/latest_report.md"},
    },
    "praveen": {
        "member_id": "member-03",
        "name": "Praveen",
        "role": "SaaS Backend & AIOps Intelligence Engineer",
        "default_tool": "Antigravity Pro",
        "branch_prefix": "feature/praveen-",
        "allowed_prefixes": ["backend/"],
        "allowed_exact": {"docs/HANDOFF_PRAVEEN.md", "audit/activity.jsonl", "audit/checkpoints/latest_report.md"},
    },
    "darain": {
        "member_id": "member-04",
        "name": "Darain",
        "role": "Frontend, UI/UX & Product Experience Engineer",
        "default_tool": "Claude Pro",
        "branch_prefix": "feature/darain-",
        "allowed_prefixes": ["frontend/"],
        "allowed_exact": {"docs/HANDOFF_DARAIN.md", "audit/activity.jsonl", "audit/checkpoints/latest_report.md"},
    },
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run_git(args: list[str]) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except FileNotFoundError:
        return 127, "", "git executable not found"


def get_git_branch() -> str:
    code, out, _ = run_git(["rev-parse", "--abbrev-ref", "HEAD"])
    if code == 0 and out:
        return out
    code2, out2, _ = run_git(["symbolic-ref", "--short", "HEAD"])
    if code2 == 0 and out2:
        return out2
    return "UNINITIALIZED"


def get_git_commit_sha() -> str:
    code, out, _ = run_git(["rev-parse", "HEAD"])
    return out if code == 0 and out else "NO_COMMITS_YET"


def get_changed_files(base_ref: str | None = None) -> list[str]:
    files: set[str] = set()
    if base_ref:
        code, out, _ = run_git(["diff", "--name-only", f"{base_ref}...HEAD"])
        if code == 0 and out:
            files.update(line.strip().replace("\\", "/") for line in out.splitlines() if line.strip())
        return sorted(files)

    for cmd in (
        ["diff", "--name-only", "--cached"],
        ["diff", "--name-only"],
        ["ls-files", "--others", "--exclude-standard"],
    ):
        code, out, _ = run_git(cmd)
        if code == 0 and out:
            files.update(line.strip().replace("\\", "/") for line in out.splitlines() if line.strip())
    return sorted(files)


def append_audit_record(record: dict[str, Any]) -> None:
    AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with AUDIT_LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")
