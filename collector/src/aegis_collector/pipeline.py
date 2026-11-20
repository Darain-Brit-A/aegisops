"""Tier 1 Collector 12-Step Processing Pipeline."""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import ValidationError

from aegis_collector.config import CollectorConfig
from aegis_collector.normalization.normalizer import build_allowlisted_metadata, utc_now_iso
from aegis_collector.security.policy import canonical_serialize_and_hash, detect_sensitive_fields
from aegis_collector.storage.sqlite_store import CollectorSQLiteStore
from aegis_collector.transport.sender import CollectorTransport


class CollectorPipeline:
    def __init__(
        self,
        config: CollectorConfig,
        store: CollectorSQLiteStore,
        transport: CollectorTransport,
    ) -> None:
        self.config = config
        self.store = store
        self.transport = transport

    def ingest_raw_event(self, raw_event: dict[str, Any], *, flush_immediately: bool = False) -> dict[str, Any]:
        """Execute Steps 1-11 locally: raw store -> redact/pseudonymize -> allow-list -> canonical proof -> outbox."""
        collected_at = utc_now_iso()
        raw_id = str(uuid.uuid4())
        proof_id = str(uuid.uuid4())
        adapter_name = str(raw_event.get("adapter") or self.config.adapter_mode)

        # Step 2: Persist raw locally under retention policy (NEVER exported)
        self.store.save_raw_event(raw_id, adapter_name, raw_event, collected_at)

        # Steps 3-8: Normalize, scrub, pseudonymize, build fresh allow-listed object, validate strictly
        try:
            approved, redacted_fields = build_allowlisted_metadata(raw_event, self.config, collected_at)
        except (ValidationError, ValueError, TypeError) as exc:
            redacted_fields, _ = detect_sensitive_fields(raw_event)
            fallback_payload_id = str(raw_event.get("payload_id") or uuid.uuid4())
            self.store.record_policy_rejection(
                proof_id=proof_id,
                payload_id=fallback_payload_id,
                tenant_id=self.config.tenant_id,
                collector_id=self.config.collector_id,
                policy_version=self.config.policy_version,
                event_time_utc=collected_at,
                raw_event=raw_event,
                redacted_fields=redacted_fields,
                rejection_reason=str(exc),
            )
            return {
                "accepted_locally": False,
                "delivery_state": "policy_rejected",
                "proof_id": proof_id,
                "payload_id": fallback_payload_id,
                "rejection_reason": str(exc),
            }

        # Step 9: Single canonical serialization + SHA-256 hash
        canonical_json, canonical_bytes, payload_sha256 = canonical_serialize_and_hash(approved)

        # Steps 10-11: Atomically record local Egress Proof + durable SQLite outbox
        self.store.enqueue_approved_payload(
            proof_id=proof_id,
            payload_id=approved.payload_id,
            tenant_id=approved.tenant_id,
            collector_id=approved.collector_id,
            policy_version=approved.policy_version,
            event_time_utc=approved.event_time_utc,
            raw_event=raw_event,
            redacted_fields=redacted_fields,
            outbound_canonical_json=canonical_json,
            outbound_bytes=canonical_bytes,
            payload_sha256=payload_sha256,
        )

        flush_stats = None
        if flush_immediately:
            flush_stats = self.transport.flush_outbox(limit=25, ignore_backoff=True)

        return {
            "accepted_locally": True,
            "delivery_state": "buffered" if not flush_stats else self.store.get_state("last_delivery_status", "buffered"),
            "proof_id": proof_id,
            "payload_id": approved.payload_id,
            "payload_sha256": payload_sha256,
            "redacted_fields": redacted_fields,
            "flush_stats": flush_stats,
        }
