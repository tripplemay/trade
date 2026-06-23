# B076 — cn_attack size-tilt 选股 Signoff 2026-06-24

**批次：** B076 / **Sprint：** F003（CLI 代 Codex 执行，用户 2026-06-24 指派）
**验收日期：** 2026-06-24
**Evaluator：** CLI（代执行）
**HEAD：** `213634e6`（F002 NO-GO 路径 acceptance）
**Production deploy HEAD：** `c4bd82c4`（F001 size-tilt 机制，Workbench Deploy success）
**状态：** ✅ **NO-GO（合法诚实结论）— 生产不动，零回归守门通过，独立复跑 bit-identical**

---

## 变更背景

B075 把生产 universe 扩至 1490 只，但 cn_attack 选股仍落大盘蓝筹（top-25 与种子 43 高度重叠，paper rebalanced=0）——因为 composite（动量+质量）天然偏大盘。B076 加参数化 size-tilt 因子让选股能向中小盘倾斜，**对照回测后裁定 GO/NO-GO**（B069 NO-SWITCH 先例：不为"用上宽池"硬上一个更差的策略）。

---

## 变更功能清单

### F001 — size-tilt 机制 + 对照回测（executor: generator）

**文件：**
- `trade/strategies/cn_attack_momentum_quality/parameters.py`（新增 `size_tilt_weight` 参数，默认 0.0）
- `trade/strategies/cn_attack_momentum_quality/construction.py`（composite 加 size 因子，`size_tilt_weight=0` byte-identical）
- `trade/backtest/cn_attack_momentum_quality/engine.py`（marketcap 入参，默认 None）
- `scripts/research/b076_size_tilt_comparison.py`（sweep harness）
- `scripts/research/b076_fetch_pit_marketcap.py`（baostock turn 反推 PIT circ_mv）
- `docs/test-reports/B076-size-tilt-comparison.md`（sweep 结果报告）

**改动：** 加 `size_tilt_weight`（默认 0）→ `factor_weight_mapping()` 在 `size_tilt_weight=0` 时直接返回 pre-B076 mapping（无"size"key，市值从不加载）。>0 时 percent-rank 小市值因子入 composite，基础因子按 `1-size_tilt_weight` 缩放。

**验收：** 见下方实测证据。

### F002 — NO-GO 路径确认 + 零回归 acceptance 守门（executor: generator）

**文件：**
- `tests/acceptance/test_b076_size_tilt_zero_regression.py`（4 个永久 acceptance 测试）

**改动：** NO-GO 路径 = 生产 `size_tilt_weight=0` 不动 + acceptance 锁零回归不变量。无生产代码改动。

---

## 未变更范围

| 事项 | 说明 |
|---|---|
| 生产 cn_attack 选股 | `size_tilt_weight=0` byte-identical，选股==现状蓝筹 |
| US/Master/regime/hk 策略 | cn_attack-only 批次，其余全未触动 |
| cn_attack 不可配资定性 | 仍研究态/OOS 红卡，B076 未改定性 |
| 生产 cn_attack precompute | 无 size_tilt_weight 参数传入，默认 0 |

---

## L1 门禁（§30 跳 L1 复跑，CI 全绿确认）

| CI workflow | Commit | 结论 |
|---|---|---|
| Python CI | `213634e6` | ✅ success |
| Python CI | `c4bd82c4` | ✅ success |
| Workbench Backend CI | `c4bd82c4` | ✅ success |
| Workbench Deploy | `c4bd82c4` | ✅ success |

---

## 实测证据（决策级/真数据批次）

### ① 独立复跑 — size-tilt sweep（Primary 去偏，bit-identical 复现）

命令：
```bash
.venv/bin/python scripts/research/b076_size_tilt_comparison.py \
  --b070-root data/research/b070 \
  --b070-size data/research/b076/cn_size.csv \
  --b068-root data/research/b068 \
  --out-md /tmp/b076_independent_rerun.md \
  --out-json /tmp/b076_independent_rerun.json
```

**Primary（去偏）— pure_momentum on B070 survivorship-free PIT 宇宙（1310 名含退市）：**

| 档位 | size_tilt | CAGR | Sharpe | MaxDD | OOS CAGR | OOS Sharpe | 中位市值(亿) | 市值分位 | 中小盘占比 |
|---|---|---|---|---|---|---|---|---|---|
| current | 0.0 | 13.1% | **0.56** | -58.3% | 28.4% | 0.93 | 13.5 | 0.92 | 0.00 |
| light | 0.15 | 2.2% | 0.23 | -62.6% | 14.6% | 0.62 | 6.0 | 0.78 | 0.08 |
| medium | 0.3 | 5.9% | 0.35 | -51.3% | 20.5% | 0.84 | 3.4 | 0.64 | 0.28 |
| strong | 0.5 | 7.5% | 0.42 | -51.5% | 22.5% | 0.93 | 2.1 | 0.45 | 0.64 |

**独立复跑与 generator 报告数字完全一致（bit-identical）。**

去偏 integrity：`cn_size.csv` 覆盖 **1310/1310 = 100%**（names_empty=0，含退市名）。

**Secondary（survivor-biased，仅方向性）— quality_momentum on B068：**

| 档位 | size_tilt | CAGR | Sharpe | OOS Sharpe | 中小盘占比 |
|---|---|---|---|---|---|
| current | 0.0 | 28.3% | 1.00 | 1.88 | 0.08 |
| strong | 0.5 | 43.3% | 1.27 | 2.22 | 0.48 |

> Secondary 在幸存者宇宙看似 GO——退市小盘输家缺席，偏差美化中小盘。**不作裁定依据。**

### ② 独立裁定 GO/NO-GO

**独立裁定：NO-GO。**

判断依据（generator.md §故障诊断规则：全样本+OOS 双门禁 tol=0.02）：
- light (0.15): Sharpe 0.23 vs 0.56 → 劣化 -0.33 > tol → **FAIL**
- medium (0.3): Sharpe 0.35 vs 0.56 → 劣化 -0.21 > tol → **FAIL**
- strong (0.5): Sharpe 0.42 vs 0.56 → 劣化 -0.14 > tol → **FAIL**（OOS 险平 0.93 vs 0.93 = 2024Q4 窗口幸运，非稳健）

**每个能带来中小盘广度的档位（tilt>0）均在去偏宇宙拖累全样本风险调整后收益。** 符合 spec §0 verdict-gated 规则 + B069 NO-SWITCH 先例。

★ **关键铁证（幸存者偏差镜像）**：same size-tilt 在 survivor 宇宙（B068/幸存者 B075）会误判 GO，在去偏宇宙真值 NO-GO。这正是 spec §0『回测必须用 B070 去偏宇宙』的铁证。

### ③ 零回归验证 — acceptance 4/4 PASS

```
tests/acceptance/test_b076_size_tilt_zero_regression.py::test_default_params_have_no_size_factor PASSED
tests/acceptance/test_b076_size_tilt_zero_regression.py::test_production_live_target_selects_blue_chip_momentum_without_marketcap PASSED
tests/acceptance/test_b076_size_tilt_zero_regression.py::test_size_zero_selection_is_identical_with_or_without_marketcap PASSED
tests/acceptance/test_b076_size_tilt_zero_regression.py::test_size_tilt_on_would_change_selection_so_off_is_a_real_choice PASSED
4 passed in 5.07s
```

### ④ 生产 size_tilt_weight=0 确认

```python
# workbench_api/strategy_modes/cn_attack_precompute.py:183
parameters = CnAttackParameters(factor_variant=factor_variant)
# → size_tilt_weight 无传入 → DEFAULT_SIZE_TILT_WEIGHT = 0.0

# trade/strategies/cn_attack_momentum_quality/parameters.py:40
DEFAULT_SIZE_TILT_WEIGHT = 0.0
# parameters.py:161: if self.size_tilt_weight <= 0.0: return base  (no size key)
```

生产 precompute 实例化 `CnAttackParameters` 不传 `size_tilt_weight` → 默认 0.0 → `factor_weight_mapping()` 返回 pre-B076 mapping，市值从不加载。

---

## Ops 副作用记录

本批次无数据库 ops（NO-GO 路径，生产代码/DB 未修改）。

---

## Production / HEAD 等价性

| 项 | 值 |
|---|---|
| Production 已部署 | `c4bd82c4`（F001 code，Deploy success 2026-06-23）|
| Main HEAD | `213634e6`（F002 acceptance + NO-GO doc）|
| Diff | 1 commit（仅 `tests/acceptance/test_b076_size_tilt_zero_regression.py`）|

`git diff c4bd82c4..213634e6 --name-only` = 仅 `tests/acceptance/test_b076_size_tilt_zero_regression.py`（测试文件，非 production runtime behavior）→ **接受不同步，产品代码无漂移**。

---

## Post-signoff Deploy

| 项 | 值 |
|---|---|
| 签收 commit 类型 | signoff + state machine（仅 docs/test-reports/ + progress.json + .auto-memory/）|
| Post-signoff dispatch 是否需要 | **否** |
| 接受不同步声明 | 签收 commit 仅含 signoff 报告与状态机文件，未推产品代码；按 v0.9.25 §Production/HEAD 等价性接受不同步，无需 dispatch。|

---

## Decommission Checklist

本批次不含 decommission。

---

## Soft-watch

| ID | 描述 | 风险等级 | 建议处置 |
|---|---|---|---|
| S1 | 宽池（B075 1490 名）在当前 pure_momentum 下仍等同蓝筹 43 选股（B075 诚实偏离）。size-tilt NO-GO 后此状态维持。 | low | 未来若调整策略参数（exit 规则 / factor 权重）可重测广度。 |
| S2 | 去偏宇宙仍有残余偏差（仅 HS300∪ZZ500∪SZ50，无 zz1000/zz800；退市微小盘仍缺）。 | low | B070 既有 caveat，不阻断研究评估。 |

---

## Framework Learnings

### 新规律

- **★幸存者偏差镜像（B076 实例，强化 B070 规律）**：size-tilt 在 B068 survivor 宇宙看似 GO（quality Sharpe 1.27 > 1.00），在 B070 去偏宇宙却 NO-GO（pure Sharpe 0.42 < 0.56）。**同一策略改动，幸存者宇宙与去偏宇宙给出相反 verdict**——这是 spec §0『回测必须用去偏宇宙』第一个真实对照案例，verdict-gating 拦下了一个看起来"有改善"但实际更差的策略。
  - 来源：F001 PRIMARY/SECONDARY 对比
  - 建议写入：`framework/harness/planner.md`（中小盘/小因子策略研究批次，去偏宇宙不可省）

---

## 总结

**✅ B076 F003 PASS — NO-GO（合法诚实结论）**

| 验收维度 | 结论 |
|---|---|
| 独立复跑 sweep（去偏 primary）| ✅ bit-identical，NO-GO 成立 |
| 独立裁定 GO/NO-GO（不橡皮戳）| ✅ **独立 NO-GO**（全档位全样本 Sharpe 劣化）|
| 幸存者偏差铁证 | ✅ survivor=GO vs 去偏=NO-GO — spec §0 铁证 |
| 零回归 acceptance（4/4）| ✅ PASS |
| 生产 size_tilt_weight=0 | ✅ 代码确认，market cap 从不加载 |
| CI L1 全绿 | ✅ Python CI + Backend CI + Deploy 均 success |
| HEAD≡prod（产品代码层） | ✅ 仅测试文件漂移，接受不同步 |
| research-safe 边界 | ✅ no-broker / no 真金 / cn_attack 不可配资定性不变 |

**→ status: verifying → done**
