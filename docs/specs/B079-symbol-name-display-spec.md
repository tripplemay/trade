# B079 — 标的名称显示（所有显示标的代码处加显名称）Spec

**批次定位：** 前端 UX 改进（横切前后端）。当前所有页面只显示标的代码（`600519.SH`/`AAPL`），用户要在**所有显示代码的地方加显名称**，格式=**名称为主、代码次之**（`贵州茅台  600519.SH`，代码灰色小字）。

**来源：** 2026-06-26 用户「优化标的显示逻辑，所有显示代码处都显示名称」+ AskUserQuestion 选「名称为主、代码次之」。

---

## 0. 设计要点（Explore 已核源码,焊死）

- **名称源已存在且三市场统一**：`symbols/provider.py:90 ProviderStats.long_name`——美股 yfinance `longName`（`yfinance_provider.py:119`）/ A股 akshare 证券简称（`cn_provider.py:148`）/ 港股 akshare（`akshare_fundamentals.py:148`）。落库在 `symbol_fundamentals_cache.long_name`（`db/models/symbol_fundamentals_cache.py:60`），但**稀疏**（仅被单独查看过的标的有,EOD TTL）。
- **★A股 名称每天已在拉、却被丢弃**：`cn_marketcap.py:52/63` akshare spot 含「名称」列,只用于 ST 过滤（`cn_universe.py:175`）,**没写进任何输出**——捕获它近乎零成本。
- **美股无静态 name 映射**（`ETF_UNIVERSE`/`equity_universe` 只有 ticker）;全仓无 ticker→name 字典。
- **前端共享组件 `<SymbolLink>`**（`components/symbol/SymbolLink.tsx:58`）覆盖 9 个页面/组件——**改它一处覆盖绝大多数**;另需单独处理详情页头部 `symbols/page.tsx:233`。account/fills 的 `<input>/<select>` 是录入控件,不在范围。
- **★决策（焊死）：不走 data_refresh/CSV（名称没落库 + 改日刷关键路径）;建轻量名称 lookup + 后端 enrich**。后端 enrich 优于前端逐个查（列表型响应 N 个 symbol,前端逐个打 `/fundamentals` = N 次请求 + 触发昂贵 akshare/yfinance fetch）。
- **覆盖率（要补全才能"所有地方"）**：A股 用已在拉的 akshare spot「名称」落库 + 美股/ETF/港股 proxy 用**静态 curated 映射**（universe 有界 ~40-50,稳定可靠）;缺失 → 优雅 fallback 纯 code。

---

## 1. 复用清单

| 资产 | 位置 | 用法 |
|---|---|---|
| 名称源 | `ProviderStats.long_name`（US/CN/HK 已实现）| 解析名称 |
| A股 spot 名称（被丢弃）| `cn_marketcap.py:52/63`「名称」列 | 落库捕获 |
| 共享显示组件 | `<SymbolLink>`（9 复用点）| 加 name prop |
| 详情页头部 | `symbols/page.tsx:233`（裸 code,该页已有 name）| 单独加 name |
| 待 enrich response model（8）| `schemas/`：TargetPosition/WashSaleFlag/PositionDiffEntry/PositionEntry/FillRowOut/PaperPositionPnl/PaperDriftEntry/FillSlippage | 加 name 字段 |

---

## 2. Feature 拆解（4 features：3 generator + 1 codex）

### F001 — 名称数据落库 + 批量解析（symbol→name lookup）（executor: generator）

1. **轻量名称 store**：新建 `symbol_name` 表（symbol PK / name / source / updated_at,持久非 TTL）或扩 fundamentals cache;**批量读 `get_names(symbols: list[str]) -> dict[str,str]`（纯 DB,不触发外部 fetch,缺失省略）**。
2. **A股 名称落库**：universe build / data-refresh 顺带把 `cn_marketcap` akshare spot 已抓的「名称」写进 name store（捕获现丢弃的列,零额外抓取）。
3. **美股/ETF/港股 proxy 静态映射**：curated `ticker→name` 常量（ETF_UNIVERSE + equity_universe + CN_HK_UNIVERSE,有界稳定）seed 进 name store。
4. 边界：read-only 名称元数据（§12.10.2 r）;缺失 → fallback code（不报错）。

**Acceptance：** name store + 批量 `get_names`（纯 DB）;A股 名称从 akshare spot 落库 + 美股静态映射 seed;覆盖 cn_attack universe + Master/US universe;缺失优雅省略。Gates：backend pytest/ruff 目录上下文/mypy CI-exact 0。

### F002 — 后端 enrich response model（8 处加 name）（executor: generator）

1. 给 8 个 response model 加**可选 `name` 字段**（TargetPosition/WashSaleFlag/PositionDiffEntry/PositionEntry/FillRowOut/PaperPositionPnl/PaperDriftEntry/FillSlippage）+ `SymbolPriceDetail`。
2. 组装响应时用 **batch `get_names`** 一次性给每行附 name（不逐个查）;缺失 → `name=null`。
3. 边界：纯加字段,既有 code 字段/契约零回归;research-only/no-broker 不破。

**Acceptance：** 8 model 带 name（batch 解析,1 次 DB 非 N 次）;A股 中文名 + 美股名出现在 recommendations/position-diff/fills/paper 等响应;缺失 name=null;既有契约零回归。Gates 同 F001 + acceptance（响应含 name 不破既有断言）。

### F003 — 前端显示（SymbolLink name 为主 + 详情页头部）（executor: generator）

1. **`<SymbolLink>` 加可选 `name` prop**：渲染**名称为主、代码灰色次之**（`贵州茅台  600519.SH`）;name 缺失 → 纯 code（现有兜底）。一处改覆盖 9 复用点（recommendations/position-diff/fills/ticket/paper/backtest/news/risk）。
2. **详情页头部** `symbols/page.tsx:233`：显示名称（该页已有 name 在手）。
3. 各复用点把后端 enrich 的 name 传进 `<SymbolLink name=...>`。
4. ag-grid ColDef cellRenderer 内 name+code 排版不溢出;dense table 可读。
5. vitest/e2e 更新（含 B072 闭环 e2e 名称显示不破 safety 守门）。

**Acceptance：** `<SymbolLink>` 名称为主代码次之 + 9 复用点显示名称 + 详情页头部名称;缺失纯 code 兜底;ag-grid 排版正常。Gates：vitest/tsc/eslint + Playwright e2e（含闭环 + no-execution safety 守门不破）。

### F004 — Codex 验收 + signoff（executor: codex）

- L1 全门禁（verifying 可跳 L1 复跑）。
- **L2 真机/截图**：名称在**所有显示位置**出现（recommendations/position-diff/fills/paper/backtest/详情页,贴 A股 中文名 + 美股名截图/真返回）;**缺失优雅 fallback 纯 code**（造一个无 name 标的）;batch 解析（非 N 次请求,贴证据）。
- **零回归**：执行链闭环 + no-execution/disclaimer safety 守门不破;既有 code 契约不变。
- 边界:research-only/no-broker;HEAD≡prod。signoff 实测证据逐条 + 截图。

---

## 3. 状态流转 + 不变量

- 混合批次：`planning → building(F001→F002→F003) → verifying(F004) → done`。
- **不变量**：① 既有 symbol code 字段/契约零回归（name 纯加）;② research-safe / no-broker / no-execution safety 守门不破（名称纯展示无执行 affordance）;③ 名称缺失优雅 fallback 纯 code（不报错/不空白）;④ batch 解析（1 次 DB,非前端逐个查触发外部 fetch）;⑤ 名称落库 read-only（§12.10.2 r）;⑥ §12.10.2 / ruff 目录上下文 / mypy CI-exact / vitest/tsc/eslint。
- **诚实边界**：① 名称覆盖率取决于 store 落库——A股 靠 akshare spot（已在拉）、美股靠静态映射（有界）;新上市/冷门标的若两者都缺 → 纯 code 兜底（可接受,非阻断）;② 不改任何执行/策略逻辑,纯展示层。
- **后续**：名称 store 可扩为详情页/搜索的统一 name 源;新市场扩展时补静态映射或 provider 名称。
