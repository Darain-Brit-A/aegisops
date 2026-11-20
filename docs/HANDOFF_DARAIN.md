# Handoff Guide — Member 04 (Darain): Frontend, UI/UX & Product Experience

- **Human Member**: Darain
- **Role**: Frontend, UI/UX & Product Experience Engineer
- **Owned Directory**: `frontend/` (EXCLUSIVE — do not edit `collector/`, `backend/`, or `contracts/` directly)
- **Branch Prefix**: `feature/darain-<short-topic>` (branch from `integration`)
- **AI Tool**: Claude Pro

## 1. Required Reading Before First Edit
1. `AGENTS.md`
2. `docs/TEAM_OWNERSHIP.md`
3. `docs/DESIGN_SYSTEM.md` (binding anti-AI-slop rules, color tokens, typography, 10-point audit)
4. `docs/API_CONTRACT.md` & `contracts/openapi.snapshot.json`
5. `contracts/health.schema.json`, `contracts/incident.schema.json`, `contracts/egress_proof.schema.json`
6. Optional: inspect `https://killallaislop.com` if accessible in your environment (never invent unverified guidance if unreachable).

## 2. What Is Already Scaffolded in `frontend/`
- `frontend/package.json` (React 18, TypeScript, Vite, Tailwind CSS, TanStack Query, React Router, Recharts, Lucide, Zod, Vitest, React Testing Library)
- `frontend/vite.config.ts`, `frontend/tsconfig.json`, `frontend/index.html`, `frontend/Dockerfile`
- `frontend/src/styles/tokens.css` (starting dark neutral tokens + semantic health colors)
- `frontend/src/main.tsx`, `frontend/src/App.tsx`, `frontend/src/tests/smoke.test.tsx`

## 3. Your Immediate Implementation Checklist (Priority Order)

1. **Typed API Layer & Polling (`frontend/src/lib/`, `frontend/src/hooks/`)**:
   - Strict TypeScript types + Zod schemas matching `contracts/openapi.snapshot.json`.
   - Separate clients:
     - `saasClient` (`VITE_SAAS_API_BASE_URL`, sends `X-Tenant-Token` from operator session selector — never hardcode real secrets; allow switching between dev Tenant A and Tenant B in UI to prove tenant isolation live!).
     - `localCollectorClient` (`VITE_LOCAL_COLLECTOR_INSPECT_URL` = `http://127.0.0.1:8001` ONLY for Egress Proof & Local Outbox).
   - TanStack Query hooks polling every `VITE_POLL_INTERVAL_MS` (default `3000ms`), recording browser observation timestamp when new payloads arrive for honest Reliability Lab render latency.
2. **App Shell (`frontend/src/app/`, `frontend/src/components/`)**:
   - Crisp left rail navigation (Lucide icons + labels, no emoji): Overview, Egress Proof, Incidents, Collector Fleet, Reliability Lab, Architecture & Trust.
   - Top status bar: Active Tenant badge, Region selector, live polling indicator, last successful sync UTC (monospaced).
   - Reusable `HealthBadge` (`Excellent`, `Good`, `Fair`, `Poor` — always color + text + distinct icon), `CopyableId`, `LoadingSkeleton`, `ErrorBanner`, `EmptyState`.
3. **Six Core Screens (`frontend/src/features/`)**:
   - **Fleet Overview (`/`)**: Overall fleet health, collector online/stale/offline counts, 4-state distribution, active incidents summary, Recharts event-time charts (CPU, Memory, Latency, Packet Loss with units, time range, source label, stable heights), security summary.
   - **Egress Proof (`/egress-proof`)** *(Hero Screen)*: Two-column Tier 1 Local (`:8001`) vs Tier 2 SaaS (`:8000/api/v1/saas-receipts`) comparison showing local-only raw event with redacted field badges on left, exact canonical outbound JSON + `payload_sha256` match badge on right, plus honest fallback banner if local `:8001` is disconnected.
   - **Incident Intelligence (`/incidents`)**: Correlated incidents list + detail view showing severity, deterministic `evidence_score` + formula, correlation explanation, contributing signals table, explainable recommendation card, and safe **Simulated Remediation** approval dialog (policy check + confirmation + audit record + rollback plan, badged `SIMULATED`).
   - **Collector Fleet (`/collectors`)**: Collector inventory table, staleness flags, heartbeat age, version, config status, outbox depth, resource usage, and transition history drawer.
   - **Reliability Lab (`/reliability`)**: Real measured metrics from `/api/v1/reliability` + `/local/v1/outbox` + browser-observed dashboard render latency. Always display `"Not measured"` for `null` fields — zero fake numbers.
   - **Architecture & Trust (`/trust`)**: Live data-boundary diagram, active allow-list fields from `/api/v1/architecture/trust-summary`, regional residency & tenant isolation explanation, 5-stage Autonomous Ops roadmap.
4. **Tests & Anti-Slop Audit (`frontend/src/tests/`)**:
   - Unit tests for API response rendering, loading/error states, 4-state health indicators, incident explanation details, and Egress Proof hash parity view.
   - Complete the 10-point Anti-Slop Audit in `docs/DESIGN_SYSTEM.md` before PR.

## 4. Git & Audit Workflow
```bash
git checkout integration && git pull
git checkout -b feature/darain-frontend-core
cd frontend && npm install && npm run build && npm test -- --run
cd ..
python scripts/audit/check.py --actor darain --action pre_commit_audit --task TASK-301
git add frontend/ && git commit -m "feat(frontend): build operations shell and fleet overview"
```
