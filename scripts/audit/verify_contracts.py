"""Validates all AegisOps JSON Schemas and OpenAPI snapshot in contracts/.

Performs:
1. Draft 2020-12 meta-schema validation on every *.schema.json file.
2. Positive fixture validation confirming valid payloads pass.
3. Negative adversarial validation confirming raw logs, secrets, IPs, hostnames,
   unknown fields, and non-UTC timestamps are strictly REJECTED.
4. Structural verification of contracts/openapi.snapshot.json.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, ValidationError

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACTS_DIR = REPO_ROOT / "contracts"

REQUIRED_SCHEMAS = [
    "metadata.schema.json",
    "heartbeat.schema.json",
    "health.schema.json",
    "incident.schema.json",
    "egress_proof.schema.json",
]

VALID_METADATA_SAMPLE: dict[str, Any] = {
    "schema_version": "1.0",
    "payload_id": "11111111-2222-4333-8444-555555555555",
    "collector_id": "col-acme-blr-01",
    "tenant_id": "tenant-acme-prod",
    "environment_id": "env-blr-dc1",
    "region_id": "ap-south-1",
    "source_id": "src_a1b2c3d4e5f60718293a",
    "event_time_utc": "2026-11-20T09:00:00Z",
    "source_timezone": "Asia/Kolkata",
    "event_category": "infrastructure",
    "severity": "warning",
    "health_state": "Fair",
    "metric_name": "cpu_usage_percent",
    "metric_value": 87.4,
    "metric_unit": "percent",
    "policy_version": "1",
    "event_code": "CPU_ANOMALY",
    "summary_code": "RESOURCE_DEVIATION",
    "signal_count": 1,
    "redacted_field_count": 3,
    "local_anomaly_score": 4.2,
}

ADVERSARIAL_METADATA_CASES: list[tuple[str, dict[str, Any]]] = [
    ("unknown_raw_log_field", {**VALID_METADATA_SAMPLE, "raw_log": "ERROR password=secret"}),
    ("unknown_ip_address_field", {**VALID_METADATA_SAMPLE, "ip_address": "10.0.0.5"}),
    ("unknown_hostname_field", {**VALID_METADATA_SAMPLE, "hostname": "prod-db-01.internal"}),
    ("non_pseudonymous_source_id", {**VALID_METADATA_SAMPLE, "source_id": "prod-db-01.internal"}),
    ("non_utc_timestamp", {**VALID_METADATA_SAMPLE, "event_time_utc": "2026-11-20T14:30:00+05:30"}),
    ("unapproved_summary_free_text", {**VALID_METADATA_SAMPLE, "summary_code": "Free text secret leak"}),
]

VALID_HEARTBEAT_SAMPLE: dict[str, Any] = {
    "schema_version": "1.0",
    "collector_id": "col-acme-blr-01",
    "tenant_id": "tenant-acme-prod",
    "environment_id": "env-blr-dc1",
    "region_id": "ap-south-1",
    "collector_version": "0.1.0",
    "config_status": "valid",
    "policy_version": "1",
    "sent_at_utc": "2026-11-20T09:00:05Z",
    "pending_outbox_count": 0,
    "retry_count": 0,
    "last_delivery_status": "ok",
    "collector_cpu_percent": 3.4,
    "collector_memory_mb": 64.2,
}

VALID_HEALTH_SAMPLE: dict[str, Any] = {
    "entity_type": "collector",
    "entity_id": "col-acme-blr-01",
    "tenant_id": "tenant-acme-prod",
    "health_state": "Fair",
    "previous_state": "Excellent",
    "evaluated_at_utc": "2026-11-20T09:00:10Z",
    "last_heartbeat_utc": "2026-11-20T09:00:05Z",
    "is_stale": False,
    "reason_code": "ELEVATED_RESOURCE_OR_NETWORK",
    "explanation": "CPU usage exceeded 80% threshold on pseudonymous source src_a1b2c3d4e5f60718293a.",
    "contributing_signals": [
        {
            "metric_name": "cpu_usage_percent",
            "metric_value": 87.4,
            "threshold_state": "Fair",
            "observed_at_utc": "2026-11-20T09:00:00Z",
        }
    ],
    "transitions": [
        {
            "from_state": "Excellent",
            "to_state": "Fair",
            "changed_at_utc": "2026-11-20T09:00:10Z",
            "reason_code": "ELEVATED_RESOURCE_OR_NETWORK",
            "explanation": "CPU threshold breach",
        }
    ],
}

VALID_INCIDENT_SAMPLE: dict[str, Any] = {
    "incident_id": "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
    "tenant_id": "tenant-acme-prod",
    "environment_id": "env-blr-dc1",
    "region_id": "ap-south-1",
    "title": "Correlated CPU & Network Latency Degradation",
    "status": "open",
    "severity": "high",
    "first_observed_utc": "2026-11-20T09:00:00Z",
    "last_observed_utc": "2026-11-20T09:01:00Z",
    "alert_created_utc": "2026-11-20T09:01:02Z",
    "affected_sources": ["src_a1b2c3d4e5f60718293a"],
    "correlation_rule": "ENV_RESOURCE_NETWORK_CASCADE",
    "correlation_explanation": "Grouped CPU deviation and network latency spike within 5m on env-blr-dc1.",
    "probable_cause": "Compute saturation degrading outbound request latency.",
    "uncertainty_note": "Raw process list remains local in Tier 1; confirm top PID locally.",
    "evidence_score": 80.0,
    "evidence_score_formula": "min(100, 30*min(distinct_signals=2,2) + 20*baseline_confirmed(1) + 0)",
    "contributing_signals": [
        {
            "payload_id": "11111111-2222-4333-8444-555555555555",
            "source_id": "src_a1b2c3d4e5f60718293a",
            "event_category": "infrastructure",
            "metric_name": "cpu_usage_percent",
            "metric_value": 87.4,
            "baseline_median": 32.0,
            "baseline_mad": 4.5,
            "robust_z_score": 8.3,
            "detector_method": "rolling_mad_baseline",
            "event_time_utc": "2026-11-20T09:00:00Z",
        }
    ],
    "recommendations": [
        {
            "recommendation_id": "99999999-8888-4777-8666-555555555555",
            "incident_id": "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
            "title": "Inspect local compute workload and shed non-critical traffic",
            "detector_responsible": "rolling_mad_baseline + ENV_RESOURCE_NETWORK_CASCADE",
            "probable_explanation": "Sustained CPU deviation aligns with rising latency.",
            "suggested_investigation": "Review local Tier 1 host telemetry for src_a1b2c3d4e5f60718293a.",
            "expected_benefit": "Restores P95 latency within baseline.",
            "risk_or_uncertainty": "Upstream network congestion cannot be ruled out without local flow check.",
            "evidence_strength": "Strong",
            "evidence_timestamps_utc": ["2026-11-20T09:00:00Z"],
            "simulated_remediation_available": True,
            "simulated_action_code": "SIM_SCALE_OR_THROTTLE_WORKLOAD",
            "rollback_plan": "Restore previous simulated rate-limit policy.",
        }
    ],
}

VALID_EGRESS_PROOF_SAMPLE: dict[str, Any] = {
    "proof_id": "22222222-3333-4444-8555-666666666666",
    "payload_id": VALID_METADATA_SAMPLE["payload_id"],
    "tenant_id": "tenant-acme-prod",
    "collector_id": "col-acme-blr-01",
    "policy_version": "1",
    "event_time_utc": "2026-11-20T09:00:00Z",
    "transmitted_at_utc": "2026-11-20T09:00:01Z",
    "acknowledged_at_utc": "2026-11-20T09:00:01Z",
    "delivery_state": "delivered",
    "raw_event_local_only": {"hostname": "prod-db-01.internal", "raw_log": "token=AEGIS_DEMO_SECRET_TOKEN_9F2A"},
    "redacted_fields": ["hostname", "raw_log"],
    "outbound_payload": VALID_METADATA_SAMPLE,
    "outbound_canonical_json": json.dumps(VALID_METADATA_SAMPLE, sort_keys=True, separators=(",", ":")),
    "payload_sha256": "a" * 64,
    "rejection_reason": None,
}


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def verify_all() -> tuple[bool, list[str]]:
    errors: list[str] = []

    validators: dict[str, Draft202012Validator] = {}
    for schema_name in REQUIRED_SCHEMAS:
        path = CONTRACTS_DIR / schema_name
        if not path.exists():
            errors.append(f"Missing required schema: {path}")
            continue
        try:
            schema = load_json(path)
            Draft202012Validator.check_schema(schema)
            if schema.get("additionalProperties") is not False:
                errors.append(f"Schema {schema_name} MUST set additionalProperties=false")
            validators[schema_name] = Draft202012Validator(schema)
        except Exception as exc:
            errors.append(f"Invalid JSON schema {schema_name}: {exc}")

    positive_checks = [
        ("metadata.schema.json", VALID_METADATA_SAMPLE),
        ("heartbeat.schema.json", VALID_HEARTBEAT_SAMPLE),
        ("health.schema.json", VALID_HEALTH_SAMPLE),
        ("incident.schema.json", VALID_INCIDENT_SAMPLE),
        ("egress_proof.schema.json", VALID_EGRESS_PROOF_SAMPLE),
    ]
    for schema_name, sample in positive_checks:
        if schema_name in validators:
            try:
                validators[schema_name].validate(sample)
            except ValidationError as exc:
                errors.append(f"Positive sample failed {schema_name}: {exc.message}")

    if "metadata.schema.json" in validators:
        meta_validator = validators["metadata.schema.json"]
        for case_name, bad_payload in ADVERSARIAL_METADATA_CASES:
            errs = list(meta_validator.iter_errors(bad_payload))
            if not errs:
                errors.append(f"SECURITY FAILURE: metadata.schema.json accepted adversarial case '{case_name}'")

    openapi_path = CONTRACTS_DIR / "openapi.snapshot.json"
    if not openapi_path.exists():
        errors.append(f"Missing OpenAPI snapshot: {openapi_path}")
    else:
        try:
            spec = load_json(openapi_path)
            if not str(spec.get("openapi", "")).startswith("3."):
                errors.append("openapi.snapshot.json missing OpenAPI 3.x version field")
            required_paths = [
                "/health",
                "/api/v1/ingest/telemetry",
                "/api/v1/ingest/heartbeat",
                "/api/v1/overview",
                "/api/v1/metrics",
                "/api/v1/collectors",
                "/api/v1/incidents",
                "/api/v1/saas-receipts",
                "/api/v1/reliability",
                "/local/v1/egress-proof",
            ]
            paths = spec.get("paths", {})
            for p in required_paths:
                if p not in paths:
                    errors.append(f"openapi.snapshot.json missing required path: {p}")
        except Exception as exc:
            errors.append(f"Invalid openapi.snapshot.json: {exc}")

    return len(errors) == 0, errors


def main() -> int:
    ok, errors = verify_all()
    if ok:
        print(
            f"[PASS] Verified {len(REQUIRED_SCHEMAS)} strict JSON schemas, "
            f"{len(ADVERSARIAL_METADATA_CASES)} negative privacy cases, and openapi.snapshot.json."
        )
        return 0
    print("[FAIL] Contract verification failed:")
    for err in errors:
        print(f"  - {err}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
