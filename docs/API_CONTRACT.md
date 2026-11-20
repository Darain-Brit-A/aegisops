# AegisOps API Contract

Machine-readable specification: [contracts/openapi.snapshot.json](../contracts/openapi.snapshot.json)
Strict payload schemas:
- [contracts/metadata.schema.json](../contracts/metadata.schema.json)
- [contracts/heartbeat.schema.json](../contracts/heartbeat.schema.json)
- [contracts/health.schema.json](../contracts/health.schema.json)
- [contracts/incident.schema.json](../contracts/incident.schema.json)
- [contracts/egress_proof.schema.json](../contracts/egress_proof.schema.json)

---

## 1. Authentication Headers

| Caller | Header | Scope |
| :--- | :--- | :--- |
| **Tier 1 Collector -> Tier 2 SaaS** | `X-Collector-Token: <token>` | Server-bound to `(tenant_id, collector_id, region_id)`. Mismatch returns `403`. |
| **Dashboard -> Tier 2 SaaS** | `X-Tenant-Token: <token>` | Server-bound to `(tenant_id, operator_role)`. Missing/invalid returns `401`. |
| **Local Browser -> Tier 1 Collector (`127.0.0.1:8001`)** | None required on loopback dev (CORS restricted to `localhost:5173`) | Local inspection ONLY. SaaS never calls `:8001`. |

## 2. Tier 2 SaaS Ingestion Endpoints (`http://localhost:8000`)

### `POST /api/v1/ingest/telemetry`
- **Auth**: `X-Collector-Token`
- **Body**: Strict JSON matching `contracts/metadata.schema.json` (single object).
- **Behavior**:
  1. Authenticate collector token -> resolve `(auth_tenant_id, auth_collector_id, auth_region_id)`.
  2. Reject with `403` if payload `tenant_id != auth_tenant_id` or `collector_id != auth_collector_id` (or region mismatch if supplied).
  3. Validate strictly (`extra="forbid"`) -> reject unknown/raw fields with `422`.
  4. Compute `payload_sha256` over canonical JSON of received body.
  5. Check `UNIQUE(tenant_id, payload_id)`:
     - If already accepted: increment `duplicate_rejected_count`, return `200 OK` with `{"status": "duplicate_ignored", "duplicate": true, ...}` (idempotent).
     - If new: persist event with `ingested_at_utc`, flag `out_of_order` if `event_time_utc` is older than latest seen event for `(tenant_id, source_id, metric_name)`, run health/anomaly/correlation pipeline, return `201 Created` with `IngestAckResponse`.

### `POST /api/v1/ingest/heartbeat`
- **Auth**: `X-Collector-Token`
- **Body**: Strict JSON matching `contracts/heartbeat.schema.json`.
- **Response (`200 OK`)**: Updates `last_heartbeat_utc`, `pending_outbox_count`, `retry_count`, `collector_version`, `config_status`, resource metrics, and recalculates collector health state.

## 3. Tier 2 SaaS Dashboard Read & Action Endpoints (`http://localhost:8000`)

All endpoints below require `X-Tenant-Token` and return data strictly scoped to the authenticated tenant. Frontend polls every **3 seconds** (configurable via `VITE_POLL_INTERVAL_MS`).

- `GET /health` -> `{"status": "ok", "service": "aegisops-backend", "region_id": "ap-south-1", "utc_time": "..."}`
- `GET /api/v1/overview?environment_id=&region_id=` -> Overall fleet `health_state`, health distribution counts (`Excellent`, `Good`, `Fair`, `Poor`), collector online/stale/offline counts, active incident count, recent anomalies, security event summary, `last_telemetry_utc`.
- `GET /api/v1/metrics?metric_name=&environment_id=&source_id=&minutes=60` -> Time-series points ordered strictly `ORDER BY event_time_utc ASC`, including `event_time_utc`, `ingested_at_utc`, `source_timezone`, `metric_value`, `out_of_order`.
- `GET /api/v1/collectors` -> List of collectors with `collector_id`, `environment_id`, `region_id`, `health_state`, `is_stale`, `connection_state`, `last_heartbeat_utc`, `collector_version`, `config_status`, `pending_outbox_count`, `retry_count`, `last_delivery_status`, `collector_cpu_percent`, `collector_memory_mb`, and `transitions`.
- `GET /api/v1/incidents?status=&severity=` -> List of correlated incidents matching `contracts/incident.schema.json`.
- `GET /api/v1/incidents/{incident_id}` -> Single incident with full contributing signals, timeline, and recommendations (`404` if owned by another tenant).
- `POST /api/v1/incidents/{incident_id}/simulate-remediation` -> Body: `{"operator_id": "...", "justification": "...", "confirm_simulation": true}`. Runs policy check, records immutable audit entry, transitions incident status to `mitigated_simulated`, returns simulated execution result + explicit rollback plan.
- `GET /api/v1/saas-receipts?limit=50` -> Recent approved metadata payloads received by SaaS (`payload_id`, `payload_sha256`, `event_time_utc`, `ingested_at_utc`, `payload_json`) so the Egress Proof panel can verify hash parity side-by-side with the local collector.
- `GET /api/v1/reliability` -> Measured metrics: `total_accepted`, `duplicate_rejected_count`, `out_of_order_count`, `p50_ingest_latency_ms`, `p95_ingest_latency_ms`, `p50_alert_latency_ms`, `p95_alert_latency_ms`, `collector_offline_detections`, `last_reconnect_utc`, plus explicit `null` for unmeasured metrics (never fabricated).
- `GET /api/v1/architecture/trust-summary` -> Returns active `policy_version`, allow-listed field names, `region_id`, `allowed_regions`, tenant isolation mode (`application_enforced_with_tests`), and transport security posture.

## 4. Tier 1 Local Collector Inspection Endpoints (`http://127.0.0.1:8001` — Local-Only)

- `GET /health` -> `{"status": "ok", "service": "aegisops-collector", "collector_id": "..."}`
- `GET /local/v1/egress-proof?limit=50` -> Returns local proof records conforming to `contracts/egress_proof.schema.json` (contains `raw_event_local_only`, `redacted_fields`, `outbound_canonical_json`, `payload_sha256`, `delivery_state`, `rejection_reason`).
- `GET /local/v1/outbox` -> Returns local SQLite outbox metrics: `connection_state`, `buffered_count`, `delivered_count`, `retry_count`, `last_error`, `last_reconnect_utc`, `recent_payload_ids`.
- `POST /local/v1/inject` -> Accepts a synthetic raw telemetry JSON object locally for live judge demonstrations and feeds it directly into the Tier 1 pipeline.

## 5. Standard Error Shape

All `4xx`/`5xx` API errors return:
```json
{
  "error_code": "SCHEMA_VIOLATION",
  "message": "Extra inputs are not permitted",
  "details": {}
}
```
