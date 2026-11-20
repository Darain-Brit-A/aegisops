"""Authenticated HTTPX transport with bounded exponential backoff + jitter and heartbeat delivery.

NEVER logs X-Collector-Token or Authorization headers.
Transmits the EXACT canonical UTF-8 bytes stored in SQLite outbox_queue.
"""

from __future__ import annotations

import logging
import random
from datetime import datetime, timezone
from typing import Any

import httpx
import psutil

from aegis_collector.config import CollectorConfig
from aegis_collector.security.policy import CollectorHeartbeatPayload
from aegis_collector.storage.sqlite_store import CollectorSQLiteStore

logger = logging.getLogger("aegisops.collector.transport")


def compute_backoff_seconds(attempt_count: int, max_seconds: int = 60) -> float:
    base = min(float(max_seconds), float(2 ** min(attempt_count, 6)))
    jitter = random.uniform(0.0, min(1.5, base * 0.25))
    return round(base + jitter, 2)


class CollectorTransport:
    def __init__(
        self,
        config: CollectorConfig,
        store: CollectorSQLiteStore,
        client: httpx.Client | None = None,
    ) -> None:
        self.config = config
        self.store = store
        self._client = client

    def _get_client(self) -> httpx.Client:
        if self._client is not None:
            return self._client
        return httpx.Client(timeout=5.0, verify=self.config.tls_verify)

    def _headers(self) -> dict[str, str]:
        return {
            "X-Collector-Token": self.config.auth_token,
            "Content-Type": "application/json",
            "User-Agent": f"aegisops-collector/{self.config.collector_version}",
        }

    def flush_outbox(self, limit: int = 50, ignore_backoff: bool = False) -> dict[str, int]:
        """Transmit due canonical payloads from SQLite outbox to SaaS ingest."""
        items = self.store.fetch_due_outbox_items(limit=limit, ignore_backoff=ignore_backoff)
        stats = {"attempted": 0, "delivered": 0, "duplicates": 0, "retrying": 0, "rejected": 0}
        if not items:
            return stats

        was_offline = self.store.get_state("connection_state") == "offline"
        close_after = self._client is None
        client = self._get_client()

        try:
            for item in items:
                stats["attempted"] += 1
                payload_id = item["payload_id"]
                raw_bytes: bytes = bytes(item["payload_bytes"])
                attempts = int(item["attempt_count"])

                try:
                    resp = client.post(
                        self.config.saas_ingest_url,
                        headers=self._headers(),
                        content=raw_bytes,
                    )
                except httpx.HTTPError as exc:
                    backoff = compute_backoff_seconds(attempts, self.config.max_backoff_seconds)
                    self.store.mark_outbox_retry(payload_id, f"Network error: {type(exc).__name__}", backoff)
                    self.store.set_state("connection_state", "offline")
                    self.store.set_state("last_delivery_status", "offline")
                    stats["retrying"] += 1
                    logger.warning("SaaS unreachable; buffered payload_id=%s (backoff=%.1fs)", payload_id, backoff)
                    break

                if resp.status_code in (200, 201):
                    body: dict[str, Any] = {}
                    try:
                        body = resp.json()
                    except ValueError:
                        pass
                    is_dup = bool(body.get("duplicate")) or resp.status_code == 200
                    self.store.mark_outbox_delivered(payload_id, duplicate=is_dup)
                    self.store.set_state("connection_state", "online")
                    self.store.set_state("last_delivery_status", "ok")
                    if was_offline:
                        self.store.set_state(
                            "last_reconnect_utc",
                            datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                        )
                        was_offline = False
                    if is_dup:
                        stats["duplicates"] += 1
                    else:
                        stats["delivered"] += 1
                elif resp.status_code in (400, 401, 403, 422):
                    reason = f"SaaS rejected payload (HTTP {resp.status_code})"
                    self.store.mark_outbox_rejected(payload_id, reason)
                    self.store.set_state("last_delivery_status", "rejected")
                    stats["rejected"] += 1
                    logger.error("Payload rejected by SaaS: payload_id=%s status=%d", payload_id, resp.status_code)
                else:
                    backoff = compute_backoff_seconds(attempts, self.config.max_backoff_seconds)
                    self.store.mark_outbox_retry(payload_id, f"SaaS transient HTTP {resp.status_code}", backoff)
                    self.store.set_state("connection_state", "degraded")
                    self.store.set_state("last_delivery_status", "retrying")
                    stats["retrying"] += 1
        finally:
            if close_after:
                client.close()

        return stats

    def send_heartbeat(self) -> bool:
        """Send periodic collector heartbeat conforming to contracts/heartbeat.schema.json."""
        summary = self.store.get_outbox_summary()
        proc = psutil.Process()
        mem_mb = round(proc.memory_info().rss / (1024 * 1024), 2)
        cpu_pct = round(min(100.0, float(psutil.cpu_percent(interval=None))), 2)

        hb = CollectorHeartbeatPayload(
            schema_version="1.0",
            collector_id=self.config.collector_id,
            tenant_id=self.config.tenant_id,
            environment_id=self.config.environment_id,
            region_id=self.config.region_id,  # type: ignore[arg-type]
            collector_version=self.config.collector_version,
            config_status="valid",
            policy_version=self.config.policy_version,
            sent_at_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            pending_outbox_count=summary["buffered_count"],
            retry_count=summary["retry_count"],
            last_delivery_status=summary["last_delivery_status"],  # type: ignore[arg-type]
            collector_cpu_percent=cpu_pct,
            collector_memory_mb=mem_mb,
        )

        close_after = self._client is None
        client = self._get_client()
        try:
            resp = client.post(
                self.config.saas_heartbeat_url,
                headers=self._headers(),
                content=hb.model_dump_json().encode("utf-8"),
            )
            if resp.status_code in (200, 201):
                if self.store.get_state("connection_state") == "offline":
                    self.store.set_state(
                        "last_reconnect_utc",
                        datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    )
                self.store.set_state("connection_state", "online")
                return True
            return False
        except httpx.HTTPError:
            self.store.set_state("connection_state", "offline")
            self.store.set_state("last_delivery_status", "offline")
            return False
        finally:
            if close_after:
                client.close()
