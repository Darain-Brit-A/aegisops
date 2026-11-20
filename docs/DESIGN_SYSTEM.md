# AegisOps Design System & Anti-AI-Slop Standard

Owner: **Member 04 — Darain** (Frontend, UI/UX & Product Experience Engineer, Claude Pro)

> **Reference Honesty Note**: The master specification references `https://killallaislop.com`. That website was **not** directly browsed during Member 01's architecture setup; Darain may inspect it when accessible and refine details without inventing unverified guidance. All rules below are binding baseline standards.

---

## 1. Visual Direction

AegisOps must look like a **deliberate, calm, high-precision enterprise SRE & security operations console** — comparable to disciplined developer observability tools, never a generic AI-generated marketing dashboard.

### Forbidden "AI Slop" Patterns
- Purple/magenta gradient backgrounds or glowing neon halos
- Glassmorphism (`backdrop-blur`) on every card
- Floating decorative blobs, oversized hero banners, or marketing fluff
- Emoji used as primary navigation icons (use crisp Lucide icons with text labels)
- Identical repetitive KPI cards with no visual hierarchy
- Oversized border radii (`rounded-3xl`) or heavy drop shadows
- Fabricated metrics, placeholder sparklines, or decorative charts without axes/units
- Color-only status indicators (every health state & severity MUST pair color + text label + distinct icon/shape)

## 2. Design Tokens (`frontend/src/styles/tokens.css`)

```css
:root {
  /* Neutrals */
  --bg-canvas: #0B0F14;
  --bg-surface: #111820;
  --bg-elevated: #17212B;
  --border-subtle: #27313D;
  --border-strong: #374657;

  /* Text (WCAG AA compliant on dark surfaces) */
  --text-primary: #E8EDF2;
  --text-secondary: #94A3B8;
  --text-muted: #64748B;

  /* Cool Technical Accent */
  --accent-primary: #4CC9B0;
  --accent-muted: rgba(76, 201, 176, 0.14);

  /* Semantic Health & Severity (Never used without text/icon) */
  --status-excellent: #34D399;   /* Excellent / Healthy */
  --status-good: #60A5FA;        /* Good / Informational */
  --status-fair: #FBBF24;        /* Fair / Warning */
  --status-poor: #F87171;        /* Poor / Critical */
}
```

## 3. Typography

Use at most **two font families**:
1. **Interface Sans**: `'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif`
2. **Technical Mono**: `'JetBrains Mono', 'Cascadia Code', ui-monospace, SFMono-Regular, monospace`

Always use **monospaced + `font-variant-numeric: tabular-nums`** for:
- UTC timestamps & latency values (`ms`, `s`)
- `payload_id`, `collector_id`, `source_id`, `incident_id`, `payload_sha256`
- Exact outbound JSON in the Egress Proof panel
- Numeric metric readouts and table columns

## 4. Six Core Screens (Priority Order)

1. **Fleet Overview (`/`)**: Overall 4-state health banner, collector connectivity summary, active incidents count, 4-state distribution bar, environment & region filters, event-time ordered Recharts metric series (CPU/Memory/Latency/Packet Loss), security summary, last successful update UTC.
2. **Egress Proof (`/egress-proof`)** *(Hero Differentiator)*: Clear two-column boundary split:
   - **Left (Tier 1 Local Collector `127.0.0.1:8001` — Local Only)**: Original raw event with highlighted local-only sensitive fields and explicit "NEVER TRANSMITTED" badge.
   - **Right (Tier 2 SaaS Received Metadata `localhost:8000`)**: Exact canonical outbound JSON, `payload_id`, `policy_version`, `payload_sha256` parity badge (`HASH MATCH VERIFIED`), delivery state, or policy rejection reason.
   - If the local collector endpoint is unreachable, show a clear, honest banner explaining that raw events are local-only and cannot be fetched from SaaS.
3. **Incident Intelligence (`/incidents`)**: Filterable active/resolved incidents, severity + deterministic `evidence_score` (with tooltip/caption showing exact formula), affected pseudonymous sources, correlation explanation, contributing signals table, explainable recommendation card, and safe **Simulated Remediation** approval workflow (policy check -> operator confirmation -> audit receipt + rollback plan, clearly badged `SIMULATED`).
4. **Collector Fleet (`/collectors`)**: Collector table with health state, stale indicator, last heartbeat age, version, config status, region, CPU/RAM when available, connection state, pending outbox queue count, last delivery result, and state transition history drawer.
5. **Reliability Lab (`/reliability`)**: Live measured evidence table — connection state, buffered metadata count, retry count, delivered IDs, duplicate rejections, out-of-order count, P50/P95 observed ingest & browser render latencies, last reconnect UTC. Display `"Not measured"` whenever a value is `null`.
6. **Architecture & Trust (`/trust`)**: Live visual summary of Tier 1 -> Trust Boundary -> Tier 2 pipeline, active allow-listed schema fields from `/api/v1/architecture/trust-summary`, regional routing, tenant isolation posture, and 5-stage Autonomous Ops roadmap.

## 5. Chart, State & Accessibility Standards

- Every chart MUST display: meaningful title, explicit units, time window, data source (`SaaS API`), loading skeleton, intentional empty state, and recoverable error state.
- Stable container heights (no layout jump during 3s polling).
- Keyboard-accessible navigation and visible focus rings (`2px solid var(--accent-primary)`).
- Copy-to-clipboard button on `payload_id`, `payload_sha256`, and `incident_id`.

## 6. Mandatory 10-Point Anti-Slop Audit

Before marking any screen complete, Darain must verify:
1. Does it avoid generic AI dashboard tropes?
2. Are grids, borders, and tabular numbers aligned precisely?
3. Is spacing consistent (`4px`/`8px` scale)?
4. Is typography disciplined (max 2 fonts, mono for technical values)?
5. Are chart axes, units, and legends legible and meaningful?
6. Are all colors semantically justified?
7. Is visual hierarchy clear at 1440x900 and 1280x720 demo projector resolution?
8. Are all decorative distractions removed?
9. Are loading, empty, and error states honest and helpful?
10. Can a judge or SRE verify privacy proof and incident reasoning within 10 seconds?
