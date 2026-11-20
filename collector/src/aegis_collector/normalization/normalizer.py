"""Local normalization, UTC timestamp enrichment, and Tier 1 threshold/security analysis."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from aegis_collector.config import CollectorConfig
from aegis_collector.security.policy import (
    ApprovedMetadataPayload,
    detect_sensitive_fields,
    pseudonymize_source,
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def normalize_event_time_utc(raw_timestamp: str | None, source_timezone: str) -> str:
    """Parse any ISO-8601 timestamp (UTC or local with offset/IANA TZ) into strict UTC ISO-8601."""
    if not raw_timestamp:
        return utc_now_iso()

    ts = raw_timestamp.strip()
    if ts.endswith("Z"):
        dt = datetime.fromisoformat(ts[:-1]).replace(tzinfo=timezone.utc)
    else:
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            try:
                tz = ZoneInfo(source_timezone)
            except ZoneInfoNotFoundError:
                tz = timezone.utc
            dt = dt.replace(tzinfo=tz)
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ") if dt.microsecond else dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def classify_local_signal(
    metric_name: str,
    metric_value: float,
    secret_detected: bool,
) -> tuple[str, str, str, str, float]:
    """Deterministic Tier 1 local classification returning (severity, health_state, event_code, summary_code, score)."""
    if metric_name == "cpu_usage_percent":
        if metric_value >= 95.0:
            return "critical", "Poor", "CPU_THRESHOLD_BREACH", "SERVICE_IMPACT_CRITICAL", 9.0
        if metric_value >= 80.0:
            return "warning", "Fair", "CPU_ANOMALY", "RESOURCE_DEVIATION", 5.5
        if metric_value >= 65.0:
            return "info", "Good", "METRIC_NORMAL", "MINOR_VARIANCE", 2.0

    elif metric_name == "memory_usage_percent":
        if metric_value >= 95.0:
            return "critical", "Poor", "MEMORY_THRESHOLD_BREACH", "SERVICE_IMPACT_CRITICAL", 9.0
        if metric_value >= 80.0:
            return "high" if metric_value >= 90.0 else "warning", "Fair", "MEMORY_ANOMALY", "RESOURCE_DEVIATION", 6.0
        if metric_value >= 70.0:
            return "info", "Good", "METRIC_NORMAL", "MINOR_VARIANCE", 2.0

    elif metric_name == "disk_usage_percent":
        if metric_value >= 92.0:
            return "critical", "Poor", "DISK_PRESSURE", "SERVICE_IMPACT_CRITICAL", 8.0
        if metric_value >= 80.0:
            return "warning", "Fair", "DISK_PRESSURE", "RESOURCE_DEVIATION", 4.5

    elif metric_name == "network_latency_ms":
        if metric_value >= 300.0:
            return "critical", "Poor", "NETWORK_LATENCY_SPIKE", "NETWORK_DEGRADATION", 8.5
        if metric_value >= 150.0:
            return "high" if metric_value >= 220.0 else "warning", "Fair", "NETWORK_LATENCY_SPIKE", "NETWORK_DEGRADATION", 6.0
        if metric_value >= 80.0:
            return "info", "Good", "METRIC_NORMAL", "MINOR_VARIANCE", 2.0

    elif metric_name == "network_packet_loss_percent":
        if metric_value >= 10.0:
            return "critical", "Poor", "NETWORK_PACKET_LOSS", "NETWORK_DEGRADATION", 9.5
        if metric_value >= 2.0:
            return "warning", "Fair", "NETWORK_PACKET_LOSS", "NETWORK_DEGRADATION", 5.0

    elif metric_name == "service_availability_percent":
        if metric_value < 95.0:
            return "critical", "Poor", "SERVICE_UNAVAILABLE", "SERVICE_IMPACT_CRITICAL", 9.5
        if metric_value < 99.5:
            return "warning", "Fair", "SERVICE_DEGRADED", "SERVICE_IMPACT_CRITICAL", 4.5

    elif metric_name == "failed_auth_attempts_count":
        if metric_value >= 20:
            return "critical", "Poor", "AUTH_FAILURE_BURST", "SECURITY_RISK_ELEVATED", 9.0
        if metric_value >= 8:
            return "warning", "Fair", "AUTH_FAILURE_BURST", "SECURITY_RISK_ELEVATED", 5.5

    elif metric_name == "suspicious_activity_score":
        if metric_value >= 80.0:
            return "critical", "Poor", "SUSPICIOUS_SECURITY_SIGNAL", "SECURITY_RISK_ELEVATED", 8.5
        if metric_value >= 50.0:
            return "warning", "Fair", "SUSPICIOUS_SECURITY_SIGNAL", "SECURITY_RISK_ELEVATED", 5.0

    if secret_detected:
        return "info", "Good", "RAW_SECRET_REDACTED_LOCALLY", "POLICY_REDACTED_SUMMARY", 1.0

    return "info", "Excellent", "METRIC_NORMAL", "BASELINE_NOMINAL", 0.0


def build_allowlisted_metadata(
    raw_event: dict[str, Any],
    config: CollectorConfig,
    collected_at_utc: str,
) -> tuple[ApprovedMetadataPayload, list[str]]:
    """Construct a brand-new allow-listed metadata object from raw Tier 1 telemetry."""
    redacted_fields, secret_detected = detect_sensitive_fields(raw_event)

    raw_source_key = str(
        raw_event.get("hostname")
        or raw_event.get("host")
        or raw_event.get("ip_address")
        or raw_event.get("source_ip")
        or raw_event.get("source_name")
        or "local-host-default"
    )
    source_id = pseudonymize_source(raw_source_key, config.hmac_secret)
    source_tz = str(raw_event.get("source_timezone") or config.source_timezone)
    event_time_utc = normalize_event_time_utc(raw_event.get("event_time_utc"), source_tz)

    metric_name = str(raw_event.get("metric_name", ""))
    metric_value = float(raw_event.get("metric_value", 0.0))
    metric_unit = str(raw_event.get("metric_unit", "percent"))
    event_category = str(raw_event.get("event_category", "infrastructure"))
    signal_count = int(raw_event.get("signal_count", 1))
    payload_id = str(raw_event.get("payload_id") or uuid.uuid4())

    severity, health_state, event_code, summary_code, local_score = classify_local_signal(
        metric_name=metric_name,
        metric_value=metric_value,
        secret_detected=secret_detected,
    )

    processed_at_utc = utc_now_iso()

    # Construct brand-new allow-listed object — NEVER copy raw_event!
    approved = ApprovedMetadataPayload(
        schema_version="1.0",
        payload_id=payload_id,
        collector_id=config.collector_id,
        tenant_id=config.tenant_id,
        environment_id=str(raw_event.get("environment_id") or config.environment_id),
        region_id=config.region_id,  # type: ignore[arg-type]
        source_id=source_id,
        event_time_utc=event_time_utc,
        collected_at_utc=collected_at_utc,
        processed_at_utc=processed_at_utc,
        source_timezone=source_tz,
        event_category=event_category,  # type: ignore[arg-type]
        severity=severity,  # type: ignore[arg-type]
        health_state=health_state,  # type: ignore[arg-type]
        metric_name=metric_name,  # type: ignore[arg-type]
        metric_value=metric_value,
        metric_unit=metric_unit,  # type: ignore[arg-type]
        policy_version=config.policy_version,
        event_code=event_code,  # type: ignore[arg-type]
        summary_code=summary_code,  # type: ignore[arg-type]
        signal_count=signal_count,
        redacted_field_count=len(redacted_fields),
        local_anomaly_score=local_score,
    )
    return approved, redacted_fields
