# AegisOps 24-Hour Execution Task Board

Priority Legend: `P0` = Must-have privacy/reliability core | `P1` = Core AIOps intelligence & evidence | `P2` = Hardening & polish.

## Phase 1: Foundation & Contracts
- [x] `TASK-001` (`P0`): Repository initialization, architecture docs, trust boundaries, data policy, and ADRs.
- [x] `TASK-002` (`P0`): Strict versioned JSON Schemas (`contracts/`) and OpenAPI 3.1 snapshot.
- [x] `TASK-003` (`P0`): Audit automation (`scripts/audit/*`), Git hooks, CODEOWNERS, PR template, and CI workflow.
- [x] `TASK-004` (`P0`): Isolated-network `docker-compose.yml`, TLS overlay `docker-compose.tls.yml`, `.env.example`, `Makefile`, and simulator fixtures.
- [x] `TASK-005` (`P0`): Actionable role handoff guides (`HANDOFF_MISHAEL.md`, `HANDOFF_SHERWIN.md`, `HANDOFF_PRAVEEN.md`, `HANDOFF_DARAIN.md`).

## Phase A: Tier 1 Local Collector (`collector/`)
- [x] `TASK-101` (`P0`): Pluggable source adapters (`simulator`, `psutil`, `organizer_stream`), UTC normalization, and local SQLite `raw_events` with retention purge.
- [x] `TASK-102` (`P0`): Default-deny allow-list builder, sensitive-field detector, HMAC-SHA256 pseudonymizer, canonical UTF-8 JSON serializer + SHA-256 hash, and local `egress_proofs`.
- [x] `TASK-103` (`P0`): Durable SQLite `outbox_queue` surviving restart, HTTPX authenticated transport (`X-Collector-Token`) with bounded backoff + jitter, heartbeat loop, and local `:8001` Inspection API.
- [x] `TASK-104` (`P0`): Privacy zero-leak tests, policy rejection tests, canonical hash parity tests, and outbox restart-survival tests (8/8 PASS).

## Phase B: Tier 2 SaaS Backend & AIOps (`backend/`)
- [x] `TASK-201` (`P0`): SQLAlchemy 2 ORM models for all 12+ entities (`UNIQUE(tenant_id, payload_id)`) + deterministic multi-tenant dev seed.
- [x] `TASK-202` (`P0`): Server-bound collector auth (`403` on tenant spoof), operator auth (`X-Tenant-Token`), strict `extra="forbid"` ingestion (`422` on raw fields), and idempotent deduplication.
- [x] `TASK-203` (`P0`): `POST /api/v1/ingest/heartbeat`, `GET /api/v1/overview`, `GET /api/v1/metrics` (`ORDER BY event_time_utc ASC`), `GET /api/v1/collectors`, `GET /api/v1/saas-receipts`.
- [x] `TASK-204` (`P1`): 4-state health evaluator (`Excellent`, `Good`, `Fair`, `Poor`) with 45s stale / 60s offline downgrading and UTC `health_transitions` history.
- [x] `TASK-205` (`P1`): Dual anomaly detection (static thresholds + rolling Median/MAD with `MIN_SAMPLES=8` cold-start & zero-MAD protection).
- [x] `TASK-206` (`P1`): Deterministic incident correlation, explainable recommendations with deterministic `evidence_score` formula, and safe simulated remediation (`POST /api/v1/incidents/{id}/simulate-remediation`).
- [x] `TASK-207` (`P1`): Measured reliability endpoint (`GET /api/v1/reliability`), trust summary (`GET /api/v1/architecture/trust-summary`), and backend test suite (8/8 PASS).

## Phase C: Operations Dashboard (`frontend/`)
- [x] `TASK-301` (`P0`): Anti-AI-slop design tokens, accessible app shell, live Tenant A/B session switcher, typed API clients (SaaS `:8000` + local-only Collector `:8001`), TanStack Query 3s polling.
- [x] `TASK-302` (`P0`): **Fleet Overview** and **Collector Fleet** screens with Recharts event-time charts and UTC transition history.
- [x] `TASK-303` (`P0`): **Egress Proof Panel** with Tier 1 Raw vs Tier 2 SaaS side-by-side comparison, live `SHA-256 MATCH VERIFIED` badge, and one-click local synthetic secret injection.
- [x] `TASK-304` (`P1`): **Incident Intelligence** screen with deterministic evidence formula, contributing signals table, explainable recommendations, and interactive Safe Simulated Remediation approval workflow.
- [x] `TASK-305` (`P1`): **Reliability Lab** (browser latency tracking + honest `"Not measured"` display) and **Architecture & Trust** screens + Vitest suite (5/5 PASS) + production Vite build PASS.

## Phase D: Full E2E Integration, Hardening & Release
- [x] `TASK-006` (`P0`): Full cross-tier E2E integration suite (`scripts/validation/test_e2e_full_system.py`) verifying all 10 integration checks and all 8 live validation scenarios + real measured evidence (`audit/evidence/e2e_measured_evidence.json`).
- [x] `TASK-007` (`P1`): TLS 1.3 reverse-proxy demo overlay (`docker-compose.tls.yml`) and final `integration_gate.py` -> `main` release.
- [ ] `TASK-008` (`P1`, Demo Day): Run live `docker compose up --build`, execute 18-step `docs/DEMO_RUNBOOK.md`, capture live browser render P95 latency, and connect official organizer stream URL once released.
