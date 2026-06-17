# B064 §23 — CN/HK 基本面 + 新闻 akshare 端点实跑验证报告

**日期：** 2026-06-18
**角色：** Generator（F001/F002 实施前的 §23 硬前置实跑，framework v0.9.45 §23 / 铁律 9）
**环境：** 本机 darwin（repo 根 `.venv` akshare 1.18.64）。**注意**：这是 generator 选型 + shape 映射的实跑证据；**生产 VM 真机可达性结论以 Codex F004 为权威**（L2 真机验收，evaluator §29 实测证据硬段）。
**探针工具：** `scripts/test/cn_hk_fundamentals_news_probe.py`（每候选独立子进程 + 硬超时；Codex 可在 VM 复跑）。

---

## 1. 结论摘要

**§23 最大未知（港股基本面/新闻源可达性）正面解决** —— 港股基本面**和**港股新闻**均可达**，不需诚实空态降级。A 股基本面/新闻全部可达。选定函数集已端到端实跑出真值（见 §3 端到端证据）。

| 数据 | 选定函数 | 可达 | 关键字段 |
|---|---|---|---|
| A股 基本面（财务+比率） | `stock_financial_abstract` | ✅ | 营业总收入/归母净利润/ROE/毛利率/销售净利率/资产负债率/基本每股收益/每股净资产/产权比率（CAS，metric×period pivot，最新报告期取数）|
| A股 估值 | `stock_value_em` | ✅ | 总市值/PE(TTM)/市净率/总股本（raw 元，日频取最新行）|
| HK 基本面（财务+比率） | `stock_financial_hk_analysis_indicator_em` | ✅ | OPERATE_INCOME/HOLDER_PROFIT/BASIC_EPS/BPS/GROSS_PROFIT_RATIO/NET_PROFIT_RATIO/ROE_AVG/DEBT_ASSET_RATIO/CURRENCY=HKD/名称（年度）|
| HK 估值 | `stock_hk_valuation_baidu` | ✅ | 总市值（亿 HKD →×1e8）/市盈率(TTM)/市净率（baidu host，非 B062 超时的 eastmoney push host）|
| A股 + HK 个股新闻 | `stock_news_em` | ✅ | 关键词/新闻标题/新闻内容/发布时间/文章来源/新闻链接（**CN+HK 同函数均可达，标题均中文 → 免翻**）|

## 2. 候选函数实跑矩阵（首轮 + 估值二轮）

**可达（选用）：**
- `stock_financial_abstract(symbol="600519")` — 80 指标 × 多报告期 pivot，~4s。
- `stock_value_em(symbol="600519")` — 2050 日行，总市值 raw 元，~4s。
- `stock_financial_hk_analysis_indicator_em(symbol="00700", indicator="年度")` — 9 年度行，~3s，CURRENCY=HKD。
- `stock_hk_valuation_baidu(symbol="00700", indicator=...)` — 总市值/PE(TTM)/市净率 各 365 日，~3s。
- `stock_zh_valuation_baidu(symbol="600519", indicator=...)` — A股估值（备选；总市值单位为**亿**，已改用 `stock_value_em` raw 元以与 yfinance 单位一致）。
- `stock_news_em(symbol="600519")` 与 `stock_news_em(symbol="00700")` — 各 10 条中文新闻，~3s。

**不可达（弃用，§23「不假设兄弟函数可达」）：**
- `stock_individual_info_em` — JSONDecodeError（空响应，市值/PE 源；二次重试仍失败）。
- `stock_hk_spot_em()` — SSLError on `72.push2.eastmoney.com`（eastmoney push host，同 B062 港股端点教训）。
- `stock_a_indicator_lg` — akshare 1.18.64 已无此函数（AttributeError）。
- `stock_hk_indicator_eniu` — TimeoutError（亿牛 host hang 35s）。

> **方法论印证 B062 教训：** eastmoney **push host**（`*.push2.eastmoney.com`）系列从本机不可达（SSL/timeout），而 eastmoney **finance/data host**（`stock_financial_abstract` / `stock_news_em` / `stock_value_em`）与 baidu host（`stock_hk_valuation_baidu`）可达。选型严格只用已实跑可达者。

## 3. 端到端真值证据（real provider → parser → cache → service，本机 backend venv + 真 akshare）

| 标的 | available | 标准 | 货币 | 报告期 | 市值 | PE(TTM) | PB | ROE | 营收 | EPS | 名称 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **600519.SH 贵州茅台** | ✅ | CAS | CNY | 2026-03-31 | ¥1,550,101,185,240 | 18.74 | 5.72 | 10.57% | ¥54.7B | 21.76 | （A股源无名称，诚实 null）|
| **0700.HK 腾讯控股** | ✅ | HKFRS | HKD | 2025-12-31 | HK$4,056,738,000,000 | 15.23 | 3.18 | 21.13% | HK$751.8B | 24.749 | 腾讯控股 |
| **AAPL（US 回归）** | ✅ | US-GAAP | USD | 2026-03-28 | $4.33T | 35.67 | 40.58 | 141.5% | $451.4B | 8.26 | Apple Inc. |

- 第二次同日查询命中缓存（`symbol_fundamentals_cache`），provider 不再触网（EOD TTL 生效）。
- HK 无 debt_to_equity（源仅 DEBT_ASSET_RATIO）→ 诚实 null；shares_outstanding HK 诚实 null。
- A股名称无可达结构化源 → 诚实 null（详情页仍以 symbol 标识，可接受）。

## 4. 单位约定（焊进 parser，与 yfinance 一致以复用前端格式化器）

- 毛利率/净利率/ROE：akshare 百分数 → **分数**（÷100，对齐 yfinance profitMargins/returnOnEquity）。
- debt_to_equity / debt_to_asset：保留**百分数**（对齐 yfinance debtToEquity 量级）。
- 市值/营收/净利/股本：**raw 货币单位**（CN 元 from `stock_value_em`；HK = baidu 亿 ×1e8）。

## 5. 边界守护（与全系统红线一致）

- 仅数据库（akshare），无券商 SDK；akshare lazy-import（§12.10.2 请求路径无 trade，AST 守门含 `akshare_fundamentals.py`）。
- 基本面/新闻仅进 lookup 详情页缓存（`symbol_fundamentals_cache` 独立表），**不进任何策略/回测/推荐/账户路径**。
- no-AI：基本面=确定性真值；新闻=展示 + （CN/HK 标题已中文，B054 翻译边界保留但 CN/HK 无需触发）。
- 不可达 → `available=False` + reason（`source_unavailable`），非 500；失败快照不缓存（下次重试）。

## 6. 给 Codex F004 的复验指引

在生产 VM 复跑 `scripts/test/cn_hk_fundamentals_news_probe.py`（确认 VM host 可达性结论），并对部署后的 `/api/symbols/{600519.SH,0700.HK,AAPL}/fundamentals` + `/news` 贴**真返回数字/条目**（evaluator §29 实测证据硬段）。VM akshare 可达性可能与本机不同——若某函数在 VM 不可达，对应市场该项应诚实 `available=False`/空态（不阻塞 done，A股达成即核心价值）。
