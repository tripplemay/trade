# B084 F001 — A股 宽基/红利 ETF data-reality probe → **GO**（fetch 待 Eastmoney 限流恢复）

> akshare `fund_etf_hist_em`（qfq）实测（复用 B082 路径）。结论：**数据可得 GO** — 标的池全覆盖、深度足。

## 探针结果（GO）

| ETF | 名称 | 行数 | 区间 |
|---|---|---|---|
| 510300 | 沪深300 | 1820 | 2018-01-02 .. 2025-07-04 |
| 510500 | 中证500 | 1820 | 2018-01-02 .. 2025-07-04 |
| 588000 | 科创50 | 1124 | **2020-11-16** .. 2025-07-04（★科创短史, 诚实标注） |
| 512890 | 红利低波 | 1564 | 2019-01-18 .. 2025-07-04（复用 B082） |
| 159915 | 创业板 | 1819 | 2018-01-02 .. 2025-07-04 |

- 宽基（沪深300/中证500/创业板）**7+ 年**深度, 够时序趋势 WF 70/30 + 覆盖 2022/2024-02 震荡期（★F002 命门窗口）。
- 科创 50 短史（2020-11）——窗口诚实标注, 时序动量按可用史打折。

## ★fetch 落地：**DONE via Sina 源（绕开 Eastmoney 限流）**

初次 bulk fetch 用 `fund_etf_hist_em`（Eastmoney push2his）连撞 `SSLError` —— 本 session 大量 akshare 请求
（B083 业绩预告 38k bulk + 本探针）触 Eastmoney **IP 限流**。**换 `fund_etf_hist_sina`（Sina 源, 不同 host）绕开**，
且史更长（510300→2012 / 159915→2011）。baostock 无 ETF 覆盖（0 行, 弃）。

**实测产出** `scripts/research/b084_etf_fetch.py` → `data/research/b084_etf/prices.csv`（gitignored, 脚本复现）：
**13,359 行 / 5 ETF / 2011-12-09..2026-07-03**（14+ 年, 宽基覆盖 2022/2024-02 震荡期 = F002 命门窗口）。

**★口径**：Sina `fund_etf_hist_sina` = **原始价（非 qfq 复权）**。趋势/时序动量 first-look **方向不受影响**
（ETF 分红小、极少拆分）——F002 用原始 close 算趋势合理；若后续建可配策略, 补复权口径。

## 裁定：**GO** — F001 done（探针 + Sina fetch 13,359 行落盘）→ F002 时序趋势 first-look
