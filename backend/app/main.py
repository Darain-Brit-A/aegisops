"""Minimal Tier 2 SaaS Backend FastAPI scaffold.

Owned by Member 03 (Praveen). See docs/HANDOFF_PRAVEEN.md for implementation plan.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="AegisOps Central SaaS & AIOps API",
    version="0.1.0",
    description="Metadata-only multi-tenant SaaS ingestion, health, anomaly detection, and incident correlation API.",
)

cors_origins = [
    origin.strip()
    for origin in os.getenv("BACKEND_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "aegisops-backend",
        "region_id": os.getenv("AEGISOPS_REGION_ID", "ap-south-1"),
        "utc_time": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
