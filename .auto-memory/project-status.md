---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留问题
type: project
---
## 当前状态
- **B018-gap-root-cause-attribution：`done`**；Codex 已完成 F003-F005 独立验收、写入签收报告并收口。
- 报告：`docs/test-reports/B018-gap-attribution-2026-05-15.md`
- 签收：`docs/test-reports/B018-gap-attribution-signoff-2026-05-15.md`
- Snapshot：`regime-adaptive:b69883b08eedea7d`，`real_data_status=ran`
- 结论：`l2_vol_scaling` 是主拖累，`l1_gating` 次之；`vol_target` / `cadence` 是主要可调轴，`universe` ablation 多数受 defensive 不变量限制。
- 后续建议：`BL-B018-S1` 进入 backlog，追踪 `B010` quarterly cadence / 10%~12% vol-target 联合 retune。
- 硬边界：默认 CI 仍 fixture/mock-first；`trade/` 模块零第三方依赖；no-broker/no-paper/no-AI/no-secret-in-strategy；所有输出 research-only。

## 已完成签收
- B001-B008: strategy roadmap through research-grade data expansion all signed off.
- B009 public data snapshot MVP: `docs/test-reports/B009-public-data-snapshot-mvp-signoff-2026-05-13.md`
- B010 risk parity backtest MVP: `docs/test-reports/B010-risk-parity-backtest-mvp-signoff-2026-05-13.md`
- B011 portfolio allocation risk MVP: `docs/test-reports/B011-portfolio-allocation-risk-mvp-signoff-2026-05-13.md`
- B012 paper trading prep MVP: `docs/test-reports/B012-paper-trading-prep-mvp-signoff-2026-05-14.md`
- B013 regime-adaptive multi-asset MVP: `docs/test-reports/B013-regime-adaptive-multi-asset-mvp-signoff-2026-05-14.md`
- B014 regime-adaptive stress validation: `docs/test-reports/B014-regime-adaptive-stress-validation-signoff-2026-05-14.md`
- B015 regime-adaptive activation policy: `docs/test-reports/B015-regime-adaptive-activation-policy-signoff-2026-05-14.md`
- B016 risk parity HRP upgrade: `docs/test-reports/B016-risk-parity-hrp-upgrade-signoff-2026-05-15.md`
- B017 B015+B016 real-data validation: `docs/test-reports/B017-real-data-validation-signoff-2026-05-15.md`

## 生产状态
- No deployment, DB, broker API, secrets, paper/live trading, or live-money operation.

## 已知 gap（非阻塞）
- Backlog: BL-B010-S1 / BL-B011-S2 / BL-B013-D1 / BL-B013-D2 / BL-B018-S1（B018 新增：B010 quarterly cadence + 10–12% vol-target retune 候选）。
- 本机 system `python3` 为 3.9.6；所有检查必须用 `.venv/bin/python`。
- framework/proposed-learnings.md 当前为空（v0.9.21 已沉淀 2 条 5/15 候选：fixture-vs-real reversal + gap-attribution methodology）。

<!-- 覆盖写；保持 ≤30 行；只放 WHAT，不重复 progress.json 结构化字段。 -->
