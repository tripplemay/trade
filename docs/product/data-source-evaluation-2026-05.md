# Data Source Evaluation（2026-05-25）

> **状态：** **approved**（2026-05-25 用户批准）
> **配套：** `docs/product/roadmap-2026-05.md` Stream 1.A + 1.B + 1.C
> **目的：** 为 Stream 1（Real data ingest）做数据源选型，作为 Stream 1.A spec 的权威输入。
> **范围：** 价格 + 财务 + News（仅简提，详细见 Stream 2 / 单独 doc）+ 选型 + 架构 + cost。

---

## 1. 选型约束（用户已批 2026-05-25）

| 维度 | 用户偏好 | 含义 |
|---|---|---|
| 资产范围 | 美股 ETF + 美股个股 + 港股/中概（**US-listed ADR/ETF proxy 优先**）| 不引入港股原生 paid 数据 |
| 财务数据 | 中等优先 | 价格先做（Stream 1.B），财务后一批次（Stream 1.C）|
| Point-in-time 严格度 | **严格** | 防未来函数；财报披露日后才可见；strategy doc §5.3 + B025 spec §4.1 都已要求 |
| 接入频率 | **历史 snapshot 一次性入仓 + 每日 EOD 增量** | B009 snapshot 路径增强；CI 仍离线（读 fixture-shaped 本地数据）|
| Cost 预算（含本 doc + doc C LLM）| ¥500-2000/月 | 本 doc 数据源预算建议 ¥200-700（剩余给 LLM）|

## 2. 资产范围细化

### 2.1 美股 ETF（必需，所有 sleeve 都用）

当前 Master Portfolio 4 sleeve 涉及的 ETF（保守列表，实际更多）：

| Sleeve | 主要 ETF |
|---|---|
| Momentum | SPY / QQQ / IWM / EFA / EEM / TLT / GLD |
| Risk Parity | SPY / TLT / IEF / GLD / VNQ |
| Defensive / Cash | SGOV / BIL / SHY |
| Benchmarks（对比用）| RSP / VTI |

### 2.2 美股个股（B025 us_quality_momentum 30-50 ticker）

B025 fixture `data/fixtures/us_quality_momentum/universe.csv` 已定义 30-50 ticker（横跨 ≥7 GICS sector）。Stream 1.B 真数据替换时直接复用此 universe。

### 2.3 港股 / 中概（US-listed proxy）

按用户偏好走 **US-listed ADR/ETF**：

| Theme | US-listed proxy（无需港股 paid 数据）|
|---|---|
| China broad | FXI / MCHI / KWEB |
| HK | EWH |
| Tech / Internet ADR | BABA / PDD / NTES / TCEHY |
| 新能源车 | NIO / XPEV / LI |

**HK-China satellite (BL-B011-S2) Stream 2 / 后续批次** 可走这些 proxy，不引入港股原生数据。

### 2.4 不在范围

- ❌ FX / 货币兑换（multi-currency 暂不在范围；用户全部投资资产以 USD 主导）
- ❌ 港股原生（如 0700.HK 腾讯原股，paid 数据 ≥$200/月）
- ❌ 加密 / 保险 / 房产（positioning §6 永久 YAGNI）
- ❌ 期权 / 期货（vol-target / VIX overlay 是 backlog low，暂不需）
- ❌ 实时 intraday tick（EOD 足够 quarterly + daily monitoring 使用）

## 3. 数据源对比 — 价格

### 3.1 Free / 半 free

| Provider | Cost | ETF+个股 | 港股 ADR | EOD 历史 | EOD 增量 | PIT 价格 | Rate limit | 注释 |
|---|---|---|---|---|---|---|---|---|
| **yfinance** | 免费 | ✅ | ✅（HK suffix）| 30+ 年 | ⚠️ 偶尔被限 | ⚠️ 历史已修正（split adjusted retroactively）| 无明示但易被禁 | 非官方 wrapper of Yahoo Finance；不可靠 |
| **Alpha Vantage** | Free tier 5/min, 500/day | ✅ | ⚠️ 部分 | 20+ 年 | ✅ | ✅ | 5/min 免费 / 75/min Premium $50 | 官方 API，但 free tier 慢 |
| **IEX Cloud (Cloud retired 2024, replaced by IEX Cloud 2.0 / Flexible plan)** | 旧免费 tier 退役 | ✅ 美股 | ❌ | 10 年 | ✅ | ✅ | 严格 | 2024 后定价方案重组，需重新评估 |
| **Stooq** | 免费 | ✅ | ✅ | 30+ 年 | ⚠️ 部分 | ⚠️ | 无 | 数据质量参差 |
| **FRED** (Federal Reserve) | 免费 | ❌（只宏观）| ❌ | ✅ | ✅ | ✅ | 无明示 | 宏观经济数据（10y / VIX / CPI 等），辅助 Stream 2 market context |

### 3.2 Paid Starter tier（**推荐主选**）

| Provider | Cost ($/月) | ETF+个股 | 港股 ADR | EOD 历史 | EOD 增量 | PIT | Rate limit | 注释 |
|---|---|---|---|---|---|---|---|---|
| **Polygon.io Starter** | **$30 (~¥200)** | ✅ 全美股 | ✅ ADR | 20+ 年 | ✅ 每日 EOD（盘后 ~6pm ET）| ✅ 严格 | 5 req/min unlimited 历史 | **推荐主选**：覆盖全 + PIT + 文档好 |
| **Tiingo Starter** | $10 (~¥70) | ✅ 美股 | ⚠️ 部分 ADR | 30+ 年 | ✅ | ✅ | 60 req/hour | 便宜，覆盖略次于 Polygon |
| **Alpha Vantage Premium** | $50 (~¥350) | ✅ | ⚠️ | 20+ 年 | ✅ | ✅ | 75/min | 较贵且无明显优势 |
| **EODHD Fundamentals + EOD** | $30-100 (~¥200-700) | ✅ + 财务 | ✅ | 30+ 年 | ✅ | ✅ | 100K req/day | 可同时覆盖价格 + 财务（Stream 1.C 选型时再评）|

### 3.3 Paid Developer / Institutional（**不推荐**，超预算）

| Provider | Cost | 注释 |
|---|---|---|
| Polygon Developer | $200 (~¥1400) | 含 unlimited rate + tick 级 + options |
| EODHD All-in-One | $250+ (~¥1750) | 全市场 + tick + options |
| FactSet / Refinitiv | $1000+ | institutional only |
| Bloomberg API | $2000+ | institutional only |

## 4. 数据源对比 — 财务（point-in-time）

**Stream 1.C 用，本 doc 不锁定，仅列候选：**

| Provider | Cost | PIT 严格度 | Parse 难度 | 覆盖 | 注释 |
|---|---|---|---|---|---|
| **SEC EDGAR** | 免费 | ✅ 严格（原始 filing date）| ⚠️ 自己 parse XBRL | 美股全 | **首选**（免费 + 最严格 PIT）|
| **Polygon Fundamentals** | 含在 Polygon Starter $30 | ✅ | ✅ 已 parse | 美股 | 与 Stream 1.B 同 provider |
| **EODHD Fundamentals** | $30-100 | ✅ | ✅ 已 parse | 美股 + 部分国际 | 单独 paid，质量良好 |
| **AlphaVantage Fundamentals** | $50 | ⚠️ 部分 | ✅ | 美股 | 不如 Polygon / EODHD |

**Stream 1.C 决策建议（待 Stream 1.B 完成后再细化）：**

1. **首选**：SEC EDGAR 自 parse（免费 + 最严 PIT）
2. **若 SEC EDGAR parse 成本高于 paid**：Polygon Fundamentals（与 Stream 1.B 同 provider，cost = $30 已含）
3. **若 Polygon 不够覆盖某些 ratio**：补 EODHD Fundamentals $30-100

## 5. 数据源对比 — News（Stream 2 范围，简提）

不在本 doc 详细评估；详见后续单独 doc。候选简介：

| Provider | Cost | 注释 |
|---|---|---|
| **SEC EDGAR filings** | 免费 | 监管文件原文（10-K / 10-Q / 8-K），与 quant signal 高质量关联 |
| **Bloomberg RSS public** | 免费 | 公开 RSS feed，标题级 |
| **Yahoo Finance RSS** | 免费 | 标题 + 摘要 |
| **NewsAPI** | $0-449 | 全网 news aggregator |
| **Tiingo News** | 含在 Tiingo Starter | 与 ticker 关联预处理 |

## 6. 推荐配置（v0.9.28 起 Stream 1.A 落地参考）

### 6.1 Stream 1.A + 1.B（价格）

**首选：Polygon.io Starter $30/月**

理由：
- 覆盖全（ETF + 个股 + ADR + 港股 proxy）
- 严格 PIT（split adjusted historical correctly）
- 历史 backfill 20+ 年 + 每日 EOD 增量稳定
- 含 Polygon Fundamentals（Stream 1.C 同 provider 一站式）
- Rate limit 5/min 对 batch backfill 足够（30-50 ticker × 1 day = 5-10 min 跑完）

**备选 / 双源 cross-check（可选）**：yfinance 免费 + Alpha Vantage free tier — 用作 Polygon 数据异常时的 cross-validation（不作为主源）。

### 6.2 Stream 1.C（财务）

**首选：SEC EDGAR 免费**（自己 parse XBRL）

**触发降级到 paid 的条件：**
- SEC EDGAR XBRL parse 成本（开发时间）超过 3-5 天
- 某些 ratio（如 EV/EBITDA / FCF Yield）SEC 原文需要计算且容易出错
- 跨国公司（如 BABA / TSM 等 ADR）SEC 数据不全

**降级到 paid 选项**：
- 已含在 Polygon Starter 的 Polygon Fundamentals（cost = $0 额外）
- 或 EODHD Fundamentals $30-100（含国际 ADR）

### 6.3 News（Stream 2，简定）

**MVP 首选**：SEC EDGAR filings + Yahoo Finance RSS + FRED（免费 + 高质量 + 与 quant signal 强关联）。

详细评估留 Stream 2 spec / 单独 doc。

## 7. 架构方案

### 7.1 历史 snapshot backfill

```
data/snapshots/
├── prices/
│   ├── polygon/                      # provider-specific raw
│   │   ├── SPY-2010-2026.csv
│   │   ├── QQQ-2010-2026.csv
│   │   └── ...
│   └── unified/                      # normalized fixture-shaped
│       ├── prices_daily.csv          # 与 B025 fixture 同 schema
│       └── ...
└── fundamentals/
    ├── sec_edgar/
    │   └── <ticker>/<cik>/...filings parsed
    └── unified/
        └── fundamentals.csv          # 与 B025 fixture 同 schema
```

**关键设计：**

- **provider-specific 与 unified 双层存储**：raw 保留（便于 cross-check），unified 走 fixture schema（B009 / B025 已锁定的 column 顺序与命名）
- **fixture-shaped unified 层是 CI 离线路径**：测试不读 raw / 不调 API；strategy 代码不区分"真数据 vs fixture"（都读 unified 层）
- **PIT enforcement at loader layer**：`trade/data/loader.py` 接收 `as_of_date` 参数，过滤 unified.report_date <= as_of_date

### 7.2 每日 EOD 增量

**Cron job（B009 snapshot 路径扩展）：**

```
每天美股盘后 21:30 UTC（4:30 PM ET）：
1. Polygon API 拉取所有 universe ticker 当日 OHLCV
2. append 到 data/snapshots/prices/polygon/{ticker}-*.csv
3. 同时 append 到 data/snapshots/prices/unified/prices_daily.csv
4. 触发 dependent 路径（如 Recommendations refresh / Risk Panel update）
```

**幂等 + 容错：**

- 同日重复跑不重复 append（dedupe by (date, ticker)）
- API 5xx / rate limit / network fail → retry 3 次 + slack/log alert
- 周末 / 假期不跑（NYSE 日历）

### 7.3 CI 离线约束

- **CI 不调 Polygon / SEC EDGAR / 任何外部 API**
- pytest 读 `data/fixtures/` （B025 已建立 schema） + 测试样本 `data/snapshots/unified/` 子集
- 增量 cron job 在 production VM 跑，CI 不跑

## 8. Cost 预算分配

| 项 | 月预估 |
|---|---|
| Polygon Starter $30 = ¥200 | ¥200 |
| EODHD Fundamentals（可选，Stream 1.C 触发降级时启用）$30-100 | ¥0-700 |
| FRED / SEC EDGAR / Yahoo RSS（全部免费）| ¥0 |
| **数据源小计** | **¥200-900** |
| LLM API（doc C，预估 cap ¥1500）| ¥500-1500 |
| **合计 月预算 cap** | **¥700-2400**（与 roadmap §2 ¥500-2000 接近上限；EODHD 上线时需 review）|

## 9. 不做的事

- ❌ 实时 intraday tick（cost 高 + 用户场景不需要）
- ❌ Options / futures 数据
- ❌ Bloomberg / FactSet / Refinitiv institutional API
- ❌ 港股原生 paid 数据（走 US-listed ADR proxy）
- ❌ FX / crypto / 房产 / 保险
- ❌ 多 provider 并行调用相同 endpoint（cross-check 仅对异常做）
- ❌ Real-time websocket（EOD 足够）
- ❌ 在业务代码 import yfinance / polygon-api-client 等 SDK（强制走 `trade/data/loader.py` Repository 层）
- ❌ CI 跑 live API call（fixture-first 永久边界）

## 10. 验证与 cross-check 策略

### 10.1 Initial backfill 验证

- 拉取后跑 `scripts/validate_snapshot.py`：
  - 行数 = expected trading days × ticker count（±0.5%）
  - 价格非负、volume 非负
  - 与 yfinance free 抽样 cross-check（≥5 ticker × 5 random dates）
  - 与 FRED 指数（SPY → S&P 500 close）误差 < 0.5%

### 10.2 Daily EOD 增量验证

- 每日 cron 完成后跑 light validation：
  - 当日 ticker 拉取数 == universe size
  - 当日 close 与 t-1 跨度 [-15%, +15%]（异常熔断报 alert）
  - 周末 / 假期不应跑

### 10.3 Provider 异常 fallback

- Polygon 5xx 或 rate limit 触顶 → 当日 fallback yfinance + Alpha Vantage free + 等次日 Polygon 重试
- 连续 7 天 fallback → 报告升级（人工 review）

## 11. 后续 batch 依赖

- **Stream 1.A spec** 必须基于本 doc §6（推荐）+ §7（架构）+ §9（不做的事）
- **Stream 1.B 历史价格 snapshot batch** 实施时落地 §7.1 双层存储
- **Stream 1.C 财务 batch** 启动前重读本 doc §4 + §6.2，二次确认 SEC EDGAR vs paid 选型
- **doc F**（AI safety evals）独立，不与本 doc 强耦合

## 12. Doc Lifecycle

- **当前状态：** **approved**（2026-05-25 用户批准）
- **生效信号：** Stream 1.A spec acceptance 必须显式引用本 doc §6（首选 Polygon Starter）+ §7（双层存储 + PIT loader）+ §9（不做的事 9 条）
- **修订流程：** Provider 定价 / API 变化时需要修订；至少**每 12 个月校准**

---

> 配套：roadmap Stream 1.A + 1.B + 1.C；llm-provider-evaluation §6（cost 预算合计参考）+ positioning §6.1 AI 边界（PIT 严格性是 AI 输出可信度的下层基础）
