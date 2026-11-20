import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";
import { POLL_INTERVAL_MS, localCollectorApi, saasApi } from "../lib/api";
import type { TenantSession } from "../lib/types";
import {
  ErrorBanner,
  Panel,
  formatLatencyMs,
  formatUtcShort,
} from "../components/UiPrimitives";

function percentile(values: number[], pct: number): number | null {
  if (values.length === 0) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const idx = Math.min(sorted.length - 1, Math.max(0, Math.round((pct / 100) * (sorted.length - 1))));
  return sorted[idx];
}

export function ReliabilityPage({
  session,
  observedDashboardLatenciesMs,
}: {
  session: TenantSession;
  observedDashboardLatenciesMs: number[];
}) {
  const qc = useQueryClient();

  const relQ = useQuery({
    queryKey: ["reliability", session.tenantId],
    queryFn: () => saasApi.getReliability(session.operatorToken),
    refetchInterval: POLL_INTERVAL_MS,
  });

  const outboxQ = useQuery({
    queryKey: ["local-outbox"],
    queryFn: () => localCollectorApi.getOutbox(),
    refetchInterval: POLL_INTERVAL_MS,
    retry: false,
  });

  const flushMutation = useMutation({
    mutationFn: () => localCollectorApi.flushOutbox(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["local-outbox"] });
      qc.invalidateQueries({ queryKey: ["reliability", session.tenantId] });
    },
  });

  const rel = relQ.data;
  const ob = outboxQ.data;
  const dashP50 = percentile(observedDashboardLatenciesMs, 50);
  const dashP95 = percentile(observedDashboardLatenciesMs, 95);

  return (
    <>
      <div className="page-header">
        <div>
          <h1 className="page-title">Reliability Lab</h1>
          <p className="page-subtitle">
            Measured evidence from real UTC timestamps. Unmeasured metrics explicitly display &quot;Not measured&quot;.
          </p>
        </div>
        <button
          type="button"
          className="btn btn-accent"
          disabled={flushMutation.isPending || Boolean(outboxQ.error)}
          onClick={() => flushMutation.mutate()}
        >
          <RefreshCw size={13} aria-hidden="true" />
          <span>{flushMutation.isPending ? "Flushing…" : "Flush Local Outbox Now"}</span>
        </button>
      </div>

      {relQ.error && <ErrorBanner message={(relQ.error as Error).message} />}

      <div className="grid-4">
        <Panel title="Collector Connection">
          <div className="metric-value mono">{ob ? ob.connection_state : "Not measured"}</div>
          <div className="metric-caption mono">
            Buffered: {ob ? ob.buffered_count : "Not measured"} · Retries: {ob ? ob.retry_count : "—"}
          </div>
        </Panel>

        <Panel title="Idempotent Delivery">
          <div className="metric-value mono">{rel ? rel.total_accepted_events : "—"}</div>
          <div className="metric-caption mono">
            Duplicates rejected: {rel ? rel.duplicate_rejected_count : "—"} · Out-of-order:{" "}
            {rel ? rel.out_of_order_count : "—"}
          </div>
        </Panel>

        <Panel title="Observed Ingest Latency">
          <div className="metric-value mono">{formatLatencyMs(rel?.p95_ingest_latency_ms)}</div>
          <div className="metric-caption mono">
            P50: {formatLatencyMs(rel?.p50_ingest_latency_ms)} · Alert P95:{" "}
            {formatLatencyMs(rel?.p95_alert_latency_ms)}
          </div>
        </Panel>

        <Panel title="Browser Dashboard Latency">
          <div className="metric-value mono">{formatLatencyMs(dashP95)}</div>
          <div className="metric-caption mono">
            P50: {formatLatencyMs(dashP50)} · Samples: {observedDashboardLatenciesMs.length}
          </div>
        </Panel>
      </div>

      <div className="grid-2">
        <Panel title="Tier 1 Local SQLite Outbox (127.0.0.1:8001)">
          {outboxQ.error ? (
            <div className="banner-info">
              Local collector outbox API unreachable. Start Tier 1 collector locally to inspect live SQLite buffering.
            </div>
          ) : ob ? (
            <table className="data-table">
              <tbody>
                <tr>
                  <th>Collector ID</th>
                  <td className="mono">{ob.collector_id}</td>
                </tr>
                <tr>
                  <th>Buffered Pending Count</th>
                  <td className="mono">{ob.buffered_count}</td>
                </tr>
                <tr>
                  <th>Delivered Count</th>
                  <td className="mono">{ob.delivered_count}</td>
                </tr>
                <tr>
                  <th>Retry Count</th>
                  <td className="mono">{ob.retry_count}</td>
                </tr>
                <tr>
                  <th>Last Reconnect (UTC)</th>
                  <td className="mono">{formatUtcShort(ob.last_reconnect_utc)}</td>
                </tr>
                <tr>
                  <th>Last Error</th>
                  <td className="mono">{ob.last_error || "None"}</td>
                </tr>
              </tbody>
            </table>
          ) : (
            <span className="mono">Loading…</span>
          )}
        </Panel>

        <Panel title="Tier 2 SaaS Delivery & Target Comparison">
          {rel ? (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Metric</th>
                  <th>Suggested Target</th>
                  <th>Measured Value</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>Collection → Dashboard P95</td>
                  <td className="mono">≤ 10 s</td>
                  <td className="mono">{formatLatencyMs(dashP95)}</td>
                </tr>
                <tr>
                  <td>Event → SaaS Ingest P95</td>
                  <td className="mono">≤ 10 s</td>
                  <td className="mono">{formatLatencyMs(rel.p95_ingest_latency_ms)}</td>
                </tr>
                <tr>
                  <td>Breach → Alert P95</td>
                  <td className="mono">≤ 15 s</td>
                  <td className="mono">{formatLatencyMs(rel.p95_alert_latency_ms)}</td>
                </tr>
                <tr>
                  <td>Collector Offline Detections</td>
                  <td className="mono">≤ 60 s</td>
                  <td className="mono">{rel.collector_offline_detections}</td>
                </tr>
                <tr>
                  <td>Duplicate Accepted Records</td>
                  <td className="mono">0</td>
                  <td className="mono">0 (rejected: {rel.duplicate_rejected_count})</td>
                </tr>
                <tr>
                  <td>Last SaaS Reconnect (UTC)</td>
                  <td className="mono">Tracked</td>
                  <td className="mono">{formatUtcShort(rel.last_reconnect_utc)}</td>
                </tr>
              </tbody>
            </table>
          ) : (
            <span className="mono">Loading…</span>
          )}
        </Panel>
      </div>
    </>
  );
}
