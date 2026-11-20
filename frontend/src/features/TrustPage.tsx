import { useQuery } from "@tanstack/react-query";
import { saasApi } from "../lib/api";
import type { TenantSession } from "../lib/types";
import { ErrorBanner, Panel } from "../components/UiPrimitives";

export function TrustPage({ session }: { session: TenantSession }) {
  const trustQ = useQuery({
    queryKey: ["trust-summary", session.tenantId],
    queryFn: () => saasApi.getTrustSummary(session.operatorToken),
  });

  const t = trustQ.data;

  return (
    <>
      <div className="page-header">
        <div>
          <h1 className="page-title">Architecture &amp; Trust</h1>
          <p className="page-subtitle">
            Live verification of implemented two-tier trust boundaries, allow-listed metadata schema, regional routing, and Autonomous Ops safeguards.
          </p>
        </div>
      </div>

      {trustQ.error && <ErrorBanner message={(trustQ.error as Error).message} />}

      <Panel title="Implemented Two-Tier Trust Boundary">
        <div className="grid-2">
          <div className="panel" style={{ background: "var(--bg-elevated)" }}>
            <div className="panel-title">Tier 1 — Customer Environment (Local Collector)</div>
            <ul style={{ margin: 0, paddingLeft: "18px", color: "var(--text-secondary)", fontSize: "13px" }}>
              <li>Collects raw telemetry locally (Simulator / psutil / pluggable Organizer Stream).</li>
              <li>Stores raw logs and secrets strictly in local SQLite under retention controls.</li>
              <li>Scrubs sensitive fields and generates HMAC-SHA256 pseudonymous source IDs.</li>
              <li>Builds a fresh default-deny allow-listed object (additionalProperties=false).</li>
              <li>Canonical UTF-8 JSON bytes shared identically across Egress Proof, SHA-256 hash, SQLite Outbox, and HTTPX transport.</li>
            </ul>
          </div>
          <div className="panel" style={{ background: "var(--bg-elevated)" }}>
            <div className="panel-title">Tier 2 — Central Multi-Tenant SaaS (Metadata-Only)</div>
            <ul style={{ margin: 0, paddingLeft: "18px", color: "var(--text-secondary)", fontSize: "13px" }}>
              <li>Authenticates collectors via X-Collector-Token bound server-side to tenant_id.</li>
              <li>Rejects any unapproved or raw field with HTTP 422 (Pydantic extra=&apos;forbid&apos;).</li>
              <li>Enforces idempotent deduplication on UNIQUE(tenant_id, payload_id).</li>
              <li>Evaluates 4-state health with stale/offline downgrades, rolling Median/MAD anomalies, and deterministic incident correlation.</li>
              <li>Never accesses Tier 1 SQLite or fetches raw customer logs.</li>
            </ul>
          </div>
        </div>
      </Panel>

      {t && (
        <div className="grid-2">
          <Panel title="Active Security & Residency Posture">
            <table className="data-table">
              <tbody>
                <tr>
                  <th>Active Policy Version</th>
                  <td className="mono">v{t.policy_version} ({t.egress_model})</td>
                </tr>
                <tr>
                  <th>Tenant Assigned Region</th>
                  <td className="mono">{t.assigned_region_id} (active ingest: {t.active_ingest_region_id})</td>
                </tr>
                <tr>
                  <th>Supported Regions</th>
                  <td className="mono">{t.supported_regions.join(", ")}</td>
                </tr>
                <tr>
                  <th>Tenant Isolation Mode</th>
                  <td className="mono">{t.tenant_isolation_mode} (DB RLS: {String(t.database_rls_enabled)})</td>
                </tr>
                <tr>
                  <th>Transport Posture</th>
                  <td className="mono">{t.transport_posture}</td>
                </tr>
                <tr>
                  <th>Heartbeat Thresholds</th>
                  <td className="mono">
                    Stale &gt; {t.heartbeat_stale_seconds}s · Offline &gt; {t.heartbeat_offline_seconds}s
                  </td>
                </tr>
                <tr>
                  <th>Autonomous Ops Mode</th>
                  <td className="mono">{t.remediation_mode}</td>
                </tr>
              </tbody>
            </table>
          </Panel>

          <Panel title={`Approved Outbound Metadata Allow-List (${t.allowlisted_fields.length} Fields)`}>
            <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
              {t.allowlisted_fields.map((field) => (
                <span key={field} className="badge badge-excellent mono">
                  {field}
                </span>
              ))}
            </div>
            <div className="metric-caption" style={{ marginTop: "8px" }}>
              Any property outside this exact set (including raw_log, password, api_key, hostname, ip_address, or arbitrary free text) is rejected by both Tier 1 and Tier 2.
            </div>
          </Panel>
        </div>
      )}

      <Panel title="Five-Stage AIOps to Autonomous Ops Roadmap">
        <table className="data-table">
          <thead>
            <tr>
              <th>Stage</th>
              <th>Capability</th>
              <th>Status in AegisOps</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td className="mono">1. Observe</td>
              <td>Collect, redact, allow-list, and visualize fleet health &amp; metrics</td>
              <td><span className="badge badge-excellent">Implemented</span></td>
            </tr>
            <tr>
              <td className="mono">2. Detect</td>
              <td>Static thresholds + Rolling Median/MAD baseline deviations</td>
              <td><span className="badge badge-excellent">Implemented</span></td>
            </tr>
            <tr>
              <td className="mono">3. Correlate</td>
              <td>Deterministic multi-signal incident grouping &amp; noise reduction</td>
              <td><span className="badge badge-excellent">Implemented</span></td>
            </tr>
            <tr>
              <td className="mono">4. Recommend</td>
              <td>Explainable recommendations with deterministic evidence score &amp; uncertainty</td>
              <td><span className="badge badge-excellent">Implemented</span></td>
            </tr>
            <tr>
              <td className="mono">5. Act (Future)</td>
              <td>Policy-checked, human-approved remediation with audit log &amp; rollback plan</td>
              <td><span className="badge badge-fair">Safe Simulation Only</span></td>
            </tr>
          </tbody>
        </table>
      </Panel>
    </>
  );
}
