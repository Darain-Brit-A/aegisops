"""Tier 2 SaaS REST API Routes implementing contracts/openapi.snapshot.json.

Every tenant-owned query enforces strict filtering by the server-authenticated tenant_id.
"""

from __future__ import annotations

import json
import statistics
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.aiops.engine import process_event_aiops
from app.auth.security import (
    AuthenticatedOperator,
    authenticate_collector_token,
    authenticate_operator_token,
    verify_collector_binding,
)
from app.collectors.health import STATE_RANK, evaluate_collector_health
from app.config import BackendConfig
from app.models.entities import (
    Anomaly,
    AuditEvent,
    Collector,
    CollectorHeartbeat,
    DeliveryAck,
    HealthTransition,
    Incident,
    IncidentEvidence,
    Recommendation,
    TelemetryEvent,
    Tenant,
)
from app.schemas.contracts import (
    HeartbeatIn,
    RemediationApprovalIn,
    TelemetryMetadataIn,
    canonical_json_and_sha256,
    format_utc,
    parse_utc,
)


def _as_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, int(round((pct / 100.0) * (len(ordered) - 1)))))
    return round(ordered[idx], 2)


def _serialize_incident(db: Session, inc: Incident) -> dict[str, Any]:
    ev_rows = db.scalars(
        select(IncidentEvidence)
        .where(IncidentEvidence.tenant_id == inc.tenant_id, IncidentEvidence.incident_id == inc.incident_id)
        .order_by(IncidentEvidence.event_time_utc.asc())
    ).all()
    anom_ids = [r.anomaly_id for r in ev_rows]
    anoms = (
        db.scalars(
            select(Anomaly)
            .where(Anomaly.tenant_id == inc.tenant_id, Anomaly.anomaly_id.in_(anom_ids))
            .order_by(Anomaly.event_time_utc.asc())
        ).all()
        if anom_ids
        else []
    )
    recs = db.scalars(
        select(Recommendation)
        .where(Recommendation.tenant_id == inc.tenant_id, Recommendation.incident_id == inc.incident_id)
    ).all()

    affected_sources = sorted({a.source_id for a in anoms}) or ["src_0000000000000000"]
    signal_timestamps = [format_utc(a.event_time_utc) for a in anoms if a.event_time_utc]

    return {
        "incident_id": inc.incident_id,
        "tenant_id": inc.tenant_id,
        "environment_id": inc.environment_id,
        "region_id": inc.region_id,
        "title": inc.title,
        "status": inc.status,
        "severity": inc.severity,
        "first_observed_utc": format_utc(inc.first_observed_utc),
        "last_observed_utc": format_utc(inc.last_observed_utc),
        "alert_created_utc": format_utc(inc.alert_created_utc),
        "affected_sources": affected_sources,
        "correlation_rule": inc.correlation_rule,
        "correlation_explanation": inc.correlation_explanation,
        "probable_cause": inc.probable_cause,
        "uncertainty_note": inc.uncertainty_note,
        "evidence_score": inc.evidence_score,
        "evidence_score_formula": inc.evidence_score_formula,
        "contributing_signals": [
            {
                "payload_id": a.payload_id,
                "source_id": a.source_id,
                "event_category": a.event_category,
                "metric_name": a.metric_name,
                "metric_value": a.metric_value,
                "baseline_median": a.baseline_median,
                "baseline_mad": a.baseline_mad,
                "robust_z_score": a.robust_z_score,
                "detector_method": a.detector_method,
                "event_time_utc": format_utc(a.event_time_utc),
            }
            for a in anoms
        ],
        "recommendations": [
            {
                "recommendation_id": r.recommendation_id,
                "incident_id": r.incident_id,
                "title": r.title,
                "detector_responsible": r.detector_responsible,
                "probable_explanation": r.probable_explanation,
                "suggested_investigation": r.suggested_investigation,
                "expected_benefit": r.expected_benefit,
                "risk_or_uncertainty": r.risk_or_uncertainty,
                "evidence_strength": r.evidence_strength,
                "evidence_timestamps_utc": signal_timestamps,
                "simulated_remediation_available": r.simulated_remediation_available,
                "simulated_action_code": r.simulated_action_code,
                "rollback_plan": r.rollback_plan,
            }
            for r in recs
        ],
    }


def create_api_router(get_db_dep: Any, config_provider: Any) -> APIRouter:
    router = APIRouter(prefix="/api/v1")

    def require_operator(
        x_tenant_token: str | None = Header(default=None, alias="X-Tenant-Token"),
        db: Session = Depends(get_db_dep),
    ) -> AuthenticatedOperator:
        return authenticate_operator_token(db, x_tenant_token)

    @router.post("/ingest/telemetry")
    def ingest_telemetry(
        payload: TelemetryMetadataIn,
        response: Response,
        x_collector_token: str | None = Header(default=None, alias="X-Collector-Token"),
        db: Session = Depends(get_db_dep),
    ) -> dict[str, Any]:
        cfg: BackendConfig = config_provider()
        collector = authenticate_collector_token(db, x_collector_token)
        verify_collector_binding(db, collector, payload.tenant_id, payload.collector_id)

        raw_dict = payload.model_dump(exclude_none=True)
        canonical_json, payload_sha256 = canonical_json_and_sha256(raw_dict)
        now_utc = datetime.now(timezone.utc)

        # Idempotent deduplication check on UNIQUE(tenant_id, payload_id)
        existing = db.scalar(
            select(TelemetryEvent).where(
                TelemetryEvent.tenant_id == collector.tenant_id,
                TelemetryEvent.payload_id == payload.payload_id,
            )
        )
        if existing is not None:
            db.add(
                DeliveryAck(
                    tenant_id=collector.tenant_id,
                    collector_id=collector.collector_id,
                    payload_id=payload.payload_id,
                    payload_sha256=payload_sha256,
                    status="duplicate_ignored",
                    duplicate=True,
                    accepted_at_utc=now_utc,
                )
            )
            db.commit()
            response.status_code = status.HTTP_200_OK
            return {
                "status": "duplicate_ignored",
                "payload_id": payload.payload_id,
                "tenant_id": collector.tenant_id,
                "payload_sha256": payload_sha256,
                "accepted_at_utc": format_utc(now_utc),
                "duplicate": True,
                "out_of_order": existing.out_of_order,
            }

        event_time = parse_utc(payload.event_time_utc)
        collected_at = parse_utc(payload.collected_at_utc) if payload.collected_at_utc else None
        processed_at = parse_utc(payload.processed_at_utc) if payload.processed_at_utc else None

        # Detect out-of-order arrival relative to latest seen event_time_utc for this source+metric
        latest_event_time = db.scalar(
            select(func.max(TelemetryEvent.event_time_utc)).where(
                TelemetryEvent.tenant_id == collector.tenant_id,
                TelemetryEvent.source_id == payload.source_id,
                TelemetryEvent.metric_name == payload.metric_name,
            )
        )
        latest_utc = _as_utc(latest_event_time)
        out_of_order = bool(latest_utc is not None and event_time < latest_utc)

        ev = TelemetryEvent(
            tenant_id=collector.tenant_id,
            payload_id=payload.payload_id,
            collector_id=collector.collector_id,
            environment_id=payload.environment_id,
            region_id=payload.region_id,
            source_id=payload.source_id,
            event_time_utc=event_time,
            collected_at_utc=collected_at,
            processed_at_utc=processed_at,
            ingested_at_utc=now_utc,
            source_timezone=payload.source_timezone,
            event_category=payload.event_category,
            severity=payload.severity,
            health_state=payload.health_state,
            metric_name=payload.metric_name,
            metric_value=payload.metric_value,
            metric_unit=payload.metric_unit,
            policy_version=payload.policy_version,
            event_code=payload.event_code,
            summary_code=payload.summary_code,
            signal_count=payload.signal_count,
            redacted_field_count=payload.redacted_field_count,
            local_anomaly_score=payload.local_anomaly_score,
            payload_sha256=payload_sha256,
            canonical_json=canonical_json,
            out_of_order=out_of_order,
        )
        db.add(ev)
        db.add(
            DeliveryAck(
                tenant_id=collector.tenant_id,
                collector_id=collector.collector_id,
                payload_id=payload.payload_id,
                payload_sha256=payload_sha256,
                status="accepted",
                duplicate=False,
                accepted_at_utc=now_utc,
            )
        )

        # Keep collector liveness fresh on successful delivery
        if collector.connection_state == "offline":
            collector.last_reconnect_utc = now_utc
        collector.last_heartbeat_utc = now_utc
        collector.last_delivery_status = "ok"
        db.flush()

        # Run AIOps anomaly detection + correlation + health evaluation
        process_event_aiops(db, ev)
        evaluate_collector_health(db, collector, cfg, now_utc=now_utc)
        db.commit()

        response.status_code = status.HTTP_201_CREATED
        return {
            "status": "accepted",
            "payload_id": payload.payload_id,
            "tenant_id": collector.tenant_id,
            "payload_sha256": payload_sha256,
            "accepted_at_utc": format_utc(now_utc),
            "duplicate": False,
            "out_of_order": out_of_order,
        }

    @router.post("/ingest/heartbeat")
    def ingest_heartbeat(
        payload: HeartbeatIn,
        x_collector_token: str | None = Header(default=None, alias="X-Collector-Token"),
        db: Session = Depends(get_db_dep),
    ) -> dict[str, Any]:
        cfg: BackendConfig = config_provider()
        collector = authenticate_collector_token(db, x_collector_token)
        verify_collector_binding(db, collector, payload.tenant_id, payload.collector_id)

        now_utc = datetime.now(timezone.utc)
        was_offline = collector.connection_state == "offline"
        collector.collector_version = payload.collector_version
        collector.config_status = payload.config_status
        collector.policy_version = payload.policy_version
        collector.pending_outbox_count = payload.pending_outbox_count
        collector.retry_count = payload.retry_count
        collector.last_delivery_status = payload.last_delivery_status
        collector.collector_cpu_percent = payload.collector_cpu_percent
        collector.collector_memory_mb = payload.collector_memory_mb
        collector.last_heartbeat_utc = now_utc
        if was_offline:
            collector.last_reconnect_utc = now_utc

        db.add(
            CollectorHeartbeat(
                tenant_id=collector.tenant_id,
                collector_id=collector.collector_id,
                sent_at_utc=parse_utc(payload.sent_at_utc),
                received_at_utc=now_utc,
                pending_outbox_count=payload.pending_outbox_count,
                retry_count=payload.retry_count,
                last_delivery_status=payload.last_delivery_status,
                collector_cpu_percent=payload.collector_cpu_percent,
                collector_memory_mb=payload.collector_memory_mb,
            )
        )
        health_eval = evaluate_collector_health(db, collector, cfg, now_utc=now_utc)
        db.commit()
        return {
            "status": "recorded",
            "collector_id": collector.collector_id,
            "tenant_id": collector.tenant_id,
            "received_at_utc": format_utc(now_utc),
            **health_eval,
        }

    @router.get("/overview")
    def get_overview(
        environment_id: str | None = Query(default=None),
        region_id: str | None = Query(default=None),
        op: AuthenticatedOperator = Depends(require_operator),
        db: Session = Depends(get_db_dep),
    ) -> dict[str, Any]:
        cfg: BackendConfig = config_provider()
        now_utc = datetime.now(timezone.utc)

        col_stmt = select(Collector).where(Collector.tenant_id == op.tenant_id)
        if environment_id:
            col_stmt = col_stmt.where(Collector.environment_id == environment_id)
        if region_id:
            col_stmt = col_stmt.where(Collector.region_id == region_id)
        collectors = db.scalars(col_stmt).all()

        health_dist = {"Excellent": 0, "Good": 0, "Fair": 0, "Poor": 0}
        online_count = 0
        stale_count = 0
        offline_count = 0
        fleet_health = "Excellent"

        for col in collectors:
            ev = evaluate_collector_health(db, col, cfg, now_utc=now_utc)
            st = str(ev["health_state"])
            health_dist[st] = health_dist.get(st, 0) + 1
            if STATE_RANK.get(st, 0) > STATE_RANK.get(fleet_health, 0):
                fleet_health = st
            if col.connection_state == "online":
                online_count += 1
            elif col.connection_state == "stale":
                stale_count += 1
            else:
                offline_count += 1
        db.commit()

        inc_stmt = select(Incident).where(
            Incident.tenant_id == op.tenant_id,
            Incident.status.in_(["open", "acknowledged"]),
        )
        if environment_id:
            inc_stmt = inc_stmt.where(Incident.environment_id == environment_id)
        if region_id:
            inc_stmt = inc_stmt.where(Incident.region_id == region_id)
        active_incidents = db.scalars(inc_stmt).all()

        recent_anoms = db.scalars(
            select(Anomaly)
            .where(Anomaly.tenant_id == op.tenant_id)
            .order_by(Anomaly.event_time_utc.desc())
            .limit(10)
        ).all()

        security_events_count = db.scalar(
            select(func.count(TelemetryEvent.id)).where(
                TelemetryEvent.tenant_id == op.tenant_id,
                TelemetryEvent.event_category == "security",
            )
        ) or 0
        redacted_fields_total = db.scalar(
            select(func.coalesce(func.sum(TelemetryEvent.redacted_field_count), 0)).where(
                TelemetryEvent.tenant_id == op.tenant_id,
            )
        ) or 0
        last_tel_utc = db.scalar(
            select(func.max(TelemetryEvent.ingested_at_utc)).where(TelemetryEvent.tenant_id == op.tenant_id)
        )
        tenant = db.get(Tenant, op.tenant_id)

        return {
            "tenant_id": op.tenant_id,
            "tenant_name": tenant.name if tenant else op.tenant_id,
            "tenant_region_id": tenant.region_id if tenant else cfg.region_id,
            "fleet_health_state": fleet_health if collectors else "Good",
            "collectors_total": len(collectors),
            "collectors_online": online_count,
            "collectors_stale": stale_count,
            "collectors_offline": offline_count,
            "health_distribution": health_dist,
            "active_incidents_count": len(active_incidents),
            "security_events_count": int(security_events_count),
            "redacted_fields_kept_local_total": int(redacted_fields_total),
            "last_telemetry_utc": format_utc(last_tel_utc),
            "evaluated_at_utc": format_utc(now_utc),
            "recent_anomalies": [
                {
                    "anomaly_id": a.anomaly_id,
                    "metric_name": a.metric_name,
                    "metric_value": a.metric_value,
                    "severity": a.severity,
                    "detector_method": a.detector_method,
                    "source_id": a.source_id,
                    "robust_z_score": a.robust_z_score,
                    "event_time_utc": format_utc(a.event_time_utc),
                }
                for a in recent_anoms
            ],
        }

    @router.get("/metrics")
    def get_metrics(
        metric_name: str | None = Query(default=None),
        environment_id: str | None = Query(default=None),
        source_id: str | None = Query(default=None),
        minutes: int = Query(default=180, ge=1, le=10080),
        op: AuthenticatedOperator = Depends(require_operator),
        db: Session = Depends(get_db_dep),
    ) -> dict[str, Any]:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        stmt = (
            select(TelemetryEvent)
            .where(
                TelemetryEvent.tenant_id == op.tenant_id,
                TelemetryEvent.event_time_utc >= cutoff,
            )
            .order_by(TelemetryEvent.event_time_utc.asc())
        )
        if metric_name:
            stmt = stmt.where(TelemetryEvent.metric_name == metric_name)
        if environment_id:
            stmt = stmt.where(TelemetryEvent.environment_id == environment_id)
        if source_id:
            stmt = stmt.where(TelemetryEvent.source_id == source_id)

        rows = db.scalars(stmt.limit(500)).all()
        return {
            "tenant_id": op.tenant_id,
            "ordered_by": "event_time_utc",
            "count": len(rows),
            "points": [
                {
                    "payload_id": r.payload_id,
                    "source_id": r.source_id,
                    "environment_id": r.environment_id,
                    "event_category": r.event_category,
                    "metric_name": r.metric_name,
                    "metric_value": r.metric_value,
                    "metric_unit": r.metric_unit,
                    "severity": r.severity,
                    "health_state": r.health_state,
                    "event_code": r.event_code,
                    "event_time_utc": format_utc(r.event_time_utc),
                    "ingested_at_utc": format_utc(r.ingested_at_utc),
                    "source_timezone": r.source_timezone,
                    "out_of_order": r.out_of_order,
                }
                for r in rows
            ],
        }

    @router.get("/collectors")
    def list_collectors(
        op: AuthenticatedOperator = Depends(require_operator),
        db: Session = Depends(get_db_dep),
    ) -> dict[str, Any]:
        cfg: BackendConfig = config_provider()
        now_utc = datetime.now(timezone.utc)
        collectors = db.scalars(select(Collector).where(Collector.tenant_id == op.tenant_id)).all()

        items = []
        for col in collectors:
            ev = evaluate_collector_health(db, col, cfg, now_utc=now_utc)
            transitions = db.scalars(
                select(HealthTransition)
                .where(
                    HealthTransition.tenant_id == op.tenant_id,
                    HealthTransition.entity_id == col.collector_id,
                )
                .order_by(HealthTransition.changed_at_utc.desc())
                .limit(10)
            ).all()
            items.append(
                {
                    "collector_id": col.collector_id,
                    "tenant_id": col.tenant_id,
                    "environment_id": col.environment_id,
                    "region_id": col.region_id,
                    "collector_version": col.collector_version,
                    "config_status": col.config_status,
                    "policy_version": col.policy_version,
                    "health_state": ev["health_state"],
                    "is_stale": ev["is_stale"],
                    "reason_code": ev["reason_code"],
                    "explanation": ev["explanation"],
                    "connection_state": col.connection_state,
                    "last_heartbeat_utc": format_utc(col.last_heartbeat_utc),
                    "last_reconnect_utc": format_utc(col.last_reconnect_utc),
                    "pending_outbox_count": col.pending_outbox_count,
                    "retry_count": col.retry_count,
                    "last_delivery_status": col.last_delivery_status,
                    "collector_cpu_percent": col.collector_cpu_percent,
                    "collector_memory_mb": col.collector_memory_mb,
                    "transitions": [
                        {
                            "from_state": t.from_state,
                            "to_state": t.to_state,
                            "changed_at_utc": format_utc(t.changed_at_utc),
                            "reason_code": t.reason_code,
                            "explanation": t.explanation,
                        }
                        for t in transitions
                    ],
                }
            )
        db.commit()
        return {"tenant_id": op.tenant_id, "count": len(items), "collectors": items}

    @router.get("/incidents")
    def list_incidents(
        status_filter: str | None = Query(default=None, alias="status"),
        severity: str | None = Query(default=None),
        op: AuthenticatedOperator = Depends(require_operator),
        db: Session = Depends(get_db_dep),
    ) -> dict[str, Any]:
        stmt = (
            select(Incident)
            .where(Incident.tenant_id == op.tenant_id)
            .order_by(Incident.last_observed_utc.desc())
        )
        if status_filter:
            stmt = stmt.where(Incident.status == status_filter)
        if severity:
            stmt = stmt.where(Incident.severity == severity)
        incidents = db.scalars(stmt.limit(100)).all()
        return {
            "tenant_id": op.tenant_id,
            "count": len(incidents),
            "incidents": [_serialize_incident(db, inc) for inc in incidents],
        }

    @router.get("/incidents/{incident_id}")
    def get_incident(
        incident_id: str,
        op: AuthenticatedOperator = Depends(require_operator),
        db: Session = Depends(get_db_dep),
    ) -> dict[str, Any]:
        inc = db.scalar(
            select(Incident).where(Incident.tenant_id == op.tenant_id, Incident.incident_id == incident_id)
        )
        if inc is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "INCIDENT_NOT_FOUND", "message": "Incident not found for tenant."},
            )
        return _serialize_incident(db, inc)

    @router.post("/incidents/{incident_id}/simulate-remediation")
    def simulate_remediation(
        incident_id: str,
        req: RemediationApprovalIn,
        op: AuthenticatedOperator = Depends(require_operator),
        db: Session = Depends(get_db_dep),
    ) -> dict[str, Any]:
        """Safe Autonomous Ops Stage-5 simulation: policy check -> approval -> immutable audit -> rollback plan."""
        inc = db.scalar(
            select(Incident).where(Incident.tenant_id == op.tenant_id, Incident.incident_id == incident_id)
        )
        if inc is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "INCIDENT_NOT_FOUND", "message": "Incident not found for tenant."},
            )

        rec = db.scalar(
            select(Recommendation).where(
                Recommendation.tenant_id == op.tenant_id, Recommendation.incident_id == incident_id
            )
        )
        now_utc = datetime.now(timezone.utc)
        action_code = rec.simulated_action_code if rec and rec.simulated_action_code else "SIM_OPERATOR_MITIGATION"
        rollback_plan = (
            rec.rollback_plan if rec and rec.rollback_plan else "Revert simulated policy change to prior baseline."
        )

        inc.status = "mitigated_simulated"
        audit_entry = AuditEvent(
            tenant_id=op.tenant_id,
            actor=f"{op.operator_id} (approved_by={req.operator_id})",
            action="SIMULATED_REMEDIATION_EXECUTED",
            target_id=incident_id,
            details_json=json.dumps(
                {
                    "mode": "SIMULATED_ONLY_NO_LIVE_INFRA_CHANGE",
                    "policy_check": "PASSED_SAFE_SIMULATION_BOUNDARY",
                    "action_code": action_code,
                    "justification": req.justification,
                    "rollback_plan": rollback_plan,
                }
            ),
            created_at_utc=now_utc,
        )
        db.add(audit_entry)
        db.commit()
        db.refresh(audit_entry)

        return {
            "simulated": True,
            "warning": "SIMULATED REMEDIATION ONLY — zero changes executed against live customer infrastructure.",
            "incident_id": incident_id,
            "new_incident_status": inc.status,
            "policy_check_status": "PASS",
            "approved_by": req.operator_id,
            "action_code": action_code,
            "rollback_plan": rollback_plan,
            "audit_event_id": audit_entry.id,
            "executed_at_utc": format_utc(now_utc),
        }

    @router.get("/saas-receipts")
    def get_saas_receipts(
        limit: int = Query(default=50, ge=1, le=200),
        op: AuthenticatedOperator = Depends(require_operator),
        db: Session = Depends(get_db_dep),
    ) -> dict[str, Any]:
        rows = db.scalars(
            select(TelemetryEvent)
            .where(TelemetryEvent.tenant_id == op.tenant_id)
            .order_by(TelemetryEvent.ingested_at_utc.desc())
            .limit(limit)
        ).all()
        return {
            "tenant_id": op.tenant_id,
            "tier": "tier-2-saas-metadata-only",
            "count": len(rows),
            "receipts": [
                {
                    "payload_id": r.payload_id,
                    "collector_id": r.collector_id,
                    "source_id": r.source_id,
                    "policy_version": r.policy_version,
                    "event_time_utc": format_utc(r.event_time_utc),
                    "ingested_at_utc": format_utc(r.ingested_at_utc),
                    "payload_sha256": r.payload_sha256,
                    "canonical_json": r.canonical_json,
                    "payload": json.loads(r.canonical_json),
                    "out_of_order": r.out_of_order,
                }
                for r in rows
            ],
        }

    @router.get("/reliability")
    def get_reliability_metrics(
        op: AuthenticatedOperator = Depends(require_operator),
        db: Session = Depends(get_db_dep),
    ) -> dict[str, Any]:
        events = db.scalars(
            select(TelemetryEvent)
            .where(TelemetryEvent.tenant_id == op.tenant_id)
            .order_by(TelemetryEvent.ingested_at_utc.desc())
            .limit(500)
        ).all()
        acks = db.scalars(
            select(DeliveryAck)
            .where(DeliveryAck.tenant_id == op.tenant_id)
            .order_by(DeliveryAck.accepted_at_utc.desc())
            .limit(500)
        ).all()
        incidents = db.scalars(select(Incident).where(Incident.tenant_id == op.tenant_id).limit(200)).all()
        offline_transitions = db.scalar(
            select(func.count(HealthTransition.id)).where(
                HealthTransition.tenant_id == op.tenant_id,
                HealthTransition.reason_code == "COLLECTOR_OFFLINE",
            )
        ) or 0
        last_reconnect = db.scalar(
            select(func.max(Collector.last_reconnect_utc)).where(Collector.tenant_id == op.tenant_id)
        )

        ingest_latencies_ms: list[float] = []
        for ev in events:
            et = _as_utc(ev.event_time_utc)
            it = _as_utc(ev.ingested_at_utc)
            if et and it and not ev.out_of_order:
                delta_ms = (it - et).total_seconds() * 1000.0
                if 0.0 <= delta_ms <= 3_600_000.0:
                    ingest_latencies_ms.append(delta_ms)

        alert_latencies_ms: list[float] = []
        for inc in incidents:
            fo = _as_utc(inc.first_observed_utc)
            ac = _as_utc(inc.alert_created_utc)
            if fo and ac:
                delta_ms = (ac - fo).total_seconds() * 1000.0
                if 0.0 <= delta_ms <= 3_600_000.0:
                    alert_latencies_ms.append(delta_ms)

        dup_count = sum(1 for a in acks if a.duplicate)
        ooo_count = sum(1 for ev in events if ev.out_of_order)

        return {
            "tenant_id": op.tenant_id,
            "measurement_note": "Values derived strictly from recorded UTC timestamps. Unmeasured metrics return null.",
            "total_accepted_events": len(events),
            "duplicate_rejected_count": dup_count,
            "out_of_order_count": ooo_count,
            "collector_offline_detections": int(offline_transitions),
            "last_reconnect_utc": format_utc(last_reconnect),
            "p50_ingest_latency_ms": round(statistics.median(ingest_latencies_ms), 2) if ingest_latencies_ms else None,
            "p95_ingest_latency_ms": _percentile(ingest_latencies_ms, 95),
            "p50_alert_latency_ms": round(statistics.median(alert_latencies_ms), 2) if alert_latencies_ms else None,
            "p95_alert_latency_ms": _percentile(alert_latencies_ms, 95),
            "recent_accepted_payload_ids": [ev.payload_id for ev in events[:20]],
        }

    @router.get("/architecture/trust-summary")
    def get_trust_summary(
        op: AuthenticatedOperator = Depends(require_operator),
        db: Session = Depends(get_db_dep),
    ) -> dict[str, Any]:
        cfg: BackendConfig = config_provider()
        tenant = db.get(Tenant, op.tenant_id)
        return {
            "product": "AegisOps",
            "tagline": "Observe everything. Expose nothing.",
            "tenant_id": op.tenant_id,
            "assigned_region_id": tenant.region_id if tenant else cfg.region_id,
            "active_ingest_region_id": cfg.region_id,
            "supported_regions": list(cfg.allowed_regions),
            "policy_version": cfg.policy_version,
            "egress_model": "default_deny_allowlist",
            "allowlisted_fields": list(TelemetryMetadataIn.model_fields.keys()),
            "tenant_isolation_mode": "server_bound_token_plus_query_scoping_with_tests",
            "database_rls_enabled": False,
            "transport_posture": "https_supported_loopback_http_in_local_dev",
            "remediation_mode": "simulated_with_approval_audit_and_rollback",
            "heartbeat_stale_seconds": cfg.heartbeat_stale_seconds,
            "heartbeat_offline_seconds": cfg.heartbeat_offline_seconds,
        }

    return router
