"""AegisOps AIOps Engine: Dual Anomaly Detection, Deterministic Correlation, and Explainable Recommendations.

Method A: Configurable static thresholds.
Method B: Rolling Median / MAD robust z-score (MIN_SAMPLES=8 cold-start protection + explicit MAD==0 handling).
Correlation: Deterministic grouping by (tenant_id, environment_id, operational domain, 5-minute window).
Recommendations: Deterministic evidence_score with explicit formula — never fabricated ML probabilities.
"""

from __future__ import annotations

import statistics
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import Anomaly, Incident, IncidentEvidence, Recommendation, TelemetryEvent

MIN_BASELINE_SAMPLES = 8
MAD_ROBUST_Z_THRESHOLD = 3.5
CORRELATION_WINDOW_MINUTES = 5

# Static thresholds: metric_name -> (warning_threshold, critical_threshold, direction, min_zero_mad_delta)
STATIC_THRESHOLDS: dict[str, tuple[float, float, str, float]] = {
    "cpu_usage_percent": (80.0, 95.0, "high", 20.0),
    "memory_usage_percent": (80.0, 95.0, "high", 15.0),
    "disk_usage_percent": (80.0, 92.0, "high", 10.0),
    "network_latency_ms": (150.0, 300.0, "high", 50.0),
    "network_packet_loss_percent": (2.0, 10.0, "high", 2.0),
    "service_availability_percent": (99.5, 95.0, "low", 2.0),
    "failed_auth_attempts_count": (8.0, 20.0, "high", 5.0),
    "suspicious_activity_score": (50.0, 80.0, "high", 20.0),
}

SEVERITY_RANK = {"info": 0, "warning": 1, "high": 2, "critical": 3}


@dataclass(frozen=True)
class BaselineStats:
    status: str  # "learned" | "insufficient_history"
    sample_count: int
    median: float | None
    mad: float | None
    robust_z: float | None
    is_anomaly: bool


def evaluate_rolling_mad_baseline(
    history_values: list[float],
    current_value: float,
    min_zero_mad_delta: float = 15.0,
) -> BaselineStats:
    """Compute robust Median/MAD deviation with explicit cold-start and zero-MAD guards."""
    n = len(history_values)
    if n < MIN_BASELINE_SAMPLES:
        return BaselineStats(
            status="insufficient_history",
            sample_count=n,
            median=None,
            mad=None,
            robust_z=None,
            is_anomaly=False,
        )

    med = float(statistics.median(history_values))
    abs_devs = [abs(v - med) for v in history_values]
    mad = float(statistics.median(abs_devs))
    diff = current_value - med

    if mad == 0.0:
        # Explicit zero-MAD handling: avoid division by zero; flag only if deviation exceeds domain delta
        is_anom = abs(diff) >= min_zero_mad_delta
        pseudo_z = round(abs(diff) / max(1.0, min_zero_mad_delta / 4.0), 2) if is_anom else 0.0
        return BaselineStats(
            status="learned",
            sample_count=n,
            median=round(med, 3),
            mad=0.0,
            robust_z=pseudo_z,
            is_anomaly=is_anom,
        )

    robust_z = 0.6745 * diff / mad
    return BaselineStats(
        status="learned",
        sample_count=n,
        median=round(med, 3),
        mad=round(mad, 3),
        robust_z=round(robust_z, 2),
        is_anomaly=abs(robust_z) >= MAD_ROBUST_Z_THRESHOLD,
    )


def evaluate_static_threshold(metric_name: str, metric_value: float) -> tuple[bool, str]:
    rule = STATIC_THRESHOLDS.get(metric_name)
    if not rule:
        return False, "info"
    warn_th, crit_th, direction, _ = rule
    if direction == "high":
        if metric_value >= crit_th:
            return True, "critical"
        if metric_value >= warn_th:
            return True, "high" if metric_value >= (warn_th + crit_th) / 2.0 else "warning"
        return False, "info"
    else:
        if metric_value <= crit_th:
            return True, "critical"
        if metric_value <= warn_th:
            return True, "warning"
        return False, "info"


def _correlation_domain(event_category: str) -> str:
    """Separate security incidents from infrastructure/network/application cascades so unrelated events never merge."""
    if event_category == "security":
        return "security_access"
    return "infra_network_service"


def _compute_evidence_score(anomalies: list[Anomaly]) -> tuple[float, str, str]:
    distinct_metrics = len({a.metric_name for a in anomalies})
    baseline_confirmed = any(a.detector_method == "rolling_mad_baseline" for a in anomalies)
    max_sev = max((a.severity for a in anomalies), key=lambda s: SEVERITY_RANK.get(s, 0), default="warning")
    sev_weight = 1.0 if max_sev == "critical" else (0.75 if max_sev == "high" else 0.5)

    score = min(
        100.0,
        round(
            30.0 * min(distinct_metrics, 2)
            + (20.0 if baseline_confirmed else 0.0)
            + 20.0 * sev_weight,
            1,
        ),
    )
    formula = (
        f"min(100, 30*min(distinct_metrics={distinct_metrics},2) "
        f"+ 20*baseline_confirmed({1 if baseline_confirmed else 0}) "
        f"+ 20*severity_weight({sev_weight}))"
    )
    strength = "Strong" if score >= 75 else ("Moderate" if score >= 50 else "Low")
    return score, formula, strength


def _build_incident_narrative(
    domain: str,
    environment_id: str,
    anomalies: list[Anomaly],
) -> tuple[str, str, str, str, str, str, str, str, str]:
    metrics = sorted({a.metric_name for a in anomalies})
    sources = sorted({a.source_id for a in anomalies})
    detectors = sorted({a.detector_method for a in anomalies})

    if domain == "security_access":
        title = f"Security Authentication Burst in {environment_id}"
        rule = "ENV_SECURITY_AUTH_BURST"
        corr_exp = (
            f"Grouped {len(anomalies)} security signal(s) ({', '.join(metrics)}) across "
            f"{len(sources)} pseudonymous source(s) in {environment_id} within {CORRELATION_WINDOW_MINUTES}m."
        )
        cause = "Repeated failed authentication attempts indicate credential stuffing or misconfigured local client."
        uncertainty = "Raw usernames and source IP addresses remain strictly local in Tier 1; inspect local auth logs."
        rec_title = "Enforce temporary rate-limit on authentication gateway and audit local auth logs"
        investigation = (
            f"Inspect Tier 1 local raw logs for pseudonymous source(s) {', '.join(sources)} "
            "to identify offending client IP or misconfigured service account."
        )
        benefit = "Mitigates brute-force risk while maintaining zero raw PII exposure in SaaS."
        sim_action = "SIM_ENABLE_AUTH_RATE_LIMIT"
        rollback = "Revert simulated authentication rate-limit rule to baseline threshold."
        return title, rule, corr_exp, cause, uncertainty, rec_title, investigation, benefit, f"{sim_action}||{rollback}"

    if len(metrics) >= 2:
        title = f"Correlated Resource & Network Degradation in {environment_id}"
        rule = "ENV_RESOURCE_NETWORK_CASCADE"
        corr_exp = (
            f"Correlated {len(anomalies)} related alerts ({', '.join(metrics)}) across "
            f"{len(sources)} pseudonymous source(s) in {environment_id} within a {CORRELATION_WINDOW_MINUTES}-minute window "
            f"using {', '.join(detectors)}."
        )
        cause = "Sustained compute/memory saturation is cascading into elevated latency or packet loss."
    else:
        primary = metrics[0]
        title = f"Anomalous {primary} Deviation in {environment_id}"
        rule = "SINGLE_SIGNAL_ANOMALY"
        corr_exp = (
            f"Flagged {len(anomalies)} anomalous observation(s) of {primary} on {', '.join(sources)} "
            f"via {', '.join(detectors)}."
        )
        cause = f"Observed {primary} significantly exceeded operational threshold or rolling Median/MAD baseline."

    uncertainty = (
        "SaaS receives approved metadata only; local process traces and packet captures remain in Tier 1 "
        "and should be checked before permanent capacity changes."
    )
    rec_title = f"Investigate {', '.join(metrics)} pressure and apply simulated load shedding"
    investigation = (
        f"Check Tier 1 host metrics for {', '.join(sources)} in {environment_id}; verify recent deployments "
        "or traffic bursts matching the event-time timestamps."
    )
    benefit = "Stabilizes service latency and restores health state toward Excellent."
    sim_action = "SIM_THROTTLE_OR_SCALE_WORKLOAD"
    rollback = "Restore prior simulated workload concurrency and rate-limit policy."
    return title, rule, corr_exp, cause, uncertainty, rec_title, investigation, benefit, f"{sim_action}||{rollback}"


def process_event_aiops(db: Session, event: TelemetryEvent) -> tuple[Anomaly | None, Incident | None]:
    """Run Method A (threshold) + Method B (rolling Median/MAD) + deterministic incident correlation."""
    rule = STATIC_THRESHOLDS.get(event.metric_name)
    min_zero_mad_delta = rule[3] if rule else 15.0

    # Gather rolling history strictly ordered by event_time_utc (excluding current row)
    prior_events = db.scalars(
        select(TelemetryEvent.metric_value)
        .where(
            TelemetryEvent.tenant_id == event.tenant_id,
            TelemetryEvent.source_id == event.source_id,
            TelemetryEvent.metric_name == event.metric_name,
            TelemetryEvent.payload_id != event.payload_id,
        )
        .order_by(TelemetryEvent.event_time_utc.desc())
        .limit(40)
    ).all()

    baseline = evaluate_rolling_mad_baseline(list(prior_events), event.metric_value, min_zero_mad_delta)
    static_hit, static_sev = evaluate_static_threshold(event.metric_name, event.metric_value)

    if not static_hit and not baseline.is_anomaly:
        return None, None

    if event.event_category == "security" and static_hit:
        detector_method = "security_burst_rule"
        severity = static_sev
    elif baseline.is_anomaly:
        detector_method = "rolling_mad_baseline"
        if static_hit and SEVERITY_RANK.get(static_sev, 0) >= SEVERITY_RANK["high"]:
            severity = static_sev
        else:
            severity = "high" if (baseline.robust_z is not None and abs(baseline.robust_z) >= 5.0) else "warning"
    else:
        detector_method = "static_threshold"
        severity = static_sev

    now_utc = datetime.now(timezone.utc)
    anomaly = Anomaly(
        anomaly_id=str(uuid.uuid4()),
        tenant_id=event.tenant_id,
        payload_id=event.payload_id,
        environment_id=event.environment_id,
        source_id=event.source_id,
        event_category=event.event_category,
        metric_name=event.metric_name,
        metric_value=event.metric_value,
        baseline_median=baseline.median,
        baseline_mad=baseline.mad,
        robust_z_score=baseline.robust_z,
        detector_method=detector_method,
        severity=severity,
        event_time_utc=event.event_time_utc,
        detected_at_utc=now_utc,
    )
    db.add(anomaly)
    db.flush()

    domain = _correlation_domain(event.event_category)
    ev_time = (
        event.event_time_utc.astimezone(timezone.utc)
        if event.event_time_utc.tzinfo
        else event.event_time_utc.replace(tzinfo=timezone.utc)
    )
    window_start = ev_time - timedelta(minutes=CORRELATION_WINDOW_MINUTES)

    # Find an existing open incident in the same tenant, environment, correlation domain, and 5-min window
    existing_incident = db.scalar(
        select(Incident)
        .where(
            Incident.tenant_id == event.tenant_id,
            Incident.environment_id == event.environment_id,
            Incident.correlation_group == domain,
            Incident.status.in_(["open", "acknowledged"]),
            Incident.last_observed_utc >= window_start,
        )
        .order_by(Incident.last_observed_utc.desc())
    )

    if existing_incident is None:
        inc_id = str(uuid.uuid4())
        score, formula, strength = _compute_evidence_score([anomaly])
        (
            title,
            corr_rule,
            corr_exp,
            cause,
            uncertainty,
            rec_title,
            investigation,
            benefit,
            action_and_rb,
        ) = _build_incident_narrative(domain, event.environment_id, [anomaly])
        sim_action, rollback = action_and_rb.split("||", 1)

        incident = Incident(
            incident_id=inc_id,
            tenant_id=event.tenant_id,
            environment_id=event.environment_id,
            region_id=event.region_id,
            correlation_group=domain,
            title=title,
            status="open",
            severity=severity,
            correlation_rule=corr_rule,
            correlation_explanation=corr_exp,
            probable_cause=cause,
            uncertainty_note=uncertainty,
            evidence_score=score,
            evidence_score_formula=formula,
            first_observed_utc=ev_time,
            last_observed_utc=ev_time,
            alert_created_utc=now_utc,
        )
        db.add(incident)
        db.flush()

        db.add(
            IncidentEvidence(
                tenant_id=event.tenant_id,
                incident_id=inc_id,
                anomaly_id=anomaly.anomaly_id,
                payload_id=event.payload_id,
                source_id=event.source_id,
                event_time_utc=ev_time,
            )
        )
        db.add(
            Recommendation(
                recommendation_id=str(uuid.uuid4()),
                tenant_id=event.tenant_id,
                incident_id=inc_id,
                title=rec_title,
                detector_responsible=f"{detector_method} + {corr_rule}",
                probable_explanation=cause,
                suggested_investigation=investigation,
                expected_benefit=benefit,
                risk_or_uncertainty=uncertainty,
                evidence_strength=strength,
                simulated_remediation_available=True,
                simulated_action_code=sim_action,
                rollback_plan=rollback,
            )
        )
        return anomaly, incident

    # Correlate into existing open incident
    db.add(
        IncidentEvidence(
            tenant_id=event.tenant_id,
            incident_id=existing_incident.incident_id,
            anomaly_id=anomaly.anomaly_id,
            payload_id=event.payload_id,
            source_id=event.source_id,
            event_time_utc=ev_time,
        )
    )
    db.flush()

    ev_rows = db.scalars(
        select(IncidentEvidence).where(IncidentEvidence.incident_id == existing_incident.incident_id)
    ).all()
    anom_ids = [r.anomaly_id for r in ev_rows]
    all_anoms = db.scalars(select(Anomaly).where(Anomaly.anomaly_id.in_(anom_ids))).all()

    score, formula, strength = _compute_evidence_score(list(all_anoms))
    (
        title,
        corr_rule,
        corr_exp,
        cause,
        uncertainty,
        rec_title,
        investigation,
        benefit,
        action_and_rb,
    ) = _build_incident_narrative(domain, event.environment_id, list(all_anoms))
    sim_action, rollback = action_and_rb.split("||", 1)

    existing_incident.title = title
    existing_incident.correlation_rule = corr_rule
    existing_incident.correlation_explanation = corr_exp
    existing_incident.probable_cause = cause
    existing_incident.uncertainty_note = uncertainty
    existing_incident.evidence_score = score
    existing_incident.evidence_score_formula = formula
    if SEVERITY_RANK.get(severity, 0) > SEVERITY_RANK.get(existing_incident.severity, 0):
        existing_incident.severity = severity
    first_obs = (
        existing_incident.first_observed_utc.astimezone(timezone.utc)
        if existing_incident.first_observed_utc.tzinfo
        else existing_incident.first_observed_utc.replace(tzinfo=timezone.utc)
    )
    last_obs = (
        existing_incident.last_observed_utc.astimezone(timezone.utc)
        if existing_incident.last_observed_utc.tzinfo
        else existing_incident.last_observed_utc.replace(tzinfo=timezone.utc)
    )
    if ev_time < first_obs:
        existing_incident.first_observed_utc = ev_time
    if ev_time > last_obs:
        existing_incident.last_observed_utc = ev_time

    rec = db.scalar(
        select(Recommendation).where(Recommendation.incident_id == existing_incident.incident_id).limit(1)
    )
    if rec:
        rec.title = rec_title
        rec.detector_responsible = f"{', '.join(sorted({a.detector_method for a in all_anoms}))} + {corr_rule}"
        rec.probable_explanation = cause
        rec.suggested_investigation = investigation
        rec.expected_benefit = benefit
        rec.risk_or_uncertainty = uncertainty
        rec.evidence_strength = strength
        rec.simulated_action_code = sim_action
        rec.rollback_plan = rollback

    return anomaly, existing_incident
