# 交易/推荐链路保真度审查（2026-06-09）

> **作者：** Planner（用户 2026-06-09 指派「全面审查交易、推荐相关功能是否按真实策略为用户发出调仓/交易指令」）。
> **审查问题：** 从真实策略到用户实际执行的调仓/交易指令，全链路是否忠实？有没有占位/陈旧/错误值导致用户按错误信号交易？
> **方法：** 3 个并行只读对抗式审查 agent——(1) 策略→推荐保真；(2) 推荐→diff→ticket 保真；(3) 风控 gate 保真。**关键发现经 Planner 亲自读码复核确认。**

---

## 1. 结论摘要

**正常模式（非防守）全链路忠实，风控 gate 层干净。但发现 1 个安全关键缺陷（防守模式 ticket 股数 ~100 倍错误）+ 1 个中等陈旧度披露问题。**

| 链路环节 | 判定 |
|---|---|
| 真实策略源（master 4 sleeve 真实评分）| ✅ 忠实 |
| precompute（每日 timer 真跑 trade 引擎写库）| ✅ 忠实 |
| 推荐请求层（读真实 precompute，AST 守门无 trade import）| ✅ 忠实 |
| current_weight（B046 真实 mark-to-market）| ✅ 忠实 |
| position-diff（正常模式：真实 target − 真实 current，口径一致）| ✅ 忠实 |
| **防守模式 ticket（SGOV 买入股数）** | 🔴 **CRITICAL 失真** |
| as_of_date（推荐新鲜度披露）| 🟡 Medium 陈旧 |
| 风控 gate（kill_switch/wash_sale/per-sleeve DD）| ✅ 真实（B048 修复有效）|

---

## 2. 🔴 CRITICAL — 防守模式 SGOV 买入股数 ~100 倍错误

### 现象
风险红态（kill_switch 触发，master DD ≥ 15%）时用户用「防守 ticket」（B023 F006 normal/defensive radio）→ 生成的 ticket 中 **SGOV 买入股数 = 账户总权益的美元数**（把美元当股数），而非 `总权益 ÷ SGOV 市价`。SGOV ~$100/股时，$100,000 权益应买 ~1000 股，ticket 却显示**买 100,000 股**（约 100 倍）。

### 证据（Planner 亲自复核）
`services/tickets.py:240-257` `_defensive_diff_rows()` SGOV 买入行：
```python
"target_shares": total_equity,   # ← ❌ 美元金额直接当股数
"delta_shares": total_equity,    # ← ❌ 同上（应为 total_equity / sgov_price）
"delta_dollar": total_equity,    # ✅ 金额正确
"reference_price": None,          # 无参考价（掩盖了股数错误）
```
对比正常路径 `services/execution.py:201`：`target_shares = target_dollar / reference_price`（正确）。防守路径漏了除以市价这一步。

### 用户影响
- ticket 的 Markdown/导出（`tickets.py` 渲染 + export 写盘）直接用 `delta_shares` 显示「BUY 100,000 SGOV」。
- 用户照 ticket 下单 → 买超 ~100 倍（$10M vs $100k）。**这是用户会实际执行的交易指令，安全关键。**
- 触发条件：仅防守模式（风险红态）；非每次，但触发即危险。

### 为何漏网
`tests/unit/test_risk_panel.py` 的防守 ticket 测试只断言 Markdown **含 "SGOV"/"Defensive" 文本**，**未验证股数数值**（`delta_shares == total_equity / sgov_price`）。BL-B023-S2 红态演练（B042）也只看红 banner + ticket 出现，未核股数。

### 修复方向
防守 SGOV 行须取真实 SGOV 市价（SGOV 在价格 universe 内）→ `delta_shares = total_equity / sgov_mark`；或无价时**诚实只显金额、股数留空 + 标注「执行时按市价折算」**，绝不把美元当股数。补数值保真单测（防守 SGOV 股数 × 市价 ≈ 金额）。

---

## 3. 🟡 Medium — as_of_date 写死 today，隐藏信号日/陈旧度

### 现象
`services/recommendations.py:263` `get_current_recommendations` 设 `as_of = date.today().isoformat()`——**硬编码今天**。而 `recommendation_snapshot` 行有真实 `as_of_date`（信号日，如最近季度末）。用户在推荐页看到 `as_of: 2026-06-09`（今天），但目标权重其实基于更早的信号日；若 precompute 长期没成功跑（timer 挂了），snapshot 冻结但 as_of 仍显示今天 → **用户误以为推荐反映当下，实则陈旧**。

### 用户影响
权重本身真实（非占位），但新鲜度被误导——用户可能基于「以为是今天的」陈旧信号交易。中等：不直接致错单，但误导决策时点。

### 修复方向
返回 snapshot 真实 `as_of_date`（信号日）+ 可选 `computed_at`，让陈旧度可见；或 UI 同时显示「信号日 X / 数据截至 Y」。

---

## 4. ✅ 健康面确认（审查留证）

### 4.1 策略→推荐忠实（无 B044 等权回潮）
- 真实策略源：`trade/portfolio/master.py:157-160` 4 sleeve 真实配置（40/30/20/10）；`master_portfolio.py:469-540` `_resolve_child_weights` 逐 sleeve 真实评分。
- precompute：`recommendations/precompute.py:93-197` `score_master_target` 真 import trade 跑真实评分写 `recommendation_snapshot`；timer 每日 03:00 UTC（数据刷新后）。
- 请求层：`services/recommendations.py:204-227` 只读 precompute 真实结果，无快照→`[]` 友好空态（非占位）；AST 守门 `test_recommendations_request_self_contained.py` 断言请求路径不 import trade。

### 4.2 正常模式 diff→ticket 忠实
- `services/execution.py:192-208`：target_dollar = target_weight × total_equity；target_shares = target_dollar ÷ 市价；delta_shares = target − current（符号正确 buy/sell）；current_weight 真 mark-to-market（市值权重，与 target 同口径）。
- 普通模式 ticket 如实从 diff 派生（side/quantity）。

### 4.3 风控 gate 真实（B048 修复确认有效，无假绿灯回潮）
- kill_switch：`recommendations.py:239-240` 读真实 `master_drawdown(reconstruct_nav_history())`，阈值 0.15 单一来源（`nav_history.py:46`），DD≥0.15→gate fail（非硬编码 0.00 pass）。
- wash_sale：`wash_sale.py:86-131` 从真实 `fill_journal_entry` 检测亏损卖出+30 日回补（非恒空）。
- per-sleeve DD：`nav_history.py:129-133` 各 sleeve 独立序列（非镜像 master）；`valuation_basis=cost_degraded` 是诚实降级标注（非掩盖）。
- gate→指令：gate informational（research-only，`risk_panel.py` 注释明确不硬阻），红态给 `alternative_defensive_ticket` 供用户选——by-design，非脱节。

### 4.4 陈旧文档（低，非缺陷）
- `services/recommendations.py:1-16` 模块 docstring 仍说「equal-weight across 4 sleeves until F011」——B044 已实现真实权重，注释陈旧。
- `schemas/execution.py:85-87` `reference_price` docstring 说 avg_cost，实际是 latest_close（B046 改）。

---

## 5. 建议（按严重度）

1. **🔴 防守 SGOV 股数（CRITICAL）**：安全关键交易指令缺陷，优先修——防守 ticket 取真实 SGOV 市价折算股数 + 数值保真单测。建议立项 hotfix（铁律 9 流程：本报告=根因分析，待用户确认 scope→Generator 修→Evaluator 验数值）。
2. **🟡 as_of_date（Medium）**：返回 snapshot 真实信号日，陈旧度可见。
3. **🟢 陈旧 docstring（Low）**：更正 recommendations 模块 + execution schema 注释，随修一并清。

**总判断**：用户「按真实策略发指令」在**正常模式下成立**（策略→推荐→diff→正常 ticket 全忠实，风控真实）。**唯一严重缺口是防守模式 ticket 的 SGOV 股数把美元当股数（~100 倍）**——风险红态下用户照单交易会严重超买，须优先修复。
