import { useCallback, useState } from "react";
import {
  Activity,
  AlertTriangle,
  Gauge,
  LayoutDashboard,
  Lock,
  Server,
  Shield,
} from "lucide-react";
import { DEV_TENANT_SESSIONS, POLL_INTERVAL_MS } from "./lib/api";
import type { TenantSession } from "./lib/types";
import { OverviewPage } from "./features/OverviewPage";
import { EgressProofPage } from "./features/EgressProofPage";
import { IncidentsPage } from "./features/IncidentsPage";
import { CollectorsPage } from "./features/CollectorsPage";
import { ReliabilityPage } from "./features/ReliabilityPage";
import { TrustPage } from "./features/TrustPage";

type ScreenKey = "overview" | "egress" | "incidents" | "collectors" | "reliability" | "trust";

const NAV_ITEMS: Array<{ key: ScreenKey; label: string; icon: typeof LayoutDashboard }> = [
  { key: "overview", label: "Fleet Overview", icon: LayoutDashboard },
  { key: "egress", label: "Egress Proof", icon: Lock },
  { key: "incidents", label: "Incident Intelligence", icon: AlertTriangle },
  { key: "collectors", label: "Collector Fleet", icon: Server },
  { key: "reliability", label: "Reliability Lab", icon: Gauge },
  { key: "trust", label: "Architecture & Trust", icon: Shield },
];

export default function App() {
  const [screen, setScreen] = useState<ScreenKey>("overview");
  const [session, setSession] = useState<TenantSession>(DEV_TENANT_SESSIONS[0]);
  const [observedLatenciesMs, setObservedLatenciesMs] = useState<number[]>([]);

  const handleObservedLatency = useCallback((ms: number) => {
    setObservedLatenciesMs((prev) => [...prev.slice(-49), ms]);
  }, []);

  return (
    <div className="app-shell">
      <aside className="sidebar" aria-label="Primary navigation">
        <div className="brand-block">
          <div className="brand-title">
            <Activity size={17} color="var(--accent-primary)" aria-hidden="true" />
            <span>AegisOps</span>
          </div>
          <div className="brand-tagline">Observe everything. Expose nothing.</div>
        </div>

        <nav className="nav-list">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const active = screen === item.key;
            return (
              <button
                key={item.key}
                type="button"
                className={`nav-item ${active ? "active" : ""}`}
                aria-current={active ? "page" : undefined}
                onClick={() => setScreen(item.key)}
              >
                <Icon size={15} aria-hidden="true" />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>

        <div className="sidebar-footer">
          <label htmlFor="tenant-switcher" style={{ fontSize: "11px", color: "var(--text-secondary)" }}>
            Active Tenant Session (Demo Isolation)
          </label>
          <select
            id="tenant-switcher"
            className="select-input mono"
            value={session.tenantId}
            onChange={(e) => {
              const found = DEV_TENANT_SESSIONS.find((s) => s.tenantId === e.target.value);
              if (found) setSession(found);
            }}
          >
            {DEV_TENANT_SESSIONS.map((s) => (
              <option key={s.tenantId} value={s.tenantId}>
                {s.label}
              </option>
            ))}
          </select>
          <div className="metric-caption mono">
            Region: {session.regionId} · Poll: {POLL_INTERVAL_MS / 1000}s
          </div>
        </div>
      </aside>

      <div className="main-column">
        <header className="topbar">
          <div className="topbar-meta">
            <span className="badge badge-excellent">Metadata-Only SaaS</span>
            <span className="mono">Tenant: {session.tenantId}</span>
            <span className="mono">Region: {session.regionId}</span>
          </div>
          <div className="topbar-meta mono">
            <span>Tier 1 Raw Data: Local Only</span>
          </div>
        </header>

        <main className="page-content">
          {screen === "overview" && (
            <OverviewPage session={session} onObservedLatency={handleObservedLatency} />
          )}
          {screen === "egress" && <EgressProofPage session={session} />}
          {screen === "incidents" && <IncidentsPage session={session} />}
          {screen === "collectors" && <CollectorsPage session={session} />}
          {screen === "reliability" && (
            <ReliabilityPage
              session={session}
              observedDashboardLatenciesMs={observedLatenciesMs}
            />
          )}
          {screen === "trust" && <TrustPage session={session} />}
        </main>
      </div>
    </div>
  );
}
