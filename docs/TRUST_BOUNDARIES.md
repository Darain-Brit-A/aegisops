# AegisOps Trust Boundaries & Security Architecture

## 1. Two-Tier Trust Boundary

AegisOps enforces a hard security perimeter between **Tier 1 (Customer Environment)** and **Tier 2 (Central SaaS)**.

| Dimension | Tier 1 — Customer Environment (`collector/`) | Tier 2 — Central SaaS (`backend/`) |
| :--- | :--- | :--- |
| **Data Held** | Raw logs, stack traces, hostnames, IPs, synthetic secrets, HMAC pseudonym salt, local SQLite raw store, egress proof log, outbox queue | Approved allow-listed metadata only, pseudonymous `source_id`s, heartbeats, anomalies, incidents, recommendations, audit logs |
| **Network Exposure** | Outbound-only HTTPS/HTTP to SaaS ingest endpoint; loopback-only (`127.0.0.1:8001`) inspection UI | Inbound authenticated ingest API (`:8000/api/v1/ingest/*`) and operator API (`:8000/api/v1/*`) |
| **Docker Network** | `ingest-boundary` ONLY (physically blocked from reaching PostgreSQL on `saas-internal`) | `saas-internal` (PostgreSQL) + `ingest-boundary` |
| **Cross-Tier Access** | Collector pushes allow-listed metadata to SaaS | SaaS NEVER pulls from collector and NEVER accesses collector SQLite |

## 2. Authentication & Authorization Controls

1. **Collector Authentication (`X-Collector-Token`)**:
   - Each collector holds a unique credential loaded from environment variables (never hardcoded or committed).
   - On the SaaS side, credentials are stored as SHA-256/salted hashes mapped to an exact `(tenant_id, collector_id, region_id)` tuple.
   - **Server-Bound Tenant Enforcement**: If a collector authenticated as `tenant-acme-prod` / `col-acme-blr-01` sends a payload claiming `tenant_id: "tenant-globex-prod"` or another `collector_id`, the SaaS immediately rejects the request with `403 Forbidden` and logs a security audit event.
   - Credential rotation is supported by storing active key version / `rotated_at_utc` fields in the `collectors` table so dual-token overlap can be enabled cleanly.

2. **Operator Dashboard Authentication (`X-Tenant-Token`)**:
   - Dashboard requests include a tenant-scoped operator token with an explicit role (`operator`, `admin`, `viewer`).
   - All dashboard API endpoints require authentication; unauthenticated requests receive `401 Unauthorized`.
   - Every query against tenant-owned tables MUST filter by the authenticated `tenant_id`.

3. **Tenant Isolation Posture (Honest Statement)**:
   - **Implemented in Prototype**: Strict server-bound tenant authentication + mandatory `tenant_id` foreign keys on every tenant-owned table + repository/service-layer `WHERE tenant_id = :auth_tenant_id` enforcement + automated cross-tenant isolation integration tests (`Tenant A` attempting to read `Tenant B` incidents, metrics, collectors, and receipts).
   - **Production Roadmap**: PostgreSQL Row-Level Security (RLS) policies setting `app.current_tenant_id` per transaction and per-region physical database clusters. We do **not** claim DB-level RLS is active until implemented and tested.

## 3. Transport Encryption (TLS Posture)

- **Local Development (`docker-compose.yml` / loopback)**: Uses HTTP on `127.0.0.1` / Docker bridge strictly for frictionless local development and testing. **We explicitly do NOT claim local loopback HTTP satisfies production TLS requirements.**
- **Production / Deployed Demo Mode**: Collector HTTPX transport enforces HTTPS (`https://...`) with `COLLECTOR_TLS_VERIFY=true` against a TLS-terminating reverse proxy (e.g., Caddy/Nginx/managed ingress with TLS 1.3) in front of the regional SaaS ingest endpoint.

## 4. Credential & Secret Hygiene

- Secrets are injected strictly via environment variables (`.env`, never committed).
- `scripts/audit/check_secrets.py` scans tracked and staged files before every commit and in CI.
- Collector never logs `X-Collector-Token`, `Authorization` headers, or `COLLECTOR_HMAC_SECRET`.
- Demonstration scenarios use clearly marked harmless synthetic strings (e.g. `AEGIS_DEMO_SECRET_TOKEN_9F2A`) that are retained locally and proven absent from outbound JSON and SaaS storage.
