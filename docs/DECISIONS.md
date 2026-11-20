# AegisOps Architecture Decision Records (ADRs)

## ADR-001: Modular Monolith SaaS + Independent SQLite Collector
- **Status**: Accepted
- **Context**: 24-hour hackathon with 4 engineers; judges award 90/100 marks to architecture, working prototype, and live demo evidence.
- **Decision**: Build Tier 2 SaaS as a single FastAPI modular monolith backed by PostgreSQL 16, and Tier 1 Collector as an independent Python service backed by local SQLite (WAL mode). No Kubernetes, Kafka, or microservice sprawl.
- **Consequences**: Minimal integration friction, fast reproducible Docker Compose startup, clean network isolation (`saas-internal` vs `ingest-boundary`).

## ADR-002: Default-Deny Allow-List Construction + HMAC-SHA256 Pseudonyms
- **Status**: Accepted
- **Context**: Blacklist-based redaction (copying raw event and deleting `password`) fails silently whenever new secret keys or free-text fields appear.
- **Decision**: Construct every outbound payload from a fresh schema object strictly conforming to `contracts/metadata.schema.json` (`additionalProperties: false`). Replace raw hostnames/IPs with `src_<hmac_sha256(local_secret, raw_id)[:20]>`.
- **Consequences**: Unapproved fields are structurally impossible to serialize or pass Pydantic `extra="forbid"` validation.

## ADR-003: Single Canonical Serialization Function for Egress Proof
- **Status**: Accepted
- **Context**: Judges must trust that the Egress Proof panel displays the exact bytes transmitted over the network, not a reconstructed approximation.
- **Decision**: Serialize validated metadata once via `json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")`. Use those identical bytes for local proof display, SHA-256 hashing, SQLite outbox storage, and HTTPX transmission.
- **Consequences**: SaaS re-hashes received bytes; matching `payload_sha256` proves byte-for-byte fidelity.

## ADR-004: At-Least-Once Transactional Outbox + Idempotent SaaS Deduplication
- **Status**: Accepted
- **Context**: Outage recovery must guarantee zero missing records and zero duplicate accepted records, even across collector restarts.
- **Decision**: Persist approved bytes + UUID `payload_id` in SQLite `outbox_queue` before HTTP send; retry with bounded exponential backoff + jitter; enforce `UNIQUE(tenant_id, payload_id)` in PostgreSQL and return `200 duplicate_ignored` on replay.
- **Consequences**: Honest at-least-once delivery with idempotent acceptance; never falsely claims exactly-once network delivery.

## ADR-005: Robust Median/MAD Anomaly Detection + Deterministic Correlation + Explicit Evidence Score
- **Status**: Accepted
- **Context**: Judges weight explainable AIOps heavily and penalize opaque black-box claims or fabricated confidence scores.
- **Decision**: Combine configurable static thresholds with rolling Median/MAD robust z-score (`MIN_SAMPLES = 8`, explicit zero-MAD handling), deterministic multi-signal correlation rules, and a transparent formula-backed `evidence_score` (0–100).
- **Consequences**: Zero cold-start hallucinations, fast deterministic execution, every incident and recommendation traces directly to `payload_id`s and UTC timestamps.

## ADR-006: Stable 3-Second Polling via TanStack Query Instead of WebSockets
- **Status**: Accepted
- **Context**: Live dashboard updates must meet the <= 10s P95 latency target without brittle socket reconnection bugs during live outage demos.
- **Decision**: Use TanStack Query polling (`3000ms` default) with server-sourced UTC timestamps and explicit browser observation timestamps for Reliability Lab latency tracking.
- **Consequences**: Simple, resilient across backend restarts/outages, easily within the 10s target.

## ADR-007: Application-Enforced Tenant Isolation + Integration Tests (RLS as Roadmap)
- **Status**: Accepted
- **Context**: Multi-tenant separation is mandatory and must be verified live.
- **Decision**: Bind `tenant_id` server-side from authenticated collector/operator tokens, enforce `tenant_id` foreign keys and query filters on every endpoint, and back this with cross-tenant negative integration tests. Document PostgreSQL RLS as a production hardening step rather than claiming it prematurely.
- **Consequences**: Strong, verified isolation within 24 hours with total honesty about production hardening.
