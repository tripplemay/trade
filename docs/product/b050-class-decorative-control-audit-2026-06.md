# B050 类反模式系统审查（2026-06-09）

> **作者：** Planner（用户 2026-06-09 指派「全面核查系统中其他功能是否存在类似问题」）。
> **反模式定义：** 用户提供的输入（控件值/请求参数/配置）被**接收·校验·存储**，却被**执行/计算层忽略**，使控件成为装饰品、参数对结果无影响。
> **触发：** B050 回测页「选任何策略结果都一样」缺陷。
> **方法：** 3 个并行只读代码审查 agent 分域穷查——(1) 后端请求参数消费；(2) 前端交互控件接线；(3) worker/job/precompute 执行层入参消费。

---

## 1. 结论摘要

**系统性问题基本局限在回测执行路径（B050，已立项在修）。** 其余功能健康：

- ✅ **前端控件全部健康**——无装饰性/未接线控件；问题在后端执行层，非前端。
- ✅ **后端请求参数绝大多数 honored**——recommendations/execution/fills/account 等参数都真正影响结果。
- ✅ **执行层（precompute/data-refresh/canonical）无写死忽略**——对每个 sleeve/symbol 真实计算（无 B048 之前的 master-镜像/硬编码回潮）。
- ⚠️ **新发现 2 处低severity 缺陷** + **1 处 B050 实现依赖**（见 §3/§4）。

---

## 2. 已知缺陷（B050，在修）

| 缺陷 | 位置 | 用户症状 |
|---|---|---|
| backtest `strategy_id` 被 worker 忽略 | `services/backtests.py:45`（仅校验）→ `worker.py:186`（写死 master）| 选任何策略结果都一样 |

→ B050（building 中）修复：worker 按 strategy_id 分发到对应单策略引擎。

---

## 3. 新发现缺陷（本次审查产出）

### 3.1 backtest `parameters` 字典同样被忽略（Low — 潜伏）

- **位置**：`BacktestRunRequest.parameters`（schema）→ `services/backtests.py:51` 存进 params → `worker.py` 从不读取。
- **现状**：与 strategy_id 同源——B050 修 strategy_id 分发时，`parameters` 也应一并接线（各单策略引擎 `run_*_backtest` 都接受 `strategy_parameters`，如 `RiskParityParameters`/`MomentumParameters`）。
- **降级为 Low 的原因**：**前端当前未暴露 parameters 编辑器**（回测页只有策略选择/快照/日期/对比开关，无参数调节 UI），所以用户暂时无法显式设置 → 潜伏而非用户当下可感知。
- **建议**：并入 B050 —— 要么把 `parameters` 接进各引擎的 `strategy_parameters`，要么显式从 schema 移除（避免又一个「plumbed but ignored」字段）。

### 3.2 backlog `status` 字段被忽略（Low — 内部工具页）

- **位置**：`BacklogUpdateRequest.status`（schema 收）→ `services/backlog.py:248` **显式不存**（注释「request.status is not stored」）→ `services/backlog.py:112` 读时**硬编码 `status="open"`**。
- **用户症状**：编辑 backlog 条目把 status 改为 in_progress/done → 提交 → 刷新后**恢复 "open"**。状态管理完全无效。
- **根因**：`BacklogEntryModel` 根本没有 status 列（存它需 migration）。
- **降级为 Low 的原因**：backlog 是**内部工具页**（非用户投资页，里程碑 C 已明确排除），影响面小。
- **建议**：加入 backlog.json 需求池作小修（建 status 列 + 存 + 读真实值），或显式从 schema 移除 status（若产品上 backlog 不需要状态流转）。

---

## 4. B050 实现依赖（非缺陷，但必须让 Generator 知道）

**`canonical.py:44-48` 会被 B050 破坏。** canonical 是定时 job（每日生成 Master 投资报告，**by-design 写死 master 正确**，无用户输入被忽略，非反模式）。但它构造的 `run` 是 `SimpleNamespace(run_id=…, params={})`——**没有 `strategy_id` 属性**。B050 改 `run_backtest_job` 读 `run.strategy_id` 分发后，canonical 调用会 `AttributeError`。

→ **B050 必须处理**：canonical 的 `run` stand-in 设 `strategy_id=MASTER_STRATEGY_ID`（"master_portfolio"），或 worker 分发对缺失 strategy_id 默认 master。已在 B050 spec §10 风险表补此条。

---

## 5. 健康面确认（非缺陷，审查留证）

### 5.1 前端控件（全 wired 或合理 display-only）

| 页面 | 控件 | 状态 |
|---|---|---|
| backtest | 策略选择/快照/日期/SPY 对比开关 | wired（值发后端；对比开关控图表）|
| execution/ticket | normal/defensive radio | **wired**（`defensive: mode==="defensive"` 发后端真影响 diff）|
| execution/fills | 票据选择/allow-unmatched/CSV/手填行 | wired |
| execution/journal-history | 时间窗选择 | wired（`?window=` 查询参数）|
| execution/account | 现金/币种/持仓行 | wired（PUT body）|
| recommendations | 简单/专业视图 tabs | display-only（B041 注释明确仅换展示，正当）|
| strategies | 表格行选择 | wired（fetch 详情）|

### 5.2 后端参数（honored）

recommendations news 的 `sleeve/topic/source/form_type/limit`、ticket 的 `as_of_date/notes/defensive`、position-diff 的 `as_of`、slippage 的 `window`、fills 的 `allow_unmatched`——**全部被下游真正使用**。

### 5.3 执行层（无写死/镜像）

recommendations precompute、advisor precompute、data_refresh、prices/news CLI、price_history backfill——**对每个 sleeve/symbol 真实独立计算**（无 B048 之前 per-sleeve DD 镜像 master / kill_switch 硬编码 pass 的回潮）。canonical 写死 master = by-design（旗舰投资报告就是 master 组合）。

---

## 6. 建议

1. **`parameters` 并入 B050**（已在修，顺手接线或显式移除）。
2. **canonical/B050 依赖**：已补 B050 spec 风险，确保 Generator 处理。
3. **backlog `status`**：低优先，加 backlog.json 需求池 or 显式移除字段。

**总体判断**：除回测路径（B050 在修）外，系统无其它用户可感知的「装饰性控件/被忽略参数」。前端接线健康，执行层无写死回潮。这是一个健康信号——B050 是孤立缺陷，非系统性蔓延。
