# AegisOps Database Schema Design

AegisOps maintains **two completely separate datastores** across the trust boundary:
1. **Tier 2 PostgreSQL 16 (`backend/`)**: Multi-tenant metadata-only relational store.
2. **Tier 1 Local SQLite (`collector/`)**: Local-only raw telemetry store, egress proof log, and transactional outbox.

---

## Part A — Tier 2 SaaS PostgreSQL Schema (`backend/`)

Every tenant-owned table includes an explicit `tenant_id` foreign key and index. All timestamps use `TIMESTAMPTZ` (UTC).

### 1. `tenants`
- `tenant_id` `VARCHAR(64)` PK
- `name` `VARCHAR(128)` NOT NULL
- `region_id` `VARCHAR(32)` NOT NULL (e.g., `ap-south-1`)
- `created_at_utc` `TIMESTAMPTZ` NOT NULL

### 2. `environments`
- `environment_id` `VARCHAR(64)` PK
- `tenant_id` `VARCHAR(64)` FK -> `tenants.tenant_id` NOT NULL
- `region_id` `VARCHAR(32)` NOT NULL
- `display_label` `VARCHAR(128)` NOT NULL
- `created_at_utc` `TIMESTAMPTZ` NOT NULL
- Unique `(tenant_id, environment_id)`

### 3. `collectors`
- `collector_id` `VARCHAR(64)` PK
- `tenant_id` `VARCHAR(64)` FK -> `tenants.tenant_id` NOT NULL
- `environment_id` `VARCHAR(64)` FK -> `environments.environment_id` NOT NULL
- `region_id` `VARCHAR(32)` NOT NULL
- `token_hash` `VARCHAR(128)` NOT NULL (SHA-256 hash of `X-Collector-Token`)
- `token_version` `INTEGER` DEFAULT 1 NOT NULL (rotation-ready)
- `collector_version` `VARCHAR(32)` NOT NULL
- `config_status` `VARCHAR(32)` DEFAULT `'valid'` NOT NULL
- `policy_version` `VARCHAR(16)` DEFAULT `'1'` NOT NULL
- `health_state` `VARCHAR(16)` DEFAULT `'Good'` NOT NULL
- `connection_state` `VARCHAR(32)` DEFAULT `'online'` NOT NULL
- `last_heartbeat_utc` `TIMESTAMPTZ` NULL
- `last_reconnect_utc` `TIMESTAMPTZ` NULL
- `pending_outbox_count` `INTEGER` DEFAULT 0 NOT NULL
- `retry_count` `INTEGER` DEFAULT 0 NOT NULL
- `last_delivery_status` `VARCHAR(32)` DEFAULT `'idle'` NOT NULL
- `collector_cpu_percent` `DOUBLE PRECISION` NULL
- `collector_memory_mb` `DOUBLE PRECISION` NULL

### 4. `telemetry_events` (Approved Metadata Only)
- `id` `BIGSERIAL` PK
- `tenant_id` `VARCHAR(64)` FK -> `tenants.tenant_id` NOT NULL
- `payload_id` `UUID` NOT NULL
- `collector_id` `VARCHAR(64)` FK -> `collectors.collector_id` NOT NULL
- `environment_id` `VARCHAR(64)` NOT NULL
- `region_id` `VARCHAR(32)` NOT NULL
- `source_id` `VARCHAR(64)` NOT NULL (HMAC pseudonym)
- `event_time_utc` `TIMESTAMPTZ` NOT NULL
- `collected_at_utc` `TIMESTAMPTZ` NULL
- `processed_at_utc` `TIMESTAMPTZ` NULL
- `ingested_at_utc` `TIMESTAMPTZ` NOT NULL
- `source_timezone` `VARCHAR(64)` NOT NULL
- `event_category` `VARCHAR(32)` NOT NULL
- `severity` `VARCHAR(16)` NOT NULL
- `health_state` `VARCHAR(16)` NOT NULL
- `metric_name` `VARCHAR(64)` NOT NULL
- `metric_value` `DOUBLE PRECISION` NOT NULL
- `metric_unit` `VARCHAR(32)` NOT NULL
- `policy_version` `VARCHAR(16)` NOT NULL
- `event_code` `VARCHAR(64)` NOT NULL
- `summary_code` `VARCHAR(64)` NOT NULL
- `signal_count` `INTEGER` DEFAULT 1 NOT NULL
- `redacted_field_count` `INTEGER` DEFAULT 0 NOT NULL
- `local_anomaly_score` `DOUBLE PRECISION` NULL
- `payload_sha256` `VARCHAR(64)` NOT NULL
- `out_of_order` `BOOLEAN` DEFAULT FALSE NOT NULL
- **Idempotency Constraint**: `UNIQUE (tenant_id, payload_id)`
- **Indexes**:
  - `idx_telemetry_tenant_event_time (tenant_id, event_time_utc DESC)`
  - `idx_telemetry_tenant_source_metric (tenant_id, source_id, metric_name, event_time_utc DESC)`

### 5. `collector_heartbeats`
- `id` `BIGSERIAL` PK
- `tenant_id` `VARCHAR(64)` FK -> `tenants.tenant_id` NOT NULL
- `collector_id` `VARCHAR(64)` FK -> `collectors.collector_id` NOT NULL
- `sent_at_utc` `TIMESTAMPTZ` NOT NULL
- `received_at_utc` `TIMESTAMPTZ` NOT NULL
- `pending_outbox_count` `INTEGER` NOT NULL
- `retry_count` `INTEGER` NOT NULL
- `last_delivery_status` `VARCHAR(32)` NOT NULL
- `collector_cpu_percent` `DOUBLE PRECISION` NULL
- `collector_memory_mb` `DOUBLE PRECISION` NULL

### 6. `health_transitions`
- `id` `BIGSERIAL` PK
- `tenant_id` `VARCHAR(64)` FK -> `tenants.tenant_id` NOT NULL
- `entity_type` `VARCHAR(32)` NOT NULL
- `entity_id` `VARCHAR(128)` NOT NULL
- `from_state` `VARCHAR(16)` NULL
- `to_state` `VARCHAR(16)` NOT NULL
- `reason_code` `VARCHAR(64)` NOT NULL
- `explanation` `TEXT` NOT NULL
- `changed_at_utc` `TIMESTAMPTZ` NOT NULL

### 7. `anomalies`
- `anomaly_id` `UUID` PK
- `tenant_id` `VARCHAR(64)` FK -> `tenants.tenant_id` NOT NULL
- `payload_id` `UUID` NOT NULL
- `environment_id` `VARCHAR(64)` NOT NULL
- `source_id` `VARCHAR(64)` NOT NULL
- `event_category` `VARCHAR(32)` NOT NULL
- `metric_name` `VARCHAR(64)` NOT NULL
- `metric_value` `DOUBLE PRECISION` NOT NULL
- `baseline_median` `DOUBLE PRECISION` NULL
- `baseline_mad` `DOUBLE PRECISION` NULL
- `robust_z_score` `DOUBLE PRECISION` NULL
- `detector_method` `VARCHAR(64)` NOT NULL
- `severity` `VARCHAR(16)` NOT NULL
- `event_time_utc` `TIMESTAMPTZ` NOT NULL
- `detected_at_utc` `TIMESTAMPTZ` NOT NULL

### 8. `incidents`
- `incident_id` `UUID` PK
- `tenant_id` `VARCHAR(64)` FK -> `tenants.tenant_id` NOT NULL
- `environment_id` `VARCHAR(64)` NOT NULL
- `region_id` `VARCHAR(32)` NOT NULL
- `title` `VARCHAR(200)` NOT NULL
- `status` `VARCHAR(32)` NOT NULL
- `severity` `VARCHAR(16)` NOT NULL
- `correlation_rule` `VARCHAR(128)` NOT NULL
- `correlation_explanation` `TEXT` NOT NULL
- `probable_cause` `TEXT` NOT NULL
- `uncertainty_note` `TEXT` NOT NULL
- `evidence_score` `DOUBLE PRECISION` NOT NULL
- `evidence_score_formula` `TEXT` NOT NULL
- `first_observed_utc` `TIMESTAMPTZ` NOT NULL
- `last_observed_utc` `TIMESTAMPTZ` NOT NULL
- `alert_created_utc` `TIMESTAMPTZ` NOT NULL

### 9. `incident_evidence`
- `id` `BIGSERIAL` PK
- `tenant_id` `VARCHAR(64)` FK -> `tenants.tenant_id` NOT NULL
- `incident_id` `UUID` FK -> `incidents.incident_id` NOT NULL
- `anomaly_id` `UUID` FK -> `anomalies.anomaly_id` NOT NULL
- `payload_id` `UUID` NOT NULL
- `source_id` `VARCHAR(64)` NOT NULL
- `event_time_utc` `TIMESTAMPTZ` NOT NULL

### 10. `recommendations`
- `recommendation_id` `UUID` PK
- `tenant_id` `VARCHAR(64)` FK -> `tenants.tenant_id` NOT NULL
- `incident_id` `UUID` FK -> `incidents.incident_id` NOT NULL
- `title` `VARCHAR(200)` NOT NULL
- `detector_responsible` `VARCHAR(128)` NOT NULL
- `probable_explanation` `TEXT` NOT NULL
- `suggested_investigation` `TEXT` NOT NULL
- `expected_benefit` `TEXT` NOT NULL
- `risk_or_uncertainty` `TEXT` NOT NULL
- `evidence_strength` `VARCHAR(16)` NOT NULL
- `simulated_remediation_available` `BOOLEAN` DEFAULT TRUE NOT NULL
- `simulated_action_code` `VARCHAR(64)` NULL
- `rollback_plan` `TEXT` NULL
- `created_at_utc` `TIMESTAMPTZ` NOT NULL

### 11. `delivery_acknowledgments` & `audit_events`
- `delivery_acknowledgments`: `(id, tenant_id, collector_id, payload_id, payload_sha256, status, duplicate, accepted_at_utc)` — tracks exact delivered and duplicate-rejected IDs for Reliability Lab.
- `audit_events`: `(id, tenant_id, actor, action, target_id, details_json, created_at_utc)` — immutable record of auth rejections, simulated remediations, and policy approvals.

---

## Part B — Tier 1 Local Collector SQLite Schema (`collector/`)

Stored strictly on the local host/volume (`collector_local.db`) with WAL mode enabled (`PRAGMA journal_mode=WAL;`).

1. **`raw_events`**: `(raw_id TEXT PK, received_at_utc TEXT, adapter_name TEXT, raw_json TEXT, expires_at_utc TEXT)` — purged by local retention job.
2. **`egress_proofs`**: `(proof_id TEXT PK, payload_id TEXT, tenant_id TEXT, collector_id TEXT, policy_version TEXT, event_time_utc TEXT, transmitted_at_utc TEXT, acknowledged_at_utc TEXT, delivery_state TEXT, raw_json TEXT, redacted_fields_json TEXT, outbound_canonical_json TEXT, payload_sha256 TEXT, rejection_reason TEXT)`.
3. **`outbox_queue`**: `(payload_id TEXT PK, payload_bytes BLOB NOT NULL, payload_sha256 TEXT NOT NULL, enqueued_at_utc TEXT NOT NULL, next_attempt_at_utc TEXT NOT NULL, attempt_count INTEGER DEFAULT 0, status TEXT NOT NULL, last_error TEXT, delivered_at_utc TEXT)` — guarantees survival across collector restarts and preserves `payload_id` across retries.
4. **`collector_state`**: `(key TEXT PK, value TEXT, updated_at_utc TEXT)` — tracks `last_reconnect_utc`, connection state, and delivery counters.
