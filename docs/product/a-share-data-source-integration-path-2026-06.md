# A 股数据源接入路径（2026-06-13）

> **作者：** Planner（用户 2026-06-13：基于 TradingAgents-astock 研究结论，规划接入 A 股数据源的路径）。
> **依据：** `docs/product/external-tradingagents-astock-assessment-2026-06.md`（借数据源/把领域信号量化化，**坚决不借 LLM 决策**）+ 现有数据架构核实。
> **立场：** 这是**数据源接入路径**，不是 A 股策略立项。诚实标明工程现实与边界。

---

## 0. 一句话结论

A 股数据接入应**数据先行、分层、复用 B059 的 provider 抽象**：先做一次 **feasibility spike**（验证免费 A 股数据库从我们 VM 真能跑），再把 A 股作为 **B059 `SymbolDataProvider` 的又一个 provider** 插入（价格优先），同时新建**符号/市场维度 + CN 交易日历**这两个横切地基。**接在 B059 之后**（B059 先把抽象的"插座"建好，A 股是"插头"）。基本面/新闻/币种/交易规则**逐期延后**。**借 TradingAgents 的数据源，不借它的 LLM 决策。**

---

## 1. 目标与边界

**目标：** 让系统能取到 A 股的**真实行情数据**（价格优先，后续基本面/新闻），为未来「A 股标的查询（B059 扩展）」「A 股策略/多市场（B055-P3/ 未来）」打地基。

**边界（红线，与全系统一致）：**
- **这是数据路径，不是策略承诺**：接数据 ≠ 建 A 股策略 ≠ 交易 A 股。严格数据先行。
- **借数据源，不借 LLM 决策**（TradingAgents 结论）：未来若用其领域信号（龙虎榜/北向/解禁），**翻译成确定性量化因子**，不做 LLM 辩论决策。
- **no-broker**：`futu`/`tiger`（富途/老虎券商 SDK）**在 safety 禁列**——但 A 股**数据库**（AkShare/baostock/Tushare/mootdx）不是券商、不在禁列，可接。**务必只接数据库、不接券商 SDK。**
- **no-AI**：数据展示/量化，不预测。
- **§12.10.2**：A 股 loader 入数据层（同 yfinance_loader），off-request-path / 缓存+限流的请求路径服务。
- **EOD + 诚实标注**：A 股也走 EOD 收盘价；数据源（akshare/baostock 等，非官方/scrape 类）+ as-of 诚实标注。

---

## 2. A 股数据源选型

| 库 | 覆盖 | 免费 | 特点 | 取舍 |
|---|---|---|---|---|
| **AkShare** | 价格/基本面/指数/龙虎榜/北向… 最广 | ✅ | 聚合东财/新浪/THS/TDX，社区最活跃、最广 | ✅ **首选**（一库多源，覆盖最全）|
| **baostock** | A 股历史价格/基本面，干净 | ✅ 无 token | 历史数据稳定、接口规整、无额度 | ✅ **价格地基备选/对照**（最稳的免费历史）|
| Tushare | 价格/基本面 | ⚠️ 好数据需 points/付费 | 老牌但免费档受限 | 暂不（避免付费） |
| mootdx | TDX 协议直连行情 | ✅ | TradingAgents-astock 用的；TDX 服务器 | 备选（直连，但协议层更底层）|
| futu/tiger SDK | — | — | **券商 SDK，禁列** | ❌ **不接** |

**建议：** **价格地基用 baostock（最稳免费历史）或 AkShare 二选一/互为 fallback**，基本面/领域数据后续用 AkShare（覆盖广）。**provider 抽象留多源 fallback**（任一非官方源可能失效）。

---

## 3. A 股数据的工程现实（必须正视的挑战）

1. **符号体系不同**：6 位代码 + 交易所后缀（`600519.SH` 沪 / `000001.SZ` 深 / `300xxx.SZ` 创业板 / `688xxx.SH` 科创）。现有模型 **US-implicit 无市场维度** → 必须加 **market/exchange 维度**（横切，触及全系统）。
2. **交易日历不同**：A 股按中国节假日，与 US 无重叠。现无 CN 日历 → 需新建。
3. **币种 CNY ≠ USD**：价格 CNY。跨市场组合/NAV 聚合需 FX → **延后**（等真要把 US+A 股放一个组合再做）。
4. **基本面 schema 不同**：A 股基本面来自东财/THS/AkShare（中国会计准则 CAS），**SEC EDGAR(美股 only) 路径不延伸** → A 股基本面是另一套源 + 另一套 schema。
5. **复权约定**：前复权/后复权 —— 须一致选一种（类比 US adjusted close）。
6. **非官方/scrape 类、ToS 灰**：免费 A 股源多爬东财/新浪或 TDX 协议（同 yfinance 风险）→ provider 抽象 + 诚实 data_source + 优雅失败。
7. **地理/访问风险（真实 ops）**：源在中国，部署 VM 在境外（GCP）→ 访问东财/新浪可能慢/偶发受阻。**这是首要 de-risk 项 → Phase 0 spike 必做**。
8. **领域数据（龙虎榜/北向/解禁）**：TradingAgents 的特色信号，AkShare 有 → 未来**量化因子化**，非本期。

---

## 4. 接入架构（分层）+ 与 B059 的关系

```
┌─ 符号/市场维度层（横切地基）：symbol = (code, market, exchange, currency)；US-implicit → 显式多市场
├─ 交易日历层：CN 日历（中国节假日）
├─ 数据 provider 层：A 股 provider（AkShare/baostock）插入 B059 SymbolDataProvider 抽象 ★复用
├─ data_refresh / 缓存层：A 股价格入数据层（同 yfinance），cost_guard 限流 ★复用
├─ 币种/FX 层（延后）：CNY 标注；跨市场聚合再做 FX
├─ 基本面层（延后）：A 股基本面(AkShare/CAS)，独立于 SEC
├─ 新闻层（延后）：A 股新闻源，扩 B034/35
└─ 交易规则层（最后，仅 A 股执行才需）：T+1/涨跌停/手数/ST
```

**★关键复用：B059 正在建 `SymbolDataProvider` 抽象**（任意 ticker provider 接口）。**A 股 = 该抽象的又一个 provider**。所以 A 股数据接入 ≈「加一个 CN provider + 符号市场维度 + CN 日历」，不另起炉灶。**这是 A 股接 B059 之后的最强理由**：插座先建好，插头才有处插。

> 附带价值：现有 `hk_china_universe.py` 用美股 ADR/ETF proxy 绕开 A 股数据（BL-B011-S2）；A 股数据地基建好后，未来可用真 A 股/港股数据**替换 proxy**，让 HK-China sleeve 更真。

---

## 5. 分期路径（建议）

| Phase | 内容 | 投入 | 产出 |
|---|---|---|---|
| **P0 可行性 spike**（**先做，de-risk**）| 验证 baostock/AkShare 从**生产 VM** 真能拉到 A 股 EOD（如 600519.SH 一年日线）+ 评估稳定性/延迟/额度 + 确认不引入禁用 broker SDK | S | 去/不去的事实依据（地理访问是最大未知）|
| **P1 数据地基 + A 股 lookup** | 符号/市场维度 + CN 交易日历 + A 股价格 provider 插 B059 抽象 + 入 data_refresh/缓存 + B059 详情页支持 A 股代码（EOD 诚实标注，CNY）| L | 用户能在 B059 查 A 股（600519.SH→贵州茅台价格/图），数据地基立 |
| **P2 A 股基本面 + 新闻** | AkShare A 股基本面（CAS schema，独立 SEC）+ A 股新闻扩 B034/35；B059 详情页 A 股区块 | M | A 股标的详情页丰富化 |
| **P3 A 股策略/回测/执行**（远期，B055-P3/未来）| A 股策略 + 回测 + 交易规则引擎(T+1/涨跌停/手数/ST) + 领域信号量化因子化 | XL | A 股策略模式（需 B057 框架 + 本数据地基）|
| **币种/跨市场组合** | CNY/USD FX + 跨市场 NAV 聚合 | M | 仅当真持有 US+A 股一个视图时做 |

**P3 的交易规则 + 领域因子量化化 = TradingAgents 借鉴的落点**（数据源→P0-P2，领域信号/规则→P3）。

---

## 6. 风险与缓解

| 风险 | 缓解 |
|---|---|
| **地理访问**（境外 VM 拉中国源不稳）| **P0 spike 先验**；不行则评估代理/镜像或换源；这是去/不去的关键 |
| 非官方源失效（同 yfinance）| provider 抽象多源 fallback（AkShare↔baostock）+ 诚实 data_source + 优雅失败 |
| 误接券商 SDK（futu/tiger 禁列）| 只接数据库（AkShare/baostock）；safety 守门兜底 |
| 符号/日历/币种横切改动大 | 作横切地基谨慎做（P1），不 bolt-on；market 维度向后兼容（US 默认）|
| scope 蔓延成"做 A 股策略" | 严格数据先行；策略是 P3/远期，不在数据路径内 |

## 7. 建议落项与排序

- **接在 B059 之后**（复用其 provider 抽象；先插座后插头）。
- **P0 spike 独立小项先行**（去/不去的事实依据，地理访问是最大未知）。
- 登 backlog：`B0XX-ashare-data-source`（P0 spike → P1 数据地基+lookup；P2/P3 延后）。
- 与需求池其它项的相对序由用户定；A 股数据是**未来多市场的地基**，B055-P3 多市场依赖它。

**一句话**：数据先行、复用 B059 抽象、P0 先验地理访问、借数据源不借 LLM 决策——这是把 A 股从"想做"变成"可落地"的最稳路径。
