# B020 Research Workbench (Phase 1) Spec

## Background

B019 closes the strategy-research loop on B010 / B013 (cadence + vol_target retune, `docs/test-reports/B019-retune-signoff-2026-05-15.md`). PRD §10 / §11 success criteria are substantively met; PRD §12 originally listed "B009 Broker Adapter Paper" as the final MVP milestone but the user (single individual investor, USD 100k–500k personal account, monthly/quarterly cadence) elected manual execution over auto broker integration. Auto broker integration is permanently moved to PRD §5 non-MVP scope (see ADR `docs/adr/2026-05-15-workbench-direction.md`, commit `b7cba91`, and PRD §7 / §12 amendments in commit `522e34a`).

PRD §12 has been rewritten so the remaining MVP path is **B020 Research Workbench (Phase 1)** + **B021 Workbench Phase 2 (manual execution UI)**. B020 is read-mostly with the minimum-necessary write actions; B021 layers manual-execution workflows on top.

The workbench is the new canonical user surface. The CLI remains supported for automation, CI, and headless reproducibility — every UI action must have an equivalent CLI command. The workbench never connects to a broker, never holds a credential, and never places an order.

## Goal

Ship a local browser-based workbench that:

- Renders the research-only `trade/` pipeline through 7 pages (Home / Strategies / Backtest / Reports / Recommendations / Snapshots / Backlog).
- Reaches "professional financial tool" visual and interaction polish (Bloomberg / TradingView / Koyfin reference points, in 2026-modern shadcn/ui idiom).
- Stays single-user, localhost-only, zero-credential, zero-broker-SDK.
- Reuses the existing `trade/` Python codebase for all backtest / strategy / risk / report logic — no logic is duplicated or reimplemented in the workbench layer.
- Establishes the directory boundary `workbench/` (sibling to `trade/`) so the project's "pure stdlib `trade/`" culture remains intact; workbench dependencies (FastAPI, Pydantic, Node, Next.js, npm packages) live exclusively under `workbench/`.

This batch creates the workbench scaffolding + the 7 read-mostly pages + minimum-necessary write actions, not a manual-execution UI, not an OMS, not a real paper broker adapter, not a live execution path, not a multi-user system, not a cloud-deployable surface.

## Hard Decisions

### Tech stack (locked in ADR §决策 1)

- **Backend:** Python 3.11+, FastAPI, Pydantic v2, Uvicorn (ASGI). Backend code lives at `workbench/backend/`. Imports from `trade/` are allowed and encouraged (the workbench is the consumer); the workbench does not redefine domain types — Pydantic models mirror `trade/` dataclasses via thin adapters.
- **Frontend:** Next.js 14+ App Router, TypeScript (strict mode), React 18+, Tailwind CSS, shadcn/ui (components copied into `workbench/frontend/src/components/ui/` per shadcn convention — owned source). Frontend code lives at `workbench/frontend/`.
- **Tables:** AG Grid Community (free tier; virtualization, sorting, filtering, in-cell editing where needed, CSV export built-in).
- **Charts:** TradingView lightweight-charts (equity, drawdown, sweep curves — finance-native, zero-license-cost). Apache ECharts (pie, treemap, heatmap, sankey — auxiliary).
- **State:** TanStack Query (server-state cache + revalidation), Zustand (client-state where required; expected to be minimal in Phase 1).
- **Icons:** Lucide.
- **Build / test (frontend):** Next.js native build, Vitest (unit), Playwright (E2E smoke). ESLint + Prettier with project-level config.
- **Build / test (backend):** standard `.venv/bin/python` workflows; pytest for unit, httpx TestClient for API contract; ruff + mypy + compileall as usual.
- **Type sharing:** FastAPI auto-generates OpenAPI; `openapi-typescript` (Node CLI) regenerates `workbench/frontend/src/types/api.ts` on demand and as a CI drift check.

Rejected (with rationale in ADR): Streamlit (chrome and layout fight the bar), HTMX-only (caps at ~70 % of the stated bar), SvelteKit (finance component ecosystem is React-first), Tauri/Electron desktop packaging (Phase 3+ at best), MUI / Ant Design (closed black-box dependencies vs shadcn's owned-source model).

### Project structure

```
trade/                       # unchanged, pure stdlib
workbench/
├── backend/
│   ├── pyproject.toml       # FastAPI + Pydantic + Uvicorn + (dev) httpx + pytest + ruff + mypy
│   ├── workbench_api/
│   │   ├── __init__.py
│   │   ├── app.py           # FastAPI app factory; localhost-only binding asserted in tests
│   │   ├── routes/
│   │   │   ├── dashboard.py
│   │   │   ├── strategies.py
│   │   │   ├── backtests.py
│   │   │   ├── reports.py
│   │   │   ├── recommendations.py
│   │   │   ├── snapshots.py
│   │   │   └── backlog.py
│   │   ├── adapters/        # trade/ dataclass → Pydantic model adapters
│   │   ├── safety.py        # forbidden-import guard test helpers
│   │   └── settings.py
│   └── tests/
│       ├── unit/
│       └── api/             # httpx TestClient route tests
├── frontend/
│   ├── package.json
│   ├── package-lock.json    # committed
│   ├── tsconfig.json
│   ├── next.config.mjs
│   ├── tailwind.config.ts
│   ├── playwright.config.ts
│   ├── vitest.config.ts
│   ├── src/
│   │   ├── app/             # App Router pages: layout / page / loading per route
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx                       (Home)
│   │   │   ├── strategies/page.tsx
│   │   │   ├── backtest/page.tsx
│   │   │   ├── reports/page.tsx
│   │   │   ├── reports/[id]/page.tsx
│   │   │   ├── recommendations/page.tsx
│   │   │   ├── snapshots/page.tsx
│   │   │   └── backlog/page.tsx
│   │   ├── components/
│   │   │   ├── ui/          # shadcn-owned components
│   │   │   ├── chart/       # lightweight-charts + ECharts wrappers
│   │   │   ├── table/       # AG Grid wrappers + reusable column defs
│   │   │   └── shell/       # TopBar / SideNav / Footer / ThemeProvider
│   │   ├── lib/             # api client, formatters, hooks
│   │   ├── types/
│   │   │   └── api.ts       # generated from OpenAPI; CI drift-checked
│   │   └── styles/
│   └── tests/
│       ├── unit/            # Vitest
│       └── e2e/             # Playwright smoke (Codex F014)
└── README.md                # dev / build / test / boot runbook
```

`scripts/start_workbench.sh` (new, generator) starts both backend and frontend in dev mode against a single command. Production-equivalent: `next build && next start` + `uvicorn workbench_api.app:app --host 127.0.0.1 --port 8723`.

### Safety boundaries (non-negotiable)

- **Localhost-only:** Uvicorn binds `127.0.0.1`. A unit test asserts no `0.0.0.0` / public binding is reachable. CORS allows only `http://localhost:*` origins. Reverse-proxy or external exposure is explicitly out of scope and any code change that would enable it is rejected.
- **No broker SDK imports:** `workbench/backend/` and `workbench/frontend/` MUST NOT import `ib_insync`, `alpaca`, `alpaca_trade_api`, `futu`, `tiger`, `tradier`, `polygon`, or any equivalent. A regression test enforces this list (mirrors B012 pattern).
- **No paper-trading API URLs:** `paper-api.alpaca.markets`, IBKR paper Gateway hostnames, and equivalents must not appear in code or config. Static-string regression test enforces.
- **No secrets:** No `.env` loading; no `os.environ` reads outside an allow-list (which contains nothing in Phase 1). No API key fields in any UI form. No credential storage.
- **No AI auto-decision:** No LLM API calls. No automated parameter mutation triggered by UI. Manual mutation (e.g., changing a backlog entry's priority) is allowed because the user is the actor.
- **No live trading entry:** UI buttons that emit orders, fills, or anything that could be construed as a trade execution are forbidden. The Recommendations page exports a Markdown checklist only; the checklist's literal disclaimer string is unit-tested.
- **Research-only disclaimer:** Every page renders a fixed footer string ("research-only; not a trading instruction" or equivalent fixed canonical text). Visual regression test verifies presence on every route.

### Data-fetch and run model

- Read endpoints are synchronous and return current state. TanStack Query handles client-side caching and revalidation.
- The "trigger backtest" write endpoint runs the backtest synchronously and returns the result. B019 sweep data shows real-snapshot backtests complete in < 10 s p95; synchronous is acceptable in Phase 1. If a future page needs long-running work, an SSE channel can be added in Phase 2 / 3 — out of Phase 1 scope.
- The "snapshot refresh" endpoint runs `scripts/refresh_public_snapshot` as a subprocess; progress is reported via Server-Sent Events. This is the one Phase 1 long-running operation and the only place SSE is required.
- All write endpoints return the new server state in the response body so the client doesn't need a separate read round-trip.

### Style / UX defaults

- **Theme:** dark by default (financial tool convention). A theme toggle is out of Phase 1 (deferred to Phase 3+). Base color palette: Zinc or Slate via `tweakcn` (build-time theme editor, dev-only — generated CSS variables are committed; `tweakcn` adds no runtime dependency).
- **Density:** "compact" rather than "comfortable" — global Tailwind padding / margin defaults reduced from SaaS-comfort (`p-4`) to high-density (`p-2`); Button and AG Grid row default heights also reduced.
- **Typography:**
  - UI text: **Inter** (variable font, loaded via `next/font/google`).
  - Numeric content (PnL, weights, ratios, drawdowns, Sharpe, table cells with numbers): **JetBrains Mono** (variable font, loaded via `next/font/google`) with `font-variant-numeric: tabular-nums` enforced globally on `.numeric` className. This eliminates digit-width jitter on streaming refresh — non-negotiable in financial UIs.
- **P&L color tokens:**
  - Up / profit / gain: `#00c853` (Material Green A700)
  - Down / loss: `#ff3b30` (iOS system red)
  - Tokens registered as `--color-up` / `--color-down` CSS variables in the Zinc/Slate theme; can be re-tuned at F001 time via `tweakcn` if contrast against the dark surface needs adjustment. shadcn `destructive` token reserved for system errors (validation failure / API error), not P&L losses.
- **Accessibility:** shadcn/ui inherits Radix primitives → keyboard-accessible by default. Phase 1 does not introduce a command palette; basic keyboard navigation is shipped as a side effect.
- **Loading:** every async route uses `loading.tsx` in App Router for instant skeletons.
- **Errors:** every async route uses `error.tsx` for graceful degradation; uncaught backend errors surface as toast notifications, not full-screen blanks.
- **Empty states:** every list view has an explicit empty state with a help link to the relevant `docs/`.

### Reference data sources

All reads ultimately go through `trade/` modules:

- `trade.master.run_backtest()` for backtest runs
- `trade.strategies.*` for strategy registries
- `trade.snapshots.*` (if exists; otherwise direct read of `data/public-cache/*.json` via adapter)
- `docs/test-reports/B0*-*.md` for the Reports page (file-system listing + Markdown rendering)
- `backlog.json` for the Backlog page
- `docs/specs/`, `docs/engineering/`, `docs/strategy/` for cross-link resolution

The workbench backend never duplicates business logic — adapters convert `trade/` dataclasses to Pydantic response models and back. If `trade/` does not expose a needed accessor, the right fix is to add a small public function in `trade/`, not to bypass it in the workbench.

### Account state and Recommendations data

The Recommendations page consumes a user-provided `accounts/me.json` (schema defined in B012). Phase 1 expectation: user maintains this file manually; the workbench reads it and offers a one-click reload after the user edits it externally. Phase 2 adds in-UI editing.

If `accounts/me.json` is absent, the Recommendations page shows an empty state with instructions to create it and a link to the B012 spec section that defines the schema.

## Architecture

### Request lifecycle (read)

```
Browser ── HTTP GET /api/strategies
   │
   └─→ FastAPI route handler
         │
         └─→ workbench_api.adapters.strategies.list_all()
               │
               └─→ trade.strategies registry → adapter → Pydantic response
         │
         └─→ JSON response
   │
   └─→ TanStack Query caches by ['strategies']
   │
   └─→ React Server Component / Client Component renders
```

### Request lifecycle (write — snapshot refresh)

```
Browser ── POST /api/snapshots/refresh ── SSE upgrade
   │
   └─→ FastAPI route handler launches subprocess
         (scripts/refresh_public_snapshot)
         │
         └─→ stream stdout lines as SSE events
   │
   └─→ Client component renders progress; on completion, invalidates ['snapshots']
```

### CI integration

GitHub Actions adds two jobs:

- `workbench-backend`: pytest + ruff + mypy on `workbench/backend/`.
- `workbench-frontend`: `npm ci` + Vitest + Playwright (against backend running in a service container or `start-server-and-test`).

Both jobs are independent from the existing `trade/` CI and add no dependencies to the `trade/` test path. Default `trade/` CI continues to be fixture/mock-first and offline; workbench CI also stays offline (no network calls in tests; snapshot fixtures committed to the repo for backend tests).

## Feature Requirements

### F001 — Workbench monorepo scaffolding (template-based)

Executor: generator.

Establish the `workbench/{backend,frontend}` directory layout. Backend: `pyproject.toml` with FastAPI / Pydantic v2 / Uvicorn / pytest / httpx / ruff / mypy, a minimal FastAPI app with `/health` endpoint, localhost-only binding, ruff + mypy clean, pytest passing.

**Frontend: vendor `shadcn-dashboard-landing-template` (by ShadcnStore, MIT) and pre-configure for financial use.** Per `docs/research/2026-05-15-workbench-template-research.md`, this template is the chosen starting point. Execution sequence:

1. **Day 1 pre-flight check** (Next.js 15 + React 19 + Tailwind v4 ecosystem viability):
   - Create a throwaway Next.js 15 + Tailwind v4 project.
   - Install **AG Grid Community** (latest), **TradingView lightweight-charts** (latest), **ECharts** + `echarts-for-react` (latest); render one minimal example of each (≤ 50 lines apiece).
   - Run `npm run build`; confirm no peer-dep `npm WARN` for any of the three; confirm runtime no console errors.
   - **Pass criterion:** all three demos render and build cleanly.
   - **Fall-back:** if any of the three has a peer-dep blocker or runtime error not resolvable in ≤ 2 hours, drop Next.js 15 / React 19 / Tailwind v4 and use Next.js 14 + React 18 + Tailwind 3 as the template baseline. Record the decision and which package blocked in an ADR addendum (`docs/adr/2026-05-15-workbench-direction.md` §"Stack version downgrade decision").
2. **Vendor the template** into `workbench/frontend/`. The template's git history is not preserved; this is a snapshot copy under the project's own license. License notation: append the template's `LICENSE` content to `workbench/frontend/LICENSE-third-party.md`.
3. **Cleanup demo / dummy apps.** Delete every demo route and component not on the 7-page list (Mail, Tasks, E-commerce, Calendar, etc.). After cleanup run:
   - `npx unimported` — no orphan files
   - `npx depcheck` — no unused dependencies
   - `npx ts-unused-exports tsconfig.json --excludePathsFromReport='src/types/api.ts'` — no orphan exports
   - Manual `tree workbench/frontend/src/` — every subdirectory must trace to a page on the 7-page list or be one of `components/{ui,chart,table,shell}`, `lib/`, `types/`, `styles/`.
4. **Apply financial pre-configuration:**
   - Tailwind config: reduce default spacing scale (e.g. `p-4` defaults map to `0.5rem`).
   - Fonts: load Inter and JetBrains Mono via `next/font/google`; apply Inter to `<body>`, JetBrains Mono + `tabular-nums` to `.numeric` className.
   - Theme: run `tweakcn` once during F001, lock a Zinc-based dark palette with `--color-up: #00c853` and `--color-down: #ff3b30`; commit the generated `globals.css` variable block.
   - Default `<Button size>` reduced to `sm` everywhere; default `<Table>` row height set to `compact`.
   - Top-level `app/layout.tsx`: shell + dark class on `<html>` + disclaimer footer.
5. **TypeScript strict + ESLint + Prettier + Vitest + Playwright config + sample tests passing.**

CI: add `workbench-backend` and `workbench-frontend` jobs to `.github/workflows/`; both jobs green on this feature's commit. `workbench/README.md` covers dev / build / test commands plus a "template provenance" note pointing at the research report + the upstream template URL + the cleanup audit report.

Acceptance: backend `uvicorn workbench_api.app:app --host 127.0.0.1 --port 8723` boots; `curl http://127.0.0.1:8723/health` returns `{"status":"ok"}`; frontend `npm run dev` boots Next.js dev server at `http://localhost:3000`; the cleanup audit commands all pass (no unimported / no depcheck warnings / no orphan ts-unused-exports); `next build` succeeds without peer-dep warnings for AG Grid / lightweight-charts / ECharts; both `pytest workbench/backend/tests/` and `npm test --prefix workbench/frontend` pass; both `ruff check workbench/backend` and `mypy workbench/backend` clean; CI green on PR; `trade/` test suite unaffected (all 592 existing tests still pass); `workbench/frontend/LICENSE-third-party.md` contains the template's upstream MIT text.

### F002 — OpenAPI → TypeScript types pipeline + CI drift check

Executor: generator.

Add `workbench/frontend/scripts/generate-types.sh` that runs `openapi-typescript` against the FastAPI OpenAPI JSON (fetched from a running backend or saved to disk) and writes `workbench/frontend/src/types/api.ts`. Add CI step that regenerates types and `git diff --exit-code` fails the build if drift is detected. Document in `workbench/README.md` how to refresh types locally.

Acceptance: `bash workbench/frontend/scripts/generate-types.sh` regenerates `api.ts` deterministically; CI drift check passes on this feature's commit and fails on an intentional drift commit; types are imported by at least one frontend module to prove the pipeline works end-to-end.

### F003 — Shell layout + safety regression tests

Executor: generator.

Implement the persistent shell (TopBar with project name + snapshot indicator + nav links, SideNav with 7 page links + active state, Footer with research-only disclaimer). Dark theme tokens registered. Safety regression tests added: localhost-only binding asserted, no broker SDK imports allowed (mirrors B012's regression test pattern), no `paper-api` / `live-api` URL strings in `workbench/`. Disclaimer string is a single canonical constant; a unit test verifies it appears in the Footer component and is the project's standard string.

Acceptance: loading any URL shows TopBar / SideNav / Footer correctly; Playwright smoke test verifies the disclaimer is visible on every of the 7 routes; safety tests pass; `ruff` / `mypy` / `compileall` / `pytest` / `npm test` / `npm run lint` / `npm run typecheck` all clean.

### F004 — Chart component library

Executor: generator.

Wrappers under `workbench/frontend/src/components/chart/`:

- `EquityCurveChart` — lightweight-charts area chart, supports multi-series overlay (legend-driven toggle on/off), crosshair tooltip, brush selection emitting `[startDate, endDate]` to a callback, PNG export button.
- `DrawdownChart` — lightweight-charts histogram below zero, shares time axis with EquityCurveChart when both rendered.
- `SweepHeatmap` — ECharts heatmap for sweep matrices (cadence × vol_target colored by metric).
- `AllocationPie` — ECharts pie for target portfolio weights.
- `AllocationBar` — ECharts horizontal bar for compare-to-current.

PNG export uses `chart.takeScreenshot()` for lightweight-charts and `chart.getDataURL()` for ECharts. Vitest unit tests render each component with canned props and assert basic DOM presence; visual regression deferred.

Acceptance: each component renders deterministically with canned props; PNG export emits a downloadable blob in test environment (mocked); Vitest unit tests pass; Storybook-equivalent dev page at `/dev/charts` renders all components with example data (kept behind a `NEXT_PUBLIC_DEV_ROUTES` flag; not navigable from production shell).

### F005 — Table component + CSV export

Executor: generator.

Wrappers under `workbench/frontend/src/components/table/`:

- `DataTable<T>` — AG Grid Community wrapper with sensible defaults (sortable, filterable, resizable, sticky header), accepts column defs + row data, exposes `exportCsv()` ref method.
- Reusable column defs: `dateColumn`, `currencyColumn`, `percentColumn`, `basisPointsColumn`, `weightColumn` — each with appropriate formatting and right-alignment.

Acceptance: `DataTable` renders a 1000-row mock dataset with virtualization (renders ≤ ~30 rows in DOM at any time); CSV export produces a valid CSV (in test, mock blob); column defs match snapshot tests for formatting; Vitest unit tests pass.

### F006 — Home / Dashboard page (vertical slice)

Executor: generator.

Backend: `GET /api/dashboard` returns `{nav, masterDrawdown, killSwitchThreshold, daysToNextRebalance, lastRebalance: {date, fillCount, slippageBps}, recentReports: [{id, title, date, status, path}], actionItems: [{id, severity, message}]}`. Frontend: Home page renders the four top cards + recent reports list (links to `/reports/[id]`) + action items section. Empty states for "no rebalance yet" and "no action items".

Acceptance: route returns valid payload from canned `trade/` fixtures + canned `backlog.json` + canned `docs/test-reports/`; Vitest renders the page with mock API; Playwright smoke test loads the page and verifies the 4 cards are visible; httpx TestClient asserts schema contract.

### F007 — Strategies page (vertical slice)

Executor: generator.

Backend: `GET /api/strategies` returns sleeve list with config + active flag + cumulative performance summary. `GET /api/strategies/{id}` returns detail with provenance links to spec / code / last sweep. Frontend: master list (AG Grid `DataTable`) + per-strategy detail panel (config card, equity curve, drawdown, turnover heatmap, performance comparison). Selectable from URL `/strategies?selected=B013`.

Acceptance: strategy registry from `trade/` surfaces all 4 sleeves with current B019 defaults reflected (B013 quarterly/0.11, others unchanged); per-strategy detail loads charts deterministically; CSV export of strategy list works; spec / code link buttons open the corresponding file in a new tab (frontend route renders the file content from `GET /api/docs/{path}` which sanitizes path traversal).

### F008 — Backtest viewer page (vertical slice)

Executor: generator.

Backend: `POST /api/backtests/run` accepts `{strategyId, snapshotId, startDate, endDate, parameters}` and synchronously runs `trade.master.run_backtest()` (or per-strategy equivalent), returns the standard result object. `GET /api/backtests/{run_id}` retrieves a cached result. Frontend: **layout uses shadcn `<ResizablePanelGroup>` for a single horizontal split — left pane holds the selector (strategy / snapshot / window + run button); right pane holds the result area** (metrics card stack on top, EquityCurveChart + DrawdownChart in the middle, allocation history + trades AG Grid tables at the bottom). Comparison toggle: layer SPY and static 60/40 on the equity curve.

Hard scope boundary on the ResizablePanel: this is a **single horizontal split confined to F008 alone**. We are **not** introducing `react-grid-layout`, **not** persisting panel sizes across reloads, **not** allowing the user to add / remove panels, **not** synchronizing splits across pages. The full "multi-panel dockable layout" remains in §Out Of Scope (Phase 3+). The intent is solely to give the Backtest viewer a Bloomberg-style left-list + right-detail feel without committing to a layout-engine.

Acceptance: end-to-end smoke from selector → run → chart render; metrics card values match `trade/` backtest output to the cent; Playwright smoke test runs a canned B010 backtest on a fixture snapshot in < 5 s; ResizablePanel drag works with mouse + keyboard (Radix primitive handles both); other 6 pages have **no** ResizablePanel (regression assertion).

### F009 — Reports page (vertical slice)

Executor: generator.

Backend: `GET /api/reports` returns list of test reports + signoffs from `docs/test-reports/` (filename + extracted title + date + PASS/FAIL hint). `GET /api/reports/{slug}` returns rendered Markdown + extracted tables as structured JSON (so the frontend can re-render with AG Grid instead of HTML `<table>` when desired). Frontend: list of reports + per-report rendering page. Markdown rendering uses `react-markdown` + `remark-gfm` + custom code-block + table renderer (defaults to AG Grid for tables ≥ 10 rows). Cross-links (`docs/specs/B0*.md`, `docs/test-reports/B0*.md`) resolve to internal routes.

Acceptance: all current B017 / B018 / B019 reports render cleanly; tables in B018 attribution and B019 sweep reports are interactive (sortable); cross-links to specs and other reports work; smoke test loads B019 retune sweep report and verifies the sweep matrix table appears as an interactive table.

### F010 — Recommendations page (vertical slice)

Executor: generator.

Backend: `GET /api/recommendations/current` loads `accounts/me.json` + latest snapshot + master portfolio config, runs the master portfolio at the latest signal date, returns `TargetPositions` + diff vs current account + gate check results + wash-sale flags (heuristic: same symbol bought within last 30 days from journal). `POST /api/recommendations/export-ticket` writes a Markdown checklist to `docs/runs/<date>/order-ticket-<date>.md` and returns the path; does **not** place any order. Frontend: AllocationPie + AllocationBar + positions table + rationale + gate panel + wash-sale flags + Export Markdown Ticket button. If `accounts/me.json` is missing, empty state with instructions.

Acceptance: with a committed sample `accounts/me.json` fixture, end-to-end run produces a valid target portfolio with stable numbers; export ticket button creates a Markdown file matching the B020 ticket template; literal disclaimer "research-only; this is a manual review checklist, not a trading instruction" is asserted in the exported Markdown by unit test.

### F011 — Snapshots page (vertical slice)

Executor: generator.

Backend: `GET /api/snapshots` returns list of snapshots under `data/public-cache/` with quality status. `POST /api/snapshots/refresh` runs `scripts/refresh_public_snapshot` as subprocess and streams progress over SSE. Frontend: DataTable of snapshots + Refresh button that opens a progress dialog (modal) streaming SSE events. On completion, list refreshes and a toast notifies success/failure.

Acceptance: snapshot list loads with quality flags; refresh button triggers subprocess (mocked in test with a 2-second canned subprocess); SSE events render in the progress dialog; on completion the list re-fetches; failure shows a toast with the underlying error message.

### F012 — Backlog page (vertical slice)

Executor: generator.

Backend: `GET /api/backlog`, `POST /api/backlog`, `PATCH /api/backlog/{id}`, `DELETE /api/backlog/{id}`, plus an automatic `git add backlog.json && git commit -m "chore(backlog): <change>"` after each mutation (commit author records the workbench as the actor; user can still amend later). Frontend: DataTable of backlog with priority filter + Add / Edit / Delete actions (Dialog modals with form validation).

Acceptance: list loads with current 4 entries reflecting BL-B011-S2 high after B019 wrap-up; create / edit / delete works end-to-end; each mutation produces a git commit on the working tree; commit messages match `chore(backlog): add|edit|delete BL-<id>`; on git error (e.g., conflict) the mutation fails closed and surfaces a toast.

### F013 — Workbench documentation + screenshots + runbook

Executor: generator.

`workbench/README.md` covers: prerequisites (Python 3.11+, Node 20+), one-command boot (`scripts/start_workbench.sh`), dev / build / test commands for both backend and frontend, troubleshooting (port conflicts, snapshot refresh failures, type-drift CI errors). Add screenshots (PNG, ≤ 300 KB each, committed) of each of the 7 pages with a representative state. Add `docs/dev/workbench-architecture.md` covering the request lifecycle, project structure, and safety guards. Update top-level `CLAUDE.md` reference-docs section to point at the new workbench docs.

Acceptance: README's commands actually work (Codex F014 verifies); screenshots correspond to current UI; architecture doc cross-references B012 (BrokerAdapter ABC anchor), B019 (signoff that closed the strategy loop), ADR `2026-05-15-workbench-direction`.

### F014 — Codex L1 + L2 verification + workbench signoff

Executor: codex.

Phase 1 verification checklist:

1. Backend: `pytest workbench/backend/tests/ -q` all green; ruff + mypy + compileall clean.
2. Frontend: `npm test --prefix workbench/frontend` all green; lint + typecheck clean.
3. Playwright E2E smoke walks all 7 pages, asserts no console errors, asserts disclaimer visible on each.
4. Safety regression: `rg "ib_insync|alpaca|futu|tiger|tradier|polygon|paper-api|live-api" workbench/` returns no functional hits (test files and disclaimer-style strings are explicitly allowed).
5. Localhost binding: an integration test attempts to reach the API at `http://0.0.0.0:8723` and asserts the connection is refused (or only `127.0.0.1` is reachable).
6. Numeric correctness: run a canned B010 backtest through the workbench API and assert the result matches `trade.master.run_backtest()` called directly with the same inputs, byte-for-byte for floats (no rounding loss in the adapter layer).
7. Existing `trade/` test suite still passes unchanged.
8. CI passes on the final F014 commit.

Codex writes `docs/test-reports/B020-workbench-phase1-signoff-2026-MM-DD.md` using `framework/templates/signoff-report.md`. Signoff documents scope, verification commands and results, screenshots referenced, known limitations (Phase 2 gaps: execution UI, account journal, in-UI account editing), and the standard research-only disclaimer. Update `progress.json` (`status → done`, `docs.signoff` set, `evaluator_feedback` summarizes), close `BL-B011-S2` if a satellite implementation batch has been opened in the interim (not required), otherwise leave it as high-priority backlog.

## Out Of Scope

- **Execution UI** — diff / order-ticket / fill-upload UIs all deferred to B021. Phase 1 Recommendations page exports a Markdown checklist only.
- **Account journal viewer** — historical fill log, slippage trends, kill-switch event log all in B021.
- **In-UI editing of `accounts/me.json`** — Phase 1 expects manual edits + reload.
- **Multi-panel dockable layouts** (`react-grid-layout` style — user adds/removes/saves panels across the workbench) — deferred to Phase 3+. **Exception:** F008 Backtest viewer uses a single shadcn `<ResizablePanelGroup>` horizontal split, confined to that one page; this is not the deferred capability.
- **Command palette** (⌘K cmdk), **theme toggle**, **i18n**, **real-time data streams (WebSocket / SSE for live prices)**, **desktop packaging (Tauri / Electron)** — deferred to Phase 3+ or never.
- **PDF report assembly** and **self-contained HTML snapshots** — rejected per ADR §决策 4 (browser print-to-PDF is the free fallback).
- **Multi-account support** — single account in Phase 1.
- **AI-assisted features** — no LLM integration in this batch. May appear later under PRD §14 boundaries (explanation only, never auto-decision).
- **Authentication / authorization** — single user, localhost only, no auth.
- **Cloud deployment** — explicitly stays local. PRD §8.
- **Backwards-compatibility shims for the historical "no dashboard" stance** — none required; the PRD §7 amendment is the canonical source.

## Acceptance

Batch is **done** when:

1. F001 → F005 (scaffolding + components): all green on `main`; backend and frontend boot; type pipeline works; CI passes.
2. F006 → F012 (7 vertical-slice pages): each page loads on its route; renders deterministic fixture data; passes its Vitest + Playwright smoke; backend httpx contract tests pass.
3. F013 (docs): `workbench/README.md` boots a developer from zero to running workbench in ≤ 10 minutes; screenshots present.
4. F014 (Codex verification): all 8 checklist items green; signoff written; `progress.json.status = done` with `docs.signoff` populated.
5. All hard safety boundaries hold: no broker SDK, no paper / live API URL strings, no secrets, no AI auto-decision, localhost-only binding, disclaimer on every page.
6. Existing `trade/` test suite unchanged and green.
7. `BL-B011-S2` (satellites) remains visible in the workbench (UI shows the stub fall-through honestly) and remains in `backlog.json` at priority `high` ready for the next batch.

_Disclaimer: research-only; never authorizes paper or live trading._
