"""Pluggable Tier 1 telemetry source adapters: simulator, psutil, and organizer_stream."""

from __future__ import annotations

import json
import socket
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import psutil


class TelemetrySourceAdapter(ABC):
    name: str

    @abstractmethod
    def collect(self) -> list[dict[str, Any]]:
        """Collect raw Tier 1 telemetry events."""


class PsutilLocalAdapter(TelemetrySourceAdapter):
    """Collects genuine local host CPU, memory, and disk telemetry inside Tier 1."""

    name = "psutil"

    def __init__(self, source_timezone: str = "Asia/Kolkata") -> None:
        self.source_timezone = source_timezone

    def collect(self) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        hostname = socket.gethostname()
        cpu = psutil.cpu_percent(interval=0.05)
        mem = psutil.virtual_memory().percent
        disk = psutil.disk_usage("/").percent if Path("/").exists() else 0.0
        return [
            {
                "adapter": self.name,
                "hostname": hostname,
                "source_timezone": self.source_timezone,
                "event_time_utc": now,
                "event_category": "infrastructure",
                "metric_name": "cpu_usage_percent",
                "metric_value": round(float(cpu), 2),
                "metric_unit": "percent",
                "raw_log": f"psutil local sample host={hostname} cpu={cpu}%",
            },
            {
                "adapter": self.name,
                "hostname": hostname,
                "source_timezone": self.source_timezone,
                "event_time_utc": now,
                "event_category": "infrastructure",
                "metric_name": "memory_usage_percent",
                "metric_value": round(float(mem), 2),
                "metric_unit": "percent",
                "raw_log": f"psutil local sample host={hostname} memory={mem}%",
            },
            {
                "adapter": self.name,
                "hostname": hostname,
                "source_timezone": self.source_timezone,
                "event_time_utc": now,
                "event_category": "infrastructure",
                "metric_name": "disk_usage_percent",
                "metric_value": round(float(disk), 2),
                "metric_unit": "percent",
                "raw_log": f"psutil local sample host={hostname} disk={disk}%",
            },
        ]


class SimulatorFixtureAdapter(TelemetrySourceAdapter):
    """Replays local synthetic test fixtures (explicitly NOT the official organizer stream)."""

    name = "simulator"

    def __init__(self, fixtures_path: Path | None = None) -> None:
        default_path = Path(__file__).resolve().parents[4] / "simulator" / "fixtures" / "sample_raw_events.json"
        self.fixtures_path = fixtures_path or default_path
        self._cursor = 0

    def collect(self) -> list[dict[str, Any]]:
        if not self.fixtures_path.exists():
            return []
        events = json.loads(self.fixtures_path.read_text(encoding="utf-8")).get("events", [])
        if not events:
            return []
        event = dict(events[self._cursor % len(events)])
        self._cursor += 1
        event["event_time_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        return [event]


class OrganizerStreamAdapter(TelemetrySourceAdapter):
    """Configurable HTTP/JSON adapter ready for the official CICADA 2026 telemetry stream."""

    name = "organizer_stream"

    def __init__(self, stream_url: str, timeout: float = 5.0) -> None:
        self.stream_url = stream_url
        self.timeout = timeout

    def collect(self) -> list[dict[str, Any]]:
        if not self.stream_url:
            return []
        resp = httpx.get(self.stream_url, timeout=self.timeout)
        resp.raise_for_status()
        payload = resp.json()
        if isinstance(payload, list):
            return [dict(item) for item in payload]
        if isinstance(payload, dict) and "events" in payload:
            return [dict(item) for item in payload["events"]]
        if isinstance(payload, dict):
            return [payload]
        return []
