"""AegisOps automated engineering audit gate (pre-commit / pre-push / manual).

Records real repository state and actual check results into audit/activity.jsonl
and prints a standardized ENGINEERING AUDIT summary.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_ownership import check_ownership  # noqa: E402
from check_secrets import scan_repository  # noqa: E402
from common import (  # noqa: E402
    REPO_ROOT,
    TEAM_PROFILES,
    append_audit_record,
    get_changed_files,
    get_git_branch,
    get_git_commit_sha,
    run_git,
    utc_now_iso,
)
from verify_contracts import verify_all as verify_contracts  # noqa: E402


def run_cmd(cmd: list[str], extra_env: dict[str, str] | None = None) -> tuple[int, str]:
    import os

    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    proc = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, check=False, env=env)
    output = (proc.stdout + "\n" + proc.stderr).strip()
    return proc.returncode, output


def run_lint_check(actor: str) -> str:
    if not shutil.which("ruff"):
        return "SKIPPED"
    targets = {
        "mishael": ["scripts"],
        "sherwin": ["collector"],
        "praveen": ["backend"],
        "darain": [],
    }[actor]
    if not targets:
        return "NOT APPLICABLE"
    code, _ = run_cmd(["ruff", "check", *targets])
    return "PASS" if code == 0 else "FAIL"


def run_test_check(actor: str) -> str:
    import os

    if actor == "darain":
        return "SKIPPED"
    test_dirs = {
        "mishael": ["collector/tests", "backend/tests"],
        "sherwin": ["collector/tests"],
        "praveen": ["backend/tests"],
    }[actor]
    existing = [d for d in test_dirs if (REPO_ROOT / d).exists()]
    if not existing:
        return "NOT APPLICABLE"
    py_path = os.pathsep.join([str(REPO_ROOT / "collector" / "src"), str(REPO_ROOT / "backend")])
    for test_dir in existing:
        code, _ = run_cmd(
            [sys.executable, "-m", "pytest", "-p", "no:anyio", "-p", "no:cacheprovider", "--import-mode=importlib", test_dir, "-q"],
            extra_env={"PYTHONPATH": py_path},
        )
        if code != 0:
            return "FAIL"
    return "PASS"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run AegisOps engineering audit.")
    parser.add_argument("--actor", required=True, choices=sorted(TEAM_PROFILES.keys()))
    parser.add_argument("--action", default="pre_commit_audit")
    parser.add_argument("--task", default="UNSPECIFIED")
    parser.add_argument("--tool", default=None, help="AI coding tool used")
    parser.add_argument("--skip-tests", action="store_true")
    parser.add_argument("--allow-integration-override", action="store_true")
    parser.add_argument("--next-action", default="Proceed with authorized Git workflow")
    args = parser.parse_args()

    profile = TEAM_PROFILES[args.actor]
    tool_used = args.tool or profile["default_tool"]
    branch = get_git_branch()
    commit_sha = get_git_commit_sha()
    changed_files = get_changed_files()

    # 1. Whitespace/conflict marker check
    diff_code, _, _ = run_git(["diff", "--check"])
    diff_status = "PASS" if diff_code == 0 else "FAIL"

    # 2. Ownership check
    own_ok, own_violations, _ = check_ownership(
        actor=args.actor,
        branch=branch,
        allow_integration_override=args.allow_integration_override,
    )
    own_status = "PASS" if own_ok else "FAIL"

    # 3. Contract validation
    contract_ok, contract_errors = verify_contracts()
    contract_status = "PASS" if contract_ok else "FAIL"

    # 4. Secret scan
    secret_ok, secret_findings = scan_repository()
    secret_status = "PASS" if secret_ok else "FAIL"

    # 5. Lint & Tests
    lint_status = run_lint_check(args.actor)
    test_status = "SKIPPED" if args.skip_tests else run_test_check(args.actor)

    required_statuses = [diff_status, own_status, contract_status, secret_status, test_status]
    failed = any(st == "FAIL" for st in required_statuses) or lint_status == "FAIL"
    overall_result = "BLOCKED" if failed else "PASS"
    risk_level = "HIGH" if failed else ("MEDIUM" if any(f.startswith("contracts/") for f in changed_files) else "LOW")
    integration_impact = (
        "Shared contracts modified — notify affected owners"
        if any(f.startswith("contracts/") for f in changed_files)
        else "Module-scoped or governance update"
    )

    record = {
        "timestamp_utc": utc_now_iso(),
        "actor": profile["member_id"],
        "human_name": profile["name"],
        "role": profile["role"],
        "ai_tool": tool_used,
        "action": args.action,
        "task": args.task,
        "branch": branch,
        "commit_sha": commit_sha,
        "files_changed": changed_files,
        "checks": {
            "diff_check": diff_status,
            "ownership": own_status,
            "contracts": contract_status,
            "secret_scan": secret_status,
            "lint": lint_status,
            "tests": test_status,
        },
        "integration_impact": integration_impact,
        "risk_level": risk_level,
        "result": overall_result,
        "next_action": args.next_action,
    }
    append_audit_record(record)

    print("ENGINEERING AUDIT")
    print(f"Actor: {profile['name']} ({profile['member_id']}) — {profile['role']}")
    print(f"AI Tool: {tool_used}")
    print(f"Task: {args.task}")
    print(f"Branch: {branch}")
    print(f"Current commit: {commit_sha}")
    print(f"Changed files ({len(changed_files)}): {', '.join(changed_files[:12])}" + (" ..." if len(changed_files) > 12 else ""))
    print(f"Git diff check: {diff_status}")
    print(f"Ownership check: {own_status}")
    print(f"Contract check: {contract_status}")
    print(f"Lint: {lint_status}")
    print(f"Tests: {test_status}")
    print(f"Secret scan: {secret_status}")
    print(f"Integration impact: {integration_impact}")
    print(f"Risk level: {risk_level}")
    print(f"Result: {overall_result}")
    print(f"Next action: {args.next_action}")

    if own_violations:
        print("\nOwnership violations:")
        for v in own_violations:
            print(f"  - {v}")
    if contract_errors:
        print("\nContract errors:")
        for e in contract_errors:
            print(f"  - {e}")
    if secret_findings:
        print("\nSecret scan findings:")
        for s in secret_findings:
            print(f"  - {s}")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
