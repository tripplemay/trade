# B025 US Quality Reverify3 Blocker 2026-05-25

## Scope
- F006 `reverifying` round 3
- L1 local rerun on current `main`
- L2 production VM re-check after Generator fix-round 3 deploy escape hatch

## Result
- `L1 PASS`
- `L2 FUNCTIONAL PASS / HARD FAIL`
- Remaining hard blocker is again `Production HEAD ≡ main HEAD`

## Evidence
- Current local / origin `main` HEAD:
  - `git rev-parse HEAD` → `f45ac462f4eb144bf7024b2ea311548e71502f08`
  - `git log --oneline -n 2` →
    - `f45ac46 chore(B025-F006): fix-round 3 complete, status→reverifying`
    - `afa154d ci(deploy): add workflow_dispatch trigger so chore-only main SHAs can deploy`
- Production health:
  - `curl -sS https://trade.guangai.ai/api/health`
  - Response `version` = `afa154dc958033a2b426759544466ff763d4fdd0`
- Therefore production is healthy but not equal to current `main`

### L1 local verification
- Local stack had a stale pre-reverify process on `3000/8723`; first Playwright run failed against that old runtime.
- After killing the stale processes and restarting via the required flow:
  - `NEXTAUTH_SECRET=codex-local-test-secret ALLOWED_USER_EMAIL=codex@example.com bash scripts/test/codex-setup.sh`
  - backend startup log reported `version":"f45ac46"`
- Full local gates:
  - backend `pytest tests -q` → `241 passed, 2 skipped`
  - backend `ruff check .` → pass
  - backend `mypy workbench_api tests` → pass
  - trade `pytest tests -q` → `727 passed`
  - trade `mypy trade` → pass
  - frontend `npm run lint` / `npm run typecheck` / `npm test` (`157 passed`) / `npm run build` / `npm audit --omit=dev --audit-level=high` → pass
  - artifact grep on `.next/static` → no localhost backend host
  - focused rerun on the previously flaky suite after restart:
    - `NEXTAUTH_SECRET=codex-local-test-secret ALLOWED_USER_EMAIL=codex@example.com npx playwright test tests/e2e/b025-us-quality-bilingual.spec.ts`
    - Result: `14 passed`

### L2 production functional verification
- With `__Secure-authjs.session-token`, both locales rendered correctly on:
  - `/strategies`
  - `/recommendations`
  - `/risk`
  - `/reports`
  - `/reports/B025-us-quality-momentum-backtest`
- `GET /api/debug/recent-errors` returned:
  - `200 {"count":0,"records":[]}`
- Locale switch focused minimal repro on production:
  - zh-CN `/strategies` → switch to `en` → `US Quality Momentum`
  - navigate to `/risk` → English subtitle persists
  - repeated repro `3/3` succeeded with `NEXT_LOCALE=en`

## Required Action
- Generator / deploy owner must redeploy current `main@f45ac462f4eb144bf7024b2ea311548e71502f08` to production.
- After deploy, re-check only:
  - `https://trade.guangai.ai/api/health.version == f45ac462f4eb144bf7024b2ea311548e71502f08`
  - one smoke pass of `/strategies`, `/risk`, `/reports`, `/api/debug/recent-errors`

## Conclusion
- Do **not** sign off B025 F006 in this round.
- Functional acceptance is green; deployment hash equivalence is still red.
