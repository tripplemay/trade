---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留问题
type: project
---
## 当前状态
- **B018-gap-root-cause-attribution：`building`**；Planner 完成 spec + features.json，等待 Generator 起步 F001。
- Spec: `docs/specs/B018-gap-root-cause-attribution-spec.md`
- 起因：B017 经验给出两个负面发现 — B015 regime activation 不缩窄 B013 vs 60/40 gap；B016 HRP 不缩窄 B010 vs 60/40 gap（HRP -$496 + turnover +41%）。Gap 真实来源仍未知。MVP PRD §10/§11/§4/§12 已基本完成（5/6 §12 里程碑过；最后 Broker Adapter Paper 跨 §5 非 MVP 边界）。继续盲目加策略变体有放大错误风险。B018 是研究归因批次。
- 5 features（混合批次）：F001-F002 generator（pnl_attribution + parameter_sweep 模块 + 测试）+ F003-F005 codex（真实数据归因 + 三轴 sweep + 诊断报告 + Pareto 推荐 + signoff）。
- 关键决策：(1) 新模块在 trade/analysis/，纯 stdlib（无 scipy/numpy/pandas/sklearn）；(2) override config 内联构造，**不 mutate strategy 默认参数**；(3) sweep 三轴：vol_target ∈ {5,8,10,12,15}% + universe ablation 4-5 variant + cadence 3-4 variant；(4) 至少 3 个 Pareto 推荐含具体 trade-off 数字；(5) B018 **不改任何 strategy/spec/test 默认**，retune 候选只入 backlog；(6) manifest 缺失 fallback synthetic + skipped。
- 硬边界：默认 CI 仍 fixture/mock-first；`trade/` 模块零第三方依赖；no-broker/no-paper/no-AI/no-secret-in-strategy；report 含 research-only disclaimer。

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
- BL-B010-S1 + BL-B011-S2 + BL-B013-D1 + BL-B013-D2 仍在 backlog；B018 完成后可能新增 BL-B018-* retune 候选。
- 本机 system `python3` 为 3.9.6；所有检查必须用 `.venv/bin/python`。
- framework/proposed-learnings.md 有 2 条 2026-05-15 待确认条目（synthetic-vs-real reversal warning + gap source unknown），待用户某次 done wrap-up 时一并 sign off。

<!-- 覆盖写；保持 ≤30 行；只放 WHAT，不重复 progress.json 结构化字段。 -->
