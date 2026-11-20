import type {
  CollectorsResponse,
  IncidentsResponse,
  LocalEgressProofResponse,
  LocalOutboxResponse,
  MetricsResponse,
  OverviewResponse,
  ReliabilityResponse,
  RemediationResponse,
  SaasReceiptsResponse,
  TenantSession,
  TrustSummaryResponse,
} from "./types";

export const SAAS_API_BASE =
  import.meta.env.VITE_SAAS_API_BASE_URL || "http://localhost:8000/api/v1";

export const LOCAL_COLLECTOR_BASE =
  import.meta.env.VITE_LOCAL_COLLECTOR_INSPECT_URL || "http://127.0.0.1:8001";

export const POLL_INTERVAL_MS = Number(import.meta.env.VITE_POLL_INTERVAL_MS || "3000");

/**
 * Local development operator session profiles for live multi-tenant isolation demonstration.
 * Tokens match synthetic local dev placeholders in .env.example (never production credentials).
 */
export const DEV_TENANT_SESSIONS: TenantSession[] = [
  {
    tenantId: "tenant-acme-prod",
    label: "Acme Enterprise (ap-south-1)",
    regionId: "ap-south-1",
    operatorToken: "dev-op-token-acme-local-placeholder",
  },
  {
    tenantId: "tenant-globex-prod",
    label: "Globex Cloud (eu-central-1)",
    regionId: "eu-central-1",
    operatorToken: "dev-op-token-globex-local-placeholder",
  },
];

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(url, init);
  if (!resp.ok) {
    let detail = `HTTP ${resp.status}`;
    try {
      const errBody = await resp.json();
      detail = errBody?.detail?.message || errBody?.message || detail;
    } catch {
      // keep status text
    }
    throw new Error(detail);
  }
  return (await resp.json()) as T;
}

export const saasApi = {
  getOverview(token: string, environmentId?: string, regionId?: string): Promise<OverviewResponse> {
    const params = new URLSearchParams();
    if (environmentId) params.set("environment_id", environmentId);
    if (regionId) params.set("region_id", regionId);
    const qs = params.toString() ? `?${params.toString()}` : "";
    return fetchJson(`${SAAS_API_BASE}/overview${qs}`, {
      headers: { "X-Tenant-Token": token },
    });
  },

  getMetrics(token: string, metricName?: string, minutes = 180): Promise<MetricsResponse> {
    const params = new URLSearchParams({ minutes: String(minutes) });
    if (metricName) params.set("metric_name", metricName);
    return fetchJson(`${SAAS_API_BASE}/metrics?${params.toString()}`, {
      headers: { "X-Tenant-Token": token },
    });
  },

  getCollectors(token: string): Promise<CollectorsResponse> {
    return fetchJson(`${SAAS_API_BASE}/collectors`, {
      headers: { "X-Tenant-Token": token },
    });
  },

  getIncidents(token: string, status?: string): Promise<IncidentsResponse> {
    const qs = status ? `?status=${encodeURIComponent(status)}` : "";
    return fetchJson(`${SAAS_API_BASE}/incidents${qs}`, {
      headers: { "X-Tenant-Token": token },
    });
  },

  simulateRemediation(
    token: string,
    incidentId: string,
    operatorId: string,
    justification: string
  ): Promise<RemediationResponse> {
    return fetchJson(`${SAAS_API_BASE}/incidents/${incidentId}/simulate-remediation`, {
      method: "POST",
      headers: {
        "X-Tenant-Token": token,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        operator_id: operatorId,
        justification,
        confirm_simulation: true,
      }),
    });
  },

  getSaasReceipts(token: string, limit = 50): Promise<SaasReceiptsResponse> {
    return fetchJson(`${SAAS_API_BASE}/saas-receipts?limit=${limit}`, {
      headers: { "X-Tenant-Token": token },
    });
  },

  getReliability(token: string): Promise<ReliabilityResponse> {
    return fetchJson(`${SAAS_API_BASE}/reliability`, {
      headers: { "X-Tenant-Token": token },
    });
  },

  getTrustSummary(token: string): Promise<TrustSummaryResponse> {
    return fetchJson(`${SAAS_API_BASE}/architecture/trust-summary`, {
      headers: { "X-Tenant-Token": token },
    });
  },
};

export const localCollectorApi = {
  getEgressProof(limit = 30): Promise<LocalEgressProofResponse> {
    return fetchJson(`${LOCAL_COLLECTOR_BASE}/local/v1/egress-proof?limit=${limit}`);
  },

  getOutbox(): Promise<LocalOutboxResponse> {
    return fetchJson(`${LOCAL_COLLECTOR_BASE}/local/v1/outbox`);
  },

  injectRawEvent(rawEvent: Record<string, unknown>, flush = true): Promise<Record<string, unknown>> {
    return fetchJson(`${LOCAL_COLLECTOR_BASE}/local/v1/inject?flush=${flush}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(rawEvent),
    });
  },

  flushOutbox(): Promise<Record<string, unknown>> {
    return fetchJson(`${LOCAL_COLLECTOR_BASE}/local/v1/flush`, { method: "POST" });
  },
};
