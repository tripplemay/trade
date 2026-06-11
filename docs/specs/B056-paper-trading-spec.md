# B056 — 模拟盘（Paper Trading / 前向模拟）基建（每策略一个虚拟账户，Master 先行）

> **批次类型：** 混合批次（3 generator + 1 codex）
> **状态：** 草案（待 B054 done 后转 planning→building；本会话 2026-06-11 与用户讨论定案）
> **来源：** 2026-06-11 用户讨论确认——交易前基建功能，横切应用所有策略。
> **排序：** B054 中文化 → **B056 模拟盘（本批，Master 先）** → B055 进攻引擎。非交易 gate（与实盘并行）。

---

## 1. 愿景：回测与实盘之间的「前向桥」

| | 回答什么 | 时间 | 真金 |
|---|---|---|---|
| 回测 Backtest | 策略在**过去**会怎样（可能过拟合）| 历史 | 无 |
| **🆕 模拟盘 Paper（本批）** | 策略**现在、往前**正在怎样（真·样本外）| **前向实时累积** | 无 |
| 实盘 Real | 我的钱跟着策略 | 前向 | 有 |

**模拟盘 = 一个虚拟账户**：给一笔虚拟本金，**忠实跟着策略目标配置**，在策略调仓日自动虚拟调仓（按当日收盘价成交 + 真实成本），**每天**用真实价格 mark-to-market，显示**账户盈亏曲线 + 每个资产盈亏**。让用户下真单前/中，看策略真刀真枪前向的表现——backtest 过拟合的最佳解药。

**用户确认决策（2026-06-11）：** 与实盘**并行**（实盘小仓起步 + 模拟盘长期验证，模拟盘非 gate）；排 **B054 后 B055 前**；**真·基建**（一套引擎参数化为「哪个策略」，Master 先，B055/未来策略各插一个）。**成本=真实计**（含手续费/滑点，前向测试该诚实，planner 默认用户未反对）。

---

## 2. 架构（大量复用现有）

| 复用 | 用途 |
|---|---|
| 策略目标（Master `recommendation_snapshot` / 未来 B055 引擎）| 模拟盘调仓日跟它配置 |
| 每日价格管线（`price_snapshot`/`price_history`，data-refresh）| 每日 MTM 标价 |
| `services/mark_to_market.py` | 算虚拟持仓市值/权重/盈亏 |
| account_snapshot 模型范式 | 仿建 paper 账户表 |

**新建：** paper 账户表（per 策略：虚拟现金/持仓/start 配置）+ paper_nav_history（每日 MTM 点）+ 虚拟调仓模拟引擎 + 每日 MTM job（timer）+ 模拟盘前端页。

**前向语义（用户要的）：** 从「打开模拟盘那天」起——按当日收盘价虚拟买入当前策略目标→每日 MTM 往前攒→到策略下个调仓日虚拟再平衡。纯前向（不 seed 历史；equity 从激活日单点起累积）。

**测策略非测执行：** 模拟盘按收盘价成交+模型成本=测**策略本身**表现；用户**真实执行质量**（限价/T+1/滑点）由实盘 journal 衡量——两者分工，不混。

---

## 3. Feature 分解（Master 先，参数化）

| id | executor | 标题 |
|---|---|---|
| F001 | generator | paper 账户模型 + 虚拟调仓引擎（参数化策略，跟目标配置，收盘价成交+成本）|
| F002 | generator | 每日 MTM job + nav history（timer，复用价格管线+mark_to_market）|
| F003 | generator | 模拟盘前端页（账户盈亏曲线 + 每资产盈亏，中文）|
| F004 | codex | L1+L2 真 VM——模拟盘忠实跟 Master + 每日 MTM/盈亏正确 + 前向累积 + signoff |

## 4. F001 — paper 账户 + 虚拟调仓引擎（generator）

1. **数据模型**：`paper_account`（strategy_id / 虚拟现金 / base_currency / 激活日 / 成本参数）+ paper 持仓（symbol/shares/avg_cost）+ migration。**参数化策略**：一个引擎，按 strategy_id 接不同策略目标（Master 先；B055 未来同接口）。
2. **虚拟调仓**：在策略调仓日（Master quarter-end；未来 B055 month-end）按策略目标权重×当前 paper NAV 算目标股数→**虚拟成交于当日收盘价**→**应用真实成本**（手续费/滑点 bps，planner 决默认值）→更新 paper 持仓。激活日按当前目标首次建仓。
3. **§12.10.2 边界**：调仓引擎读策略目标（已落库）+ 价格（只读），off 请求路径（job/timer 侧）；不接券商（虚拟）。
4. **测试**：激活建仓+调仓日再平衡+成本应用+边角（无目标/无价格 graceful）。
5. Gates：backend pytest ≥ baseline+ / ruff / mypy 0 / alembic head。

## 5. F002 — 每日 MTM + nav history（generator）

1. **每日 MTM job**（timer，~每日收盘后）：对每个 paper 账户用最新收盘价 mark-to-market（复用 mark_to_market）→记一个 `paper_nav_history` 点（date/nav/per-position 市值）；检查是否到调仓日→触发 F001 调仓。
2. **每资产盈亏**：记录每持仓 成本→当前价→浮盈浮亏（绝对+%）。
3. **timer 接线**：新 systemd timer（§24 read-only timer L2 必查接线，evaluator）；§12.11 deploy post-step assert。
4. **测试**：MTM 算 nav 正确+nav history 累积+per-asset 盈亏+timer 幂等。
5. Gates：同 F001 + timer 接线。

## 6. F003 — 模拟盘前端页（generator）

1. **新页「模拟盘」**（per 策略，Master 先）：账户**盈亏曲线**（nav 时间序列 + 总收益% + vs benchmark 如 SPY，planner 决）+ **每资产盈亏表**（symbol/持仓/成本/现价/浮盈浮亏）+ 当前配置 vs 策略目标 + 激活日/天数。
2. **中文**（B054 后，全中文；i18n parity）。
3. **空/前向态**：刚激活单点→友好「模拟盘运行 X 天，前向累积中」。
4. **测试**：vitest（曲线/盈亏表/空态）+ i18n parity + api.ts。
5. Gates：frontend vitest/tsc/lint / i18n parity / api.ts drift 0。

## 7. F004 — Codex L1+L2 + signoff（codex）

L1 全门禁。L2 真 VM：激活 Master 模拟盘（设虚拟本金如 $100k）→**首次建仓忠实跟 Master 目标**（持仓=目标权重）；触发每日 MTM→nav/per-asset 盈亏随真实价格变动正确；**前向累积**（多日 nav history 点）；调仓日再平衡（若 L2 期跨调仓日，否则验逻辑）；模拟盘页中文显账户+每资产盈亏；回归 B050-B055 不破+recent-errors=0+HEAD≡main；timer 接线（§24）；演练自清。Signoff `docs/test-reports/B056-...-signoff.md`（§模拟盘忠实跟策略证据+§MTM 盈亏正确+§前向累积）。§25 须正面真机证据。

## 8. 开放决策（留 planning）

- 虚拟本金（用户设，默认如 $100k）；benchmark（SPY / 60-40）；成本模型 bps 默认值；是否允许可选 seed-start-date（默认否，纯前向）；MTM timer 时刻（对齐 prices timer 后）。

## 9. 风险与缓解

| 风险 | 缓解 |
|---|---|
| 模拟盘与实盘语义混淆 | 明确：模拟=测策略（收盘价+成本）；实盘 journal=测执行；两账户分开 |
| 前向初期数据少 | 用户已知「前向要等时间」；空态友好提示运行天数 |
| 参数化不足致 B055 难接 | F001 引擎按 strategy_id 参数化，Master/B055 同接口 |

## 10. Core Acceptance（一句话）

一个参数化的模拟盘引擎：给策略一笔虚拟本金，忠实跟其配置、每日真实价格 MTM，前向显示账户盈亏+每资产盈亏——让用户下真单前/中看策略真实前向表现；Master 先行，B055/未来策略各插一个。
