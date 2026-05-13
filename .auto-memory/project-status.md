---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留问题
type: project
---
## 当前状态
- **B010-risk-parity-backtest-mvp：`verifying`**；Generator 完成 F001-F006，等待 Codex 执行 F007 独立验收。
- Spec: `docs/specs/B010-risk-parity-backtest-mvp-spec.md`
- F006 新增 `tests/unit/test_risk_parity_safety_guards.py`：网络/凭据/经纪商/AI/public-import/前端导入隔离、离线运行、报告无 paper/live 用词、不写 fixture 目录、无杠杆校验、public_import 不自动触发。

## 已完成签收
- B001 strategy roadmap: `docs/test-reports/B001-independent-reverification-signoff-2026-05-12.md`
- B002 data/broker specs: `docs/test-reports/B002-independent-signoff-2026-05-12.md`
- B003 MVP PRD: `docs/test-reports/B003-mvp-product-prd-signoff-2026-05-12.md`
- B004 engineering foundation: `docs/test-reports/B004-core-engineering-foundation-signoff-2026-05-12.md`
- B005 pre-backtest adjudication: `docs/test-reports/B005-pre-backtest-architecture-adjudication-signoff-2026-05-12.md`
- B006 Global ETF backtest MVP: `docs/test-reports/B006-global-etf-backtest-mvp-signoff-2026-05-12.md`
- B007 backtest quality hardening: `docs/test-reports/B007-backtest-quality-hardening-signoff-2026-05-12.md`
- B008 research-grade data expansion: `docs/test-reports/B008-research-grade-data-expansion-signoff-2026-05-13.md`
- B009 public data snapshot MVP: `docs/test-reports/B009-public-data-snapshot-mvp-signoff-2026-05-13.md`

## B010 目标
- 实现 Risk Parity / Vol Target 回测 MVP：inverse vol、no leverage、monthly T-day/T+1 workflow、reports。
- 复用 B009 snapshot/data-quality semantics，保持 fixture/mock-first CI 与 no-live/no-secret/no-network-by-default/no-broker/no-AI guards。

## 生产状态
- No deployment, DB, broker API, secrets, paper/live trading, or live-money operation.

## 已知 gap（非阻塞）
- B010 首版不做 ERC/min-var optimizer、paper/live broker、frontend dashboard 或生产级投资建议。

<!-- 覆盖写；保持 ≤30 行；只放 WHAT，不重复 progress.json 结构化字段。 -->
