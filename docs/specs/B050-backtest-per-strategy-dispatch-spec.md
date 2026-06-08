# B050 — 回测页单策略调度接线（修复「选任何策略结果都一样」）

> **批次类型：** 混合批次（4 generator + 1 codex）
> **状态：** planning → building
> **触发：** 用户 2026-06-09 报生产现象——回测页选任何策略、相同时段结果完全一样。
> **Planner 根因裁定（铁律 9，不改产品码）：** worker 写死跑 Master 组合回测，无视 `strategy_id`。
> **来源：** 用户报障 + Planner/Explore 实地核查 2026-06-09。

---

## 1. 根因（已实地确证）

回测请求链：前端选 `strategy_id` → POST `/api/backtests/run`。

1. **前端确实发了 strategy_id**：`backtest/page.tsx` 从 `/api/strategies` 拉列表选 `strategyId` 随 POST 发出。
2. **API 校验并落库了 strategy_id**：`services/backtests.py:45` `run_backtest()` 校验 `strategy_id` 在注册表存在，`enqueue(strategy_id=…, params=…)` 入队，`backtest_run.strategy_id` 列已存（`db/models/backtest_run.py:48-49`）。
3. **❌ worker 执行时无视 strategy_id**：`backtests/worker.py:147` `run_backtest_job()` **写死调用** `run_master_portfolio_quarterly_backtest()`（worker.py:186），只从 `run.params` 取日期范围（worker.py:172），**从不读 `run.strategy_id`**；连 `BacktestRunLike` 协议（worker.py:52-57）都只暴露 `run_id`+`params`。

→ **同一时段下，任何 strategy_id 都跑同一个 Master 组合回测 → 结果完全相同。** 这是真实缺陷：策略选择器存在、`trade/backtest/` 下单策略引擎也存在，只是 worker 没把两者接起来（B047 仅接了 Master 一条）。

---

## 2. 目标与范围

**目标：** worker 按 `strategy_id` 分发到对应回测引擎，使「不同策略 → 不同结果」。

**范围（用户 2026-06-09 拍板「完整 scope」）：** 接线全部 4 个活跃策略 + Master 组合显式选项 + 新建 B011 港股中国独立引擎；regime 研究态友好排除。

| 策略 | 引擎 | 本批动作 |
|---|---|---|
| `B006-global-etf-momentum` | `trade/backtest/monthly.py::run_multi_monthly_backtest`（现成）| 分发 + 结果适配 |
| `B016-risk-parity-hrp` | `trade/backtest/risk_parity.py::run_risk_parity_monthly_backtest`（现成）| 分发 + 结果适配 |
| `B025-us-quality-momentum` | `trade/backtest/us_quality_momentum/engine.py::run_backtest`（现成，返回 `pd.DataFrame`）| 分发 + 新报告 builder + DataFrame 适配 |
| `B011-satellite-hk-china` | **无独立引擎**（只在 Master 内部 `generate_hk_china_signal`）| **新建** `trade/` 独立引擎 + 报告 |
| `master_portfolio`（新增显式项）| `trade/backtest/master_portfolio.py::run_master_portfolio_quarterly_backtest`（现成）| 注册表加显式条目 + 分发 |
| `B013/B014/B015 regime` | research 态 weight=0.0 | 友好排除（`error_kind=inactive_strategy`）|

**不做：** 不改各策略**信号/评分算法**；不改 master 组合逻辑；不引入 broker/execution；不激活 regime；不改 async 架构。§12.10.2（worker 是唯一 trade importer，请求路径禁 import）/no-execution/定位§1.1/i18n parity 等永久硬边界不破。

---

## 3. 架构设计

### 3.1 分发（worker）

`run_backtest_job(run)` 读 `run.strategy_id`（已落库），查**分发表** `strategy_id → (engine_fn, result_adapter, report_builder)`，跑对应引擎。`BacktestRunLike` 协议加 `strategy_id` 字段。未知/research 态 → 抛结构化 `error_kind=inactive_strategy`（worker 已有 error_kind 机制，B047-OPS2）。

### 3.2 结果适配（关键难点）

各引擎返回**结构不同构**（字段名差异 + us_quality 返回 `pd.DataFrame`）。采用**每策略适配器**（per-strategy adapter，而非一个带分支的巨型 mapper）：每个适配器把该引擎 result → 统一 `BacktestRunResponse` 字段（`metrics`/`equity`/`allocations`/`trades`，schema 见 `schemas/backtests.py:57-81`）。

| 引擎 result | 差异 | 适配要点 |
|---|---|---|
| MomentumMonthlyResult | `equity_curve: tuple[EquityPoint]` + `fills` | 直接映射 |
| RiskParityBacktestResult | 同构 + `portfolio_target_weights` vs `signal.target_weights` | 字段名适配 |
| MasterPortfolioBacktestResult | `portfolio_target_weights` + kill_switch | 复用现有 mapping |
| UsQualityBacktestResult | `equity_curve: pd.DataFrame`（无 `tuple[EquityPoint]`）/`rebalance_periods`（非 `_results`）/**无 fills** | DataFrame→EquitySample 转换 + period 字段名 + trades 空或从 period 派生 |

现有 `backtests/mapping.py` 的 `map_metrics` 硬编码 Master 报告结构——保留为 Master 适配器，新增其余策略适配器。

### 3.3 报告 markdown

各策略报告 builder：Master（现成 `reporting/master_portfolio.py`）/risk_parity（现成 `reporting/risk_parity.py`）/momentum（现成 `reporting/reports.py`）；**us_quality + hk_china 需新建** report builder。

---

## 4. Feature 分解

| id | executor | 标题 |
|---|---|---|
| F001 | generator | 分发核心 + Tier-1 适配（momentum/risk_parity/master 显式项）+ regime 友好排除 + 测试 |
| F002 | generator | us_quality 分发——新报告 builder + DataFrame/字段适配 + 测试 |
| F003 | generator | **新建 B011 港股中国独立回测引擎**（trade/）+ 报告 builder + 分发 + 测试 |
| F004 | generator | 前端——inactive_strategy 双语友好提示 + 结果标注所跑策略 + 选择器含 master + vitest/Playwright |
| F005 | codex | L1+L2 真 VM——★每策略产**不同非退化**结果 + regime 友好 + signoff |

---

## 5. F001 — 分发核心 + Tier-1（generator）

1. **worker 读 strategy_id**：`BacktestRunLike` 协议加 `strategy_id: str`；`run_backtest_job` 按 `strategy_id` 查分发表。
2. **分发表**：`strategy_id → (engine_fn, result_adapter, report_builder)`，覆盖 `B006-global-etf-momentum`（`run_multi_monthly_backtest`）、`B016-risk-parity-hrp`（`run_risk_parity_monthly_backtest`）、`master_portfolio`（现有 `run_master_portfolio_quarterly_backtest`）。各引擎所需 `signal_dates`/`records`/`params` 按现有 `_load_backtest_snapshot` + `_signal_dates_in_range` 复用；引擎间 cadence 差异（monthly vs quarterly）按各引擎契约传入。
3. **结果适配器**：momentum / risk_parity / master 各一个 adapter，result → `metrics`/`equity`/`allocations`/`trades`（处理 `portfolio_target_weights` vs `signal.target_weights` 字段名差异）。保留现 `map_*` 为 master adapter。
4. **master 显式注册项**：`services/strategies.py` 注册表加 `master_portfolio` 条目（旗舰组合，显式可选；否则修复后用户无法再跑 master）；前端选择器据 `/api/strategies` 自动呈现。
5. **regime 友好排除**：`B013/B014/B015`（research 态 weight=0.0）→ worker 抛 `error_kind=inactive_strategy`（不跑 master 兜底）。`services/backtests.py` 校验层可提前挡（research 态不入队，返 422/友好）或入队后 worker 标 error_kind——generator 二选一并注明。
6. **测试**：分发表三策略各产**不同** metrics/equity（断言彼此不相等，核心反例）+ regime→inactive_strategy + strategy_id 读取 + 适配器字段映射。
7. **Gates**：backend pytest ≥ baseline+ / ruff 0 / mypy 0 / §12.10.2 守门（worker 仍是唯一 importer，请求路径不变）。
8. **不动**：信号/评分算法 / master 组合逻辑。

---

## 6. F002 — us_quality 分发（generator）

1. **新报告 builder**：`trade/reporting/us_quality_momentum.py`（或就近）`build_us_quality_report_payload` + `render_us_quality_markdown`（模仿 risk_parity report）。
2. **DataFrame 适配**：`UsQualityBacktestResult.equity_curve`（`pd.DataFrame`）→ `list[EquitySample]`（date/nav）；`rebalance_periods`（字段名）→ allocations；**无 fills** → trades 空列表或从 period 持仓变化派生（generator 定，注明诚实口径，不伪造）。
3. **分发表加 B025**：接 F001 分发表。
4. **测试**：us_quality 产非退化结果且**异于** momentum/risk_parity/master（同时段）+ DataFrame 转换 + 空 fills 处理。
5. **Gates**：同 F001。

---

## 7. F003 — B011 港股中国独立引擎（generator，触 trade/ 包）

1. **新建独立引擎**：`trade/backtest/hk_china.py::run_hk_china_quarterly_backtest`（或 monthly，cadence 对齐该 sleeve 在 master 内的实际 cadence，generator 据 `master.py` sleeve 配置定并注明），**复用现有 `generate_hk_china_signal`**（master_portfolio.py:520-537 已用），**严禁另写一套发散的信号逻辑**——standalone 必须与 master 内 sleeve 同源信号，否则两个 hk_china 回测口径背离。结果对象同构 risk_parity（equity_curve/rebalance_results/fills）。
2. **新建报告 builder**：`trade/reporting/hk_china.py::build_hk_china_report_payload` + `render_hk_china_markdown`。
3. **分发表加 B011** + 结果适配器。
4. **守门**：新引擎随 trade wheel 打包（§12.10.3 force-include 若涉及 fixtures）；§12.10.2 仍只在 worker import。
5. **测试**：hk_china standalone 产非退化结果且**异于**其它策略（同时段）+ 信号同源核验（与 master 内 sleeve 信号一致性，至少结构层）+ trade 包单测。
6. **Gates**：backend pytest（含 trade/ 包）≥ baseline+ / ruff 0 / mypy 0。

---

## 8. F004 — 前端（generator）

1. **inactive_strategy 双语友好提示**：接 F001 `error_kind=inactive_strategy` → i18n 双语「研究态策略暂不支持独立回测」（en+zh-CN），不漏原始串（复用 B047-OPS2 error_kind→i18n 机制）。
2. **结果标注所跑策略**：回测结果区显示「策略：{所选策略名}」，让用户确认跑的是所选策略（消除「都一样」的歧义）。
3. **选择器含 master**：确认 `/api/strategies` 含 F001 新增 master_portfolio 条目，选择器正确呈现 + 默认值合理。
4. **测试**：vitest（inactive_strategy→双语 / 结果标注策略名 / 选择器含 master）+ Playwright（选不同策略走通，至少 mock 层）+ i18n parity。
5. **Gates**：frontend vitest ≥ baseline+ / lint 0 / tsc 0 / api.ts drift 0（若后端 schema 变则同步）/ i18n parity / no-execution 守门。

---

## 9. F005 — Codex L1+L2 真 VM + signoff（codex）

**L1**：F001-F004 全门禁——backend pytest（分发/各适配器/hk_china 引擎/regime inactive）+ frontend vitest/tsc/lint + ruff/mypy + §12.10.2 守门 + i18n parity + api.ts drift 0 + artifact grep secret=0。

**L2（真 VM）**：
1. ★**核心反例**：同一时段，依次跑 `B006 momentum` / `B016 risk_parity` / `B025 us_quality` / `B011 hk_china` / `master_portfolio` —— 每个产**非退化**结果（equity 点数 >> 2 / 有交易 / metrics 非占位）且**彼此不相等**（至少 metrics 或 equity 曲线明显不同）。这是本批 core acceptance：**证明「不同策略 → 不同数据」**。**evaluator.md §25 适用**：须正面证据（实际跑出彼此不同的非退化结果），不得因「分发表写了」放行。
2. **regime**：选 `B013/B014/B015` → 中文友好「研究态暂不支持独立回测」，非原始异常串、非静默跑 master。
3. **回归**：B047-OPS2 默认范围 Run 仍 OK（master 或默认策略）；recent-errors={count:0}；HEAD≡main；B026 absent；B023 闭环不破。
4. **Signoff**：`docs/test-reports/B050-backtest-per-strategy-dispatch-signoff-2026-MM-DD.md` 用模板（§Production/HEAD 等价 + §Post-signoff Deploy + **§每策略结果差异性证据表**：列各策略的 cagr/sharpe/equity 点数证明互异）。更新 progress.json status→done / docs.signoff / evaluator_feedback。

---

## 10. 风险与缓解

| 风险 | 缓解 |
|---|---|
| 各引擎 result 不同构致适配器漏字段/类型错 | per-strategy adapter 隔离 + 每策略单测断言字段 + L2 真跑核验 |
| us_quality `pd.DataFrame`/无 fills 适配出错 | F002 显式 DataFrame→EquitySample + 空 fills 诚实口径（不伪造） |
| hk_china standalone 另写一套发散信号 | F003 强制复用 `generate_hk_china_signal`，与 master sleeve 同源 |
| 修复后 master 无法再被选 | F001 注册表加显式 master_portfolio 条目 |
| 某策略某时段数据不足退化 | 复用 B047-OPS2 drop-earliest 重试 + error_kind；L2 用有效范围验非退化 |

---

## 11. Core Acceptance（一句话）

同一时段，回测页选不同策略产出**彼此不同的非退化结果**（momentum/risk_parity/us_quality/hk_china/master 各异），regime 研究态友好排除——彻底修复「选任何策略结果都一样」。
