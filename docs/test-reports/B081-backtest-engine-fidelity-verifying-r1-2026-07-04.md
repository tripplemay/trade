# B081 回测引擎修真 — 独立验收 verifying-r1（→ FIXING）

**批次：** B081 cn_attack 回测引擎修真（6 项高估源修复 + A/B 8 组 + registry + 红卡）
**验收人：** 独立 Evaluator（代 Codex，用户 /goal 授权，与实现者上下文隔离）
**日期：** 2026-07-04
**裁定：** **FIXING** — 常规项全 PASS + 旧口径 bit 级复现 ✓；但**数字审计（本批核心）坐实 2 项口径/verdict-gating 问题**（疑点 3 + 疑点 1/4），另 1 项 soft-watch。引擎保真批次的 A/B 数字本身**可复现且正确**，但其**结论（红卡因果叙事）被误 attribute + 基线混入未 verdict 的策略变动**，批次目的（可信保真结论）未达成。

> **本批宁严勿松原则：** A/B 原始数字全部可复现（lot@100k 精确复现 −8.6%、old_all_off bit 级复现 B070），非造假。问题在**数字的解释**：红卡把 10 万本金容量下限误称"分数股假象/edge 消失"，且把收益改善型策略变动（partial_rebalance）当保真修复默认上线并混入基线。

---

## A. 常规项（全 PASS）

| 项 | 结论 | 证据 |
|---|---|---|
| L1 CI 全绿 | ✓ | main 最近 push（F004 200f4c8）Python CI + Backend CI + Frontend CI 全 success；F001-F003 各 push 亦全绿 |
| 旧口径 bit 级复现 B070 signoff | ✓ | 忠实 replay（`scripts/research/b081_audit_evaluator.py` experiment_events，复用真引擎 helper）复现 old_all_off：ending **243406.0** / turnover **194.01** / rebs **639**，`matches_old=true`。runner 自带断言亦 PASS（full_cagr 0.1312 / ending 243406 / OOS 0.284） |
| 不改策略信号逻辑（不变量①） | ✓ | `git diff 0ea7c53^..HEAD` 不含 `signal.py`/`construction.py`（二者最后改动在 B076/B068/B066）。修改仅在 engine/costs/parameters/reporting + backend 登记路径 |
| 死参数移除（#6） | ✓ | `grep rebalance_frequency trade/strategies/cn_attack_momentum_quality/parameters.py` 无命中（已移除；其余策略的同名字段无关） |
| 印花税 5bp（#4） | ✓ | costs.py `DEFAULT_STAMP_DUTY_BPS=5.0`，old 10bp 经 `CnCostModel(stamp_duty_bps=10.0)` 显式复现；A/B off 组用 10bp、new 用 5bp。**小注**：new 对 2019–2023 段亦用 5bp（真实该段 10bp，2023-08-28 减半）→ 前段成本略乐观，spec §0#4 明示的 flat-5bp 简化，影响微小 |
| registry + 红卡（B080 基建） | ✓（机制） | migration 0034 幂等 seed 8 组（insert-only-missing）+ 0035 更新红卡；backend test 验 count==8 / validated False / -14.7%。**生产只读实测**：alembic head=**0035**、trial_registry batch=B081 **8 条**（总 27+8=35）、红卡 2 strategy 均 **validated=0**（不变量④守住）、source=b081_engine_fidelity |
| live advisory 新口径不报错 | ✓ | 本地 live smoke（`scripts/research/b081_live_smoke.py`）：`compute_cn_attack_live_target` 用**新默认 config** 运行**无报错**，发布 25 名 weights_sum=1.0 / cash≈0 / rebalanced=true |

---

## B. 数字审计（本批核心 — Planner 四疑点逐一裁定）

所有 evaluator 实验脚本 + 原始数据落 `scripts/research/b081_audit_evaluator.py` + `data/research/b070/b081_audit_evaluator.json`。

### 疑点 2 — 停牌 / 退市零影响 → **合法 no-op（PASS，需空验证标注）**

**裁定：正面证据确认 = 真 0 事件，非开关未接。**

- **开关已接上（单测证明）**：`test_suspension_halt_freezes_a_held_name`（drop held 名 mid-window bar → 断言 `run(True).ending_value != run(False)`）、`test_price_limit_gating_restricts_a_locked_name`（+15% 涨停 → 断言 diverge）、`test_delist_confirmation_detection`（检测逻辑正确）。→ 开关接上且能改变行为。
- **反事实事件计数（忠实旧路径 replay，在真实旧持仓簿上，`matches_old=true` 保证可信）**：

| 开关 | 宇宙事件供给 | 持仓簿咬中 | 结论 |
|---|---|---|---|
| suspension_halt | — | **0 名 / 0 天** | 此策略从不持名入停牌日 → 合法 no-op |
| delist_liquidation | 宇宙内 **52 次退市确认** | **0 名 / 0 天** | 52 次退市但动量在退市前已把名字换出 → 合法 no-op（坐实 Planner 假设） |
| price_limit_gating | — | **23 名 / 12 天** | 真实小效果，匹配 A/B 微小 delta（OOS 28.4%→28.9%、rebs 639→642） |

- **动作**：`only_suspension_halt`/`only_delist_liquidation` 与 old bit-identical = 真 0 事件（合理），非 bug。registry note 已标 NO-OP。**须补**：`new_all_on_recovery_0p5` == `new_all_on` 逐字相同（delist 0 触发 → recovery 敏感度**不可测**）→ 报告/敏感列应显式标"空验证（0 退市清仓触发）"而非呈现为"敏感度低"。

### 疑点 1 — lot_rounding 灾难劣化（13.1%→−8.6%）→ **10 万本金容量下限假象（口径问题，非策略真相）**

**决定性对照实验（Planner 必跑项）：only_lot_rounding × 本金扫描**

| 本金 | full CAGR | OOS CAGR | OOS Sharpe | turnover | rebs | ending |
|---|---|---|---|---|---|---|
| off@100k（旧口径基准） | 13.1% | 28.4% | 0.93 | 194 | 639 | 243406 |
| **lot@100k** | **−8.6%** | **−16.0%** | −2.16 | 1160 | 1749 | 52147 |
| **lot@1M** | **+10.5%** | **+23.5%** | **0.87** | 249 | 849 | 2052573 |
| **lot@10M** | **+13.2%** | **+28.2%** | **0.93** | 195 | 644 | 24480605 |

> **容量恢复曲线（决定性）**：OOS CAGR 100k **−16.0%** → 1M **+23.5%** → 10M **+28.2%**（≈ off@100k 28.4%，**保留 99% edge**）；换手 1160 → 249 → **195**（≈ off 194）；rebs 1749 → 849 → **644**（≈ off 639）。单调恢复到旧口径 → lot_rounding 的 −16% **纯粹是 10 万本金容量下限**，10M 本金下几乎零效果。"分数股假象"彻底证伪。

**+ 一手可买性静态探针（14 个采样调仓日，25 名等权）：**
- **10 万本金**：每调仓日 **3–16 名（均值 ~9）买不起一手**（一手成本中位 ~2000–7000 元，峰值达 97304 元 > 每名目标仓位 4000 元）
- **100 万本金**：0–1 名买不起
- **1000 万本金**：0 名

**机制裁定 = 资金粒度真相（capacity floor），非 band×取整 bug：**
- 10 万本金下 25 名等权（每名 4% = 4000 元），A股高价名一手 > 4000 元 → ~9/25 名被 skip 留现金 → 实际持仓簿永远远离 target → `_would_be_turnover(current, target) ≈ 9×4% = 36% > 20% band` **每日重触发** → 换手爆炸 6x（194→1160）、rebs 639→1749。
- **100 万本金下数字恢复**：full −8.6%→**+10.5%**、OOS −16.0%→**+23.5%**、换手 1160→**249**（归一）、rebs 1749→**849**。→ 确认为**容量下限**，非路径 bug。
- **诚实结论应是**：策略在 10 万本金下**不可按 spec（25 名等权整手）实施 = 容量下限**；≥100 万本金下 lot_rounding 仅使 OOS 28.4%→23.5%（**保留 ~83% edge**，换手正常）。**不是"策略 −8.6%"**。

### 疑点 3 — partial_rebalance 大幅变好 + rebs×2.4 → **未 verdict-gated 的策略 cadence 变动（坐实 → FIXING ISSUE 1）**

**裁定：Option A 实质是"更频繁小步调仓"的策略变体，超出「执行保真修复」，不应作默认口径 silently 上线。**

- **实现（engine.py:715-728）**：`partial_rebalance=True` **完全绕过 no_trade_band**（策略核心"不动区"机制），把触发从"聚合 would-be turnover > 20%"改为 `_partial_would_be_turnover > 0`（任一名进出 / 漂移 > 0.5%）。
- **A/B 实测**：`only_partial_rebalance` rebs **639→1517（×2.4）**、turnover **194→236（↑，非↓）**、full CAGR **13.1%→20.7%（↑）**、OOS **28.4%→32.7%（↑）**。
- **矛盾点**：
  1. 改变了**哪些天交易**（调仓 cadence），是收益改善型策略行为变动，非"执行/估值/成本层"保真。
  2. generator commit 7a063c7 亲述"makes the default trade **MORE** than the old band (53 vs 14.6 turnover)"，却标为"**更保守/数字变差** direction"——与 A/B 实测收益**变好**相反；"old band held unrealistically long"是策略设计观点，非执行保真事实。
  3. spec §0#5 原意 = "band **触发后**只交易超阈名"（band 仍作触发），Option A 偏离（drop band）。
  4. 违反 B069/B076 verdict-gating（策略变动须独立 verdict）+ spec §3 不变量①精神。
  5. spec F001 acceptance "部分调仓换手 **< 全量**" 在聚合层被证伪（236 > 194）。
- **Cadence 隔离对照（evaluator，fullband0.001@100k = 全额 re-target + 近零 band，≈ 每日全簿调仓、无 lot_rounding）**：full 12.3% / OOS **29.5%** / turnover 264 / rebs **1749**。→ 单纯"高频调仓"（全额）已达 OOS 29.5%（≈ old）；partial 的 OOS 32.7% 中额外 +3pp 来自"部分执行降 churn"。两者叠加 = 与旧 20%-band-全簿-调仓**本质不同的调仓策略**（更高频 + 更小步），确证 partial=收益改善型策略变动而非执行保真。

### 疑点 4 — new_all_on 红卡语义 → **误 attribute 容量下限 + 混入策略变动（坐实 → FIXING ISSUE 2）**

- new_all_on(−6.6% / OOS −14.7%) = lot_rounding@10万容量假象（疑点 1，主导）+ partial_rebalance 策略变动（疑点 3，+7.6pp 被 lot thrash 掩盖）+ suspension/delist（0）+ price_limit（~0）+ stamp5（微）。
- **决定性直接证伪（evaluator followup）：红卡所依据的完整 shipped 配置 new_all_on 在 100 万本金 = full +11.6% / OOS +24.8% / rebs 1704**（vs new_all_on@100k −6.6% / OOS −14.7%）。→ **同一新口径配置在充足本金下 OOS 为正**，红卡"修真后策略样本外亏损"在 ≥100 万本金**成立不了**，−14.7% 纯粹是 10 万零售容量下限。
- **红卡（生产已部署）headline**：「原 B070 +28.4% 大半是分数股假象，修真后策略样本外亏损。」
- **被 lot@1M/lot@10M 证伪**：100 万本金 OOS **+23.5%**（保留 ~83% edge）、**1000 万本金 OOS +28.2%（保留 99% edge，≈ off 28.4%）**；edge **未消失**，转负**只**发生在 10 万零售容量下限。"分数股假象（fractional-share artifact）"+"策略样本外亏损（无条件）"= **误 attribute + 过度概括**。
- **方向安全但叙事错误**：validated 恒 False、更保守（不变量④守住），但**因果叙事错误**（容量下限 ≠ edge 是假象），且 new_all_on 基线**混入 partial 策略变动**（非纯保真）。

---

## C. FIXING issues（须修 + 复验判据）

### ISSUE 1（HIGH）— partial_rebalance Option A：未 verdict 的策略 cadence 变动混入保真基线
- **文件**：`trade/backtest/cn_attack_momentum_quality/engine.py`（`partial_rebalance` 默认 True + `_partial_would_be_turnover` band-bypass:715-728）
- **复现**：`only_partial_rebalance` rebs 639→1517、turnover 194→236↑、CAGR 13.1%→20.7%↑、OOS 28.4%→32.7%↑
- **修法（二选一，交 Planner→用户裁定）**：
  - (A) `partial_rebalance` 默认改 **False**（保守；作需独立 verdict 的策略维度 opt-in）→ new_all_on 基线回归纯保真；或
  - (B) 按 spec §0#5 原意重做（band **保持触发** + 触发后部分执行）→ 预期换手↓（真保真方向）。
  - 任一都须把 partial 从"引擎修真基线"剥离，new_all_on / 红卡口径重算。
- **复验判据**：new_all_on（不含 partial 策略变动）A/B 重跑 + 红卡口径基于 fidelity-only；或 partial 单独走策略 verdict 批次。

### ISSUE 2（HIGH）— 红卡 headline 误 attribute 10 万本金容量下限为"分数股假象/edge 消失"
- **文件**：`workbench/backend/workbench_api/strategy_modes/cn_attack_precompute.py`（`CN_ATTACK_RESEARCH_CAVEAT.headline_zh/en`）+ `docs/test-reports/B081-engine-fidelity-ab.md` + `workbench/backend/workbench_api/monitoring/trial_backfill_b081.py`（`_AB_METRICS`）+ 生产红卡行（migration 0035 已部署，须补一个更正 migration）
- **复现**：lot@100k −8.6%/OOS −16.0% vs lot@1M +10.5%/OOS +23.5%（`b081_audit_evaluator.json`）+ 可买性探针（10万本金 ~9/25 买不起一手）
- **修法**：红卡/报告/registry 改为**资本条件化**表述，如「10 万零售本金下 25 名等权触及容量下限（~9/25 整手买不起）→ OOS 转负；≥100 万本金下 lot_rounding 仅使 OOS 28.4%→23.5%，edge 保留」。移除"largely a fractional-share artifact / 策略样本外亏损（无条件）"措辞。红卡数字若保留更保守值须注明"10 万本金容量下限口径"。
- **复验判据**：红卡 headline 不再无条件宣称"策略样本外亏损/分数股假象"；改容量条件化；与 ISSUE 1 联动重算 new_all_on 口径。

### ISSUE 3（SOFT-WATCH，非 blocking）— 快照未重算 + 空验证标注
- (a) 生产 cn_attack 快照 computed_at=2026-07-04 03:40/03:56 UTC（**早于** F004 部署 17:27 UTC），内嵌 caveat 仍旧 "-9%~-11%" B066 版，红卡表已 "-14.7%" → **瞬态不一致**，待下一次 daily timer（07-05 03:40 UTC）自愈。**本地 live smoke 已证新口径 precompute 不报错**：old_lot_off would_be_turnover=**0.19 < band → HOLD**（不动区正常，winners run）vs new_default（lot@100k）would_be_turnover=**1.0（最大）→ 恒 rebalance**——10 万本金 lot 取整使 held 簿退化到与 target 几近完全不相交，"不动区/winners run"特性**实质关闭**（但发布 target 仍干净 25 等权 sum=1.0，**无破损输出**；ISSUE 1 修复后随之改善）。建议 07-05 后复核快照 caveat==红卡表。
- (b) `master_meta` **无 parameter_hash 字段** → spec F005"parameter_hash 变更已在快照 meta 体现"字面不可核。建议校正 spec 措辞或改核 trial_registry.parameter_hash。
- (c) recovery_rate=0.5 敏感列 = **空验证**（delist 0 触发 → 与 1.0 逐字相同）→ 报告须标"空验证（0 退市清仓触发）"。

---

## D. Evaluator 复跑证据清单
- `scripts/research/b081_audit_evaluator.py` — 资金扫描 + 可买性探针 + 忠实旧路径 replay 事件计数（`matches_old=true` 自校验）
- `scripts/research/b081_live_smoke.py` — 新默认口径 live advisory 无报错验证
- `scripts/research/b081_audit_followup.py` — new_all_on@1M / fidelity_only 隔离（容量 vs 策略变动，后台跑作佐证，不改变裁定）
- `data/research/b070/b081_audit_evaluator.json` — 原始实测数字
- 生产只读核查：alembic head=0035 / trial_registry B081=8 / 红卡 validated=0 / 快照 computed_at 早于部署

**状态流转**：verifying → **fixing**（fix_rounds 保持 0，首轮 verify→fixing）。generator 接 ISSUE 1/2 修复 → reverifying。
