"""Reproducible live scenario driver for AegisOps judge validation (Section 8).

Injects synthetic raw events into the Tier 1 Local Collector inspection endpoint
(127.0.0.1:8001/local/v1/inject) so the real collector pipeline performs local storage,
redaction, HMAC pseudonymization, egress proof logging, outbox buffering, and SaaS delivery.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parents[2]
SCENARIOS_PATH = REPO_ROOT / "simulator" / "scenarios" / "scenarios.json"
FIXTURES_PATH = REPO_ROOT / "simulator" / "fixtures" / "sample_raw_events.json"


def load_data() -> tuple[list[dict], list[dict]]:
    scenarios = json.loads(SCENARIOS_PATH.read_text(encoding="utf-8"))["scenarios"]
    events = json.loads(FIXTURES_PATH.read_text(encoding="utf-8"))["events"]
    return scenarios, events


def main() -> int:
    parser = argparse.ArgumentParser(description="Run AegisOps live validation scenarios.")
    parser.add_argument("--list", action="store_true", help="List available scenarios")
    parser.add_argument("--scenario", help="Scenario ID to inject (or 'all')")
    parser.add_argument(
        "--collector-url",
        default="http://127.0.0.1:8001/local/v1/inject",
        help="Tier 1 local collector inject endpoint",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print payloads without sending HTTP requests")
    args = parser.parse_args()

    scenarios, events = load_data()
    if args.list or not args.scenario:
        print("Available AegisOps Live Validation Scenarios (Section 8):")
        for sc in scenarios:
            print(f"  - {sc['id']:22s} : {sc['title']} ({sc['expected_behavior']})")
        return 0

    selected = scenarios if args.scenario == "all" else [s for s in scenarios if s["id"] == args.scenario]
    if not selected:
        print(f"[FAIL] Unknown scenario '{args.scenario}'. Use --list to see valid IDs.")
        return 1

    events_by_scenario: dict[str, list[dict]] = {}
    for ev in events:
        events_by_scenario.setdefault(ev["scenario_id"], []).append(ev)

    for sc in selected:
        sc_events = events_by_scenario.get(sc["id"], [])
        print(f"\n=== Scenario: {sc['id']} — {sc['title']} ===")
        print(f"Expected: {sc['expected_behavior']}")
        if not sc_events:
            print("  (Operational scenario — follow docs/DEMO_RUNBOOK.md control step)")
            continue
        for ev in sc_events:
            if args.dry_run:
                print(f"  [DRY-RUN] Would POST to {args.collector_url}: {json.dumps(ev)}")
                continue
            try:
                resp = httpx.post(args.collector_url, json=ev, timeout=5.0)
                print(f"  POST {args.collector_url} -> HTTP {resp.status_code}")
            except httpx.HTTPError as exc:
                print(f"  [ERROR] Failed to reach local collector at {args.collector_url}: {exc}")
                return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
