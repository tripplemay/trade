# B025 US Quality Reverify2 Blocker 2026-05-25

## Scope
- F006 `reverifying` round 2
- L1 full rerun on local `localhost:3099`
- L2 production VM verification for `https://trade.guangai.ai`

## Result
- `L1 PASS`
- `L2 PARTIAL PASS / HARD FAIL`
- Hard blocker is unchanged from the batch boundary: **Production HEAD must equal `main` HEAD**, but production is still serving `0b61dda` while local `main` is `7bb25f4`.

## Evidence
- Local HEAD:
  - `git rev-parse HEAD` → `7bb25f45339065eaca1ed27fe89d5bd005c8188a`
- Production health/version:
  - `curl -sS https://trade.guangai.ai/api/health`
  - Response: `{"status":"ok","version":"0b61dda9a17ebf6d7cdec9626f716d7e7d18ebef","db_connectivity":"ok",...}`
- Production service logs confirm old boot artifact:
  - `ssh tripplezhou@34.180.93.185 "sudo systemctl status workbench-backend.service --no-pager -n 20"`
  - Backend startup log: `workbench started","version":"0b61dda9a17ebf6d7cdec9626f716d7e7d18ebef"`
- L1 local gates all green:
  - backend: `pytest tests -q` → `241 passed, 2 skipped`
  - backend: `ruff check .` → pass
  - backend: `mypy workbench_api tests` → pass
  - trade: `pytest tests -q` → `727 passed`
  - trade: `mypy trade` → pass
  - fixture regressions: `tests/unit/test_us_quality_fixture.py` `25 passed`; `tests/unit/test_us_quality_factors.py` `24 passed`
  - frontend: `npm run lint` / `npm run typecheck` / `npm test` (`157 passed`) / `npm run build` / `npm audit --omit=dev --audit-level=high` → pass
  - artifact grep: `.next/static` contains no backend localhost URL
  - Playwright: `npx playwright test` → `33 passed`
- L2 production functional checks on old deploy mostly pass when using the production cookie name `__Secure-authjs.session-token`:
  - zh-CN `/strategies` → `美股质量动量`
  - en `/strategies` → `US Quality Momentum`
  - zh-CN + en `/recommendations` both expose `risk-sleeve-satellite_us_quality`
  - zh-CN + en `/risk` both render expected bilingual subtitle
  - zh-CN + en `/reports` list shows `report-link-B025-us-quality-momentum-backtest`
  - zh-CN + en `/reports/B025-us-quality-momentum-backtest` both contain `research-only` + `仅供研究使用`
  - locale switch focused repro `3/3` passed: zh-CN → en, cookie persisted to `/risk`
  - `GET /api/debug/recent-errors` with signed session cookie → `200 {"count":0,"records":[]}`
- Important deploy drift detail:
  - Production frontend rejected plain `authjs.session-token` and redirected `/strategies` to `/login?callbackUrl=%2Fstrategies`
  - The same signed token worked once sent as `__Secure-authjs.session-token`
  - This is another symptom that the running production bundle/config is not identical to current `main`

## Required Action
- Generator / deploy owner must deploy `main@7bb25f4` to production and restart both `workbench-backend.service` and `workbench-frontend.service`.
- After deploy, re-check:
  - `/api/health.version == 7bb25f45339065eaca1ed27fe89d5bd005c8188a`
  - protected routes still render with `__Secure-authjs.session-token`
  - locale switch persists across `/strategies -> /risk`

## Conclusion
- Do **not** sign off B025 F006 in this round.
- Reason: functional surface is largely healthy, but the hard acceptance gate `Production HEAD ≡ main HEAD` is failing on the real VM.
