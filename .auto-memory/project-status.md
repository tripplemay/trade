---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留问题
type: project
---
## 当前状态
- **B015-regime-adaptive-activation-policy：`verifying`**；Generator 完成 F001-F005，Codex 接手 F006 独立验收。
- Spec: `docs/specs/B015-regime-adaptive-activation-policy-spec.md`
- Generator 交付物：`trade/strategies/regime_adaptive/config.py`（新 `regime_activation_policy` 字段 + 三 enum + 校验 + parameter_hash 包含）、`trend_gating.py`（`should_l1_gate_run` 9-cell 真值表 + `build_policy_skipped_trend_result`）、`backtest.py`（先 L3 再条件化 L1，`l1_active: bool` 上 period trace）、新增 `activation_policy_comparison.py`（3-policy 对比 harness + B014 manifest loader + monthly signal-date 选取 + try-real-snapshot wrapper）、新增 `activation_policy_report.py`（B015 报告 builder + B014 sidecar 复用 + gap narrative）。新 script `scripts/generate_b015_activation_policy_report.py` 已运行，committed 报告 = manifest-absent path（real_data_status=skipped）。
- 测试覆盖：423 tests pass，ruff 0 issues，mypy 44 trade/ files clean，compileall all green。新增 41 个 B015 测试覆盖配置、真值表、ungated builder、workflow 集成、3-policy 对比、CSV loader、report schema、gap narrative 三分支、backwards-compat（always_on gating mask 与直接 apply_trend_gating 比对 bit-for-bit）、安全 guard 回归。
- 默认 `always_on` 与 B013 signoff 行为 bit-for-bit 一致（通过 `apply_trend_gating` 直接调用对比验证）；B011 master sleeve registration 测试不修改即通过。
- 硬边界保持：无新增 broker/AI/network SDK import；strategy 模块无 `os.environ` 读取；默认 fixture run 无 socket I/O；report 输出无 paper/live execution 用语；默认 CI 不依赖真实 manifest。

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
- B015 committed comparison report 是 manifest-absent 路径（synthetic fixture）；要看真实 only_non_normal / only_crisis 是否缩窄 vs 60/40 gap，需本机 fetch yfinance manifest 后重跑 generate_b015 脚本。

<!-- 覆盖写；保持 ≤30 行；只放 WHAT，不重复 progress.json 结构化字段。 -->
