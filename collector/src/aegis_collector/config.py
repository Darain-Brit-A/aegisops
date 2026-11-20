"""Configuration for Tier 1 Local Collector.

Secrets (COLLECTOR_AUTH_TOKEN, COLLECTOR_HMAC_SECRET) are loaded strictly from
environment variables and NEVER logged or included in outbound payloads.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CollectorConfig:
    collector_id: str
    tenant_id: str
    environment_id: str
    region_id: str
    collector_version: str
    policy_version: str
    source_timezone: str
    saas_ingest_url: str
    saas_heartbeat_url: str
    auth_token: str
    hmac_secret: str
    sqlite_path: Path
    raw_retention_hours: int
    tls_verify: bool
    adapter_mode: str
    organizer_stream_url: str
    heartbeat_interval_seconds: int
    flush_interval_seconds: int
    max_backoff_seconds: int = 60

    @classmethod
    def from_env(cls) -> CollectorConfig:
        return cls(
            collector_id=os.getenv("COLLECTOR_ID", "col-acme-blr-01"),
            tenant_id=os.getenv("AEGISOPS_DEV_TENANT_A_ID", os.getenv("COLLECTOR_TENANT_ID", "tenant-acme-prod")),
            environment_id=os.getenv("COLLECTOR_ENVIRONMENT_ID", "env-blr-dc1"),
            region_id=os.getenv("COLLECTOR_REGION_ID", "ap-south-1"),
            collector_version=os.getenv("COLLECTOR_VERSION", "0.1.0"),
            policy_version=os.getenv("AEGISOPS_POLICY_VERSION", "1"),
            source_timezone=os.getenv("COLLECTOR_SOURCE_TIMEZONE", "Asia/Kolkata"),
            saas_ingest_url=os.getenv(
                "COLLECTOR_SAAS_INGEST_URL", "http://localhost:8000/api/v1/ingest/telemetry"
            ),
            saas_heartbeat_url=os.getenv(
                "COLLECTOR_SAAS_HEARTBEAT_URL", "http://localhost:8000/api/v1/ingest/heartbeat"
            ),
            auth_token=os.getenv("COLLECTOR_AUTH_TOKEN", "dev-col-token-acme-local-placeholder"),
            hmac_secret=os.getenv(
                "COLLECTOR_HMAC_SECRET", "local-only-pseudonym-salt-change-me-never-transmit"
            ),
            sqlite_path=Path(os.getenv("COLLECTOR_SQLITE_PATH", "./collector/data/collector_local.db")),
            raw_retention_hours=int(os.getenv("COLLECTOR_RAW_RETENTION_HOURS", "24")),
            tls_verify=os.getenv("COLLECTOR_TLS_VERIFY", "true").lower() not in {"0", "false", "no"},
            adapter_mode=os.getenv("COLLECTOR_ADAPTER_MODE", "simulator"),
            organizer_stream_url=os.getenv("COLLECTOR_ORGANIZER_STREAM_URL", ""),
            heartbeat_interval_seconds=int(os.getenv("COLLECTOR_HEARTBEAT_INTERVAL_SECONDS", "10")),
            flush_interval_seconds=int(os.getenv("COLLECTOR_FLUSH_INTERVAL_SECONDS", "2")),
        )
