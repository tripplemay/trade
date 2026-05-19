---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留问题
type: project
---
## 当前状态
- **MVP `done` ✅ + 进入 observation 期（用户决策 2026-05-20）**。B023 Workbench Phase 2 已签收 `docs/test-reports/B023-workbench-phase2-signoff-2026-05-19.md`（3 fix-rounds，L1 全绿 + L2 真 VM 18 项真读+真写闭环；Production HEAD = main HEAD `d0ae21f`；0 新 framework learnings）。完工声明：`docs/prd/mvp-completion-declaration-2026-05-20.md`。
- **下一批次：暂停**（用户决策）。让 MVP 在生产跑 1-2 个月度 rebalance 周期收集真实使用反馈，再决定 post-MVP 路径（候选 B024 = BL-B011-S2 US Quality / HK-China satellite）。Planner standby；无 active 批次。

## 已完成签收
- B001-B023 全部已签收。最近 3 批：B021 (cloud deploy + auth)、B022 (workbench phase 1)、B023 (manual execution UI)。
- MVP 实际批次链路：B001/B002 规划 → B003-B007 engine + global ETF backtest → B010 risk parity → B011 master portfolio → B012 paper-trading prep（BrokerAdapter ABC 永久 unwired）→ B013/B015/B016 strat refinements → B018/B019 attribution + retune → B020-B023 workbench 4 批次 → 落 cloud。

## 生产状态
- `https://trade.guangai.ai` live，B022 7 read-mostly 页 + B023 5 execution workflow 页 + 6 表 + OAuth gating + /api/health 6 字段 + /api/debug/recent-errors 全部健康。daily 03:00 UTC backup auto；workbench-deploy.yml 全绿。生产 HEAD = main HEAD（v0.9.25 §Production/HEAD 等价性 规则统管）。

## 永久硬边界（MVP 后继续）
no-broker SDK / no-paper-or-live URL / no-credential / no-auto-execution / 多用户禁 / Cloud SQL 禁 / 任何按钮 labelled execute/place order/send to broker 禁 / same-origin /api/* / auth-gated / Repository 读写非直 file / framework v0.9.21-v0.9.25 全约束。

## post-MVP backlog（按优先级）
- **BL-B011-S2 high**（US Quality Momentum + HK-China ETF satellite 实现 — 两个独立 spec）— 用户已标 high 等接 satellite。
- BL-B010-S1 low / BL-B013-D1 low (smoothed vol) / BL-B013-D2 low (VIX overlay)。
- 新加：BL-B023-S1 low（生产 target_positions 空 → 准备最小 seed 后跑常规非 defensive 票据冒烟）+ BL-B023-S2 low（risk-panel kill-switch UI 演练 with red sample fixture）。

## 已知 gap（非阻塞）
- 本机 `python3` 为 3.9.6；所有检查必须用 `.venv/bin/python`。
- B021 soft-watch S1：非 allowlist 浏览器实测未做（无可用第二 Google 账号）。
- framework/proposed-learnings.md 当前空（v0.9.21-v0.9.25 沉淀完成；B023 零新候选）。

<!-- 覆盖写；保持 ≤30 行；只放 WHAT，不重复 progress.json 结构化字段。 -->
