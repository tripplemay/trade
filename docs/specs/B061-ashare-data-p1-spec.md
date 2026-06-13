# B061 — A 股数据源 P1：数据地基 + A 股 lookup

> **批次类型：** 混合批次（4 generator + 1 codex）。**多市场数据地基**（A 股第一落地）。
> **状态：** planning → building（2026-06-13；B060 P0 spike 判定 **GO** 后立项）。
> **依据：** `docs/product/a-share-data-source-integration-path-2026-06.md`（§8 P0 指标 / §9 符号 schema 设计 / §10 P1 feature 草拆）。B060 signoff P0=GO（生产 VM 可达 sina/tushare、akshare+baostock 装 OK、600519.SH 519ms 取数成功）。

---

## 1. 目标与范围

**目标：** 让系统能取 A 股真实 EOD 数据，并在 B059 `/symbols` 查 A 股代码（如 `600519.SH`→贵州茅台 价格图）。这是未来多市场（B055-P3 / A 股策略）的数据地基。

**范围（P1，严格数据/lookup 层）：** 符号/市场维度 + CN 价格 provider（插 B059 抽象）+ CN 交易日历 + B059 详情页支持 A 股代码。

**不做（仍 US-only，延后）：** 账户/NAV/组合/执行/票据/策略/回测/交易规则（T+1/涨跌停/手数/ST）/跨市场 FX。币种 P1 **仅元数据/展示**（¥ vs $），不入组合聚合。

> **设计精髓（§9）：** market 限定 canonical 字符串 + 派生 SymbolRef + 裸=US 默认 → **加一层非动全身**：US 数据零迁移、CN 同表共存、市场维度锁在数据/lookup 层。

---

## 2. 复用

- **B059 `SymbolDataProvider` 抽象**：A 股 = 该抽象的又一个 provider（§9.8 按市场路由）。
- **B059 `symbol_price_cache`**（migration 0024）：CN 按 canonical 键同表共存，+ 可选 market/currency 列（§9.5）。
- **B059 `/symbols` 详情页 + B060 SymbolLink**：A 股代码自然可查/可点。
- **cost_guard**：限流。**akshare/baostock**：B060 已验装 OK。

---

## 3. §8 深度指标先验（B060 GO 的诚实限定）

B060 P0=GO 基于**地理访问 + 工具链 + 一次取数**（600519 仅 10 行样本）。本批 P1 **第一要务是把 §8 更深指标验实**（在 F002 构建 provider 时即暴露 + F005 真机坐实）：
- **全历史深度** ≥3–5 年日线（非 10 行样本）。
- **全 5 代表符号** 600519.SH/000001.SZ/300750.SZ/688981.SH/000300 可取。
- **交叉源一致**：akshare vs baostock 同日收盘 <0.5%（除复权口径）。
- **规模**：~300 标的日更可行 + 安全 call rate + 复权约定一致。

若某项不达标 → fixing 调整（换源/缓解/窄 universe），不强行宣布完成。

---

## 4. Feature 分解（5 features，4g + 1c）

| id | executor | 标题 |
|---|---|---|
| F001 | generator | 符号/市场维度地基：SymbolRef + canonical 约定 + normalize + 校验/消歧（§9.3-9.4）|
| F002 | generator | CN 价格 provider（akshare 主 + baostock 对照/fallback）插 B059 抽象 + 按市场路由 + 缓存/限流 + 币种 + §8 深度 |
| F003 | generator | CN 交易日历 + gap 检查按市场（§9.6）|
| F004 | generator | B059 详情页支持 A 股代码（CNY/as-of/源 诚实标注，复用 SymbolLink）|
| F005 | codex | L1+L2 真机：A 股 lookup + §8 深度验证 + US 回归不破 + 边界 + signoff |

### F001 — 符号/市场维度地基（generator）
1. **SymbolRef 值对象**（§9.3）：`parse(canonical)` → `{canonical, code, market, exchange, currency, board}`；US 裸=默认（market=US/currency=USD），CN=6 位+`.SH/.SZ`。
2. **消歧**（§9.3 坑）：后缀 ∈ 已知市场码集合（SH/SZ）才算市场限定；`BRK.B` 的 `.B` 非市场码→判 US。不能见点就拆。
3. **board 由 code 前缀推断**（§9.3，为未来交易规则预留，P1 不用）：600/601/603/605→沪主板、688→科创、000/001/002/003→深主板、300/301→创业板。
4. **normalize(symbol)**：裸→US 默认；带市场码→解析。所有读写经 normalize。
5. **向后兼容**（§9.4 铁律）：现有 US 裸 symbol 数据/键/路径**零迁移、零改动**。
6. **测试**：US 裸默认 / CN 解析 / BRK.B 消歧 / board 推断 / 非法 ticker 拒绝 / US 现有路径不破。
7. Gates：backend pytest/ruff/**mypy CI-exact(`workbench_api tests`，§19 教训)** 0。

### F002 — CN 价格 provider（generator，最重）
1. **CN provider 实现**：`SymbolDataProvider` 的 CN 实现，**akshare 主**（东财历史，B060 已验）+ **baostock 对照/fallback**；canonical↔native 适配（§9.2：akshare `600519`+市场 / baostock `sh.600519`）。
2. **按市场路由**（§9.8）：CN canonical → CN provider；裸/US → 现有 yfinance。
3. **缓存/限流**：复用 `symbol_price_cache`（+market/currency 列，§9.5）+ cost_guard；EOD 日 TTL。
4. **币种**（§9.7，仅元数据/展示）：价格记录带 currency（CN=CNY/US=USD），不入组合聚合。
5. **§8 深度**：取**全历史**（≥3–5 年）非样本；全 5 符号；与 baostock 交叉源 sanity。
6. **边界**：§12.10.2（akshare/baostock loader 不 import trade→请求路径 OK，否则异步 job，AST 守门必过）；**no-broker（只接 akshare/baostock，不接 futu/tiger 禁列）**；新路由配套 next.config（§20 教训）。
7. **测试**：CN provider 全历史取数 + 适配 + 路由 + 缓存 + 币种 + 交叉源 sanity + §12.10.2/no-broker 守门。
8. Gates：backend pytest/ruff/mypy CI-exact 0 / alembic head（cache 列）/ api.ts drift / no-broker safety。依赖 F001。

### F003 — CN 交易日历（generator）
CN 交易日历（中国节假日）；`TradingCalendar(market)`；`quality.py` gap 检查按市场选日历（CN 符号用 CN 日历，避免误判缺口）。测试：CN 日历正确 + gap 检查市场感知。Gates 同 F001。依赖 F001。

### F004 — B059 详情页支持 A 股代码（generator）
`/symbols` 详情页接受 A 股代码（600519.SH）→ 价格/图/统计，**诚实标注 CNY + as-of + 源(akshare)**；币种展示（¥ for CN / $ for US，F002 加 currency 后 US 也补 $）；B060 SymbolLink 对 A 股代码现在解析。i18n + api.ts。测试：A 股 lookup 渲染 + CNY 标注 + 源标注 + US 仍 $。Gates：frontend vitest/tsc/lint / i18n parity / api.ts drift。依赖 F002。

### F005 — Codex L1+L2 + signoff（codex）
L1 全门禁。L2 真 VM：① **A 股 lookup**：`/symbols` 查 600519.SH→茅台 价格图（CNY 标注）+ 其它代表符号；② ★**§8 深度验证**：全历史深度 ≥3–5 年 / 全 5 符号 / akshare-baostock 交叉源 <0.5% / ~300 规模日更可行性 / 连通性成功率；③ **US 回归不破**：US 符号仍经 yfinance 正常（SPY/NVDA）；④ **边界**：no-broker SDK（只 akshare/baostock）、no-execution、no-AI、EOD/CNY 诚实标注；⑤ recent-errors=0 + HEAD≡main；⑥ 演练自清。Signoff（§A 股 lookup 证据 + §§8 深度指标实测 + §US 不破 + §边界 + §Ops）。

---

## 5. 风险与缓解

| 风险 | 缓解 |
|---|---|
| §8 深度/交叉源不达标（GO 仅验浅层）| F002 构建即暴露 + F005 真机坐实；不达标→fixing 换源/缓解，不强行完成 |
| 符号/日历横切改动大 | §9「加一层非动全身」：裸=US 默认、CN 同表共存、锁数据/lookup 层；US 零迁移 |
| 误接券商 SDK | 只接 akshare/baostock；no-broker safety 守门兜底 |
| akshare 非官方失效 | provider 抽象 + baostock fallback + 诚实 data_source |
| scope 蔓延成 A 股策略/执行 | P1 严格数据/lookup；账户/执行/策略/FX 不碰 |

## 6. Core Acceptance（一句话）

用户能在 `/symbols` 查 A 股代码（600519.SH→茅台 价格图，CNY/as-of/源 诚实标注），数据经 CN provider（akshare 主+baostock 对照）插 B059 抽象、§8 深度指标（全历史/5 符号/交叉源/规模）真机验实；**且 US lookup 回归不破、只接数据库不接券商、市场维度锁在数据/lookup 层（账户/执行/策略/FX 不动）**。
