import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ShieldCheck } from "lucide-react";
import { POLL_INTERVAL_MS, saasApi } from "../lib/api";
import type { IncidentRecord, RemediationResponse, TenantSession } from "../lib/types";
import {
  CopyableId,
  EmptyState,
  ErrorBanner,
  Panel,
  SeverityBadge,
  formatUtcShort,
} from "../components/UiPrimitives";

export function IncidentsPage({ session }: { session: TenantSession }) {
  const qc = useQueryClient();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [justification, setJustification] = useState(
    "Reviewed correlated metadata signals and MAD baseline evidence; approving safe simulation."
  );
  const [confirmSim, setConfirmSim] = useState(false);
  const [lastSimResult, setLastSimResult] = useState<RemediationResponse | null>(null);

  const incidentsQ = useQuery({
    queryKey: ["incidents", session.tenantId],
    queryFn: () => saasApi.getIncidents(session.operatorToken),
    refetchInterval: POLL_INTERVAL_MS,
  });

  const simMutation = useMutation({
    mutationFn: (incidentId: string) =>
      saasApi.simulateRemediation(session.operatorToken, incidentId, "sre-operator", justification),
    onSuccess: (data) => {
      setLastSimResult(data);
      setConfirmSim(false);
      qc.invalidateQueries({ queryKey: ["incidents", session.tenantId] });
      qc.invalidateQueries({ queryKey: ["overview", session.tenantId] });
    },
  });

  const incidents: IncidentRecord[] = incidentsQ.data?.incidents ?? [];
  const selected = incidents.find((i) => i.incident_id === selectedId) ?? incidents[0] ?? null;

  return (
    <>
      <div className="page-header">
        <div>
          <h1 className="page-title">Incident Intelligence</h1>
          <p className="page-subtitle">
            Deterministic alert correlation, rolling Median/MAD evidence, explainable recommendations, and safe simulated remediation.
          </p>
        </div>
      </div>

      {incidentsQ.error && <ErrorBanner message={(incidentsQ.error as Error).message} />}

      <div className="grid-2">
        <Panel title={`Correlated Incidents (${incidents.length})`}>
          {incidentsQ.isLoading ? (
            <EmptyState message="Loading incidents…" />
          ) : incidents.length === 0 ? (
            <EmptyState message="No correlated incidents for this tenant yet." />
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Severity</th>
                  <th>Title</th>
                  <th>Status</th>
                  <th>Evidence</th>
                  <th>Signals</th>
                </tr>
              </thead>
              <tbody>
                {incidents.map((inc) => (
                  <tr
                    key={inc.incident_id}
                    onClick={() => {
                      setSelectedId(inc.incident_id);
                      setLastSimResult(null);
                    }}
                    style={{
                      cursor: "pointer",
                      background:
                        selected?.incident_id === inc.incident_id ? "var(--bg-elevated)" : undefined,
                    }}
                  >
                    <td>
                      <SeverityBadge severity={inc.severity} />
                    </td>
                    <td>
                      <div style={{ fontWeight: 500 }}>{inc.title}</div>
                      <div className="metric-caption mono">
                        {inc.environment_id} · {formatUtcShort(inc.last_observed_utc)}
                      </div>
                    </td>
                    <td className="mono">{inc.status}</td>
                    <td className="mono">{inc.evidence_score}/100</td>
                    <td className="mono">{inc.contributing_signals.length}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Panel>

        <Panel title="Explainable Incident Analysis">
          {!selected ? (
            <EmptyState message="Select an incident to inspect its correlation reasoning and recommendations." />
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
              <div style={{ display: "flex", gap: "8px", alignItems: "center", flexWrap: "wrap" }}>
                <SeverityBadge severity={selected.severity} />
                <span className="badge badge-neutral mono">{selected.status}</span>
                <span className="badge badge-good mono">Evidence Score: {selected.evidence_score}/100</span>
                <CopyableId value={selected.incident_id} maxChars={18} />
              </div>

              <div>
                <div style={{ fontWeight: 600, fontSize: "15px" }}>{selected.title}</div>
                <div className="metric-caption mono" style={{ marginTop: "4px" }}>
                  Formula: {selected.evidence_score_formula}
                </div>
              </div>

              <div className="panel" style={{ background: "var(--bg-elevated)", padding: "12px" }}>
                <div className="metric-caption">
                  <strong>Correlation Rule ({selected.correlation_rule}):</strong> {selected.correlation_explanation}
                </div>
                <div className="metric-caption">
                  <strong>Probable Cause:</strong> {selected.probable_cause}
                </div>
                <div className="metric-caption">
                  <strong>Uncertainty / Local Boundary:</strong> {selected.uncertainty_note}
                </div>
              </div>

              <div>
                <h3 className="panel-title" style={{ marginBottom: "8px" }}>
                  Contributing Signals ({selected.contributing_signals.length})
                </h3>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Metric</th>
                      <th>Value</th>
                      <th>Detector</th>
                      <th>Median / MAD / Z</th>
                      <th>Event Time (UTC)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {selected.contributing_signals.map((sig) => (
                      <tr key={sig.payload_id}>
                        <td className="mono">{sig.metric_name}</td>
                        <td className="mono">{sig.metric_value}</td>
                        <td className="mono">{sig.detector_method}</td>
                        <td className="mono">
                          {sig.baseline_median !== null
                            ? `${sig.baseline_median} / ${sig.baseline_mad} / z=${sig.robust_z_score}`
                            : "threshold"}
                        </td>
                        <td className="mono">{formatUtcShort(sig.event_time_utc)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {selected.recommendations.map((rec) => (
                <div
                  key={rec.recommendation_id}
                  className="panel"
                  style={{ background: "var(--bg-elevated)", padding: "12px" }}
                >
                  <div className="panel-header">
                    <strong>{rec.title}</strong>
                    <span className="badge badge-excellent">{rec.evidence_strength} Evidence</span>
                  </div>
                  <div className="metric-caption">
                    <strong>Detector:</strong> <span className="mono">{rec.detector_responsible}</span>
                  </div>
                  <div className="metric-caption">
                    <strong>Suggested Investigation:</strong> {rec.suggested_investigation}
                  </div>
                  <div className="metric-caption">
                    <strong>Expected Benefit:</strong> {rec.expected_benefit}
                  </div>
                  <div className="metric-caption">
                    <strong>Risk / Uncertainty:</strong> {rec.risk_or_uncertainty}
                  </div>
                  {rec.rollback_plan && (
                    <div className="metric-caption">
                      <strong>Rollback Plan:</strong> {rec.rollback_plan}
                    </div>
                  )}

                  {rec.simulated_remediation_available && selected.status !== "mitigated_simulated" && (
                    <div
                      style={{
                        borderTop: "1px solid var(--border-subtle)",
                        paddingTop: "10px",
                        display: "flex",
                        flexDirection: "column",
                        gap: "8px",
                      }}
                    >
                      <div className="metric-caption">
                        <strong>Safe Simulated Remediation</strong> (Action:{" "}
                        <span className="mono">{rec.simulated_action_code}</span> — zero real infra changes)
                      </div>
                      <input
                        type="text"
                        className="text-input"
                        value={justification}
                        onChange={(e) => setJustification(e.target.value)}
                        aria-label="Operator approval justification"
                      />
                      <label style={{ display: "flex", gap: "8px", alignItems: "center", fontSize: "12px" }}>
                        <input
                          type="checkbox"
                          checked={confirmSim}
                          onChange={(e) => setConfirmSim(e.target.checked)}
                        />
                        <span>Confirm policy-checked human approval for SIMULATED execution</span>
                      </label>
                      <div>
                        <button
                          type="button"
                          className="btn btn-accent"
                          disabled={!confirmSim || simMutation.isPending}
                          onClick={() => simMutation.mutate(selected.incident_id)}
                        >
                          <ShieldCheck size={13} aria-hidden="true" />
                          <span>
                            {simMutation.isPending ? "Recording Simulation…" : "Approve & Run Simulated Remediation"}
                          </span>
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              ))}

              {lastSimResult && lastSimResult.incident_id === selected.incident_id && (
                <div className="banner-info">
                  <strong>SIMULATED REMEDIATION AUDIT #{lastSimResult.audit_event_id}:</strong>{" "}
                  Policy Check <span className="mono">{lastSimResult.policy_check_status}</span> · Action{" "}
                  <span className="mono">{lastSimResult.action_code}</span> · Rollback:{" "}
                  {lastSimResult.rollback_plan}
                </div>
              )}
            </div>
          )}
        </Panel>
      </div>
    </>
  );
}
