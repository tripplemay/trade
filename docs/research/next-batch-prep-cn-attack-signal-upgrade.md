# Next-batch prep — cn_attack 信号升级 A/B (cn-attack-signal-upgrade)

> **状态：DRAFT / 立项前准备，非 active 批次。** B083 PEAD 在 `verifying`（待 F003 codex）。
> backlog **P2**，评审 §3.4/§ 学术：残差动量 / SUE 叠加 / 剔涨停 / 2 月规避。**直接被本 session 的 B081 发现驱动**：
> cn_attack edge = **资本条件化**（10万 −16.0% / 100万 +27.1%，纯保真 PIT）——edge 真实但脆弱，signal 升级是提升它的正路。

## 为什么是它 / 选批理由

- **B081 刚证 cn_attack 有真 edge（100万 +27.1% OOS，保留 B070 ~95%）但资本受限 + 2024Q4 顺风**。升级信号 = 让 edge 更稳、更少依赖单一动量。
- 评审列的四个升级方向都是**低成本、高证据**的 A 股动量增强：
  1. **残差动量**（idiosyncratic momentum）：剔除市场/风格 β 后的残差动量——A 股证据（Lin 2020 EFM；IRFA 2021《Understanding idiosyncratic momentum in the Chinese stock market》，评审引）比裸动量更稳、更少反转。
  2. **SUE 叠加**（标准化盈余惊喜）：动量 × PEAD 惊喜——**可复用 B083 的业绩预告 events**（若 B083 F003 过/数据在）。注意 B083 first-look 提示预告-surprise 单用弱，但**与动量叠加**是不同假设。
  3. **剔涨停**（可执行性）：**直接复用 B081 F003 `_limit_hit_names`**——选股时剔当日一字涨停名（买不进的纸面 alpha），已是引擎开关。
  4. **2 月规避**（季节性）：A 股 2 月（春节/年报预告密集期）动量易反转——季节性 gate。**须防过拟合**（先验 + OOS 分月检验，不扫月份参数）。

## 设计骨架（A/B 对照，照 B081 引擎修真 A/B 模板）

- **基线 = 当前 cn_attack pure_momentum**（B070 去偏 PIT，纯保真口径 = B081 修真后）。
- **各升级单开 + 组合**（A/B 组，同 B081 `b081_engine_fidelity_ab.py` 模板）：+残差动量 / +SUE / +剔涨停 / +2月规避 / 全叠加。
- **双本金**（10万/100万，B081 F005 教训：容量口径必报）。
- **验收**：去偏 PIT WF 70/30 + CPCV-lite + DSR（trial N，A/B 各组登记）+ 红黄绿卡。**每组 vs 基线 delta**，看是否真提升 100万口径 OOS 且降波动。

## ★焊死 / 防坑（B081 血泪直接适用）

1. **禁扫参**：残差动量的回看窗、SUE 阈、2月 gate **先验定死**（评审/文献口径），A/B 只比"开/关"不扫参（B081 partial=True 混入基线的教训：改动须 verdict-gated 分账，非默认混入）。
2. **数字变差 = 诚实**：升级若在保真口径下**不提升**（如残差动量 OOS 不优于裸动量），诚实记 INCONCLUSIVE，不硬上（B083 PEAD 先例）。
3. **过度归因**：单一窗口/顺风别当稳健证据（B081 F004 分数股假象误判的教训——独立验收会抓）。

## 复用清单

| 复用项 | 来源 | 用于 |
|---|---|---|
| A/B 对照 runner（resumable+pickle 缓存） | B081 `scripts/research/b081_engine_fidelity_ab.py` | 各升级组对照 |
| 涨跌停剔除 | B081 F003 `_limit_hit_names` | 剔涨停 |
| 业绩预告 events（SUE 源） | B083 F001 `b083_pead_fetch` | SUE 叠加 |
| 引擎/信号骨架 | `trade/strategies|backtest/cn_attack_momentum_quality/` | 核心 |
| 去偏 PIT / WF / CPCV / 红卡 / trial | B070/B080/B081 | 验收 |

## 开放问题（planner）

- **范围**：四升级全做（大批）vs 先做证据最强的残差动量 + 剔涨停（小批）？建议后者先行（残差动量 A 股证据最一致）。
- **与 ETF-trend 的优先级**：两者都 P2；ETF-trend 工作量更小（数据已备），cn_attack-signal 价值更直接（治本已配资研究的旗舰策略）。planner 权衡。
