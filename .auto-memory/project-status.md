---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留问题
type: project
---
## 当前状态
- **B008-research-grade-data-expansion：`done`**；F001-F006 completed and Evaluator signoff passed.
- Spec: `docs/specs/B008-research-grade-data-expansion-spec.md`

## 已完成签收
- B001 strategy roadmap: `docs/test-reports/B001-independent-reverification-signoff-2026-05-12.md`
- B002 data/broker specs: `docs/test-reports/B002-independent-signoff-2026-05-12.md`
- B003 MVP PRD: `docs/test-reports/B003-mvp-product-prd-signoff-2026-05-12.md`
- B004 engineering foundation: `docs/test-reports/B004-core-engineering-foundation-signoff-2026-05-12.md`
- B005 pre-backtest adjudication: `docs/test-reports/B005-pre-backtest-architecture-adjudication-signoff-2026-05-12.md`
- B006 Global ETF backtest MVP: `docs/test-reports/B006-global-etf-backtest-mvp-signoff-2026-05-12.md`
- B007 backtest quality hardening: `docs/test-reports/B007-backtest-quality-hardening-signoff-2026-05-12.md`
- B008 research-grade data expansion: `docs/test-reports/B008-research-grade-data-expansion-signoff-2026-05-13.md`

## 生产状态
- First implementation batch completed locally; no deployment, DB, broker API, secrets, or live-money operation.

## 下一步建议
- Planner may start done-stage memory/backlog handling and ask user for the next batch.

## 已知 gap（非阻塞）
- B008 research sample remains synthetic/short; public data import remains disabled stub by design.

<!-- 覆盖写；保持 ≤30 行；只放 WHAT，不重复 progress.json 结构化字段。 -->
