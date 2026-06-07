---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留问题
type: project
---
## 当前状态
- **B046-tradeable-diff-current-weight：`verifying`**（2026-06-07；真实评分基础 Batch 3；**里程碑 C 交易闭环关键拼图**）。F001+F002 generator done，交 Codex F003（L1+L2 真 VM 验收 + signoff）。**F001 done**(57084cb)：mark-to-market 可交易 diff——新 services/mark_to_market.py + execution.get_position_diff 改市价(保留 avg_cost 记账) + rec current_weight 真实。**F002 done**：regime reconcile——services/strategies.py 注册表对齐 master 实际组成(加 B006 momentum 0.40/B011 satellite_hk_china stub 0.10；B013-15 regime status→research；B016 注 master_strategy_id)，下游 home/advisor/news 自动 regroup 不破。backend 870 passed/ruff/mypy 0/§12.10.2 不破。**F003（Codex）剩**：L2 真 VM 验 ticket diff mark-to-market 准确+rec 真实+注册表对齐+B023 工作流不破+signoff。spec `docs/specs/B046-tradeable-diff-current-weight-spec.md`。里程碑 C 路径：B046→BL-B023-S1 闭环冒烟(用本批真实 diff)→HK-China→B042/B043。
- **B045-OPS1-trade-wheel-deploy-reliability：✅ `done`**（2026-06-07，0 fix-round，S4 resolved）。trade wheel `--force-reinstall --no-deps` + deploy 后 smoke import check（v0.9.36 铁律已实施）；fresh deploy trade 0.2.0 自动匹配无需手动。signoff `docs/test-reports/B045-OPS1-trade-wheel-deploy-reliability-signoff-2026-06-07.md`。
- **B045-OPS1-trade-wheel-deploy-reliability：✅ `done`**（2026-06-07，0 fix-round）。**S4 resolved**：根因=deploy.sh `--force-reinstall` 未带 `--no-deps`→重解析 pandas/numpy 在 VM 卡住留旧版；修为 `--force-reinstall --no-deps` + deploy 后 smoke import check（失败 ::error:: exit 1 硬失败，v0.9.36 铁律已实施）。fresh deploy(run 27081690834) trade 0.2.0 自动匹配无需手动，precompute 正常 saved=6。signoff `docs/test-reports/B045-OPS1-trade-wheel-deploy-reliability-signoff-2026-06-07.md`。
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
