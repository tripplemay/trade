---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留问题
type: project
---
## 当前状态
- **B014-regime-adaptive-stress-validation：`fixing`**；Codex 报告 Stooq /q/d/l/ apikey 门梢阻塞，**Planner override 为 Stooq → yfinance 切换**（pip 包，免 API key，自动化），等待 Generator 按新方向重做 F001/F002 实现。
- Spec: `docs/specs/B014-regime-adaptive-stress-validation-spec.md`（含 Amendment 2026-05-14 数据源 pivot）。
- F001/F002 标 completed（Stooq 实现），fix 迭代将替换为 yfinance 实现；fix_rounds 由 Generator 推进时 bump。
- Generator fix tasks（详见 progress.json `generator_handoff.fix_tasks`）：删 Stooq fetcher + tests；加 yfinance 依赖；新增 `scripts/fetch_yfinance_regime_adaptive_csvs.py` 用 yfinance.Ticker.history(auto_adjust=True) + lowercase canonical schema `date,open,high,low,close,adjusted_close,volume`；新增 mocked-yfinance 测试；保持 SGOV 例外 + 其他 8 ≥95% + opt-in + fail-closed；**B013 策略代码不变**。
- Codex 后续（generator_handoff.post_fix_codex_workflow）：跑 yfinance fetcher → acquire 注册 manifest → F004 2020+2022 stress → F005 跨策略对比 → F006 evidence-backed 签收。
- 关键决策（不变）：9 资产宇宙；SGOV 2020-05-28 允许 short-history；2020 窗口 02-01→12-31（SGOV 上市前 cash placeholder），2022 窗口 01-01→12-31；跨策略对比 B013/B006/B010/60-40；**B014 不修改 B013 策略代码**；max DD>15% 走 proposed-learnings。
- 硬边界：默认 CI 仍 fixture/mock-first；yfinance 是 scripts/ 唯一网络入口；no-broker/no-paper/no-AI/no-secret-in-strategy。

## 已完成签收
- B001-B008: strategy roadmap through research-grade data expansion all signed off.
- B009 public data snapshot MVP: `docs/test-reports/B009-public-data-snapshot-mvp-signoff-2026-05-13.md`
- B010 risk parity backtest MVP: `docs/test-reports/B010-risk-parity-backtest-mvp-signoff-2026-05-13.md`
- B011 portfolio allocation risk MVP: `docs/test-reports/B011-portfolio-allocation-risk-mvp-signoff-2026-05-13.md`
- B012 paper trading prep MVP: `docs/test-reports/B012-paper-trading-prep-mvp-signoff-2026-05-14.md`
- B013 regime-adaptive multi-asset MVP: `docs/test-reports/B013-regime-adaptive-multi-asset-mvp-signoff-2026-05-14.md`

## 生产状态
- No deployment, DB, broker API, secrets, paper/live trading, or live-money operation.

## 已知 gap（非阻塞）
- B013 的 2020/2022 max DD<15% claim 仍待 B014 经验验证；B014 完成后 B013 stress gate 从 skipped 翻为 pass/fail。
- BL-B010-S1 + BL-B011-S2 + BL-B010-S3 + BL-B013-D1 + BL-B013-D2 仍在 backlog。
- 本机 system `python3` 为 3.9.6；所有检查必须用 `.venv/bin/python`（环境记录在 environment.md）。
- B014 fix 迭代引入 yfinance 第三方依赖（仅 scripts/ 范围，不进 strategy 模块）。

<!-- 覆盖写；保持 ≤30 行；只放 WHAT，不重复 progress.json 结构化字段。 -->
