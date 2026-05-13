---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留问题
type: project
---
## 当前状态
- **B011-portfolio-allocation-risk-mvp：`done`**；Codex 第二轮 F006 复验通过并签收。
- Spec: `docs/specs/B011-portfolio-allocation-risk-mvp-spec.md`
- Review (round 1): `docs/test-reports/B011-portfolio-allocation-risk-mvp-review-2026-05-13.md`
- Signoff: `docs/test-reports/B011-portfolio-allocation-risk-mvp-signoff-2026-05-13.md`
- Evidence: pytest 159, ruff/compileall/mypy, B011 subset 68 under empty env; intra-quarter dates fail closed, quarter-end dates pass; `BL-B010-S2` absorbed by calculated 60/40 baseline.

## 已完成签收
- B001-B008: strategy roadmap through research-grade data expansion all signed off.
- B009 public data snapshot MVP: `docs/test-reports/B009-public-data-snapshot-mvp-signoff-2026-05-13.md`
- B010 risk parity backtest MVP: `docs/test-reports/B010-risk-parity-backtest-mvp-signoff-2026-05-13.md`
- B011 portfolio allocation risk MVP: `docs/test-reports/B011-portfolio-allocation-risk-mvp-signoff-2026-05-13.md`

## 生产状态
- No deployment, DB, broker API, secrets, paper/live trading, or live-money operation.

## 已知 gap（非阻塞）
- B011 首版不实现 satellite 策略（US quality / HK-China），仅 stub 接口。
- 不做 dynamic regime allocation、ERC / min-var optimizer、frontend dashboard、paper/live broker、生产级投资建议。
- BL-B010-S1（风险平价专用 fixture/workflow config）仍在 backlog，等待后续批次。

<!-- 覆盖写；保持 ≤30 行；只放 WHAT，不重复 progress.json 结构化字段。 -->
