export type HealthState = "Excellent" | "Good" | "Fair" | "Poor";
export type Severity = "info" | "warning" | "high" | "critical";

export interface TenantSession {
  tenantId: string;
  label: string;
  regionId: string;
  operatorToken: string;
}

export interface OverviewResponse {
  tenant_id: string;
  tenant_name: string;
  tenant_region_id: string;
  fleet_health_state: HealthState;
  collectors_total: number;
  collectors_online: number;
  collectors_stale: number;
  collectors_offline: number;
  health_distribution: Record<HealthState, number>;
  active_incidents_count: number;
  security_events_count: number;
  redacted_fields_kept_local_total: number;
  last_telemetry_utc: string | null;
  evaluated_at_utc: string;
  recent_anomalies: Array<{
    anomaly_id: string;
    metric_name: string;
    metric_value: number;
    severity: Severity;
    detector_method: string;
    source_id: string;
    robust_z_score: number | null;
    event_time_utc: string;
  }>;
}

export interface MetricPoint {
  payload_id: string;
  source_id: string;
  environment_id: string;
  event_category: string;
  metric_name: string;
  metric_value: number;
  metric_unit: string;
  severity: Severity;
  health_state: HealthState;
  event_code: string;
  event_time_utc: string;
  ingested_at_utc: string;
  source_timezone: string;
  out_of_order: boolean;
}

export interface MetricsResponse {
  tenant_id: string;
  ordered_by: string;
  count: number;
  points: MetricPoint[];
}

export interface CollectorTransition {
  from_state: HealthState | null;
  to_state: HealthState;
  changed_at_utc: string;
  reason_code: string;
  explanation: string;
}

export interface CollectorRecord {
  collector_id: string;
  tenant_id: string;
  environment_id: string;
  region_id: string;
  collector_version: string;
  config_status: string;
  policy_version: string;
  health_state: HealthState;
  is_stale: boolean;
  reason_code: string;
  explanation: string;
  connection_state: string;
  last_heartbeat_utc: string | null;
  last_reconnect_utc: string | null;
  pending_outbox_count: number;
  retry_count: number;
  last_delivery_status: string;
  collector_cpu_percent: number | null;
  collector_memory_mb: number | null;
  transitions: CollectorTransition[];
}

export interface CollectorsResponse {
  tenant_id: string;
  count: number;
  collectors: CollectorRecord[];
}

export interface ContributingSignal {
  payload_id: string;
  source_id: string;
  event_category: string;
  metric_name: string;
  metric_value: number;
  baseline_median: number | null;
  baseline_mad: number | null;
  robust_z_score: number | null;
  detector_method: string;
  event_time_utc: string;
}

export interface RecommendationRecord {
  recommendation_id: string;
  incident_id: string;
  title: string;
  detector_responsible: string;
  probable_explanation: string;
  suggested_investigation: string;
  expected_benefit: string;
  risk_or_uncertainty: string;
  evidence_strength: "Low" | "Moderate" | "Strong";
  evidence_timestamps_utc: string[];
  simulated_remediation_available: boolean;
  simulated_action_code: string | null;
  rollback_plan: string | null;
}

export interface IncidentRecord {
  incident_id: string;
  tenant_id: string;
  environment_id: string;
  region_id: string;
  title: string;
  status: "open" | "acknowledged" | "mitigated_simulated" | "resolved";
  severity: Severity;
  first_observed_utc: string;
  last_observed_utc: string;
  alert_created_utc: string;
  affected_sources: string[];
  correlation_rule: string;
  correlation_explanation: string;
  probable_cause: string;
  uncertainty_note: string;
  evidence_score: number;
  evidence_score_formula: string;
  contributing_signals: ContributingSignal[];
  recommendations: RecommendationRecord[];
}

export interface IncidentsResponse {
  tenant_id: string;
  count: number;
  incidents: IncidentRecord[];
}

export interface RemediationResponse {
  simulated: boolean;
  warning: string;
  incident_id: string;
  new_incident_status: string;
  policy_check_status: string;
  approved_by: string;
  action_code: string;
  rollback_plan: string;
  audit_event_id: number;
  executed_at_utc: string;
}

export interface SaasReceiptRecord {
  payload_id: string;
  collector_id: string;
  source_id: string;
  policy_version: string;
  event_time_utc: string;
  ingested_at_utc: string;
  payload_sha256: string;
  canonical_json: string;
  payload: Record<string, unknown>;
  out_of_order: boolean;
}

export interface SaasReceiptsResponse {
  tenant_id: string;
  tier: string;
  count: number;
  receipts: SaasReceiptRecord[];
}

export interface LocalEgressProofRecord {
  proof_id: string;
  payload_id: string;
  tenant_id: string;
  collector_id: string;
  policy_version: string;
  event_time_utc: string;
  transmitted_at_utc: string | null;
  acknowledged_at_utc: string | null;
  delivery_state: string;
  raw_event_local_only: Record<string, unknown>;
  redacted_fields: string[];
  outbound_payload: Record<string, unknown> | null;
  outbound_canonical_json: string | null;
  payload_sha256: string | null;
  rejection_reason: string | null;
}

export interface LocalEgressProofResponse {
  tier: string;
  notice: string;
  collector_id: string;
  policy_version: string;
  count: number;
  records: LocalEgressProofRecord[];
}

export interface LocalOutboxResponse {
  collector_id: string;
  tenant_id: string;
  region_id: string;
  saas_ingest_url: string;
  connection_state: string;
  last_delivery_status: string;
  last_reconnect_utc: string | null;
  buffered_count: number;
  delivered_count: number;
  rejected_count: number;
  retry_count: number;
  last_error: string | null;
  recent_delivered_ids: string[];
}

export interface ReliabilityResponse {
  tenant_id: string;
  measurement_note: string;
  total_accepted_events: number;
  duplicate_rejected_count: number;
  out_of_order_count: number;
  collector_offline_detections: number;
  last_reconnect_utc: string | null;
  p50_ingest_latency_ms: number | null;
  p95_ingest_latency_ms: number | null;
  p50_alert_latency_ms: number | null;
  p95_alert_latency_ms: number | null;
  recent_accepted_payload_ids: string[];
}

export interface TrustSummaryResponse {
  product: string;
  tagline: string;
  tenant_id: string;
  assigned_region_id: string;
  active_ingest_region_id: string;
  supported_regions: string[];
  policy_version: string;
  egress_model: string;
  allowlisted_fields: string[];
  tenant_isolation_mode: string;
  database_rls_enabled: boolean;
  transport_posture: string;
  remediation_mode: string;
  heartbeat_stale_seconds: number;
  heartbeat_offline_seconds: number;
}
