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

## Acceptance — permanent recurring-invariant regressions (B071 F004)

| | Detail |
|---|---|
| Tool | `pytest` (golden real-data fixture, no DB) + `pytest` + `initialised_db` (DB / recommendation chain) |
| Where | `tests/acceptance/` (repo-root, pure engine) + `workbench/backend/tests/acceptance/` (DB) |
| Network | none — runs entirely on `data/fixtures/golden/` (committed real data) and in-process SQLite |
| CI step | `python-ci.yml` → "Run acceptance invariants"; `workbench-backend.yml` → "Pytest — acceptance invariants" (explicit, not folded into the implicit testpaths run) |

The acceptance tier is where a batch's **bespoke L2 real-data verification
becomes a permanent regression** — "验收即代码". It freezes the recurring
behaviour invariants the evaluator used to re-verify by hand each batch, run
deterministically on the golden fixture. The B071 seed set (6 invariants):
① ★N strategies same-window pairwise-distinct (B050) · ② weights + cash buffer
sum to 1 · ③ no negative cash (reconcile 409) · ④ single account source ·
⑤ Master backwards-compat (canonical 4-sleeve composition + regime default) ·
⑥ defensive shares × mark ≈ equity (golden SGOV).

Each acceptance invariant must have **teeth**: deliberately breaking the
invariant (mutation) must turn the corresponding test red. The evaluator
mutation-checks this (B071 F005) — an acceptance test that stays green when the
invariant is broken is worse than no test.

> **Convention — verification-as-code is standard going forward.** Every batch,
> the Generator (or an independent agent) writes that batch's **novel** L2
> real-data checks as acceptance assertions here, so they become permanent CI
> regressions instead of one-off Codex real-machine passes. This does **not**
> retire the independent adversarial review (铁律 4): because the assertions are
> written by the same side that writes the code, the review area is narrowed to
> the **novel / ambiguous** judgement, while the mechanical recurring invariants
> are CI-green by construction. (Role-context formalisation of this convention
> is a Planner item — see `framework/proposed-learnings.md`.)

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

### Golden real-data fixture (B071 F002 — fixture-first formal supplement)

`data/fixtures/golden/` is a committed **real-data** fixture: a frozen subset
of real Tiingo prices + real SEC EDGAR fundamentals (38 price tickers / 25 with
fundamentals, 2019-2023 covering the 2020 COVID + 2022 bear regimes, < 5 MB),
carved (not generated) from the gitignored `data/snapshots/` real-data files by
`data/fixtures/golden/_freeze.py`. See `data/fixtures/golden/README.md`.

It is the **fixture-first principle extended**, not violated: it lets CI run
**deterministic real-data backtest / recommendation assertions** (same input →
same output, no network, no random) — directly attacking the self-declared gap
above ("real-data reverify could only be a one-time Codex pass"). The recurring
invariants (N-strategy pairwise-distinct / weights sum to 1 / no negative cash /
defensive shares×mark≈equity / Master backwards-compat) become **permanent
acceptance regressions** under `tests/acceptance/` (B071 F003/F004), so they are
守一次永远守 instead of re-verified by hand each batch. The synthetic
`_generate.py` fixtures stay for their deterministic unit baselines; golden is a
*real-data* layer on top, never a replacement. The v0.9.21 #1 reverify rule
still governs **genuinely new** real-data shapes — golden only retires the
*recurring* real-data checks, not the novel ones.

## What this document doesn't try to do

- Visual regression / Lighthouse / Sentry — out of every currently
  planned batch (B020–B023); revisit if production usage demands.
- Cross-browser matrix beyond chromium — same.
- Load / soak / stress tests — Codex-owned, declared in
  `executor: codex` features; deliverable is a report under
  `docs/test-reports/`, not green CI.

_Disclaimer: research-only; never authorizes paper or live trading._
