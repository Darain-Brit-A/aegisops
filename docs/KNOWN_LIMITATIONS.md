# AegisOps Known Limitations & Production Hardening Roadmap

In alignment with CICADA 2026 evaluation integrity, AegisOps explicitly distinguishes what is **implemented in the 24-hour prototype** versus what would be required for **production enterprise deployment**.

## 1. Transport Encryption (TLS)
- **Prototype**: Local Docker Compose and loopback testing use unencrypted HTTP (`http://localhost:8000` / `http://backend:8000`). The collector HTTPX client supports HTTPS with `COLLECTOR_TLS_VERIFY=true` and rejects untrusted certificates when pointed at an HTTPS endpoint.
- **Production Gap**: Full production requires mutual TLS (mTLS) or TLS 1.3 ingress termination with automated certificate rotation and short-lived collector credentials.

## 2. Multi-Tenant Data Isolation
- **Prototype**: Server-bound tenant authentication, mandatory `tenant_id` foreign keys on every tenant-owned table, query-level `WHERE tenant_id = :auth_tenant_id` enforcement, and automated cross-tenant isolation tests.
- **Production Gap**: PostgreSQL Row-Level Security (RLS) policies, per-tenant encryption keys (CMK/KMS), and optional dedicated tenant database schemas or regional clusters.

## 3. Multi-Region Data Residency
- **Prototype**: Every tenant and collector carries an explicit `region_id`, validated by the regional ingest routing interface, running on a single deployed regional instance.
- **Production Gap**: Physically separated regional clusters (e.g., `ap-south-1`, `eu-central-1`, `us-east-1`) with DNS/GeoDNS routing and compliance-audited zero cross-region replication.

## 4. Organizer Telemetry Stream Schema
- **Prototype**: Implements a pluggable `TelemetrySourceAdapter` abstraction with local `simulator` fixtures and `psutil` host metrics ready to adapt once the organizer-provided telemetry stream endpoint and schema are distributed.
- **Honest Distinction**: Local simulator fixtures are clearly labeled as test fixtures and are never claimed to be the official organizer stream.

## 5. Autonomous Ops Remediation
- **Prototype**: Safe **simulated remediation** only — demonstrates policy check, human operator approval, immutable audit record, and rollback plan without executing real infrastructure commands.
- **Production Gap**: Signed, idempotent remediation runners inside Tier 1 with RBAC, blast-radius limits, canary execution, and automated rollback triggers.

## 6. Authentication & Identity Management
- **Prototype**: Token-based collector credentials (`X-Collector-Token`) and tenant operator tokens (`X-Tenant-Token`) loaded from environment variables with rotation-ready schema fields.
- **Production Gap**: Enterprise OIDC/SAML SSO, RBAC policy engine, HSM/Vault secret management, and automated token rotation workflows.

## 7. Scalability & Long-Term Storage
- **Prototype**: Single PostgreSQL 16 instance + modular monolith FastAPI backend + 3-second frontend polling.
- **Production Gap**: Time-partitioned PostgreSQL / TimescaleDB hypertables, horizontal stateless ingest replicas behind a load balancer, and retention/downsampling policies.
