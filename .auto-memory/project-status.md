---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留问题
type: project
---
## 当前状态
- **B014-regime-adaptive-stress-validation：`verifying`**；Generator 完成 F001+F002，移交 Codex 跑 F003-F006（一次性真实抓取 + stress + 跨策略对比 + evidence-backed 签收）。
- Spec: `docs/specs/B014-regime-adaptive-stress-validation-spec.md`
- 已完成 (Generator): F001 `scripts/fetch_stooq_regime_adaptive_csvs.py` + F002 `tests/unit/test_stooq_fetcher.py`（26 个 mocked HTTP 单测，0 真实网络）。Fetcher 输出 `<SYMBOL>.csv` 用 lowercase canonical schema `date,open,high,low,close,adjusted_close,volume`（Stooq 免费 CSV 是 split-adjusted，close 直接落 adjusted_close）。
- Codex 入口（详见 progress.json `generator_handoff`）：先跑 fetcher 抓 `data/public-cache-staging/`，再 `acquire_regime_adaptive_snapshot.py` 注册 manifest，然后 F004 2020+2022 stress + F005 跨策略 + F006 签收。
- 关键决策：Stooq stooq.com/q/d/l/ 唯一允许 host；fetcher stdlib-only（urllib + csv）+ opt-in flag；SGOV 2020-05-28 上市作为允许 short-history；其他 8 资产 ≥95% 覆盖否则 fail-closed；2020 窗口 2020-02-01→2020-12-31（SGOV 上市前作为 cash placeholder），2022 窗口 2022-01-01→2022-12-31；跨策略对比 B013/B006/B010/60-40；**B014 不修改 B013 策略代码**；max DD>15% 走 proposed-learnings 建议参数 retune。
- 硬边界保留：默认 CI 仍 fixture/mock-first（pytest 362 全过；ruff/compileall/mypy 干净）；fetcher 是 strategy 模块外（scripts/）唯一网络入口；no-broker/no-paper/no-AI/no-secret-in-strategy。

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

<!-- 覆盖写；保持 ≤30 行；只放 WHAT，不重复 progress.json 结构化字段。 -->
