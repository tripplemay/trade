# proposed-learnings 归档 — v0.9.48（2026-06-18）

> 来源批次：B066 ashare-attack-momentum-quality（A股 进攻策略 P1，0 fix-round done）。F002/F003 自跑 adversarial review 各抓 1 真 bug，用户 B066 done 收尾批准沉淀。两条均 generator 主动对抗审查产出（good practice）。

---

## ① 回测引擎真实数据缺口：停牌 ffill + NaN 安全读价（禁 `or 0.0`）+ 缺价回归测试（B066 F002）

**类型：** 新坑（backtest 引擎 / pandas — 真实数据缺口被合成测试掩盖）

A股 停牌(停盘) = 某 (ticker,日) 行缺失 → pivot 出 NaN。两个被合成测试（每 ticker 每日都有价）掩盖的真实 bug（均 HIGH）：(1) rebalance 分支只从「有价目标」重建持仓 → 停牌持仓被丢弃，市值凭空蒸发（权益守恒破，实测 100k→50k）；(2) `float(row.get(t,0.0) or 0.0)` 不能把 NaN 归零——`nan or 0.0 == nan`（NaN 在 Python 为真值）→ 停牌名污染 mark-to-market → equity NaN → pct_change 吞跨 NaN 真实收益、cummax 毒化致 max_drawdown 失真。

**沉淀落点：** `generator.md §28`——(a) ffill 结转最后已知价 + 持仓 carry-forward 永不静默消失；(b) 显式 NaN 安全读价（`v is None or pd.isna(v) or v<=0`），禁 `v or 0.0`；(c) 合成数据每格有价系统性掩盖停牌路径，真实数据批次须专门缺价/停牌回归测试。commit `3228c06` 系。

---

## ② 多变体研究报告：退化空仓变体必须红旗，勿静默报 0.00%（B066 F003）

**类型：** 新规律（研究诚实性 / 多变体回测报告）

多变体对比报告里，一个变体若空截面/缺因子数据（A股 质量因子在 fundamentals 稀薄时选不出股）→ 退化满仓现金、CAGR/Sharpe/换手全 0、never traded。报告若把干净的 0.00% 当真实结果展示（尤其驱动 headline 图表+payload metrics），研究判定被悄悄破坏——分不清「故意持现金」vs「数据缺失没测到」。

**沉淀落点：** `generator.md §29`——研究报告红旗体系除「样本内≠样本外 winner / 夏普离谱 / 全变体无差异」外，必须含 (1) `no_activity` 红旗（rebalance_count==0/换手 0+曲线平 → 标「never traded，0.00% 非真实结果」，命中 headline 尤其响亮）+ (2) 同子族内 toggle 失效红旗（同因子 N 个退出变体结果字节相同=退出规则从未生效，全局 spread 测试两族发散时会漏掉）。同族于 evaluator.md §29/§25。

---

**框架版本：** v0.9.47 → **v0.9.48**。活跃候选队列清空。CHANGELOG v0.9.48。
