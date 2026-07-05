# B084 F002 — A股 ETF 时序趋势 first-look → **LEAN-GO（有防守 edge，但 OOS 窗口落位需严验）**

> first-look 证据一测（非可配资）。★先验口径（禁扫参）：月末 **12-月绝对动量** > 0 → 持有该 ETF（等权持有腿）否则退现金；
> 月度调仓。★无前视（单测 test_b084_etf_trend 锁：signal 用 ≤t 价、收益取 t+1）。对照买入持有（等权全 5 ETF）。

## 结果（5 宽基/红利 ETF, 2011-2026, 163 月, 平均持 2.24/5）

| | full CAGR | full Sharpe | full MaxDD | OOS CAGR | OOS Sharpe | OOS MaxDD |
|---|---|---|---|---|---|---|
| **时序趋势** | **17.9%** | **0.566** | **−45.9%** | 19.7% | **1.139** | **−7.7%** |
| 买入持有 | 14.2% | 0.478 | −53.2% | 8.9% | 0.488 | −24.9% |

- **趋势全面胜买入持有**：更高 CAGR + 更高 Sharpe + **更浅回撤**（−45.9% vs −53.2%，OOS −7.7% vs −24.9%）。
- **★震荡/熊市分窗口（命门）**：**2022 熊市趋势 −6.0% vs 持有 −8.4%**（趋势退现金**减亏 = 防守有效，非预期的假信号损耗**）；
  2024H1 趋势 +7.1% vs 持有 +7.4%（近平）。**未见评审警告的震荡损耗**——因月度 12-月动量是**慢信号**（宽基 ETF，非日频/微盘），whipsaw 小。

## 裁定：**LEAN-GO**（防守型趋势 edge 真实，但非 definitive GO）

> **正式 trial verdict = INCONCLUSIVE**（正向/防守 lean）：有效验证集只含 GO/NO_GO/INCONCLUSIVE/NA；
> LEAN-GO 映射为 INCONCLUSIVE ——真实正向但 OOS 窗口落位使其未达 definitive GO，须严验后再判。避 B081 式过度归因。

- **正向**：趋势在**所有口径**（收益/夏普/回撤）胜买入持有，熊市防守有效 → 满足 spec§2 F002 "夏普>买入持有+震荡可控" 的 GO 方向。
- **★caveat（避 B081 式过度归因，决定 LEAN 非 definitive GO）**：
  1. **OOS Sharpe 1.14 > full 0.566 = 窗口落位假象嫌疑**（同 B070 教训）：OOS（后 30%≈2022-2026）**恰含 2022 熊市**——趋势防守正好在此窗口发光；OOS>IS **非稳健证据**，是窗口落位。
  2. **样本小**：仅 5 ETF、平均持 2.24、163 月——集中度高，统计力弱。
  3. **原始价（非复权）**：Sina 口径；趋势方向不受影响但绝对收益略偏。
  4. full Sharpe edge（0.566 vs 0.478）**温和非悬殊**。

## 结论（供 planner / evaluator）

- **LEAN-GO**：时序趋势在 A 股宽基 ETF 有**真实防守型 edge**（减回撤为主），值得**推荐独立策略批次严格验证**——
  **CPCV-lite + 更多 ETF（行业/更多宽基）+ 复权口径 + 更长/多 OOS 窗**，确认 OOS>IS 非纯窗口落位后再判可配。
- **不 over-claim**：当前 OOS 亮眼含 2022 熊市窗口落位红利，full 口径 edge 温和；防守价值 > 绝对收益提升。
- trial_registry 登记本 first-look（config=12月时序动量/5ETF/月度, verdict=LEAN-GO）作 DSR N。

## 复现
`scripts/research/b084_etf_fetch.py`（prices, Sina）→ `scripts/research/b084_etf_trend_ic.py`（trend vs hold + 分窗口）。前视单测 `tests/unit/test_b084_etf_trend.py`。
