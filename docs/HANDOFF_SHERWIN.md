# Handoff Guide — Member 02 (Sherwin): Local Collector, Security & Reliability

- **Human Member**: Sherwin
- **Role**: Local Collector, Security & Reliability Engineer
- **Owned Directory**: `collector/` (EXCLUSIVE — do not edit `backend/`, `frontend/`, or `contracts/` directly)
- **Branch Prefix**: `feature/sherwin-<short-topic>` (branch from `integration`)
- **AI Tools**: Antigravity Pro -> Codex Plus (ownership never changes)

## 1. Required Reading Before First Edit
1. `AGENTS.md`
2. `docs/TEAM_OWNERSHIP.md`
3. `docs/DATA_POLICY.md` (exact 12-step local pipeline + canonical JSON rule)
4. `docs/DATABASE_SCHEMA.md` (Part B: Local SQLite schema)
5. `docs/API_CONTRACT.md` (Section 2 Ingest + Section 4 Local `:8001` Inspection API)
6. `contracts/metadata.schema.json`, `contracts/heartbeat.schema.json`, `contracts/egress_proof.schema.json`
7. `simulator/fixtures/sample_raw_events.json`

## 2. What Is Already Scaffolded in `collector/`
- `collector/pyproject.toml` (dependencies: `pydantic`, `httpx`, `psutil`, `fastapi`, `uvicorn`, `jsonschema`)
- `collector/Dockerfile`
- `collector/src/aegis_collector/main.py` (minimal health entrypoint on `:8001`)
- `collector/tests/test_scaffold.py`

## 3. Your Immediate Implementation Checklist (Priority Order)

1. **`collector/src/aegis_collector/security/`**:
   - Default-deny allow-list builder constructing a brand-new `ApprovedMetadataPayload` (`extra="forbid"`) matching `contracts/metadata.schema.json` — NEVER copy raw dict & pop keys.
   - Sensitive field detector recording `redacted_fields` names (secrets, tokens, passwords, raw logs, stack traces, hostnames, IPs, emails, usernames).
   - HMAC-SHA256 pseudonymizer: `src_` + `hmac.new(COLLECTOR_HMAC_SECRET, raw_id, sha256).hexdigest()[:20]`.
   - **Single canonical serializer** (`sort_keys=True, separators=(",", ":"), ensure_ascii=False`) + `hashlib.sha256(canonical_bytes).hexdigest()`.
2. **`collector/src/aegis_collector/storage/`**:
   - SQLite (WAL mode) tables: `raw_events` (with retention purge), `egress_proofs`, `outbox_queue` (`payload_id` PK, `payload_bytes` BLOB, retry tracking), `collector_state`.
   - Survives collector process restart without losing pending records or mutating `payload_id`.
3. **`collector/src/aegis_collector/adapters/` & `normalization/` & `analysis/`**:
   - Pluggable `TelemetrySourceAdapter`: `simulator` (loads `simulator/fixtures/sample_raw_events.json`), `psutil` (live local CPU/memory/disk), and `organizer_stream` stub configured via `COLLECTOR_ORGANIZER_STREAM_URL`.
   - UTC normalization preserving `source_timezone`.
   - Local security aggregation (e.g., convert repeated failed auth raw logs into `failed_auth_attempts_count` + `AUTH_FAILURE_BURST` without exporting usernames/IPs).
4. **`collector/src/aegis_collector/transport/`**:
   - HTTPX client sending exact `outbox_queue.payload_bytes` with `X-Collector-Token` header to `COLLECTOR_SAAS_INGEST_URL`.
   - Bounded exponential backoff + jitter on network/5xx errors; marks `delivered` or `duplicate_acknowledged` ONLY on SaaS `201`/`200` ack.
   - Periodic heartbeat sender to `COLLECTOR_SAAS_HEARTBEAT_URL` matching `contracts/heartbeat.schema.json`.
   - NEVER log `X-Collector-Token` or `COLLECTOR_HMAC_SECRET`.
5. **`collector/src/aegis_collector/audit/` (Local Inspection API `:8001`)**:
   - `GET /health`
   - `GET /local/v1/egress-proof?limit=50` (conforms to `contracts/egress_proof.schema.json`)
   - `GET /local/v1/outbox`
   - `POST /local/v1/inject` (accepts raw event JSON for live judge scenario injection)
6. **Mandatory Tests (`collector/tests/`)**:
   - Secret redaction & zero-leak proof (verify synthetic secret `AEGIS_DEMO_SECRET_TOKEN_9F2A`, raw IP, hostname, raw log never appear anywhere in outbound canonical bytes).
   - Policy rejection test (invalid payload blocked + recorded with `policy_rejected`).
   - Canonical hash parity test (proof hash == outbox hash == transmitted bytes hash).
   - SQLite outbox restart survival & retry preserving identical `payload_id`.

## 4. Git & Audit Workflow
```bash
git checkout integration && git pull
git checkout -b feature/sherwin-collector-core
# implement & test
pytest collector/tests -v
python scripts/audit/check.py --actor sherwin --action pre_commit_audit --task TASK-101
git add collector/ && git commit -m "feat(collector): implement default-deny pipeline and sqlite outbox"
```
