# B083 — PEAD / 业绩预告事件 first-look（评审 P1 排序 2）Spec

> **性质：first-look（信号族证据一测），非完整策略批次。** 评审 §3.4 排序 2：数据零成本、证据最一致的
> **新信号族**。先做 forward-return rank-IC 一测（同 B077 模式）——IC 显著+单调 → 推荐独立策略批次；
> IC 噪音 → INCONCLUSIVE 归档（省成本，不硬上）。预研 `docs/research/next-batch-prep-pead-first-look.md`；
> 来源 `docs/research/ashare-strategy-deep-review-2026-07-03.md` §3.4/§4/§5。

## 设计要点（焊死）

1. **first-look = 低承诺**：产物是 **rank-IC 证据报告 + GO/INCONCLUSIVE 裁定**，非可配资策略。不建 paper/红卡/生产模式。
2. **★前视/时点严谨（命门）**：盈余惊喜用**公告/预告发布日**定义，进场用发布日**之后**可交易价格（T+1 open）。
   预告 `stock_yjyg_em`/快报 `stock_yjkb_em` 有**公告日**字段——必须 PIT，禁用财报期末日（会前视虚高 IC）。
3. **数据地基 = 本批自带探针**：akshare 已确认可得 `stock_yjyg_em`(业绩预告)/`stock_yjkb_em`(快报)/
   `stock_yysj_em`(预约披露)/`stock_profit_forecast_em`(分析师预期)。F001 探针实测覆盖/字段/公告日时点/延迟，
   不可得或时点不可 PIT → 诚实 NO-GO 停批。
4. **盈余惊喜度量（先验定死，禁扫参）**：优先 **预告净利润区间中点 vs 去年同期**（zero-extra-data，最稳），
   analyst 一致预期作 secondary（`stock_profit_forecast_em` 覆盖够则用）。分档（预增/预减/扭亏/首亏/续盈…）或连续 SUE。
5. **宇宙**：复用 B070 去偏 PIT 宇宙口径（与 B082/cn_attack 同源），事件子集 = 该宇宙内有预告/快报的名。
6. **涨跌停可执行性标注**：大惊喜次日常一字涨停买不进——IC 报告须**分层报告**（含/剔除次日涨跌停触板名的 IC），
   诚实标注纸面 vs 可执行 alpha 差（B081 F003 涨跌停开关的逻辑在此作分析口径，非交易执行）。

## 1. 复用清单

| 复用项 | 来源 | 用于 |
|---|---|---|
| 探针纪律（数据现实报告 + GO/NO-GO） | B077 F001 / B082 F001 | F001 |
| 数据接入模式 | B059 provider 抽象 + B065 data_refresh 管线（best-effort/timeout-bounded） | F001 预告/快报序列接入 |
| forward-return rank-IC 框架 | B077 F002（smart-money LHB first-look IC N1/N5/N10/N20） | F002 直接复用 |
| PIT 宇宙 | B070 去偏 PIT（data/research/b070 快照口径） | F002 事件宇宙 |
| trial_registry 登记 | B080 data-migration 模式 | F002 IC trial 登记 |
| 涨跌停触板判定 | B081 F003 `_limit_hit_names`（开盘 vs 前收 ±10%/±20%） | F002 IC 分层口径（分析非执行） |

## 2. Feature 拆解（3：2 generator + 1 codex）

### F001 (g) — 业绩预告事件数据地基探针 + PIT 接入（含 GO/NO-GO）
- 双机实测 `stock_yjyg_em`/`stock_yjkb_em`/`stock_yysj_em`/`stock_profit_forecast_em`：覆盖率（宽宇宙 vs 有事件子集）、
  **公告日字段可 PIT 性**（发布日 vs 财报期末）、字段（预告净利润区间/类型/去年同期）、历史深度、刷新延迟。报告落盘 `docs/test-reports/`。
- data_refresh 接入 5 序列风格（timeout-bounded + best-effort + 自有快照目录），**排在 Tiingo run_refresh 之前**（B082 F004 ISSUE-1 教训）。
- **不可得/时点不可 PIT → NO-GO 停批合法**（诚实交代，同 B082 F001）。

### F002 (g) — 盈余惊喜信号 + forward-return rank-IC first-look
- 盈余惊喜 = 预告净利润区间中点 vs 去年同期（先验口径，禁扫参）；事件日 = 公告日（PIT）；进场 = 公告日 T+1 open。
- forward-return rank-IC N1/N5/N10/N20（同 B077），去偏 PIT 宇宙事件子集；分档 group-mean 单调性；
  **涨跌停分层**（含/剔除次日触板名两版 IC）。
- 报告落盘 `docs/test-reports/B083-pead-first-look-ic.md`（含覆盖率/IC/单调性/涨跌停可执行性差/诚实边界）+ trial_registry 登记（data-migration，B080 模式）。
- **裁定**：\|IC\| 显著（>~0.03）且跨 horizon 同号 + 分档单调 → GO（推荐独立策略批次入 backlog）；否则 INCONCLUSIVE 归档。

### F003 (codex) — 独立验收 + signoff
- Codex 独立：IC 数字从零重实现抽验（不 import 我方脚本）；**前视/时点严谨性核查**（公告日 PIT、进场 T+1、无财报期末前视）；
  惊喜口径无扫参（grep 单一 param bundle）；涨跌停分层口径正确；覆盖率/延迟探针复核；零回归（不触 cn_attack/B082 产品码）。
- signoff `docs/test-reports/B083-pead-first-look-signoff.md`；GO/INCONCLUSIVE 裁定确认。

## 3. 验收（通用段）
- Gates：mypy / ruff / 单测（IC 计算 + 探针 + 涨跌停分层）/ 若触 backend 则 backend 门禁 / CI。
- 诚实：first-look 结论标注为**证据一测非可配资**；INCONCLUSIVE 是合法且常见结局；覆盖率/前视/涨跌停口径显式披露。
- 零回归：不改 cn_attack/dividend_lowvol 产品码。
