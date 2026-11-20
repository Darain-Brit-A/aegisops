import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { vi } from "vitest";
import App from "../App";
import { HealthBadge, formatLatencyMs } from "../components/UiPrimitives";
import { EgressProofPage } from "../features/EgressProofPage";
import { ReliabilityPage } from "../features/ReliabilityPage";
import { DEV_TENANT_SESSIONS } from "../lib/api";

function renderWithQuery(ui: React.ReactElement) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe("AegisOps Operations Dashboard", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders app shell, branding, and all 6 primary navigation items", () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          tenant_id: "tenant-acme-prod",
          tenant_name: "Acme",
          tenant_region_id: "ap-south-1",
          fleet_health_state: "Excellent",
          collectors_total: 1,
          collectors_online: 1,
          collectors_stale: 0,
          collectors_offline: 0,
          health_distribution: { Excellent: 1, Good: 0, Fair: 0, Poor: 0 },
          active_incidents_count: 0,
          security_events_count: 0,
          redacted_fields_kept_local_total: 4,
          last_telemetry_utc: null,
          evaluated_at_utc: "2026-11-20T09:00:00Z",
          recent_anomalies: [],
          points: [],
        }),
      })
    );

    renderWithQuery(<App />);
    expect(screen.getByText("AegisOps")).toBeInTheDocument();
    expect(screen.getByText("Observe everything. Expose nothing.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Fleet Overview" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Egress Proof" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Incident Intelligence" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Collector Fleet" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reliability Lab" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Architecture & Trust" })).toBeInTheDocument();
  });

  it("renders all four semantic health states with explicit text labels (never color-only)", () => {
    render(
      <div>
        <HealthBadge state="Excellent" />
        <HealthBadge state="Good" />
        <HealthBadge state="Fair" />
        <HealthBadge state="Poor" />
      </div>
    );
    expect(screen.getByText("Excellent")).toBeInTheDocument();
    expect(screen.getByText("Good")).toBeInTheDocument();
    expect(screen.getByText("Fair")).toBeInTheDocument();
    expect(screen.getByText("Poor")).toBeInTheDocument();
  });

  it("displays SHA-256 MATCH VERIFIED when Tier 1 proof matches Tier 2 SaaS receipt", async () => {
    const sharedHash = "a".repeat(64);
    const sharedId = "11111111-2222-4333-8444-555555555555";

    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(async (url: string) => {
        if (url.includes("/local/v1/egress-proof")) {
          return {
            ok: true,
            json: async () => ({
              tier: "tier-1-local-only",
              notice: "Local only",
              collector_id: "col-acme-blr-01",
              policy_version: "1",
              count: 1,
              records: [
                {
                  proof_id: "proof-1",
                  payload_id: sharedId,
                  tenant_id: "tenant-acme-prod",
                  collector_id: "col-acme-blr-01",
                  policy_version: "1",
                  event_time_utc: "2026-11-20T09:00:00Z",
                  transmitted_at_utc: "2026-11-20T09:00:01Z",
                  acknowledged_at_utc: "2026-11-20T09:00:01Z",
                  delivery_state: "delivered",
                  raw_event_local_only: { api_key: "AEGIS_DEMO_SECRET_TOKEN_9F2A" },
                  redacted_fields: ["api_key"],
                  outbound_payload: { payload_id: sharedId, metric_name: "cpu_usage_percent" },
                  outbound_canonical_json: "{}",
                  payload_sha256: sharedHash,
                  rejection_reason: null,
                },
              ],
            }),
          };
        }
        return {
          ok: true,
          json: async () => ({
            tenant_id: "tenant-acme-prod",
            tier: "tier-2-saas-metadata-only",
            count: 1,
            receipts: [
              {
                payload_id: sharedId,
                collector_id: "col-acme-blr-01",
                source_id: "src_a1b2c3d4e5f60718293a",
                policy_version: "1",
                event_time_utc: "2026-11-20T09:00:00Z",
                ingested_at_utc: "2026-11-20T09:00:01Z",
                payload_sha256: sharedHash,
                canonical_json: "{}",
                payload: {},
                out_of_order: false,
              },
            ],
          }),
        };
      })
    );

    renderWithQuery(<EgressProofPage session={DEV_TENANT_SESSIONS[0]} />);
    expect(await screen.findByText("SHA-256 MATCH VERIFIED")).toBeInTheDocument();
    expect(screen.getByText("LOCAL ONLY")).toBeInTheDocument();
  });

  it("honestly displays 'Not measured' for null reliability metrics instead of fake numbers", async () => {
    expect(formatLatencyMs(null)).toBe("Not measured");

    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(async (url: string) => {
        if (url.includes("/local/v1/outbox")) {
          return { ok: false, status: 503, json: async () => ({}) };
        }
        return {
          ok: true,
          json: async () => ({
            tenant_id: "tenant-acme-prod",
            measurement_note: "Real timestamps only",
            total_accepted_events: 0,
            duplicate_rejected_count: 0,
            out_of_order_count: 0,
            collector_offline_detections: 0,
            last_reconnect_utc: null,
            p50_ingest_latency_ms: null,
            p95_ingest_latency_ms: null,
            p50_alert_latency_ms: null,
            p95_alert_latency_ms: null,
            recent_accepted_payload_ids: [],
          }),
        };
      })
    );

    renderWithQuery(
      <ReliabilityPage session={DEV_TENANT_SESSIONS[0]} observedDashboardLatenciesMs={[]} />
    );
    const notMeasured = await screen.findAllByText("Not measured");
    expect(notMeasured.length).toBeGreaterThanOrEqual(2);
  });

  it("switches active tenant session via dropdown", () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ points: [], recent_anomalies: [], health_distribution: {} }),
      })
    );

    renderWithQuery(<App />);
    const select = screen.getByLabelText(/Active Tenant Session/i);
    fireEvent.change(select, { target: { value: "tenant-globex-prod" } });
    expect(screen.getByText("Tenant: tenant-globex-prod")).toBeInTheDocument();
  });
});
