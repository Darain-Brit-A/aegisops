# AegisOps Data Protection & Egress Policy

Policy Version: `1`
Default Posture: **DEFAULT-DENY EGRESS**

## 1. Twelve-Step Local Collector Processing Pipeline

Every incoming telemetry record MUST pass through these stages in order inside Tier 1 (`collector/`):

1. **Ingest & Parse** raw event from configured adapter (`simulator`, `psutil`, or `organizer_stream`).
2. **Persist Raw Locally** into local SQLite `raw_events` table under configurable retention (`COLLECTOR_RAW_RETENTION_HOURS`, default 24h) with periodic purge.
3. **Normalize** timestamps into UTC ISO-8601 (`event_time_utc`), preserving `source_timezone`, and map raw metrics into canonical internal types.
4. **Detect & Scrub Sensitive Fields**: Identify and record names of sensitive fields (secrets, tokens, passwords, private keys, raw log bodies, stack traces, IP addresses, hostnames, emails, usernames, request bodies).
5. **Aggregate / Summarize Locally**: Convert noisy raw events (e.g., repeated failed login lines) into numeric counts (`failed_auth_attempts_count`), controlled `event_code`, and `summary_code`.
6. **Generate Stable Pseudonymous Source ID**: Compute `source_id = "src_" + hmac.new(COLLECTOR_HMAC_SECRET, raw_source_key, sha256).hexdigest()[:20]`. Never use plain unsalted hashes of predictable hostnames/IPs.
7. **Construct Fresh Allow-Listed Object**: Instantiate a brand-new outbound object containing **only** fields defined in `contracts/metadata.schema.json`. **NEVER** copy the raw event dict and pop/delete secret keys.
8. **Validate Against Strict Schema**: Validate with `additionalProperties: false` (Pydantic `extra="forbid"` + JSON Schema). If validation fails, record a `policy_rejected` egress proof with `rejection_reason` and **block transmission**.
9. **Canonical Serialization & Hashing**: Pass the validated object through ONE canonical serialization function:
   ```python
   canonical_json = json.dumps(payload_dict, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
   canonical_bytes = canonical_json.encode("utf-8")
   payload_sha256 = hashlib.sha256(canonical_bytes).hexdigest()
   ```
10. **Record Local Egress Proof**: Persist `raw_event_local_only`, `redacted_fields`, `outbound_canonical_json`, `payload_sha256`, and `delivery_state = "buffered"` in local SQLite `egress_proofs`.
11. **Enqueue Transactional Outbox**: Persist the exact `canonical_bytes` and stable `payload_id` in local SQLite `outbox_queue` before attempting any network call.
12. **Transmit & Record Result**: Send the exact stored `canonical_bytes` over HTTPX with `X-Collector-Token` and update `egress_proofs.delivery_state` (`delivered`, `duplicate_acknowledged`, or `failed_retrying`) only after SaaS durable acknowledgment.

## 2. Field-by-Field Allow-List vs Local-Only Data

### Allowed Outbound Fields (`contracts/metadata.schema.json`)

| Field | Type / Constraint | Purpose |
| :--- | :--- | :--- |
| `schema_version` | `"1.0"` | Contract version enforcement |
| `payload_id` | UUID v4 | Idempotent deduplication across retries |
| `collector_id` | Slug (`col-...`) | Identifies collector health & ownership |
| `tenant_id` | Slug (`tenant-...`) | Cross-checked against server-bound collector credential |
| `environment_id` | Slug (`env-...`) | Environment/site scoping for correlation |
| `region_id` | Region enum (optional) | Regional ingest validation |
| `source_id` | `src_<hex>` (HMAC-SHA256) | Pseudonymous source correlation without exposing hostnames/IPs |
| `event_time_utc` | ISO-8601 UTC | Event-time ordering for charts and anomaly baselines |
| `collected_at_utc` | ISO-8601 UTC (optional) | Latency measurement boundary |
| `processed_at_utc` | ISO-8601 UTC (optional) | Local processing latency measurement |
| `source_timezone` | IANA TZ (e.g. `Asia/Kolkata`) | Global multi-timezone context |
| `event_category` | Controlled enum | `infrastructure`, `network`, `security`, `application`, `collector` |
| `severity` | Controlled enum | `info`, `warning`, `high`, `critical` |
| `health_state` | Controlled enum | `Excellent`, `Good`, `Fair`, `Poor` |
| `metric_name` | Controlled enum | Approved telemetry metric name |
| `metric_value` | Bounded number | Numeric observation or aggregated count |
| `metric_unit` | Controlled enum | `percent`, `ms`, `mbps`, `count`, `ratio`, `score`, `status_code` |
| `policy_version` | Numeric string | Active egress policy version |
| `event_code` | Controlled enum | Structured machine-readable event code |
| `summary_code` | Controlled enum | Structured concise alert context (no arbitrary free text) |
| `signal_count` | Integer >= 1 (optional) | Count of raw events aggregated locally |
| `redacted_field_count` | Integer >= 0 (optional) | Count of sensitive fields kept local |
| `local_anomaly_score` | Number 0..100 (optional) | Local deviation magnitude |

### Strictly Forbidden from Leaving Tier 1 (Examples Retained Locally / Dropped)

- `raw_log`, `message`, `stack_trace`, `exception_detail`
- `password`, `api_key`, `access_token`, `authorization`, `cookie`, `private_key`, `secret`
- `hostname`, `fqdn`, `ip_address`, `source_ip`, `dest_ip`, `mac_address`
- `username`, `user_email`, `account_id`, `session_id`, `request_body`, `sql_query`

## 3. Egress Proof Integrity Guarantee

Because the exact same `canonical_bytes` produced in Step 9 are:
1. Stored in `egress_proofs.outbound_canonical_json`
2. Hashed into `egress_proofs.payload_sha256`
3. Persisted in `outbox_queue.payload_bytes`
4. Transmitted verbatim as the HTTP request body
5. Re-hashed on the SaaS side upon ingestion and returned via `/api/v1/saas-receipts`

A judge can visually compare `payload_id` and `payload_sha256` between the **Local Collector Egress Proof** (`127.0.0.1:8001/local/v1/egress-proof`) and the **SaaS Received Record** (`localhost:8000/api/v1/saas-receipts`) and mathematically verify byte-for-byte identity with zero leaked raw fields.
