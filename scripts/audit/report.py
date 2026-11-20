"""Generates a concise human-readable audit summary from audit/activity.jsonl."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import AUDIT_LOG_PATH, REPO_ROOT, utc_now_iso  # noqa: E402


def main() -> int:
    if not AUDIT_LOG_PATH.exists():
        print("No audit entries found yet.")
        return 0

    lines = [line.strip() for line in AUDIT_LOG_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    records = [json.loads(line) for line in lines]

    print(f"AegisOps Audit Report — Generated {utc_now_iso()}")
    print(f"Total entries: {len(records)}")
    print("-" * 72)
    for rec in records[-15:]:
        print(
            f"[{rec.get('timestamp_utc')}] {rec.get('human_name', rec.get('actor'))} | "
            f"{rec.get('action')} | branch={rec.get('branch')} | "
            f"commit={str(rec.get('commit_sha', ''))[:8]} | result={rec.get('result')}"
        )

    checkpoint_dir = REPO_ROOT / "audit" / "checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    summary_path = checkpoint_dir / "latest_report.md"
    md_lines = [
        "# AegisOps Latest Engineering Audit Report",
        "",
        f"- Generated (UTC): `{utc_now_iso()}`",
        f"- Total Audit Entries: `{len(records)}`",
        "",
        "| Timestamp (UTC) | Member | Action | Branch | Commit | Result |",
        "| :--- | :--- | :--- | :--- | :--- | :--- |",
    ]
    for rec in records[-25:]:
        md_lines.append(
            f"| `{rec.get('timestamp_utc')}` | {rec.get('human_name', rec.get('actor'))} | "
            f"`{rec.get('action')}` | `{rec.get('branch')}` | `{str(rec.get('commit_sha', ''))[:8]}` | "
            f"**{rec.get('result')}** |"
        )
    summary_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    print(f"\nWrote checkpoint report: {summary_path.relative_to(REPO_ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
