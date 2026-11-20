"""Default-deny egress policy, HMAC pseudonymization, and canonical serialization.

NON-NEGOTIABLE SECURITY INVARIANTS:
1. Outbound payloads are ALWAYS built from a fresh Pydantic model with extra='forbid'
   strictly matching contracts/metadata.schema.json. NEVER copy raw JSON and pop keys.
2. Source identifiers are HMAC-SHA256 pseudonyms salted with a local-only secret.
3. ONE canonical serialization function produces the exact UTF-8 bytes used for
   egress proof display, SHA-256 hashing, SQLite outbox persistence, and HTTP transport.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

EventCategory = Literal["infrastructure", "network", "security", "application", "collector"]
SeverityLevel = Literal["info", "warning", "high", "critical"]
HealthState = Literal["Excellent", "Good", "Fair", "Poor"]
RegionId = Literal["ap-south-1", "eu-central-1", "us-east-1", "us-west-2"]
MetricName = Literal[
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
MetricUnit = Literal["percent", "ms", "mbps", "count", "ratio", "score", "status_code"]
EventCode = Literal[
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
SummaryCode = Literal[
    "BASELINE_NOMINAL",
    "MINOR_VARIANCE",
    "RESOURCE_DEVIATION",
    "NETWORK_DEGRADATION",
    "SECURITY_RISK_ELEVATED",
    "SERVICE_IMPACT_CRITICAL",
    "POLICY_REDACTED_SUMMARY",
]

SENSITIVE_KEY_NAMES = {
    "raw_log",
    "message",
    "stack_trace",
    "exception",
    "exception_detail",
    "password",
    "passwd",
    "secret",
    "api_key",
    "apikey",
    "token",
    "access_token",
    "refresh_token",
    "authorization",
    "cookie",
    "private_key",
    "hostname",
    "fqdn",
    "host",
    "ip_address",
    "ip",
    "source_ip",
    "dest_ip",
    "mac_address",
    "username",
    "user",
    "user_email",
    "email",
    "account_id",
    "session_id",
    "request_body",
    "sql_query",
}

SECRET_VALUE_PATTERNS = [
    re.compile(r"password\s*=", re.IGNORECASE),
    re.compile(r"token\s*=", re.IGNORECASE),
    re.compile(r"api[_-]?key\s*=", re.IGNORECASE),
    re.compile(r"AEGIS_DEMO_SECRET", re.IGNORECASE),
    re.compile(r"SYNTHETIC_DEMO_PASS", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b"),
]

UTC_ISO_PATTERN = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,6})?(Z|\+00:00)$"
UUID_PATTERN = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
SLUG_PATTERN = r"^[a-z0-9][a-z0-9_-]{2,63}$"


class ApprovedMetadataPayload(BaseModel):
    """Strict allow-listed outbound payload conforming to contracts/metadata.schema.json."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    payload_id: str = Field(pattern=UUID_PATTERN)
    collector_id: str = Field(pattern=SLUG_PATTERN)
    tenant_id: str = Field(pattern=SLUG_PATTERN)
    environment_id: str = Field(pattern=SLUG_PATTERN)
    region_id: RegionId
    source_id: str = Field(pattern=r"^src_[a-f0-9]{16,32}$")
    event_time_utc: str = Field(pattern=UTC_ISO_PATTERN)
    collected_at_utc: str | None = Field(default=None, pattern=UTC_ISO_PATTERN)
    processed_at_utc: str | None = Field(default=None, pattern=UTC_ISO_PATTERN)
    source_timezone: str = Field(
        min_length=3,
        max_length=64,
        pattern=r"^(UTC|[A-Za-z_]+/[A-Za-z0-9_+-]+(/[A-Za-z0-9_+-]+)?)$",
    )
    event_category: EventCategory
    severity: SeverityLevel
    health_state: HealthState
    metric_name: MetricName
    metric_value: float = Field(ge=-1_000_000, le=1_000_000_000)
    metric_unit: MetricUnit
    policy_version: str = Field(pattern=r"^[0-9]+(\.[0-9]+)?$", max_length=16)
    event_code: EventCode
    summary_code: SummaryCode
    signal_count: int = Field(default=1, ge=1, le=1_000_000)
    redacted_field_count: int = Field(default=0, ge=0, le=1000)
    local_anomaly_score: float | None = Field(default=None, ge=0, le=100)


class CollectorHeartbeatPayload(BaseModel):
    """Strict collector heartbeat payload conforming to contracts/heartbeat.schema.json."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    collector_id: str = Field(pattern=SLUG_PATTERN)
    tenant_id: str = Field(pattern=SLUG_PATTERN)
    environment_id: str = Field(pattern=SLUG_PATTERN)
    region_id: RegionId
    collector_version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9.]+)?$")
    config_status: Literal["valid", "degraded", "policy_mismatch"] = "valid"
    policy_version: str = Field(pattern=r"^[0-9]+(\.[0-9]+)?$")
    sent_at_utc: str = Field(pattern=UTC_ISO_PATTERN)
    pending_outbox_count: int = Field(ge=0)
    retry_count: int = Field(ge=0)
    last_delivery_status: Literal["ok", "retrying", "offline", "rejected", "idle"]
    collector_cpu_percent: float | None = Field(default=None, ge=0, le=100)
    collector_memory_mb: float | None = Field(default=None, ge=0)


def pseudonymize_source(raw_source_key: str, hmac_secret: str) -> str:
    """Derive a stable, non-reversible HMAC-SHA256 pseudonymous source_id locally."""
    digest = hmac.new(
        hmac_secret.encode("utf-8"),
        raw_source_key.strip().lower().encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"src_{digest[:20]}"


def detect_sensitive_fields(raw_event: dict[str, Any]) -> tuple[list[str], bool]:
    """Identify sensitive field names retained locally and whether secret values were spotted."""
    redacted: list[str] = []
    secret_detected = False

    for key, value in raw_event.items():
        lower_key = key.lower()
        is_sensitive_key = lower_key in SENSITIVE_KEY_NAMES or any(
            marker in lower_key for marker in ("secret", "password", "token", "key", "auth", "cookie", "ip", "host")
        )
        is_secret_val = False
        if isinstance(value, str):
            for pat in SECRET_VALUE_PATTERNS:
                if pat.search(value):
                    is_secret_val = True
                    secret_detected = True
                    break
        if is_sensitive_key or is_secret_val:
            redacted.append(key)
            if lower_key in {"password", "passwd", "secret", "api_key", "token", "access_token", "private_key"}:
                secret_detected = True

    return sorted(set(redacted)), secret_detected


def canonical_serialize_and_hash(payload: ApprovedMetadataPayload | dict[str, Any]) -> tuple[str, bytes, str]:
    """Single canonical serializer shared by Egress Proof, SHA-256 hash, Outbox, and HTTP transport."""
    if isinstance(payload, ApprovedMetadataPayload):
        data = payload.model_dump(exclude_none=True)
    else:
        data = payload
    canonical_json = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    canonical_bytes = canonical_json.encode("utf-8")
    payload_sha256 = hashlib.sha256(canonical_bytes).hexdigest()
    return canonical_json, canonical_bytes, payload_sha256
