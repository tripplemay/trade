# B060 — 全站标的名可点击 + A 股数据源可行性 spike（P0）

> **批次类型：** 混合批次（2 generator + 1 codex）。一个用户便利小功能 + 一个 A 股 de-risk spike。
> **状态：** planning → building（2026-06-13 用户：沉淀框架后做 A 股数据源，同时顺便做全站标的名可点击）。
> **范围裁定：** A 股本批**只做 P0 可行性 spike**（回答"能不能做"），**不做 P1**（符号/市场维度等重活）——P1 待 P0=GO 后另立项。clickable-symbols 是 B059 的自然入口扩展，顺带做。

---

## 1. 两块内容

| 块 | 内容 | executor |
|---|---|---|
| **A. 全站标的名可点击** | 全站展示标的处 → 点击跳 B059 `/symbols` 详情页 | generator |
| **B. A 股数据源 P0 可行性 spike** | 验证境外生产 VM 能否稳定取 A 股 EOD（地理访问是最大未知）→ 出 go/no-go 报告 | generator 供脚本 + codex 跑+报告 |

> A 股完整路径见 `docs/product/a-share-data-source-integration-path-2026-06.md`（§8 P0 spike 细化 = 本批 B 块的依据）。

---

## 2. A — 全站标的名可点击（generator）

**目标：** 全站任何展示标的代码/名的地方，点击 → 跳 `/symbols?symbol=XXX`（B059 详情页深链），方便随手查。

**设计：**
- 建共享 `<SymbolLink symbol="AAPL">` 组件统一接线（symbol 大写规范化 + `/symbols?symbol=` 深链，复用 F002 已建）。
- 全站一次接线：推荐 / 持仓 / position-diff / ticket / 模拟盘 / 风险 / 回测 / 新闻 等 DataTable 的 symbol 列 cellRenderer + 卡片/列表组件。
- **research-only**：点击仅查看价格，**无交易动作**——SymbolLink 纳入 `no-execution-buttons` 守门（它是导航到只读页，非买卖按钮，安全）。
- 无新后端（复用 B059 `/symbols`）；i18n（链接是 symbol 语言中性；tooltip「查看行情」需 i18n parity）。

**边界：** §12.10.2/no-broker/no-AI 不破；A 股代码暂无数据（点击跳详情页会走 B059 的无效/降级路径，待 A 股数据后自然可用）。

**测试：** SymbolLink 渲染/跳转/大写规范化 + 全站接线点 vitest + no-execution 守门含 SymbolLink + i18n parity。
**Gates：** frontend vitest/tsc/lint / i18n parity / api.ts drift 0 / safety(no-execution+no-broker)。

---

## 3. B — A 股 P0 可行性 spike（generator 脚本 + codex 跑+报告）

**目的：** 回答唯一去/不去问题——**境外生产 VM 能否稳定取到够用的 A 股 EOD 数据**。**先试 AkShare（东财历史，大站最可能通），baostock 对照/fallback。**

**指标 + GO 阈值（见路径文档 §8.3）：** 连通性成功率 **≥95%**·p95 **< ~5s**/覆盖代表标的 **5/5**(600519.SH/000001.SZ/300750.SZ/688981.SH/000300)/深度 **≥3–5 年**/复权可得/交叉源 **<0.5%**/规模日更可行/**不引入禁列 broker SDK**(futu/tiger)/币种单位正确。

**判据：** GO（达标→进 P1）/ CONDITIONAL（能拉但 flaky/慢/限流→报告写缓解：缓存/China-region 代理/窄 universe）/ NO-GO（VM 频繁 geo-block→需中国区组件或延后）。

**边界：** **只接数据库（AkShare/baostock），不接券商 SDK**（futu/tiger 在 safety 禁列）；spike 不写产品代码（probe 脚本入 `scripts/test/`）；不动现有数据/符号模型。

---

## 4. Feature 分解（3 features，2g + 1c）

| id | executor | 标题 |
|---|---|---|
| F001 | generator | 全站标的名可点击——共享 SymbolLink 组件 + 全站接线 + no-execution 守门 + 测试 |
| F002 | generator | A 股 P0 probe 脚本（scripts/test/，AkShare+baostock 探针，按 §8 指标采集，不接禁列 SDK）|
| F003 | codex | 跑 A 股 P0 spike（生产 VM）→ feasibility 报告(go/no-go) + L1/L2 验 clickable-links + signoff |

### F003 — Codex（spike 执行 + 验收 + signoff）
1. **A 股 P0 spike**：在生产 VM 临时 venv 装 AkShare/baostock，跑 F002 probe 脚本，采集 §8.3 指标（连通性/覆盖/深度/质量/交叉源/规模/依赖卫生），写 `docs/test-reports/` 下 A 股数据 feasibility 报告 + **明确 go/conditional/no-go 判定**（含 conditional 缓解方案）。**说明**：本 feature「PASS」= spike 跑完 + 报告产出 + 判定明确（**NO-GO 也是成功的 spike**，不是 fail）。不接券商 SDK。
2. **验 clickable-links**：L1 全门禁；L2 真机——全站 symbol 可点击跳 `/symbols`、无任何买卖/执行按钮（no-execution 守门）、Master/B059 不破、recent-errors=0、HEAD≡main。
3. **signoff**：`docs/test-reports/B060-...-signoff-*.md`（§clickable-links 验收 + §A 股 P0 feasibility 判定 + §不破 + §Ops）。

---

## 5. 风险与缓解

| 风险 | 缓解 |
|---|---|
| A 股 VM geo-block（最大未知）| 这正是 spike 要答的；NO-GO 出口诚实，不强行 P1 |
| 误接券商 SDK | 只接数据库；safety 守门兜底 |
| clickable 破 no-execution | SymbolLink 是只读导航非买卖按钮；纳入守门 + F003 验 |
| spike 误判为"做 A 股策略" | 本批只 P0 spike + clickable；A 股 P1+ 另立项 |

## 6. Core Acceptance（一句话）

全站标的名可点击跳 `/symbols` 详情页（research-only、无交易入口、Master/B059 不破）；**且** A 股数据源 P0 可行性 spike 在生产 VM 跑出**明确的 go/conditional/no-go 判定报告**（回答"境外 VM 能否稳定取 A 股 EOD"），不接券商 SDK。
