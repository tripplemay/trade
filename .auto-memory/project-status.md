---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留问题
type: project
---
## 当前状态
- **B007-backtest-quality-hardening：`done`**；Generator F001-F005 completed，Evaluator F006 L1 verification PASS.
- Signoff: `docs/test-reports/B007-backtest-quality-hardening-signoff-2026-05-12.md`
- L1 passed: pytest, ruff, compileall, mypy; workflow E2E generated deterministic JSON/Markdown reports.

## 已完成签收
- B001 strategy roadmap: `docs/test-reports/B001-independent-reverification-signoff-2026-05-12.md`
- B002 data/broker specs: `docs/test-reports/B002-independent-signoff-2026-05-12.md`
- B003 MVP PRD: `docs/test-reports/B003-mvp-product-prd-signoff-2026-05-12.md`
- B004 engineering foundation: `docs/test-reports/B004-core-engineering-foundation-signoff-2026-05-12.md`
- B005 pre-backtest adjudication: `docs/test-reports/B005-pre-backtest-architecture-adjudication-signoff-2026-05-12.md`
- B006 Global ETF backtest MVP: `docs/test-reports/B006-global-etf-backtest-mvp-signoff-2026-05-12.md`
- B007 backtest quality hardening: `docs/test-reports/B007-backtest-quality-hardening-signoff-2026-05-12.md`

## 生产状态
- First implementation batch completed locally; no deployment, DB, broker API, secrets, or live-money operation.

## 下一步建议
- Planner should decide next batch: research-grade data expansion, drawdown scenario hardening, risk parity MVP, or paper/mock broker planning.

## 已知 gap（非阻塞）
- B007 soft-watch: default clean workflow has monotonic equity curve; missing T+1 warning modes are unit-tested but not default E2E; synthetic fixtures validate mechanics, not investable research quality.

<!-- 覆盖写；保持 ≤30 行；只放 WHAT，不重复 progress.json 结构化字段。 -->
