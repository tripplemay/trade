# B070 F004 Signoff — A股 进攻策略 去幸存者偏差重验 验收报告

**批次:** B070 / **Sprint:** F004 (Codex 验收)  
**验收日期:** 2026-06-19  
**Evaluator:** Andy (CLI 代 Codex)  
**HEAD≡Prod:** `e91b669396a21a1624eabef0e1f819d4a3c40ea3` (feat(B070-F003), VM API 实测确认)  
**状态:** ✅ PASS（研究判定：SURVIVES_DEBIASING）

---

## §1 核心研究结论（§29 实测证据硬段）

### 1.1 批次核心问题答案

**「去掉幸存者偏差后，这个 A股 进攻策略还成立吗？」**

**→ 仍成立（SURVIVES_DEBIASING），但幸存者偏差使表观 OOS 虚高约一倍。**

### 1.2 F003 真数字对比（f003_survivorship_comparison.json 实测）

| 宇宙 | 调仓次 | CAGR | Sharpe | MaxDD | **OOS CAGR** | **OOS Sharpe** | OOS DD |
|---|---|---|---|---|---|---|---|
| survivorship_free_pit | 639 | 13.1% | 0.56 | -58.3% | **28.4%** | **0.93** | -27.8% |
| biased_control | 611 | 28.8% | 0.93 | -50.2% | **55.0%** | **1.45** | -25.1% |

```json
{
  "judgment": {
    "verdict": "SURVIVES_DEBIASING",
    "survivorship_bias_full_cagr": 0.1569,
    "survivorship_bias_oos_cagr": 0.2663,
    "survivorship_bias_oos_sharpe": 0.517,
    "pit_oos_cagr": 0.2839,
    "pit_oos_sharpe": 0.93,
    "control_oos_cagr": 0.5502,
    "control_oos_sharpe": 1.447
  },
  "pit": {
    "rebalance_count": 639,
    "exit_count": 0,
    "is_split_date": "2024-04-18",
    "is_cagr": 0.0714,
    "is_sharpe": 0.386
  }
}
```

**判定依据（spec §3 judge() 规则）：**  
PIT OOS CAGR = 28.4% > 0 ✅ AND PIT OOS Sharpe = 0.93 > 0 ✅ → SURVIVES_DEBIASING

---

## §2 F001 三关口 feasibility（GO 已入 git）

| 关口 | 结果 | 证据 |
|---|---|---|
| A. 历史 PIT 成分（baostock query_hs300/zz500/sz50） | ✅ GO | 2007→2026，hs300 成员变更 226 名，zz500 451 名，sz50 38 名 |
| B. 退市名价格（baostock 历史价格） | ✅ GO | 乐视网/暴风集团/康得新/*ST济堂 各 487-731 行，全可达 |
| C. 规模可行 | ⚠️ 慢但可行 | 800名×约14s/名=~187min（实际用 F002/F003 批量拉取完成） |

`feasibility_probe_local.json` 实测证据，baostock Gate A+B 全 GO。✅

---

## §3 F002 宇宙构建真证据

```json
{
  "rebalance_count": 29,
  "current_member_count": 800,
  "union_ever_members": 1310,
  "non_current_members": 536
}
```

**对照构造一致性验证：**

```python
# control universe: all_same_members=True (单一幸存集应用到所有日期)
control: Dates=29, rows=23200, all_same_members=True  ← 幸存者偏差构造正确
# PIT universe: all_same_members=False (真实 PIT 成员变化)
pit: Dates=29, rows=23199, all_same_members=False, union=1310  ← PIT 真实变动
# 仅在 PIT 不在对照（退市+历史成员）: 536 名
```

调仓日早期（2019-03）non_current_fraction = 46.5%（近半数退市或已出指数），验证 PIT 的真实偏差纠正力度。✅

---

## §4 退市估值 null-result（engine ffill 行为）

`_wide()` 对退市名使用 `ffill` 冻结最后成交价（非归零）：

```python
# engine.py:168
.ffill()   # 停牌/退市名保持最后已知价，不污染 NaN
```

**Generator 实验验证（已入 session_notes）：** 强制退市名末 bar 后置零 vs ffill，两种处理 PIT 回测结果**完全一致**（full_cagr=0.1312，ending≈243406，Δ≈0）→ 退市估值口径对结论零影响。

`+26.6pp 幸存者偏差为下界`（43/52 *ST 末价冻结略低估真实亏损）。✅

---

## §5 诚实边界（spec §3 §5 全部已入 committed .md）

来自 `docs/test-reports/B070-survivorship-comparison.md`（已 commit b56d8e9）：

1. **因子仅 pure_momentum**：退市名无免费 quality 基本面（baostock 历史 query_profit 对退市名数据缺）→ 2 因子版需 follow-on。momentum 是主驱动（B068 Q1 确认），结论方向不变。

2. **去偏仅限指数 band（HS300∪ZZ500∪SZ50）**：无 zz1000/zz800 → 退市微小盘仍缺 = 残余偏差，真实高估下界可能 > +26.6pp。

3. **OOS Sharpe > IS Sharpe（0.93 > 0.39）是窗口落位假象**：70/30 split 将 2024Q4 「924」反弹全放入 OOS 窗口，非稳健性证据。OOS 正收益=边际为正，非可配资证据。

4. **exit_count=0 结构性**：momentum_decay 无显式离场规则，退市/动量衰减名通过跌出 top-N 由 no-trade-band 调仓卖出（非 bug）。

---

## §6 L1 门禁全通

| 测试集 | 结果 |
|--------|------|
| `trade/` pytest（含 B070 60 项） | **983 passed** |
| workbench backend safety + unit | **214 passed, 15 skipped** |
| B070 专项 unit（60 项） | **60 passed** |
| B069 守门（test_live_producer_keeps_equal_weighting_b069） | ✅ PASSED |

```
# trade/ (983)
983 passed in 139.11s

# backend safety + precompute + cn_universe (214)
214 passed, 15 skipped in 2.04s

# B070 unit (60)
60 passed in 0.31s
  test_survives_when_pit_oos_positive_cagr_and_sharpe   PASSED
  test_collapses_when_pit_oos_cagr_nonpositive          PASSED
  test_build_current_control_applies_today_members_to_all_dates  PASSED
  test_delisted_fraction                                PASSED
  (+ 56 more)
```

---

## §7 零回归

B070 改动范围（仅研究/脚本层）：
- `scripts/research/b070_*.py` — 研究脚本（非生产路径）
- `tests/unit/test_b070_*.py` — 研究单元测试
- `docs/` — 文档
- `workbench/backend/workbench_api/data_refresh/cn_universe.py` — 仅 docstring 改动

**生产代码零改动**（B067/B066/Master 不破）；`allow_sina_fallback` 默认 False，B067 daily refresh 字节级不变。✅

---

## §8 VM HEAD≡Prod

```bash
GET https://trade.guangai.ai/api/health
{
  "status": "ok",
  "version": "e91b669396a21a1624eabef0e1f819d4a3c40ea3",
  "db_connectivity": "ok",
  "uptime_seconds": 2615.715
}
```

`e91b669` = B070 F003（幸存者偏差量化），VM 已部署。✅

---

## §9 研究判定（F004 spec §3 结论分支）

**「GO + 策略仍成立」分支：**

去偏后 PIT OOS CAGR 28.4% / Sharpe 0.93（均为正）→ A股 进攻策略**首次 survivorship-free 验证通过**。

重要诚实约束（不动）：
- OOS 红卡（B066: validated=False, oos_result=negative）续挂 → B067 advisory surface 持续展示
- 仍研究态，不可配资
- 去偏后正收益≠可配资（OOS 窗口含 2024Q4 顺风高估）
- 质量因子去偏待 baostock 基本面管线（follow-on）

---

## §10 签收结论

**B070 F001-F003 全部特性签收：PASS（研究态：SURVIVES_DEBIASING）**

| Feature | 内容 | 结论 |
|---------|------|------|
| F001 | §23 三关口 feasibility = GO（免费 baostock 能去幸存者偏差） | ✅ |
| F002 | PIT 宇宙真建（29 季度×800，1310 union，536 历史名含退市） | ✅ |
| F003 | 去偏 vs 偏差 OOS 对比 + 研究判定（SURVIVES_DEBIASING，偏差+26.6pp） | ✅ |

**→ status: verifying → done**
