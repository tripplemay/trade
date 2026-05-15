# Workbench Testing Strategy

Status: B020 — Dev Infrastructure (initial draft, expanded as later batches
add the surfaces it talks about).

This document is the canonical reference for how the workbench is tested.
Three correctness layers (L1 / L2 / L3) plus a separate hard-boundary
guard tier. Every layer runs in CI; every layer has a "where to write it"
home in the repo so future contributors don't have to guess.

## Principles

1. **Fixture- and mock-first.** Real network, real broker APIs, real cloud
   storage never run in CI. Tests that need realistic data point at
   committed fixtures or in-process fakes. The framework v0.9.21 lesson
   #1 ("synthetic vs. real reversal warning") is in effect: any feature
   that requires a real-data reverify gets one explicit Codex pass
   against a recent live dataset before signoff. Day-to-day development
   never touches the live wire.
2. **One assertion per assertion.** Tests fail with a clear "which
   contract broke" surface — names are self-explanatory
   (`test_alpaca_not_imported_anywhere`) and the failure surface labels
   which layer / boundary tripped.
3. **CI matches local.** If a check passes locally and fails in CI, the
   pipeline is broken — not the developer. The `workbench/README.md`
   "Zero-to-running" sequence is the canonical command set and matches
   what the workflows run.
4. **Boundary tests are not feature tests.** A red `tests/safety/*` is a
   hard-policy breach, not a regression — review them like security
   findings, not flaky tests.

## L1 — Unit

| | Backend | Frontend |
|---|---|---|
| Tool | `pytest` | `vitest` |
| Where | `workbench/backend/tests/unit/` | `workbench/frontend/tests/unit/` |
| Network | none | none |
| Globals / I/O | pure functions, mocked deps | `environment: "node"`, no DOM |
| CI step | `workbench-backend.yml` → "Pytest — unit" | `workbench-frontend.yml` → "Vitest unit" |

L1 isolates the smallest correctness-bearing units: a function, a
component prop contract, a constant, a typed model. No HTTP, no DB, no
filesystem beyond what the test owns. Both runners default to fast
parallel execution.

## L2 — Integration

| | Backend | Frontend |
|---|---|---|
| Tool | `pytest` + `httpx.AsyncClient` / `TestClient` | `vitest` with mocked API clients, OR Playwright against a running backend |
| Where | `workbench/backend/tests/integration/` (created when the first integration test lands) | `workbench/frontend/tests/integration/` (same) |
| Network | in-process FastAPI, no external | mocked fetch / `msw`, or local backend |
| CI step | extends "Pytest — unit" step; merged in the same workflow | runs inside Vitest before Playwright |

L2 exercises the contract between modules: a FastAPI route + the
service it calls, a hook + a fake `fetch`, a Playwright spec that hits
a real `npm run dev` server. Anything that crosses the API surface
belongs here.

## L3 — End-to-end

| | Detail |
|---|---|
| Tool | Playwright (chromium only in B020) |
| Where | `workbench/frontend/tests/e2e/` |
| Pattern | `start-server-and-test "npm run dev -- --port 3000" http://127.0.0.1:3000 "npx playwright test"` |
| Browsers | chromium only B020 — Firefox / WebKit considered when a real cross-browser bug appears |
| CI step | `workbench-frontend.yml` → "Playwright E2E smoke"; HTML report + screenshots + video upload on failure |

L3 is the smallest realistic user trip — load a route, click a thing,
read what came back. The chromium-only choice in B020 is a CI wall-time
tradeoff; rebalance only when a customer-facing bug shows up that
chromium would miss.

## Safety boundary guards

Hard-policy enforcement, separate from feature tests. A red guard is a
breach, not a regression.

| Guard | Path | Surface protected |
|---|---|---|
| Broker SDK imports (backend) | `workbench/backend/tests/safety/test_no_broker_sdk_imports.py` | No `ib_insync`, `alpaca`, `alpaca_trade_api`, `futu`, `tiger`, `tradier`, `polygon`, `oandapy`, `tradeapi` reachable from workbench backend |
| Paper / live API URLs (backend) | `tests/safety/test_no_paper_or_live_urls.py` | No literal references to `paper-api.alpaca.markets`, `api.alpaca.markets`, `paper.gateway.ibkr.com`, `gw.gateway.ibkr.com`, `api.futu.com`, `api.tigerbrokers.com` |
| Settings env-var allowlist | `tests/safety/test_settings_env_allowlist.py` | `workbench_api.settings` reads only env vars in `ALLOWED_ENV_VARS` (empty in B020) |
| Broker SDK imports (frontend) | `workbench/frontend/tests/safety/no-broker-sdk-imports.spec.ts` | No `@alpaca/*`, `ib-insync`, `futu-api`, `tiger-securities` (or comparable) under `src/` or in `package.json` |
| Disclaimer present (frontend) | `tests/safety/disclaimer-present.spec.ts` | Every navigable route renders the canonical disclaimer (B020: just `/`) |

The backend guards run in `workbench-backend.yml` → "Pytest — safety
boundary guards". The frontend guards run alongside unit / E2E in
`workbench-frontend.yml`.

When a guard trips, do **not** add an exception — first investigate the
import / URL / env var and confirm it is legitimately needed for the
research-only mission. If it is, the spec needs an explicit decision in
ADR + the guard updated in the same PR. The default answer is "remove
the offender."

## Fixture and mock policy

- Realistic-shaped test data lives under `workbench/backend/tests/fixtures/`
  (created when the first fixture lands; see existing `trade/`
  fixtures for the format precedent).
- For external services the workbench will integrate with in B021+
  (broker paper API, Google OAuth, GCS), tests use in-process fakes
  and never reach the live endpoint in CI.
- Generator's `framework/proposed-learnings.md` lesson v0.9.21 #1
  remains in force: any feature whose correctness depends on real
  upstream data shape gets a Codex-driven real-data reverify before
  signoff. Day-to-day CI never escapes the fixtures.

## What this document doesn't try to do

- Visual regression / Lighthouse / Sentry — out of every currently
  planned batch (B020–B023); revisit if production usage demands.
- Cross-browser matrix beyond chromium — same.
- Load / soak / stress tests — Codex-owned, declared in
  `executor: codex` features; deliverable is a report under
  `docs/test-reports/`, not green CI.

_Disclaimer: research-only; never authorizes paper or live trading._
