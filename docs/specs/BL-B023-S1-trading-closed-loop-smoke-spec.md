# BL-B023-S1 — 交易闭环端到端生产冒烟（用真实评分 + 真实 current + 真实安全层）

> **状态：** planning（2026-06-08 起草）。
> **批次类型：** 验证/冒烟（**Codex-only 批次**，executor:codex；交付物=结果报告非代码）。**里程碑 C 完成标准 §6——『按系统指示交易』闭环可用的端到端确证。**
> **来源：** B023 signoff §Soft-watch S1（B023 L2 仅走 defensive=true 空路径，常规 recommendation-driven ticket 端到端未物理覆盖）+ 里程碑 C 交易闭环重定义。
> **前置：** B046（真实 diff）+ B048（真实安全层）+ B048-OPS1（deploy 可靠）均已 done；B044/B045（真实评分）已就位。

---

## 1. 目标

在 **production VM** 上用**真实评分 target（B044/B045）+ 真实 current_weight（B046 mark-to-market）+ 真实安全层（B048 kill_switch/wash_sale）**，跑通一次**非 defensive 路径**的交易闭环端到端冒烟，确证「按系统指示交易」可用：

```
Recommendations(真实 target) → position-diff(真实 mark-to-market) → order ticket
  → record fills → reconcile → journal
```

**这是里程碑 C 交易闭环可信的端到端确证。** 不写新代码——用既有真实流 + 真实账户跑 + 记录证据。

---

## 2. 范围（Codex-only）

- **不写产品代码**（executor:codex；如发现缺陷，记 finding → 转 Generator fix-round / 新批次）。
- 在 VM 用 workbench UI / authenticated API 手动 PUT 真实账户（含 positions + sleeve tag，post-B048-F002）+ 确保 data-refresh 已拉近期价（缓解 B048 S1 cost_degraded）。
- 跑端到端非 defensive 路径，留 journal 作证据，成功后 ticket void / account 恢复（B023 既有约定）。

---

## 3. 永久硬边界（继承）

- **no-broker / no-execution / 手动下单**：冒烟不真实下单到券商；"fills" 是模拟录入（研究闭环），ticket 是指示。
- B023 工作流不破（仅行使，不改）。
- 定位 §1.1 不出收益预测。

---

## 4. 冒烟步骤（= Codex 验收 acceptance / 测试计划）

1. **Setup**：authenticated PUT 真实账户（cash + positions 含 sleeve tag）；确认 data-refresh 近期价已拉（记录 valuation_basis = market 还是 cost_degraded，B048 S1）。
2. **Recommendations**：GET /api/recommendations/current → **真实非空 target**（B044/B045，如 SGOV/EEM/SPY…）+ **真实 current_weight ≠ 0.0**（B046 mark-to-market）+ **gate_checks kill_switch 反映真实 DD**（B048，非硬编码 pass）+ **wash_sale_flags 真实**（B048，构造亏损卖+回补则非空 / 否则空且合规）。
3. **position-diff**：GET /api/execution/position-diff → **真实 mark-to-market diff**（买卖 shares 基于市价 NAV，非成本价/非空）。
4. **order ticket**：POST /api/execution/tickets（非 defensive）→ Markdown 作业单含真实 diff + 双语 disclaimer。
5. **fills**：record fills（CSV import / API）模拟执行该 ticket。
6. **reconcile**：reconcile 计划 vs fills，标偏差。
7. **journal**：journal 留痕整笔。
8. **回归**：B026 banner absent / recent-errors=0 / health 200 / HEAD≡main。
9. **Cleanup**：ticket void + account 恢复，journal 留作证据。

---

## 5. 验收门槛汇总（F001 codex）

- **L2 端到端非 defensive 闭环跑通**：上述 1-9 步全过；**关键证据**：
  - /current 真实 target + current_weight≠0 + gate kill_switch 真实 + wash_sale 真实；
  - position-diff 真实 mark-to-market（记录 valuation_basis + degrade 哪些点）；
  - ticket→fills→reconcile→journal 链路完整，journal 留痕；
  - 非 defensive 路径（区别于 B023 L2 仅 defensive）。
- **结果报告** docs/test-reports/BL-B023-S1-trading-closed-loop-smoke-2026-MM-DD.md：闭环各步证据 + valuation_basis 声明 + 截图（可选）+ 发现的 finding（若有）+ 里程碑 C §6 达成判定。
- **Finding 处置**：闭环中若发现真实缺陷（如 diff/gate/wash 异常），记 finding → 转 Generator fix-round 或新批次，本冒烟标 PARTIAL。
- 更新 progress.json status→done / docs.signoff / evaluator_feedback。

---

## 6. 不做的事（YAGNI）

- 不写产品代码 / 不引 fixture seed automation（手动 PUT 真实账户）。
- 不真实下单到券商（no-broker）。
- 不做 kill-switch red 样本 UI 演练（BL-B023-S2，随 B042）。
- 不做持续测试基建（仅一次冒烟）。

---

## 7. 参考文档

- B023 工作流：`docs/dev/workbench-manual-execution-runbook.md`
- 真实评分/diff/安全层：B044/B045 + B046（mark_to_market）+ B048（risk/gate/wash）signoff
- 里程碑 C §6：`docs/product/progress-review-2026-06.md`

---

## 8. 风险与缓解

| 风险 | 缓解 |
|---|---|
| B048 S1 cost_degraded（price_history 不覆盖近期 snapshot 日期）| 先确认 data-refresh 拉近期价；冒烟记录 valuation_basis 诚实声明（v0.9.21）|
| 真实账户 PUT 误操作生产数据 | 冒烟后 account 恢复 + ticket void；journal 留证；操作在用户授权下 |
| 闭环中发现真实缺陷 | 记 finding → fix-round/新批次，冒烟 PARTIAL，不强过 |
