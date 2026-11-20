"""Durable Tier 1 Local SQLite storage: raw_events, egress_proofs, outbox_queue, collector_state.

Uses WAL journaling so pending outbox payloads survive collector process restarts
with zero loss and preserved payload_ids.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_iso(dt: datetime | None = None) -> str:
    return (dt or _utc_now()).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


class CollectorSQLiteStore:
    def __init__(self, db_path: Path, raw_retention_hours: int = 24) -> None:
        self.db_path = db_path
        self.raw_retention_hours = raw_retention_hours
        self._lock = threading.RLock()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=15.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _init_schema(self) -> None:
        with self._lock, self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS raw_events (
                    raw_id TEXT PRIMARY KEY,
                    received_at_utc TEXT NOT NULL,
                    adapter_name TEXT NOT NULL,
                    raw_json TEXT NOT NULL,
                    expires_at_utc TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS egress_proofs (
                    proof_id TEXT PRIMARY KEY,
                    payload_id TEXT NOT NULL,
                    tenant_id TEXT NOT NULL,
                    collector_id TEXT NOT NULL,
                    policy_version TEXT NOT NULL,
                    event_time_utc TEXT NOT NULL,
                    transmitted_at_utc TEXT,
                    acknowledged_at_utc TEXT,
                    delivery_state TEXT NOT NULL,
                    raw_json TEXT NOT NULL,
                    redacted_fields_json TEXT NOT NULL,
                    outbound_canonical_json TEXT,
                    payload_sha256 TEXT,
                    rejection_reason TEXT,
                    created_at_utc TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_egress_payload_id ON egress_proofs(payload_id);
                CREATE INDEX IF NOT EXISTS idx_egress_created ON egress_proofs(created_at_utc DESC);

                CREATE TABLE IF NOT EXISTS outbox_queue (
                    payload_id TEXT PRIMARY KEY,
                    payload_bytes BLOB NOT NULL,
                    payload_sha256 TEXT NOT NULL,
                    enqueued_at_utc TEXT NOT NULL,
                    next_attempt_at_utc TEXT NOT NULL,
                    attempt_count INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL,
                    last_error TEXT,
                    delivered_at_utc TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_outbox_status_next ON outbox_queue(status, next_attempt_at_utc);

                CREATE TABLE IF NOT EXISTS collector_state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at_utc TEXT NOT NULL
                );
                """
            )

    def save_raw_event(self, raw_id: str, adapter_name: str, raw_event: dict[str, Any], received_at_utc: str) -> None:
        expires = _utc_iso(_utc_now() + timedelta(hours=self.raw_retention_hours))
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO raw_events(raw_id, received_at_utc, adapter_name, raw_json, expires_at_utc) "
                "VALUES (?, ?, ?, ?, ?)",
                (raw_id, received_at_utc, adapter_name, json.dumps(raw_event, ensure_ascii=False), expires),
            )

    def purge_expired_raw_events(self) -> int:
        now = _utc_iso()
        with self._lock, self._connect() as conn:
            cur = conn.execute("DELETE FROM raw_events WHERE expires_at_utc < ?", (now,))
            return cur.rowcount

    def enqueue_approved_payload(
        self,
        *,
        proof_id: str,
        payload_id: str,
        tenant_id: str,
        collector_id: str,
        policy_version: str,
        event_time_utc: str,
        raw_event: dict[str, Any],
        redacted_fields: list[str],
        outbound_canonical_json: str,
        outbound_bytes: bytes,
        payload_sha256: str,
    ) -> None:
        """Atomically persist local egress proof AND durable outbox item before any network call."""
        now = _utc_iso()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO egress_proofs (
                    proof_id, payload_id, tenant_id, collector_id, policy_version,
                    event_time_utc, transmitted_at_utc, acknowledged_at_utc, delivery_state,
                    raw_json, redacted_fields_json, outbound_canonical_json, payload_sha256,
                    rejection_reason, created_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, 'buffered', ?, ?, ?, ?, NULL, ?)
                """,
                (
                    proof_id,
                    payload_id,
                    tenant_id,
                    collector_id,
                    policy_version,
                    event_time_utc,
                    json.dumps(raw_event, ensure_ascii=False),
                    json.dumps(redacted_fields),
                    outbound_canonical_json,
                    payload_sha256,
                    now,
                ),
            )
            conn.execute(
                """
                INSERT OR IGNORE INTO outbox_queue (
                    payload_id, payload_bytes, payload_sha256, enqueued_at_utc,
                    next_attempt_at_utc, attempt_count, status, last_error, delivered_at_utc
                ) VALUES (?, ?, ?, ?, ?, 0, 'pending', NULL, NULL)
                """,
                (payload_id, sqlite3.Binary(outbound_bytes), payload_sha256, now, now),
            )

    def record_policy_rejection(
        self,
        *,
        proof_id: str,
        payload_id: str,
        tenant_id: str,
        collector_id: str,
        policy_version: str,
        event_time_utc: str,
        raw_event: dict[str, Any],
        redacted_fields: list[str],
        rejection_reason: str,
    ) -> None:
        now = _utc_iso()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO egress_proofs (
                    proof_id, payload_id, tenant_id, collector_id, policy_version,
                    event_time_utc, transmitted_at_utc, acknowledged_at_utc, delivery_state,
                    raw_json, redacted_fields_json, outbound_canonical_json, payload_sha256,
                    rejection_reason, created_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, 'policy_rejected', ?, ?, NULL, NULL, ?, ?)
                """,
                (
                    proof_id,
                    payload_id,
                    tenant_id,
                    collector_id,
                    policy_version,
                    event_time_utc,
                    json.dumps(raw_event, ensure_ascii=False),
                    json.dumps(redacted_fields),
                    rejection_reason,
                    now,
                ),
            )

    def fetch_due_outbox_items(self, limit: int = 50, ignore_backoff: bool = False) -> list[dict[str, Any]]:
        now = _utc_iso()
        with self._lock, self._connect() as conn:
            if ignore_backoff:
                rows = conn.execute(
                    "SELECT * FROM outbox_queue WHERE status IN ('pending', 'retrying') "
                    "ORDER BY enqueued_at_utc ASC LIMIT ?",
                    (limit,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM outbox_queue WHERE status IN ('pending', 'retrying') "
                    "AND next_attempt_at_utc <= ? ORDER BY enqueued_at_utc ASC LIMIT ?",
                    (now, limit),
                ).fetchall()
            return [dict(r) for r in rows]

    def mark_outbox_delivered(self, payload_id: str, *, duplicate: bool = False) -> None:
        now = _utc_iso()
        proof_state = "duplicate_acknowledged" if duplicate else "delivered"
        with self._lock, self._connect() as conn:
            conn.execute(
                "UPDATE outbox_queue SET status = 'delivered', delivered_at_utc = ?, last_error = NULL "
                "WHERE payload_id = ?",
                (now, payload_id),
            )
            conn.execute(
                "UPDATE egress_proofs SET delivery_state = ?, transmitted_at_utc = COALESCE(transmitted_at_utc, ?), "
                "acknowledged_at_utc = ? WHERE payload_id = ?",
                (proof_state, now, now, payload_id),
            )

    def mark_outbox_retry(self, payload_id: str, error_msg: str, backoff_seconds: float) -> None:
        now = _utc_now()
        next_try = _utc_iso(now + timedelta(seconds=backoff_seconds))
        now_iso = _utc_iso(now)
        with self._lock, self._connect() as conn:
            conn.execute(
                "UPDATE outbox_queue SET status = 'retrying', attempt_count = attempt_count + 1, "
                "next_attempt_at_utc = ?, last_error = ? WHERE payload_id = ?",
                (next_try, error_msg[:500], payload_id),
            )
            conn.execute(
                "UPDATE egress_proofs SET delivery_state = 'failed_retrying', transmitted_at_utc = ? "
                "WHERE payload_id = ?",
                (now_iso, payload_id),
            )

    def mark_outbox_rejected(self, payload_id: str, reason: str) -> None:
        now_iso = _utc_iso()
        with self._lock, self._connect() as conn:
            conn.execute(
                "UPDATE outbox_queue SET status = 'rejected', last_error = ? WHERE payload_id = ?",
                (reason[:500], payload_id),
            )
            conn.execute(
                "UPDATE egress_proofs SET delivery_state = 'policy_rejected', transmitted_at_utc = ?, "
                "rejection_reason = ? WHERE payload_id = ?",
                (now_iso, reason[:500], payload_id),
            )

    def set_state(self, key: str, value: str) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO collector_state(key, value, updated_at_utc) VALUES (?, ?, ?)",
                (key, value, _utc_iso()),
            )

    def get_state(self, key: str, default: str | None = None) -> str | None:
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT value FROM collector_state WHERE key = ?", (key,)).fetchone()
            return str(row["value"]) if row else default

    def list_egress_proofs(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM egress_proofs ORDER BY created_at_utc DESC LIMIT ?",
                (limit,),
            ).fetchall()
        results: list[dict[str, Any]] = []
        for row in rows:
            outbound_str = row["outbound_canonical_json"]
            results.append(
                {
                    "proof_id": row["proof_id"],
                    "payload_id": row["payload_id"],
                    "tenant_id": row["tenant_id"],
                    "collector_id": row["collector_id"],
                    "policy_version": row["policy_version"],
                    "event_time_utc": row["event_time_utc"],
                    "transmitted_at_utc": row["transmitted_at_utc"],
                    "acknowledged_at_utc": row["acknowledged_at_utc"],
                    "delivery_state": row["delivery_state"],
                    "raw_event_local_only": json.loads(row["raw_json"]),
                    "redacted_fields": json.loads(row["redacted_fields_json"]),
                    "outbound_payload": json.loads(outbound_str) if outbound_str else None,
                    "outbound_canonical_json": outbound_str,
                    "payload_sha256": row["payload_sha256"],
                    "rejection_reason": row["rejection_reason"],
                }
            )
        return results

    def get_outbox_summary(self) -> dict[str, Any]:
        with self._lock, self._connect() as conn:
            buffered = conn.execute(
                "SELECT COUNT(*) AS c FROM outbox_queue WHERE status IN ('pending', 'retrying')"
            ).fetchone()["c"]
            delivered = conn.execute(
                "SELECT COUNT(*) AS c FROM outbox_queue WHERE status = 'delivered'"
            ).fetchone()["c"]
            rejected = conn.execute(
                "SELECT COUNT(*) AS c FROM outbox_queue WHERE status = 'rejected'"
            ).fetchone()["c"]
            retries = conn.execute(
                "SELECT COALESCE(SUM(attempt_count), 0) AS s FROM outbox_queue"
            ).fetchone()["s"]
            recent_delivered = [
                r["payload_id"]
                for r in conn.execute(
                    "SELECT payload_id FROM outbox_queue WHERE status = 'delivered' "
                    "ORDER BY delivered_at_utc DESC LIMIT 20"
                ).fetchall()
            ]
            last_err_row = conn.execute(
                "SELECT last_error FROM outbox_queue WHERE last_error IS NOT NULL "
                "ORDER BY enqueued_at_utc DESC LIMIT 1"
            ).fetchone()
        return {
            "connection_state": self.get_state("connection_state", "online"),
            "last_delivery_status": self.get_state("last_delivery_status", "idle"),
            "last_reconnect_utc": self.get_state("last_reconnect_utc"),
            "buffered_count": int(buffered),
            "delivered_count": int(delivered),
            "rejected_count": int(rejected),
            "retry_count": int(retries),
            "last_error": last_err_row["last_error"] if last_err_row else None,
            "recent_delivered_ids": recent_delivered,
        }
