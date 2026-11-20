"""Minimal Tier 1 Local Collector entrypoint scaffold.

Owned by Member 02 (Sherwin). See docs/HANDOFF_SHERWIN.md for implementation plan.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="AegisOps Local Collector Inspection API (Tier 1 Local-Only)",
    version="0.1.0",
    description="Local-only inspection API for Egress Proof and outbox diagnostics. NEVER exposed to SaaS.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "aegisops-collector",
        "collector_id": os.getenv("COLLECTOR_ID", "col-acme-blr-01"),
        "region_id": os.getenv("COLLECTOR_REGION_ID", "ap-south-1"),
        "utc_time": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
