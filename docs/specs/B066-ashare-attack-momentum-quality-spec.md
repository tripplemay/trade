# B066 — A股 进攻型动量+质量选股策略（P1：引擎 + 多变体回测验证，research-only）Spec

**批次定位：** A股 进攻模型的**策略批 P1**（接在 B065 数据地基之后，3 步路线图第②步）。建一个**独立于 Master** 的进攻型 A股 个股选股引擎，跑**多变体回测 + 样本外验证**，让用户在回测页看到历史表现 + 变体对比，据此判定是否值得上 P2 实盘 advisory surface——**先验证再上实盘**。

**来源：** 2026-06-18 用户讨论定案（捕获于 backlog `B055` decisions）。**前置已就绪**：B065 数据地基 done（A股 CAS 基本面进 fundamentals.csv + 宽 PIT universe + qfq 质量），**S1 cross-source 闸已关**（收益率偏差 <0.013%，数据可信）。

**P1 边界（research-only）：** 本批**只建引擎 + 回测验证**，**不含实盘推荐/执行 surface**（每日 advisory 输出 = P2）。advisory / 不自动下单 / no-broker 边界不变。

---

## 1. 愿景与设计定案（用户拍板，backlog B055 2026-06-18）

独立进攻卫星，与 Master 并行（Master=稳健核心 ETF 季度；本模式=进攻个股月级监控）。**定案设计：**

| 维度 | 决定 |
|---|---|
| 性格 | **纯进攻**（始终满仓 top N，**无市场防御闸**——吸取 hk_china_real「200D 闸全防御什么都没测到」教训），**诚实披露回撤** |
| 因子（A/B 测试）| **2 变体**：变体A = 质量过滤→动量排名；变体B = 纯动量（无质量过滤）→ 对比看质量在 A股 是否真加值 |
| 退出/获利了结 | **3 变体回测对比**：(a) 仅动量衰减退出（跌出 top-N，让赢家奔跑）/ (b) +移动止损（高点回撤 X%）/ (c) +硬获利目标（+X% 卖）→ walk-forward 选净收益最优 |
| 运行节奏 | **每日监控 + 不动区(no-trade band)阈值触发**：每 EOD 重算目标，仅在与现仓显著偏离才调仓（多数日无需调仓）；P1 回测**模拟此每日循环**以得真实换手/成本 |
| 集中度 | top 20-30 等权 + 单票上限 ~8% |
| 成本 | **真 A股 成本**：印花税 0.1%（**仅卖出**）+ 佣金 ~0.025% + 滑点 |
| 防过拟合 | walk-forward 样本外**强制**；★2 因子×3 退出 = 多变体 → 数据窥探风险高 → out-of-sample 验证 + **全变体诚实披露，不 cherry-pick in-sample winner** |
| 基准 | 沪深300 |

**P1 核心交付 = 研究判定：** 哪个变体组合在 A股 上净收益最优（样本外）、质量过滤是否加值、哪种退出规则好——据此决定是否进 P2。

---

## 2. 复用清单（核过源码——Explore 摸查）

| 复用资产 | 位置 | 用法 |
|---|---|---|
| 因子原语 | `trade/strategies/us_quality_momentum/factors.py`（`momentum_12_1` L109、`quality_score` L146=rank(roe)+rank(gross_margin)+rank(fcf_yield)−rank(debt_to_assets)）| **几乎原样镜像**（PIT-aware，as_of 防泄漏）|
| 排名标准化 | `…/ranking.py`（`percent_rank` L17）| 直接复用 |
| 组合构造 | `…/construction.py`（`build_portfolio` L264:composite→top-N→等权→单票cap→行业cap）| 复用（A股 无 GICS→行业cap 降级/关）|
| 信号编排（as_of 友好 + `current_holdings` 入参）| `…/signal.py`（`generate_signal(parameters, as_of_date, current_holdings)` L98）| **不动区/exit 的天然挂载点**（current_holdings 已用于 earnings held-frozen）|
| 参数 dataclass | `…/parameters.py`（frozen，top_n/factor_weights/max_position_weight/cadence）| 镜像 + 加 A股 变体/成本/exit 字段 |
| B050 回测分发 | `workbench_api/backtests/worker.py`（`_DISPATCH` L501、`_run_us_quality` L378 自 load 不用 records、`_strategy_parameters` L157、`_drop_earliest_retry` L176）| 加 `_run_cn_attack` runner + `_DISPATCH` 一行 |
| adapter | `backtests/adapters.py`（`adapt_us_quality` L135→equity/allocations/trades）| 同构则复用，否则加 `adapt_cn_attack` |
| report builder | `trade/reporting/us_quality_momentum.py`（payload L90 + markdown L176 + map_metrics）| 镜像 `cn_attack.py` |
| 策略 registry（前端露出）| `workbench_api/services/strategies.py`（`_REGISTRY` L78、`_summary(status=...)` L57、`list_strategies` L314）| 加条目，**`id` 必须==`_DISPATCH` key**，`status="research"`，**不入 `INACTIVE_STRATEGY_IDS`** |
| 回测页前端 | `frontend/.../backtest/page.tsx`（拉 `/api/strategies` → 选择器 L335）| **零改动**（registry 露出即可选）|
| 月度信号日 | `trade/analysis/parameter_sweep.py`（`build_monthly_signal_dates` L868）+ worker `_monthly_signal_dates` L136 | 复用（不动区在其上叠加）|
| 数据 loader（prices/fundamentals 已含 A股）| `trade/data/us_quality_universe.py`（`load_prices` L266 / `load_fundamentals` L294，自动读 unified CSV，A股 已 B065 写入）；`trade/data/data_root.py`（`WORKBENCH_DATA_ROOT`）| prices/fundamentals **直接复用**（A股 已在同一 unified CSV）|
| B065 universe 产出 | `cn_pit_universe.csv`（header `as_of_date,ticker,rank,market_cap,avg_turnover,composite_score`，B065 `cn_universe.py:point_in_time_top_n`）| **新 loader 读它**（按 as_of 取成员）|
| B057 模式框架（P2 hook）| `strategy_modes/registry.py` `_MODES` L83 | **P1 不动**；引擎结果同构 adapt_us_quality 即兼容，P2 再 append |

**成本模型现状（须扩展）：** `trade/backtest/us_quality_momentum/engine.py`（`BacktestConfig` L51 `cost_bps`/`slippage_bps`，`friction_rate` L59，`_weight_turnover` L182，`period_cost = capital × turnover × friction_rate` L295）是**对称单一 friction**，**不区分买/卖** → A股 印花税仅卖出无法表达。

---

## 3. 必须新写/改的点（Explore 结论）

1. **A股 universe loader**：新增读 `cn_pit_universe.csv`（schema 异于 US `universe.csv`），按 `as_of_date` 取当时 top-N 成员喂引擎（**不复用** `load_universe`，它读 US fixture 格式）。A股 无 GICS sector + 无 earnings calendar → `build_portfolio` 的 `sector_map`/`earnings_dates` 传空/降级。
2. **方向化 A股 成本模型**：`BacktestConfig` 扩 `stamp_duty_bps`（**仅卖出** 10bps=0.1%）+ `commission_bps`（~2.5bps 双边）+ `slippage_bps`；`_weight_turnover` 拆 `buy_turnover`/`sell_turnover` 分方向计成本。
3. **每日 as-of 驱动循环 + 不动区**：无现成「每日重算回测」循环（现引擎离散月/季信号日）。新建每日（或频繁）驱动循环，复用 `generate_signal(as_of, current_holdings)`；**不动区(no-trade band)**：仅当目标与现仓偏离超阈值才调仓（current_holdings 是 held-frozen 挂载点）。回测据此得真实换手/成本。
4. **2 因子变体参数化**：变体A `factor_weights` 含质量（质量过滤→动量）；变体B 纯动量（quality 权重 0 / 跳过质量过滤）。
5. **3 退出变体参数化**：(a) 动量衰减（跌出 top-N 自然退）/(b) 移动止损（持仓从持有期高点回撤 X% 触发卖，需引擎跟踪每仓 peak）/(c) 硬获利目标（+X% 卖）。
6. **research registry**：`id`==`_DISPATCH` key（同字符串），`status="research"`，**不入** `INACTIVE_STRATEGY_IDS`（否则回测被拒）。
7. **S3 CN 价源稳健（B065 发现）**：akshare eastmoney `stock_zh_a_hist` 此刻 VM 不可达、sina `stock_zh_a_daily` 稳且与 baostock 一致 → data_refresh CN 价源**优先/fallback sina**（B062 修 HK 同款），保回测数据新鲜。

---

## 4. Feature 拆解（4 features：3 generator + 1 codex）

### F001 — A股 进攻引擎 + cn universe loader + 2 因子变体（executor: generator，触 trade/）

1. **cn universe loader**：读 `cn_pit_universe.csv`，按 `as_of_date` 取 top-N 成员（PIT，无泄漏）；A股 无 sector/earnings → 降级处理。
2. **引擎镜像**：复用/镜像 us_quality `factors/ranking/construction/signal`；**质量因子直接复用**（B065 已把 A股 CAS 写进同一 fundamentals.csv，`quality_score` 对 A股 frame 算排名——B065 已验）；动量复用 `momentum_12_1`。
3. **2 因子变体参数化**：变体A 质量过滤→动量排名；变体B 纯动量。top 20-30 等权 + 单票 ≤8%；**纯进攻无 regime gate**。
4. `generate_signal(as_of, current_holdings)` 每日 as-of 可算（为 F002 不动区/exit 铺路）。
5. **S3**：确保 CN 价源稳健（eastmoney 不可达 fallback sina），回测 prices 新鲜（data_refresh 侧小改）。
6. mypy trade 自检（B050 教训）。

**Acceptance：** cn universe loader 给定 as_of 取正确 PIT 成员（无泄漏单测）；引擎对 A股 universe 产 top 20-30 等权组合（质量过滤变体 vs 纯动量变体产**不同**选股）；质量因子对 A股 算出真排名。Gates：backend+trade pytest/ruff(目录上下文)/mypy(workbench+trade) 0。

### F002 — 每日监控驱动 + 不动区 + 3 退出变体 + A股 方向化成本回测引擎（executor: generator，触 trade/）

1. **每日驱动循环**：按交易日推进，每日 `generate_signal(as_of, current_holdings)` 算目标。
2. **不动区(no-trade band)**：仅当目标 vs 现仓偏离超阈值（如持仓跌出 top-N 缓冲带 / 新票强势入选 / 权重漂移超容忍）才调仓；否则持有。**输出每日{目标, 是否调仓, 卖出/获利了结清单}**（P1 落回测，P2 落 surface）。
3. **3 退出变体**：(a) 动量衰减退出 /(b) 移动止损（跟踪每仓持有期 peak，回撤 X% 卖）/(c) 硬获利目标（+X% 卖）——参数化可切。
4. **方向化 A股 成本**：印花税 0.1% 仅卖出 + 佣金 + 滑点；turnover 拆买/卖分方向计；T+1 open 成交（复用 `_execute_at_open`）。
5. 真实换手/成本/回撤 metrics（诚实，纯进攻吃满回撤）。

**Acceptance（§29 实测）：** 回测跑出**非退化** equity（多点/有交易/真 metrics）；不动区生效（多数日无调仓，换手受控）；3 退出变体产**不同** turnover/收益；A股 成本正确（卖出含印花税、买入不含）。Gates 同 F001。

### F003 — 多变体回测接线 + 回测页露出 + 对比报告 + walk-forward（executor: generator）

1. **B050 分发**：`_DISPATCH` 加 `cn-attack-momentum-quality`（或类似）+ runner（自 load universe/prices/fundamentals，吃 start/end + 变体参数）+ adapter（复用/新增）+ report builder。
2. **registry 露出**：`services/strategies.py` 加条目，`id`==dispatch key，`status="research"`，双语名（如「A股 进攻动量质量(研究态)」）；前端零改动可选跑。
3. **多变体对比报告**（双语）：2 因子 × 3 退出 = 6 配置的 CAGR/Sharpe/MaxDD/换手/成本/vs 沪深300；**walk-forward**（in-sample 设计段 + out-of-sample 验证段对比）；**★过拟合红旗标注**：全变体披露、不 cherry-pick in-sample winner、夏普离谱存疑。
4. **回测页可跑**：用户选该策略 → 跑 → 看变体对比 + 样本外。

**Acceptance：** 回测页可选该策略并跑出真实 A股 结果；报告含 6 变体对比 + walk-forward + 过拟合标注 + 沪深300 基准；inactive_strategy 不误触（research 但可跑）。Gates：backend pytest + frontend vitest/tsc/eslint/i18n parity/api.ts drift（若 schema 变）+ ruff 目录上下文。

### F004 — Codex 回测验证 + signoff（executor: codex）

**真数据批次——signoff 必含「实测证据」硬段（evaluator §29）：**
- L1 全门禁（backend + trade mypy + ruff 目录上下文 + frontend）。
- **L2 真机实测（VM，贴真返回）：**
  - 回测页跑该策略 → **非退化结果**（equity 多点 / 有交易 / 真 metrics）。
  - **变体对比真数字**（2 因子 × 3 退出，各产非退化且彼此不同 → 质量是否加值 / 哪种退出好的研究证据）。
  - **walk-forward 样本外合理性**：out-of-sample 段表现 plausible，**非明显过拟合**（夏普离谱存疑）；选出的是合理 A股 流动大盘股、换手合理。
  - **A股 成本保真**：卖出含印花税 0.1%、买入不含；不动区使换手受控。
  - **★S1 全量复确认**：用 B065 F003 cross-source 工具对**全 cn_seed universe**复跑（把 planner 3 名抽样扩到全量），确认 <0.5%（或诚实口径差）。
  - 边界 adversarial：**research-only（无实盘推荐/执行 surface）**、no-broker、no 收益预测、研究态不碰 live。
  - 回归 B050-B065 不破；HEAD≡prod；recent-errors=0。
- **P1 结论 = 研究判定**：A股 进攻策略是否值得进 P2 实盘 advisory surface（哪变体最优 / 质量是否加值 / 哪退出好 / 样本外是否稳）。signoff `docs/test-reports/B066-…-signoff-*.md`，实测证据硬段逐条贴真观测。

---

## 5. 状态流转 + 风险

- 混合批次：`planning → building(F001→F002→F003) → verifying(F004) → done`。
- **风险与缓解：**
  - **过拟合**（多变体 2×3 + 高频重灾区）→ walk-forward out-of-sample 强制 + 全变体诚实披露 + 不 cherry-pick + 夏普离谱存疑（F004 核）。
  - **个股暴雷/动量崩盘** → 质量过滤减轻（变体A）；P1 仅回测不实盘。
  - **A股 历史较短 + 数据缺口** → PIT universe + 诚实标注样本期；CN 价源 sina 稳健（S3）。
  - **触 trade/ CI 严** → 本地 `mypy trade` + `ruff check .` 目录上下文（v0.9.47）。
  - **不动区/exit 参数可调=过拟合面** → out-of-sample 验证这些参数，不在 in-sample 调到最优。

## 6. 不变量清单（Codex 回归核）

1. Master/regime/其它策略/回测/lookup 零回归（新策略独立注册，不改公共路径）。
2. **research-only**：无实盘推荐 surface、无执行、无 paper 激活（P2 才做）；不碰 live。
3. no-broker / no 收益预测 / no 自动下单。
4. trade 离线（akshare/baostock 在 workbench data_refresh 侧）；§12.10.2 不破。
5. US 数据/策略零回归（A股 行追加，US 行不动）。
