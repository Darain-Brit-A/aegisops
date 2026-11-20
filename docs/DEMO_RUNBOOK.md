# AegisOps Live Demo Runbook & Judge Q&A

Tagline: **"Observe everything. Expose nothing."**

## 1. Pre-Demo Checklist (5 Minutes Before Judges Arrive)

1. Confirm Docker stack or local services are healthy (`python scripts/validation/smoke_test.py`).
2. Confirm clean demo state with synthetic Tenant A (`tenant-acme-prod`) and Tenant B (`tenant-globex-prod`) seeded.
3. Open browser tabs at 1440x900 (or projector resolution):
   - Tab 1: **AegisOps Dashboard** (`http://localhost:5173`)
   - Tab 2: **Local Collector Inspection API** (`http://127.0.0.1:8001/local/v1/egress-proof`) — proves local-only raw inspection.
4. Keep terminal ready with `python scripts/demo/run_scenarios.py --list` for on-the-spot judge scenario injection.

> **Security Rule**: Use ONLY synthetic demonstration tokens (e.g., `AEGIS_DEMO_SECRET_TOKEN_9F2A`). Never display real credentials.

---

## 2. 18-Step Live Demonstration Sequence

1. **Open Fleet Overview (`/`)**: Show overall fleet health state, active collectors, environment/region filters, and last telemetry UTC timestamp.
2. **Show Collector Fleet (`/collectors`)**: Highlight live collector heartbeat, version, region (`ap-south-1`), `Excellent`/`Good` state, and zero outbox backlog.
3. **Inject Scenario 1 — Raw Log Containing Synthetic Secret**: Run `python scripts/demo/run_scenarios.py --scenario raw_secret`.
4. **Open Egress Proof Panel (`/egress-proof`)**:
   - Left pane (Tier 1 Local Collector `:8001`): Show original raw event containing synthetic secret `AEGIS_DEMO_SECRET_TOKEN_9F2A`, raw hostname `prod-db-01.internal`, and source IP `10.42.8.19` — highlighted as **LOCAL ONLY**.
   - Right pane (Tier 2 SaaS `:8000`): Show exact canonical outbound JSON containing only allow-listed fields + HMAC pseudonym `src_<hex>`.
5. **Prove Byte-for-Byte Integrity**: Point to matching `payload_id` and `payload_sha256` between local collector proof and SaaS `/api/v1/saas-receipts`.
6. **Prove Strict Schema Rejection**: Show SaaS rejecting a direct injection attempt containing an unapproved field (`raw_log`) with HTTP `422`.
7. **Inject Scenario 3 — Repeated Failed Logins**: Show local security aggregation producing `failed_auth_attempts_count` and `AUTH_FAILURE_BURST` without exporting usernames or IPs.
8. **Inject Scenarios 4, 5 & 6 — CPU Deviation + Memory Pressure + Network Latency Spike**: Trigger baseline anomaly + threshold breach on related sources in `env-blr-dc1`.
9. **Show Health-State Transition**: Show monitored source / fleet transitioning from `Excellent` -> `Fair` -> `Poor` with UTC timestamp and `reason_code`.
10. **Open Incident Intelligence (`/incidents`)**: Show multiple related alerts grouped into **one correlated incident** (noise reduction), with affected pseudonymous sources and correlation rule explanation.
11. **Inspect Explainable Recommendation**: Show contributing `payload_id`s, UTC timestamps, rolling Median/MAD `robust_z_score`, deterministic `evidence_score` with exact formula, probable cause, suggested investigation, and uncertainty note.
12. **Demonstrate Safe Simulated Remediation (Scenario 8)**: Walk through policy check -> operator approval -> immutable audit entry -> rollback plan (explicitly labeled `SIMULATED`).
13. **Trigger Scenario 2 — Forced SaaS Outage**: Stop the `backend` container (`docker compose stop backend`) while the collector keeps receiving events.
14. **Show Local Buffering & Offline Detection**: Open Collector Outbox (`/local/v1/outbox`) showing `buffered_count` increasing durably in SQLite; show offline detection downgrading collector state to `Poor` within 60s.
15. **Restore SaaS Connection**: Run `docker compose start backend`. Show automatic retry backoff draining buffered payloads with preserved `payload_id`s.
16. **Prove Zero Loss & Zero Duplicates (Scenario 7)**: Replay an already-delivered `payload_id` and inject an out-of-order multi-timezone event (`America/New_York` + `Asia/Kolkata`); show `200 duplicate_ignored`, `duplicate_rejected_count` incrementing, and event-time chart ordering remaining uncorrupted.
17. **Open Reliability Lab (`/reliability`) & Architecture & Trust (`/trust`)**: Display actual measured ingest/alert/dashboard latencies, sent vs received ID parity, tenant isolation test evidence (`Tenant A` vs `Tenant B`), and regional routing design.
18. **State Production Limitations Honestly**: Summarize [docs/KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md) transparently.

---

## 3. Concise Answers to Section 7 Judge Questions

- **What stays local vs leaves the collector?** Raw logs, stack traces, passwords/tokens, hostnames, IPs, usernames, and request bodies stay in Tier 1 local SQLite (`raw_events`). Only the strict allow-listed fields in `contracts/metadata.schema.json` leave Tier 1.
- **How is egress enforced?** Default-deny: we construct a brand-new allow-listed object (never copy-and-delete from raw JSON), validate against `additionalProperties: false`, serialize once canonically, and reject violations locally before queueing.
- **How do we know the Egress Proof is authentic?** One canonical serialization function generates the exact UTF-8 bytes stored in `egress_proofs`, hashed into `payload_sha256`, queued in `outbox_queue`, and transmitted over HTTP. SaaS re-hashes received bytes and exposes `/api/v1/saas-receipts` for live hash comparison.
- **How are collectors authenticated & data encrypted?** Each collector uses a unique `X-Collector-Token` hashed and server-bound to `(tenant_id, collector_id, region_id)` on SaaS; mismatched tenant IDs return `403`. Local dev uses loopback HTTP; production/deployed demos terminate HTTPS/TLS 1.3 with `COLLECTOR_TLS_VERIFY=true`.
- **How does tenant isolation work?** Every tenant-owned PostgreSQL table enforces a `tenant_id` foreign key, all APIs derive `tenant_id` from server-validated tokens, every query filters by `tenant_id`, and automated cross-tenant tests verify isolation. DB-level PostgreSQL RLS is our documented next step for production.
- **How do we distinguish real anomalies from normal spikes?** Dual detection: configurable operational thresholds plus rolling Median/MAD robust z-score (`MIN_SAMPLES=8`, explicit zero-MAD handling) so cold starts and noisy outliers do not trigger false alarms.
- **How are alerts correlated & recommendations explained?** Deterministic grouping by `(tenant_id, environment_id, source/dependency, 5-min window)` with explicit `correlation_explanation`, deterministic `evidence_score` formula, contributing `payload_id`s, and stated uncertainty.
- **What happens during SaaS outage & how are duplicates avoided?** Approved canonical bytes + stable UUID `payload_id` are persisted in a durable SQLite transactional outbox before sending. Retries preserve `payload_id` with bounded exponential backoff + jitter. SaaS enforces `UNIQUE(tenant_id, payload_id)` and idempotently acknowledges replays without duplicating records.
- **What prevents unsafe remediation?** Autonomous actions are simulated only behind a policy check, explicit operator approval, audit log, and rollback plan—no real infrastructure mutation occurs.
