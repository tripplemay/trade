---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留问题
type: project
---
## 当前状态
- **B014-regime-adaptive-stress-validation：`fixing`**；Codex 已验证 yfinance fetcher 能真实抓取 9 资产 CSV，但 snapshot importer 在 SPY/SGOV 上 fail closed，需 Generator 修复覆盖起始日逻辑后再继续 F003-F006。
- Spec: `docs/specs/B014-regime-adaptive-stress-validation-spec.md`（含 Amendment 2026-05-14 数据源 pivot）。
- 已交付（fix round 1）：删 `scripts/fetch_stooq_regime_adaptive_csvs.py` + `tests/unit/test_stooq_fetcher.py`；`pyproject.toml` 加 `yfinance>=0.2.40`；新增 `scripts/fetch_yfinance_regime_adaptive_csvs.py`（yfinance.Ticker.history `auto_adjust=True`, `actions=False`, `raise_errors=True`，lowercase canonical schema 不变）+ `tests/unit/test_yfinance_fetcher.py`（23 个 mocked-yfinance 单测，0 真实网络）。SGOV 短历史例外 + 其他 8 ≥95% + opt-in + fail-closed 全保留。**B013 策略代码不变**。
- Codex 后续（progress.json `generator_handoff.post_fix_codex_workflow`）：yfinance fetcher 已成功；当前卡在 acquire 注册 manifest，因 importer 仍要求请求起始日精确覆盖而拒绝 SPY（2018-01-01 为假日）和 SGOV（实际首可得日 2020-06-01）。需 Generator 修复 importer/coverage 逻辑后再继续 F004/F005/F006。
- 关键决策（不变）：9 资产宇宙；SGOV 2020-05-28 允许 short-history；2020 窗口 02-01→12-31（SGOV 上市前 cash placeholder），2022 窗口 01-01→12-31；跨策略对比 B013/B006/B010/60-40；max DD>15% 走 proposed-learnings。
- 硬边界：默认 CI 仍 fixture/mock-first（pytest 359 全过；ruff/compileall/mypy 干净）；yfinance 是 scripts/ 唯一网络入口；no-broker/no-paper/no-AI/no-secret-in-strategy。
- 踩坑沉淀：pandas.Timestamp 继承自 datetime（→ date），fetcher 内 `isinstance(value, date)` 短路返回 Timestamp 会让 `< date` 抛 TypeError；先 `to_pydatetime().date()` 再 fallback。

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
- B014 真实 CSV 已拿到 staging；当前阻塞是 importer coverage 规则过严，不是数据源不可用。

<!-- 覆盖写；保持 ≤30 行；只放 WHAT，不重复 progress.json 结构化字段。 -->
