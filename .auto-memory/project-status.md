---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留问题
type: project
---
## 当前状态
- **B019-b010-b013-cadence-vol-target-retune：`fixing`**；F001 已完成，F002 已完成（real-data sweep + Pareto + gate verdict），B013 gate_met=True / winning_cell=('quarterly', 0.11)，B010 gate_met=False；Generator 接 F003（仅 B013 retune + conditional linkage），共 5 features 完成 2。
- Spec：`docs/specs/B019-b010-b013-cadence-vol-target-retune-spec.md`
- 两阶段执行：Stage 1 = sweep + Pareto + gate verdict（F001 generator + F002 codex）；Stage 2 conditional = default mutation + 联动（F003+F004 generator）+ 回归 signoff（F005 codex）。
- 网格：vol_target ∈ {0.09, 0.10, 0.11, 0.12, 0.13} × cadence ∈ {monthly, quarterly}，60 cells/3 windows，复用 B014 snapshot `regime-adaptive:b69883b08eedea7d`。
- 4 条 gate（同时满足才进 Stage 2）：calm ending value +1% / calm gap vs 60/40 缩窄 5pp / stress 双窗口 max DD do-no-harm / turnover ≤ +15%。
- B018 已签收：`docs/test-reports/B018-gap-attribution-signoff-2026-05-15.md`；attribution 结论 `l2_vol_scaling` 是主拖累驱动 B019 选 vol_target+cadence 两轴。
- 硬边界：默认 CI 仍 fixture/mock-first；`trade/` 模块零第三方依赖；no-broker/no-paper/no-AI/no-secret-in-strategy；所有输出 research-only；framework v0.9.21 #1 强制 real-data reverify。
- **下一批次决策（B019 done 后启动）：B020 Manual Execution Helper**（position diff + order ticket + manual fill journal），用户 2026-05-15 决定走手动下单路线，PRD §12 原 B009 Broker Adapter Paper 修订为此批次（spec 调整在 B020 立项时一并做），auto-broker 接入永久延后到 PRD §5 非 MVP 范围。

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
- B018 gap root-cause attribution: `docs/test-reports/B018-gap-attribution-signoff-2026-05-15.md`

## 生产状态
- No deployment, DB, broker API, secrets, paper/live trading, or live-money operation.

## 已知 gap（非阻塞）
- Backlog: BL-B010-S1 / BL-B011-S2 / BL-B013-D1 / BL-B013-D2；BL-B018-S1 由 B019 直接执行中（resolved 待 F005）。
- 本机 system `python3` 为 3.9.6；所有检查必须用 `.venv/bin/python`。
- framework/proposed-learnings.md 当前为空（v0.9.21 已沉淀 2 条 5/15 候选：fixture-vs-real reversal + gap-attribution methodology）。

<!-- 覆盖写；保持 ≤30 行；只放 WHAT，不重复 progress.json 结构化字段。 -->
