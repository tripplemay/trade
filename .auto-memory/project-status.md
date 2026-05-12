---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留问题
type: project
---
## 当前状态
- **B007-backtest-quality-hardening：`verifying`**；Generator completed F001-F005，Evaluator should perform F006.
- Goal: close B006 soft-watch with multi-rebalance fixtures, explicit missing T+1 Open handling, clean/warning risk scenarios, stronger metrics/equity curve reports, and preserved safety guards.
- Local env ready: `.venv` Python 3.11.14; baseline pytest, ruff, compileall, mypy passed.

## 已完成签收
- B001 strategy roadmap: `docs/test-reports/B001-independent-reverification-signoff-2026-05-12.md`
- B002 data/broker specs: `docs/test-reports/B002-independent-signoff-2026-05-12.md`
- B003 MVP PRD: `docs/test-reports/B003-mvp-product-prd-signoff-2026-05-12.md`
- B004 engineering foundation: `docs/test-reports/B004-core-engineering-foundation-signoff-2026-05-12.md`
- B005 pre-backtest adjudication: `docs/test-reports/B005-pre-backtest-architecture-adjudication-signoff-2026-05-12.md`
- B006 Global ETF backtest MVP: `docs/test-reports/B006-global-etf-backtest-mvp-signoff-2026-05-12.md`

## 生产状态
- First implementation batch completed locally; no deployment, DB, broker API, secrets, or live-money operation.

## 下一步建议
- Evaluator should run F006 L1 verification and write B007 signoff report.

## 已知 gap（非阻塞）
- B007 intentionally does not add live data, broker/paper execution, frontend, database, risk parity, multi-factor, or AI trading.

<!-- 覆盖写；保持 ≤30 行；只放 WHAT，不重复 progress.json 结构化字段。 -->
