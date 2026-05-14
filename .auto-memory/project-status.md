---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留问题
type: project
---
## 当前状态
- **B016-risk-parity-hrp-upgrade：`done`**；Codex F006 独立验收完成并签收。
- Spec: `docs/specs/B016-risk-parity-hrp-upgrade-spec.md`
- 交付：trade/strategies/risk_parity.py (Literal+dispatcher), trade/strategies/risk_parity_hrp.py (pure-stdlib HRP), trade/strategies/risk_parity_hrp_comparison.py (harness+report), scripts/generate_b016_hrp_comparison_report.py (CLI), trade/reporting/risk_parity.py (per-period weighting_method in trace).
- Canonical artifact: `docs/test-reports/B016-risk-parity-hrp-comparison-2026-05-14.{md,json}`（status=skipped，manifest 不在 repo 是 by-design）。
- 测试：526 PASS，mypy strict / ruff / compileall 全清；inverse-vol path bit-for-bit B010 锚点 + 18 项 B016 安全 guard 已加入。
- 起因：B011 master sleeve + B013 L2 都复用 B010 plain inverse-vol；arxiv 2026 多篇支持 HRP；B014 跨策略发现 B010 inverse-vol 在 calm window 让 60/40 ~25pp，HRP correlation-aware 可能缩窄 gap。
- 硬边界：默认 CI 仍 fixture/mock-first；`trade/` 模块零第三方依赖（仅 yfinance 在 scripts/）；no-broker/no-paper/no-AI/no-secret-in-strategy；B016 输出含 research-only disclaimer。

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
- BL-B010-S1 + BL-B011-S2 + BL-B013-D1 + BL-B013-D2 仍在 backlog（BL-B010-S3 = 本批次 B016）。
- 本机 system `python3` 为 3.9.6；所有检查必须用 `.venv/bin/python`。
- B015 / B016 比较 report 真实数据路径需 B014 snapshot manifest 在仓库；不在则按 spec 走 skipped。

<!-- 覆盖写；保持 ≤30 行；只放 WHAT，不重复 progress.json 结构化字段。 -->
