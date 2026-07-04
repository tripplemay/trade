# B081 回测引擎修真 — 独立验收 SIGNOFF（reverifying → DONE）

**批次：** B081 cn_attack 回测引擎修真（6 项高估源修复 + A/B 8 组 + registry + 红卡）
**验收人：** 独立 Evaluator（代 Codex，用户 /goal 授权）
**日期：** 2026-07-04
**轮次：** verifying-r1（FIXING，2 HIGH issues）→ fixing round 1 → **reverifying → DONE（全 PASS）**
**裁定：** **PASS → done**。ISSUE-1/2 修复经独立复验全部坐实解决，生产 L2 实测一致，措辞忠实我的实测结论。ISSUE-3 为已知自愈 soft-watch（carried）。

> **独立性披露（铁律 4）：** 本轮 fixing 由 planner 会话按默认映射亲自实施（并行 generator 会话休眠）。本复验面对的是 **planner 写的代码**，本人以最高怀疑度独立审查——每一条断言均自行实测/变异检查/生产查询/数字比对，不采信任何转述。evaluator≠implementer 独立性成立。

---

## 复验方法（不采信转述，全部独立执行）

| 判据 | 方法 | 结果 |
|---|---|---|
| ISSUE-1 partial 默认 False | git show diff + 自跑 33 cn_attack 单测 | ✓ 默认 `False`；33 passed |
| 守门单测有牙 | **变异检查**：临时翻回 `True` → 守门测试必须红 | ✓ `1 failed`（有牙），文件已还原 |
| live 默认=纯保真口径 | 代码实测 `CnAttackBacktestConfig()` 各开关 | ✓ partial=False / lot·停牌·退市·涨跌停=True / stamp=5bp = fidelity_only |
| 旧口径 bit 级不受影响 | 自跑 old_kou_jing/no_trade_band 回归 | ✓ 2 passed（开关显式传参路径不受默认翻转影响）|
| ISSUE-2 红卡资本条件化 | git diff + backend registration 测试 + 生产只读 | ✓ 见下 |
| 6 审计 trial 数字忠实 | 逐条比对 trial_backfill metrics vs 我 r1 实测 | ✓ 6/6 逐字一致 |
| 端到端 registration | 自跑 backend `test_b081_engine_fidelity_registration` | ✓ 3 passed（count==14 + 卡片更正 + 叙事移除守门）|
| 生产部署一致 | VM 只读查 alembic/card/registry | ✓ 见下 |

---

## ISSUE-1 复验（partial_rebalance 策略变动 → 默认 False）— PASS

- `engine.py`：`partial_rebalance: bool = True` → **`False`**，注释更正说明 F005 审计证其为收益改善型策略 cadence 变动（rebs 639→1517、OOS +28.4%→+32.7%），按 B069/B076 verdict-gating 默认 False、开关保留作待独立 verdict 的研究选项。
- 守门单测 `test_partial_rebalance_defaults_false_b081_issue1` 断言 `CnAttackBacktestConfig().partial_rebalance is False`。**变异检查确认有牙**：临时翻回 True → 该测试 `1 failed`（还原后原文件不变）。
- **回归安全**：A/B runner 各组均**显式**传 `partial_rebalance`（off 组 False / new 组 True），默认翻转不影响；old_all_off bit 级复现（我 r1 replay matches_old=true）不受影响。33 cn_attack 单测全绿。
- **live 默认口径**现为 fidelity_only（partial OFF），符合 planner 裁定"live 默认路径纯保真"。

## ISSUE-2 复验（红卡误 attribute → 资本条件化）— PASS

**代码/迁移**：
- `CN_ATTACK_RESEARCH_CAVEAT` 重写：range `-16.0% @10万 / +27.1% @100万 (B081 纯保真 PIT)`；headline 删除"分数股假象/策略样本外亏损"，改资本条件化（"约 9 只买不起一手=容量下限非策略失效"/"100 万保留 B070 约 95% edge"/"正 OOS 含 2024Q4 顺风仍不可配资"）；`validated=False`、`oos_result=negative`（10 万零售 paper 账户口径，理由注释在码）。
- migration 0036：UPDATE 卡片（byte-identical to in-code fallback，source=`b081_f005_capital_conditioned`）+ insert-only-missing 6 审计 trial；downgrade 完整。

**生产只读实测（VM 34.180.93.185，部署链已完成 20:51 UTC）**：
```
alembic head            = 0036_b081_card_capital_conditioned
trial_registry B081     = 14  (8 A/B + 6 审计)
红卡 (2 strategy)        : validated=0 / oos_result=negative /
                          source=b081_f005_capital_conditioned /
                          range="-16.0% @10万 / +27.1% @100万 (B081 纯保真 PIT)"
headline_zh             含"容量下限" ✓ / 不含"分数股假象" ✓ / 含 2024Q4 顺风 caveat ✓
审计 trial spot-check    lot@10M "13.2%/28.2%/195/644 ≈old 99% edge" ✓
                        fidelity_only@1M "11.7%/27.1%/246/844 ~95% edge" ✓
```

**措辞忠实性核对（我 r1 实测 vs planner 措辞）**：全部一致——容量下限（~9/25 买不起一手）、纯保真基线 @1M +27.1%（~95% edge）、2024Q4 顺风 caveat 保留、空验证标注（ab.md §4：recovery0.5==new_all_on 因持仓簿 0 次退市清仓触发 / suspension·delist bit 级一致同理）。

## 6 审计 trial 忠实性（逐条比对我 r1 实测）— PASS

| trial | planner 登记 | 我 r1 实测 | 一致 |
|---|---|---|---|
| audit_lot_at_1m | 10.5%/OOS23.5%/249/849 | 10.48/23.54/248.9/849 | ✓ |
| audit_lot_at_10m | 13.2%/OOS28.2%/195/644 | 13.21/28.18/195.2/644 | ✓ |
| audit_new_all_on_at_1m | 11.6%/OOS24.8%/265/1704 | 11.55/24.81/264.9/1704 | ✓ |
| audit_fidelity_only_at_100k | -8.3%/OOS-16.0%/1154/1749 | -8.32/-15.97/1153.6/1749 | ✓ |
| audit_fidelity_only_at_1m | 11.7%/OOS27.1%/246/844 | 11.68/27.13/246.2/844 | ✓ |
| audit_fullband_0p001 | OOS29.5% | 29.52 | ✓ |

---

## 常规门禁 / CI / 部署

- fix commit `4e1feed`：Python CI + Backend CI + Frontend CI **全绿**；Workbench Deploy 链式部署 success（20:51 UTC）。
- 自跑：cn_attack 33 + backend registration 3 + bootstrap CLI 5 + 变异检查 = 全绿。
- signal.py/construction.py 仍未动（不变量①）；validated 恒 False（不变量④）。

## carried soft-watch（非 blocking）

- **ISSUE-3(a) 快照自愈**：生产 cn_attack 快照 computed_at=2026-07-04 03:56 UTC（早于部署），内嵌 research_caveat 仍旧 B066 "-9%~-11%"；**权威红卡表（oos_verification_card）已更正**。快照 daily timer 下次 **2026-07-05 03:40 UTC（~6h）** 自愈（部署不触发 precompute timer）。建议 07-05 后 spot-check 快照 caveat==卡片表。同 B080"monitoring job 首跑自愈"先例。
- **ISSUE-3(b) parameter_hash**：`master_meta` 无该字段，spec F005 该核查项字面不可核（措辞问题，非产品缺陷；建议 spec 校正）。
- **ISSUE-3(c) 空验证标注**：已在 ab.md §4 补齐（DONE）。
- **微观察（非问题）**：`_AB_METRICS` verbatim 字符串保留 as-run（含"sub-lot *ST skipped"等原始 A/B 措辞，机制上高价名一手>目标仓位更精确）；权威更正在审计 trial + 红卡 + 注释，registry 追加式记录，可接受。

---

## 裁定

**B081 全 5 features PASS → status=done，completed_features=5。** 引擎修真 6 项修复经两轮闭环验收：实现正确（各开关独立、旧口径 bit 级复现）、A/B 数字可信（四疑点决定性澄清）、红卡口径经 fixing 修正为资本条件化（去除被证伪的"分数股假象"叙事，validated 恒 False 守不变量④）、partial 策略变动按 verdict-gating 剥离为默认 False。生产 L2 实测一致。

**接续**：partial_rebalance=True 作为"更高频响应信号"的策略变体，留待**独立 A/B verdict 批次**（backlog）。live 持久账簿降级仍为 spec §4 follow-up。快照自愈 07-05 spot-check。
