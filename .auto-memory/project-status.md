---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留问题
type: project
---
## 当前状态
- **B028-real-data-backfill：`fixing`**；F001 completed + F002 completed + F003 completed + F004 pending。Spec：`docs/specs/B028-real-data-backfill-spec.md`；blocker：`docs/test-reports/B028-real-data-backfill-blocker-2026-05-26.md`。
- Codex 首轮验收结论：**L1 PASS / L2 FAIL**。L1：backend `pytest 304 passed, 2 skipped` + `ruff` + `mypy`；trade `mypy` 通过（`trade pytest` 当前为空套件）；frontend `vitest 166` + `build` + Playwright `38 passed`；artifact grep 未命中 `TIINGO_API_KEY` / Tiingo/Yahoo endpoint 泄漏。
- backfill / PIT spot-check 已通过：`data/snapshots/prices/tiingo/` 共 `52` 文件；`data/snapshots/prices/unified/prices_daily.csv` 共 `153386` 行；`docs/test-reports/B028-cross-check-2026-05-26.md` 为 `25/25 PASS`；`load_prices(['SPY'], as_of=2020-03-01)` 最大日期 `2020-02-28`，PIT 过滤正确。
- production 功能面未见回归：`/api/debug/recent-errors` 返回 `{"count":0,"records":[]}`；`/strategies` 仍命中 B026 banner 文案。
- **当前唯一硬 blocker：Production HEAD ≠ main HEAD。** production `/api/health.version=8338fc05d2fde18a487d11eb8c240c6bcbbaebb0`，本地 `HEAD=e730a0b498d5c0171414d549a7cb1ac17d0fcd5c`；diff 不仅含状态机文件，还包含 `trade/data/loader.py` 与 `scripts/validate_snapshot.py`，不能按 metadata-only 接受。
- Generator 下一步：让 production 追到当前 `main` HEAD；Codex 复验时只需重点重查 SHA 等价性、`/api/debug/recent-errors` 与 B026 banner，不必重跑全量本地 backfill 除非再有产品代码变更。

## 已完成签收 + MVP 完工
- B001-B027 全部签收。MVP substantively 完成 (PRD §10/§11/§12) — 完工声明：`docs/prd/mvp-completion-declaration-2026-05-20.md`。
- 最近：B027 Real Data Snapshot Foundation signoff 2026-05-26；B026 Synthetic Data Banner signoff 2026-05-26。

## 生产状态
- `https://trade.guangai.ai` live with 双语 workbench + OAuth + `/api/health` + `/api/debug/recent-errors` + B026 synthetic data banner；当前线上 SHA 仍停在 B028 F002 阶段的 `8338fc0`。

## 永久硬边界（B028 起继续）
- 系统层：no-broker SDK / no-paper-or-live URL / no-credential（API key 走 secret 不入代码）/ no-auto-execution / 多用户禁 / Cloud SQL 禁 / same-origin /api/* / auth-gated / Repository 读写非直 file
- UI 层：no-execution buttons + 中文等价禁词同级 / Order ticket Markdown 双语 disclaimer 永存 / **B026 banner 保留显示**
- 数据 / CI 层：fixture-first 离线 CI（CI 不调 live vendor）/ pyproject runtime-vs-dev hygiene（v0.9.29 §12.8）/ cloud-deploy workflow_dispatch + chore commit 后 dispatch deploy
- 新增：Tiingo API key 永不入前端/build/log；月预算 cap `$10` enforced（≥80% alert / ≥100% BudgetExceeded raise）
