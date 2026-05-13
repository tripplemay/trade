---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留问题
type: project
---
## 当前状态
- **B009-public-data-snapshot-mvp：`fixing`**；Evaluator reverification found B009-F006-1 still incomplete.
- Reverify report: `docs/test-reports/B009-public-data-snapshot-mvp-reverification-2026-05-13.md`

## 已完成签收
- B001 strategy roadmap: `docs/test-reports/B001-independent-reverification-signoff-2026-05-12.md`
- B002 data/broker specs: `docs/test-reports/B002-independent-signoff-2026-05-12.md`
- B003 MVP PRD: `docs/test-reports/B003-mvp-product-prd-signoff-2026-05-12.md`
- B004 engineering foundation: `docs/test-reports/B004-core-engineering-foundation-signoff-2026-05-12.md`
- B005 pre-backtest adjudication: `docs/test-reports/B005-pre-backtest-architecture-adjudication-signoff-2026-05-12.md`
- B006 Global ETF backtest MVP: `docs/test-reports/B006-global-etf-backtest-mvp-signoff-2026-05-12.md`
- B007 backtest quality hardening: `docs/test-reports/B007-backtest-quality-hardening-signoff-2026-05-12.md`
- B008 research-grade data expansion: `docs/test-reports/B008-research-grade-data-expansion-signoff-2026-05-13.md`

## B009 目标
- 按 MVP PRD 补齐 manual public data import、local snapshot manifest、显式 snapshot loader、quality gate、research run artifact。
- 保持 fixture/mock-first CI 与 no-live/no-secret/no-network-by-default/no-broker/no-AI guards。

## 当前阻塞
- B009-F006-1R: real import writes `{snapshot_id}-manifest.json`, but loader searches `{snapshot_file_stem}-manifest.json`; real import workflow artifacts still show manifest `None`.

## 生产状态
- No deployment, DB, broker API, secrets, paper/live trading, or live-money operation.

## 已知 gap（非阻塞）
- B009 仍不承诺 PIT/生产级行情；public data snapshot 仅用于 research-only best-effort 本地研究。

<!-- 覆盖写；保持 ≤30 行；只放 WHAT，不重复 progress.json 结构化字段。 -->
