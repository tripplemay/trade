# B046 — 可交易 diff（mark-to-market）+ current_weight + regime reconcile

> **状态：** planning（2026-06-07 起草）。
> **批次类型：** 新功能（真实评分基础 Batch 3；**里程碑 C 交易闭环关键拼图**，backlog order 1）。
> **来源：** B044 done 拆分 + 2026-06-07 里程碑 C 重定义（用户交易闭环）。
> **配套：** `docs/product/progress-review-2026-06.md`（里程碑 C 交易闭环）/ `docs/dev/workbench-manual-execution-runbook.md`（B023 工作流，不破）。

---

## 1. 目标

让「按系统指示交易」的 **ticket 买卖 diff 真实准确**——核心是把当前持仓估值从**成本价（avg_cost）改为市价（mark-to-market 最新收盘）**，使 target vs current 的 delta 反映真实当前配置。附带统一 recommendations 展示的 current_weight，并 reconcile 策略注册表对齐 master 实际组成。

**Explore 关键发现（决定本批重点）**：可交易的 diff **不在 recommendations，在 execution `get_position_diff()`**——它已在算 current_weight，但用 `持股 × avg_cost / total_equity`（成本价）。成本价低估涨幅持仓的当前权重 → ticket 让用户**过度买入**。**真正修法 = execution diff 改 mark-to-market。**

---

## 2. 决策（2026-06-07 用户已批，★=拍板）

| 决策点 | 选择 | 说明 |
|---|---|---|
| 交易 diff 范围 | ★ **execution diff 改 mark-to-market + rec 展示 current_weight** | ticket 的可交易 diff 是真正核心；rec 展示同步保持一致 |
| regime reconcile | ★ **纳入 B046** | 注册表对齐 master 实际 4-sleeve，验下游不破 |
| NAV/估值基准 | **mark-to-market（持仓 × 最新收盘）一致用于分子分母**（planner 决） | 复用 home.py（B037）模式；不混用成本价/市价 |
| avg_cost 保留 | **不删 avg_cost**（planner 决） | wash-sale / cost-basis 可能依赖；本批仅改**权重/diff 估值基准**，不动成本基记账 |

---

## 3. 永久硬边界（继承）

- **no-broker / no-execution / no-auto-execution**：系统只出 ticket（指示），用户手动下单；本批不新增任何执行/下单能力，不连券商。
- **B023 交易工作流不破**：Recommendations→diff→ticket→fills→reconcile→journal 端到端不回归；wash-sale flags / gate checks / cost-basis 依赖 avg_cost 的逻辑不破。
- 定位 §1.1：diff/权重是配置事实，不输出收益预测数字。
- §12.10.2：请求路径仍禁 import trade（AST 守门不破；本批只动 workbench_api 评估/展示层，不碰 precompute）。

---

## 4. 技术架构

### 4.1 共享 mark-to-market current-weight 助手（F001）

- 抽取/复用 home.py（B037）的 mark-to-market 模式：`current_weight[symbol] = (shares × latest_close) / NAV`，其中 NAV = cash + Σ(shares × latest_close)（market-value NAV，分子分母一致市价）。
- 助手输入：latest AccountSnapshot positions + PriceProvider.get_marks（price_snapshot 最新收盘）+ Account cash。
- **边界**：无 snapshot → current_weight=0.0（空账户路径）；某 symbol 无 price mark → 该 symbol degrade（记录，不崩；沿用 home.py degrade 语义）；NAV=0 → 0.0 防除零；target 有但未持仓 → current=0.0；持仓有但不在 target → execution 侧 sell-to-zero 行单独处理。

### 4.2 execution `get_position_diff()` 改 mark-to-market（F001，核心）

- `services/execution.py` `get_position_diff()`：`reference_price` 从 `snapshot.avg_cost` → **PriceProvider 最新收盘（market price）**；`total_equity` → market-value NAV；`delta_weight = target_weight - current_weight(market)`。
- **保留 avg_cost** 供 wash-sale / cost-basis（不删字段、不改记账）；仅权重/diff 估值改市价。
- ticket 生成（tickets.py `generate_ticket` → 读 `get_position_diff`）自动得到 mark-to-market diff（无需改 ticket 渲染）。
- 无 price mark 的持仓 → diff 行 degrade 标注（不静默当 0）。

### 4.3 recommendations 展示 current_weight（F001，一致性）

- `services/recommendations.py` `_build_target_positions`：current_weight 从硬编码 0.0 → 复用 §4.1 助手真实值；diff=target-current（与 execution 同基准，展示与可交易 diff 一致）。

### 4.4 regime reconcile（F002）

- `services/strategies.py` 注册表对齐 `trade/portfolio/master.py` 实际组成：
  - **加** `global_etf_momentum`（momentum sleeve 0.40，现注册表缺）+ `satellite_hk_china` stub（0.10，现缺）条目。
  - **B013/B014/B015 regime 孤儿项**：重标为研究态 / deactivate（regime_adaptive 在 master `planning_weight=0.0` 且 `_resolve_child_weights` weight>0 抛 BacktestError → 留研究态，激活属未来 B013）。
  - B016 strategy_id（B016-risk-parity-hrp vs master risk_parity_vol_target）口径对齐/注明。
- **下游消费者必验不破**：`/api/strategies`（前端 Strategies 页）/ home.py `_registry_sleeves`（sleeve breakdown）/ advisor precompute universe / news sleeve_tickers——注册表变更后这些 regroup，须验渲染/分组正确 + 相关测试更新。

### 4.5 测试

- pytest：mark-to-market 助手（已知持仓+价格→已知 current_weight；无 mark/无 snapshot/NAV=0 边界）；execution diff market vs 旧 avg_cost（已知场景 delta 变化）；recommendations current_weight 真实；regime reconcile 注册表对齐 + 下游（home sleeve breakdown / advisor / news）不破。
- **B023 工作流回归**：ticket→fills→reconcile 既有测试不破；wash-sale 仍用 avg_cost。

---

## 5. Feature 拆分

| ID | executor | 标题 |
|---|---|---|
| F001 | generator | 共享 mark-to-market current-weight 助手 + execution `get_position_diff()` 改市价（核心可交易 diff）+ recommendations 展示 current_weight + 边界 + pytest（不破 B023/wash-sale）|
| F002 | generator | regime reconcile：strategies 注册表对齐 master 实际 4-sleeve（加 momentum/hk_china、regime 留研究态）+ 验下游 home/advisor/news/strategies 不破 + pytest |
| F003 | codex | L1 + L2 真 VM 验收（ticket diff mark-to-market 准确 + rec current_weight 真实 + 注册表对齐 master + B023 工作流不破 + 下游消费者不破）+ signoff |

---

## 6. 不做的事（YAGNI）

- 不新增执行/下单/broker 能力（系统只出指示）。
- 不删 avg_cost / 不改 wash-sale / cost-basis 记账（仅权重估值基准改市价）。
- 不激活 regime sleeve（master weight>0 抛 BacktestError；留未来 B013）。
- 不做 HK-China 策略实现（order 3，独立批次）/ 不做交易闭环端到端冒烟（BL-B023-S1，order 2 独立）。
- 不改 master 评分逻辑 / B044/B045 precompute / 前端 Rec UI 结构（B041，仅数据真实化）。
- 不输出收益预测数字。

---

## 7. 验收门槛汇总

- **F001**：mark-to-market 助手（边界齐）+ execution `get_position_diff()` 市价（ticket diff 准确）+ recommendations current_weight 真实；diff 分子分母一致市价；**avg_cost 保留 + wash-sale 不破**；backend pytest ≥ baseline+≥10 / ruff 0 / mypy 0；§12.10.2 守门不破。
- **F002**：strategies 注册表对齐 master 实际 4-sleeve（momentum/risk_parity/us_quality/hk_china stub；regime 研究态）；**下游 home sleeve breakdown / advisor precompute / news sleeve_tickers / /api/strategies 全不破**（测试更新+验证）；backend pytest ≥ baseline+ / ruff / mypy 0。
- **F003**：L1 全门禁 + secret grep 0 + B023 工作流回归测试绿；L2（真 VM）：(1) health 200 + SHA≡main HEAD + recent-errors=0；(2) **ticket diff mark-to-market**——手动 PUT 一段含浮盈持仓 → `/api/execution/position-diff` 的 current_weight 按市价（非成本价）+ ticket 买卖 delta 准确（对比成本价口径差异，记录）；(3) **`/api/recommendations/current` current_weight 真实**（非 0.0，与 execution 同基准）；(4) **注册表对齐 master**（`/api/strategies` 反映 4-sleeve，regime 研究态）+ home sleeve breakdown / advisor / news 不破；(5) anon 401；(6) B026 absent。Signoff: docs/test-reports/B046-...-signoff-2026-MM-DD.md（§Production/HEAD + §Post-signoff Deploy + **§交易 diff mark-to-market vs cost-basis 对比记录**）。Framework 候选：mark-to-market vs cost-basis 双估值口径若出新通用规律记 §Framework Learnings。

---

## 8. 参考文档

- Explore 复用面：`services/home.py`（B037 mark-to-market）/ `services/prices_provider.py`（PriceProvider）/ `services/dashboard.py`（_aggregate_nav）
- 交易 diff/ticket：`services/execution.py`（`get_position_diff` L168-173 avg_cost）/ `services/tickets.py`（`generate_ticket`）/ `routes/execution.py`
- 占位点：`services/recommendations.py`（`_build_target_positions` current=0.0 L171）
- regime reconcile：`services/strategies.py`（注册表）vs `trade/portfolio/master.py`（实际组成）
- B023 工作流：`docs/dev/workbench-manual-execution-runbook.md`

---

## 9. 风险与缓解

| 风险 | 缓解 |
|---|---|
| 改 execution diff 破坏 B023 ticket→fills→reconcile | F001 保留 avg_cost（仅权重估值改市价）；B023 回归测试绿；F003 L2 端到端验工作流不破 |
| mark-to-market 估值缺 price mark 静默当 0 | degrade 标注（home.py 语义）；无 mark 的持仓 diff 行明示，不蒙混 |
| regime reconcile 改注册表破坏下游 home/advisor/news | F002 显式验 4 消费者 + 测试更新；regime 留研究态不激活（不触 BacktestError）|
| Account.equity_value 语义（成本 vs 市价）致 NAV 口径混乱 | NAV 统一用 market-value（cash + Σ 持仓市值），分子分母一致；spec §4.1 明确，F001 确认 Account 语义 |
| current_weight 与 execution diff 两处口径不一致 | 同一 mark-to-market 助手喂两处（§4.1）|

---

## 10. 与既有批次的边界 + 后续

- **不改**：master 评分 / B044/B045 precompute / B041 前端 Rec UI 结构 / avg_cost 记账 / wash-sale。
- **解锁**：交易闭环 diff 真实可交易（里程碑 C §5 关键拼图）。
- **后续（backlog order）**：BL-B023-S1 交易闭环端到端冒烟（order 2，用本批真实 diff）→ HK-China 实现（order 3）→ B042 Risk UI → B043 AI 解释。
