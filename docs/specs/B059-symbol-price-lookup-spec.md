# B059 — 标的信息查询/展示（任意 ticker + 丰富详情页：价格+基本面+新闻，EOD）

> **批次类型：** 混合批次（4 generator + 1 codex）。**平台原语 + 用户便利功能。**
> **状态：** planning → building（2026-06-13 用户确认「标的查询」启动；scope 见 §1，2026-06-12 已讨论定）。
> **来源：** 2026-06-12 用户「可在系统内方便查询任意标的价格信息，类似专业交易软件」；两次 scope 选择=任意 ticker + 丰富详情页。
> **核心洞察（先复用再自研）：** 数据 + 图表大部分已是现成依赖（见 §3），本批主要是「组合已有 + 搭查询 surface」，非集成新平台。

---

## 1. 用户要什么

「可在系统内方便查询**任意标的**的价格信息，类似专业交易软件」。用户两次 scope 选择：
- **标的范围**：**任意 ticker**（非仅策略 universe）。
- **信息广度**：**丰富标的详情页**（价格 + 基本面 + 新闻）。

---

## 2. 必须先校准的预期（诚实，写进 UI）

- **EOD 收盘价，非实时行情**：数据是日线收盘价（每日 data-refresh 拉一次），**不做/不假装实时报价/盘中分时/逐笔**。界面标「**收盘价 + as-of 日期 + 数据源**」，不误导成 live。
- **基本面仅美股**：SEC EDGAR 只有美股；非美 ticker → 只有价格、无基本面，**诚实降级标注**（不留空像 bug）。

---

## 3. 复用已有（先复用再自研，已核实 2026-06-13）

| 需要 | 已有现成 | 位置 |
|---|---|---|
| **任意 ticker 价格+基本面+新闻数据** | **yfinance**（库已是依赖，arbitrary ticker，免费）| `workbench_api/data/yfinance_loader.py` |
| 价格（EOD）| Tiingo | `tiingo_loader.py` |
| 美股基本面（权威）| SEC EDGAR + XBRL | `sec_edgar_loader.py` / `fundamentals_loader.py` / `xbrl_parser.py` |
| 新闻 | B034/B035 新闻子系统 | `news/` |
| **专业图表 UI** | **`lightweight-charts`（TradingView）+ echarts** | `frontend/package.json`（已装）|
| 限流/成本守门 | `cost_guard.py` | `workbench_api/data/cost_guard.py` |

> 所以本批 ≈「把已有 loader 接到按需查询端点 + 用已装的 TradingView 图表搭详情页」，不集成新平台。

---

## 4. 范围

**做（分 3 期，批次内）：**
- **P1 价格详情**：任意 ticker → on-demand 拉价 + 缓存 + 限流 → 收盘价 + 历史曲线图（lightweight-charts）+ 52 周高/低 + 区间收益。
- **P2 基本面**：SEC 美股（权威）+ yfinance 补充字段；非美 ticker 诚实降级。
- **P3 新闻**：复用 B034/B035，扩「按 symbol 查」。

**硬边界（红线）：**
- **research-only / no-broker**：**绝不加买卖按钮**（`no-execution-buttons` 守门）；不接 broker SDK（`test_no_broker_sdk_imports` 守门，禁 alpaca/polygon/tradier 等——yfinance/Tiingo/SEC 数据源不在禁列，OK）。
- **no-AI**：只展示数据，**不预测涨跌**、不"AI 说会涨"。
- **§12.10.2**：按需拉取若 import `trade` 须 off-request-path（异步 job）；若用 workbench data loader（不 import trade）可请求路径内但须缓存 + 限流。AST 守门必过。
- **诚实标注**：EOD/as-of/数据源（real/fixture）/基本面 US-only 降级。
- **新路由配套**（B057 教训）：新增后端路由前缀须同步进 `next.config` PROXIED_PREFIXES + `dev-rewrites-cover-backend-api` 守门测试。
- **新页 disclaimer**（safety 守门）：新 navigable 路由须渲染 canonical disclaimer。

**不做：** 实时/盘中行情；交易/下单任何入口；AI 预测；非美基本面硬造。

---

## 5. Feature 分解（5 features，4g + 1c）

| id | executor | 标题 |
|---|---|---|
| F001 | generator | P1 后端：标的数据服务（provider 抽象 + on-demand 拉价 + 缓存 + cost_guard 限流 + 无效 ticker 报错）+ 价格查询(收盘/历史/52周/区间收益) |
| F002 | generator | P1 前端：标的搜索 + 价格详情页（lightweight-charts 图 + 统计 + EOD/as-of/源 诚实标注，中文，新页 disclaimer）|
| F003 | generator | P2 基本面富化（SEC 美股 + yfinance 字段；非美降级）后端 + 详情页区块 |
| F004 | generator | P3 新闻富化（复用 B034/B035 扩 symbol 查询）后端 + 详情页区块 |
| F005 | codex | L1+L2 真机：任意 ticker 查询 + EOD/no-execution/no-AI 边界 + US-only 降级 + 缓存/限流 + Master/B058 不破 + signoff |

### F001 — P1 后端标的数据服务（generator）
1. **Provider 抽象**：定义 `SymbolDataProvider` 接口（get_price_history / get_quote / get_stats）；**yfinance 作首个实现**（任意 ticker，免费）；抽象留后路（未来 yfinance 不稳→换/加 Finnhub/FMP，**不提前集成付费**）。
2. **On-demand 拉取 + 缓存**：查询 → 先查缓存（DB 表 / 复用 price_history，按 symbol + as-of TTL，EOD 日 TTL）→ 命中即返、未命中按需拉 + 写缓存。
3. **限流**：复用 `cost_guard` 防任意 ticker 打爆外部 API。
4. **无效 ticker 报错**：清晰 actionable（非模糊 500）。
5. **价格查询**：最新收盘 + 历史序列 + 52 周高/低 + 区间收益（1M/3M/6M/1Y/YTD）。
6. **边界**：§12.10.2 AST 守门过（不在请求路径 import trade；若 yfinance_loader 不 import trade 则请求路径内 OK，否则异步 job）；no-broker 守门过；新路由进 next.config PROXIED_PREFIXES + 守门测试。
7. **测试**：provider 抽象 + 缓存命中/未命中 + 限流 + 无效 ticker + 价格统计；§12.10.2/no-broker 守门。
8. Gates：backend pytest ≥ baseline+ / ruff / mypy 0 / api.ts drift / alembic head（若加缓存表）。

### F002 — P1 前端价格详情页（generator）
1. **标的搜索框** + **价格详情页**：lightweight-charts 历史价格图（line/candle）+ 最新收盘 + 52 周高低 + 区间收益。
2. **诚实标注**：收盘价 + as-of 日期 + 数据源 badge；**无任何买卖按钮**；新页渲染 disclaimer。
3. 中文 + i18n parity + api.ts 同步。
4. **测试**：vitest（搜索/图渲染/诚实标注/无 execution 入口）+ i18n parity + disclaimer-present 守门。
5. Gates：frontend vitest/tsc/lint / i18n parity / api.ts drift 0 / safety（disclaimer + no-broker-frontend）。

### F003 — P2 基本面（generator）
SEC 美股基本面（复用 `fundamentals_loader` / xbrl）+ yfinance 补充（市值/PE/营收/利润率等）；**非美 ticker 诚实降级**（"基本面仅美股"）；详情页基本面区块（中文 + as-of + 源）。测试：US 有基本面 / 非美降级 / 字段映射。Gates 同 F001/F002。依赖 F001。

### F004 — P3 新闻（generator）
复用 B034/B035 新闻子系统，扩"按任意 symbol 查"（现按 sleeve universe）；详情页新闻区块（标题 + 源 + 时间，中文，复用 title_zh 翻译）；无新闻诚实空态。测试：symbol 新闻查询 + 空态。Gates 同上。依赖 F001。

### F005 — Codex L1+L2 + signoff（codex）
L1 全门禁。L2 真 VM：① **任意 ticker 查询**：查一个 universe 内（如 SPY）+ 一个 universe 外任意美股（如 NVDA）+ 一个无效 ticker（报错 actionable）；② **EOD 诚实**：界面标收盘价/as-of/源，无实时假象；③ ★**边界**：无任何买卖按钮（no-execution）、无 AI 预测（no-AI）、无 broker SDK；④ **US-only 基本面降级**：非美 ticker 只价格无基本面且诚实标注；⑤ **缓存/限流**：重复查命中缓存、不打爆外部 API；⑥ Master/B058 推荐/模拟盘/执行不破 + recent-errors=0 + HEAD≡main；⑦ 演练自清。Signoff（§任意 ticker 证据 + §EOD/边界 + §US-only 降级 + §缓存 + §不破 + §Ops）。

---

## 6. 风险与缓解

| 风险 | 缓解 |
|---|---|
| yfinance 非官方/可能失效 | provider 抽象留后路（未来换/加 Finnhub/FMP）；失效时 actionable 报错不白屏 |
| 任意 ticker 打爆外部 API | cost_guard 限流 + 缓存（EOD 日 TTL） |
| 被误读为实时行情 | UI 强标收盘价 + as-of；不做盘中 |
| 误加交易入口 | no-execution-buttons 守门 + F005 验无买卖按钮 |
| §12.10.2 破边界 | F001 守门测试；若 import trade 走异步 job |
| 新路由 dev 代理漏 | B057 教训：同步 next.config PROXIED_PREFIXES + 守门测试 |

## 7. Core Acceptance（一句话）

用户能在系统内**查询任意 ticker** 的**价格（EOD 收盘+历史图+统计）+ 美股基本面 + 新闻**，全部诚实标注（收盘价/as-of/源/US-only 降级），**无任何交易入口、无 AI 预测**；复用已有 yfinance/SEC/新闻/lightweight-charts，**且 Master/B058 不破**。
