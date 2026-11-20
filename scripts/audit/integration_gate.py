"""AegisOps Integration Gate — required before merging `integration` -> `main`."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_secrets import scan_repository  # noqa: E402
from common import REPO_ROOT, append_audit_record, get_git_branch, get_git_commit_sha, utc_now_iso  # noqa: E402
from verify_contracts import verify_all as verify_contracts  # noqa: E402


def run_step(name: str, cmd: list[str]) -> tuple[str, str]:
    import os

    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join([str(REPO_ROOT / "collector" / "src"), str(REPO_ROOT / "backend")])
    proc = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, check=False, env=env)
    status = "PASS" if proc.returncode == 0 else "FAIL"
    detail = (proc.stdout + "\n" + proc.stderr).strip()
    return status, detail


def main() -> int:
    results: dict[str, str] = {}
    failures: list[str] = []

    contracts_ok, contract_errs = verify_contracts()
    results["contracts"] = "PASS" if contracts_ok else "FAIL"
    if not contracts_ok:
        failures.extend(contract_errs)

    secrets_ok, secret_errs = scan_repository()
    results["secret_scan"] = "PASS" if secrets_ok else "FAIL"
    if not secrets_ok:
        failures.extend(secret_errs)

    for label, cmd in [
        ("collector_tests", [sys.executable, "-m", "pytest", "-p", "no:anyio", "-p", "no:cacheprovider", "--import-mode=importlib", "collector/tests", "-q"]),
        ("backend_tests", [sys.executable, "-m", "pytest", "-p", "no:anyio", "-p", "no:cacheprovider", "--import-mode=importlib", "backend/tests", "-q"]),
        ("smoke_test", [sys.executable, "scripts/validation/smoke_test.py"]),
    ]:
        status, detail = run_step(label, cmd)
        results[label] = status
        if status == "FAIL":
            failures.append(f"{label} failed:\n{detail}")

    overall = "FAIL" if failures else "PASS"
    append_audit_record(
        {
            "timestamp_utc": utc_now_iso(),
            "actor": "member-01",
            "human_name": "Mishael",
            "role": "Lead Systems Architect, DevOps & Integration Engineer",
            "ai_tool": "Antigravity Pro",
            "action": "integration_gate",
            "task": "INTEGRATION_GATE",
            "branch": get_git_branch(),
            "commit_sha": get_git_commit_sha(),
            "files_changed": [],
            "checks": results,
            "result": overall,
            "next_action": "Merge to main approved" if overall == "PASS" else "Fix failing gate checks before merge",
        }
    )

    print("AEGISOPS INTEGRATION GATE")
    for key, val in results.items():
        print(f"  - {key}: {val}")
    print(f"Overall: {overall}")
    if failures:
        print("\nFailures:")
        for f in failures:
            print(f"  * {f}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
