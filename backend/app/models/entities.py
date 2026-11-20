"""SQLAlchemy 2 ORM models for AegisOps Tier 2 Multi-Tenant Metadata-Only SaaS.

Every tenant-owned table enforces an explicit tenant_id foreign key.
TelemetryEvent enforces UNIQUE(tenant_id, payload_id) for idempotent delivery.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Tenant(Base):
    __tablename__ = "tenants"

    tenant_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    region_id: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class Environment(Base):
    __tablename__ = "environments"
    __table_args__ = (UniqueConstraint("tenant_id", "environment_id", name="uq_env_tenant"),)

    environment_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), ForeignKey("tenants.tenant_id"), nullable=False, index=True)
    region_id: Mapped[str] = mapped_column(String(32), nullable=False)
    display_label: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class OperatorCredential(Base):
    __tablename__ = "operator_credentials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), ForeignKey("tenants.tenant_id"), nullable=False, index=True)
    operator_id: Mapped[str] = mapped_column(String(64), nullable=False)
    role: Mapped[str] = mapped_column(String(32), default="operator", nullable=False)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    created_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class Collector(Base):
    __tablename__ = "collectors"

    collector_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), ForeignKey("tenants.tenant_id"), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(64), ForeignKey("environments.environment_id"), nullable=False)
    region_id: Mapped[str] = mapped_column(String(32), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    token_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    collector_version: Mapped[str] = mapped_column(String(32), default="0.1.0", nullable=False)
    config_status: Mapped[str] = mapped_column(String(32), default="valid", nullable=False)
    policy_version: Mapped[str] = mapped_column(String(16), default="1", nullable=False)
    health_state: Mapped[str] = mapped_column(String(16), default="Good", nullable=False)
    connection_state: Mapped[str] = mapped_column(String(32), default="idle", nullable=False)
    last_heartbeat_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_reconnect_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pending_outbox_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_delivery_status: Mapped[str] = mapped_column(String(32), default="idle", nullable=False)
    collector_cpu_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    collector_memory_mb: Mapped[float | None] = mapped_column(Float, nullable=True)


class TelemetryEvent(Base):
    __tablename__ = "telemetry_events"
    __table_args__ = (
        UniqueConstraint("tenant_id", "payload_id", name="uq_telemetry_tenant_payload"),
        Index("idx_telemetry_tenant_event_time", "tenant_id", "event_time_utc"),
        Index("idx_telemetry_tenant_source_metric", "tenant_id", "source_id", "metric_name", "event_time_utc"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), ForeignKey("tenants.tenant_id"), nullable=False, index=True)
    payload_id: Mapped[str] = mapped_column(String(64), nullable=False)
    collector_id: Mapped[str] = mapped_column(String(64), ForeignKey("collectors.collector_id"), nullable=False)
    environment_id: Mapped[str] = mapped_column(String(64), nullable=False)
    region_id: Mapped[str] = mapped_column(String(32), nullable=False)
    source_id: Mapped[str] = mapped_column(String(64), nullable=False)
    event_time_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    collected_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processed_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ingested_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    source_timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    event_category: Mapped[str] = mapped_column(String(32), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    health_state: Mapped[str] = mapped_column(String(16), nullable=False)
    metric_name: Mapped[str] = mapped_column(String(64), nullable=False)
    metric_value: Mapped[float] = mapped_column(Float, nullable=False)
    metric_unit: Mapped[str] = mapped_column(String(32), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(16), nullable=False)
    event_code: Mapped[str] = mapped_column(String(64), nullable=False)
    summary_code: Mapped[str] = mapped_column(String(64), nullable=False)
    signal_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    redacted_field_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    local_anomaly_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    canonical_json: Mapped[str] = mapped_column(Text, nullable=False)
    out_of_order: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class CollectorHeartbeat(Base):
    __tablename__ = "collector_heartbeats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), ForeignKey("tenants.tenant_id"), nullable=False, index=True)
    collector_id: Mapped[str] = mapped_column(String(64), ForeignKey("collectors.collector_id"), nullable=False)
    sent_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    pending_outbox_count: Mapped[int] = mapped_column(Integer, nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False)
    last_delivery_status: Mapped[str] = mapped_column(String(32), nullable=False)
    collector_cpu_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    collector_memory_mb: Mapped[float | None] = mapped_column(Float, nullable=True)


class HealthTransition(Base):
    __tablename__ = "health_transitions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), ForeignKey("tenants.tenant_id"), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    from_state: Mapped[str | None] = mapped_column(String(16), nullable=True)
    to_state: Mapped[str] = mapped_column(String(16), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(64), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    changed_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class Anomaly(Base):
    __tablename__ = "anomalies"

    anomaly_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), ForeignKey("tenants.tenant_id"), nullable=False, index=True)
    payload_id: Mapped[str] = mapped_column(String(64), nullable=False)
    environment_id: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[str] = mapped_column(String(64), nullable=False)
    event_category: Mapped[str] = mapped_column(String(32), nullable=False)
    metric_name: Mapped[str] = mapped_column(String(64), nullable=False)
    metric_value: Mapped[float] = mapped_column(Float, nullable=False)
    baseline_median: Mapped[float | None] = mapped_column(Float, nullable=True)
    baseline_mad: Mapped[float | None] = mapped_column(Float, nullable=True)
    robust_z_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    detector_method: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    event_time_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    detected_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class Incident(Base):
    __tablename__ = "incidents"

    incident_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), ForeignKey("tenants.tenant_id"), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(64), nullable=False)
    region_id: Mapped[str] = mapped_column(String(32), nullable=False)
    correlation_group: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="open", nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    correlation_rule: Mapped[str] = mapped_column(String(128), nullable=False)
    correlation_explanation: Mapped[str] = mapped_column(Text, nullable=False)
    probable_cause: Mapped[str] = mapped_column(Text, nullable=False)
    uncertainty_note: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    evidence_score_formula: Mapped[str] = mapped_column(Text, nullable=False)
    first_observed_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_observed_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    alert_created_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class IncidentEvidence(Base):
    __tablename__ = "incident_evidence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), ForeignKey("tenants.tenant_id"), nullable=False, index=True)
    incident_id: Mapped[str] = mapped_column(String(64), ForeignKey("incidents.incident_id"), nullable=False, index=True)
    anomaly_id: Mapped[str] = mapped_column(String(64), ForeignKey("anomalies.anomaly_id"), nullable=False)
    payload_id: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[str] = mapped_column(String(64), nullable=False)
    event_time_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Recommendation(Base):
    __tablename__ = "recommendations"

    recommendation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), ForeignKey("tenants.tenant_id"), nullable=False, index=True)
    incident_id: Mapped[str] = mapped_column(String(64), ForeignKey("incidents.incident_id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    detector_responsible: Mapped[str] = mapped_column(String(128), nullable=False)
    probable_explanation: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_investigation: Mapped[str] = mapped_column(Text, nullable=False)
    expected_benefit: Mapped[str] = mapped_column(Text, nullable=False)
    risk_or_uncertainty: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_strength: Mapped[str] = mapped_column(String(16), nullable=False)
    simulated_remediation_available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    simulated_action_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    rollback_plan: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class DeliveryAck(Base):
    __tablename__ = "delivery_acknowledgments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), ForeignKey("tenants.tenant_id"), nullable=False, index=True)
    collector_id: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    duplicate: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    accepted_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    actor: Mapped[str] = mapped_column(String(128), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    target_id: Mapped[str] = mapped_column(String(128), nullable=False)
    details_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
