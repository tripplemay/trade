---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留问题
type: project
---
## 当前状态
- **B015-regime-adaptive-activation-policy：`building`**；Planner 完成 spec + features.json，等待 Generator 起步 F001。
- Spec: `docs/specs/B015-regime-adaptive-activation-policy-spec.md`
- 起因：B014 跨策略对比发现 B013 在非危机期间绝对收益让出给 60/40（126,726 vs 158,978 in 2020-06..2022-12）。B015 是最小切片研究批次。
- 6 features：F001-F005 generator + F006 codex（混合批次）。
- 关键决策：单一新增 config 字段 regime_activation_policy ∈ {always_on / only_non_normal / only_crisis}（默认 always_on）；只 gate L1 200-SMA 趋势过滤；L2 inverse-vol + 8% vol target、L3 crisis 减半语义**不变**；默认必须与 B013 signoff bit-for-bit 一致；B011 Master Portfolio sleeve 默认走 always_on 自动保持 B011 invariants；只修改 trade/strategies/regime_adaptive/ 内部，其他策略代码与 specs 不动；B014 yfinance snapshot 复用。
- 硬边界：默认 CI 仍 fixture/mock-first；no-broker/no-paper/no-AI/no-secret-in-strategy；B015 输出含 research-only disclaimer。

## 已完成签收
- B001-B008: strategy roadmap through research-grade data expansion all signed off.
- B009 public data snapshot MVP: `docs/test-reports/B009-public-data-snapshot-mvp-signoff-2026-05-13.md`
- B010 risk parity backtest MVP: `docs/test-reports/B010-risk-parity-backtest-mvp-signoff-2026-05-13.md`
- B011 portfolio allocation risk MVP: `docs/test-reports/B011-portfolio-allocation-risk-mvp-signoff-2026-05-13.md`
- B012 paper trading prep MVP: `docs/test-reports/B012-paper-trading-prep-mvp-signoff-2026-05-14.md`
- B013 regime-adaptive multi-asset MVP: `docs/test-reports/B013-regime-adaptive-multi-asset-mvp-signoff-2026-05-14.md`
- B014 regime-adaptive stress validation: `docs/test-reports/B014-regime-adaptive-stress-validation-signoff-2026-05-14.md`（empirical 2020 DD -4.76% / 2022 DD -1.66%）

## 生产状态
- No deployment, DB, broker API, secrets, paper/live trading, or live-money operation.

## 已知 gap（非阻塞）
- BL-B010-S1 + BL-B011-S2 + BL-B010-S3 + BL-B013-D1 + BL-B013-D2 仍在 backlog。
- 本机 system `python3` 为 3.9.6；所有检查必须用 `.venv/bin/python`（环境记录在 environment.md）。
- B015 假设 always_on 默认能保持 B013 bit-for-bit 行为；若 fixture-based golden diff 出现差异，是 F005 backwards-compat 失败信号。

<!-- 覆盖写；保持 ≤30 行；只放 WHAT，不重复 progress.json 结构化字段。 -->
