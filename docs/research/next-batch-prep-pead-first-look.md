# Next-batch prep — PEAD / 业绩预告事件 first-look (pead-first-look)

> **状态：DRAFT / 立项前准备，非 active 批次。** B082 红利低波在 `reverifying`（待独立 evaluator L2 复验）。
> 本文是等待复验期间对 backlog **排序第 2** 项做的 §Research&Reuse 前置调研 + 设计骨架，**不动**状态机。
> 复用模式同 `next-batch-prep-dividend-lowvol-defense.md`（该预研被 planner 直接用于开 B082）。
> 来源：`docs/research/ashare-strategy-deep-review-2026-07-03.md` §3.4 排序 2、§4 Tushare 重构、§5 路线图 P1。

## 为什么是它（选批理由）

- **评审排序第 2**（§3.4）：证据**最一致**、**数据零成本**——个人可实施策略里性价比最高的**新信号族**。
- **PEAD = post-earnings-announcement drift**：业绩公告（含预告/快报）后，价格向盈余惊喜方向**持续漂移**数周。
  A股证据 EMFT 2022/2025（评审 §参考文献）；中国 A股散户主导 + 关注度延迟 → 漂移比成熟市场更持久。
- 与红利低波（防守腿）**互补**：PEAD 是**进攻型事件 alpha**，两者组合 = 防守 + 进攻，填 cn_attack 红卡期空档。

## 数据（zero-cost，本批自带 spike——同 B082 F001 模式）

- **akshare 免费**：业绩预告（`stock_yjyg_em` 类）、业绩快报、**预约披露日**（`stock_yysj` 类）。
- ★**数据现实探针先行**（B082 F001 血泪：`data-reality probe GO/NO-GO`，双机实测覆盖率/字段/延迟）——
  PEAD 尤其要验：预告**发布时点** vs 正式财报时点（避免前视）、覆盖率（1490 宽宇宙 vs 实际有预告的子集）、
  盈余惊喜可算字段（预告净利润区间 / 快报 EPS vs 一致预期或去年同期）。
- 评审 §4：Tushare ¥200 的**主价值已重构**为支撑 PEAD（`disclosure_date`/`forecast`）——若 akshare 覆盖/时点不足，
  Tushare 是 fallback 数据源（但先验 akshare，零成本优先）。

## 设计骨架（待正式 spec 细化）

1. **事件定义**：盈余惊喜 = f(预告/快报 净利润 vs 预期基准)。分档（大幅预增/预减/扭亏/首亏…）或连续 SUE。
2. **信号**：事件后 t+1 进场（**避免前视**——用**公告日之后**可交易的价格），持有 N 日（PEAD 漂移窗口，研报常见 20-60 日，
   本批实测衰减）。横截面按惊喜排序做多头（或多空 first-look IC，同 B077 模式）。
3. **★first-look 优先 = 低承诺验收**（评审语气"first-look"）：**先做 forward-return rank-IC**（N1/N5/N10/N20，同 B077），
   IC 显著 + 单调 → 再进策略回测；IC 噪音 → INCONCLUSIVE 归档（省成本）。这是**事件信号族的正确第一步**。
4. **回测（若 IC 过关）**：复用 `trade/backtest/` 骨架 + **B081 引擎修真开关全开**（手数取整/停牌退市/涨跌停——
   PEAD 尤其撞**涨跌停**：预增大惊喜次日常一字涨停买不进 → `price_limit_gating` 必开，否则虚高不可执行的 alpha）。
5. **双本金容量口径**（B081 F005 教训）：事件驱动换手高 + 小盘惊喜多 → 手数/容量约束更咬；10万/100万双口径必报。

## ★两条直接适用的血泪教训（B081/B082）

1. **涨跌停可执行性（PEAD 命门）**：盈余大惊喜 → 次日一字板 → **`price_limit_gating` 不开则 alpha 是纸面的**。
   B081 F003 的涨跌停禁买卖开关直接复用。
2. **前视/时点严谨**：预告**发布时点** vs 财报时点必须 PIT——用发布日**之后**的价格进场，否则 IC 虚高（幸存者+前视双重）。

## 验收口径

- **first-look**：forward-return rank-IC（B077 模式）+ INCONCLUSIVE 门槛（\|IC\|<0.03 且不单调 → 归档）。
- **若进策略**：去偏 PIT + WF 70/30 + CPCV-lite + DSR（trial N）+ B066 式红黄绿卡（validated=False 起步）。
- **引擎修真 A/B**（B081 模板）：确认 PEAD edge 非涨跌停不可执行 / 手数容量假象。

## 开放问题（planner 开批时确认）

- **first-look-only 先行**（IC 一测，最小承诺）vs 直接策略回测？评审"first-look"倾向前者——建议 P0 IC 探针 + 数据现实 spike，IC 过关再 P1 策略。
- 惊喜度量：预告净利润区间中点 vs 一致预期（需分析师预期数据，akshare 覆盖？）vs 去年同期（zero-data，先行）。
- 宇宙：全 A（1490 宽）vs 去偏 PIT 子集（同 B070/B082 宇宙口径复用）。
- 数据源：akshare 先验（零成本），不足则 Tushare ¥200 fallback（评审 §4 已为此重构采购理由）。

## follow-up / backlog（evaluator 在 B081/B082 标注，供 planner done 阶段并入）

- B081: `partial_rebalance=True` 收益改善策略变体 → 独立 verdict 批次；`new_all_on@1M/fidelity_only` 隔离佐证。
- B082: dividend_lowvol 刷新**排序脆弱性**（今治本隔离，但 refresh 编排整体脆弱）→ backlog；`live 持久账簿` spec §4 follow-up；
  成分轻度增强（本批只做纯 ETF 持有）→ follow-up。
