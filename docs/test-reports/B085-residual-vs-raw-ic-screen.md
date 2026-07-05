# B085 F001 (screen) — 残差动量 vs 裸动量 rank-IC → **弱但真实的方向支持**（引擎 A/B 值得做，但期望要低）

> **廉价安全前置筛**（引擎 A/B 之前）：同 B083/B084 forward-return rank-IC，残差动量 vs 裸动量**头对头**在 B070 adj_close 面板。
> **零回归**：不触 cn_attack 产品码。★fair：raw + residual **同窗口/skip**（残差仅多减 β·市场）。★无前视（单测 test_b085_residual_vs_raw_ic 锁：
> forward return 严格取未来、raw momentum 不依赖未来）。★口径：相对比较（残差 vs 裸）共享幸存者偏差故对其稳健；绝对 IC 带 b070 宇宙偏差（诚实披露）。

## 结果（B070 宇宙, 2019-04..2026, 51 月度点, adj_close）

| 信号 | IC 均值 | IC t-stat | 解读 |
|---|---|---|---|
| **残差动量** | **0.0108** | 0.45 | 绝对 IC **弱**（t=0.45 不显著，< \|IC\|>0.03 GO 门槛） |
| 裸动量 | −0.0009 | −0.04 | **~零 IC** → 证实 A 股裸动量弱（升级的前提成立） |
| **改进（残差−裸, 配对）** | **+0.0118** | **1.98** | **borderline 显著**（t=1.98 恰低于 2.0） |

## 裁定：**弱但真实的方向支持** — 引擎 A/B 值得做，期望要低（非 strong GO）

- **正向（支持升级）**：残差动量**配对显著地改进**裸动量（delta t=1.98），与残差动量假设一致（β 调整确加值）；裸动量 ~零 IC 证实 A 股裸动量弱这一升级前提。→ **引擎 A/B（fresh context）值得做**——有真实（若小）改进可测。
- **★caveat（避 B084 式过度乐观，定"弱"非 strong）**：
  1. 残差动量**绝对 IC 仍弱**（0.0108, t=0.45, 远低于 |IC|>0.03 GO 门槛）——比裸动量好，但非强独立信号。
  2. 改进 t=1.98 **恰低于 2.0** = **borderline 非铁证**，别当"显著"过度宣称。
  3. 绝对 IC 带 b070 大盘宇宙幸存者偏差（相对比较稳健，绝对值谨慎）。
- **对引擎 A/B 的含义**：预期引擎 A/B 显示**小幅**改进（非转变）；残差动量的 edge 是**边际**的。若引擎 A/B 在保真+双本金口径下改进不达实质 → INCONCLUSIVE 合法（同 B083/B084）。

## 结论（供 F001 引擎 A/B fresh context + F002 evaluator）
- 前置筛**已廉价确认**：残差动量 > 裸动量（borderline 显著），前提（裸动量弱）成立 → **引擎 A/B 值得做但期望低**。
- 引擎 A/B（残差 rank 喂 cn_attack 引擎, 双本金, 分子窗损耗+turnover, 保真口径）仍留 fresh context 严做（判断重, B084 教训）。
- trial 登记本前置筛作 DSR N（config=残差 vs 裸动量 IC 筛, verdict=INCONCLUSIVE 弱方向支持）。

## 复现
`scripts/research/b085_residual_momentum.py`（残差动量计算）→ `python -m scripts.research.b085_residual_vs_raw_ic`（IC 筛）。前视单测 `tests/unit/test_b085_residual_vs_raw_ic.py`。
