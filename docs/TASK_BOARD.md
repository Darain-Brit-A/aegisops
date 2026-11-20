# AegisOps 24-Hour Execution Task Board

Priority Legend: `P0` = Must-have privacy/reliability core | `P1` = Core AIOps intelligence & evidence | `P2` = Hardening & polish.

## Phase 1: Hour 0–2 — Foundation (Current)
- [x] `TASK-001` (`P0`, Mishael): Initialize repository, architecture docs, trust boundaries, data policy, and ADRs.
- [x] `TASK-002` (`P0`, Mishael): Author strict versioned JSON Schemas (`contracts/`) and OpenAPI 3.1 snapshot.
- [x] `TASK-003` (`P0`, Mishael): Build audit automation (`scripts/audit/*`), Git hooks, CODEOWNERS, PR template, and CI workflow.
- [x] `TASK-004` (`P0`, Mishael): Create `docker-compose.yml` with isolated networks, `.env.example`, `Makefile`, shared simulator fixtures, and minimal buildable scaffolds.
- [x] `TASK-005` (`P0`, Mishael): Create actionable handoff guides (`HANDOFF_SHERWIN.md`, `HANDOFF_PRAVEEN.md`, `HANDOFF_DARAIN.md`).

## Phase 2: Hour 2–6 — Core Implementation (Parallel Work Starts)
- [ ] `TASK-101` (`P0`, Sherwin): Implement Tier 1 adapters (`simulator`, `psutil`, pluggable `organizer_stream`), UTC normalization, and local SQLite `raw_events` store with retention purge.
- [ ] `TASK-102` (`P0`, Sherwin): Implement default-deny allow-list builder, secret detector, HMAC-SHA256 pseudonymizer, canonical JSON serializer + SHA-256 hash, and local `egress_proofs` table.
- [ ] `TASK-103` (`P0`, Sherwin): Implement durable SQLite `outbox_queue`, HTTPX authenticated transport (`X-Collector-Token`), bounded exponential backoff + jitter, and local inspection API (`127.0.0.1:8001`).
- [ ] `TASK-201` (`P0`, Praveen): Implement SQLAlchemy 2 models + Alembic migrations for all PostgreSQL entities (`docs/DATABASE_SCHEMA.md`) and dev tenant/collector seed.
- [ ] `TASK-202` (`P0`, Praveen): Implement collector token auth (server-bound `tenant_id` check), operator token auth (`X-Tenant-Token`), strict `POST /api/v1/ingest/telemetry` (`extra="forbid"`), and idempotent deduplication on `UNIQUE(tenant_id, payload_id)`.
- [ ] `TASK-203` (`P0`, Praveen): Implement `POST /api/v1/ingest/heartbeat`, `GET /api/v1/overview`, `GET /api/v1/metrics` (ordered by `event_time_utc`), `GET /api/v1/collectors`, and `GET /api/v1/saas-receipts`.
- [ ] `TASK-301` (`P0`, Darain): Build design tokens, app shell, navigation, Zod-validated API clients (SaaS `:8000` + local-only Collector `:8001`), and TanStack Query 3s polling hooks.
- [ ] `TASK-302` (`P0`, Darain): Build **Fleet Overview** (`/`) and **Collector Fleet** (`/collectors`) screens with loading/empty/error states.

**Milestone M1 (Hour 6)**: A sanitized telemetry event travels from Tier 1 Collector -> Tier 2 SaaS -> PostgreSQL -> Frontend Dashboard, with matching `payload_sha256` in Egress Proof.

## Phase 3: Hour 6–10 — Working MVP & Health
- [ ] `TASK-104` (`P0`, Sherwin): Add collector heartbeat loop, privacy leak tests (verify synthetic secrets/raw fields never appear in outbound bytes), and restart-survival outbox tests.
- [ ] `TASK-204` (`P1`, Praveen): Implement 4-state health evaluator (`Excellent`, `Good`, `Fair`, `Poor`) with 45s stale / 60s offline downgrading and UTC `health_transitions` history.
- [ ] `TASK-205` (`P1`, Praveen): Implement dual anomaly detection: Method A (static thresholds) + Method B (rolling Median/MAD robust z-score with `MIN_SAMPLES=8` and zero-MAD handling).
- [ ] `TASK-303` (`P0`, Darain): Build **Egress Proof** (`/egress-proof`) side-by-side Tier 1 Raw vs Tier 2 SaaS Received view with `payload_sha256` parity badge.
- [ ] `TASK-006` (`P0`, Mishael): Wire end-to-end integration tests (collector -> SaaS -> tenant isolation -> duplicate rejection -> outage recovery).

## Phase 4: Hour 10–14 — AIOps Intelligence & Reliability
- [ ] `TASK-206` (`P1`, Praveen): Implement deterministic incident correlation engine, explainable recommendations with deterministic `evidence_score`, `GET /api/v1/incidents`, and `POST /api/v1/incidents/{id}/simulate-remediation`.
- [ ] `TASK-207` (`P1`, Praveen): Implement `GET /api/v1/reliability` (actual measured P50/P95 ingest & alert latencies, duplicate counts, out-of-order counts) and `GET /api/v1/architecture/trust-summary`.
- [ ] `TASK-304` (`P1`, Darain): Build **Incident Intelligence** (`/incidents`) with correlation trace, evidence score formula, and safe Simulated Remediation approval flow.
- [ ] `TASK-305` (`P1`, Darain): Build **Reliability Lab** (`/reliability`) with browser-side dashboard render latency instrumentation and **Architecture & Trust** (`/trust`).
- [ ] `TASK-007` (`P1`, Mishael): Run all 8 live validation scenarios via `scripts/demo/run_scenarios.py` and record observed evidence in `docs/JUDGE_EVIDENCE.md`.

## Phase 5: Hour 14–21 — Hardening & Demo Readiness
- [ ] `TASK-008` (`P1`, All): Cross-tenant isolation verification, out-of-order multi-timezone verification, outage/reconnect zero-loss/zero-duplicate proof, anti-slop UI audit, accessibility check.
- [ ] `TASK-009` (`P2`, Mishael): Finalize deployment / TLS reverse-proxy demo setup, rehearse 18-step `docs/DEMO_RUNBOOK.md`, capture backup evidence.

## Phase 6: Hour 21–24 — Freeze
- [ ] `TASK-010` (`P0`, Mishael): Code freeze, final `integration_gate.py`, repository audit checkpoint, final live rehearsal.
