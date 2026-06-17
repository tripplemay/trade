# B064 Signoff 2026-06-18

> **状态：** ✅ **L1 + L2 FULL PASS → B064 DONE**  
> **批次：** B064 — A股+港股 基本面+新闻（lookup 展示）= A股数据源 P2  
> **定位：** B059 `/symbols` 详情页对 A股(.SH/.SZ)+港股(.HK) 展示真实基本面（CAS/HKFRS 口径）+ 真实个股新闻  
> **Evaluator：** Claude CLI（evaluator 角色，代 Codex 执行）

---

## 实测证据硬段（evaluator §29，非「端点存在」）

### A股 600519.SH（贵州茅台）基本面 — VM 真值

| 字段 | 实测值 |
|---|---|
| **source** | akshare |
| **currency** | CNY |
| **accounting_standard** | CAS |
| **as_of_report** | 2026-03-31 |
| **market_cap** | ¥1,550,101,185,240（约¥1.55万亿）|
| **trailing_pe** | 18.74 |
| **price_to_book** | 5.72 |
| **return_on_equity** | 0.1057（= 10.57%）|
| **profit_margins** | 0.5222（= 52.22%）|
| **revenue** | ¥54,702,912,385（约¥547亿）|
| **eps** | 21.76 |
| **debt_to_equity** | 14.32 |
| **shares_outstanding** | 1,250,081,601 |

### 港股 0700.HK（腾讯控股）基本面 — VM 真值

| 字段 | 实测值 |
|---|---|
| **source** | akshare |
| **long_name** | 腾讯控股 |
| **currency** | HKD |
| **accounting_standard** | HKFRS |
| **as_of_report** | 2025-12-31 |
| **market_cap** | HK$4,056,737,999,999（约HK$4.06万亿）|
| **trailing_pe** | 15.23 |
| **price_to_book** | 3.18 |
| **return_on_equity** | 0.2113（= 21.13%）|
| **revenue** | HK$751,766,000,000（约HK$7518亿）|
| **eps** | 24.749 |
| **net_income** | HK$224,842,000,000（约HK$2248亿）|

### A股 600519.SH 新闻 — VM 真条目（ingest 10 条）

| # | ticker | 标题（截断至 55 字符）| published_at |
|---|---|---|---|
| 1 | 600519.SH | 贵州茅台：余思明获聘董事会秘书 | 2026-06-12 02:27 UTC |
| 2 | 600519.SH | 25只个股大宗交易超5000万元 | 2026-06-14 23:59 UTC |
| ... | ... | (共 10 条中文新闻) | ... |

### 港股 0700.HK 新闻 — VM 真条目（ingest 10 条）

| # | ticker | 标题（截断至 55 字符）| published_at |
|---|---|---|---|
| 1 | 0700.HK | 腾讯控股00700.HK)6月17日回购111.80万股，耗资5.01亿港元 | 2026-06-17 13:07 UTC |
| 2 | 0700.HK | 腾讯控股00700.HK)6月16日回购5.01亿港元，年内累计回购199.02亿港元 | 2026-06-16 14:51 UTC |
| 3 | 0700.HK | 腾讯控股00700.HK)6月15日回购108.10万股，耗资5.01亿港元 | 2026-06-15 13:13 UTC |
| ... | ... | (共 10 条，标题均中文) | ... |

### 美股 AAPL 零回归 — VM 真值

| 字段 | 实测值 |
|---|---|
| **provider** | YFinanceSymbolProvider（US path，无改动）|
| **company_name** | Apple Inc. |
| **currency** | USD |
| **market_cap** | $4,346,723,172,352（约$4.35T）|
| **trailing_pe** | 35.83 |
| **accounting_standard** | US-GAAP |
| **AAPL news count in DB** | 201 条（现有，零改动）|

---

## L1 门禁

✅ **FULL PASS**

| 门禁项 | 结果 | 数值 |
|---|---|---|
| **Backend pytest** | ✅ | 1367 passed, 17 skipped |
| **Backend mypy (CI-exact, 416 files)** | ✅ | 0 errors |
| **Backend ruff** | ✅ | All checks passed |
| **Safety tests** | ✅ | 158 passed, 15 skipped |
| **Frontend vitest** | ✅ | 334 passed (52 test files) |
| **Frontend tsc** | ✅ | 0 errors |
| **Frontend eslint** | ✅ | 0 warnings |
| **i18n parity (en/zh-CN)** | ✅ | 0 missing keys |

---

## L2 生产真机验证

✅ **FULL PASS**

### 环境状态

| 项 | 结果 |
|---|---|
| **API 健康** | ✅ status=ok, db_connectivity=ok, recent-errors=0 |
| **部署版本** | ✅ f7e93d6（B064 最后功能 commit）|
| **Alembic head** | ✅ `0026_b064_symbol_fundamentals_cache` |
| **symbol_fundamentals_cache 表** | ✅ 独立存在，schema 完整 |

### §23 VM 端点可达性（复验）

| 函数 | VM 结果 | 说明 |
|---|---|---|
| `stock_individual_info_em` | ❌ JSONDecodeError | 弃用（同本机结果）|
| `stock_financial_abstract` | ✅ 80 rows | CN 基本面（选用）|
| `stock_financial_analysis_indicator` | ✅ 13 rows | CN 备选 |
| `stock_hk_spot_em` | ❌ RemoteDisconnected | eastmoney push host（弃用，B062 同族）|
| `stock_financial_hk_analysis_indicator_em` | ✅ 9 rows | HK 基本面（选用）|
| `stock_hk_indicator_eniu` | ✅ 4009 rows | HK 估值备选 |
| `stock_news_em (CN 600519)` | ✅ 10 rows | CN 新闻（选用）|
| `stock_news_em (HK 00700)` | ✅ 10 rows | HK 新闻（选用）|

**结论：港股基本面+新闻 VM 可达（§23 最大未知已正面解决）。无需诚实空态降级。**

### A股 + 港股 基本面验证

- ✅ CN provider: `CnSymbolProvider.get_stats('600519.SH')` → 真值（见实测证据硬段）
- ✅ HK provider: `HkSymbolProvider.get_stats('0700.HK')` → 真值（见实测证据硬段）
- ✅ 货币感知：CNY / HKD 分别正确
- ✅ 会计准则：CAS / HKFRS 分别标注
- ✅ 缓存表 `symbol_fundamentals_cache` 独立，不触 price_snapshot/price_history/recommendation_snapshot

### 新闻 ingest 验证

- ✅ `ingest_symbol_news(session, ref_cn)` → 10 new items ingested（600519.SH）
- ✅ `ingest_symbol_news(session, ref_hk)` → 10 new items ingested（0700.HK）
- ✅ **cache-first 生效**：第二次 ingest 返回 0 new items
- ✅ 中文标题（无需 B054 翻译触发）
- ✅ DB 真实存在：600519.SH 10条，0700.HK 10条

### 美股零回归

- ✅ `AAPL` → `YFinanceSymbolProvider`（US gate 不破）
- ✅ SPY → `market=US`（路由不变）
- ✅ AAPL news: 201 条现有数据无改动

---

## 边界 adversarial 核查

| 边界 | 状态 |
|---|---|
| **no-broker**（无券商 SDK）| ✅ akshare_fundamentals.py / cn_hk_news.py：无 futu/tiger/okx import |
| **akshare lazy-import**（§12.10.2）| ✅ `import akshare as ak` 在函数体内（line 70 两个模块均相同） |
| **AST 守门**（新模块入 allowlist）| ✅ test_symbols_request_self_contained.py：`akshare_fundamentals.py`（line 49）、`cn_hk_news.py`（line 52）均在 allowlist |
| **no-trade import**（请求路径）| ✅ 两个新模块无 `import trade` |
| **research-safe / lookup only**（不进策略路径）| ✅ 仅 lookup 路由（/symbols/{symbol}/fundamentals、/news）；recommendation_snapshot=16 rows 无变动 |
| **no-AI 预测**（基本面/新闻无 AI）| ✅ 确定性数值直取 akshare；新闻展示不生成观点；CN/HK 新闻标题中文免触 B054 |
| **缓存隔离**（独立表不破策略）| ✅ symbol_fundamentals_cache 独立；price_snapshot/price_history/price_history 策略表无变动 |
| **trade 离线**（本批不碰 trade）| ✅ trade/ 本批零修改 |
| **no-execution / disclaimer**（安全守门）| ✅ safety tests 158 passed；no-resizable-panel + disclaimer + production-callback-url |

---

## 不变量核查（spec §6）

1. ✅ **美股 lookup 零回归**：AAPL 基本面/新闻/价格路径无变动
2. ✅ **Master/策略/回测路径零回归**：recommendation_snapshot=16 rows
3. ✅ **trade 离线不破**：本批零改 trade/
4. ✅ **§12.10.2 请求路径无 trade import**：AST 守门绿
5. ✅ **no-execution / no-AI / no-broker / disclaimer**：全通过
6. ✅ **缓存隔离**：symbol_fundamentals_cache 独立表

---

## 交付物确认

✅ **F001** — A股+港股基本面 market-aware + symbol_fundamentals_cache（migration 0026）  
✅ **F002** — on-demand cache-first 新闻 ingest → news 表（幂等，ticker 关联）  
✅ **F003** — 详情页基本面区块（货币感知 ¥/HK$/$ + CAS/HKFRS 口径 + 诚实源/as-of + 中文新闻）  
✅ **F004** — L1+L2 全 PASS + 边界 adversarial + 实测证据硬段（本报告）  

---

## 签收结论

### Status：✅ **L1 + L2 FULL PASS → B064 DONE**

**B059 /symbols 详情页 A股+港股真实展示达成**：
- 价格 + 基本面（CAS/HKFRS 口径，货币感知）+ 个股新闻（中文）三段完整
- 港股基本面+新闻源 VM 可达（§23 最大未知正面解决）
- 美股 AAPL 零回归（US-GAAP / USD / yfinance 路径不变）
- 所有硬边界守住（no-AI / no-broker / research-safe / trade 离线）
