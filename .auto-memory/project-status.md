---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留问题
type: project
---
## 当前状态
- **B003-mvp-product-prd：`done`**；MVP PRD 已独立签收。
- 当前无 active batch，`backlog.json` 为空。

## 已完成签收
- B001 strategy roadmap: `docs/test-reports/B001-independent-reverification-signoff-2026-05-12.md`
- B002 data/broker specs: `docs/test-reports/B002-independent-signoff-2026-05-12.md`
- B003 MVP PRD: `docs/test-reports/B003-mvp-product-prd-signoff-2026-05-12.md`

## 生产状态
- Documentation-only so far; no product code, migrations, deployment, broker API, secrets, or live-money operation.

## 下一步建议
- Next Planner should open **B004-core-engineering-foundation**.
- B004 should produce engineering docs/spec first: Python package boundary, config, fixture policy, pytest/ruff/CI, no-live guards, frontend architecture plan only.
- Then B005 should implement Global ETF Backtest MVP.

## 已知 gap（非阻塞）
- B004/B005 need fixture/mock-only CI and L1 guards for no live broker, PIT, paper/live boundaries, and AI no-buy/no-autoparameter behavior.

<!-- 写入规则（来自 harness-rules.md §记忆分层）：
1. 覆盖写，不追加；保持 ≤30 行
2. 所有角色都可写，谁产生变更谁更新
3. 内容边界：只放 WHAT（会变的事实），不放 HOW（行为规范，那是 role-context 的事）
4. 不重复 progress.json 已有的结构化数据（status/completed_features/fix_rounds 等）
-->
