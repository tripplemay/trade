# Proposed Learnings Archive — v0.9.21

> 归档日期：2026-05-15
> 来源批次：B017-real-data-validation 跨批次 negative findings + B018-gap-root-cause-attribution 方法论落地
> 闭环情况：2 条 learnings Accept（用户 5/15 done wrap-up 决议）+ 落 framework，CHANGELOG v0.9.21 已记录。

---

## [2026-05-15] Claude CLI — 来源：B017 real-data validation cross-batch finding（v0.9.21 #1）

**类型：** 新坑（backtest evaluation discipline）

**内容：** Synthetic-fixture 信号可能与真实数据信号反向。B016 HRP vs inverse-vol 在 synthetic fixture 上 HRP 略优；B017 真实 yfinance snapshot 上 HRP `-$496` + turnover `+41%`（完全反转）。此类反转风险在任何 fixture-first MVP 框架下都存在 —— fixture 仅证明实现正确性，不能用作策略 conclusion。

**沉淀位置（已写入）：**
- `docs/engineering/testing-and-fixture-policy.md` §"Fixture vs Real-Data Signal Reversal" — 含 B016→B017 反转表 + acceptance gate 必须 real-data reverify 的硬规则
- `.auto-memory/role-context/evaluator.md` §"Fixture-only PASS 不构成策略性能 conclusion"

**实物时间线（B016 → B017 5/15）：**

1. **B016（5/15 02:18）** synthetic fixture 上 HRP 与 inverse-vol 对比，HRP 略胜 —— Codex 签收 PASS
2. **B017（5/15 02:48）** B015 + B016 真实数据 reverify：B016 HRP 在 yfinance snapshot 上 `-$496` ending value、turnover `+41%`，完全反转
3. **5/15 done wrap-up** Planner 提出"fixture vs real-data signal reversal"作为 framework 候选 → 用户 5/15 确认 → 沉淀 v0.9.21 #1

---

## [2026-05-15] Claude CLI — 来源：B018 gap attribution methodology（v0.9.21 #2）

**类型：** 新规律（research methodology — gap root-cause attribution 协议）

**内容（修订自原 "open research question" 候选条目）：**

原 5/15 候选条目把 B013/B010 vs 60/40 gap 列为 open research question，并建议"考虑新开 B018"。B018 已经做完并回答了原问题：root cause = `l2_vol_scaling`（主拖累），`l1_gating` 次拖累，actionable axes = `vol_target` + `cadence`，`universe` ablation 被 defensive 不变量约束。

修订后的可沉淀价值是 **方法论本身**：当一个性能 gap 已经被多个直觉性"修复假设"在真实数据上证伪后，下一步是 **per-asset + per-layer attribution + 三轴 sweep 系统归因**，而不是再开第三个"新 variant"批次盲试。

**4-step 协议：**

1. Per-asset attribution — `Σ capital × weight × return`，定位 gap 的*症状载体*
2. Per-layer attribution — `Σ capital × parked_fraction × (defensive − avg_risk)`，定位 *root cause 候选*
3. 三轴 sensitivity sweep — risk-target 知（如 vol_target）× universe ablation × rebalance cadence；找最强 actionable axis 与受约束的轴
4. Pareto 推荐集 — 至少 3 配置（low-DD / balanced / high-return）含具体 trade-off 数字

**硬边界：** 归因模块 pure-stdlib；override 配置内联构造，**不 mutate 默认参数**；manifest-absent fallback synthetic + `real_data_status='skipped'`；输出 research-only。

**沉淀位置（已写入）：**
- 新增 `docs/engineering/gap-attribution-methodology.md`（含 4-step 协议 + B017→B018 实证 + 硬边界 + reference implementation 路径）

**实物时间线（B017 → B018 5/15）：**

1. **B017 done wrap-up（5/15 早间）** Planner 列出两个 negative finding（B015 activation policy 不缩窄 / B016 HRP 反转），险些建议"再开新 weighting 假设批次"
2. **MVP PRD 复盘** Planner 发现 PRD §12 milestone 5/6 已过；继续盲试新策略变体有放大错误的风险
3. **B018 选型** Planner 推荐方向"先归因，后决策"；用户选项 1 通过
4. **B018 完成（5/15 04:00 前后）** Codex 签收 PASS，验证 root cause = `l2_vol_scaling`；新增 `BL-B018-S1` 入 backlog（B010 quarterly cadence + 10–12% vol-target retune 候选）
5. **5/15 done wrap-up** Planner 把"原 open question 条目"修订为方法论 → 用户 5/15 确认 → 沉淀 v0.9.21 #2
