# AegisOps Team Ownership & Collaboration Matrix

Project: **AegisOps** (`aegisops`) — *"Observe everything. Expose nothing."*

## 1. Authorized Team Members

| Member ID | Human Name | Role | Owned Paths | Branch Prefix | AI Tools |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **MEMBER 01** | **Mishael** | Lead Systems Architect, DevOps & Integration Engineer | `docs/`, `contracts/`, `scripts/`, `.github/`, `simulator/`, `audit/`, `docker-compose.yml`, `Makefile`, `README.md`, `AGENTS.md`, `.env.example`, `.gitignore` | `feature/mishael-*` | Antigravity Pro / Codex Plus |
| **MEMBER 02** | **Sherwin** | Local Collector, Security & Reliability Engineer | `collector/` | `feature/sherwin-*` | Antigravity Pro / Codex Plus |
| **MEMBER 03** | **Praveen** | SaaS Backend & AIOps Intelligence Engineer | `backend/` | `feature/praveen-*` | Antigravity Pro |
| **MEMBER 04** | **Darain** | Frontend, UI/UX & Product Experience Engineer | `frontend/` | `feature/darain-*` | Claude Pro |

## 2. Ownership Enforcement Rules

1. **Strict Single-Owner Domains**: No two members independently edit the same module. Automated ownership verification runs locally via `python scripts/audit/check_ownership.py --actor <name>` and remotely in GitHub Actions on every PR.
2. **Tool Rotation Does Not Change Ownership**: When Mishael or Sherwin transitions from Antigravity Pro to Codex Plus, their owned files and branch prefix stay identical.
3. **Contract Change Protocol**:
   - Any change to `contracts/*.json` or `docs/API_CONTRACT.md` is coordinated through **Mishael**.
   - `python scripts/audit/verify_contracts.py` must pass before merging.
   - Affected owners (`sherwin`, `praveen`, `darain`) are notified and update their typed models/clients accordingly.
4. **Branch & Merge Policy**:
   - All development occurs on `feature/<member>-<topic>` branched from `integration`.
   - Only **Mishael** merges PRs into `integration` after CI passes.
   - `main` receives merges only from `integration` after passing `python scripts/audit/integration_gate.py`.
   - Never force-push `main` or `integration`.

## 3. Quota & Handoff Discipline

- Keep agent file reads scoped to your owned module + `AGENTS.md` + relevant `contracts/`.
- Before switching AI tools or ending a shift, update `docs/HANDOFF_<NAME>.md` with current branch, commit SHA, working features, failing tests, and exact next step.
