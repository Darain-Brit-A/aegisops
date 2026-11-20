"""Verifies that changed files respect AegisOps four-person module ownership."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import TEAM_PROFILES, get_changed_files, get_git_branch  # noqa: E402


def infer_actor_from_branch(branch: str) -> str | None:
    lowered = branch.lower()
    for actor, profile in TEAM_PROFILES.items():
        if lowered.startswith(profile["branch_prefix"]):
            return actor
    if lowered in {"main", "integration"}:
        return "mishael"
    return None


def is_path_owned(actor: str, rel_path: str) -> bool:
    profile = TEAM_PROFILES[actor]
    normalized = rel_path.replace("\\", "/").lstrip("./")
    if normalized in profile["allowed_exact"]:
        return True
    return any(normalized.startswith(prefix) for prefix in profile["allowed_prefixes"])


def check_ownership(
    actor: str | None = None,
    base_ref: str | None = None,
    branch: str | None = None,
    allow_integration_override: bool = False,
) -> tuple[bool, list[str], str]:
    active_branch = branch or get_git_branch()
    resolved_actor = (actor or infer_actor_from_branch(active_branch) or "").lower()

    if resolved_actor not in TEAM_PROFILES:
        return (
            False,
            [f"Could not determine authorized actor from --actor or branch '{active_branch}'."],
            resolved_actor or "unknown",
        )

    changed = get_changed_files(base_ref=base_ref)
    if not changed:
        return True, [], resolved_actor

    violations: list[str] = []
    for path in changed:
        if not is_path_owned(resolved_actor, path):
            if allow_integration_override and resolved_actor == "mishael":
                continue
            violations.append(
                f"Unauthorized path '{path}' for actor '{resolved_actor}' ({TEAM_PROFILES[resolved_actor]['role']})"
            )

    return len(violations) == 0, violations, resolved_actor


def main() -> int:
    parser = argparse.ArgumentParser(description="Check AegisOps file ownership boundaries.")
    parser.add_argument("--actor", choices=sorted(TEAM_PROFILES.keys()), help="Human team member")
    parser.add_argument("--base-ref", help="Git base ref for PR diff (e.g. origin/integration)")
    parser.add_argument("--branch", help="Branch name override (for CI)")
    parser.add_argument(
        "--allow-integration-override",
        action="store_true",
        help="Allow Member 01 (Mishael) reviewed cross-module bootstrap/integration edits.",
    )
    args = parser.parse_args()

    ok, violations, resolved_actor = check_ownership(
        actor=args.actor,
        base_ref=args.base_ref,
        branch=args.branch,
        allow_integration_override=args.allow_integration_override,
    )
    if ok:
        print(f"[PASS] Ownership check passed for actor '{resolved_actor}'.")
        return 0
    print(f"[FAIL] Ownership violations detected for actor '{resolved_actor}':")
    for v in violations:
        print(f"  - {v}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
