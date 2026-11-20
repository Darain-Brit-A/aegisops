# AegisOps

> **Observe everything. Expose nothing.**

AegisOps is a privacy-first, two-tier AIOps observability platform built for **CICADA 2026**. It collects and analyzes infrastructure, network, application, and security telemetry inside the customer's local environment (Tier 1), keeps raw logs, payloads, and secrets strictly local, and transmits only schema-validated, allow-listed metadata over authenticated transport to a central multi-tenant SaaS platform (Tier 2).

## Core Capabilities

- **Tier 1 — Local Collector (`collector/`)**: Normalizes local telemetry, stores raw records locally under retention policy, scrubs sensitive fields, generates HMAC-salted pseudonymous source IDs, builds outbound payloads from a fresh allow-list schema, logs exact canonical outbound bytes and SHA-256 hashes for the **Egress Proof Panel**, buffers metadata in a durable SQLite transactional outbox, and delivers with retry/backoff and heartbeats.
- **Tier 2 — Central Multi-Tenant SaaS (`backend/`)**: Authenticates collectors with server-bound tenant identities, rejects non-allow-listed fields, deduplicates retries idempotently by `(tenant_id, payload_id)`, evaluates 4-state health (`Excellent`, `Good`, `Fair`, `Poor`) with stale-heartbeat downgrading, detects threshold and rolling median/MAD baseline anomalies, correlates related alerts into incidents, and generates explainable recommendations with deterministic evidence scores.
- **Operations Dashboard (`frontend/`)**: Technical, high-signal SRE interface featuring Fleet Overview, Incident Intelligence, Collector Fleet, Egress Proof (paired with the local-only collector inspection endpoint), Reliability Lab, and Architecture & Trust views.

## Repository Structure

```text
aegisops/
  README.md                 # Project overview and quickstart
  AGENTS.md                 # Mandatory agent identification, ownership, and audit rules
  docker-compose.yml        # Isolated two-tier local stack (PostgreSQL, SaaS, Collector, Frontend)
  Makefile                  # Standard build, audit, test, and smoke-test targets
  .env.example              # Environment variable template (synthetic dev placeholders only)
  contracts/                # Versioned JSON Schemas (Draft 2020-12) and OpenAPI 3.1 snapshot
  docs/                     # Architecture, trust boundaries, data policy, ownership, handoffs, runbook
  scripts/                  # Audit automation, contract validation, hooks, smoke & demo scripts
  audit/                    # Append-only engineering activity log (activity.jsonl) & checkpoints
  simulator/                # Shared synthetic telemetry fixtures and 8 judge validation scenarios
  collector/                # Tier 1 Local Collector (Owned by Member 02 — Sherwin)
  backend/                  # Tier 2 SaaS Backend & AIOps (Owned by Member 03 — Praveen)
  frontend/                 # Operations Dashboard (Owned by Member 04 — Darain)
  .github/                  # CODEOWNERS, PR template, and CI workflow
```

## Team Ownership

| Member | Role | Owns | Branch Prefix | AI Tools |
| :--- | :--- | :--- | :--- | :--- |
| **Member 01 — Mishael** | Lead Systems Architect, DevOps & Integration Engineer | `docs/`, `contracts/`, `scripts/`, `.github/`, `simulator/`, root config | `feature/mishael-*` | Antigravity Pro / Codex Plus |
| **Member 02 — Sherwin** | Local Collector, Security & Reliability Engineer | `collector/` | `feature/sherwin-*` | Antigravity Pro / Codex Plus |
| **Member 03 — Praveen** | SaaS Backend & AIOps Intelligence Engineer | `backend/` | `feature/praveen-*` | Antigravity Pro |
| **Member 04 — Darain** | Frontend, UI/UX & Product Experience Engineer | `frontend/` | `feature/darain-*` | Claude Pro |

See [docs/TEAM_OWNERSHIP.md](docs/TEAM_OWNERSHIP.md) and [AGENTS.md](AGENTS.md) before making any changes.

## Quickstart

### 1. Configure local environment

```bash
cp .env.example .env
python scripts/bootstrap/install_hooks.py
```

### 2. Validate contracts and run repository audit

```bash
python scripts/audit/verify_contracts.py
python scripts/audit/check.py --actor mishael --action manual_check
```

### 3. Run module tests

```bash
pytest collector/tests
pytest backend/tests
```

### 4. Start the local two-tier stack (Docker Compose)

```bash
docker compose up --build
```

- **SaaS Backend API**: `http://localhost:8000` (health: `/health`, API: `/api/v1/*`)
- **Local Collector Inspection API (local-only)**: `http://127.0.0.1:8001` (never accessed by SaaS)
- **Frontend Dashboard**: `http://localhost:5173`

> **Security Note**: Local development uses HTTP on loopback (`127.0.0.1`). Production and deployed demonstrations require HTTPS/TLS termination at the regional ingest boundary. See [docs/TRUST_BOUNDARIES.md](docs/TRUST_BOUNDARIES.md) and [docs/KNOWN_LIMITATIONS.md](docs/KNOWN_LIMITATIONS.md).

## Key Documentation

- [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md) — Official CICADA 2026 evaluation criteria and targets
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — Two-tier architecture, network hops, and AIOps design
- [docs/TRUST_BOUNDARIES.md](docs/TRUST_BOUNDARIES.md) — Security controls, isolation, and TLS posture
- [docs/DATA_POLICY.md](docs/DATA_POLICY.md) — Default-deny egress allow-list, redaction, and egress proof
- [docs/API_CONTRACT.md](docs/API_CONTRACT.md) — SaaS and local collector API specification
- [docs/DATABASE_SCHEMA.md](docs/DATABASE_SCHEMA.md) — PostgreSQL (SaaS) and SQLite (Collector) schemas
- [docs/DESIGN_SYSTEM.md](docs/DESIGN_SYSTEM.md) — Anti-AI-slop visual system for the dashboard
- [docs/DEMO_RUNBOOK.md](docs/DEMO_RUNBOOK.md) — Live demo flow and Judge Q&A reference
- [docs/JUDGE_EVIDENCE.md](docs/JUDGE_EVIDENCE.md) — Verification matrix mapped to rubric marks
