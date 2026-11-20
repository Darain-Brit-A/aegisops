# Handoff Guide — Member 03 (Praveen): SaaS Backend & AIOps Intelligence

- **Human Member**: Praveen
- **Role**: SaaS Backend & AIOps Intelligence Engineer
- **Owned Directory**: `backend/` (EXCLUSIVE — do not edit `collector/`, `frontend/`, or `contracts/` directly)
- **Branch Prefix**: `feature/praveen-<short-topic>` (branch from `integration`)
- **AI Tool**: Antigravity Pro

## 1. Required Reading Before First Edit
1. `AGENTS.md`
2. `docs/TEAM_OWNERSHIP.md`
3. `docs/API_CONTRACT.md` & `contracts/openapi.snapshot.json`
4. `docs/DATABASE_SCHEMA.md` (Part A: Tier 2 PostgreSQL schema)
5. `docs/ARCHITECTURE.md` (Sections 4–6: 4-state health, MAD anomaly detection, correlation, evidence score)
6. `contracts/metadata.schema.json`, `contracts/heartbeat.schema.json`, `contracts/health.schema.json`, `contracts/incident.schema.json`

## 2. What Is Already Scaffolded in `backend/`
- `backend/pyproject.toml` (dependencies: `fastapi`, `uvicorn`, `pydantic`, `sqlalchemy`, `alembic`, `psycopg`, `httpx`, `numpy`, `jsonschema`)
- `backend/Dockerfile`
- `backend/app/main.py` (minimal FastAPI `/health` app)
- `backend/tests/test_scaffold.py`

## 3. Your Immediate Implementation Checklist (Priority Order)

1. **Models & Migrations (`backend/app/models/`, `backend/migrations/`)**:
   - SQLAlchemy 2 models for all entities in `docs/DATABASE_SCHEMA.md` (support PostgreSQL via `DATABASE_URL`, and SQLite in-memory/file for fast unit tests).
   - Unique idempotency constraint `UNIQUE(tenant_id, payload_id)` on `telemetry_events`.
   - Dev bootstrap seed creating `tenant-acme-prod` + `col-acme-blr-01` and `tenant-globex-prod` + `col-globex-fra-01` using tokens from `.env` (hashed with SHA-256).
2. **Authentication & Tenant Isolation (`backend/app/auth/`)**:
   - `X-Collector-Token` dependency resolving server-bound `(tenant_id, collector_id, region_id)` — return `401` if invalid, `403` if payload `tenant_id` or `collector_id` does not match credential.
   - `X-Tenant-Token` dependency resolving `(tenant_id, operator_role)` — every read/action query MUST filter by `tenant_id`.
3. **Strict Ingestion & Idempotency (`backend/app/ingestion/`)**:
   - `POST /api/v1/ingest/telemetry`: Pydantic v2 model with `ConfigDict(extra="forbid")` matching `contracts/metadata.schema.json` (`422` on any unknown field). Compute canonical SHA-256 hash. On duplicate `(tenant_id, payload_id)`, increment duplicate counter and return `200` `{"status": "duplicate_ignored", "duplicate": true, ...}`. On new event, detect `out_of_order` (comparing `event_time_utc` against latest stored for `(tenant_id, source_id, metric_name)`), persist, run health + AIOps pipeline, return `201`.
   - `POST /api/v1/ingest/heartbeat`: Validate against `heartbeat.schema.json`, record heartbeat, update collector online/reconnect state.
4. **4-State Health Engine (`backend/app/collectors/`)**:
   - Implement `Excellent`, `Good`, `Fair`, `Poor` precedence rules from `docs/ARCHITECTURE.md`.
   - Stale-heartbeat downgrade: `> 45s` -> `Fair` (`HEARTBEAT_STALE`), `> 60s` -> `Poor` (`COLLECTOR_OFFLINE`). Never keep a stale collector `Excellent`.
   - Persist UTC transitions in `health_transitions`.
5. **AIOps Intelligence (`backend/app/aiops/`, `backend/app/incidents/`)**:
   - Method A: Configurable static thresholds (CPU, memory, disk, latency, packet loss, availability, failed auth).
   - Method B: Rolling Median/MAD robust z-score (`MIN_SAMPLES = 8`, explicit `insufficient_history` on cold start, explicit delta fallback when `MAD == 0`).
   - Deterministic Incident Correlation: group related anomalies within `(tenant_id, environment_id)` and 5-minute window; never merge unrelated environments/categories blindly.
   - Explainable Recommendations + deterministic `evidence_score` with exact `evidence_score_formula`, `probable_cause`, `uncertainty_note`, contributing `payload_id`s, and UTC timestamps.
   - `POST /api/v1/incidents/{incident_id}/simulate-remediation`: policy check + operator approval + immutable `audit_events` record + rollback plan (clearly marked simulated).
6. **Dashboard & Reliability APIs (`backend/app/api/`, `backend/app/reliability/`)**:
   - `GET /api/v1/overview`, `GET /api/v1/metrics` (`ORDER BY event_time_utc ASC`), `GET /api/v1/collectors`, `GET /api/v1/incidents`, `GET /api/v1/incidents/{id}`, `GET /api/v1/saas-receipts`, `GET /api/v1/reliability` (real measured P50/P95 latencies, `null` when unmeasured), `GET /api/v1/architecture/trust-summary`.
7. **Mandatory Tests (`backend/tests/`)**:
   - Strict schema rejection (`raw_log` / `password` -> `422`), collector tenant spoofing (`403`), cross-tenant isolation (`Tenant A` cannot read `Tenant B` incidents/metrics/collectors/receipts), idempotent duplicate replay (`201` then `200`, single DB row), stale heartbeat -> `Poor`, MAD cold-start & zero-MAD handling, multi-alert correlation, out-of-order event-time ordering.

## 4. Git & Audit Workflow
```bash
git checkout integration && git pull
git checkout -b feature/praveen-backend-core
# implement & test
pytest backend/tests -v
python scripts/audit/check.py --actor praveen --action pre_commit_audit --task TASK-201
git add backend/ && git commit -m "feat(backend): add tenant-isolated ingestion and aiops pipeline"
```
