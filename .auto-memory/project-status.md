---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留问题
type: project
---
## 当前状态
- **B027-real-data-snapshot-foundation：`done`**；F001 completed（11206ac）+ F002 completed（3d14413）+ F003 completed（Codex signoff）。Spec：`docs/specs/B027-real-data-snapshot-foundation-spec.md`；signoff：`docs/test-reports/B027-real-data-snapshot-foundation-signoff-2026-05-26.md`。
- Codex 复验结论：**PASS**。L1：backend `pytest 277 passed, 2 skipped` + `ruff` + `mypy` + alembic round-trip；frontend `vitest 166` + `build` + Playwright `38 passed`；artifact grep 未命中 `TIINGO_API_KEY` / Tiingo host 泄漏。
- L2：production `/api/health.version=49462d62428b78c7f4ec66f5c66a3ae833a30ea0`；本地 `HEAD=033d2f45163526129240e37f4cd1890223d57817`，diff 仅含 `progress.json` + `.auto-memory/project-status.md` 这 1 个 metadata commit，可接受。
- 真实 Tiingo smoke 已通过：VM 上按服务工作目录执行 `TiingoSnapshotLoader().health_check()` 返回 `True`；`tiingo_budget_log` 总 call_count `2 -> 3`，`DELTA=1`；production DB `alembic_version=0003_b027_tiingo_budget_log`。
- authenticated `/api/debug/recent-errors` 返回 `{"count":0,"records":[]}`；`/strategies` 页面仍命中 B026 synthetic banner 中文文案。截图证据已落盘：`docs/screenshots/B027-snapshot-foundation/{production-health,recent-errors,strategies-banner}.png`。
- 本批次目标完成：Tiingo Starter + Repository 抽象 + cost guard + budget log + production secret 注入全部闭环；**仍不做** backfill / 不切 sleeve / 不动 strategy 数据源（B028+ 责任）。
- 后续路径：B028（1.B 价格 backfill + `yfinance_loader.py` cross-check）→ B029（1.C 财务 SEC EDGAR）→ B030（1.D 全 sleeve 切真）→ 里程碑 A Layer 0→1。

## 已完成签收 + MVP 完工
- B001-B027 全部签收。MVP substantively 完成 (PRD §10/§11/§12) — 完工声明：`docs/prd/mvp-completion-declaration-2026-05-20.md`。
- 最近：B027 Real Data Snapshot Foundation signoff 2026-05-26；B026 Synthetic Data Banner signoff 2026-05-26；B025 US Quality Momentum signoff 2026-05-25。

## 生产状态
- `https://trade.guangai.ai` live with 双语 workbench + OAuth + `/api/health` + `/api/debug/recent-errors` + B026 synthetic data banner；B027 Tiingo foundation 已部署到 production。

## 永久硬边界（B027 起继续；v0.9.28 + B027 新增）
- 系统层：no-broker SDK / no-paper-or-live URL / no-credential（**Tiingo API key 走 secret 不入代码**）/ no-auto-execution / 多用户禁 / Cloud SQL 禁 / same-origin /api/* / auth-gated / Repository 读写非直 file
- UI 层：no-execution buttons + 中文等价禁词同级 / Order ticket Markdown 双语 disclaimer 永存 / **B026 banner 保留显示**
- 数据 / CI 层：fixture-first 离线 CI（CI 不调 live Tiingo）/ cloud-deploy workflow_dispatch + chore commit 后 dispatch deploy
- 新增：Tiingo API key 永不入前端/build/log；月预算 cap `$10` enforced（≥80% alert / ≥100% BudgetExceeded raise）
