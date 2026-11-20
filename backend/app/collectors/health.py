"""Four-State Health Evaluation Engine (Excellent, Good, Fair, Poor) with stale-data downgrading."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import BackendConfig
from app.models.entities import Collector, HealthTransition, TelemetryEvent

STATE_RANK = {"Excellent": 0, "Good": 1, "Fair": 2, "Poor": 3}


def _as_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def record_transition_if_changed(
    db: Session,
    *,
    tenant_id: str,
    entity_type: str,
    entity_id: str,
    previous_state: str | None,
    new_state: str,
    reason_code: str,
    explanation: str,
    now_utc: datetime,
) -> bool:
    if previous_state == new_state:
        return False
    db.add(
        HealthTransition(
            tenant_id=tenant_id,
            entity_type=entity_type,
            entity_id=entity_id,
            from_state=previous_state,
            to_state=new_state,
            reason_code=reason_code,
            explanation=explanation,
            changed_at_utc=now_utc,
        )
    )
    return True


def evaluate_collector_health(
    db: Session,
    collector: Collector,
    config: BackendConfig,
    now_utc: datetime | None = None,
) -> dict[str, object]:
    """Evaluate collector 4-state health with explicit stale/offline downgrade rules.

    A stale collector MUST NEVER remain Excellent even if its last reported metrics were healthy.
    """
    now = _as_utc(now_utc) or datetime.now(timezone.utc)
    last_hb = _as_utc(collector.last_heartbeat_utc)
    prev_state = collector.health_state

    is_stale = False
    reason_code = "ALL_NOMINAL"
    explanation = "Collector heartbeat current and recent telemetry within nominal thresholds."
    new_state = "Excellent"
    connection_state = collector.connection_state

    if last_hb is None:
        is_stale = True
        new_state = "Good"
        connection_state = "awaiting_heartbeat"
        reason_code = "NO_TELEMETRY_YET"
        explanation = "Collector registered but no heartbeat received yet."
    else:
        age_seconds = (now - last_hb).total_seconds()
        if age_seconds > config.heartbeat_offline_seconds:
            is_stale = True
            new_state = "Poor"
            connection_state = "offline"
            reason_code = "COLLECTOR_OFFLINE"
            explanation = (
                f"Collector heartbeat age ({int(age_seconds)}s) exceeded offline threshold "
                f"({config.heartbeat_offline_seconds}s). Downgraded to Poor."
            )
        elif age_seconds > config.heartbeat_stale_seconds:
            is_stale = True
            new_state = "Fair"
            connection_state = "stale"
            reason_code = "HEARTBEAT_STALE"
            explanation = (
                f"Collector heartbeat age ({int(age_seconds)}s) exceeded stale threshold "
                f"({config.heartbeat_stale_seconds}s). Downgraded from Excellent to Fair."
            )
        else:
            connection_state = "online"
            # Incorporate latest telemetry health state for this collector
            latest_events = db.scalars(
                select(TelemetryEvent)
                .where(
                    TelemetryEvent.tenant_id == collector.tenant_id,
                    TelemetryEvent.collector_id == collector.collector_id,
                )
                .order_by(TelemetryEvent.event_time_utc.desc())
                .limit(5)
            ).all()

            worst_state = "Excellent"
            worst_ev: TelemetryEvent | None = None
            for ev in latest_events:
                if STATE_RANK.get(ev.health_state, 0) > STATE_RANK.get(worst_state, 0):
                    worst_state = ev.health_state
                    worst_ev = ev

            new_state = worst_state
            if worst_ev and worst_state == "Poor":
                reason_code = "CRITICAL_DEGRADATION_OR_SECURITY"
                explanation = (
                    f"Critical signal {worst_ev.metric_name}={worst_ev.metric_value} "
                    f"({worst_ev.event_code}) on {worst_ev.source_id}."
                )
            elif worst_ev and worst_state == "Fair":
                reason_code = "ELEVATED_RESOURCE_OR_NETWORK"
                explanation = (
                    f"Elevated signal {worst_ev.metric_name}={worst_ev.metric_value} "
                    f"({worst_ev.event_code}) on {worst_ev.source_id}."
                )
            elif worst_ev and worst_state == "Good":
                reason_code = "MINOR_BASELINE_DRIFT"
                explanation = f"Minor deviation on {worst_ev.metric_name}={worst_ev.metric_value}."

    collector.health_state = new_state
    collector.connection_state = connection_state
    record_transition_if_changed(
        db,
        tenant_id=collector.tenant_id,
        entity_type="collector",
        entity_id=collector.collector_id,
        previous_state=prev_state,
        new_state=new_state,
        reason_code=reason_code,
        explanation=explanation,
        now_utc=now,
    )

    return {
        "health_state": new_state,
        "previous_state": prev_state,
        "connection_state": connection_state,
        "is_stale": is_stale,
        "reason_code": reason_code,
        "explanation": explanation,
    }
