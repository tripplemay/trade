# B076 — cn_attack size-tilt 选股（让宽池真正改变选股，回测验证，条件上生产）Spec

**批次定位：** 策略研究 + 条件部署。B075 把生产 universe 扩到 1490,但选股仍落大盘蓝筹(top-25 与种子 43 高度重叠,paper rebalanced=0)——因为选股 composite(动量+质量)天然偏大盘。本批加一个**参数化 size-tilt 因子**让选股能向中小盘倾斜,**对照回测看放开蓝筹偏向是捡黑马还是踩雷**,**backtest 过关才上生产、不过关诚实 NO-GO**(B069 inverse-vol NO-SWITCH 先例)。

**来源：** 2026-06-22 用户「扩股票池」→ B075 发现单纯扩宇宙不改选股 → 用户选「A. 立后续改选股让宽池生效」。

---

## 0. ★诚实约束（焊死）

- **verdict-gated（同 B068/B069/B070）**：size-tilt 是**策略改动 → 必须回测验证**。GO（某 tilt 档位风险调整后不劣于现状且真带来中小盘广度）才上生产;**NO-GO（所有档位更差/只加风险）= 合法诚实结论,不改生产、照实报告**。
- **零回归默认**：`size_tilt_weight` 默认 **0 = 现状行为完全不变**（蓝筹选股）。回测扫 >0;GO 才把生产参数设为胜出档位。
- **回测必须用去偏 PIT 宇宙（B070）**：size-tilt 最可能改变的是中小盘,而中小盘**幸存者偏差最重**——回测须用 B070 survivorship-free PIT 宽宇宙（baostock 标注成分），**不得用 B075 当前 1490（对回测是幸存者偏差）**。OOS 诚实标注（B070 caveat:OOS 正收益部分是 2024Q4 反弹窗口落位）。
- **研究态不变**：本批改选股但**不改"未验证/不可配资"定性**;中小盘更激进=更可能暴雷,质量变体的基本面剔除是唯一防护。
- **cn_attack-only**：US/Master/regime/hk 零回归。

---

## 1. 现状 + 复用清单（已核源码）

| 资产 | 位置 | 用法 |
|---|---|---|
| composite 聚合 | `cn_attack/construction.py _aggregate_composite_score`（percent_rank 因子加权和,NaN-drop）| 加 size 因子(干净,US 零回归)|
| 因子权重参数 | `parameters.py momentum_weight/quality_weight`（quality_momentum）| 加 `size_tilt_weight`(默认 0)|
| 市值数据 | `cn_marketcap.py`（宇宙构建已 fetch 历史市值）| 线到选股层做 size 因子 |
| 去偏 PIT 宽宇宙 | B070 survivorship-free PIT（baostock 标注成分,1310 union）| 回测宇宙（非 B075 当前 1490）|
| 回测/对照 harness | B068/B069/B070 对照回测 + tests/acceptance（B071-B073）| size-tilt sweep 对照 |
| cn_attack precompute | `strategy_modes/cn_attack_precompute.py` | GO→size_tilt 参数上生产 |

---

## 2. Feature 拆解（3 features：2 generator + 1 codex）

### F001 — size-tilt 机制 + 对照回测（sweep，去偏宇宙，真数字 verdict）（executor: generator）

1. **机制**：composite 加一个 **percent-ranked size 因子**（市值越小得分越高 = small-tilt），参数 `size_tilt_weight`（默认 0;momentum/quality/size 权重 renormalize）。两变体（quality_momentum / pure_momentum）都支持。市值线到选股层。
2. **对照回测（B070 去偏 PIT 宽宇宙，OOS）**：扫 `size_tilt_weight` 档位（0=现状 / light / medium / strong）× 两变体,真成本（印花税仅卖+佣金+滑点）。
3. **真数字**：CAGR / Sharpe / max DD / 换手 + **★中小盘广度指标**（选股市值分布 / 与种子 43 重叠度 / 实际中小盘占比）——量化"tilt 到底有没有真把中小盘选进来"。
4. **verdict**：GO（某档位风险调整后不劣 + 真带广度）/ NO-GO（全更差或只加风险）。诚实 OOS caveat（2024Q4 窗口）。

**Acceptance：** size-tilt 机制（默认 0 零回归）+ 两变体支持;对照回测 sweep 真数字（CAGR/Sharpe/DD/换手/中小盘广度）+ GO/NO-GO verdict;用 B070 去偏宇宙非 B075 当前。Gates：trade pytest + mypy trade + ruff 目录上下文。

### F002 — 条件接生产（GO→size_tilt 上 precompute；NO-GO→不改生产）+ 不变量（executor: generator）

1. **GO 路径**：把 F001 胜出 `size_tilt_weight` 档位接 cn_attack precompute 两变体 → 生产 advisory/模拟盘选股反映 size-tilt;price_snapshot 同步新选股目标（复用 B074 cn_snapshot_sync）。
2. **NO-GO 路径**：生产 `size_tilt_weight` 保持 0（现状蓝筹）,**不改生产**,F001 verdict 写报告;本 feature 退化为"确认默认 0 零回归 + 文档化 NO-GO"。
3. **acceptance 守门**：`size_tilt_weight=0` 时选股 == 现状（零回归不变量,B071-B073 层）。
4. 边界：cn_attack-only;US/Master/regime/hk 零回归。

**Acceptance：** GO→生产 size_tilt 上 precompute（选股变化可见）;NO-GO→生产默认 0 不变 + 报告;`size_tilt_weight=0` 零回归 acceptance。Gates 同 F001 + backend pytest/mypy CI-exact + acceptance。

### F003 — Codex 验收（回测真数字复现 + 条件 GO/NO-GO 诚实 + 零回归）+ signoff（executor: codex）

**策略研究/条件部署批次——signoff 含真数字 + 诚实 verdict（§29 + B068-B070 范式）：**
- L1 全门禁（verifying 可跳 L1 复跑）。
- **回测真数字复现**：独立复跑 size-tilt sweep（B070 去偏宇宙）→ 复现 CAGR/Sharpe/DD/中小盘广度;**独立裁定 GO/NO-GO**（不橡皮戳 generator verdict）。
- **若 GO**：VM 真机验生产选股反映 size-tilt（贴新 top-25 vs 现状蓝筹对比 + 模拟盘）;**若 NO-GO**：确认生产 `size_tilt_weight=0` 未动。
- **零回归**：`size_tilt_weight=0` 选股 == 现状;US/Master/regime/hk 不破。
- 边界:research-only/no-broker/no 真金/不改"不可配资"定性;HEAD≡prod。signoff 真数字逐条 + 明确 GO/NO-GO + OOS caveat。

---

## 3. 状态流转 + 不变量

- 混合批次：`planning → building(F001→F002) → verifying(F003) → done`。
- **不变量**：① `size_tilt_weight=0` 完全零回归（默认=现状蓝筹选股）;② US/Master/regime/hk 零回归（cn_attack-only）;③ 回测用 B070 去偏 PIT 宇宙（非 B075 当前 1490）;④ research-safe / no-broker / no 真金 / 不改"不可配资"定性;⑤ §12.10.2 / ruff 目录上下文 / mypy CI-exact;⑥ verdict-gated（NO-GO 不改生产）。
- **诚实边界**：① NO-GO 是合法结论（B069 先例,不为"用上宽池"硬上一个更差的策略）;② 即便 GO,也只是"选股更广",不改 cn_attack 研究态/不可配资定性;③ 中小盘 OOS 幸存者偏差最重 + 2024Q4 窗口,verdict 须诚实标注。
- **后续**：GO 后可考虑 size-tilt 模拟盘对照（新增 paper 账户跟踪）/ 港股同款;NO-GO 则宽宇宙维持基础设施态。
