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

## ★fetch 落地：待 Eastmoney 限流恢复（transient, 非数据问题）

`scripts/research/b084_etf_fetch.py`（fetch 池→`data/research/b084_etf/prices.csv`）已就绪, ruff clean。
**探针成功后, bulk fetch 连续撞 `SSLError push2his.eastmoney.com`** —— 本 session 大量 akshare 请求（B083 业绩预告 bulk +
本探针）触 Eastmoney **IP 限流**（同 B082 Tiingo 429 transient 类）。**数据可得性已由探针证实**；fetch 待限流恢复
（fresh session / 隔一段重跑 `b084_etf_fetch.py`, 每 ETF 缓存断点续跑）。

## 裁定：**GO**（数据可得）；F001 part2 = 限流恢复后跑 fetch 落 prices.csv → F002 时序趋势 first-look
