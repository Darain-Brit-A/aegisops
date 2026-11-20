"""Comprehensive security, privacy, egress proof, and outbox durability tests for Tier 1 Collector."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import httpx
from jsonschema import Draft202012Validator

from aegis_collector.config import CollectorConfig
from aegis_collector.normalization.normalizer import normalize_event_time_utc
from aegis_collector.pipeline import CollectorPipeline
from aegis_collector.security.policy import canonical_serialize_and_hash, pseudonymize_source
from aegis_collector.storage.sqlite_store import CollectorSQLiteStore
from aegis_collector.transport.sender import CollectorTransport

REPO_ROOT = Path(__file__).resolve().parents[2]
METADATA_SCHEMA = json.loads((REPO_ROOT / "contracts" / "metadata.schema.json").read_text(encoding="utf-8"))
EGRESS_PROOF_SCHEMA = json.loads((REPO_ROOT / "contracts" / "egress_proof.schema.json").read_text(encoding="utf-8"))
META_VALIDATOR = Draft202012Validator(METADATA_SCHEMA)
PROOF_VALIDATOR = Draft202012Validator(EGRESS_PROOF_SCHEMA)


def make_config(tmp_path: Path) -> CollectorConfig:
    return CollectorConfig(
        collector_id="col-acme-blr-01",
        tenant_id="tenant-acme-prod",
        environment_id="env-blr-dc1",
        region_id="ap-south-1",
        collector_version="0.1.0",
        policy_version="1",
        source_timezone="Asia/Kolkata",
        saas_ingest_url="https://saas.aegisops.test/api/v1/ingest/telemetry",
        saas_heartbeat_url="https://saas.aegisops.test/api/v1/ingest/heartbeat",
        auth_token="dev-col-token-acme-local-placeholder",
        hmac_secret="unit-test-local-secret-salt",
        sqlite_path=tmp_path / "collector_test.db",
        raw_retention_hours=24,
        tls_verify=True,
        adapter_mode="simulator",
        organizer_stream_url="",
        heartbeat_interval_seconds=10,
        flush_interval_seconds=2,
    )


def test_secret_redaction_and_default_deny_zero_leak(tmp_path: Path) -> None:
    cfg = make_config(tmp_path)
    store = CollectorSQLiteStore(cfg.sqlite_path)
    captured_bodies: list[bytes] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["X-Collector-Token"] == cfg.auth_token
        captured_bodies.append(request.content)
        return httpx.Response(201, json={"status": "accepted", "duplicate": False})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    pipeline = CollectorPipeline(cfg, store, CollectorTransport(cfg, store, client=client))

    raw_event = {
        "adapter": "simulator",
        "hostname": "prod-payments-db-01.internal",
        "ip_address": "10.42.8.19",
        "username": "svc_billing",
        "password": "SYNTHETIC_DEMO_PASS_01",
        "api_key": "AEGIS_DEMO_SECRET_TOKEN_9F2A",
        "raw_log": "ERROR token=AEGIS_DEMO_SECRET_TOKEN_9F2A password=SYNTHETIC_DEMO_PASS_01",
        "source_timezone": "Asia/Kolkata",
        "event_time_utc": "2026-11-20T14:30:00+05:30",
        "event_category": "infrastructure",
        "metric_name": "cpu_usage_percent",
        "metric_value": 42.5,
        "metric_unit": "percent",
    }

    res = pipeline.ingest_raw_event(raw_event, flush_immediately=True)
    assert res["accepted_locally"] is True
    assert len(captured_bodies) == 1

    transmitted_bytes = captured_bodies[0]
    transmitted_text = transmitted_bytes.decode("utf-8")

    # CRITICAL PRIVACY INVARIANT: ZERO raw secrets, hostnames, IPs, usernames, or raw logs transmitted
    for forbidden in [
        "AEGIS_DEMO_SECRET_TOKEN_9F2A",
        "SYNTHETIC_DEMO_PASS_01",
        "prod-payments-db-01.internal",
        "10.42.8.19",
        "svc_billing",
        "raw_log",
        "password",
        "api_key",
    ]:
        assert forbidden not in transmitted_text, f"PRIVACY LEAK: '{forbidden}' found in outbound bytes!"

    # Must strictly validate against shared contracts/metadata.schema.json
    parsed = json.loads(transmitted_text)
    META_VALIDATOR.validate(parsed)
    assert parsed["event_time_utc"] == "2026-11-20T09:00:00Z"
    assert parsed["source_id"].startswith("src_")
    assert parsed["event_code"] == "RAW_SECRET_REDACTED_LOCALLY"

    # Egress Proof integrity: exact byte & SHA-256 parity
    proofs = store.list_egress_proofs(limit=5)
    assert len(proofs) == 1
    proof = proofs[0]
    PROOF_VALIDATOR.validate(proof)
    assert proof["delivery_state"] == "delivered"
    assert proof["outbound_canonical_json"] == transmitted_text
    assert proof["payload_sha256"] == hashlib.sha256(transmitted_bytes).hexdigest()
    assert proof["raw_event_local_only"]["api_key"] == "AEGIS_DEMO_SECRET_TOKEN_9F2A"
    assert "api_key" in proof["redacted_fields"]
    assert "password" in proof["redacted_fields"]


def test_hmac_pseudonym_stability_and_salt_sensitivity() -> None:
    p1 = pseudonymize_source("prod-db-01.internal", "secret-salt-a")
    p2 = pseudonymize_source("PROD-DB-01.INTERNAL", "secret-salt-a")
    p3 = pseudonymize_source("prod-db-01.internal", "secret-salt-b")
    assert p1 == p2
    assert p1 != p3
    assert p1.startswith("src_") and len(p1) == 24
    assert "prod-db" not in p1


def test_policy_rejection_blocks_outbox_and_logs_reason(tmp_path: Path) -> None:
    cfg = make_config(tmp_path)
    store = CollectorSQLiteStore(cfg.sqlite_path)
    pipeline = CollectorPipeline(cfg, store, CollectorTransport(cfg, store))

    bad_raw = {
        "hostname": "host-01",
        "event_category": "infrastructure",
        "metric_name": "UNAPPROVED_ARBITRARY_METRIC",
        "metric_value": 10.0,
        "metric_unit": "percent",
    }
    res = pipeline.ingest_raw_event(bad_raw, flush_immediately=False)
    assert res["accepted_locally"] is False
    assert res["delivery_state"] == "policy_rejected"
    assert store.get_outbox_summary()["buffered_count"] == 0

    proofs = store.list_egress_proofs(limit=5)
    assert len(proofs) == 1
    PROOF_VALIDATOR.validate(proofs[0])
    assert proofs[0]["delivery_state"] == "policy_rejected"
    assert proofs[0]["outbound_canonical_json"] is None
    assert proofs[0]["rejection_reason"]


def test_outbox_survives_restart_and_retries_preserve_payload_id(tmp_path: Path) -> None:
    cfg = make_config(tmp_path)
    store_before = CollectorSQLiteStore(cfg.sqlite_path)

    # Simulate SaaS outage during initial ingest
    def offline_handler(_req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("SaaS unreachable")

    offline_client = httpx.Client(transport=httpx.MockTransport(offline_handler))
    pipeline_before = CollectorPipeline(cfg, store_before, CollectorTransport(cfg, store_before, client=offline_client))

    res = pipeline_before.ingest_raw_event(
        {
            "hostname": "app-01.internal",
            "event_category": "infrastructure",
            "metric_name": "disk_usage_percent",
            "metric_value": 71.0,
            "metric_unit": "percent",
            "source_timezone": "America/New_York",
            "event_time_utc": "2026-11-20T04:00:00-05:00",
        },
        flush_immediately=True,
    )
    original_payload_id = res["payload_id"]
    assert store_before.get_outbox_summary()["buffered_count"] == 1
    assert store_before.get_outbox_summary()["connection_state"] == "offline"

    # Simulate complete process restart with a brand-new SQLite store instance on the same file
    store_after = CollectorSQLiteStore(cfg.sqlite_path)
    assert store_after.get_outbox_summary()["buffered_count"] == 1

    received_payloads: list[dict[str, Any]] = []

    def online_handler(req: httpx.Request) -> httpx.Response:
        received_payloads.append(json.loads(req.content.decode("utf-8")))
        return httpx.Response(201, json={"status": "accepted", "duplicate": False})

    online_client = httpx.Client(transport=httpx.MockTransport(online_handler))
    transport_after = CollectorTransport(cfg, store_after, client=online_client)
    flush_stats = transport_after.flush_outbox(limit=10, ignore_backoff=True)

    assert flush_stats["delivered"] == 1
    assert len(received_payloads) == 1
    assert received_payloads[0]["payload_id"] == original_payload_id
    assert received_payloads[0]["event_time_utc"] == "2026-11-20T09:00:00Z"
    assert store_after.get_outbox_summary()["buffered_count"] == 0
    assert store_after.get_outbox_summary()["delivered_count"] == 1
    assert store_after.get_outbox_summary()["last_reconnect_utc"] is not None


def test_failed_logins_redacted_without_username_or_ip(tmp_path: Path) -> None:
    cfg = make_config(tmp_path)
    store = CollectorSQLiteStore(cfg.sqlite_path)
    pipeline = CollectorPipeline(cfg, store, CollectorTransport(cfg, store))

    res = pipeline.ingest_raw_event(
        {
            "hostname": "bastion-02.internal",
            "source_ip": "198.51.100.77",
            "username": "root_demo_user",
            "event_category": "security",
            "metric_name": "failed_auth_attempts_count",
            "metric_value": 27,
            "metric_unit": "count",
            "raw_log": "Failed password for root_demo_user from 198.51.100.77",
        },
        flush_immediately=False,
    )
    assert res["accepted_locally"] is True
    proof = store.list_egress_proofs(limit=1)[0]
    outbound = proof["outbound_canonical_json"]
    assert "root_demo_user" not in outbound
    assert "198.51.100.77" not in outbound
    assert proof["outbound_payload"]["event_code"] == "AUTH_FAILURE_BURST"
    assert proof["outbound_payload"]["health_state"] == "Poor"


def test_multi_timezone_normalization() -> None:
    assert normalize_event_time_utc("2026-11-20T14:30:00+05:30", "Asia/Kolkata") == "2026-11-20T09:00:00Z"
    assert normalize_event_time_utc("2026-11-20T04:00:00-05:00", "America/New_York") == "2026-11-20T09:00:00Z"
    assert normalize_event_time_utc("2026-11-20T09:00:00Z", "UTC") == "2026-11-20T09:00:00Z"


def test_canonical_serialization_determinism() -> None:
    c1, b1, h1 = canonical_serialize_and_hash({"b": 1, "a": 2})
    c2, b2, h2 = canonical_serialize_and_hash({"a": 2, "b": 1})
    assert c1 == c2 == '{"a":2,"b":1}'
    assert b1 == b2
    assert h1 == h2 == hashlib.sha256(b1).hexdigest()
