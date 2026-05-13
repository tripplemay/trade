---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留问题
type: project
---
## 当前状态
- **B011-portfolio-allocation-risk-mvp：`verifying`**；Generator 完成 F001-F005，等待 Codex 执行 F006 独立验收。
- Spec: `docs/specs/B011-portfolio-allocation-risk-mvp-spec.md`
- 新模块：`trade/portfolio/master.py`、`trade/backtest/master_portfolio.py`、`trade/reporting/master_portfolio.py`；新测试覆盖 config/backtest/kill-switch/report/safety-guards 共 64 个用例；calculated 60/40 baseline 已吸收 BL-B010-S2。

## 已完成签收
- B001-B008: strategy roadmap through research-grade data expansion all signed off.
- B009 public data snapshot MVP: `docs/test-reports/B009-public-data-snapshot-mvp-signoff-2026-05-13.md`
- B010 risk parity backtest MVP: `docs/test-reports/B010-risk-parity-backtest-mvp-signoff-2026-05-13.md`

## B011 目标
- 实现最小 Master Portfolio Allocation MVP：静态规划权重、quarterly rebalance、account-level drawdown kill-switch、组合层 reports（含 calculated baseline）。
- 子策略保留独立 monthly 节奏与独立 reports，Master 只在 quarter-end 消费其 target weights。
- 复用 B009 snapshot/data-quality semantics，保持 fixture/mock-first CI 与 no-live/no-secret/no-network-by-default/no-broker/no-paper/no-AI guards。

## 生产状态
- No deployment, DB, broker API, secrets, paper/live trading, or live-money operation.

## 已知 gap（非阻塞）
- B011 首版不实现 satellite 策略（US quality / HK-China），仅 stub 接口。
- 不做 dynamic regime allocation、ERC / min-var optimizer、frontend dashboard、paper/live broker、生产级投资建议。
- BL-B010-S1（风险平价专用 fixture/workflow config）仍在 backlog，等待后续批次。

<!-- 覆盖写；保持 ≤30 行；只放 WHAT，不重复 progress.json 结构化字段。 -->
