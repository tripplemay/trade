# B020 Workbench Dev Infrastructure Spec

## Background

B019 closed the strategy-research loop on B010 / B013. ADR `docs/adr/2026-05-15-workbench-direction.md` (with cloud addendum) established the workbench-first MVP completion path: 4 sequential batches B020 → B021 → B022 → B023 (Dev Infra → Cloud Deploy → Workbench Phase 1 → Workbench Phase 2). PRD §7 / §8 / §12 amended in same session.

The user explicitly asked that **CI/CD/E2E infrastructure be established before any frontend feature work begins**. This batch (B020) is that infrastructure layer: pure dev tooling, no cloud dependency, no auth, no business features. It provides the foundation that B021 (Cloud Deploy & Auth) and B022 (Workbench Phase 1) build on.

B020 deliberately **does not** touch:
- Google OAuth / NextAuth integration (that's B021).
- SQLite / database layer (that's B021).
- Production deployment / nginx / certbot (that's B021).
- Page implementations / UI / API endpoints serving real data (that's B022).
- Manual execution UX (that's B023).

B020 establishes only the scaffolding, tooling, CI, testing conventions, safety guards, and OpenAPI ↔ TypeScript pipeline that subsequent batches consume.

## Goal

Ship the workbench monorepo skeleton, CI workflows, testing strategy, and code-generation pipeline — without writing any business logic or page UI — so that:

1. A developer can clone the repo and within ~10 minutes have backend + frontend dev servers running locally with all lint / type / test commands green.
2. Every PR triggers automated lint, type-check, unit-test, and (placeholder) E2E checks for both backend and frontend in CI; failures block merge.
3. The safety regression test scaffolding is in place so subsequent feature batches inherit hard-boundary enforcement (no broker SDK, no paper / live API URLs, disclaimer presence on every page) for free.
4. The OpenAPI → TypeScript types pipeline exists end-to-end so that B021 / B022 can wire the actual API contract without scaffolding rework.
5. Project culture is preserved: `trade/` remains pure stdlib; all workbench dependencies isolated under `workbench/`.

This batch creates the dev-time scaffolding only. It does **not** make the workbench externally accessible, does **not** persist any business data, and does **not** authenticate users.

## Hard Decisions

### Project structure (locked from ADR §决策 1, refined here)

```
trade/                       # unchanged, pure stdlib
workbench/
├── backend/
│   ├── pyproject.toml       # FastAPI + Pydantic v2 + Uvicorn + dev tooling
│   ├── workbench_api/
│   │   ├── __init__.py
│   │   ├── app.py           # FastAPI app factory; /health endpoint only in B020
│   │   └── settings.py      # env var loader; allowlist of permitted env names enforced
│   └── tests/
│       ├── unit/
│       │   └── test_health.py
│       └── safety/
│           ├── test_no_broker_sdk_imports.py
│           ├── test_no_paper_or_live_urls.py
│           └── test_settings_env_allowlist.py
├── frontend/
│   ├── package.json
│   ├── package-lock.json    # committed
│   ├── tsconfig.json        # strict mode
│   ├── next.config.mjs
│   ├── tailwind.config.ts   # dark theme tokens stubbed; full theme is B022
│   ├── playwright.config.ts # browsers: chromium only in B020
│   ├── vitest.config.ts
│   ├── eslint.config.mjs
│   ├── prettier.config.mjs
│   ├── src/
│   │   ├── app/
│   │   │   └── page.tsx     # placeholder Home that just renders "Workbench scaffold OK" + the disclaimer Footer
│   │   ├── components/
│   │   │   └── shell/
│   │   │       └── Footer.tsx   # canonical disclaimer constant; reused in B022
│   │   ├── lib/
│   │   │   └── disclaimer.ts    # exports DISCLAIMER_TEXT constant
│   │   ├── types/
│   │   │   └── api.ts           # generated from backend OpenAPI; in B020 contains only /health type
│   │   └── styles/
│   │       └── globals.css      # base reset + dark mode root; financial palette is B022
│   ├── scripts/
│   │   └── generate-types.sh    # openapi-typescript runner
│   └── tests/
│       ├── unit/
│       │   └── disclaimer.spec.ts
│       ├── safety/
│       │   ├── no-broker-sdk-imports.spec.ts
│       │   └── disclaimer-present.spec.ts
│       └── e2e/
│           └── home-loads.spec.ts   # Playwright smoke
├── README.md                # dev / build / test runbook + boot quickstart
└── scripts/
    └── start_workbench.sh   # boots backend (uvicorn 127.0.0.1:8723) + frontend (next dev 3000) concurrently
```

### Tech choices (carried from ADR; locked here for backend, deferred for frontend visual layer)

- **Backend:** Python 3.11+, FastAPI, Pydantic v2, Uvicorn (ASGI). pytest + httpx (TestClient) + ruff + mypy.
- **Frontend:** Next.js 14 baseline (B020 pre-flight check; if AG Grid / lightweight-charts / ECharts compatibility on Next.js 15 + React 19 + Tailwind v4 is verified during B022 F001, the upgrade path is well-defined and template clone happens then). For B020 we ship Next.js 14 + React 18 + Tailwind 3 to keep scaffolding work stable; B022 may upgrade. Vitest + Playwright + ESLint + Prettier.
- **Type-sharing:** `openapi-typescript` Node CLI; pipeline scaffolded but only generates `/health` type in B020.
- **Theme tokens / template / font / color palette / AG Grid / charts:** all deferred to B022 F001 (template clone batch). B020 ships only the bare minimum — placeholder Home page + Footer with disclaimer + dark mode root class.

### Safety boundary scaffolding (key B020 deliverable)

Safety regression tests are scaffolded in B020 even though the protected surface (UI pages, broker integration, paper-API endpoints) does not exist yet. The tests assert against the **whole `workbench/` tree** so that the moment a developer (or AI agent) introduces a forbidden import, the test goes red.

Tests written in B020:

1. **`test_no_broker_sdk_imports.py`** (backend): grep `workbench/backend/` (excluding venv / `__pycache__`) for any import of `ib_insync`, `alpaca`, `alpaca_trade_api`, `futu`, `tiger`, `tradier`, `polygon`, `oandapy`, `tradeapi`. Returns 0 hits.
2. **`test_no_paper_or_live_urls.py`** (backend): grep `workbench/backend/` for string literals matching `paper-api.alpaca.markets`, `api.alpaca.markets`, `paper.gateway.ibkr.com`, `gw.gateway.ibkr.com`, `api.futu.com`, `api.tigerbrokers.com`. Returns 0 hits.
3. **`test_settings_env_allowlist.py`** (backend): assert `workbench_api.settings` only reads env vars from a known allowlist (in B020 the allowlist is empty — `/health` needs no env var); any future env var must be added to allowlist explicitly.
4. **`no-broker-sdk-imports.spec.ts`** (frontend): grep `workbench/frontend/src/` and `workbench/frontend/package.json` for any reference to `@alpaca/`, `ib-insync`, `futu-api`, `tiger-securities`, equivalent. Returns 0 hits.
5. **`disclaimer-present.spec.ts`** (frontend Playwright): load every navigable route (B020: just `/`); assert the canonical disclaimer text is visible. The `DISCLAIMER_TEXT` constant is exported from `workbench/frontend/src/lib/disclaimer.ts` and tested independently in `disclaimer.spec.ts` for stability.

These tests must run in the CI workflow; failure blocks merge.

### Localhost-only binding (B020 only)

Backend binds `127.0.0.1` by default. The actual cloud-deployment binding (which becomes `0.0.0.0` behind nginx + OAuth gating) is B021's concern. In B020 the binding is hard-coded to `127.0.0.1` because no one should be able to reach the placeholder Home page from anywhere except localhost yet.

A unit test asserts that `workbench_api.app.create_app()` produces a configuration that, when run with default Uvicorn settings, listens on `127.0.0.1` only. Cloud-binding flexibility is added in B021.

### CI integration

Two new workflows in `.github/workflows/`:

- **`workbench-backend.yml`** — runs on PR + push to `main` for changes touching `workbench/backend/**`:
  - Set up Python 3.11.
  - pip cache.
  - Install `workbench/backend/[dev]`.
  - Run `pytest workbench/backend/tests/ -q`.
  - Run `ruff check workbench/backend`.
  - Run `mypy workbench/backend`.
  - Run safety regression tests as a separate step (so the failure surface labels which boundary tripped).
- **`workbench-frontend.yml`** — runs on PR + push to `main` for changes touching `workbench/frontend/**`:
  - Set up Node 20.
  - npm cache.
  - Playwright browser cache (chromium only in B020 to keep CI fast).
  - `npm ci --prefix workbench/frontend`.
  - `npm run lint --prefix workbench/frontend`.
  - `npm run typecheck --prefix workbench/frontend`.
  - `npm test --prefix workbench/frontend` (Vitest).
  - `npx start-server-and-test --prefix workbench/frontend dev http://localhost:3000 'npm run test:e2e --prefix workbench/frontend'` (Playwright smoke).
  - On Playwright failure: upload Playwright HTML report + screenshots / video as artifact.

The existing `python-ci.yml` (which covers `trade/`) continues unchanged; no shared steps, no shared cache, full isolation.

### Branch protection (user-action)

A `docs/dev/branch-protection-guidance.md` document (deliverable of F005) records the GitHub branch-protection rules the user is asked to manually configure in Settings:

- `main` requires status check: `python-ci`, `workbench-backend`, `workbench-frontend` all pass.
- `main` requires linear history (rebase only; matches existing project workflow).
- Force push to `main` blocked.
- (Optional) require 1 review on PR — user can decide whether to enable for solo workflow.

The doc is reference; actual configuration is the user's manual step. B021 / B022 / B023 inherit these rules without further setup.

## Architecture (B020 only)

### Backend

Trivially simple in B020. Single endpoint:

```
GET /health → 200 {"status":"ok","version":"<git_sha>"}
```

`workbench_api.settings` defines an `Settings` class (Pydantic `BaseSettings`) with an explicit allowed-env-var allowlist; in B020 the allowlist is empty.

### Frontend

App Router with one route (`/`). The page renders:

- A placeholder card: "Workbench scaffold OK — backend says: `<status from /health>`"
- A Footer with the canonical disclaimer text.

`api.ts` types are generated from backend OpenAPI; in B020 the only type is the `/health` response. The page uses the generated type for type-safe fetch.

### Booting

`scripts/start_workbench.sh` runs both:

```
uvicorn workbench_api.app:app --host 127.0.0.1 --port 8723 --reload &
npm run dev --prefix workbench/frontend &
wait
```

Documented in `workbench/README.md` for newcomers.

## Feature Requirements

### F001 — Workbench skeleton + Python/Node toolchain bootstrap

Executor: generator.

Establish `workbench/{backend,frontend}` directory layout per §Project structure. Backend: `pyproject.toml` with FastAPI / Pydantic v2 / Uvicorn / pytest / httpx / ruff / mypy; minimal FastAPI app exposing `/health`; ruff + mypy clean; pytest passing. Frontend: Next.js 14 + React 18 + TypeScript strict + Tailwind 3 + ESLint + Prettier + Vitest + Playwright config; placeholder Home page renders the disclaimer constant; `npm run lint`, `npm run typecheck`, `npm test`, `npx playwright test --reporter=list` all green on a clean clone. `scripts/start_workbench.sh` boots both servers. `workbench/README.md` covers prerequisites + clone + install + boot + test.

Acceptance:

1. From a clean `git clone` + `python3.11 -m venv .venv && .venv/bin/pip install -e workbench/backend[dev] && cd workbench/frontend && npm ci`, the boot command works.
2. `curl http://127.0.0.1:8723/health` returns `{"status":"ok","version":"<sha>"}`.
3. `http://localhost:3000/` shows the placeholder card + disclaimer in the dev browser.
4. `pytest workbench/backend/tests/` green; `ruff check workbench/backend` clean; `mypy workbench/backend` clean.
5. `npm test --prefix workbench/frontend` green; `npm run lint --prefix workbench/frontend` clean; `npm run typecheck --prefix workbench/frontend` clean; `npx playwright test --prefix workbench/frontend` green (the home-loads smoke test passes).
6. Existing `trade/` test suite unaffected (all 592+ existing tests still pass; total wall time not regressed beyond noise).
7. `workbench/README.md` documents the above commands and the 10-minute zero-to-running expectation.

### F002 — CI workflows (workbench-backend + workbench-frontend)

Executor: generator.

Add `.github/workflows/workbench-backend.yml` and `.github/workflows/workbench-frontend.yml` per §CI integration. Each runs on PR + push to `main` filtered by path (`workbench/backend/**` and `workbench/frontend/**` respectively). Caches: pip, npm, Playwright browsers. Concurrent backend+frontend startup for E2E uses `start-server-and-test` against a separate backend process. Playwright failure uploads HTML report + screenshots / video as workflow artifact.

Acceptance:

1. Both workflows green on the F002 commit.
2. Cache hit on second run (verified via workflow log).
3. Intentional backend test break on a throwaway commit causes `workbench-backend` to fail, blocks PR merge in branch-protected setup.
4. Intentional frontend test break on a throwaway commit causes `workbench-frontend` to fail with an artifact uploaded.
5. `python-ci.yml` workflow continues to pass unchanged (no regression to existing trade/ pipeline).
6. CI total wall time for a typical PR ≤ 10 minutes (backend + frontend in parallel jobs).

### F003 — Testing strategy doc + safety guard scaffolding

Executor: generator.

Write `docs/dev/workbench-testing-strategy.md` defining:

- L1 (unit): runs in default CI; no network; pure functions / single-component / mocked deps. Backend: pytest. Frontend: Vitest.
- L2 (integration): runs in default CI; backend integration tests via httpx TestClient; frontend integration tests via Vitest with mocked API clients; OR Playwright tests against a running backend.
- L3 (E2E): runs in default CI; Playwright + start-server-and-test pattern; chromium only in B020, expanded in later batches if needed.
- Safety regression tests: separate test directory, run in default CI, treated as boundary-violation guards (failure indicates a hard policy breach, not a feature regression).
- Fixture-first / mock-first default; no real network in CI; framework v0.9.21 #1 (fixture-vs-real reversal warning) cited.

Implement the 5 safety regression tests listed in §Safety boundary scaffolding. Each test must trip on an intentional regression commit (verified by Codex F005). All 5 tests run in CI as part of `workbench-backend` (3 tests) and `workbench-frontend` (2 tests) workflows.

Acceptance:

1. `docs/dev/workbench-testing-strategy.md` ≤ 200 lines, covers L1/L2/L3 + safety + fixture-first + framework v0.9.21 #1 reference.
2. All 5 safety regression tests written and green on the F003 commit.
3. Each test demonstrably fails when the boundary is intentionally violated (Codex F005 verifies this with throwaway commits).
4. Tests are named so the failure surface is self-explanatory (e.g., `test_no_broker_sdk_imports.py::test_alpaca_not_imported_anywhere`).

### F004 — OpenAPI ↔ TypeScript types pipeline + CI drift check

Executor: generator.

Add `workbench/frontend/scripts/generate-types.sh` that:

1. Starts backend uvicorn in background.
2. Curls `/openapi.json` to a temp file.
3. Runs `npx openapi-typescript /tmp/openapi.json -o workbench/frontend/src/types/api.ts`.
4. Stops backend.
5. `git diff --exit-code workbench/frontend/src/types/api.ts` (used in CI to detect drift).

Add a CI step in `workbench-frontend.yml` that runs the script and fails the build if the generated `api.ts` differs from the committed version.

The placeholder Home page in F001 must consume the generated `/health` type to prove the pipeline is wired end-to-end.

Acceptance:

1. `bash workbench/frontend/scripts/generate-types.sh` is idempotent (running twice produces identical output).
2. CI drift check passes on F004 commit.
3. CI drift check fails on a throwaway commit that changes the backend `/health` schema without regenerating types (verified by Codex F005).
4. Home page renders typed data from `/health` (TypeScript compiler verifies the type is consumed).

### F005 — Dev docs + branch-protection guidance + Codex L1 verification + signoff

Executor: codex.

Write `docs/dev/branch-protection-guidance.md` documenting the GitHub branch-protection rules the user is asked to configure manually (see §Branch protection above).

Write `docs/dev/workbench-architecture.md` skeleton covering:

- Project structure (`workbench/{backend,frontend}` overview)
- Backend: FastAPI app factory + settings allowlist + safety guards
- Frontend: Next.js App Router placeholder + disclaimer Footer + types/api.ts pipeline
- CI: two workflows + caching + safety guard placement
- Cross-references: ADR `2026-05-15-workbench-direction.md` + B021 / B022 / B023 specs (B021 / B022 specs may not yet exist; cross-reference is forward-looking)
- Boundaries reaffirmed: pure stdlib `trade/` + isolated workbench/ deps + no broker SDK + research-only disclaimer + cloud-deploy is B021's concern not B020's

Codex verification checklist (mandatory, all must pass):

1. From a clean `git clone`, follow `workbench/README.md` and reach a running backend + frontend in ≤ 10 minutes (record actual time + commands run).
2. `pytest workbench/backend/tests/` green; `ruff check workbench/backend` clean; `mypy workbench/backend` clean.
3. `npm test --prefix workbench/frontend` green; `npm run lint --prefix workbench/frontend` clean; `npm run typecheck --prefix workbench/frontend` clean.
4. `npx playwright test --prefix workbench/frontend` green; HTML report renders.
5. CI green on the verification commit; both workflows.
6. Trip-test each of the 5 safety regression tests with throwaway commits in a side branch (e.g., add `import alpaca` to a backend file → `test_no_broker_sdk_imports.py` fails); confirm tests fail as designed; revert.
7. Trip-test the OpenAPI drift check by changing the backend `/health` response schema in a side branch without regenerating types; confirm CI fails; revert.
8. Existing `trade/` test suite unchanged and green.

Codex writes `docs/test-reports/B020-dev-infrastructure-signoff-2026-MM-DD.md` using `framework/templates/signoff-report.md`. Signoff records scope, verification commands & results, the 5 trip-test outcomes, and the standard research-only disclaimer. Update `progress.json`: `status → done`, `docs.signoff` set, `evaluator_feedback` summarizes.

## Out of Scope

- Google OAuth / NextAuth / any authentication. Deferred to **B021**.
- SQLite / Alembic / Repository data layer. Deferred to **B021**.
- Dockerfile / systemd / nginx / certbot / cloud deployment. Deferred to **B021**.
- GitHub Actions deploy job (the SSH-deploy CI/CD pipeline). Deferred to **B021**.
- Backup automation / GCS / observability tooling. Deferred to **B021**.
- shadcn/ui template clone, financial color palette, Inter / JetBrains Mono fonts, AG Grid, lightweight-charts, ECharts integration. All deferred to **B022 F001**.
- Any of the 7 workbench pages (Home / Strategies / Backtest / Reports / Recommendations / Snapshots / Backlog) beyond the F001 placeholder Home. Deferred to **B022**.
- Manual execution UI (target positions diff / order ticket / fill journal). Deferred to **B023**.
- Visual regression tests, Lighthouse performance budgets, Sentry error tracking. Out of all current planned batches; revisit only if real production use surfaces the need.

## Acceptance

Batch is **done** when:

1. F001 — F004 all green on `main`; both new CI workflows green; `trade/` CI workflow unchanged and green.
2. F005 Codex verification: all 8 checklist items pass; all 5 safety regression trip-tests pass; OpenAPI drift trip-test passes; signoff written.
3. `progress.json.status = done`; `docs.signoff` populated.
4. From a fresh `git clone`, a developer reaches a running workbench (backend + frontend + placeholder Home page with disclaimer visible) in ≤ 10 minutes following `workbench/README.md`.
5. No business logic, no UI pages beyond placeholder Home, no broker SDK, no auth, no cloud deployment introduced — those are explicitly B021 / B022 / B023's concerns.
6. `workbench/README.md`, `docs/dev/workbench-testing-strategy.md`, `docs/dev/workbench-architecture.md`, `docs/dev/branch-protection-guidance.md` all exist and pass `markdown-link-check` (or equivalent manual review).

_Disclaimer: research-only; never authorizes paper or live trading._
