"""Tier 1 Local Collector Service & Local-Only Egress Proof Inspection API (:8001).

CRITICAL TRUST BOUNDARY RULE:
This FastAPI app runs inside Tier 1 (bound to 127.0.0.1:8001).
It exposes raw local events side-by-side with exact canonical outbound JSON so
operators and judges can verify Egress Proof. Tier 2 SaaS NEVER connects here.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, Query, status
from fastapi.middleware.cors import CORSMiddleware

from aegis_collector.adapters.sources import (
    OrganizerStreamAdapter,
    PsutilLocalAdapter,
    SimulatorFixtureAdapter,
    TelemetrySourceAdapter,
)
from aegis_collector.config import CollectorConfig
from aegis_collector.pipeline import CollectorPipeline
from aegis_collector.storage.sqlite_store import CollectorSQLiteStore
from aegis_collector.transport.sender import CollectorTransport

logging.basicConfig(level=os.getenv("COLLECTOR_LOG_LEVEL", "INFO"))
logger = logging.getLogger("aegisops.collector")


class CollectorRuntime:
    def __init__(self, config: CollectorConfig | None = None) -> None:
        self.config = config or CollectorConfig.from_env()
        self.store = CollectorSQLiteStore(
            db_path=self.config.sqlite_path,
            raw_retention_hours=self.config.raw_retention_hours,
        )
        self.transport = CollectorTransport(self.config, self.store)
        self.pipeline = CollectorPipeline(self.config, self.store, self.transport)
        self.adapter = self._build_adapter()
        self._stop_event = threading.Event()
        self._worker_thread: threading.Thread | None = None

    def _build_adapter(self) -> TelemetrySourceAdapter:
        mode = self.config.adapter_mode.lower()
        if mode == "psutil":
            return PsutilLocalAdapter(source_timezone=self.config.source_timezone)
        if mode == "organizer_stream" and self.config.organizer_stream_url:
            return OrganizerStreamAdapter(self.config.organizer_stream_url)
        return SimulatorFixtureAdapter()

    def start_background_loops(self) -> None:
        if os.getenv("COLLECTOR_DISABLE_BACKGROUND_LOOP", "0") == "1":
            return
        if self._worker_thread and self._worker_thread.is_alive():
            return
        self._stop_event.clear()
        self._worker_thread = threading.Thread(target=self._run_loop, name="aegis-collector-loop", daemon=True)
        self._worker_thread.start()

    def stop_background_loops(self) -> None:
        self._stop_event.set()
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=2.0)

    def _run_loop(self) -> None:
        last_hb = 0.0
        last_collect = 0.0
        last_purge = 0.0
        while not self._stop_event.is_set():
            now = time.monotonic()
            try:
                if now - last_collect >= max(5, self.config.flush_interval_seconds * 2):
                    for ev in self.adapter.collect():
                        self.pipeline.ingest_raw_event(ev, flush_immediately=False)
                    last_collect = now

                self.transport.flush_outbox(limit=50)

                if now - last_hb >= self.config.heartbeat_interval_seconds:
                    self.transport.send_heartbeat()
                    last_hb = now

                if now - last_purge >= 300:
                    self.store.purge_expired_raw_events()
                    last_purge = now
            except Exception as exc:
                logger.exception("Collector background cycle error: %s", exc)

            self._stop_event.wait(timeout=max(1, self.config.flush_interval_seconds))


_runtime: CollectorRuntime | None = None


def get_runtime() -> CollectorRuntime:
    global _runtime
    if _runtime is None:
        _runtime = CollectorRuntime()
    return _runtime


@asynccontextmanager
async def lifespan(_app: FastAPI):
    rt = get_runtime()
    rt.start_background_loops()
    try:
        yield
    finally:
        rt.stop_background_loops()


app = FastAPI(
    title="AegisOps Local Collector Inspection API (Tier 1 Local-Only)",
    version="0.1.0",
    description="Local-only inspection API for Egress Proof and outbox diagnostics. NEVER exposed to SaaS.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    cfg = CollectorConfig.from_env()
    return {
        "status": "ok",
        "service": "aegisops-collector",
        "collector_id": cfg.collector_id,
        "region_id": cfg.region_id,
        "policy_version": cfg.policy_version,
        "adapter_mode": cfg.adapter_mode,
        "utc_time": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


@app.get("/local/v1/egress-proof")
def list_egress_proof(limit: int = Query(default=50, ge=1, le=200)) -> dict[str, Any]:
    rt = get_runtime()
    records = rt.store.list_egress_proofs(limit=limit)
    return {
        "tier": "tier-1-local-only",
        "notice": "Raw events shown here remain strictly inside Tier 1 local SQLite and are NEVER transmitted to SaaS.",
        "collector_id": rt.config.collector_id,
        "policy_version": rt.config.policy_version,
        "count": len(records),
        "records": records,
    }


@app.get("/local/v1/outbox")
def get_outbox_diagnostics() -> dict[str, Any]:
    rt = get_runtime()
    summary = rt.store.get_outbox_summary()
    return {
        "collector_id": rt.config.collector_id,
        "tenant_id": rt.config.tenant_id,
        "region_id": rt.config.region_id,
        "saas_ingest_url": rt.config.saas_ingest_url,
        **summary,
    }


@app.post("/local/v1/inject", status_code=status.HTTP_202_ACCEPTED)
def inject_raw_event(raw_event: dict[str, Any], flush: bool = Query(default=True)) -> dict[str, Any]:
    """Accept a synthetic local raw event for live judge demonstrations and feed Tier 1 pipeline."""
    rt = get_runtime()
    return rt.pipeline.ingest_raw_event(raw_event, flush_immediately=flush)


@app.post("/local/v1/flush")
def flush_now() -> dict[str, Any]:
    """Immediately attempt to drain pending SQLite outbox payloads to Tier 2 SaaS."""
    rt = get_runtime()
    stats = rt.transport.flush_outbox(limit=100, ignore_backoff=True)
    hb_ok = rt.transport.send_heartbeat()
    return {"flush": stats, "heartbeat_sent": hb_ok, "outbox": rt.store.get_outbox_summary()}
