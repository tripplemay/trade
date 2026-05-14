---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留问题
type: project
---
## 当前状态
- **B012-paper-trading-prep-mvp：`done`**；Codex 第一轮 F006 验收通过并签收（0 issues, fix_rounds=0）。
- Spec: `docs/specs/B012-paper-trading-prep-mvp-spec.md`
- Signoff: `docs/test-reports/B012-paper-trading-prep-mvp-signoff-2026-05-14.md`
- Evidence: 60 B012 测试 + 全套 pytest 219 / ruff / compileall / mypy 全过；TargetPositions 双输出、BrokerAdapter 抽象、MockBroker append-only journal、bridge fail-closed、禁止导入 / API host / 执行语义 / env / socket 全部锁定。
- MVP 状态：PRD §4.5 Paper Trading 准备项已全部完成；§10/§11 成功标准与验收标准已隐式满足。

## 已完成签收
- B001-B008: strategy roadmap through research-grade data expansion all signed off.
- B009 public data snapshot MVP: `docs/test-reports/B009-public-data-snapshot-mvp-signoff-2026-05-13.md`
- B010 risk parity backtest MVP: `docs/test-reports/B010-risk-parity-backtest-mvp-signoff-2026-05-13.md`
- B011 portfolio allocation risk MVP: `docs/test-reports/B011-portfolio-allocation-risk-mvp-signoff-2026-05-13.md`
- B012 paper trading prep MVP: `docs/test-reports/B012-paper-trading-prep-mvp-signoff-2026-05-14.md`

## 生产状态
- No deployment, DB, broker API, secrets, paper/live trading, or live-money operation.

## 已知 gap（非阻塞）
- B012 不实现真实 paper / live broker adapter，不模拟成交 / P&L；后续 B013 Broker Adapter Paper（IBKR/Alpaca paper）涉及越过 PRD §5 非 MVP 边界，需用户拍板。
- BL-B010-S1（risk parity 专用 fixture/workflow config）与 BL-B011-S2（satellite 策略 US Quality / HK-China）仍在 backlog。
- 本机 system `python3` 为 3.9.6，不满足仓库 ≥3.11；所有检查必须用 `.venv/bin/python`（已写入 environment.md）。

<!-- 覆盖写；保持 ≤30 行；只放 WHAT，不重复 progress.json 结构化字段。 -->
