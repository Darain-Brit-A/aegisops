# AegisOps Requirements Specification

Source of Truth: `Smart_Observability_Hackathon_Evaluation_Guide_v8.pdf` (TechForcz x Atria Institute of Technology — CICADA 2026 24-Hour Hackathon).

## 1. Official Problem Statement

> "End-to-end, secure AIOps observability delivering autonomous insights across enterprise, data center, cloud, and distributed architectures."

Design and develop a secure, AIOps-driven observability platform using a **two-tier architecture**:
- **Tier 1 (Customer Environment / Local Collector)**: Collects and processes telemetry inside the customer environment, keeps sensitive and raw data local by default, and transmits only approved metadata, summaries, health indicators, and concise alert context.
- **Tier 2 (Central Multi-Tenant SaaS Platform)**: Metadata-only ingestion, strict tenant separation, fleet analytics, anomaly detection, incident correlation, explainable recommendations, and a safe path toward future human-approved Autonomous Ops.

## 2. Official Judging Framework (100 Marks)

| Phase | Weight | Focus | Key Evidence Required |
| :--- | :---: | :--- | :--- |
| **Phase 1: Problem Understanding & Ideation** | **10** | Early ideation | One-page data-flow sketch with Tier 1/Tier 2 trust boundary; exact allow-list vs redacted/dropped fields; realistic 24-hour team plan. |
| **Phase 2: Architecture & Technical Design** | **25** | Design checkpoint | Architecture diagram with labeled trust boundary and every network hop; strict payload schema + allow-list mechanism; outage buffering & idempotency design; tenant isolation approach; global-ready design. |
| **Phase 3: Implementation & Working Prototype** | **35** *(10 for real-time performance & reliability)* | Technical checkpoint | Live side-by-side raw secret (collector) vs redacted metadata (SaaS); measured real-time timestamps; forced SaaS outage + reconnect ID comparison (zero loss, zero duplicates); live **Egress Proof Panel**; 4 health states (`Excellent`, `Good`, `Fair`, `Poor`) with stale-data handling. |
| **Phase 4: Final Demo, Validation & Presentation** | **30** | Final evaluation | End-to-end demo across 8 live injected scenarios; correlated multi-alert incidents; explainable recommendations (weighted higher) with contributing signals and reasoning path; honest production limitations; confident answers to Section 7 judge questions. |

## 3. Mandatory Items for Every Team

1. **Measured real-time targets** computed from actual event timestamps (never fabricated).
2. **Configurable adapter for the organizer-provided simulated telemetry stream** so bursts, latency spikes, and outages can be injected identically across teams.
3. **Egress Proof Panel**: visible log showing exact payload contents before leaving the customer environment.

## 4. Suggested Real-Time Performance Targets (Pending Organizer Confirmation)

| Measure | Suggested Target | Measurement Method |
| :--- | :--- | :--- |
| Collection to dashboard latency | P95 <= 10 seconds | `event_time_utc` vs browser dashboard render timestamp |
| Threshold breach to alert raised | <= 15 seconds | Injected spike `event_time_utc` vs `alert_created_utc` |
| Collector offline detection | <= 60 seconds of last heartbeat | Outage start vs collector status change to `Poor` |
| Post-outage backlog delivery | 100% delivered, 0 lost, 0 duplicates | Sent `payload_id` set vs SaaS accepted `payload_id` set after reconnect |

## 5. Eight Official Live Validation Scenarios (Section 8)

1. **Raw log contains a secret** -> Sensitive content stays local / redacted; SaaS receives allow-listed metadata only.
2. **Collector loses SaaS connectivity** -> Detect outage, buffer approved metadata locally in SQLite outbox, retry with backoff, resume delivery cleanly.
3. **Repeated failed logins** -> Local detection produces security summary / risk indicator without exporting raw authentication logs or usernames/IPs.
4. **Network latency rises** -> Show affected pseudonymous source, severity, event-time trend, and service impact.
5. **CPU or memory deviates from baseline** -> AIOps flags anomaly via threshold + rolling MAD baseline, explains contributing signals, and recommends investigation.
6. **Several alerts relate to one incident** -> Deterministic correlation groups related signals into one incident and reduces alert noise.
7. **Duplicate or out-of-order delivery** -> Placed by `event_time_utc` without corrupting trends; deduplicated idempotently by `(tenant_id, payload_id)`.
8. **Remediation is proposed** -> Policy check, human operator approval, immutable audit record, simulated execution, and rollback plan displayed.

## 6. Six Bonus Challenges (Section 6)

1. Privacy-aware metadata pipeline (allow-listing, redaction, HMAC pseudonymization)
2. Local buffering (SQLite transactional outbox surviving restart)
3. Explainable AIOps (contributing signals, deterministic evidence score, reasoning path)
4. Alert-noise reduction (multi-signal correlation into unified incidents)
5. Safe remediation simulation (approval + policy check + audit + rollback plan)
6. Global-ready delivery (UTC + `source_timezone`, out-of-order handling, idempotent retries, regional ingest abstraction)

## 7. External Dependencies Not Yet Provided

- **Organizer Telemetry Stream Endpoint & Exact Schema**: Not yet distributed by organizers. AegisOps implements a clean `TelemetrySourceAdapter` interface (`simulator` fixture mode + `psutil` host mode + pluggable `organizer_stream` adapter configured via `COLLECTOR_ORGANIZER_STREAM_URL`). Custom fixtures are explicitly labeled as local test fixtures and never claimed to be the official organizer stream.
- **Confirmed Performance Targets**: Targets above remain marked *Suggested (pending organizer confirmation)*.
