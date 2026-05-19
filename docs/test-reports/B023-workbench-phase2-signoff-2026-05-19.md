# B023 Workbench Phase 2 Signoff 2026-05-19

> 状态：**PASS**
> 触发：F008 round-3 L1 通过后，继续完成 L2 真 VM 复验

## Scope

- L1 本地复验：`scripts/test/codex-setup.sh`、backend `pytest/ruff/mypy`、frontend `vitest/lint/typecheck/build`、`npm audit --omit=dev --audit-level=high`、Playwright protected-route/manual-execution 主路径
- L2 真 VM 验收：`trade.guangai.ai` 上的 auth、health、manual execution API 读写闭环、journal/slippage/debug、systemd 进程状态
- 不含范围：broker SDK / 自动下单 / 外部支付或通知 / 多用户路径

## Verification

- L1 PASS
  - `bash scripts/test/codex-setup.sh`
  - `.venv/bin/python -m pytest workbench/backend/tests -q` → `202 passed, 2 skipped`
  - `.venv/bin/python -m ruff check workbench/backend`
  - `.venv/bin/python -m mypy workbench/backend`
  - `cd workbench/frontend && npm test` → `117 passed`
  - `cd workbench/frontend && npm run lint`
  - `cd workbench/frontend && npm run typecheck`
  - `cd workbench/frontend && npm run build`
  - `cd workbench/frontend && npm audit --omit=dev --audit-level=high` → exit `0`
  - `cd workbench/frontend && NEXTAUTH_SECRET=codex-local-test-secret ALLOWED_USER_EMAIL=codex@example.com npx playwright test tests/e2e/protected-routes.spec.ts tests/e2e/home-loads.spec.ts tests/safety/disclaimer-present.spec.ts` → `19 passed`
- L2 PASS
  - `GET https://trade.guangai.ai/api/health` → `status=ok`, `db_connectivity=ok`, `version=d0ae21f601320ff2356ac179431d029e76612d58`
  - `GET /api/protected-test` with minted Auth.js HS256 cookie → `200 {"status":"ok","email":"tripplezhou@gmail.com"}`
  - `systemctl status workbench-backend.service` / `workbench-frontend.service` → 两个服务均 `active (running)`；frontend 版本 `Next.js 15.5.18`
  - `GET /api/recommendations/current` → `200`，但当前 `target_positions=[]`
  - `GET /api/execution/account/latest` 初始为 `null`
  - 受控写入：`PUT /api/execution/account` 写入临时种子快照 `cash=900, positions=[SPY 1 @ 100]` → `200 snap-7b352b648707`
  - `GET /api/execution/risk-panel` → `200`，当前返回 `risk_state=null`
  - `POST /api/execution/tickets {"defensive":true,...}` → `200 tkt-20260519-99d04c95`
  - `GET /api/execution/tickets/tkt-20260519-99d04c95` → 首条交易行为 `SELL SPY 1`
  - `GET /api/execution/tickets?limit=5&offset=0` → 新票据可见
  - `POST /api/execution/fills/csv` 上传 1 行 generic CSV (`SPY sell 0.01 @ 100`) → `200`, `matched=true`
  - `GET /api/execution/fills?ticket_id=tkt-20260519-99d04c95` → `count=1`
  - `POST /api/execution/reconcile/tkt-20260519-99d04c95` → `200 snap-95442cfdd407`, `already_reconciled=false`, `unmatched_lines=[]`
  - `GET /api/execution/journal-history?since=2026-05-01` → 新票据已落历史，`status=executed`, `fill_count=1`, `avg_bps=0.0`
  - `GET /api/execution/slippage-analytics?window=3m` → `200 {"rolling_avg_bps":0.0,"trend":[{"month":"2026-05","avg_bps":0.0,"fill_count":1}]}`
  - `GET /api/debug/recent-errors` → `200 {"count":0,"records":[]}`
  - 副作用恢复：`PUT /api/execution/account {"cash":0,"base_currency":"USD","positions":[]}` → `200 snap-84ac2e8b398a`
  - 恢复后 `GET /api/execution/account/latest` → 当前态为 `cash=0`, `positions=[]`

## High-level Findings

- round-3 修复后的本地 canonical boot 已稳定：`.venv` 依赖自愈、`alembic upgrade head` schema gate、frontend 依赖升级后 `npm audit --audit-level=high` 通过。
- 生产部署版本与签收时 `main` HEAD 完全一致，且 health / systemd / debug buffer 都健康。
- Manual execution 主链路在真 VM 上已完成真实读写闭环：auth → seed account → defensive ticket → CSV fill → reconcile → journal → slippage → cleanup。

## Production / HEAD 等价性

| 项 | 值 |
|---|---|
| Production version (from `/api/health.version`) | `d0ae21f601320ff2356ac179431d029e76612d58` |
| Main HEAD (`git rev-parse HEAD`) | `d0ae21f601320ff2356ac179431d029e76612d58` |
| Diff | `0 commits` |

## Ops 副作用记录

| Agent | 阶段 | 操作摘要 | 副作用对齐 | 用户授权 |
|---|---|---|---|---|
| Codex evaluator | reverifying | `PUT /api/execution/account` 写入临时种子快照 `SPY 1 @ 100 + $900 cash` | 完成 L2 后再 `PUT /api/execution/account` 恢复为 `cash=0, positions=[]`；ticket/fill/journal 留作验收证据 | 本轮用户“开始”授权 L2 |
| Codex evaluator | reverifying | `POST /api/execution/tickets` + `POST /api/execution/fills/csv` + `POST /api/execution/reconcile/{ticket_id}` | 产生 1 张测试票据 `tkt-20260519-99d04c95`、1 行 fill、1 条 journal/slippage 记录；属于受控验收证据，不再回滚 | 本轮用户“开始”授权 L2 |

## Soft-watch

| ID | 描述 | 风险等级 | 建议处置 |
|---|---|---|---|
| S1 | 生产 VM 当前 `recommendations/current.target_positions=[]`，且初始 `account/latest=null`，因此 L2 无法物理覆盖“普通 recommendation-driven ticket”路径，只能通过 `defensive=true` 路径完成真写验收。 | medium | 后续若要做日常 operator 演练，先准备最小 target positions 数据，再补一次非 defensive 票据冒烟。 |
| S2 | `risk-panel` 在当前空风险信号下返回 `risk_state=null` / `defensive_required=null`，这次未命中红色 kill-switch 场景。 | low | 后续若补 staging/rnd 风险样本，可单独做一次 kill-switch UI/API 演练。 |

## Framework Learnings

本批次无新的 framework learnings。

## Conclusion

可以签收。
