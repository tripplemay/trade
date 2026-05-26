---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留问题
type: project
---
## 当前状态
- **B027-real-data-snapshot-foundation：`reverifying`（fix-round 1）**；F001 completed（11206ac）+ F002 completed（3d14413）+ F003 pending（Codex 复验）。Spec：`docs/specs/B027-real-data-snapshot-foundation-spec.md`。
- Generator fix-round 1（commit 468d380 + 49462d6）：(1) 把 `httpx>=0.27` 从 `[project.optional-dependencies].dev` 提到 `[project].dependencies` 让 production wheel install 包含；(2) `TiingoSnapshotLoader.health_check()` 也走 `MonthlyBudgetGuard.check_and_increment`（F002 之前只 fetch_daily_bars 过 guard，spec F003 L2 §7 要求 health_check 也 +1）。
- 加 safety regression：`tests/safety/test_runtime_dependencies_pinned.py` 用 AST 扫每个 `workbench_api/` 源，断言所有 top-level 第三方 import 都在 `[project].dependencies`；并单独 pin `httpx` 在 runtime set 防回退。
- 生产 smoke 已端到端通过：VM `import httpx` OK / `TiingoSnapshotLoader().health_check()` 真调 Tiingo 返回 True / `tiingo_budget_log` +1 row (date=2026-05-26 / call_count=1 / cost=5e-05)；production HEAD == main HEAD == `49462d6`。
- L1 本地 gates：backend pytest 277+2 skipped（B026 baseline 243+2 → +34 net B027 specs；包含 fix-round 1 的 +4）/ ruff + mypy 清 on 132 source files / trade pytest 727 + frontend vitest 166 unchanged。

## 已完成签收 + MVP 完工
- B001-B026 全部签收。MVP substantively 完成 (PRD §10/§11/§12) — 完工声明：`docs/prd/mvp-completion-declaration-2026-05-20.md`。
- 最近：B026 Synthetic Data Banner signoff 2026-05-26；B025 US Quality Momentum signoff 2026-05-25。

## 生产状态
- `https://trade.guangai.ai` live with 双语 workbench + OAuth + `/api/health` + `/api/debug/recent-errors` + B026 synthetic data banner。

## 永久硬边界（B027 起继续；v0.9.28 + B027 新增）
- 系统层：no-broker SDK / no-paper-or-live URL / no-credential（**Tiingo API key 走 secret 不入代码**）/ no-auto-execution / 多用户禁 / Cloud SQL 禁 / same-origin /api/* / auth-gated / Repository 读写非直 file
- UI 层：no-execution buttons + 中文等价禁词同级 / Order ticket Markdown 双语 disclaimer 永存 / **B026 banner 保留显示**
- 数据 / CI 层：fixture-first 离线 CI（CI 不调 live Tiingo）/ cloud-deploy workflow_dispatch + chore commit 后 dispatch deploy
- 新增：Tiingo API key 永不入前端/build/log；月预算 cap `$10` enforced（≥80% alert / ≥100% BudgetExceeded raise）
