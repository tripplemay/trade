---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留问题
type: project
---
## 当前状态
- **B006-global-etf-backtest-mvp：`building`**；Planner spec/features completed，Generator should start F001.
- Spec: `docs/specs/B006-global-etf-backtest-mvp-spec.md`

## 已完成签收
- B001 strategy roadmap: `docs/test-reports/B001-independent-reverification-signoff-2026-05-12.md`
- B002 data/broker specs: `docs/test-reports/B002-independent-signoff-2026-05-12.md`
- B003 MVP PRD: `docs/test-reports/B003-mvp-product-prd-signoff-2026-05-12.md`
- B004 engineering foundation: `docs/test-reports/B004-core-engineering-foundation-signoff-2026-05-12.md`
- B005 pre-backtest adjudication: `docs/test-reports/B005-pre-backtest-architecture-adjudication-signoff-2026-05-12.md`

## 生产状态
- Documentation-only so far; no product code, migrations, deployment, broker API, secrets, or live-money operation.

## 下一步建议
- Generator should implement F001 first: Python package scaffold, pyproject, tests directory, and CI.

## 已知 gap（非阻塞）
- B006 must preserve: CI yes, CD no, no Vitest/browser E2E, Python workflow E2E yes, fixture/mock-first, T+1 Open, no-live/no-secret/no-network guards.

<!-- 覆盖写；保持 ≤30 行；只放 WHAT，不重复 progress.json 结构化字段。 -->
