---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留问题
type: project
---
## 当前状态
- **B017-b015-b016-real-data-validation：`verifying`**（Codex-only 批次，跳过 building）；Planner 完成 spec + features.json，等待 Codex 起步 F001。
- Spec: `docs/specs/B017-b015-b016-real-data-validation-spec.md`
- 4 features 全部 executor: codex（F001 acquire snapshot / F002 regen B015 report / F003 regen B016 report / F004 cross-analysis signoff）。
- 起因：B015 与 B016 都在 done wrap-up 时留下 outstanding research item（real_data_status=skipped 因 B014 manifest 不在 repo）；用户两次选 option B 让 Codex 后续 session 处理。B017 把两个批次的真实数据验证合并 — 同一 yfinance fetch 一次拿，两个 report 一次重生成，一份 evidence-backed signoff 同时回答两个研究问题（only_non_normal/only_crisis 是否缩窄 B013 vs 60/40 gap？HRP 是否缩窄 B010 vs 60/40 gap？）。
- 关键决策：B017 **不修改任何 strategy / spec / 测试代码**；纯 Codex 跑现成 script + 写 signoff；stress threshold breach 走 framework/proposed-learnings 不算 defect；hybrid 候选走 backlog；local checks 期望 no-op。
- 硬边界：默认 CI 仍 fixture/mock-first；yfinance fetch 是 scripts/ 唯一网络入口（用户已授权一次性 fetch）；no-broker/no-paper/no-AI/no-secret-in-strategy；report 含 research-only disclaimer。

## 已完成签收
- B001-B008: strategy roadmap through research-grade data expansion all signed off.
- B009 public data snapshot MVP: `docs/test-reports/B009-public-data-snapshot-mvp-signoff-2026-05-13.md`
- B010 risk parity backtest MVP: `docs/test-reports/B010-risk-parity-backtest-mvp-signoff-2026-05-13.md`
- B011 portfolio allocation risk MVP: `docs/test-reports/B011-portfolio-allocation-risk-mvp-signoff-2026-05-13.md`
- B012 paper trading prep MVP: `docs/test-reports/B012-paper-trading-prep-mvp-signoff-2026-05-14.md`
- B013 regime-adaptive multi-asset MVP: `docs/test-reports/B013-regime-adaptive-multi-asset-mvp-signoff-2026-05-14.md`
- B014 regime-adaptive stress validation: `docs/test-reports/B014-regime-adaptive-stress-validation-signoff-2026-05-14.md`（empirical 2020 DD -4.76% / 2022 DD -1.66%）
- B015 regime-adaptive activation policy: `docs/test-reports/B015-regime-adaptive-activation-policy-signoff-2026-05-14.md`
- B016 risk parity HRP upgrade: `docs/test-reports/B016-risk-parity-hrp-upgrade-signoff-2026-05-15.md`

## 生产状态
- No deployment, DB, broker API, secrets, paper/live trading, or live-money operation.

## 已知 gap（非阻塞）
- BL-B010-S1 + BL-B011-S2 + BL-B013-D1 + BL-B013-D2 仍在 backlog（BL-B010-S3 已被 B016 消化）。
- 本机 system `python3` 为 3.9.6；所有检查必须用 `.venv/bin/python`。

<!-- 覆盖写；保持 ≤30 行；只放 WHAT，不重复 progress.json 结构化字段。 -->
