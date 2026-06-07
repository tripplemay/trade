---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留问题
type: project
---
## 当前状态
- **B045-OPS1-trade-wheel-deploy-reliability：`building`**（2026-06-07 启动；横切 ops 修复，非产品序列；同 B037-OPS1 先例）。修 B045 §Soft-watch S4——trade wheel deploy 自动装仍坏（--force-reinstall 首次 deploy 仍停旧版需手动）。**决策（★用户批）：先修 S4 再 B046 + deploy 后 smoke import check 铁律(v0.9.36)**。根因现状：CI 确实构建+下发 trade wheel(workbench-deploy.yml L127/L180-181)，deploy.sh L72 已 --force-reinstall→排除 wheel 缺失；根因更隐蔽(version bump 进构建 wheel？/--force-reinstall+--quiet deploy 用户行为？/pip cache？)，F001 真机诊断对症修。核心 durable 防线=deploy 后 smoke import check(import trade.backtest.master_portfolio+trade.data.data_root 失败硬报)。2 features：(F001 g)诊断+修自动装+deploy.sh smoke import check；(F002 c)L2 fresh deploy 后 trade version 自动匹配无需手动+smoke check 跑过+precompute import 正常+§S4 resolved。spec `docs/specs/B045-OPS1-trade-wheel-deploy-reliability-spec.md`。
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
