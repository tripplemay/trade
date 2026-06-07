---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留问题
type: project
---
## 当前状态
- **B045-OPS1-trade-wheel-deploy-reliability：`verifying`**（2026-06-07；横切 ops 修复）。**F001（generator）完成，交 Codex F002 L2。** 诊断根因（代码分析）：deploy.sh 虽 set -euo pipefail + --force-reinstall，但未带 --no-deps → --force-reinstall 连 pandas/numpy 一起重解析，VM PyPI 受限时卡住/失败留 trade 旧版（S4 最可能根因）。修复（commit 205e568）：(1) trade wheel 装法 → `--force-reinstall --no-deps`（pandas/numpy 已由 backend wheel 经 yfinance 传递装入，trade 只覆盖自身、确定性无关网络）+ 去 --quiet + pip show 版本；(2) **deploy 后 smoke import check**（装完 `import trade.backtest.master_portfolio; import trade.data.data_root`，失败 ::error:: + exit 1 硬失败，普适兜底所有 S4 候选，v0.9.36 铁律）；(3) dev rehearsal best-effort。deploy 守门测试 +2。本地 backend 853 / ruff 0 / mypy 0 / bash -n 通过。**F002 复验**：fresh deploy 后 trade version 自动匹配无需手动 + smoke check 跑过 + precompute import 正常 + §S4 resolved。spec `docs/specs/B045-OPS1-trade-wheel-deploy-reliability-spec.md`。后续 **B046=regime reconcile+account current_weight**。
- **B045-real-data-refresh-pipeline：✅ `done`**（2026-06-07，1 fix-round）。data-refresh pipeline 闭环：Tiingo prices 16500 行 + SEC EDGAR fundamentals 329 行 → VM unified CSV → trade loaders WORKBENCH_DATA_ROOT 覆盖 → precompute **data_source=mixed（3/4 sleeve real，satellite_hk_china by-design stub 无策略实现=现实天花板）**。/current 6 positions 真实权重。沉淀 v0.9.36。signoff `docs/test-reports/B045-real-data-refresh-pipeline-signoff-2026-06-07.md`。
- **B044-real-scoring-precompute：✅ `done`**。`/api/recommendations/current` equal-weight→Master 真实评分。**B046 待做：regime reconcile+account current_weight。**

## 已完成签收
- B001-B045 全部签收。

## 生产状态
- **B045 done：** prod `dfb5702` (trade 0.2.0 + fundamentals_sync)，timer auto-wired，data 19M (prices 1.1M+fundamentals 32K)，disk 84%。daily timer 每日 02:30 刷新。precompile data_source=mixed (1 sleeve_unavailable=hk_china 预期)。/current 6 pos / recent-errors=0。
- VM 运维：timer auto-wiring 就位；trade wheel deploy 需手动 force-reinstall(S4)。

## 永久硬边界
- B045 market data refresh (r) 只读 + §12.10.2 AST 守门 + data self-contained。

## Framework 状态
- **v0.9.36**（B045）：README §经验教训「venv 多包安装：deploy 静默装不上」+ smoke import check 铁律。
- v0.9.35（B044）：§12.10.2 enforcement 物理缺席→AST 守门 + README 长停机 prod==HEAD 教训。

## 已知 gap
- 本机 python3=3.9.6，用 .venv/bin/python。
- GitHub Secret 全配齐。
