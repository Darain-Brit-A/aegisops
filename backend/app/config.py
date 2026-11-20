"""Configuration for Tier 2 Central Multi-Tenant SaaS Backend."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class BackendConfig:
    database_url: str
    region_id: str
    allowed_regions: tuple[str, ...]
    policy_version: str
    heartbeat_stale_seconds: int
    heartbeat_offline_seconds: int
    cors_origins: tuple[str, ...]
    tenant_a_id: str
    tenant_a_collector_id: str
    tenant_a_collector_token: str
    tenant_a_operator_token: str
    tenant_b_id: str
    tenant_b_collector_id: str
    tenant_b_collector_token: str
    tenant_b_operator_token: str

    @classmethod
    def from_env(cls) -> BackendConfig:
        regions_raw = os.getenv("AEGISOPS_ALLOWED_REGIONS", "ap-south-1,eu-central-1,us-east-1,us-west-2")
        cors_raw = os.getenv("BACKEND_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
        default_db = (
            "sqlite:///:memory:"
            if os.getenv("PYTEST_CURRENT_TEST")
            else "sqlite:///./backend/data/aegisops_saas_dev.db"
        )
        return cls(
            database_url=os.getenv("DATABASE_URL", default_db),
            region_id=os.getenv("AEGISOPS_REGION_ID", "ap-south-1"),
            allowed_regions=tuple(r.strip() for r in regions_raw.split(",") if r.strip()),
            policy_version=os.getenv("AEGISOPS_POLICY_VERSION", "1"),
            heartbeat_stale_seconds=int(os.getenv("BACKEND_HEARTBEAT_STALE_SECONDS", "45")),
            heartbeat_offline_seconds=int(os.getenv("BACKEND_HEARTBEAT_OFFLINE_SECONDS", "60")),
            cors_origins=tuple(o.strip() for o in cors_raw.split(",") if o.strip()),
            tenant_a_id=os.getenv("AEGISOPS_DEV_TENANT_A_ID", "tenant-acme-prod"),
            tenant_a_collector_id=os.getenv("AEGISOPS_DEV_TENANT_A_COLLECTOR_ID", "col-acme-blr-01"),
            tenant_a_collector_token=os.getenv(
                "AEGISOPS_DEV_TENANT_A_COLLECTOR_TOKEN", "dev-col-token-acme-local-placeholder"
            ),
            tenant_a_operator_token=os.getenv(
                "AEGISOPS_DEV_TENANT_A_OPERATOR_TOKEN", "dev-op-token-acme-local-placeholder"
            ),
            tenant_b_id=os.getenv("AEGISOPS_DEV_TENANT_B_ID", "tenant-globex-prod"),
            tenant_b_collector_id=os.getenv("AEGISOPS_DEV_TENANT_B_COLLECTOR_ID", "col-globex-fra-01"),
            tenant_b_collector_token=os.getenv(
                "AEGISOPS_DEV_TENANT_B_COLLECTOR_TOKEN", "dev-col-token-globex-local-placeholder"
            ),
            tenant_b_operator_token=os.getenv(
                "AEGISOPS_DEV_TENANT_B_OPERATOR_TOKEN", "dev-op-token-globex-local-placeholder"
            ),
        )
