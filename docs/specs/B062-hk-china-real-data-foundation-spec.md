# B062 — hk_china 真数据地基（Batch 1：港股 provider + A股/港股进 trade 管道 + 数据质量验实）

> **批次类型：** 混合批次（3 generator + 1 codex）。**真金 hk_china 换真数据工程的第 1 批（数据地基，research-safe）。**
> **状态：** planning → building（2026-06-14；B061 A 股 lookup done 后，用户决定把 hk_china 的 US-listed ETF proxy 换成真 A股+港股、最终进 live Master）。
> **关键定位：** 本批**只建数据地基，不碰 live 推荐**。真金激活在 Batch 3（闸控于 Batch 2 回测）。

---

## 1. 背景与整体工程

用户决定：把 Master 的 hk_china sleeve（现用 US-listed ETF proxy MCHI/FXI/KWEB/ASHR）换成**真 A股+港股**，最终进 live Master。这是**真金策略改动**——分 3 批，**激活闸控于回测**：

```
Batch 1 = B062（本批，数据地基，research-safe，不碰推荐）
Batch 2 = FX 层 + real-data hk_china 策略 + ★回测对比(real vs proxy) → 决策点
Batch 3 = 激活进 live Master（★真金，闸控于 Batch 2 回测favorable + 用户确认；Master 硬回归不破）
```

**诚实前提**：现 proxy（美元 ETF，持真实中国公司）已是合法暴露、无 FX/管道复杂度；hk_china 是最小（10%）最弱 sleeve。换真数据须证明"值这堆复杂度"——故 Batch 2 回测把关，本批先把地基+数据质量做实。

---

## 2. 本批范围（数据地基，research-safe）

**做：**
- 港股 `.HK` 市场 + HK provider（lookup 层，镜像 B061 A股）。
- 真 A股+港股价格**进 trade 数据管道**（akshare 进 `data_refresh`→统一价格 CSV；**trade/ 仍离线只读 CSV**，守 B061 边界）。
- 候选 universe 的**数据质量验实**（B061 延后的 §8 深指标：全历史深度/复权/一致性——评分必须靠这个）。

**不做（延后）：** FX 层（Batch 2）/ real-data hk_china 策略（Batch 2）/ 回测（Batch 2）/ 激活 live Master（Batch 3）/ **任何 live 推荐改动**。

**候选 universe（代表集，最终由 Batch 2 策略定）：** 反映 proxy ETF 的底层暴露——港股 `0700.HK`(腾讯)/`9988.HK`(阿里-HK)/`3690.HK`(美团)/`1810.HK`(小米) + A股 `600519.SH`(茅台)/`000858.SZ`(五粮液)/`300750.SZ`(宁德)。本批 fetch+验证这个代表集。

---

## 3. 硬边界

- **research-only：本批不碰 live 推荐**（hk_china 仍跑现有 proxy；本批只把真数据备好+验质量）。
- **★Master/US 数据管道不破**：`data_refresh` 加 A股/港股 fetch **不得破坏现有 US universe fetch / 统一 CSV 的 US 数据**（Master 评分读它！）——US 数据零回归是硬验收。
- **trade 仍离线**（B061 F003 边界）：akshare 在 **workbench `data_refresh`**（写 CSV），**trade/ 不 import akshare**，只读 CSV。
- **no-broker**：只 akshare/baostock，不接 futu/tiger（safety 禁列）。
- **§12.10.2** / EOD+币种诚实 / 新路由配套 next.config（§20）/ **mypy CI-exact `workbench_api tests`（§19）**。

---

## 4. Feature 分解（4 features，3g + 1c）

| id | executor | 标题 |
|---|---|---|
| F001 | generator | 港股 `.HK` 市场 symbology + HK provider（lookup 层，镜像 B061 A股）|
| F002 | generator | 真 A股+港股进 trade 数据管道（akshare→data_refresh→统一 CSV + 币种标注；trade 仍离线）|
| F003 | generator | 候选 universe 数据质量验实工具（§8 深指标：全历史/复权/交叉源一致）|
| F004 | codex | L1+L2 真机：HK lookup + A股/港股进 CSV + §8 数据质量实测 + ★US/Master 不破 + signoff |

### F001 — 港股 symbology + HK provider（generator）
1. **`.HK` 市场**：扩 B061 SymbolRef（`0700.HK`→market=HK/exchange=XHKG/currency=HKD；B061 symbol_ref 注释已预留 HK）；裸=US/`.SH/.SZ`=CN 不变（向后兼容）。
2. **HK provider**：akshare 港股端点（baostock 仅 A股）插 B059 `SymbolDataProvider` 抽象；按市场路由（HK→HK provider）。
3. **lookup 验证**：`/symbols` 查 `0700.HK`→腾讯 价格图（HKD 标注）。
4. 测试：`.HK` 解析/路由/lookup；US/CN 不破。Gates：backend pytest/ruff/mypy CI-exact 0/api.ts drift/no-broker。

### F002 — A股+港股进 trade 数据管道（generator，最重，最危）
1. **`data_refresh` 加 A股/港股 fetch**：用 akshare 拉候选 universe 真价格，写进**统一价格 CSV**（trade 引擎读的那个）。**akshare 只在 workbench `data_refresh`，trade/ 不 import**。
2. **币种标注**：CSV/管道带 currency（A股 CNY/港股 HKD/US USD）；本批仅标注（FX 在 Batch 2）。
3. **★US 零回归（硬）**：现有 US universe fetch + CSV 的 US 行**完全不变**；A股/港股是**新增行**，不动 US。
4. **复权一致**：A股/港股取前复权（与 US adjusted close 口径一致），记录约定。
5. 测试：A股/港股写入 CSV + US 行不变 + 币种标注 + trade 仍离线（AST 守门 trade/ 不 import akshare）。Gates：backend pytest/ruff/mypy CI-exact 0/safety。依赖 F001。

### F003 — 数据质量验实工具（generator）
B061 延后的 §8 深指标，现在对候选 universe **验实**（评分依赖）：全历史深度（≥策略 lookback 需要，如 momentum 12 月+）/复权正确（验已知分红/拆股被吸收）/akshare-baostock(A股)交叉源同日<0.5% / 港股源一致性。产出结构化质量报告供 F004。测试：质量检查逻辑 + 已知样本。Gates 同 F001。

### F004 — Codex L1+L2 + signoff（codex）
L1 全门禁。L2 真 VM：① **HK lookup**：`/symbols` 查 `0700.HK`→腾讯 HKD 价格图；② **A股+港股进 CSV**：候选 universe 真价格已在统一 CSV（trade 可读）；③ ★**§8 数据质量实测**：候选 universe 全历史深度/复权/交叉源一致（评分可用性）；④ ★**US/Master 不破**：现有 US universe + Master 评分/推荐**零回归**（CSV 的 US 行不变、Master 4 sleeve 推荐不变）；⑤ **边界**：trade/ 不 import akshare、no-broker、EOD/币种诚实；⑥ recent-errors=0+HEAD≡main+演练自清。Signoff（§HK lookup + §A股港股进 CSV + §§8 质量实测 + §★US/Master 不破 + §Ops）。

---

## 5. 风险与缓解

| 风险 | 缓解 |
|---|---|
| ★data_refresh 改动破坏 US 数据→**真金 Master 评分受损** | F002 US 零回归硬约束；F004 验 Master 4 sleeve 推荐不变；A股/港股只新增行 |
| 把真数据误当"已可上 Master" | 本批 research-safe 不碰推荐；激活在 Batch 3 闸控于回测 |
| 港股 provider/数据质量不达标 | F003 验实；不达标→fixing 换源/缓解，记录 |
| akshare 泄进 trade/（破离线边界）| akshare 只在 data_refresh；AST 守门 trade/ 不 import |
| 误接券商 SDK | 只 akshare/baostock；no-broker 守门 |

## 6. Core Acceptance（一句话）

真 A股+港股价格经 akshare（在 workbench data_refresh）进入 trade 统一价格 CSV、候选 universe 的 §8 数据质量（全历史/复权/一致性）验实、`/symbols` 可查港股（0700.HK→腾讯 HKD）；**且现有 US universe + 真金 Master 评分/推荐零回归、trade/ 仍离线、不碰 live 推荐**（真金激活留 Batch 3 闸控于回测）。
