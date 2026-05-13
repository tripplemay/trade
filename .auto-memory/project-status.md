---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留问题
type: project
---
## 当前状态
- **B012-paper-trading-prep-mvp：`verifying`**；Generator 完成 F001-F005,等待 Codex 第一轮 F006 验收。
- Spec: `docs/specs/B012-paper-trading-prep-mvp-spec.md`
- 新增 `trade/paper_prep/` 包(target_positions / broker_adapter / mock_broker / bridge),5 个测试文件共 60 个用例。pytest 219 / ruff / mypy / compileall 全绿。
- 关键决策(已落地):双输出 % + $、JSON Lines append-only journal、固定 USD 250000 账户、任意时间手动触发。
- 硬边界保留:无 broker SDK 导入、无 API URL、无模拟成交、无 env/socket。

## 已完成签收
- B001-B008: strategy roadmap through research-grade data expansion all signed off.
- B009 public data snapshot MVP: `docs/test-reports/B009-public-data-snapshot-mvp-signoff-2026-05-13.md`
- B010 risk parity backtest MVP: `docs/test-reports/B010-risk-parity-backtest-mvp-signoff-2026-05-13.md`
- B011 portfolio allocation risk MVP: `docs/test-reports/B011-portfolio-allocation-risk-mvp-signoff-2026-05-13.md`

## B012 目标
- 定义研究回测与未来 paper / live 适配之间的接口边界：Target Positions schema、Broker Adapter ABC、Mock Broker（journal-only）、Backtest→Paper 桥接。
- 复用 B011 master portfolio 与 B006/B010 single-strategy 输出，不引入新 cadence。
- 保持 fixture/mock-first CI 与 no-live/no-secret/no-network-by-default/no-broker/no-paper/no-AI guards。

## 生产状态
- No deployment, DB, broker API, secrets, paper/live trading, or live-money operation.

## 已知 gap（非阻塞）
- B012 不实现真实 paper / live broker adapter，不模拟成交 / P&L；这些是后续 B013 Broker Adapter Paper 范围。
- BL-B010-S1（risk parity 专用 fixture/workflow config）与 BL-B011-S2（satellite 策略 US Quality / HK-China）仍在 backlog。

<!-- 覆盖写；保持 ≤30 行；只放 WHAT，不重复 progress.json 结构化字段。 -->
