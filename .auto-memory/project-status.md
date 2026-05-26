---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留问题
type: project
---
## 当前状态
- **B028-real-data-backfill：`reverifying`（fix-round 1）**；F001+F002+F003 completed + F004 pending（Codex 复验）。Spec：`docs/specs/B028-real-data-backfill-spec.md`。
- F004 fix-round 1：Codex 首轮 L2 blocker 是 Production HEAD drift。Root cause：F003 只动了 trade/ + scripts/，俩路径都在 workbench/{backend,frontend}/ 之外 → 双 CI paths-ignore → Workbench Deploy 没被 workflow_run 触发（v0.9.27 §12.7 prescribed workflow_dispatch）。修法：dispatch Workbench Deploy run 26429877249 success 2m。
- Production HEAD 现 == main HEAD == `15dfb4b`；db_connectivity ok；uptime 28s fresh restart；journal 干净（仅 /api/health probe + 我自己的 401 探针）。无产品代码改动；仅状态机推 reverifying + handoff 更新。
- L1 + functional L2 + backfill artifacts (52 vendor + 153386 unified rows) + cross-check 25/25 PASS + PIT spot check 与 Codex fix-round 0 报告一致不变。

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
