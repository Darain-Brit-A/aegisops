import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { POLL_INTERVAL_MS, saasApi } from "../lib/api";
import type { TenantSession } from "../lib/types";
import {
  CopyableId,
  EmptyState,
  ErrorBanner,
  HealthBadge,
  Panel,
  SeverityBadge,
  formatUtcShort,
} from "../components/UiPrimitives";

export function OverviewPage({
  session,
  onObservedLatency,
}: {
  session: TenantSession;
  onObservedLatency: (ms: number) => void;
}) {
  const [envFilter, setEnvFilter] = useState("");

  const overviewQ = useQuery({
    queryKey: ["overview", session.tenantId, envFilter],
    queryFn: async () => {
      const data = await saasApi.getOverview(session.operatorToken, envFilter || undefined);
      if (data.last_telemetry_utc) {
        const diff = Date.now() - Date.parse(data.last_telemetry_utc);
        if (diff >= 0 && diff < 3_600_000) onObservedLatency(diff);
      }
      return data;
    },
    refetchInterval: POLL_INTERVAL_MS,
  });

  const metricsQ = useQuery({
    queryKey: ["metrics", session.tenantId],
    queryFn: () => saasApi.getMetrics(session.operatorToken, undefined, 180),
    refetchInterval: POLL_INTERVAL_MS,
  });

  const resourceSeries = useMemo(() => {
    const pts = metricsQ.data?.points ?? [];
    const byTime = new Map<string, { time: string; cpu?: number; memory?: number; disk?: number }>();
    for (const p of pts) {
      if (
        p.metric_name !== "cpu_usage_percent" &&
        p.metric_name !== "memory_usage_percent" &&
        p.metric_name !== "disk_usage_percent"
      ) {
        continue;
      }
      const key = p.event_time_utc.slice(11, 19);
      const entry = byTime.get(key) ?? { time: key };
      if (p.metric_name === "cpu_usage_percent") entry.cpu = p.metric_value;
      if (p.metric_name === "memory_usage_percent") entry.memory = p.metric_value;
      if (p.metric_name === "disk_usage_percent") entry.disk = p.metric_value;
      byTime.set(key, entry);
    }
    return Array.from(byTime.values()).slice(-40);
  }, [metricsQ.data]);

  const networkSeries = useMemo(() => {
    const pts = metricsQ.data?.points ?? [];
    const byTime = new Map<string, { time: string; latency?: number; loss?: number }>();
    for (const p of pts) {
      if (p.metric_name !== "network_latency_ms" && p.metric_name !== "network_packet_loss_percent") {
        continue;
      }
      const key = p.event_time_utc.slice(11, 19);
      const entry = byTime.get(key) ?? { time: key };
      if (p.metric_name === "network_latency_ms") entry.latency = p.metric_value;
      if (p.metric_name === "network_packet_loss_percent") entry.loss = p.metric_value;
      byTime.set(key, entry);
    }
    return Array.from(byTime.values()).slice(-40);
  }, [metricsQ.data]);

  const ov = overviewQ.data;

  return (
    <>
      <div className="page-header">
        <div>
          <h1 className="page-title">Fleet Overview</h1>
          <p className="page-subtitle">
            Tenant-scoped metadata-only view ordered by UTC event time. Raw telemetry stays inside Tier 1.
          </p>
        </div>
        <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
          <label htmlFor="env-filter" style={{ fontSize: "12px", color: "var(--text-secondary)" }}>
            Environment
          </label>
          <select
            id="env-filter"
            className="select-input mono"
            value={envFilter}
            onChange={(e) => setEnvFilter(e.target.value)}
          >
            <option value="">All environments</option>
            <option value="env-blr-dc1">env-blr-dc1</option>
            <option value="env-fra-cloud1">env-fra-cloud1</option>
          </select>
        </div>
      </div>

      {overviewQ.error && <ErrorBanner message={(overviewQ.error as Error).message} />}

      <div className="grid-4">
        <Panel title="Fleet Health">
          <div>{ov ? <HealthBadge state={ov.fleet_health_state} /> : <span className="mono">Loading…</span>}</div>
          <div className="metric-caption mono">
            Last telemetry: {formatUtcShort(ov?.last_telemetry_utc)}
          </div>
        </Panel>

        <Panel title="Collector Connectivity">
          <div className="metric-value mono">
            {ov ? `${ov.collectors_online} / ${ov.collectors_total}` : "—"}
          </div>
          <div className="metric-caption mono">
            Online {ov?.collectors_online ?? 0} · Stale {ov?.collectors_stale ?? 0} · Offline{" "}
            {ov?.collectors_offline ?? 0}
          </div>
        </Panel>

        <Panel title="Active Incidents">
          <div className="metric-value mono">{ov ? ov.active_incidents_count : "—"}</div>
          <div className="metric-caption mono">
            Security signals: {ov?.security_events_count ?? 0}
          </div>
        </Panel>

        <Panel title="Fields Redacted Locally">
          <div className="metric-value mono" style={{ color: "var(--accent-primary)" }}>
            {ov ? ov.redacted_fields_kept_local_total : "—"}
          </div>
          <div className="metric-caption">
            Sensitive fields stripped in Tier 1 before egress
          </div>
        </Panel>
      </div>

      {ov && (
        <Panel title="Four-State Health Distribution">
          <div style={{ display: "flex", gap: "12px", flexWrap: "wrap", alignItems: "center" }}>
            {(["Excellent", "Good", "Fair", "Poor"] as const).map((state) => (
              <div
                key={state}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                  padding: "8px 12px",
                  background: "var(--bg-elevated)",
                  border: "1px solid var(--border-subtle)",
                  borderRadius: "4px",
                }}
              >
                <HealthBadge state={state} />
                <span className="mono" style={{ fontWeight: 600 }}>
                  {ov.health_distribution[state] ?? 0}
                </span>
              </div>
            ))}
          </div>
        </Panel>
      )}

      <div className="grid-2">
        <Panel
          title="Infrastructure Utilization (%)"
          actions={<span className="metric-caption mono">Ordered by event_time_utc · Source: SaaS API</span>}
        >
          {metricsQ.isLoading ? (
            <EmptyState message="Loading time-series telemetry…" />
          ) : resourceSeries.length === 0 ? (
            <EmptyState message="No infrastructure metadata received yet for this tenant." />
          ) : (
            <div style={{ width: "100%", height: 240 }}>
              <ResponsiveContainer>
                <LineChart data={resourceSeries}>
                  <CartesianGrid stroke="#222c37" strokeDasharray="3 3" />
                  <XAxis dataKey="time" stroke="#94a3b8" fontSize={11} />
                  <YAxis domain={[0, 100]} unit="%" stroke="#94a3b8" fontSize={11} />
                  <Tooltip
                    contentStyle={{
                      background: "#111820",
                      border: "1px solid #374657",
                      fontSize: "12px",
                    }}
                  />
                  <Line type="monotone" dataKey="cpu" name="CPU %" stroke="#4cc9b0" strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="memory" name="Memory %" stroke="#60a5fa" strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="disk" name="Disk %" stroke="#fbbf24" strokeWidth={1.5} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </Panel>

        <Panel
          title="Network Latency (ms) & Packet Loss (%)"
          actions={<span className="metric-caption mono">Ordered by event_time_utc · Source: SaaS API</span>}
        >
          {metricsQ.isLoading ? (
            <EmptyState message="Loading network telemetry…" />
          ) : networkSeries.length === 0 ? (
            <EmptyState message="No network latency or packet loss metadata received yet." />
          ) : (
            <div style={{ width: "100%", height: 240 }}>
              <ResponsiveContainer>
                <LineChart data={networkSeries}>
                  <CartesianGrid stroke="#222c37" strokeDasharray="3 3" />
                  <XAxis dataKey="time" stroke="#94a3b8" fontSize={11} />
                  <YAxis stroke="#94a3b8" fontSize={11} />
                  <Tooltip
                    contentStyle={{
                      background: "#111820",
                      border: "1px solid #374657",
                      fontSize: "12px",
                    }}
                  />
                  <Line type="monotone" dataKey="latency" name="Latency (ms)" stroke="#fbbf24" strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="loss" name="Packet Loss (%)" stroke="#f87171" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </Panel>
      </div>

      <Panel title="Recent Anomaly Activity">
        {!ov || ov.recent_anomalies.length === 0 ? (
          <EmptyState message="No anomalies detected for this tenant." />
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Event Time (UTC)</th>
                <th>Severity</th>
                <th>Metric</th>
                <th>Value</th>
                <th>Detector</th>
                <th>Robust Z</th>
                <th>Pseudonymous Source</th>
              </tr>
            </thead>
            <tbody>
              {ov.recent_anomalies.map((a) => (
                <tr key={a.anomaly_id}>
                  <td className="mono">{formatUtcShort(a.event_time_utc)}</td>
                  <td>
                    <SeverityBadge severity={a.severity} />
                  </td>
                  <td className="mono">{a.metric_name}</td>
                  <td className="mono">{a.metric_value}</td>
                  <td className="mono">{a.detector_method}</td>
                  <td className="mono">{a.robust_z_score !== null ? a.robust_z_score : "N/A"}</td>
                  <td>
                    <CopyableId value={a.source_id} maxChars={18} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>
    </>
  );
}
