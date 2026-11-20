import { useState, type ReactNode } from "react";
import {
  AlertOctagon,
  AlertTriangle,
  Check,
  CheckCircle2,
  Copy,
  Info,
} from "lucide-react";
import type { HealthState, Severity } from "../lib/types";

export function HealthBadge({ state }: { state: HealthState }) {
  const map: Record<HealthState, { cls: string; icon: ReactNode }> = {
    Excellent: { cls: "badge-excellent", icon: <CheckCircle2 size={13} aria-hidden="true" /> },
    Good: { cls: "badge-good", icon: <Info size={13} aria-hidden="true" /> },
    Fair: { cls: "badge-fair", icon: <AlertTriangle size={13} aria-hidden="true" /> },
    Poor: { cls: "badge-poor", icon: <AlertOctagon size={13} aria-hidden="true" /> },
  };
  const cfg = map[state] ?? map.Good;
  return (
    <span className={`badge ${cfg.cls}`} role="status">
      {cfg.icon}
      <span>{state}</span>
    </span>
  );
}

export function SeverityBadge({ severity }: { severity: Severity }) {
  const cls =
    severity === "critical"
      ? "badge-poor"
      : severity === "high" || severity === "warning"
        ? "badge-fair"
        : "badge-good";
  return <span className={`badge ${cls}`}>{severity.toUpperCase()}</span>;
}

export function CopyableId({ value, maxChars = 16 }: { value: string; maxChars?: number }) {
  const [copied, setCopied] = useState(false);
  const short = value.length > maxChars ? `${value.slice(0, maxChars)}…` : value;

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 1400);
    } catch {
      // Clipboard API unavailable in non-secure test contexts
    }
  }

  return (
    <button
      type="button"
      className="copy-chip mono"
      onClick={handleCopy}
      title={`Copy ${value}`}
      aria-label={`Copy identifier ${value}`}
    >
      <span>{short}</span>
      {copied ? <Check size={11} aria-hidden="true" /> : <Copy size={11} aria-hidden="true" />}
    </button>
  );
}

export function Panel({
  title,
  actions,
  children,
}: {
  title: string;
  actions?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="panel">
      <div className="panel-header">
        <h2 className="panel-title">{title}</h2>
        {actions}
      </div>
      {children}
    </section>
  );
}

export function ErrorBanner({ message }: { message: string }) {
  return (
    <div className="banner-error" role="alert">
      <strong>API Error:</strong> {message}
    </div>
  );
}

export function EmptyState({ message }: { message: string }) {
  return (
    <div style={{ padding: "20px 12px", color: "var(--text-secondary)", fontSize: "13px" }}>
      {message}
    </div>
  );
}

export function formatUtcShort(iso: string | null | undefined): string {
  if (!iso) return "Not observed";
  return iso.replace("T", " ").replace(/\.\d+Z$/, "Z");
}

export function formatLatencyMs(ms: number | null | undefined): string {
  if (ms === null || ms === undefined || Number.isNaN(ms)) return "Not measured";
  if (ms >= 1000) return `${(ms / 1000).toFixed(2)} s`;
  return `${ms.toFixed(1)} ms`;
}
