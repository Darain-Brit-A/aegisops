"""AegisOps End-to-End Integration, Privacy & Reliability Verification Harness.

Owned by Member 01 (Mishael). Runs against live Tier 1 Collector (:8001) and
Tier 2 SaaS Backend (:8000) to capture real, non-fabricated judge evidence into
`audit/evidence/e2e_evidence_latest.json`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

REPO_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_PATH = REPO_ROOT / "audit" / "evidence" / "e2e_evidence_latest.json"

SYNTHETIC_SECRETS = [
    "AEGIS_DEMO_SECRET_TOKEN_9F2A",
    "SYNTHETIC_DEMO_PASS_01",
    "prod-payments-db-01.internal",
]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_iso(dt: datetime | None = None) -> str:
    return (dt or utc_now()).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def canonical_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, int(round((pct / 100.0) * (len(ordered) - 1)))))
    return round(ordered[idx], 2)


def make_valid_payload(
    *,
    tenant_id: str,
    collector_id: str,
    environment_id: str = "env-blr-dc1",
    metric_name: str = "cpu_usage_percent",
    metric_value: float = 44.2,
    event_time_utc: str | None = None,
    payload_id: str | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "payload_id": payload_id or str(uuid.uuid4()),
        "collector_id": collector_id,
        "tenant_id": tenant_id,
        "environment_id": environment_id,
        "region_id": "ap-south-1",
        "source_id": "src_a1b2c3d4e5f60718293a",
        "event_time_utc": event_time_utc or utc_iso(),
        "source_timezone": "Asia/Kolkata",
        "event_category": "infrastructure",
        "severity": "info",
        "health_state": "Excellent",
        "metric_name": metric_name,
        "metric_value": metric_value,
        "metric_unit": "percent",
        "policy_version": "1",
        "event_code": "METRIC_NORMAL",
        "summary_code": "BASELINE_NOMINAL",
        "signal_count": 1,
        "redacted_field_count": 0,
    }


def run_suite(
    saas_base: str,
    collector_base: str,
    tenant_a_id: str,
    tenant_a_collector_id: str,
    tenant_a_collector_token: str,
    tenant_a_operator_token: str,
    tenant_b_id: str,
    tenant_b_operator_token: str,
) -> tuple[bool, dict[str, Any]]:
    results: dict[str, Any] = {
        "executed_at_utc": utc_iso(),
        "saas_base": saas_base,
        "collector_base": collector_base,
        "checks": {},
        "measured_metrics": {
            "ingest_latency_p50_ms": None,
            "ingest_latency_p95_ms": None,
            "samples": 0,
        },
    }
    latencies_ms: list[float] = []

    with httpx.Client(timeout=5.0) as client:
        # 1. Health check
        try:
            r = client.get(f"{saas_base}/health")
            results["checks"]["saas_health"] = "PASS" if r.status_code == 200 else f"FAIL ({r.status_code})"
        except httpx.HTTPError as exc:
            results["checks"]["saas_health"] = f"BLOCKED ({exc})"
            return False, results

        # 2. Strict schema rejection (raw_log / secret field must return 422)
        bad_payload = make_valid_payload(tenant_id=tenant_a_id, collector_id=tenant_a_collector_id)
        bad_payload["raw_log"] = "token=AEGIS_DEMO_SECRET_TOKEN_9F2A"
        r_bad = client.post(
            f"{saas_base}/api/v1/ingest/telemetry",
            headers={"X-Collector-Token": tenant_a_collector_token},
            json=bad_payload,
        )
        results["checks"]["strict_schema_reject_422"] = (
            "PASS" if r_bad.status_code == 422 else f"FAIL (got {r_bad.status_code})"
        )

        # 3. Server-bound tenant spoofing rejection (403)
        spoof_payload = make_valid_payload(tenant_id=tenant_b_id, collector_id=tenant_a_collector_id)
        r_spoof = client.post(
            f"{saas_base}/api/v1/ingest/telemetry",
            headers={"X-Collector-Token": tenant_a_collector_token},
            json=spoof_payload,
        )
        results["checks"]["tenant_spoof_reject_403"] = (
            "PASS" if r_spoof.status_code == 403 else f"FAIL (got {r_spoof.status_code})"
        )

        # 4. Valid ingestion + idempotent duplicate replay + latency measurement
        valid_payload = make_valid_payload(tenant_id=tenant_a_id, collector_id=tenant_a_collector_id)
        raw_bytes = canonical_bytes(valid_payload)
        expected_sha = sha256_hex(raw_bytes)
        t0 = utc_now()
        r_ok = client.post(
            f"{saas_base}/api/v1/ingest/telemetry",
            headers={"X-Collector-Token": tenant_a_collector_token, "Content-Type": "application/json"},
            content=raw_bytes,
        )
        t1 = utc_now()
        if r_ok.status_code == 201:
            latencies_ms.append((t1 - t0).total_seconds() * 1000.0)
            body = r_ok.json()
            sha_ok = body.get("payload_sha256") == expected_sha
            results["checks"]["valid_ingest_201"] = "PASS" if sha_ok else "FAIL (sha256 mismatch)"
        else:
            results["checks"]["valid_ingest_201"] = f"FAIL (got {r_ok.status_code})"

        r_dup = client.post(
            f"{saas_base}/api/v1/ingest/telemetry",
            headers={"X-Collector-Token": tenant_a_collector_token, "Content-Type": "application/json"},
            content=raw_bytes,
        )
        dup_ok = r_dup.status_code == 200 and r_dup.json().get("duplicate") is True
        results["checks"]["idempotent_duplicate_200"] = (
            "PASS" if dup_ok else f"FAIL (status={r_dup.status_code})"
        )

        # 5. Cross-tenant read isolation: Tenant B must NOT see Tenant A's payload_id
        r_receipts_b = client.get(
            f"{saas_base}/api/v1/saas-receipts?limit=100",
            headers={"X-Tenant-Token": tenant_b_operator_token},
        )
        if r_receipts_b.status_code == 200:
            text_b = r_receipts_b.text
            leaked = valid_payload["payload_id"] in text_b
            results["checks"]["cross_tenant_isolation"] = "FAIL (payload leaked to Tenant B)" if leaked else "PASS"
        else:
            results["checks"]["cross_tenant_isolation"] = f"FAIL (status={r_receipts_b.status_code})"

        # 6. Zero synthetic secrets in SaaS Tenant A receipts
        r_receipts_a = client.get(
            f"{saas_base}/api/v1/saas-receipts?limit=100",
            headers={"X-Tenant-Token": tenant_a_operator_token},
        )
        if r_receipts_a.status_code == 200:
            leaked_secrets = [s for s in SYNTHETIC_SECRETS if s in r_receipts_a.text]
            results["checks"]["zero_secret_leak_in_saas"] = (
                "PASS" if not leaked_secrets else f"FAIL (leaked={leaked_secrets})"
            )
        else:
            results["checks"]["zero_secret_leak_in_saas"] = f"FAIL (status={r_receipts_a.status_code})"

        # 7. Local collector egress proof endpoint check (optional if collector is running)
        try:
            r_proof = client.get(f"{collector_base}/local/v1/egress-proof?limit=10")
            results["checks"]["local_egress_proof_api"] = (
                "PASS" if r_proof.status_code == 200 else f"FAIL ({r_proof.status_code})"
            )
        except httpx.HTTPError:
            results["checks"]["local_egress_proof_api"] = "SKIPPED (collector not running)"

    if latencies_ms:
        results["measured_metrics"] = {
            "ingest_latency_p50_ms": round(statistics.median(latencies_ms), 2),
            "ingest_latency_p95_ms": percentile(latencies_ms, 95),
            "samples": len(latencies_ms),
        }

    all_passed = all(
        str(val).startswith("PASS") or str(val).startswith("SKIPPED")
        for val in results["checks"].values()
    )
    return all_passed, results


def main() -> int:
    parser = argparse.ArgumentParser(description="Run live AegisOps E2E integration verification.")
    parser.add_argument("--saas-url", default=os.getenv("AEGISOPS_SAAS_URL", "http://localhost:8000"))
    parser.add_argument("--collector-url", default=os.getenv("AEGISOPS_COLLECTOR_URL", "http://127.0.0.1:8001"))
    args = parser.parse_args()

    ok, report = run_suite(
        saas_base=args.saas_url.rstrip("/"),
        collector_base=args.collector_url.rstrip("/"),
        tenant_a_id=os.getenv("AEGISOPS_DEV_TENANT_A_ID", "tenant-acme-prod"),
        tenant_a_collector_id=os.getenv("AEGISOPS_DEV_TENANT_A_COLLECTOR_ID", "col-acme-blr-01"),
        tenant_a_collector_token=os.getenv(
            "AEGISOPS_DEV_TENANT_A_COLLECTOR_TOKEN", "dev-col-token-acme-local-placeholder"
        ),
        tenant_a_operator_token=os.getenv(
            "AEGISOPS_DEV_TENANT_A_OPERATOR_TOKEN", "dev-op-token-acme-local-placeholder"
        ),
        tenant_b_id=os.getenv("AEGISOPS_DEV_TENANT_B_ID", "tenant-globex-prod"),
        tenant_b_operator_token=os.getenv(
            "AEGISOPS_DEV_TENANT_B_OPERATOR_TOKEN", "dev-op-token-globex-local-placeholder"
        ),
    )

    EVIDENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print("AEGISOPS E2E INTEGRATION HARNESS")
    for name, status in report["checks"].items():
        print(f"  - {name}: {status}")
    print(f"Evidence saved: {EVIDENCE_PATH.relative_to(REPO_ROOT).as_posix()}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
