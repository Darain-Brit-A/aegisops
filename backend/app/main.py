"""Tier 2 Central Multi-Tenant SaaS Backend FastAPI Application."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.api.routes import create_api_router
from app.config import BackendConfig
from app.models.database import DatabaseManager


def create_app(config: BackendConfig | None = None) -> FastAPI:
    cfg = config or BackendConfig.from_env()
    state_holder: dict[str, DatabaseManager] = {}

    def get_db_manager() -> DatabaseManager:
        if "dbm" not in state_holder:
            dbm = DatabaseManager(cfg)
            dbm.init_db_and_seed()
            state_holder["dbm"] = dbm
        return state_holder["dbm"]

    def get_db_session() -> Generator[Session, None, None]:
        dbm = get_db_manager()
        yield from dbm.get_session()

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        get_db_manager()
        yield

    application = FastAPI(
        title="AegisOps Central SaaS & AIOps API",
        version="0.1.0",
        description="Metadata-only multi-tenant SaaS ingestion, health, anomaly detection, and incident correlation API.",
        lifespan=lifespan,
    )
    application.state.config = cfg
    application.state.get_db_manager = get_db_manager

    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(cfg.cors_origins),
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.get("/health")
    def health_endpoint() -> dict[str, str]:
        return {
            "status": "ok",
            "service": "aegisops-backend",
            "region_id": cfg.region_id,
            "policy_version": cfg.policy_version,
            "utc_time": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

    application.include_router(create_api_router(get_db_session, lambda: cfg))
    return application


app = create_app()


def health() -> dict[str, str]:
    cfg: BackendConfig = app.state.config
    return {
        "status": "ok",
        "service": "aegisops-backend",
        "region_id": cfg.region_id,
        "policy_version": cfg.policy_version,
        "utc_time": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
