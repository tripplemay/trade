---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留问题
type: project
---
## 当前状态
- **B005-pre-backtest-architecture-adjudication：`done`**；Planner F001-F005 completed，Evaluator F006 independent review PASS。
- Signoff: `docs/test-reports/B005-pre-backtest-architecture-adjudication-signoff-2026-05-12.md`

## 已完成签收
- B001 strategy roadmap: `docs/test-reports/B001-independent-reverification-signoff-2026-05-12.md`
- B002 data/broker specs: `docs/test-reports/B002-independent-signoff-2026-05-12.md`
- B003 MVP PRD: `docs/test-reports/B003-mvp-product-prd-signoff-2026-05-12.md`
- B004 engineering foundation: `docs/test-reports/B004-core-engineering-foundation-signoff-2026-05-12.md`
- B005 pre-backtest adjudication: `docs/test-reports/B005-pre-backtest-architecture-adjudication-signoff-2026-05-12.md`

## 生产状态
- Documentation-only so far; no product code, migrations, deployment, broker API, secrets, or live-money operation.

## 下一步建议
- Next implementation batch should be B006 Global ETF Backtest MVP.

## 已知 gap（非阻塞）
- B006 must implement fixture/mock-first L1 guards, T+1 Open execution assumption, no-live/no-secret boundaries, and report PM-compatible outputs.

<!-- 覆盖写；保持 ≤30 行；只放 WHAT，不重复 progress.json 结构化字段。 -->
