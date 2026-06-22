# B076 F001 — cn_attack size-tilt 对照回测（让宽池真改选股？真数字 + GO/NO-GO）

**裁定（以去偏 primary 为准）：NO-GO** — Every tilt that added breadth DEGRADED full-sample risk-adjusted return (full Sharpe < current 0.559) — leaning into small-caps hurt the period-wide Sharpe. Any OOS-Sharpe near-tie is the 2024Q4 small-cap-rally window-luck (B070 caveat), NOT robustness. Don't ship a worse strategy to 'use' the wide pool (B069 NO-SWITCH).

> **★关键对照（本批铁证）：去偏 primary = NO-GO，但 survivor secondary = GO。**同一个 size-tilt，在**幸存者偏差宇宙里看起来更优**（中小盘亏损/退市名缺席被藏），在**去偏宇宙里却拖累全样本风险调整后收益**。若按 B075 当前/幸存者宇宙回测就会**误判 GO 上生产**——这正是 spec §0『回测必须用 B070 去偏宇宙』的铁证，也是 verdict-gating 拦下一个更差策略的实例。

> **诚实边界：** verdict-gated（B069 NO-SWITCH 先例）——size-tilt 是策略改动，GO 才上生产；NO-GO 合法，不为『用上宽池』硬上一个更差的策略。回测用 **B070 去偏 PIT 宽宇宙**（中小盘幸存者偏差最重，不得用 B075 当前 1490）。OOS 正收益部分落在 2024Q4『924』反弹窗口（B070 caveat），OOS>IS 多为窗口落位、非稳健性证据。即便 GO 也只是选股更广，**不改 cn_attack 研究态 / 不可配资定性**；中小盘更激进=更可能暴雷。

窗口 2019-04-01..today；equal 权重；exit momentum_decay；真成本（印花税仅卖+佣金+滑点）；WF 70/30。

## Primary（去偏）— pure_momentum on B070 survivorship-free PIT 宇宙
**NO-GO** — Every tilt that added breadth DEGRADED full-sample risk-adjusted return (full Sharpe < current 0.559) — leaning into small-caps hurt the period-wide Sharpe. Any OOS-Sharpe near-tie is the 2024Q4 small-cap-rally window-luck (B070 caveat), NOT robustness. Don't ship a worse strategy to 'use' the wide pool (B069 NO-SWITCH).

| 档位 | size_tilt | 调仓 | CAGR | Sharpe | MaxDD | OOS CAGR | OOS Sharpe | 选股数 | 中位市值(亿) | 市值分位 | 种子43占比 | 中小盘占比 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| current | 0.0 | 639 | 13.1% | 0.56 | -58.3% | 28.4% | 0.93 | 25 | 13.5 | 0.92 | 0.00 | 0.00 |
| light | 0.15 | 799 | 2.2% | 0.23 | -62.6% | 14.6% | 0.62 | 25 | 6.0 | 0.78 | 0.00 | 0.08 |
| medium | 0.3 | 812 | 5.9% | 0.35 | -51.3% | 20.5% | 0.84 | 25 | 3.4 | 0.64 | 0.00 | 0.28 |
| strong | 0.5 | 738 | 7.5% | 0.42 | -51.5% | 22.5% | 0.93 | 25 | 2.1 | 0.45 | 0.00 | 0.64 |

- **中小盘广度读法**：`市值分位` 越低=选股越偏小盘（0=最小，1=最大）；`中小盘占比`=选股中市值低于宇宙中位的比例；`种子43占比`=与现状蓝筹种子重叠度。tilt 真生效 → 分位↓ + 中小盘占比↑。

## Secondary（survivor-biased，**仅方向性**不作裁定）— quality_momentum on B068 当前 top-N
**GO** — size_tilt=0.5 (strong) is risk-adjusted not-worse on BOTH full Sharpe (1.274 vs 1.001) and OOS Sharpe (2.221 vs 1.876) AND genuinely adds small-cap breadth (small_cap_frac 0.48 vs 0.08; cap_pctile 0.522 vs 0.832).

> 退市名无免费 quality 基本面 → quality_momentum 无法去偏；本 cut 用 B068 幸存者宇宙，**幸存者偏差反而美化中小盘**（退市小盘输家缺席）。故此 cut 仅验证 tilt 在含 quality 时的行为，NO-GO 在此更具说服力，GO 不足为凭。

| 档位 | size_tilt | 调仓 | CAGR | Sharpe | MaxDD | OOS CAGR | OOS Sharpe | 选股数 | 中位市值(亿) | 市值分位 | 种子43占比 | 中小盘占比 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| current | 0.0 | 415 | 28.3% | 1.00 | -45.9% | 74.9% | 1.88 | 25 | 13.8 | 0.83 | 0.00 | 0.08 |
| light | 0.15 | 414 | 30.7% | 1.03 | -49.0% | 80.7% | 1.94 | 25 | 7.7 | 0.67 | 0.00 | 0.16 |
| medium | 0.3 | 408 | 36.6% | 1.14 | -46.7% | 83.4% | 1.97 | 25 | 6.0 | 0.58 | 0.00 | 0.36 |
| strong | 0.5 | 327 | 43.3% | 1.27 | -51.5% | 101.4% | 2.22 | 25 | 5.1 | 0.52 | 0.00 | 0.48 |

## 诚实 caveat（焊死）
- **去偏 integrity**：cn_size.csv 覆盖 B070 宇宙 **1310/1310=100%**（names_empty=0，circ_mv 含退市名）→ 各 tilt 档位选股宇宙完全一致（apples-to-apples），无名因缺市值被丢弃，中性插补未触发 → NO-GO 干净、非覆盖缺口造成。
- **去偏天花板**（B070）：仅指数可纳入band（HS300∪ZZ500∪SZ50），无 zz1000/zz800 → 退市微小盘仍缺=残余偏差；本批 size-tilt 的『中小盘』实为指数内中小盘，非真·微盘。
- **OOS 窗口**：70/30 把 2024Q4『924』反弹放进 OOS；正 OOS 含窗口顺风，非可配资证据。
- **市值口径**：circ_mv 由 baostock `turn` 反推（close×volume×100/turn，未复权），月末降采样。
- **research-only**：no-broker / no 真金 / 不改 cn_attack 不可配资定性（B075 同）。