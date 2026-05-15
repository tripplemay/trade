# Workbench

The research workbench — a browser SPA that surfaces backtest results,
strategy comparisons, recommendations, and (eventually, in B023) a manual
execution helper. **Research-only.** The workbench never authorises paper or
live trading.

This directory holds the workbench monorepo:

```
workbench/
├── backend/          # FastAPI (Python 3.11+)
├── frontend/         # Next.js 14 (TypeScript, React 18, Tailwind 3)
└── scripts/          # boot helpers
```

The legacy `trade/` package at the repo root stays pure-stdlib and is
untouched by anything in this directory.

## Status

This is **B020 — Dev Infrastructure** scaffolding. The Home page is a
placeholder; there are no business pages, no broker integrations, no auth, no
database. Those land in later batches:

- **B021** — Cloud Deploy & Auth (Google OAuth, SQLite, nginx, deployment to
  `trade.guangai.ai`).
- **B022** — Workbench Phase 1 (the seven research pages: Home, Strategies,
  Backtest, Reports, Recommendations, Snapshots, Backlog).
- **B023** — Workbench Phase 2 (manual execution UI).

## Prerequisites

| Tool | Version |
|---|---|
| Python | **3.11+** (the repo-root `.venv/bin/python` works). |
| Node.js | **20+** |
| npm | **10+** |
| Bash | **3.2+** — works on macOS default `/bin/bash` (3.2.57); no Homebrew bash upgrade required. |

### One-time host setup for Playwright on Linux

Playwright launches headless Chromium, which needs a handful of shared
libraries that are not installed by default on most WSL / Ubuntu systems. Run
once per host:

```bash
sudo npx --prefix workbench/frontend playwright install-deps chromium
# or equivalently:
# sudo apt-get install -y libnss3 libnspr4 libasound2t64
```

CI installs these automatically via `actions/setup-node` + the Playwright
GitHub action; this step is for local development only.

## Zero-to-running in ~10 minutes

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

You should then see:

- Backend `GET http://127.0.0.1:8723/api/health` returns
  `{"status":"ok","version":"<git_sha>"}`.
- Frontend `http://127.0.0.1:3000/` renders the "Workbench scaffold OK" card
  and the research-only disclaimer footer.

## Dev / lint / test commands

### Backend

```bash
# From the repo root
.venv/bin/python -m pytest workbench/backend/tests/ -q
.venv/bin/python -m ruff check workbench/backend
.venv/bin/python -m mypy workbench/backend
```

### Frontend

```bash
# From workbench/frontend/
npm run lint           # next lint (zero warnings allowed)
npm run typecheck      # tsc --noEmit, strict mode
npm test               # Vitest unit suite
npm run test:e2e       # Playwright (requires the dev server to be reachable)
npm run format:check   # Prettier (write with `npm run format`)
npm run build          # Next.js production build
```

The Playwright config (chromium-only in B020) reads `PLAYWRIGHT_BASE_URL` so
you can point it at any running dev / preview server. The CI workflow boots
the dev server via `start-server-and-test`.

## Boot-time invariants (B020)

- Backend binds `127.0.0.1` only. The cloud binding (`0.0.0.0` behind nginx +
  Google OAuth) is B021's concern.
- `workbench_api.settings.ALLOWED_ENV_VARS` is the empty set. Any future env
  var must be added to that allowlist; the safety regression test (B020 F003)
  enforces it.
- No broker SDK, paper-API URL, or live-API URL may appear anywhere under
  `workbench/`. The B020 F003 safety guards run in CI as boundary-violation
  detectors.

## Further reading

- `docs/specs/B020-dev-infrastructure-spec.md` — this batch's spec.
- `docs/adr/2026-05-15-workbench-direction.md` — workbench-first MVP path.
- `docs/dev/workbench-testing-strategy.md` — testing layers (created in B020
  F003).
- `docs/dev/workbench-architecture.md` — architecture overview (created in
  B020 F005).
- `docs/dev/branch-protection-guidance.md` — manual GitHub branch-protection
  setup (created in B020 F005).

_Disclaimer: research-only; never authorizes paper or live trading._
