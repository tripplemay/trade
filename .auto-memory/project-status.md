---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留问题
type: project
---
## 当前状态
- **B010-risk-parity-backtest-mvp：`done`**；Codex 已完成 F007 独立 L1 验收并签收。
- Spec: `docs/specs/B010-risk-parity-backtest-mvp-spec.md`
- Signoff: `docs/test-reports/B010-risk-parity-backtest-mvp-signoff-2026-05-13.md`
- Evidence: pytest 91 passed, ruff/compileall/mypy passed, B010 risk parity subset 29 passed under empty env, explicit B009-style snapshot smoke preserved manifest + limitations.

## 已完成签收
- B001-B008: strategy roadmap through research-grade data expansion all signed off.
- B009 public data snapshot MVP: `docs/test-reports/B009-public-data-snapshot-mvp-signoff-2026-05-13.md`
- B010 risk parity backtest MVP: `docs/test-reports/B010-risk-parity-backtest-mvp-signoff-2026-05-13.md`

## B010 目标
- 实现 Risk Parity / Vol Target 回测 MVP：inverse vol、no leverage、monthly T-day/T+1 workflow、reports。
- 复用 B009 snapshot/data-quality semantics，保持 fixture/mock-first CI 与 no-live/no-secret/no-network-by-default/no-broker/no-AI guards。

## 生产状态
- No deployment, DB, broker API, secrets, paper/live trading, or live-money operation.

## 已知 gap（非阻塞）
- B010 首版不做 ERC/min-var optimizer、paper/live broker、frontend dashboard 或生产级投资建议。
- 默认 momentum fixture 不适合直接跑默认 risk parity universe；后续用户化 workflow 可补专用 fixture/config。

<!-- 覆盖写；保持 ≤30 行；只放 WHAT，不重复 progress.json 结构化字段。 -->
