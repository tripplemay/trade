# Next-batch prep — A股 ETF 时序趋势轮动 (etf-trend-ashare)

> **状态：DRAFT / 立项前准备，非 active 批次。** B083 PEAD 在 `verifying`（待 F003 codex）。
> backlog 排序 **P2**，评审 §3.4 排序 3 / §5 路线图。**工作量最小**（`global_etf_momentum.py` 改 A 股版）。
> 复用模式同 dividend-lowvol / PEAD prep（均被 planner 直接用于开批）。不动状态机。

## 为什么是它 / 选批理由

- **评审 §3.4 排序 3**：证据中（A 股指数时序动量短期存在, Physica A 2017；横截面行业动量弱→以趋势过滤/择时为主）。
- **契合度极高 / 工作量最小**（§3.4）：`trade/backtest/global_etf_momentum.py`（US ETF 时序动量）**改 A 股宽基/红利/行业 ETF 版**即可。
- **数据地基已就绪（★关键复用）**：B082 已接入 A 股 ETF 数据（akshare `fund_etf_hist_em`, 512890 等 + `snapshots/dividend_lowvol/`）。
  本批扩到宽基（510300 沪深300/510500 中证500/588000 科创50）/ 行业 / 红利 ETF——**复用 B082 F001 的 ETF fetch 管线**，不必从零。

## 设计骨架（待正式 spec）

1. **信号**：**时序动量/趋势跟踪**（每 ETF 自身 N 月动量 > 0 或价 > MA → 持有，否则退现金/防守）。非横截面行业轮动（评审：横截面行业动量弱）。
2. **标的池**：A 股宽基 + 红利低波（512890，与 B082 衔接）+ 少量行业 ETF。**上市时间决定窗口**（诚实标注，科创 ETF 短史）。
3. **★核心坑（评审焊死）**：**2022 / 2024-02 型震荡切换期假信号损耗**——趋势策略在震荡市反复止损。**必重点测这两窗口的假信号/换手损耗**，
   研报年化 18–24% 一律视样本内上限**打折**。
4. **引擎修真开关（B081）**：ETF 层多无手数/停牌/退市问题（流动、不退），但**开关照带**（成分增强路径才咬；纯 ETF 持有可豁免多数）。
   涨跌停：ETF 极少一字板，`price_limit_gating` 影响小但带上。
5. **成本口径**：ETF 无印花税（同 B082 dividend-lowvol 的 ETF 成本口径复用）。

## 复用清单

| 复用项 | 来源 | 用于 |
|---|---|---|
| 时序动量引擎骨架 | `trade/backtest/global_etf_momentum.py` | 核心信号+回测 |
| **A 股 ETF 数据管线** | **B082 F001**（akshare `fund_etf_hist_em` + snapshots/dividend_lowvol fetch 模式） | 数据地基（★最大复用，省 F001 大半） |
| ETF 成本口径（无印花税） | B082 F002 | 成本模型 |
| 回测保真开关 | B081 | 引擎口径 |
| 去偏 / WF / CPCV / 红黄绿卡 / trial 登记 | B070/B080 | 验收 |
| 模式注册 / precompute / 监控 / paper | B057/B080/B082 | 若建生产模式 |

## 开放问题（planner 开批时确认）

- **范围**：first-look IC/趋势胜率一测（低承诺）vs 直接建可配策略 + 生产模式？（PEAD 走了 first-look；本批数据地基已备+工作量小，或可直接建策略）。
- **标的池**：宽基-only（最干净）vs +行业/红利（更多标的、更多噪声）？
- **防守腿衔接**：趋势退现金时是否接 B082 红利低波 ETF 作防守腿（组合化）？
- **数据**：复用 B082 ETF 管线是否够（需补宽基/行业 ETF 序列）？

## 与其他 backlog 项 / follow-up

- 与 B082 红利低波**天然组合**（趋势进攻 + 红利防守）——可考虑组合批次。
- B081/B082 evaluator 标注的 follow-up（partial=True 变体 / refresh 编排脆弱性 fx+benchmark 前移）仍待 planner 并入 backlog。
