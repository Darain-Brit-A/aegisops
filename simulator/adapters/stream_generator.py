"""Synthetic local telemetry fixture generator for AegisOps development.

Explicitly labeled as a local development simulator — NOT the official organizer-provided
CICADA 2026 simulated telemetry stream. Generates realistic baseline series + anomalies
for Tier 1 Collector adapter testing.
"""

from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

FIXTURES_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "sample_raw_events.json"


def load_static_fixtures() -> list[dict[str, Any]]:
    data = json.loads(FIXTURES_PATH.read_text(encoding="utf-8"))
    return list(data.get("events", []))


def generate_baseline_series(
    *,
    hostname: str = "app-checkout-01.internal",
    ip_address: str = "10.42.4.12",
    source_timezone: str = "Asia/Kolkata",
    metric_name: str = "cpu_usage_percent",
    baseline_value: float = 34.0,
    jitter: float = 3.5,
    count: int = 12,
    include_spike: bool = True,
    spike_value: float = 95.8,
    seed: int = 42,
) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    now = datetime.now(timezone.utc)
    start = now - timedelta(seconds=count * 10)
    events: list[dict[str, Any]] = []

    for idx in range(count):
        ts = (start + timedelta(seconds=idx * 10)).strftime("%Y-%m-%dT%H:%M:%SZ")
        val = round(max(0.0, baseline_value + rng.uniform(-jitter, jitter)), 2)
        events.append(
            {
                "scenario_id": "baseline_series",
                "adapter": "simulator_fixture",
                "hostname": hostname,
                "ip_address": ip_address,
                "source_timezone": source_timezone,
                "event_time_utc": ts,
                "event_category": "infrastructure",
                "metric_name": metric_name,
                "metric_value": val,
                "metric_unit": "percent",
                "raw_log": f"synthetic baseline sample #{idx + 1} host={hostname} ip={ip_address}",
            }
        )

    if include_spike:
        events.append(
            {
                "scenario_id": "cpu_baseline_deviation",
                "adapter": "simulator_fixture",
                "hostname": hostname,
                "ip_address": ip_address,
                "source_timezone": source_timezone,
                "event_time_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "event_category": "infrastructure",
                "metric_name": metric_name,
                "metric_value": spike_value,
                "metric_unit": "percent",
                "raw_log": f"synthetic anomaly spike host={hostname} token=AEGIS_DEMO_SECRET_TOKEN_9F2A",
            }
        )

    return events
