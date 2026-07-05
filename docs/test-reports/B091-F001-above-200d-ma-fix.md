# B091 F001 — 修 above_200d_ma 多日历 MA bug（done, Workflow 建+2 对抗验证）

> **根因来源：** B090 F001 发现 + Codex F002 独立复现确认（最小 2-ticker 异日历样本）。`trade/strategies/hk_china_momentum/factors.py` `above_200d_ma`
> 对**多交易日历 union** 宽表 rolling 200-row（`min_periods=200`）→ 跨市独有日注 NaN → 任一票 200-row 窗内仅 ~160-188 非 NaN → MA 恒 NaN → 读 "below MA" → `regional_risk_off` 每季触发 → 真个股 sleeve 100% 趴 SGOV。

## 修法

- 新 helper `_latest_ma_own_calendar(col, ma_long)`：**先 `col.dropna()` 再 `rolling(ma_long, min_periods=ma_long).mean()`** → 各票在**自身交易日历**上算 200D MA，取最新值（自身观测 < ma_long 则 NaN）。
- `above_200d_ma` 改用 `wide.apply(...)` 逐列算 MA（替原 union-frame rolling）；`close = wide.iloc[-1]`、`(close > ma).fillna(False)` 语义不变；`trend_pass` 接口不变。
- diff：`factors.py` +23/−1。

## ★零回归铁律（live US-only proxy 逐位不变）—— 三重证明

hk_china_momentum wired 进 workbench（`backtests/worker.py` + `recommendations/precompute.py`），**live hk_china = US-only proxy ETF（MCHI/FXI/KWEB/ASHR，单交易日历）**。`dropna()` 对无缺口单日历列 = **no-op** → proxy 路径输出字节不变：

1. **builder 单测（b）**：单日历 gap-free 帧，`assert_series_equal(new, old)` PASS（布尔值/index/dtype 逐位吻合；唯一差异=cosmetic Series `.name`，无 consumer 读）。
2. **验证 #1 独立 fuzz**：200 个随机单日历帧 → **0 处 new-vs-old 不吻合**；+ later-IPO leading-NaN 票亦 no-op。
3. **验证 #2 独立 random-walk**（12 票/400 日）+ 边界（199 vs 200 obs）→ 逐位吻合。

**+ workbench `test_strategies.py` 13 passed**（live proxy 行为不变的活证）。

## 多日历修好 + 语义

- **多日历修**（单测 a）：两票 disjoint Mon/Wed/Fri vs Tue/Thu 日历各 260 上涨自观测 → 修后 above_MA=**True**（旧 union 公式=False，bug in-test 复现）。
- **语义保**（单测 c）：自身观测 < 200 → NaN MA → False；`_wide_close` 仍 filter `date<=as_of`（无前视）；`fillna(False)` 不变。

## 验收：**done**（Workflow 建 + 2 对抗验证 un-refuted, survived=true, 0 issues）
- gates: ruff clean + mypy trade(103)/backend(529) Success + tests/unit 新 3 + hk_china_strategy 9 + backend test_strategies 13 全 pass。
- 零回归: 仅 `factors.py` + 新测 diff，无其他策略/生产/data_root 改动。
- **follow-up**：修后 B090 hk_china retest 可复跑得真 real-vs-proxy go/no-go（backlog；仍受 SGOV 2020 floor+幸存者偏差限，B090 O2）。
