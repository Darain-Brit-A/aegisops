"""Comprehensive tests for Tier 2 SaaS Backend: auth, tenant isolation, idempotency, health, MAD, correlation."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
from fastapi import HTTPException, Response
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from app.aiops.engine import evaluate_rolling_mad_baseline
from app.api.routes import create_api_router
from app.collectors.health import evaluate_collector_health
from app.config import BackendConfig
from app.models.database import DatabaseManager
from app.models.entities import Collector, TelemetryEvent
from app.schemas.contracts import HeartbeatIn, RemediationApprovalIn, TelemetryMetadataIn

REPO_ROOT = Path(__file__).resolve().parents[2]
INCIDENT_SCHEMA = json.loads((REPO_ROOT / "contracts" / "incident.schema.json").read_text(encoding="utf-8"))
INCIDENT_VALIDATOR = Draft202012Validator(INCIDENT_SCHEMA)


def make_test_env() -> tuple[BackendConfig, DatabaseManager, dict[str, Any]]:
    cfg = BackendConfig(
        database_url="sqlite:///:memory:",
        region_id="ap-south-1",
        allowed_regions=("ap-south-1", "eu-central-1", "us-east-1"),
        policy_version="1",
        heartbeat_stale_seconds=45,
        heartbeat_offline_seconds=60,
        cors_origins=("http://localhost:5173",),
        tenant_a_id="tenant-acme-prod",
        tenant_a_collector_id="col-acme-blr-01",
        tenant_a_collector_token="dev-col-token-acme-local-placeholder",
        tenant_a_operator_token="dev-op-token-acme-local-placeholder",
        tenant_b_id="tenant-globex-prod",
        tenant_b_collector_id="col-globex-fra-01",
        tenant_b_collector_token="dev-col-token-globex-local-placeholder",
        tenant_b_operator_token="dev-op-token-globex-local-placeholder",
    )
    dbm = DatabaseManager(cfg)
    dbm.init_db_and_seed()
    router = create_api_router(dbm.get_session, lambda: cfg)
    endpoints = {getattr(r, "path"): getattr(r, "endpoint") for r in router.routes}
    return cfg, dbm, endpoints


def make_payload(
    *,
    tenant_id: str = "tenant-acme-prod",
    collector_id: str = "col-acme-blr-01",
    environment_id: str = "env-blr-dc1",
    source_id: str = "src_a1b2c3d4e5f60718293a",
    event_category: str = "infrastructure",
    metric_name: str = "cpu_usage_percent",
    metric_value: float = 42.0,
    metric_unit: str = "percent",
    severity: str = "info",
    health_state: str = "Excellent",
    event_code: str = "METRIC_NORMAL",
    summary_code: str = "BASELINE_NOMINAL",
    event_time_utc: str | None = None,
    payload_id: str | None = None,
    source_timezone: str = "Asia/Kolkata",
) -> TelemetryMetadataIn:
    return TelemetryMetadataIn(
        schema_version="1.0",
        payload_id=payload_id or str(uuid.uuid4()),
        collector_id=collector_id,
        tenant_id=tenant_id,
        environment_id=environment_id,
        region_id="ap-south-1",
        source_id=source_id,
        event_time_utc=event_time_utc or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        source_timezone=source_timezone,
        event_category=event_category,  # type: ignore[arg-type]
        severity=severity,  # type: ignore[arg-type]
        health_state=health_state,  # type: ignore[arg-type]
        metric_name=metric_name,  # type: ignore[arg-type]
        metric_value=metric_value,
        metric_unit=metric_unit,  # type: ignore[arg-type]
        policy_version="1",
        event_code=event_code,  # type: ignore[arg-type]
        summary_code=summary_code,  # type: ignore[arg-type]
    )


def test_strict_schema_rejects_unapproved_raw_fields() -> None:
    raw = make_payload().model_dump()
    raw["raw_log"] = "secret=AEGIS_DEMO_SECRET_TOKEN_9F2A"
    with pytest.raises(ValidationError):
        TelemetryMetadataIn(**raw)


def test_server_bound_tenant_spoofing_rejected_403() -> None:
    cfg, dbm, endpoints = make_test_env()
    ingest = endpoints["/api/v1/ingest/telemetry"]
    spoof = make_payload(tenant_id=cfg.tenant_b_id, collector_id=cfg.tenant_a_collector_id)

    with dbm.session_factory() as db:
        with pytest.raises(HTTPException) as exc:
            ingest(payload=spoof, response=Response(), x_collector_token=cfg.tenant_a_collector_token, db=db)
        assert exc.value.status_code == 403


def test_idempotent_duplicate_ingestion_and_tenant_isolation() -> None:
    cfg, dbm, endpoints = make_test_env()
    ingest = endpoints["/api/v1/ingest/telemetry"]
    receipts_ep = endpoints["/api/v1/saas-receipts"]
    reliability_ep = endpoints["/api/v1/reliability"]
    from app.auth.security import authenticate_operator_token

    p = make_payload(metric_value=55.0)
    with dbm.session_factory() as db:
        r1_resp = Response()
        ack1 = ingest(payload=p, response=r1_resp, x_collector_token=cfg.tenant_a_collector_token, db=db)
        assert r1_resp.status_code == 201
        assert ack1["duplicate"] is False

        r2_resp = Response()
        ack2 = ingest(payload=p, response=r2_resp, x_collector_token=cfg.tenant_a_collector_token, db=db)
        assert r2_resp.status_code == 200
        assert ack2["duplicate"] is True
        assert ack2["status"] == "duplicate_ignored"

        # Single stored telemetry row despite duplicate retry
        count = db.query(TelemetryEvent).filter(TelemetryEvent.payload_id == p.payload_id).count()
        assert count == 1

        # Tenant A sees its receipt; Tenant B CANNOT see Tenant A's receipt
        op_a = authenticate_operator_token(db, cfg.tenant_a_operator_token)
        op_b = authenticate_operator_token(db, cfg.tenant_b_operator_token)

        res_a = receipts_ep(limit=50, op=op_a, db=db)
        res_b = receipts_ep(limit=50, op=op_b, db=db)
        assert any(r["payload_id"] == p.payload_id for r in res_a["receipts"])
        assert not any(r["payload_id"] == p.payload_id for r in res_b["receipts"])

        rel_a = reliability_ep(op=op_a, db=db)
        assert rel_a["total_accepted_events"] == 1
        assert rel_a["duplicate_rejected_count"] == 1


def test_out_of_order_multi_timezone_event_time_ordering() -> None:
    cfg, dbm, endpoints = make_test_env()
    ingest = endpoints["/api/v1/ingest/telemetry"]
    metrics_ep = endpoints["/api/v1/metrics"]
    from app.auth.security import authenticate_operator_token

    now = datetime.now(timezone.utc)
    t_later = (now - timedelta(seconds=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    t_earlier = (now - timedelta(seconds=120)).strftime("%Y-%m-%dT%H:%M:%SZ")

    with dbm.session_factory() as db:
        ack_later = ingest(
            payload=make_payload(metric_value=40.0, event_time_utc=t_later, source_timezone="Asia/Kolkata"),
            response=Response(),
            x_collector_token=cfg.tenant_a_collector_token,
            db=db,
        )
        ack_earlier = ingest(
            payload=make_payload(metric_value=35.0, event_time_utc=t_earlier, source_timezone="America/New_York"),
            response=Response(),
            x_collector_token=cfg.tenant_a_collector_token,
            db=db,
        )
        assert ack_later["out_of_order"] is False
        assert ack_earlier["out_of_order"] is True

        op_a = authenticate_operator_token(db, cfg.tenant_a_operator_token)
        series = metrics_ep(metric_name="cpu_usage_percent", environment_id=None, source_id=None, minutes=60, op=op_a, db=db)
        pts = series["points"]
        assert len(pts) == 2
        assert pts[0]["metric_value"] == 35.0  # Ordered strictly by event_time_utc, NOT arrival time
        assert pts[1]["metric_value"] == 40.0


def test_stale_and_offline_heartbeat_downgrades_health_state() -> None:
    cfg, dbm, endpoints = make_test_env()
    hb_ep = endpoints["/api/v1/ingest/heartbeat"]

    now = datetime.now(timezone.utc)
    hb = HeartbeatIn(
        schema_version="1.0",
        collector_id=cfg.tenant_a_collector_id,
        tenant_id=cfg.tenant_a_id,
        environment_id="env-blr-dc1",
        region_id="ap-south-1",
        collector_version="0.1.0",
        config_status="valid",
        policy_version="1",
        sent_at_utc=now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        pending_outbox_count=0,
        retry_count=0,
        last_delivery_status="ok",
        collector_cpu_percent=2.5,
        collector_memory_mb=48.0,
    )
    with dbm.session_factory() as db:
        res = hb_ep(payload=hb, x_collector_token=cfg.tenant_a_collector_token, db=db)
        assert res["health_state"] == "Excellent"
        assert res["is_stale"] is False

        col = db.get(Collector, cfg.tenant_a_collector_id)
        assert col is not None

        # 50s later -> Stale (Fair), NOT Excellent
        ev_stale = evaluate_collector_health(db, col, cfg, now_utc=now + timedelta(seconds=50))
        assert ev_stale["health_state"] == "Fair"
        assert ev_stale["is_stale"] is True
        assert ev_stale["reason_code"] == "HEARTBEAT_STALE"

        # 70s later -> Offline (Poor)
        ev_offline = evaluate_collector_health(db, col, cfg, now_utc=now + timedelta(seconds=70))
        assert ev_offline["health_state"] == "Poor"
        assert ev_offline["reason_code"] == "COLLECTOR_OFFLINE"


def test_mad_baseline_cold_start_and_zero_mad_safety() -> None:
    cold = evaluate_rolling_mad_baseline([30.0, 31.0, 32.0], 95.0)
    assert cold.status == "insufficient_history"
    assert cold.is_anomaly is False

    zero_mad_normal = evaluate_rolling_mad_baseline([40.0] * 10, 42.0, min_zero_mad_delta=20.0)
    assert zero_mad_normal.mad == 0.0
    assert zero_mad_normal.is_anomaly is False

    zero_mad_spike = evaluate_rolling_mad_baseline([40.0] * 10, 88.0, min_zero_mad_delta=20.0)
    assert zero_mad_spike.mad == 0.0
    assert zero_mad_spike.is_anomaly is True

    varied = evaluate_rolling_mad_baseline([30.0, 32.0, 31.0, 29.0, 33.0, 30.5, 31.5, 32.5, 30.0, 31.0], 92.0)
    assert varied.status == "learned"
    assert varied.is_anomaly is True
    assert varied.robust_z is not None and varied.robust_z > 5.0


def test_incident_correlation_recommendations_and_simulated_remediation() -> None:
    cfg, dbm, endpoints = make_test_env()
    ingest = endpoints["/api/v1/ingest/telemetry"]
    incidents_ep = endpoints["/api/v1/incidents"]
    sim_ep = endpoints["/api/v1/incidents/{incident_id}/simulate-remediation"]
    from app.auth.security import authenticate_operator_token

    now = datetime.now(timezone.utc)
    with dbm.session_factory() as db:
        # 1. Feed 9 nominal CPU baseline points
        for i in range(9):
            ts = (now - timedelta(seconds=200 - i * 15)).strftime("%Y-%m-%dT%H:%M:%SZ")
            ingest(
                payload=make_payload(metric_name="cpu_usage_percent", metric_value=31.0 + (i % 3), event_time_utc=ts),
                response=Response(),
                x_collector_token=cfg.tenant_a_collector_token,
                db=db,
            )

        # 2. Trigger correlated CPU + Memory + Latency spikes in same environment within 30s
        ingest(
            payload=make_payload(
                metric_name="cpu_usage_percent",
                metric_value=96.5,
                severity="critical",
                health_state="Poor",
                event_code="CPU_THRESHOLD_BREACH",
                summary_code="SERVICE_IMPACT_CRITICAL",
                event_time_utc=(now - timedelta(seconds=20)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            ),
            response=Response(),
            x_collector_token=cfg.tenant_a_collector_token,
            db=db,
        )
        ingest(
            payload=make_payload(
                metric_name="memory_usage_percent",
                metric_value=92.0,
                severity="high",
                health_state="Fair",
                event_code="MEMORY_ANOMALY",
                summary_code="RESOURCE_DEVIATION",
                event_time_utc=(now - timedelta(seconds=10)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            ),
            response=Response(),
            x_collector_token=cfg.tenant_a_collector_token,
            db=db,
        )
        ingest(
            payload=make_payload(
                event_category="network",
                metric_name="network_latency_ms",
                metric_value=260.0,
                metric_unit="ms",
                severity="high",
                health_state="Fair",
                event_code="NETWORK_LATENCY_SPIKE",
                summary_code="NETWORK_DEGRADATION",
                event_time_utc=now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            ),
            response=Response(),
            x_collector_token=cfg.tenant_a_collector_token,
            db=db,
        )

        # 3. Unrelated security auth burst in same window must NOT merge into infra/network incident
        ingest(
            payload=make_payload(
                event_category="security",
                metric_name="failed_auth_attempts_count",
                metric_value=25,
                metric_unit="count",
                severity="critical",
                health_state="Poor",
                event_code="AUTH_FAILURE_BURST",
                summary_code="SECURITY_RISK_ELEVATED",
                event_time_utc=now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            ),
            response=Response(),
            x_collector_token=cfg.tenant_a_collector_token,
            db=db,
        )

        op_a = authenticate_operator_token(db, cfg.tenant_a_operator_token)
        inc_list = incidents_ep(status_filter=None, severity=None, op=op_a, db=db)
        assert inc_list["count"] == 2  # 1 correlated infra/network incident + 1 separate security incident

        infra_inc = next(i for i in inc_list["incidents"] if i["correlation_rule"] == "ENV_RESOURCE_NETWORK_CASCADE")
        INCIDENT_VALIDATOR.validate(infra_inc)
        assert len(infra_inc["contributing_signals"]) == 3
        assert infra_inc["evidence_score"] >= 80.0
        assert len(infra_inc["recommendations"]) >= 1

        # 4. Safe simulated remediation with policy check, approval, audit & rollback
        sim_res = sim_ep(
            incident_id=infra_inc["incident_id"],
            req=RemediationApprovalIn(
                operator_id="sre-mishael",
                justification="Verified correlated saturation in dashboard; approve safe simulation.",
                confirm_simulation=True,
            ),
            op=op_a,
            db=db,
        )
        assert sim_res["simulated"] is True
        assert sim_res["policy_check_status"] == "PASS"
        assert sim_res["new_incident_status"] == "mitigated_simulated"
        assert sim_res["rollback_plan"]
        assert sim_res["audit_event_id"] is not None
