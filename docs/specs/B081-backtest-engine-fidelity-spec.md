# B081 — cn_attack 回测引擎修真：停牌/退市/涨跌停/手数/成本/band（评审 P0.5）Spec

**批次定位：** 回测可信度前置批次（混合批次 4 generator + 1 codex，主战场 `trade/`）。修复评审报告 §1.4B 识别的 6 项引擎级回测高估源。修复方向全部「更保守」——**预期去偏基线数字变差 = 诚实，不构成回归**；每项修复带独立开关 + B070 去偏基线 A/B 对照，量化各高估源的影响。P2 信号升级与任何小盘策略的硬前置。

**来源：** 2026-07-03 用户立项（backlog `B0XX-backtest-engine-fidelity`，评审路线图 P0.5）← `docs/research/ashare-strategy-deep-review-2026-07-03.md` §1.4B（6 项问题的代码位置由评审工作流 code-reader 精读确认）。

**Planner 默认决策（用户 /goal 持续推进授权下采用，可随时推翻）：**
1. **退市处理口径 = 末价强制清仓 + recovery_rate 敏感性**：退市名（价格序列终止）在终止确认日按最后有效 close × `delist_recovery_rate` 强制清仓（收正常卖出成本）。默认 `recovery_rate=1.0`（末价全额，不引入拍脑袋折价），A/B 对照报告**必须附 recovery_rate=0.5 敏感性列**暴露口径敏感度。不做阶梯折价（无实证依据的自由参数）。
2. **live 持久账簿降级 follow-up**：跨 trade/workbench 边界、工作量最大且不影响回测保真（只影响 live 发布簿稳定性），本批不做，记入 §4 后续。
3. **红卡/登记走 B080 基建**：F004 基线重跑结果登记 `trial_registry`（自动，B080 F001 worker 路径或 seed 同款幂等写入）+ 若基线数字变化则更新 `oos_verification_card`（**只能更保守方向；validated 保持 False**——B080 §3 不变量②在本批同样有效）。

---

## 0. 六项修复（各带代码证据，评审工作流 2026-07-03 精读确认）

| # | 问题 | 证据 | 修法 |
|---|---|---|---|
| 1 | **停牌/退市 ffill（最重）**：停牌名 ffill 最后价且可按旧价成交；退市股序列终止后 ffill 到永远、持仓永不减记（代码自注"P1 简化"） | engine.py `_wide()` :163-173 | 停牌日（该名当日无真实 bar）禁止成交，mark 用最后有效价并计 stale 天数；退市名按默认决策 1 强制清仓 |
| 2 | **涨跌停可执行性**：`_execute_open` 无条件按开盘价成交——动量策略系统性买刚大涨的票 | engine.py :246-326 | 开盘触板判定（开盘价 vs 前收 ±9.9%/19.9%，板幅按代码前缀 300/688=20%、其余 10%，ST 不在宇宙）：涨停禁买、跌停禁卖；未成交名当日放弃（权重留现金），下一调仓日重新评估 |
| 3 | **手数取整**：份额浮点，10 万 × 4% 仓位高价股一手买不起 | engine.py :292 | 买入向下取整 100 股整数倍，余额进现金；卖出整仓全数 |
| 4 | **印花税过时**：卖出 10bp 注释"as of 2023-08"，实际 2023-08-28 起 5bp | costs.py :16-19 | 更新为 5bp（成本下降=口径更正非乐观化，A/B 报告标注） |
| 5 | **band 全量 rebalance**：触发即全簿拉回目标（实际换手 > 触发最小换手 + 路径依赖） | engine.py :277-299 | band 触发后只交易进出名单与 |Δw| 超 per-name 阈值（默认 0.5%）的名；漂移容忍内的持仓不动 |
| 6 | **死参数**：`rebalance_frequency="monthly"` 无消费点仅进 hash | parameters.py :29,91,180 | 移除字段；parameter_hash 兼容处理（hash 载荷本就 sort_keys 序列化——移除后 hash 变化，A/B 对照以新旧配置双跑覆盖；live advisory 记录的 identifier 变更在 signoff 说明） |

## 1. 复用清单

| 资产 | 位置 | 用法 |
|---|---|---|
| 引擎与成本模型 | trade/backtest/cn_attack_momentum_quality/{engine,costs}.py | 修复主战场 |
| 去偏基线数据 | data/research/b070/（PIT 宇宙+含退市价格）| A/B 对照输入（冻结快照） |
| 对照脚本骨架 | scripts/research/b070_survivorship_comparison.py + b076_size_tilt_comparison.py | F004 A/B runner 模板 |
| trial_registry / oos_verification_card | B080 F001（workbench_api/db） | 结果登记与红卡更新 |
| 对比报告器 | trade/reporting/cn_attack_wide_comparison.py | 指标口径 |

## 2. Feature 拆解（5：4 generator + 1 codex）

> **Gates（全部 generator features 通用，吸收 B080 F002 教训显式列出）**：本批主战场 `trade/` → 每个 feature 本地必跑 `.venv/bin/mypy trade` + 根 `python -m ruff check .` + 根 pytest 相关子集；若 backend 侧需要（F004 登记路径），`cd workbench/backend && .venv/bin/python -m pip install ../..` 重装 trade 后再跑 backend pytest。CI 三条全绿（Python CI + Backend CI + Frontend CI）。

### F001 (g) — 成本 5bp + 手数取整 + band 部分调仓 + 死参数清理（修复 #3#4#5#6）
- 每项独立开关进 engine config（`lot_rounding` / `partial_rebalance` 默认 True 新口径；`stamp_duty_bps` 直接改默认值 5.0）；`rebalance_frequency` 从 parameters 移除。
- 单测覆盖：手数取整余额/一手买不起→跳过留现金/band 触发只动超阈名/部分调仓换手 < 全量、hash 变更断言。
**Acceptance：** 4 项修复独立开关可回退旧口径（`lot_rounding=False` 等复现修复前数字，bit 级）；新默认口径单测全绿；Gates 通用段。

### F002 (g) — 停牌/退市处理（修复 #1）
- 停牌判定 = 该名当日无真实 bar（ffill 补出的 mark 行标 stale）；停牌日禁买禁卖，目标权重顺延；mark 保持最后有效价。
- 退市判定 = 序列终止且不再恢复（数据末日之前 N=10 交易日无 bar 且非全市场停牌日）；终止确认日按 close×recovery_rate 强制清仓收卖出成本；`delist_recovery_rate` 默认 1.0 可配。
- 单测：停牌期成交拒绝/恢复后可交易/退市清仓入现金/recovery_rate=0.5 数字变化方向正确/B070 曾实测的 ffill-vs-计0 等价场景在新口径下的行为。
**Acceptance：** 开关 `suspension_halt`/`delist_liquidation`（默认 True）；关闭时 bit 级复现旧口径；单测覆盖边界；Gates 通用段。

### F003 (g) — 涨跌停可执行性（修复 #2）
- 触板判定纯价格推断（开盘 vs 前收，板幅按前缀），无新数据依赖；涨停禁买/跌停禁卖，当日放弃留现金。
- 单测：触板买入拒绝/触板卖出拒绝/20% 板（300/688）与 10% 板判定/边界（恰好 9.9%）/放弃后下一调仓日重评。
**Acceptance：** 开关 `price_limit_gating`（默认 True）；关闭 bit 级复现旧口径；单测覆盖；Gates 通用段。

### F004 (g) — A/B 对照基线重跑 + 登记 + 红卡更新
- runner（scripts/research/b081_engine_fidelity_ab.py，模板照 b076）：在 **B070 去偏 PIT 宇宙**（冻结快照，窗口 2019-04-01..快照末）对 pure_momentum+equal 跑：旧口径（全开关 off）/ 每项单独 on（5 组）/ 全 on（新基线）/ 全 on + recovery_rate=0.5 敏感性 —— 共 8 组，产对照表（CAGR/Sharpe/MaxDD/OOS 三口径逐项 delta）落 `docs/test-reports/B081-engine-fidelity-ab.md`。
- 每组登记 trial_registry（幂等，source_ref 指向对照报告）；全 on 新基线若与现红卡数字口径冲突 → 更新 oos_verification_card（更保守方向；validated 恒 False；headline 注明"B081 引擎修真后口径"）。
- 旧口径组必须与 B070 signoff 数字 bit 级一致（复现性证明修复实现未污染旧路径）。
**Acceptance：** 8 组对照表落盘 + 27+8 条 registry + 卡片更新（若适用）+ 旧口径复现 bit 级一致；Gates 通用段 + backend 侧登记路径测试。

### F005 (codex) — 独立验收 + signoff
- L1：CI 全绿 + 新单测子集本地抽查（各开关回退 bit 级复现断言重点）。
- L2：A/B 对照表数字复核（抽 2 组手工重跑对照）；旧口径 vs B070 signoff bit 级一致实测；生产侧确认 trial_registry 新增 8 条 + 卡片状态（validated 仍 False）；live advisory 快照在新默认口径下正常产出（VM 只读）+ parameter_hash 变更已在快照 meta 体现且 surface 无报错。
- 边界：research-only/no-broker；不改策略信号逻辑（修复全在执行/估值层——diff 审计断言 signal.py/construction.py 未动）；HEAD≡prod。

## 3. 状态流转 + 不变量
- `planning → building(F001→F002→F003→F004) → verifying(F005) → done`。
- **不变量**：① 不改策略信号逻辑（signal/construction 不动，只动执行/估值/成本层）；② 每项修复独立开关、关闭时 bit 级复现旧口径（复现性=可审计）；③ 旧口径复现须对上 B070 signoff 数字；④ oos_verification_card 只能更保守方向更新、validated 恒 False（摘卡走人工批次，B080 不变量延续）；⑤ research-only / no-broker / advisory-only；⑥ Gates 通用段（trade/-edit 三门禁 + backend venv 重装）。
- **诚实边界**：① 新口径数字预期变差——这是修真目的；② 触板判定用日频开盘价近似（真实盘中触板更严，日频下界）；③ recovery_rate 无实证取值，以敏感性列呈现而非单点断言；④ live 持久账簿问题本批不修（见 §4）。
- **§4 后续（follow-up，不在本批）**：live 每日重放改持久账簿（跨 trade/workbench，候选挂 backlog）；停牌名 mark 的 stale 折价研究；分钟级触板判定（需新数据）。
