---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留问题
type: project
---
## 当前状态
- **B015-regime-adaptive-activation-policy：`done`**；Codex 已完成 verifying，写入签收报告并把 `docs.signoff` 指向 `docs/test-reports/B015-regime-adaptive-activation-policy-signoff-2026-05-14.md`。
- Spec: `docs/specs/B015-regime-adaptive-activation-policy-spec.md`
- 已交付：`regime_activation_policy` 配置开关、L1 gating activation helper、三 policy 比较 harness、比较报告、backwards-compat / safety 回归；real-data 分支在当前 checkout 中按 spec 正常 `skipped`。
- 关键决策（不变）：`always_on` 必须 bit-for-bit 保持 B013 行为；`only_non_normal` / `only_crisis` 只改变 L1 触发频率，不改 L2/L3；B011 Master Portfolio 默认注册保持 `always_on`。
- 硬边界：默认 CI 仍 fixture/mock-first；no-broker/no-paper/no-AI/no-secret-in-strategy；B014 fetcher / snapshot importer 保持不变。
- 踩坑沉淀：report 的 real-data 分支是否能 `ran` 取决于 B014 manifest 是否在仓库中；manifest 缺失时应明确 `skipped`，不能硬失败。

## 已完成签收
- B001-B008: strategy roadmap through research-grade data expansion all signed off.
- B009 public data snapshot MVP: `docs/test-reports/B009-public-data-snapshot-mvp-signoff-2026-05-13.md`
- B010 risk parity backtest MVP: `docs/test-reports/B010-risk-parity-backtest-mvp-signoff-2026-05-13.md`
- B011 portfolio allocation risk MVP: `docs/test-reports/B011-portfolio-allocation-risk-mvp-signoff-2026-05-13.md`
- B012 paper trading prep MVP: `docs/test-reports/B012-paper-trading-prep-mvp-signoff-2026-05-14.md`
- B013 regime-adaptive multi-asset MVP: `docs/test-reports/B013-regime-adaptive-multi-asset-mvp-signoff-2026-05-14.md`
- B014 regime-adaptive stress validation: `docs/test-reports/B014-regime-adaptive-stress-validation-signoff-2026-05-14.md`（empirical 2020 DD -4.76% / 2022 DD -1.66%）
- B015 regime-adaptive activation policy: `docs/test-reports/B015-regime-adaptive-activation-policy-signoff-2026-05-14.md`

## 生产状态
- No deployment, DB, broker API, secrets, paper/live trading, or live-money operation.

## 已知 gap（非阻塞）
- BL-B010-S1 + BL-B011-S2 + BL-B010-S3 + BL-B013-D1 + BL-B013-D2 仍在 backlog。
- 本机 system `python3` 为 3.9.6；所有检查必须用 `.venv/bin/python`（环境记录在 environment.md）。
- B015 committed comparison report 是 manifest-absent 路径（synthetic fixture）；要看真实 only_non_normal / only_crisis 是否缩窄 vs 60/40 gap，需本机 fetch yfinance manifest 后重跑 generate_b015 脚本。

<!-- 覆盖写；保持 ≤30 行；只放 WHAT，不重复 progress.json 结构化字段。 -->
