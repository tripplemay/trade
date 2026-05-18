---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留问题
type: project
---
## 当前状态
- **B023-workbench-phase2-manual-execution：`building`**；Generator 接 F001（3 张新表 order_ticket / fill_journal_entry / account_snapshot + Alembic migration 0002 + Repository + deploy.sh schema-assert 扩为 6 表 per v0.9.25 #1b），共 8 features 完成 0。预估 4-5 周。
- Spec：`docs/specs/B023-workbench-phase2-manual-execution-spec.md`
- 范围：闭合 monthly rebalance manual workflow — 5 新页（position-diff / ticket / fills / journal-history / account 编辑）+ slippage analytics + risk panel/kill-switch alert + Codex L2 18 项验收。**永久不连 broker**（B012 BrokerAdapter ABC 永久 unwired）。
- 后续路径：**B023 done = MVP 全 PRD §10/§11/§12 substantively 完成 for single-user manual-execution workbench**。之后是 BL-B011-S2（satellites 实现）+ BL-B013-D1/D2 等 post-MVP backlog。
- 关键决策（B023 加 / B021+B022 继承）：3 新表跟 B021 Repository 同 pattern；reconciliation 端到端 idempotent；CSV 上传 + 手工 entry 双轨；reconcile 后插 account_snapshot(source=fill_reconcile)；risk panel 红色时并排 normal+defensive ticket 让用户选。
- 硬边界：no-broker SDK / no-paper or live URL / no-credential / no-auto-execution / 多用户禁 / Cloud SQL 禁；任何按钮 labelled execute/place order/send to broker 禁；same-origin /api/* (v0.9.24 #3)；auth-gated；Repository 读写非直 file；framework v0.9.21-v0.9.25 全约束继续。
- L2 含 v0.9.25 #1d 真读+真写、新 §Production/HEAD 等价性、#3c /api/debug/recent-errors count=0 verify。

## 已完成签收
- B001-B022 全部已签收；最近：B022 workbench Phase 1 `docs/test-reports/B022-workbench-phase1-signoff-2026-05-18.md`

## 生产状态
- `https://trade.guangai.ai` live with B022 7 read-mostly 页 + 最小 write；OAuth gating；/api/health 6 字段；daily 03:00 UTC backup auto；workbench-deploy.yml CI/CD 全绿。B023 上线后再加 5 执行 workflow 页 + 3 新表。

## 已知 gap（非阻塞）
- Backlog: BL-B010-S1 low / **BL-B011-S2 high (MVP 完成后接 satellite)** / BL-B013-D1 low / BL-B013-D2 low。
- 本机 `python3` 为 3.9.6；所有检查必须用 `.venv/bin/python`。
- B021 soft-watch S1：非 allowlist 浏览器实测未做（无可用第二 Google 账号）；L1 已覆盖。
- B022 soft-watch S1：production version 与 HEAD 同步策略由 v0.9.25 §Production/HEAD 等价性 规则统管。
- framework/proposed-learnings.md 为空（v0.9.21-v0.9.25 共沉淀 13 条 5/15-5/18 候选）。

<!-- 覆盖写；保持 ≤30 行；只放 WHAT，不重复 progress.json 结构化字段。 -->
