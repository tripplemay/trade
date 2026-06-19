# B070 F003 — 幸存者偏差量化（PIT 去偏 vs current 对照）

**结论：SURVIVES_DEBIASING** — De-biased (PIT) OOS still positive CAGR AND Sharpe → the A-share attack strategy's momentum edge is NOT purely a survivorship mirage (first survivorship-free validation; still research-only, 2024Q4 tailwind persists).

> **诚实 headline：** 动量边际**去偏后仍为正**，但**幸存者偏差使表观 OOS 虚高约一倍**（OOS CAGR 55.0%→28.4%，−26.6pp；OOS Sharpe 1.45→0.93；全样本 28.8%→13.1%）。正 OOS 主要来自 2024Q4『924』反弹恰落在 OOS 窗口（70/30 把最有利≈2 年放进 OOS），**OOS Sharpe>IS Sharpe（0.93>0.39）是窗口落位假象、非稳健性证据**。读作:边际为正、表观 OOS 被幸存者偏差虚高约一倍，仍研究态、不可配资。

窗口 2019-04-01..today；pure_momentum + equal（B069）；exit momentum_decay；WF 70/30。

| 宇宙 | breadth | 调仓 | CAGR | Sharpe | MaxDD | **OOS CAGR** | **OOS Sharpe** | OOS DD |
|---|---|---|---|---|---|---|---|---|
| survivorship_free_pit | 800 | 639 | 13.1% | 0.56 | -58.3% | 28.4% | 0.93 | -27.8% |
| biased_control | 800 | 611 | 28.8% | 0.93 | -50.2% | 55.0% | 1.45 | -25.1% |

## 幸存者偏差（对照 − 去偏）
- 全样本 CAGR 高估：**+15.7%**
- **OOS CAGR 高估：+26.6%**
- OOS Sharpe 高估：+0.52

## 诚实边界
- 因子仅 pure_momentum（退市名无免费 quality 基本面 → 2 因子版需 baostock 基本面管线，follow-on）；momentum 是主驱动（B068 Q1 quality 仅风险调整）。
- 去偏仅限**指数可纳入band**（HS300∪ZZ500∪SZ50，无 zz1000/zz800）→ 退市微小盘仍缺=残余偏差。
- 2024Q4 顺风高估**不在**本批；去偏后正收益≠可配资，仍研究态，OOS 披露续挂。
- 退市估值（§5 STOP-BIAS，已实测）：引擎 `_wide()` 对退市名 **ffill 冻结于最后成交价**估值（**非计 0**；000418.SZ 冻结于并购价 57.39），下次 band 调仓按该价卖出。ffill-vs-计0 两种处理 PIT 回测**完全一致**（full_cagr 0.1312、ending 243406、Δ≈0）→ 退市估值口径对结论零影响。残余:退市资本损失未建模 + 43/52 为 *ST（末价≈0.12-1.58）冻结略低估亏损 → **真实偏差或略大于 +26.6pp，+26.6pp 为下界**。
- exit 机制：momentum_decay **无显式离场规则**（`exit_count=0` 为结构性）；退市/动量衰减名通过跌出 top-N 由 no-trade-band 调仓卖出，非 exit 事件。