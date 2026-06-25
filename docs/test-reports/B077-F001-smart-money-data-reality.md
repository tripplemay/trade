# B077 F001 — A股 聪明钱数据可得性 VM 实测（§23 数据现实，三源）

**裁定（数据可得性，非可交易 edge）：** 三源 = **1 source backtest-only-frozen / 1 USABLE_SPARSE（live+深历史）/ 1 USABLE_FULL 但太浅不可回测**。聪明钱方向**有可回测地基**（龙虎榜机构席位），可进 F002 做 first-look 信号探查 —— 但**不承诺赚钱**（first-look ≠ 可交易 edge；全回测 + verdict 是后续批次）。

| 源 | 裁定 | 信号列（实测） | 时效 | 历史深度 | 覆盖/稀疏 | 能否支撑回测 |
|---|---|---|---|---|---|---|
| **北向持股** | **BACKTEST_ONLY_FROZEN** | `今日增持资金`·`持股数量占A股百分比`；聚合 `当日成交净买额` | **冻结 2024-08-16（678 天前）** | per-stock 2017-03→2024-08-16 = **7.42y（冻结）** | Connect 标的（偏大盘） | **仅历史**：可回测 2017→2024.8，**live 已死**（不可前向跟随） |
| **龙虎榜机构席位** | **USABLE_SPARSE** | `机构买入净额`·`买方机构数`（broad-LHB `stock_lhb_detail_em` 含 `上榜后1/2/5/10日`） | **LIVE（lag 7d）** | **实测 2020-07-27→2026-06-18 = 5.89y** | **稀疏**：仅异动股，全市场每月 772→1322 起机构事件 | **是**（live + 5.89y 深度，稀疏感知构造） |
| **主力资金流超大单** | **USABLE_FULL（太浅）** | `超大单净流入-净额`·`主力净流入-净额`（+大/中/小单分档） | **LIVE（lag 1d）** | **仅 2025-12-22→2026-06-24 = 0.5y** | **全市场 per-stock**（无 Connect/异动门）；bulk snapshot 端点已死 | **否**：live 但 0.5y < 2y 太浅，`can_support_backtest=False`（结构化裁定） |

> 实测产物：`docs/test-reports/B077-F001-vm-data-reality-2026-06-25.json`（VM 权威，sample 6）+ `data/research/b077/f001_data_reality_local.json`（dev box）。探针：`scripts/research/b077_smart_money_feasibility_probe.py`（自包含 spike，VM `/tmp` 便携，root pytest 锁纯逻辑）。VM = `34.180.93.185` 的 `/opt/workbench/.venv`。

---

## 1. 北向持股 — 经典"跟北向"玩法已死（§23 2024.8 披露变更，实测铁证）

- **per-stock 持股冻结**：`stock_hsgt_individual_em` 在 **dev box + prod VM 均 6/6 可达**，序列 2017-03 起、**最后一日 2024-08-16**（678 天前）。含 `今日增持资金`（北向单股净增持）/`持股数量占A股百分比`。深度 7.42y 但**冻结**。
- **聚合日净买额冻结**：`stock_hsgt_hist_em(北向资金)` 行索引仍延伸到 2026-06-24（2695 行），但 `当日成交净买额` **最后一个非空值落在 2024-08-16**（`latest_non_null_date` 精确捕捉断点，**VM + dev box 一致**）。这是 **2024.8 取消盘中实时披露**的实测确认，**非假设**。
- **per-stock 明细 / 横截面统计端点已死**：`stock_hsgt_individual_detail_em` / `stock_hsgt_stock_statistics_em` 抛 `TypeError`（NoneType）。
- **结论**：北向 = **BACKTEST_ONLY_FROZEN** —— 有 7.42y 可回测历史（2017→2024.8），但 live 数据冻结 678 天 → **不能驱动前向跟随策略**。经典"跟北向"在免费 akshare 上已死（实测落地，非预判）。

## 2. 龙虎榜机构席位 — 最干净的 LIVE 机构信号 + 回测级深历史（但稀疏）

- `stock_lhb_jgmmtj_em(start,end)` = **机构席位净买**：实测列 `机构买入净额`·`买方机构数`·`卖方机构数`·`机构净买额占总成交额比`·`上榜日期`。**LIVE（实测 lag 7d，由真实 `上榜日期` 最大值算出，非 stamped 0）**，prod VM 可达。
- **历史深度（实测）**：4 个时间窗全部命中——2020-08（772 事件/408 股）、2023-08（745/346）、2025-07（944/466）、2026-06（1322/584）。实测跨度 **2020-07-27 → 2026-06-18 = 5.89y**。
- **broad-LHB 可达性**：`stock_lhb_detail_em` 在最近窗 **2206 行可达**，自带 `上榜后1/2/5/10日` 远期收益列（F002 便利对照；仍以 B070 去偏宇宙为准）。
- **稀疏度（如实记）**：仅**异动股**（涨跌幅/换手触发上榜）才出现，全市场每月仅 772→1322 起机构事件、346→584 只个股 → 横截面绝大多数名字大多数日子缺席。信号**条件于"已发生大波动"**（F002 须处理选择偏差/前视泄漏）。
- **裁定**：**USABLE_SPARSE**，`can_support_backtest=True`（live + 5.89y 实测深度）。

## 3. 主力资金流超大单 — LIVE + 全覆盖，但历史太浅、不可深回测

- `stock_individual_fund_flow(stock,market)` = per-stock 日级资金流：实测列 `主力净流入-净额`·`超大单净流入-净额`（+大/中/小单分档与净占比）。**LIVE（lag 1d）**，prod VM **4/6 成功（success 0.667）**；dev box success 0.8 —— **push host 偏不稳定（§23 B062 host 教训，VM 上亦然）**。
- **历史深度（硬约束）**：端点仅返回 **~120 交易日（2025-12-22→2026-06-24 = 0.5y）**/股 → **0.5y < 2y → `can_support_backtest=False`**（结构化裁定，非仅 prose）。只够近窗 first-look，无法跨多个 regime 深回测。
- **覆盖**：**全市场 per-stock**（任意 A 股皆可，无 Connect/异动门）。但 bulk 横截面 `stock_individual_fund_flow_rank` 在 prod VM **取不到（0 行）** → breadth 由 per-stock 可达性证明，非 snapshot 证明；实操须 per-stock 循环。

---

## 推荐先搭哪个（F002 正式裁定，本节仅基于数据可得性的方向性提示）

- **北向 → 排除**（live 冻结 2024.8，只剩历史，不可前向跟随）。
- **龙虎榜机构席位 → F002 首选**：**唯一兼具 live + 回测级深历史（5.89y）** 的干净机构信号；代价是稀疏（须稀疏感知 + 处理"上榜=已异动"的条件偏差）。
- **主力资金流超大单 → F002 近窗交叉验证（非回测主力）**：live + 全覆盖，但 0.5y 太浅 `can_support_backtest=False`，只够近窗 first-look IC，不足以深回测。

> F002 将对**龙虎榜机构席位**（首选）在 **B070 去偏 PIT 宇宙**上做 first-look IC / 分组 forward-return，只看**有没有相关性苗头**，不做全回测、不承诺赚钱；资金流可作近窗辅助。

## 诚实 caveat（焊死）

- **first-look ≠ 可交易 edge**：本批只回答"数据够不够"，不回答"能不能赚钱"（IC/全回测/verdict 是 F002+/下批）。
- **§23 measured-not-assumed**：北向 2024.8 断点、各源时效/深度/覆盖**全部 VM 实测并从真实字段派生**（lag 由真实 `上榜日期`/`日期` 算出，coverage breadth 由实测 snapshot 结果反映，backtest 支撑由实测深度门控）。探针 schema-discovering（不预设列名）。
- **龙虎榜稀疏=选择偏差**：信号条件于"已发生异动"，存在前视/拥挤风险，F002 须谨慎构造横截面。
- **资金流浅历史 + 不稳定**：0.5y 端点上限 + push host VM 上仅 0.667 成功 → 不可深回测，深回测需更深/付费源（本批不触及）。
- **host 可达性 best-effort**：北向 per-stock 两机皆可达但冻结；资金流 push host VM 0.667/off-box 0.8 → 生产须在 VM 跑并以 best-effort 对待。
- **纯研究硬边界**：research-only / no-broker / no 真金 / no 自动下单 / 只读公开披露 / **无生产改动、无策略部署**。探针在 `scripts/research/`，不碰 `workbench_api`/`trade`（grep 0）。
