# B030 Real Data Cutover Blocker 2026-05-27

## Scope
- F004 first-round verification
- L1 local verification for B030 F001-F003
- L2 production-focused verification for milestone A Layer 0→1

## Result
- `L1 FAIL`
- `L2 FAIL`

## Evidence

### Production hash gate is healthy
- `git rev-parse HEAD` → `169fb5ff447ae177ae10540fd9d0a4adce73fd59`
- `curl -fsS https://trade.guangai.ai/api/health`
- Response `version` = `169fb5ff447ae177ae10540fd9d0a4adce73fd59`

### Green gates
- backend: `env -u ALL_PROXY -u all_proxy -u HTTPS_PROXY -u https_proxy -u HTTP_PROXY -u http_proxy -u NO_PROXY -u no_proxy ../../.venv/bin/python -m pytest -q` → `400 passed, 2 skipped`
- backend: `../../.venv/bin/ruff check .` → pass
- backend: `../../.venv/bin/python -m mypy workbench_api tests` → pass
- trade default path: `./.venv/bin/python -m pytest tests -q` → `778 passed`
- trade fixture lock: `FORCE_FIXTURE_PATH=1 ./.venv/bin/python -m pytest tests -q` → `778 passed`
- trade: `../.venv/bin/python -m mypy .` → pass
- frontend: `npm test` → `166 passed`
- frontend: `npm run build` → pass
- frontend: `npm audit --omit=dev --audit-level=high` → only `moderate` advisories
- local Playwright (with test auth env): `NEXTAUTH_SECRET=codex-local-test-secret ALLOWED_USER_EMAIL=codex@example.com npx playwright test` → `38 passed`
- local backend health: `curl --noproxy '*' -fsS http://127.0.0.1:8723/api/health` → `{"status":"ok","version":"169fb5f","db_connectivity":"ok",...}`
- production recent errors: authenticated `GET /api/debug/recent-errors` → `{"count":0,"records":[]}`
- local reports present:
  - `reports/fixture_vs_real/overview_2026-05-27.md`
  - `reports/fixture_vs_real/master_2026-05-27.md`
  - `reports/fixture_vs_real/us_quality_2026-05-27.md`

### Non-blocking harness drift observed during L1
- `scripts/test/codex-setup.sh` still starts frontend without test auth env, so local protected-route / Playwright validation fails closed with Auth.js `MissingSecret` unless the caller explicitly injects:
  - `NEXTAUTH_SECRET=codex-local-test-secret`
  - `ALLOWED_USER_EMAIL=codex@example.com`
- `AGENTS.md` still states Codex local validation runs on `localhost:3099`, but the active local harness and Playwright config operate on `3000/8723`.
- These are environment-contract / harness drift issues, not the primary product blocker for this round.

### Hard blocker 1: F001 acceptance floor is still unmet
- `docs/test-reports/B030-pit-validation-2026-05-27.md` headline result:
  - unified fundamentals rows: `853`
  - expected floor: `>=1000`
  - zero-row tickers remain: `BAC`, `V`
- The same report marks F001 acceptance as:
  - `§(4) Rerun produces ≥1000 unified rows` → `Partial`
  - `§(5) 6 sector ticker × 5 fiscal_quarter cross-check 8 ratio non-zero` → `Partial`
- This is not just a soft-watch note; it is an explicit miss against the written F001 floor.

### Hard blocker 2: production banner is still live
- Acceptance requires B026 synthetic banner to be disabled in production after B030 cutover.
- Production authenticated pages still expose the banner text:
  - `curl -fsS --cookie "__Secure-authjs.session-token=<token>" https://trade.guangai.ai/strategies | grep -o '研究原型 · 仅含合成数据 · 不构成投资决策依据'`
  - output: `研究原型 · 仅含合成数据 · 不构成投资决策依据`
  - same direct hit on `https://trade.guangai.ai/reports`
- Production SSR/RSC payload for protected pages still includes the client component:
  - `SyntheticDataBanner`
  - observed in authenticated HTML payload for `/strategies` and `/reports`
- This means the Layer 0 warning surface is still shipped in production, so milestone A Layer 0→1 is not yet complete.

### Production surfaces that otherwise look healthy
- authenticated `GET /api/recommendations/current` → `{"as_of_date":"2026-05-26","target_positions":[],"gate_checks":[...],"account_present":false}`
- authenticated `GET /api/strategies` returns live strategy list including:
  - `B025-us-quality-momentum`
- authenticated `GET /api/reports` includes:
  - `B030-pit-validation`
  - `B029-fundamentals-snapshot-signoff`
- local compare reports show non-empty real-data metrics:
  - `us_quality` real Sharpe `1.17`, max drawdown `-41.98%`
  - `master` real annual return `8.37%`, Sharpe `0.83`

## Required Action
- Generator must address both blockers before Codex can sign off:
  1. resolve the B030 F001 fundamentals floor miss, or revise the spec via Planner decision before re-entry
  2. make production actually stop rendering / shipping the B026 synthetic banner surface

## Conclusion
- Do **not** sign off B030 F004 in this round.
- Current state is not Layer 1 complete:
  - fundamentals backfill floor is still below spec
  - production still behaves as if the synthetic-data banner close-out has not landed
