# AGENTS.md — AegisOps Autonomous Engineering Protocol

Project: **AegisOps** (`aegisops`)
Tagline: **"Observe everything. Expose nothing."**
Event: **CICADA 2026 — 24-Hour Hackathon**

---

## 1. Mandatory Session Identification

At the beginning of **every** new agent session, you MUST:

1. Identify the human team member operating the session (`mishael`, `sherwin`, `praveen`, or `darain`).
2. Read this file (`AGENTS.md`), [docs/TEAM_OWNERSHIP.md](docs/TEAM_OWNERSHIP.md), and the relevant files in `contracts/`.
3. Inspect the current repository state (`git branch`, `git status --short`) before editing anything.
4. Confirm that every file you plan to touch falls within your assigned ownership area.
5. Check [docs/INTEGRATION_STATUS.md](docs/INTEGRATION_STATUS.md) and [docs/TASK_BOARD.md](docs/TASK_BOARD.md).
6. Record task start using the audit script or task journal.

Never assume permission to modify another member's files. Do not begin implementation if the working tree has unexplained uncommitted changes.

---

## 2. Authorized Team Roster & Strict Ownership

| Member ID | Human Name | Role | Owned Paths | Branch Prefix | AI Tools |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `member-01` | **Mishael** | Lead Systems Architect, DevOps & Integration Engineer | `docs/`, `contracts/`, `scripts/`, `.github/`, `simulator/`, `audit/`, `docker-compose.yml`, `Makefile`, `README.md`, `AGENTS.md`, `.env.example`, `.gitignore` | `feature/mishael-*` | Antigravity Pro / Codex Plus |
| `member-02` | **Sherwin** | Local Collector, Security & Reliability Engineer | `collector/` | `feature/sherwin-*` | Antigravity Pro / Codex Plus |
| `member-03` | **Praveen** | SaaS Backend & AIOps Intelligence Engineer | `backend/` | `feature/praveen-*` | Antigravity Pro |
| `member-04` | **Darain** | Frontend, UI/UX & Product Experience Engineer | `frontend/` | `feature/darain-*` | Claude Pro |

Switching AI tools (e.g., Antigravity Pro to Codex Plus) **never** changes module ownership.

### Cross-Boundary Changes
- Only **Mishael** merges into `integration` and `main`.
- Shared contract changes in `contracts/` or `docs/API_CONTRACT.md` require updating `contracts/` schemas, running `python scripts/audit/verify_contracts.py`, and notifying affected owners before merge.
- No teammate may directly edit another member's module without explicit approval and a documented integration audit entry.

---

## 3. Git & Branch Safety Rules

1. **Branches**:
   - `main` — Protected release/demo branch. Receives merges only from `integration` after passing `scripts/audit/integration_gate.py`.
   - `integration` — Shared integration branch managed by Mishael.
   - `feature/<member>-<short-topic>` — All active work happens on member-prefixed feature branches.
2. **Worktree / Clone Isolation**: Each human member works in an independent clone or Git worktree. Never share a single mutable working directory across autonomous agents.
3. **Prohibited Commands**:
   - Never commit directly to `main` or `integration` during feature work.
   - Never run `git push --force` on shared branches (`main`, `integration`).
   - Never discard teammate changes or use destructive `git reset --hard` to hide conflicts.
   - Never commit `.env`, real credentials, raw customer telemetry, or `.db`/`.sqlite` files.
4. **Conventional Commits**:
   - `feat(collector): ...`
   - `fix(backend): ...`
   - `feat(frontend): ...`
   - `docs(architecture): ...`
   - `chore(audit): ...`
   - `test(security): ...`

---

## 4. Non-Negotiable Architecture & Security Invariants

1. **Default-Deny Egress**: Never build outbound payloads by copying a raw event and deleting secret keys. Always construct a fresh object strictly conforming to `contracts/metadata.schema.json` (`additionalProperties: false`).
2. **Authentic Egress Proof**: One canonical serialization function must produce the exact bytes used for (a) egress proof inspection, (b) SHA-256 payload hashing, (c) SQLite outbox persistence, and (d) HTTP transport.
3. **Local Raw Retention**: Raw logs, payloads, and secrets MUST stay in Tier 1 (`collector/`). The SaaS backend (`backend/`) must never connect to the collector's SQLite database or fetch raw events.
4. **Server-Bound Tenant Identity**: Never trust a client-supplied `tenant_id` alone. Bind `tenant_id` from the authenticated collector credential on the SaaS side.
5. **Honest Metrics & Evidence**: Never fabricate benchmark numbers, latency values, test passes, or commit SHAs. If a metric is unmeasured, report `"Not measured"`. Use only `PASS`, `FAIL`, `SKIPPED`, `BLOCKED`, or `NOT APPLICABLE` in audit reports.
6. **UTC Event-Time Ordering**: All timestamps are ISO-8601 UTC (`Z` or `+00:00`) with `source_timezone` retained as metadata. Charts and analytics order by `event_time_utc`, never arrival time.
7. **Idempotent Delivery**: At-least-once transmission from collector outbox + idempotent deduplication at SaaS on `(tenant_id, payload_id)`. Never claim exactly-once network delivery.
8. **Safe Remediation Only**: Autonomous remediation actions MUST be simulated with human approval, policy check, audit record, and rollback plan. Never execute real changes against infrastructure.

---

## 5. Mandatory Audit Gates

Run the automated audit before every commit and push:

```bash
git status --short
git diff --check
python scripts/audit/check.py --actor <mishael|sherwin|praveen|darain> --action pre_commit_audit --task "<task-id>"
```

Every engineering audit output MUST record:
- Human member name
- Assigned role
- AI coding tool used
- Git branch
- Commit SHA (derived from actual `git rev-parse HEAD`)
- Files modified
- Checks executed and actual results (`PASS` / `FAIL` / `SKIPPED` / `BLOCKED` / `NOT APPLICABLE`)
- Integration risks
- Next action

Do not commit or push if any required check reports `FAIL`.

---

## 6. Quota-Aware Handoff Protocol

When pausing work or switching AI tools, update your role handoff file:
- `docs/HANDOFF_MISHAEL.md`
- `docs/HANDOFF_SHERWIN.md`
- `docs/HANDOFF_PRAVEEN.md`
- `docs/HANDOFF_DARAIN.md`

Keep handoffs concise and factual so the next session can resume without rereading prior transcripts.
