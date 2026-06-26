# proposed-learnings 归档 — v0.9.53（2026-06-26）

> 来源批次：B077 A股 聪明钱数据可行性摸底（NOT-GO，0 fix-round done）。3 条 learning，用户 B078 done 收尾时合并批准沉淀。

---

## 1. §23 measured-not-assumed 要贯彻到每个派生字段（B077 F001）

可行性/数据现实探针即便数据是 VM 实测的，若 data-reality 的派生标签/裁定字段被 hardcode（`coverage="full_market"` / `lag_days=0` / `can_support_backtest=True`，20-agent review 抓 15 处）仍违反 §23。每个 reality 字段（coverage/lag/depth/backtest-supportability）必须从实测派生。**落点：** `generator.md §36`。

## 2. first-look IC 覆盖-门控裁定档 INCONCLUSIVE_COVERAGE_LIMITED（B077 F002）

信号大部分落在去偏宇宙外（LHB 机构席位 80.8% 小盘未覆盖）时，据子集 IC 断「无信号」=误劝退。加第三档（faint 一致方向 |IC|≥0.015 + 覆盖<50% → INCONCLUSIVE_COVERAGE_LIMITED，决定性检验=补覆盖重跑）+ 分组单调性查（驼峰非单调）。**落点：** `generator.md §37`。

## 3. date-bomb 诊断（B077 预存 date-bomb）

生产真实时钟 + 单测固定 fixture 日期 → fixture 滑出窗口 → 无关 commit 变红。诊断：CI 红但 diff 与红测试无关 + 上个 commit 绿 → 先查日期 fixture。修=时钟注入（commit `6f54e35`）。**落点：** `evaluator.md §31`。

---

**框架版本：** v0.9.52 → **v0.9.53**。CHANGELOG v0.9.53。
