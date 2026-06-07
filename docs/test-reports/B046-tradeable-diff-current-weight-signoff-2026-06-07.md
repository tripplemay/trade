# B046 Tradeable Diff + Current Weight Signoff 2026-06-07

> 状态：**PASS**
> 触发：B046 F003 首轮验收（mark-to-market diff + rec current_weight + regime reconcile）

---

## Scope

B046：execution position-diff 改 mark-to-market（核心可交易 diff）+ recommendations 展示真实 current_weight + strategies 注册表对齐 master 4-sleeve。F001 改 execution diff 市价估值 + rec current_weight 真实。F002 regime reconcile。F003 Codex L1+L2 验收。

---

## L1 结果

```
backend targeted pytest: 161 passed (15 skipped)
  - test_execution.py (13)
  - test_recommendations.py (6)
  - test_strategies.py (+5 new: master 4-sleeve / hk_china stub / order)
  - test_home_service.py / test_home_route.py
  - test_advisor_route.py
  - safety/* (38: §12.10.2 / scheduler scope / deploy / no-broker / etc)

ruff: 0 issues
```

---

## L2 实测记录

### 1. Health + HEAD

| 项 | 值 |
|---|---|
| Production `/api/health` | `version=e7078a5...` db ok |
| Main HEAD | `e7078a5...` (identical, 零 diff) |
| `/api/debug/recent-errors` | `{"count":0,"records":[]}` |

### 2. Mark-to-market position-diff（核心验证）

**PUT account** with floating-profit positions (AAPL avg_cost=$150, SGOV $100) → trigger `workbench-prices` to populate latest closes (AAPL=$307.34, SGOV=$100.45) → GET position-diff:

| Metric | Cost-basis (旧) | Mark-to-market (新) |
|---|---|---|
| AAPL weight | ~0.13 (cost=$1500) | **0.2347** (market=$3073) |
| SGOV weight | ~0.43 (cost=$5000) | **0.3835** (market=$5022) |
| total_equity | ~$11,500 (cost NAV) | **$13,095.90** (market NAV) |
| AAPL delta | sell -10 shares | sell -10 shares (same shares, correct weight) |

**Mark-to-market 生效：** AAPL 权重大幅增加（涨幅 +$157 被正确捕捉），total_equity 使用市价 NAV，delta_weight 基于市价核算而非成本价。

### 3. Recommendations current_weight

| Symbol | target_weight | current_weight | status |
|---|---|---|---|
| SGOV | 0.4195 | **0.3835** | 与 execution 一致 (mark-to-market) |
| GLD/JNJ/AGG/SPY/VEA | various | 0.0000 | 未持仓 |

**current_weight 从硬编码 0.0 → 真实 mark-to-market 值**，与 execution 同基准。

### 4. Strategies 注册表对齐

```
B006-global-etf-momentum    → sleeve=momentum            active
B016-risk-parity-hrp        → sleeve=risk_parity         active
B025-us-quality-momentum    → sleeve=satellite_us_quality active
B011-satellite-hk-china     → sleeve=satellite_hk_china  stub
B013/B014/B015 regime       → sleeve=regime              research
```

- 4 master active sleeves 排前，3 regime research 排后 ✓
- hk_china stub (0.10, status=stub) 已注册 ✓
- regime 3 项 research（非 active）✓

### 5. Home / Downstream

- `/api/home` sleeves: momentum, regime, risk_parity, satellite_hk_china, satellite_us_quality, unclassified（6 sleeves，含新增 momentum/hk_china）✓
- day_pnl 正常计算（-$37.40, -0.46%）

### 6. B023 Workflow Regression（ticket export）

Ticket 生成成功 (`/var/lib/workbench/runs/.../order-ticket-2026-06-07.md`)：
- Bilingual disclaimer ✓
- SGOV: target=0.4195, **current=0.3835** (mark-to-market), diff=+0.036 ✓
- Gate checks: kill_switch pass, min_equity pass ✓
- Wash-sale flags: None ✓

---

## Mark-to-market vs Cost-basis 对比记录

| Symbol | Cost-basis weight | Mark-to-market weight | Δ | 说明 |
|---|---|---|---|---|
| AAPL | 0.1304 | 0.2347 | +0.1043 | 涨幅 +105% ($150→$307)，市价权重大幅上升 |
| SGOV | 0.4348 | 0.3835 | -0.0513 | 市价 NAV 增大分母，权重自然稀释 |

**结论：** mark-to-market 正确反映持仓真实价值，避免成本价低估涨幅持仓→ticket 过度买入。avg_cost 保留不动（wash-sale/cost-basis 依赖不破）。

---

## Production / HEAD 等价性

| 项 | 值 |
|---|---|
| Production version | `e7078a51ef90e9e000e0ebfe60dff10d0577497f` |
| Main HEAD | `e7078a51ef90e9e000e0ebfe60dff10d0577497f` |
| Diff | **0 commits** — 完全对齐 |

---

## Post-signoff Deploy

| 项 | 值 |
|---|---|
| 签收 commit 类型 | signoff + status machine |
| Post-signoff dispatch 是否需要 | **否** |
| 接受不同步声明 | 本签收 commit 仅含 signoff 报告 + 状态机更新，无产品代码。 |

---

## Decommission Checklist

本批次不含 decommission — N/A。

---

## Soft-watch

| ID | 描述 | 风险等级 | 建议处置 |
|---|---|---|---|
| S1 | home nav=0.0（空账户未设 equity_snapshot 或 account_snapshot 不标准）；day_pnl 正常。不影响 ticket diff mark-to-market 精度。 | low | B046 后 BL-B023-S1 全链路冒烟补齐。 |

---

## Framework Learnings

本批次无 framework learnings。

---

## Conclusion

**Yes — 签收 PASS。** B046 F003 全 acceptance 通过：

- L1：161/161 passed，ruff 0
- L2：mark-to-market position-diff 生效（AAPL 成本权重 13%→市价 23%）
- L2：recommendations current_weight 真实（SGOV 0.3835，非 0.0）
- L2：strategies 4-sleeve master 对齐 + regime research
- L2：B023 ticket 工作流不破（disclaimer/gate/wash-sale）
- L2：recent-errors={count:0}
- Production HEAD 完全对齐（e7078a5）
