# B081 engine-fidelity A/B — B070 de-biased PIT (pure_momentum + equal)

Window 2019-04-01..snapshot-end. All fixes are **更保守/数字变差=诚实** (印花税 10→5bp is the lone 口径更正, numbers-better). The **old_all_off** group bit-level reproduces the B070 signoff — proof the fixes never polluted the old path.

| group | full CAGR | full Sharpe | MaxDD | ending | turnover | cost | OOS CAGR | OOS Sharpe | OOS DD | rebs |
|---|---|---|---|---|---|---|---|---|---|---|
| old_all_off | 13.1% | 0.559 | -58.3% | 243406 | 194.0 | 35802 | 28.4% | 0.93 | -27.8% | 639 |
| only_lot_rounding | -8.6% | -0.653 | -50.7% | 52147 | 1160.3 | 74041 | -16.0% | -2.162 | -31.4% | 1749 |
| only_partial_rebalance | 20.7% | 0.769 | -50.2% | 387740 | 236.0 | 58147 | 32.7% | 1.04 | -24.8% | 1517 |
| only_suspension_halt | 13.1% | 0.559 | -58.3% | 243406 | 194.0 | 35802 | 28.4% | 0.93 | -27.8% | 639 |
| only_delist_liquidation | 13.1% | 0.559 | -58.3% | 243406 | 194.0 | 35802 | 28.4% | 0.93 | -27.8% | 639 |
| only_price_limit_gating | 13.1% | 0.559 | -58.2% | 243331 | 194.8 | 35694 | 28.9% | 0.939 | -27.4% | 642 |
| new_all_on | -6.6% | -0.409 | -46.9% | 61360 | 1069.7 | 72566 | -14.7% | -1.671 | -29.4% | 1749 |
| new_all_on_recovery_0p5 | -6.6% | -0.409 | -46.9% | 61360 | 1069.7 | 72566 | -14.7% | -1.671 | -29.4% | 1749 |

> research-only / advisory-only. Each fix has an independent switch; off = bit-level pre-B081口径. Delist recovery 0.5 is the haircut sensitivity.

---

## F005 r1 审计更正（fixing 轮，2026-07-04 — planner 裁定 c772c72）

上表的 `new_all_on`（−6.6%/−14.7%）**不可作为"修真后策略基线"直接解读**，独立验收（r1 报告：`B081-backtest-engine-fidelity-verifying-r1-2026-07-04.md`）实测更正如下：

### 1. lot_rounding 的负数是 10 万本金容量下限，非策略失效
本金扫描（only_lot_rounding）：

| 本金 | full CAGR | OOS CAGR | turnover | rebs |
|---|---|---|---|---|
| off@100k（旧口径） | 13.1% | 28.4% | 194 | 639 |
| lot@100k | −8.6% | −16.0% | 1160 | 1749 |
| lot@1M | +10.5% | +23.5% | 249 | 849 |
| lot@10M | +13.2% | +28.2% | 195 | 644 |

10 万本金下 25 只等权中均值约 9 只（峰值 16）一手都买不起（4% 仓位=4000 元 < 高价股一手），残差反复触发调仓致 6× 换手；**1000 万本金下与旧口径几乎重合（保留 99% edge）——"分数股假象"叙事被证伪**。

### 2. partial_rebalance 是策略变动（默认已改 False）
Option A 绕过总量不动区、调仓 639→1517 次、OOS +28.4%→+32.7%（收益改善型）。cadence 隔离（fullband 0.001 → OOS 29.5%）证实其收益来自更高频响应信号，非执行保真。按 B069/B076 verdict-gating：默认 False，作为待独立 verdict 的研究选项。

### 3. 纯保真基线（红卡依据，fidelity_only = lot+停牌+退市+涨跌停+印花税5bp，无 partial）

| 本金 | full CAGR | OOS CAGR | turnover | rebs |
|---|---|---|---|---|
| 100k | −8.3% | −16.0% | 1154 | 1749 |
| 1M | +11.7% | **+27.1%** | 246 | 844 |

红卡已改**资本条件化**表述（migration 0036）：10 万零售本金=容量下限（OOS 负）；≥100 万本金保留 B070 约 95% edge。正 OOS 仍含 2024Q4 窗口顺风（B070 caveat），研究态/不可配资定性不变。

### 4. 空验证标注
- `new_all_on_recovery_0p5 == new_all_on` 为**空验证**：回测期内持仓簿 0 次触发退市清仓（宇宙内 52 次退市确认，但动量衰减在退市前已将名字换出）——recovery_rate 敏感性无从体现，非"不敏感"的证据。
- `only_suspension_halt` / `only_delist_liquidation` 与旧口径 bit 级一致同理（0 次咬中持仓簿；开关经单测证实已接线且能改变行为）。
