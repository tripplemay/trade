# B064 — A股 + 港股 基本面 + 新闻（lookup 展示）Spec

**批次定位：** A 股数据源 **P2**（接在 B061 A股价格地基 + B062 港股 provider 之后）。让 B059 标的详情页对 A股(.SH/.SZ) + 港股(.HK) 也能展示**真实基本面 + 个股新闻**，把详情页从「只有价格」丰富到「价格 + 基本面 + 新闻」三段——与 B059 美股详情页对齐。

**来源：** backlog `B0XX-ashare-data-source` §phase_plan P2；2026-06-18 用户拍板「基本面 + 新闻一起做」「A股 + 港股一并」。

---

## 1. 目标与边界

**目标：** B059 `/symbols` 详情页对 CN/HK 标的展示真实基本面（CAS 口径关键指标）+ 真实个股新闻，货币感知 + 诚实标源。

**红线边界（与全系统一致，硬性）：**
- **research-safe / lookup 展示 only**：接数据 ≠ 喂策略 ≠ 交易。基本面/新闻只进 lookup 详情页，**不进任何策略/回测/推荐/账户路径**。A股策略是 P3 远期。
- **no-broker**：只接数据库（akshare/baostock），**不接券商 SDK**（futu/tiger 在 safety 禁列）。
- **no-AI 预测**：展示真实数据 + 确定性指标，**不预测、不给收益预期、不替代 quant**。新闻翻译沿用 B054 边界（仅翻译，不增删改、不生成观点）。
- **§12.10.2 请求路径自包含**：所有 lookup 端点/服务**不得 import trade**；akshare/baostock **lazy-import**；新模块必须进 `tests/safety/test_symbols_request_self_contained.py` allowlist + 覆盖检查。
- **EOD + 诚实标注**：基本面/新闻均 EOD/快照口径；data_source（akshare/东财/sina 等非官方源）+ as-of 诚实标注；优雅失败（不可达 → `available=False` + reason，非 500）。
- **向后兼容铁律**：B059 美股详情页（yfinance 基本面 + SEC/Yahoo 新闻）+ 价格 lookup + Master/策略路径**零回归**。CNY/HKD 货币列与 US 共存（B061 已建 market/currency 维度）。

**不做（P3/延后）：** A股/港股策略·回测·交易规则（T+1/涨跌停/手数/ST）；领域信号（龙虎榜/北向/解禁）量化因子化；跨市场 FX/NAV 聚合；基本面进策略评分。

---

## 2. 复用清单（先复用再自研——核过源码）

| 复用资产 | 位置 | B064 用法 |
|---|---|---|
| B059 lookup 端点 | `routes/symbols.py`（`/{symbol}/fundamentals` L72-90、`/{symbol}/news` L93-111）| 端点签名不变，扩服务层支持 CN/HK |
| `SymbolDataProvider` 抽象 | `symbols/provider.py`（`ProviderStats` L57-101 含 15 基本面字段）| CN/HK provider 填充 `get_stats` 基本面字段（现仅返身份）|
| CnSymbolProvider | `symbols/cn_provider.py`（akshare `stock_zh_a_hist` qfq + baostock）| 加 A股基本面取数（lazy akshare）|
| HkSymbolProvider | `symbols/hk_provider.py`（akshare `stock_hk_daily` qfq）| 加港股基本面取数（lazy akshare）|
| provider 路由 | `symbols/service.py` `_resolve_provider`（L80-91，按 `SymbolRef.market`）| 路由已就绪，复用 |
| 基本面服务 + US-only 门禁 | `symbols/fundamentals.py`（`get_symbol_fundamentals` L37-93，US gate L51-65）| 改 market-aware：US→yfinance / CN·HK→akshare provider stats |
| 新闻表（ticker 关联）+ 仓储 | `db/models/news.py`（`title_zh` L78）+ `db/repositories/news.py`（`list_by_ticker` L89-100，`save_if_new` 幂等）| 复用表 + 仓储；新增 CN/HK 新闻入库 |
| 新闻 lookup 服务 | `symbols/news.py`（`get_symbol_news`，`title_zh` fallback）| 端点不变，复用读取 |
| B054 翻译子系统 | `news_translation/service.py`（`translate_title`，边界仅翻译）| 港股英文标题按需翻译；A股已中文免翻 |
| symbol_price_cache 隔离范式 | `db/models/symbol_price_cache.py`（独立表，migration 0024/0025，market/currency 列）| 基本面缓存照此范式新建独立表，隔离不破策略价格表 |
| §12.10.2 AST 守门 | `tests/safety/test_symbols_request_self_contained.py`（allowlist + 覆盖检查）| 新模块入 allowlist |
| SymbolRef 值对象 | `symbols/symbol_ref.py`（`Market`、`parse`、currency 派生）| 复用 market/currency 判定 |

**最新 alembic head：** `0025_b061_symbol_cache_market_currency` → 本批新 migration 从 **0026** 起。

---

## 3. 关键工程现实 + §23 硬前置（akshare 端点须实跑验证）

> **★方法论硬坑（焊进 acceptance，来源 framework v0.9.45 §23 / 铁律 9）：** akshare 不同数据（价格 vs 基本面 vs 新闻）走**不同函数、不同主机、不同可达性**。B062 港股价格端点 `stock_hk_hist` 撞 `33.push2his.eastmoney.com` 超时是前车之鉴。**基本面/新闻函数从没验过可达**——Generator 实施 F001/F002 时，**必须先从生产 VM（或等价环境）实跑候选 akshare 函数的真调用**（不只单测 mock），确认可达 + 真返回 shape + 字段，**选已验可达者**；做不到 → 该市场/数据该项标 `available=False` + 诚实 reason，**不假设兄弟函数可达**。

**候选 akshare 函数（Generator 须 §23 实跑选定，非硬指定）：**
- A股基本面：`stock_financial_abstract` / `stock_financial_analysis_indicator` / `stock_a_indicator_lg`（财务指标/估值）/ `stock_zh_a_spot_em`（实时含 PE/PB/市值）。
- 港股基本面：`stock_hk_spot_em`（估值）/ `stock_financial_hk_analysis_indicator_em`（港股财务指标）。**港股基本面源可达性是本批最大未知**（同 B062 港股端点教训）。
- A股个股新闻：`stock_news_em`（东财个股新闻）。
- 港股个股新闻：候选不确定 → **可达即接，不可达诚实空态**（不阻塞 done）。

**其它现实：** CN 用前复权 qfq（与价格 provider 一致）；基本面 CAS 口径（营收/净利/ROE/毛利率/资产负债率/PE/PB/市值等），与 SEC US-GAAP 不同 schema → 独立呈现 + 标注 CAS；货币 CNY/HKD 诚实标注。

---

## 4. Feature 拆解（4 features：3 generator + 1 codex）

### F001 — A股 + 港股 基本面取数 + 端点 market-aware（executor: generator）

**做什么：**
1. **§23 前置**：实跑候选 akshare 基本面函数（A股 + 港股），确认可达 + 字段 → 选定。港股若不可达 → 该项诚实 `available=False`，不假设。
2. CnSymbolProvider / HkSymbolProvider 新增基本面取数（lazy akshare），映射到 `ProviderStats` 基本面字段（CAS 口径关键指标）。
3. `symbols/fundamentals.py` 由 **US-only 门禁** 改 **market-aware**：US→yfinance（不变）/ CN·HK→对应 provider 的 akshare stats；非 equity / 不可达 → `available=False` + reason（`non_us` 语义改为按市场分流）。
4. **基本面缓存**（照 symbol_price_cache 隔离范式）：新表 `symbol_fundamentals_cache`（migration **0026**，含 symbol/market/currency/as_of/source/各指标/fetched_at），on-demand cache-first + EOD TTL + RateLimitGuard（避免请求路径慢/打爆 akshare）。隔离不破任何策略表。

**Acceptance（正面证据，决策/真数据项须实测——见 evaluator §29）：**
- `GET /api/symbols/600519.SH/fundamentals` → **真实茅台基本面真值**（如市值/PE/ROE 非空、CNY、source=akshare、as-of 标注），贴实测数字。
- `GET /api/symbols/0700.HK/fundamentals` → 真实腾讯基本面（HKD）**或** 诚实 `available=False`+reason（若港股源不可达，§23 实跑结论）。
- 美股 `GET /api/symbols/AAPL/fundamentals` **零回归**（仍 yfinance，US gate 不破）。
- §12.10.2：新增/改动模块入 AST 守门 allowlist，无 trade import；akshare lazy。
- 缓存隔离：`symbol_fundamentals_cache` 独立，不触 price_snapshot/price_history/symbol_price_cache 策略数据。

### F002 — A股 + 港股 个股新闻 ingest + 端点（executor: generator）

> **设计决策（planner）：** 现有美股新闻为 job/timer ingest（SEC/Yahoo，universe-bound）。但 lookup 是**任意 ticker**，不能预先 ingest 全市场。故 CN/HK 新闻采 **on-demand cache-first**：请求 `/{symbol}/news` 时 lazy akshare 取个股新闻 → `save_if_new` 入 news 表（幂等，ticker 关联）→ 复用 `get_symbol_news` 读取。偏离美股 job 范式有诚实理由（任意 ticker 不可预 ingest），Generator 若发现更优实现可偏离 + 报 planner 裁定（§22）。

**做什么：**
1. **§23 前置**：实跑 akshare A股个股新闻函数（候选 `stock_news_em`）确认可达 + shape。港股新闻源不可达 → 诚实空态。
2. 新增 CN/HK 新闻取数适配（lazy akshare）→ 规整为 News 行（source/ticker/title/url/published_at）→ `save_if_new` 入库（幂等）。on-demand cache-first（近端已 ingest 不重取）+ RateLimitGuard。
3. A股标题已中文免翻；港股若英文标题 → 复用 B054 `translate_title` 填 `title_zh`（边界仅翻译）。
4. `/{symbol}/news` 端点签名不变，CN/HK 走新 ingest 路径后由 `get_symbol_news` 读出。

**Acceptance：**
- `GET /api/symbols/600519.SH/news` → **真实茅台个股新闻条目**（标题/时间/链接，中文标题），贴实测条目。
- `GET /api/symbols/0700.HK/news` → 真实腾讯新闻 **或** 诚实空态（港股源不可达，§23 结论），不报错。
- 美股新闻 `GET /api/symbols/AAPL/news` **零回归**。
- §12.10.2 守门；akshare lazy；若新增 timer/job 须 deploy 接线（evaluator §24）+ 入口 env 守门（§12.11.1，若写生产 DB）。
- no-AI：新闻仅展示 + B054 翻译，无观点生成/无情绪预测。

### F003 — B059 详情页 A股 + 港股 基本面 + 新闻区块（executor: generator）

**做什么：**
1. `/symbols` 详情页：CN/HK 标的渲染**基本面区块**（CAS 指标 + 货币感知 ¥/HK$ + 诚实源/as-of 标注 + CAS 口径说明）+ **新闻区块**（复用 B059 新闻 UI，中文标题优先）。
2. `available=False` 时友好空态（双语，标明 reason：源不可达/非 equity），不漏英文原文。
3. i18n 双语（en + zh）parity；新增字段标签（CAS 指标名）双语。
4. no-execution / disclaimer 守门不破（无买卖按钮、详情页 disclaimer 仍渲染）。api.ts 重生 + drift 检查。

**Acceptance：**
- 详情页查 600519.SH → 价格图 + **真实基本面区块**（¥/CNY/CAS）+ **真实新闻区块**（中文）；0700.HK 同理（HK$/HKD）或诚实空态。
- AAPL 详情页**零回归**（基本面/新闻/价格全保留，$/USD）。
- vitest + tsc + eslint + i18n parity + api.ts drift 全绿；no-execution / disclaimer safety 守门过。

### F004 — Codex L2 真机验收 + signoff（executor: codex）

**做什么（决策/真数据批次——signoff 必含「实测证据」硬段，evaluator §29）：**
- L1 全门禁：backend pytest + mypy strict（`workbench_api + tests` CI-exact，§19）+ ruff；trade 不动（本批不碰 trade，确认离线不破）；frontend vitest/tsc/eslint/i18n parity/api.ts drift。
- **L2 真机实测（贴真返回，非"端点存在"）：**
  - 600519.SH 基本面**真值数字**（市值/PE/ROE 等）+ 个股新闻**真条目**。
  - 0700.HK 基本面 + 新闻：真返回**或**诚实 `available=False`/空态（§23 港股源结论），二者皆可 done，但须**贴实测结论**。
  - 美股 AAPL 基本面/新闻/价格**零回归**（pre/post 对比）；Master/策略路径不破；§12.10.2 请求路径无 trade。
  - HEAD ≡ prod；recent-errors=0；若有新 timer，systemd 接线 enabled+active（§24）。
- **边界 adversarial 抽验**：no-AI（基本面/新闻无预测/无观点生成）、no-broker、research-safe（基本面/新闻未进任何策略路径）。
- signoff 落 `docs/test-reports/`，**实测证据硬段逐条贴真观测**（缺真值 = 不得 done；"框架就绪/部署存在"不算）。

---

## 5. 状态流转 + 风险

- 普通混合批次：`planning → building（F001→F002→F003）→ verifying（F004 Codex）→ done`。
- **风险与缓解：**
  - 港股基本面/新闻源可达性（最大未知，§23）→ 实跑验，不可达诚实空态，**不阻塞 done**（A股达成即核心价值）。
  - akshare 非官方源失效 → provider 抽象 + 优雅失败 + 诚实 data_source。
  - 请求路径慢（akshare on-demand）→ cache-first + RateLimitGuard + EOD TTL。
  - 误接券商 SDK → 只 akshare/baostock，safety banlist 守门（§26.2 exact import-root）。

## 6. 不变量清单（Codex 回归核）

1. 美股 lookup（价格/基本面/新闻）零回归。
2. Master/策略/回测/推荐/账户路径零回归（基本面/新闻未进这些路径）。
3. trade 离线不破（本批不碰 trade）。
4. §12.10.2 请求路径无 trade import（AST 守门绿）。
5. no-execution / no-AI / no-broker / disclaimer 边界守。
6. 缓存隔离：`symbol_fundamentals_cache` 独立，不触策略价格表。
