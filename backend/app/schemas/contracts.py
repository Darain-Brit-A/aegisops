"""Strict Pydantic v2 schemas for Tier 2 SaaS API (extra='forbid' on all ingest boundaries)."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

UTC_ISO_PATTERN = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,6})?(Z|\+00:00)$"
UUID_PATTERN = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
SLUG_PATTERN = r"^[a-z0-9][a-z0-9_-]{2,63}$"


class TelemetryMetadataIn(BaseModel):
    """Strict mirror of contracts/metadata.schema.json with additionalProperties=false."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"]
    payload_id: str = Field(pattern=UUID_PATTERN)
    collector_id: str = Field(pattern=SLUG_PATTERN)
    tenant_id: str = Field(pattern=SLUG_PATTERN)
    environment_id: str = Field(pattern=SLUG_PATTERN)
    region_id: Literal["ap-south-1", "eu-central-1", "us-east-1", "us-west-2"] = "ap-south-1"
    source_id: str = Field(pattern=r"^src_[a-f0-9]{16,32}$")
    event_time_utc: str = Field(pattern=UTC_ISO_PATTERN)
    collected_at_utc: str | None = Field(default=None, pattern=UTC_ISO_PATTERN)
    processed_at_utc: str | None = Field(default=None, pattern=UTC_ISO_PATTERN)
    source_timezone: str = Field(
        min_length=3,
        max_length=64,
        pattern=r"^(UTC|[A-Za-z_]+/[A-Za-z0-9_+-]+(/[A-Za-z0-9_+-]+)?)$",
    )
    event_category: Literal["infrastructure", "network", "security", "application", "collector"]
    severity: Literal["info", "warning", "high", "critical"]
    health_state: Literal["Excellent", "Good", "Fair", "Poor"]
    metric_name: Literal[
        "cpu_usage_percent",
        "memory_usage_percent",
        "disk_usage_percent",
        "service_availability_percent",
        "network_bandwidth_mbps",
        "network_latency_ms",
        "network_packet_loss_percent",
        "network_connectivity_status",
        "failed_auth_attempts_count",
        "suspicious_activity_score",
        "collector_queue_depth",
    ]
    metric_value: float = Field(ge=-1_000_000, le=1_000_000_000)
    metric_unit: Literal["percent", "ms", "mbps", "count", "ratio", "score", "status_code"]
    policy_version: str = Field(pattern=r"^[0-9]+(\.[0-9]+)?$", max_length=16)
    event_code: Literal[
        "METRIC_NORMAL",
        "CPU_THRESHOLD_BREACH",
        "CPU_ANOMALY",
        "MEMORY_THRESHOLD_BREACH",
        "MEMORY_ANOMALY",
        "DISK_PRESSURE",
        "SERVICE_DEGRADED",
        "SERVICE_UNAVAILABLE",
        "NETWORK_LATENCY_SPIKE",
        "NETWORK_PACKET_LOSS",
        "NETWORK_BANDWIDTH_SATURATION",
        "CONNECTIVITY_LOST",
        "AUTH_FAILURE_BURST",
        "SUSPICIOUS_SECURITY_SIGNAL",
        "RAW_SECRET_REDACTED_LOCALLY",
    ]
    summary_code: Literal[
        "BASELINE_NOMINAL",
        "MINOR_VARIANCE",
        "RESOURCE_DEVIATION",
        "NETWORK_DEGRADATION",
        "SECURITY_RISK_ELEVATED",
        "SERVICE_IMPACT_CRITICAL",
        "POLICY_REDACTED_SUMMARY",
    ]
    signal_count: int = Field(default=1, ge=1, le=1_000_000)
    redacted_field_count: int = Field(default=0, ge=0, le=1000)
    local_anomaly_score: float | None = Field(default=None, ge=0, le=100)


class HeartbeatIn(BaseModel):
    """Strict mirror of contracts/heartbeat.schema.json."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"]
    collector_id: str = Field(pattern=SLUG_PATTERN)
    tenant_id: str = Field(pattern=SLUG_PATTERN)
    environment_id: str = Field(pattern=SLUG_PATTERN)
    region_id: Literal["ap-south-1", "eu-central-1", "us-east-1", "us-west-2"]
    collector_version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9.]+)?$")
    config_status: Literal["valid", "degraded", "policy_mismatch"]
    policy_version: str = Field(pattern=r"^[0-9]+(\.[0-9]+)?$")
    sent_at_utc: str = Field(pattern=UTC_ISO_PATTERN)
    pending_outbox_count: int = Field(ge=0)
    retry_count: int = Field(ge=0)
    last_delivery_status: Literal["ok", "retrying", "offline", "rejected", "idle"]
    collector_cpu_percent: float | None = Field(default=None, ge=0, le=100)
    collector_memory_mb: float | None = Field(default=None, ge=0)


class RemediationApprovalIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operator_id: str = Field(min_length=2, max_length=64)
    justification: str = Field(min_length=4, max_length=500)
    confirm_simulation: Literal[True]


def parse_utc(ts: str) -> datetime:
    cleaned = ts.strip()
    if cleaned.endswith("Z"):
        return datetime.fromisoformat(cleaned[:-1]).replace(tzinfo=timezone.utc)
    dt = datetime.fromisoformat(cleaned)
    return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def format_utc(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    aware = dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    return aware.strftime("%Y-%m-%dT%H:%M:%S.%fZ") if aware.microsecond else aware.strftime("%Y-%m-%dT%H:%M:%SZ")


def canonical_json_and_sha256(raw_dict: dict[str, Any]) -> tuple[str, str]:
    cjson = json.dumps(raw_dict, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(cjson.encode("utf-8")).hexdigest()
    return cjson, digest
