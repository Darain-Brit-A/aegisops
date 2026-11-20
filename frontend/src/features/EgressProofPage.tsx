import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Lock, Send, ShieldAlert } from "lucide-react";
import { LOCAL_COLLECTOR_BASE, POLL_INTERVAL_MS, localCollectorApi, saasApi } from "../lib/api";
import type { TenantSession } from "../lib/types";
import { CopyableId, EmptyState, Panel, formatUtcShort } from "../components/UiPrimitives";

export function EgressProofPage({ session }: { session: TenantSession }) {
  const qc = useQueryClient();
  const [selectedPayloadId, setSelectedPayloadId] = useState<string | null>(null);

  const localProofQ = useQuery({
    queryKey: ["local-egress-proof"],
    queryFn: () => localCollectorApi.getEgressProof(30),
    refetchInterval: POLL_INTERVAL_MS,
    retry: false,
  });

  const saasReceiptsQ = useQuery({
    queryKey: ["saas-receipts", session.tenantId],
    queryFn: () => saasApi.getSaasReceipts(session.operatorToken, 50),
    refetchInterval: POLL_INTERVAL_MS,
  });

  const injectSecretMutation = useMutation({
    mutationFn: () =>
      localCollectorApi.injectRawEvent(
        {
          scenario_id: "raw_secret",
          adapter: "live_demo_injector",
          hostname: "prod-payments-db-01.internal",
          ip_address: "10.42.8.19",
          username: "svc_billing",
          password: "SYNTHETIC_DEMO_PASS_01",
          api_key: "AEGIS_DEMO_SECRET_TOKEN_9F2A",
          raw_log:
            "INFO db-sync user=svc_billing api_token=AEGIS_DEMO_SECRET_TOKEN_9F2A password=SYNTHETIC_DEMO_PASS_01",
          source_timezone: "Asia/Kolkata",
          event_time_utc: new Date().toISOString(),
          event_category: "infrastructure",
          metric_name: "cpu_usage_percent",
          metric_value: 48.2,
          metric_unit: "percent",
        },
        true
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["local-egress-proof"] });
      qc.invalidateQueries({ queryKey: ["saas-receipts"] });
    },
  });

  const localRecords = localProofQ.data?.records ?? [];
  const saasReceipts = saasReceiptsQ.data?.receipts ?? [];
  const saasByPayloadId = new Map(saasReceipts.map((r) => [r.payload_id, r]));

  const activeProof =
    localRecords.find((r) => r.payload_id === selectedPayloadId) ?? localRecords[0] ?? null;
  const matchedSaas = activeProof ? saasByPayloadId.get(activeProof.payload_id) ?? null : null;
  const hashVerified =
    Boolean(activeProof?.payload_sha256) &&
    Boolean(matchedSaas?.payload_sha256) &&
    activeProof?.payload_sha256 === matchedSaas?.payload_sha256;

  return (
    <>
      <div className="page-header">
        <div>
          <h1 className="page-title">Egress Proof Panel</h1>
          <p className="page-subtitle">
            Cryptographic side-by-side verification: Tier 1 local raw telemetry vs. exact canonical bytes received by Tier 2 SaaS.
          </p>
        </div>
        <button
          type="button"
          className="btn btn-accent"
          disabled={injectSecretMutation.isPending || Boolean(localProofQ.error)}
          onClick={() => injectSecretMutation.mutate()}
        >
          <Send size={13} aria-hidden="true" />
          <span>{injectSecretMutation.isPending ? "Injecting…" : "Inject Synthetic Secret Event (Local)"}</span>
        </button>
      </div>

      {localProofQ.error && (
        <div className="banner-info">
          <strong>Local Collector Inspection API ({LOCAL_COLLECTOR_BASE}) is not reachable from this browser.</strong>{" "}
          By design, Tier 2 SaaS NEVER fetches or stores raw customer events. Start the Tier 1 collector locally on{" "}
          <span className="mono">127.0.0.1:8001</span> to inspect raw local events side-by-side with SaaS receipts.
        </div>
      )}

      {activeProof && (
        <div className="grid-2">
          <Panel
            title="Tier 1 — Local Collector Raw Event (NEVER Exported)"
            actions={
              <span className="badge badge-poor">
                <Lock size={12} aria-hidden="true" />
                <span>LOCAL ONLY</span>
              </span>
            }
          >
            <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", alignItems: "center" }}>
              <span className="metric-caption">Redacted / Kept Local:</span>
              {activeProof.redacted_fields.length > 0 ? (
                activeProof.redacted_fields.map((field) => (
                  <span key={field} className="badge badge-fair mono">
                    {field}
                  </span>
                ))
              ) : (
                <span className="badge badge-neutral">None</span>
              )}
            </div>
            <pre className="code-block mono">
              {JSON.stringify(activeProof.raw_event_local_only, null, 2)}
            </pre>
            <div className="metric-caption mono">
              Collector: {activeProof.collector_id} · Policy v{activeProof.policy_version} · Event:{" "}
              {formatUtcShort(activeProof.event_time_utc)}
            </div>
          </Panel>

          <Panel
            title="Tier 2 — Exact Canonical Outbound & SaaS Received Record"
            actions={
              hashVerified ? (
                <span className="badge badge-excellent">
                  <CheckCircle2 size={12} aria-hidden="true" />
                  <span>SHA-256 MATCH VERIFIED</span>
                </span>
              ) : activeProof.delivery_state === "policy_rejected" ? (
                <span className="badge badge-poor">
                  <ShieldAlert size={12} aria-hidden="true" />
                  <span>POLICY REJECTED</span>
                </span>
              ) : (
                <span className="badge badge-good mono">{activeProof.delivery_state}</span>
              )
            }
          >
            <div style={{ display: "flex", gap: "10px", flexWrap: "wrap", alignItems: "center" }}>
              <span className="metric-caption">Payload ID:</span>
              <CopyableId value={activeProof.payload_id} maxChars={24} />
              {activeProof.payload_sha256 && (
                <>
                  <span className="metric-caption">SHA-256:</span>
                  <CopyableId value={activeProof.payload_sha256} maxChars={20} />
                </>
              )}
            </div>

            {activeProof.rejection_reason ? (
              <div className="banner-error">
                <strong>Blocked before egress:</strong> {activeProof.rejection_reason}
              </div>
            ) : (
              <pre className="code-block mono">
                {activeProof.outbound_payload
                  ? JSON.stringify(activeProof.outbound_payload, null, 2)
                  : activeProof.outbound_canonical_json || "No outbound bytes"}
              </pre>
            )}

            <div className="metric-caption mono">
              {matchedSaas
                ? `SaaS accepted at ${formatUtcShort(matchedSaas.ingested_at_utc)} · Hash: ${matchedSaas.payload_sha256.slice(0, 16)}…`
                : "Not yet matched in active tenant SaaS receipts (may be buffered or belong to another tenant)."}
            </div>
          </Panel>
        </div>
      )}

      <Panel title="Recent Local Egress Proof Log & SaaS Parity">
        {localRecords.length === 0 && saasReceipts.length === 0 ? (
          <EmptyState message="No egress proof records yet. Inject an event or start the Tier 1 collector." />
        ) : localRecords.length > 0 ? (
          <table className="data-table">
            <thead>
              <tr>
                <th>Event Time (UTC)</th>
                <th>Payload ID</th>
                <th>Delivery State</th>
                <th>Redacted Fields</th>
                <th>Local SHA-256</th>
                <th>SaaS Match</th>
              </tr>
            </thead>
            <tbody>
              {localRecords.map((rec) => {
                const match = saasByPayloadId.get(rec.payload_id);
                const ok = Boolean(match && rec.payload_sha256 && match.payload_sha256 === rec.payload_sha256);
                return (
                  <tr
                    key={rec.proof_id}
                    onClick={() => setSelectedPayloadId(rec.payload_id)}
                    style={{
                      cursor: "pointer",
                      background:
                        activeProof?.payload_id === rec.payload_id ? "var(--bg-elevated)" : undefined,
                    }}
                  >
                    <td className="mono">{formatUtcShort(rec.event_time_utc)}</td>
                    <td className="mono">{rec.payload_id.slice(0, 12)}…</td>
                    <td>
                      <span
                        className={`badge ${
                          rec.delivery_state === "delivered"
                            ? "badge-excellent"
                            : rec.delivery_state === "policy_rejected"
                              ? "badge-poor"
                              : "badge-fair"
                        }`}
                      >
                        {rec.delivery_state}
                      </span>
                    </td>
                    <td className="mono">{rec.redacted_fields.join(", ") || "none"}</td>
                    <td className="mono">{rec.payload_sha256 ? `${rec.payload_sha256.slice(0, 14)}…` : "—"}</td>
                    <td>
                      {ok ? (
                        <span className="badge badge-excellent">Verified</span>
                      ) : (
                        <span className="badge badge-neutral">Pending / Tenant Scope</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Ingested (UTC)</th>
                <th>Payload ID</th>
                <th>Pseudonymous Source</th>
                <th>Policy</th>
                <th>SaaS SHA-256</th>
              </tr>
            </thead>
            <tbody>
              {saasReceipts.map((r) => (
                <tr key={r.payload_id}>
                  <td className="mono">{formatUtcShort(r.ingested_at_utc)}</td>
                  <td>
                    <CopyableId value={r.payload_id} />
                  </td>
                  <td className="mono">{r.source_id}</td>
                  <td className="mono">v{r.policy_version}</td>
                  <td>
                    <CopyableId value={r.payload_sha256} />
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
