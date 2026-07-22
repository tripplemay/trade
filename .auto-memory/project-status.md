---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）
type: project
---

## 当前状态
- **B111 双工作流 → `verifying`（Codex 做 F006/F007）**。5 个 generator 功能（F001-F005）全部 done，已推 main，CI 全绿（自动链式部署）。
- **★工作流 A = P0 生产修复（F001-F004，已部署）**——打破「连续四次信号研究为负却没人检查已部署的东西」的模式：
  - **F001 P0-1 momentum（40% 仓位）**：`prepare_momentum_records`（trade/strategies/global_etf_momentum.py）加 ETF 白名单（15 只=workbench ETF_UNIVERSE，有 drift-guard）+ 月末重采样（月线 fixture 幂等）+ 丢弃历史不足符号。★NOT 改 generate_momentum_signal 核心（H1）。修掉个股污染（CAT/HD）+ 日线毒化（3/6/9 天→月）。
  - **F002 P0-2 us_quality（20%）**：generate_signal 按 universe 过滤 prices+fundamentals 修中美日历并集 NaN 毒化；low_vol/trend 因子按 ticker dropna 算滚动窗（稠密 US no-op）；precompute 任何 sleeve 100% 防守（SGOV）→ 标 `fallback`+告警+data_source 不报 real。★通用 fallback 正确暴露 hk_china 死权重（诊断§4.4）。
  - **F003 P0-3 regime + 监控**：监控扩到 master+regime（原排除→三 P0 裸奔 7 周根因）；45 天 staleness 告警（monitoring/staleness.py）+ sleeve_cash%+nav_drawdown；regime timer 改 daily（危机每日评估，调仓仍月度=评估≠交易，evaluate_current_regime）；Persistent=true 全 timer 安全测试。★补跑 regime = 运维项（部署后 timer 自动 un-freeze）。
  - **F004 成本对齐 + min-trade**：paper engine 加 min_trade_fraction（默认 0.0 零回归，服务 0.1% equity 杀 $17 碎单，全额平仓豁免）；cost_reconciliation.py 量化回测 3bps 单边 vs paper 10bps 双边=**6.67×**（docs/research/B111-F004-cost-caliber-reconciliation.md）。★未改回测/paper 成本参数（改=重写已验证历史，越界 H1）。
- **★工作流 B = 低波 first-look（F005，research-only 0 生产码，★只算不裁 H7）**：产物 `docs/audits/B111-F005-low-vol-first-look.{json,md}`（banned-word clean）。无前视 σ=过去 12 月月度收益已实现 σ。**已算值(背景不作证据)**：主 +3.086pp/σ 比 0.857/11-11 年；G1(滞后一月) **+2.210pp**；G2(剔最低 30% 流动性) **+4.106pp**；算术 t 均<2 已并排。**★裁定归 F007**（Generator 不裁）。

## 接续 / 待决策
- **F006（Codex 验收工作流 A）**：★不得只看单测——L2 真机核验 momentum 只持 ETF、us_quality 因子非 NaN、regime as_of 前进（依赖 daily timer 部署后跑）、staleness/fallback 告警可触发、成本上升量化。逐条审 H1-H4。
- **F007（Codex 验收工作流 B + 下裁定）**：自选样本独立复算、独立执行 G1/G2、按§B.3 双判据裁定、核查§B.0 诚实性遵守、不重犯 B110 F004 三处证据强度问题、列已核对冻结条款编号。
- 首推 backend CI 触红教训：**mypy-strict 也查 tests/**，本地须 `cd workbench/backend && .venv/bin/python -m mypy`（不止 source）。已修 37a594c。
- **B110 纯 E/P ✅ done 最终 NO-GO**；**新信号搜索正式冻结**（24 战 0 胜，重开限「数据类别变了」）。

## 永久边界
- research-safe / no-broker / no-AI 预测 / no 自动下单；A 股 PIT 禁 latest-wins 等；`DATA_NO_GO` 不变。
- Generator 不裁自己代码（铁律 #4）；被规则挡住≠被验证过；Generator 不得抽评测样本。
