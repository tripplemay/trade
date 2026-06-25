# proposed-learnings 归档 — v0.9.52（2026-06-25）

> 来源批次：B076 cn_attack size-tilt 选股（verdict-gated，裁定 NO-GO，0 fix-round done）。3 条同源 learning，用户 B076 done 收尾批准沉淀。

---

## 1. 退市名市值/估值因子补数据法——baostock `turn` 反推流通市值（refines B070 去偏）

**类型：** 新规律（数据补法）

去偏 PIT 回测（含退市名）若要加**市值/估值类因子**（size-tilt / value），`stock_value_em`(eastmoney) 只覆盖**当前上市**名 → 退市名缺市值 → 因子静默丢名 = **重引入幸存者偏差**。**修法：用 baostock k-data 的 `turn`（换手率%）反推流通市值** `circ_mv = close_raw × volume × 100 / turn`（`adjustflag=3` 未复权;`turn = volume / 流通股本 × 100`）。baostock 对所有有 k-data 的名（含退市）都给 turn → 覆盖率 100%（B076: 1310/1310，names_empty=0）。通用于任何需退市名历史市值/估值的去偏研究;补完须断言覆盖率（缺名因缺因子被丢 = 偏差泄漏）。**落点：** `generator.md §35(a)`。

## 2. survivor / 去偏双 cut 验收范式（B076）

**类型：** 新坑（验收范式）

同一策略改动可能 **survivor 宇宙=GO、去偏宇宙=NO-GO**（B076: survivor B068 quality_momentum Sharpe 1.00→1.27 vs 去偏 B070 pure_momentum 0.56→0.42——退市小盘输家在 survivor 宇宙缺席,美化中小盘 tilt）。「回测必须去偏」最强铁证。**范式：primary = 去偏宇宙 gating 裁定;secondary = survivor 仅方向性参考,显式标注「survivor GO 不足为凭、survivor NO-GO 更可信」。** **落点：** `generator.md §35(b)` + `planner.md §策略-改动 verdict 设计`。

## 3. verdict risk gate 用全样本+OOS 双门禁——防 OOS-窗口美化（refines B069/B070 OOS-caveat）

**类型：** 新坑（verdict 规则）

WF-OOS 指标当 verdict risk gate 时,若 OOS 窗口恰系统性偏向被测因子（B076: 2024Q4『924』小盘反弹 favor size-tilt），OOS 被**窗口美化** → 误判 GO（B076 首版规则只看 OOS Sharpe,strong 档 0.931 vs 0.930 险平→假 GO,而全样本 Sharpe 每档恶化 0.56→0.42）。**修法：risk gate 用全样本(period-wide)指标 + OOS 双门禁,全样本恶化即 NO-GO,不让窗口幸运的 OOS 平局 override。** **落点：** `planner.md §策略-改动 verdict 设计`。

---

**框架版本：** v0.9.51 → **v0.9.52**。活跃候选队列清空。CHANGELOG v0.9.52。
