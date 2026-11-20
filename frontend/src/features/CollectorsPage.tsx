import { useQuery } from "@tanstack/react-query";
import { POLL_INTERVAL_MS, saasApi } from "../lib/api";
import type { TenantSession } from "../lib/types";
import {
  EmptyState,
  ErrorBanner,
  HealthBadge,
  Panel,
  formatUtcShort,
} from "../components/UiPrimitives";

export function CollectorsPage({ session }: { session: TenantSession }) {
  const collectorsQ = useQuery({
    queryKey: ["collectors", session.tenantId],
    queryFn: () => saasApi.getCollectors(session.operatorToken),
    refetchInterval: POLL_INTERVAL_MS,
  });

  const collectors = collectorsQ.data?.collectors ?? [];

  return (
    <>
      <div className="page-header">
        <div>
          <h1 className="page-title">Collector Fleet</h1>
          <p className="page-subtitle">
            Live Tier 1 collector heartbeats, 4-state health with stale-data downgrading, outbox queue depth, and UTC transition history.
          </p>
        </div>
      </div>

      {collectorsQ.error && <ErrorBanner message={(collectorsQ.error as Error).message} />}

      <Panel title={`Registered Collectors (${collectors.length})`}>
        {collectorsQ.isLoading ? (
          <EmptyState message="Loading collectors…" />
        ) : collectors.length === 0 ? (
          <EmptyState message="No collectors registered for this tenant." />
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Collector ID</th>
                <th>Health</th>
                <th>Connection</th>
                <th>Last Heartbeat (UTC)</th>
                <th>Region / Env</th>
                <th>Version / Policy</th>
                <th>Outbox / Retries</th>
                <th>Resources</th>
              </tr>
            </thead>
            <tbody>
              {collectors.map((c) => (
                <tr key={c.collector_id}>
                  <td>
                    <div className="mono" style={{ fontWeight: 600 }}>
                      {c.collector_id}
                    </div>
                    <div className="metric-caption">{c.explanation}</div>
                  </td>
                  <td>
                    <HealthBadge state={c.health_state} />
                    {c.is_stale && (
                      <div style={{ marginTop: "4px" }}>
                        <span className="badge badge-fair">STALE</span>
                      </div>
                    )}
                  </td>
                  <td className="mono">{c.connection_state}</td>
                  <td className="mono">{formatUtcShort(c.last_heartbeat_utc)}</td>
                  <td className="mono">
                    {c.region_id}
                    <div className="metric-caption">{c.environment_id}</div>
                  </td>
                  <td className="mono">
                    v{c.collector_version}
                    <div className="metric-caption">
                      policy v{c.policy_version} ({c.config_status})
                    </div>
                  </td>
                  <td className="mono">
                    pending: {c.pending_outbox_count}
                    <div className="metric-caption">
                      retries: {c.retry_count} · {c.last_delivery_status}
                    </div>
                  </td>
                  <td className="mono">
                    {c.collector_cpu_percent !== null ? `${c.collector_cpu_percent}% CPU` : "Not measured"}
                    <div className="metric-caption">
                      {c.collector_memory_mb !== null ? `${c.collector_memory_mb} MB` : "—"}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>

      {collectors.map((c) => (
        <Panel key={`${c.collector_id}-hist`} title={`State Transition History — ${c.collector_id}`}>
          {c.transitions.length === 0 ? (
            <EmptyState message="No state transitions recorded yet." />
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Changed At (UTC)</th>
                  <th>Transition</th>
                  <th>Reason Code</th>
                  <th>Explanation</th>
                </tr>
              </thead>
              <tbody>
                {c.transitions.map((t, idx) => (
                  <tr key={`${t.changed_at_utc}-${idx}`}>
                    <td className="mono">{formatUtcShort(t.changed_at_utc)}</td>
                    <td className="mono">
                      {t.from_state ?? "Init"} → {t.to_state}
                    </td>
                    <td className="mono">{t.reason_code}</td>
                    <td>{t.explanation}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Panel>
      ))}
    </>
  );
}
