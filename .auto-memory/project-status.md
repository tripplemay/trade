---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留问题
type: project
---
## 当前批次
- **B003-mvp-product-prd：`done`**（定义 MVP 产品边界、用户流程和验收标准）
- Planner 4/4 done，Evaluator F005 PRD consistency review PASS
- Signoff: `docs/test-reports/B003-mvp-product-prd-signoff-2026-05-12.md`

## 上一批次（B001/B002 independent signoffs done）
- B001 signoff: `docs/test-reports/B001-independent-reverification-signoff-2026-05-12.md`
- B002 signoff: `docs/test-reports/B002-independent-signoff-2026-05-12.md`

## 生产状态
- Documentation-only batch; no product code, migration, deployment, or live broker operation.

## 路线图（如有）
- Next likely batches: B004 core engineering foundation, then B005 global ETF backtest MVP.

## 已知 gap（非阻塞）
- B004/B005 need fixture/mock-only CI and L1 guards for no live broker, PIT, paper/live boundaries, and AI no-buy behavior.

## Backlog（延后）
- No known evaluator-blocking backlog item after B001/B002 independent signoffs.

<!-- 写入规则（来自 harness-rules.md §记忆分层）：
1. 覆盖写，不追加；保持 ≤30 行
2. 所有角色都可写，谁产生变更谁更新
3. 内容边界：只放 WHAT（会变的事实），不放 HOW（行为规范，那是 role-context 的事）
4. 不重复 progress.json 已有的结构化数据（status/completed_features/fix_rounds 等）
-->
