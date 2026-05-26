---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留问题
type: project
---
## 当前状态
- **B028-real-data-backfill：`done`**；F001-F004 全部 completed。Spec：`docs/specs/B028-real-data-backfill-spec.md`；signoff：`docs/test-reports/B028-real-data-backfill-signoff-2026-05-26.md`。
- Codex 复验结论：**PASS**。focused L2 blocker（production HEAD drift）已解除：production `/api/health.version=15dfb4bfcc4100b1bd1ec0755208ed8ee054fa42`；本地 `HEAD=0cad66558308e08c0d0b2b470115f6ccf197cd6e`，diff 仅含 `progress.json` + `.auto-memory/project-status.md` 这 1 个 metadata commit，可接受。
- production 功能面通过：authenticated `/api/debug/recent-errors` 返回 `{"count":0,"records":[]}`；`/strategies` 仍命中 B026 banner 文案 `研究原型 · 仅含合成数据 · 不构成投资决策依据`。
- L1 与本机 backfill 证据保留：backend `pytest 304 passed, 2 skipped` + `ruff` + `mypy`；frontend `vitest 166` + `build` + Playwright `38 passed`；`data/snapshots/prices/tiingo/` 共 `52` 文件；unified `prices_daily.csv` 共 `153386` 行；cross-check 报告 `25/25 PASS`；SPY PIT spot-check `as_of=2020-03-01 -> max date 2020-02-28`。
- 截图证据已落盘：`docs/screenshots/B028-backfill/{snapshots-structure,cross-check-report,spy-pit-spotcheck}.png`。
- 本批次目标完成：历史价格 backfill、双层 storage、yfinance 抽样背书与 PIT loader enforcement 全部闭环；strategy 代码仍未切到真实数据路径，留 B030。
- 后续路径：B029（1.C 财务 SEC EDGAR）→ B030（1.D 全 sleeve 切真 + reports/ fixture vs real 对比）→ 里程碑 A Layer 0→1。

## 已完成签收 + MVP 完工
- B001-B028 全部签收。MVP substantively 完成 (PRD §10/§11/§12) — 完工声明：`docs/prd/mvp-completion-declaration-2026-05-20.md`。
- 最近：B028 Real Data Backfill signoff 2026-05-26；B027 Real Data Snapshot Foundation signoff 2026-05-26；B026 Synthetic Data Banner signoff 2026-05-26。

## 生产状态
- `https://trade.guangai.ai` live with 双语 workbench + OAuth + `/api/health` + `/api/debug/recent-errors` + B026 synthetic data banner；production 已追到 B028 deploy SHA `15dfb4b`。

## 永久硬边界（B028 起继续）
- 系统层：no-broker SDK / no-paper-or-live URL / no-credential（API key 走 secret 不入代码）/ no-auto-execution / 多用户禁 / Cloud SQL 禁 / same-origin /api/* / auth-gated / Repository 读写非直 file
- UI 层：no-execution buttons + 中文等价禁词同级 / Order ticket Markdown 双语 disclaimer 永存 / **B026 banner 保留显示**
- 数据 / CI 层：fixture-first 离线 CI（CI 不调 live vendor）/ pyproject runtime-vs-dev hygiene（v0.9.29 §12.8）/ cloud-deploy workflow_dispatch + chore commit 后 dispatch deploy
- 新增：Tiingo API key 永不入前端/build/log；月预算 cap `$10` enforced（≥80% alert / ≥100% BudgetExceeded raise）
