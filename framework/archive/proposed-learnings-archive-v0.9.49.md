# proposed-learnings 归档 — v0.9.49（2026-06-21）

> 来源批次：B071 测试自动化基建 Phase 0+1（门禁确权 + golden 真数据 + 验收即代码，0 fix-round done）。3 条 learnings，用户 B071 done 收尾批准沉淀。

---

## ① 回测引擎复权口径必须一致（raw-open 买 / adj-close 估值混用 = bug，合成 fixture adj==close 系统性掩盖）（B071 F003）

**类型：** 新坑（backtest 引擎 / 真实数据复权）+ 验证本批 golden 使命

B071 建 golden 真数据 fixture 注入 us_quality 回测，**首跑即抓真实 bug**：`engine.py:307` 用未复权 `open` 买股数、`:308` 用复权 `adj_close` 估值。真实数据 close/adj_close 因累计拆股+分红回调差 ~40×（NVDA close 751 vs adj_close 18.7）→ 持仓系统性错配 → golden 上 us_quality 假亏 −99.4%。**关键规律**：合成 fixture 的 `adj_close == close`（B025 us_quality fixture 全 86790 行 adj==close）→ raw/adj 口径混用在合成数据上零差异、完全掩盖；只有真实复权数据才暴露=「golden 真数据下沉 CI」要解决的特性。

**沉淀落点：** `generator.md §30`（执行与估值同一复权口径，禁 raw-open 买+adj-close 估值混用；真实数据批次须 golden acceptance）。修复 commit `cb69763`（`_wide_open` 用复权 open + 合成 adj==close 向后兼容；亦影响生产 VM us_quality 回测，已随绿 CI 自动部署）。同族 §28（停牌 ffill/NaN）。

## ②（折入 §30.1）records 引擎 raw-close 估值轻微失真（B071 F003，用户裁本批不修）

records-based 引擎（monthly.py / risk_parity.py）执行用 raw-open、估值用 raw-close（内部一致），但信号 momentum 用 adj_close → 持有一个拆股个股穿越其拆股月时 raw-open(拆股前)→raw-close(拆股后)显示假期亏（如 AMZN 2022-06 20:1）。golden 上 master/momentum/risk_parity 结果合理（±22%，ETF 为主、个股拆股月恰未持有）→ 非阻断、本批不修（用户 2026-06-21 裁定）。**沉淀为 §30.1 已知非阻断限制**：未来若个股策略持有拆股名穿越拆股月须修。

## ③ 验收即代码常态化 + evaluator verifying 跳 L1（B071 F004 + 门禁确权）

**类型：** 模板修订 / 流程约定（角色规范）

B071 建 `tests/acceptance/` 永久不变量回归层（golden 真数据跑）。约定：每批 Generator/独立 agent 把本批新颖 L2 真实数据检查写成 acceptance 断言，使一次性真机验收沉淀为永久 CI 回归。门禁确权（`docs/dev/B071-gate-authority-audit.md`）坐实 L1 全门禁已全自动 CI → evaluator verifying 可跳 L1 复跑、复发不变量由 acceptance CI 守、只审新颖/模糊。守铁律 4：独立评审缩到新颖/模糊 + F005 mutation-check 对冲（10/10 mutation 全红）。

**沉淀落点：** `generator.md §31`（验收即代码常态化）+ `evaluator.md §30`（verifying 跳 L1 + 只审新颖/模糊）+ `role-context/generator.md` + `role-context/evaluator.md`（active 行为约定）。已记 `docs/dev/workbench-testing-strategy.md`「Acceptance tier」节。

---

**框架版本：** v0.9.48 → **v0.9.49**。活跃候选队列清空。CHANGELOG v0.9.49。意义=测试自动化路线图地基落地（真实数据回归桶下沉 CI），golden 真数据当场修潜伏生产 bug。
