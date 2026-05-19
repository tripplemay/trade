# Workbench

Research workbench — a browser SPA that surfaces backtest results, strategy
comparisons, recommendations, and snapshot data. **Research-only.** The
workbench never authorises paper or live trading.

Production: **`https://trade.guangai.ai`** (Google OAuth, single-email allowlist).

This directory is the workbench monorepo:

```
workbench/
├── backend/     # FastAPI (Python 3.11+); SQLite via Alembic + Repository
├── frontend/    # Next.js 14 (TypeScript strict, React 18, Tailwind 3)
├── deploy/      # nginx vhost + systemd units (used by GHA deploy)
└── scripts/     # boot helpers
```

The legacy `trade/` package at the repo root stays pure-stdlib and is
untouched by anything in this directory.

## Status — B023 Phase 2 in progress

B022 Phase 1 shipped 7 research pages on 2026-05-18; B023 layers the
manual-execution workflow on the same shell. F001-F006 are live behind
OAuth on `trade.guangai.ai`; F007 (docs + screenshots — this commit) and
F008 (Codex L1+L2 signoff) close the batch.

### B022 Phase 1 — research pages

| Page | Purpose | Vertical-slice feature |
|---|---|---|
| Home (`/`) | NAV / drawdown / kill-switch + recent reports + action items | F006 |
| Strategies (`/strategies`) | 4-sleeve registry + per-strategy config + provenance + charts | F007 |
| Backtest (`/backtest`) | ResizablePanel split: selector + metrics + equity/drawdown + trades CSV | F008 |
| Reports (`/reports`, `/reports/[slug]`) | Markdown rendering + ≥10-row tables → AG Grid | F009 |
| Recommendations (`/recommendations`) | Target weights + gate checks + **Export markdown ticket** (with research-only disclaimer literal) + B023 F006 RiskBanner | F010 |
| Snapshots (`/snapshots`) | Inventory + SSE-streamed refresh modal | F011 |
| Backlog (`/backlog`) | CRUD + git auto-commit (`chore(backlog): add\|edit\|delete BL-WB-XXXX`) | F012 |

### B023 Phase 2 — manual-execution pages

| Page | Purpose | Vertical-slice feature |
|---|---|---|
| Position diff (`/execution/position-diff`) | Current vs target AllocationBar + 9-col signed Δ DataTable + CSV export + Unmatched flag | F002 |
| Account (`/execution/account`) | Cash + positions form → inserts `account_snapshot(source=ui_edit)` | F002 |
| Ticket (`/execution/ticket`) | Generate Markdown + History list + F006 RiskBanner + normal/defensive radio when red | F003 + F006 |
| Ticket detail (`/execution/ticket/[id]`) | Read-only past-ticket viewer + Download Markdown | F003 |
| Fills (`/execution/fills`) | CSV upload (generic / Schwab / IBKR) or manual entry; row-level errors; `allow_unmatched` gate | F004 |
| Journal (`/execution/journal-history`) | Past tickets + slippage analytics (3m/6m/1y trend + outliers); sortable / CSV export | F005 |

See `docs/dev/workbench-architecture.md` for surface-by-surface details, the
request lifecycle, deploy chain (including the B023 6-table schema-assert),
and safety-guard inventory. The end-to-end user flow (Recommendations →
diff → ticket → broker app → fills → reconcile → journal) lives in
`docs/dev/workbench-manual-execution-runbook.md`.

History: B020 (infrastructure) → B021 (cloud + auth) → B022 (research
pages, signed off 2026-05-18) → **B023 (this batch — manual-execution
UI).**

## Prerequisites

| Tool | Version | Notes |
|---|---|---|
| Python | **3.11+** | Repo-root `.venv/bin/python` works; system `/usr/bin/python3` is fine if ≥ 3.11. |
| Node.js | **20+** | The CI runs Node 20 + forces JS-actions onto Node 24 (`FORCE_JAVASCRIPT_ACTIONS_TO_NODE24=true`). |
| npm | **10+** | |
| Bash | **3.2+** | macOS default works; Homebrew bash upgrade not required. |

### One-time host setup for Playwright on Linux

Playwright needs shared libraries (libnss3 / libnspr4 / libasound2t64) that
WSL / Ubuntu don't install by default:

```bash
sudo -E npx --prefix workbench/frontend playwright install-deps chromium
# Note `-E`: sudo otherwise strips http_proxy and apt times out on west-of-mirror hosts.
```

CI installs these automatically via `actions/setup-node` + the Playwright
action; this step is for local development only.

## Zero-to-running

From a fresh `git clone`:

```bash
# 1. Backend venv (project root)
python3.11 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -e "workbench/backend[dev]"

# 2. Frontend dependencies
npm --prefix workbench/frontend install

# 3. Playwright browser (downloads ~150 MB the first time)
npx --prefix workbench/frontend playwright install chromium

# 4. Boot both servers
bash workbench/scripts/start_workbench.sh
```

Expected after step 4:

- `GET http://127.0.0.1:8723/api/health` → `{"status":"ok", …six observability fields…}`.
- `http://127.0.0.1:3000/` redirects to `/login`; the disclaimer footer renders.
- Setting `NEXTAUTH_SECRET` + `ALLOWED_USER_EMAIL` (any test values locally)
  lets the Playwright authed project sign in via a minted HS256 JWS cookie
  (see `workbench/frontend/tests/e2e/auth-setup.ts`).

## Dev / lint / test commands

### Backend (from repo root)

```bash
.venv/bin/python -m pytest workbench/backend/tests/ -q
.venv/bin/python -m ruff check workbench/backend
.venv/bin/python -m mypy
```

`mypy` is wired in `workbench/backend/pyproject.toml` to scan
`workbench_api` + `tests` in strict mode.

### Frontend (from `workbench/frontend/`)

```bash
npm run lint           # next lint (zero warnings allowed)
npm run typecheck      # tsc --noEmit, strict mode
npm test               # Vitest unit + safety suite (~67 tests)
npm run test:e2e       # Playwright (3 projects: setup / anon / authed)
npm run format:check   # Prettier
npm run build          # Next.js production build (standalone)
npm run generate-types # regenerate src/types/api.ts from the live backend
```

The Playwright config reads `PLAYWRIGHT_BASE_URL` so you can point it at a
running dev / preview server. The CI workflow boots the dev server via
`start-server-and-test` and runs Playwright against `127.0.0.1:3000`.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `npm run lint` passes locally, CI lint fails. | `.next/cache/eslint` caches the last result. `rm -rf workbench/frontend/.next/cache && npm run lint` reproduces CI. (Lesson: B022 F007.) |
| `npm run typecheck` passes locally, CI typecheck fails. | `workbench/frontend/tsconfig.tsbuildinfo` is stale. `rm tsconfig.tsbuildinfo && npm run typecheck` reproduces CI. (Lesson: B022 F005.) |
| Playwright cold-compile times out on `/strategies` or `/backtest`. | Bumped per-test `navigationTimeout` + `actionTimeout` + global `expect.timeout`. See `workbench/frontend/playwright.config.ts`. |
| `Port 8723 already in use` when running `start_workbench.sh`. | `lsof -ti:8723 \| xargs kill -9`; the script does not bring its own port manager. |
| Snapshot refresh modal hangs. | The B022 F011 SSE generator is synthetic (≤300ms total). Real subprocess wiring lands in B023; until then, the page logs each stage event into the browser DevTools network panel. |
| `bash scripts/generate-types.sh` says "PYTHON_BIN not executable". | Make sure `.venv/bin/python` exists at the repo root (run the venv-create step in §Zero-to-running). |
| Strategies page spec/code buttons 404. | Resolved in B022 F009 via `/docs/[...path]` viewer. If a 404 surfaces post-F009, the file is missing from the repo — fix the spec path in `services/strategies.py`. |
| Backlog mutation returns 500 "git commit failed". | Either the repo working tree is dirty (run `git status`) or a pre-commit hook is rejecting the change. The toast surfaces the underlying error. |

## Safety boundaries (carry-over)

- Backend env vars are gated by `workbench_api.settings.ALLOWED_ENV_VARS`; the
  safety regression keeps the model + allowlist in lockstep.
- `workbench/` source rejects any broker SDK / paper-API / live-API URL.
- Every protected page renders the canonical disclaimer (Playwright pinned).
- `Recommendations / Export Markdown Ticket` writes the literal
  `"research-only; this is a manual review checklist, not a trading instruction"`
  string — pinned in `tests/unit/test_recommendations.py`.
- `ResizablePanel` is only allowed on the Backtest page
  (`tests/safety/no-resizable-panel-outside-backtest.spec.ts`).
- Production callback URL must live under `trade.guangai.ai`
  (`tests/safety/production-callback-url.spec.ts`).

## Further reading

- `docs/dev/workbench-architecture.md` — architecture, 7-page surfaces,
  request lifecycle, cloud deploy chain, safety inventory.
- `docs/dev/branch-protection-guidance.md` — manual GitHub branch-protection
  setup, includes the `workbench-deploy.yml` candidate.
- `docs/dev/workbench-testing-strategy.md` — testing layers (vitest +
  Playwright + backend pytest + Codex L2 on the real VM).
- `docs/dev/codex-policies.md` — Codex L1/L2 testing policy matrix.
- `docs/dev/B021-vm-setup-runbook.md` — VM bootstrap notes (one-time).
- `docs/screenshots/README.md` — gallery capture checklist (B022 F013).
- `docs/specs/B022-workbench-phase1-spec.md` — the Phase 1 spec these pages
  ship.

_Disclaimer: research-only; never authorizes paper or live trading._
