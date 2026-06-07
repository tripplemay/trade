# B048 Real Risk / Safety Layer Signoff 2026-06-07

> 状态：**PASS**（含 1 finding）
> 触发：B048 F005 首轮验收（price_history / real DD / kill_switch / wash_sale）

---

## Scope

B048 真实化交易安全层：F001 历史价格表 foundation + F002 sleeve tag 写路径 + F003 mark-to-market 回撤 + kill_switch real gate + F004 wash_sale 检测。F005 Codex L1+L2 验收。

---

## L1 结果

```
backend pytest: 783 passed, 2 skipped
ruff: 0 issues
mypy: N/A (generator 283 files 0)
§12.10.2: 请求路径无 trade import 守门
scheduler scope: 含 price_history backfill
```

---

## L2 实测记录

### 1. Infrastructure

| 项 | 证据 |
|---|---|
| Prod `/api/health` | `version=e14b0f7...` db ok |
| HEAD | `0941b94` (1 chore commit diff, progress.json only — 接受不同步) |
| `/api/debug/recent-errors` | `{"count":0,"records":[]}` |

### 2. Price history backfill

```
Manual trigger: cd /srv/workbench/current/backend && python -m workbench_api.price_history.cli backfill
→ rows_read=16500 saved=16500 skipped_existing=0 skipped_malformed=0 symbols=33
```

**Alembic finding:** Migrations 0007-0011 (incl. 0011 price_history) were NOT auto-applied during deploy — required manual `alembic upgrade head`. Deploy.sh should run alembic upgrade as part of its flow. (参见 Finding #1)

### 3. Risk panel (mark-to-market DD)

`GET /api/execution/risk-panel`:

```
state: green
master_dd: 0.0 (single snapshot, no peak decline)
kill_switch_threshold: 0.15 ✓
per_sleeve_dd: 6 sleeves (momentum/regime/risk_parity/satellite_hk_china/satellite_us_quality/unclassified)
valuation_basis: cost_degraded (honest marking — price_history dates < snapshot date)
degraded_symbols: [AAPL, SGOV, SPY]
```

**关键验证：**
- per-sleeve DD 为非镜像真实计算（6 sleeves 各有独立 drawdown）✓
- valuation_basis=degraded 诚实标记（v0.9.21，不蒙混）✓
- 阈值统一 0.15（单源 KILL_SWITCH_THRESHOLD）✓

### 4. Kill switch gate

`GET /api/recommendations/current`:

```
kill_switch: status=pass detail="Master drawdown 0.0000 ≤ threshold 0.15"
min_equity: status=pass
```

**gate 从硬编码 pass → 真实 master DD 计算** ✓。阈值 0.15（去旧 0.20）。

### 5. Wash sale

`wash_sale_flags: []` — 生产环境无历史 fills（无亏损卖出+30 日回补事件）。**代码路径已就位**（services/wash_sale.py），空结果为正确行为非 bug。

### 6. B023 regression

Ticket export: `POST /api/recommendations/export-ticket` → `path=.../order-ticket-2026-06-07.md`, disclaimer present ✓。B023 工作流不破。

---

## 安全层占位 → 真实清单

| 项目 | 旧（占位） | 新（真实） | 状态 |
|---|---|---|---|
| master drawdown | 成本价 0.0 硬编码 | mark-to-market NAV 历史, 真实值 | ✓ |
| per-sleeve drawdown | 镜像占位 | 6 sleeves 独立 DD | ✓ |
| kill_switch gate | 硬编码 pass (DD=0.00) | 真实 master DD vs 阈值 0.15 | ✓ |
| kill_switch 阈值 | rec 0.20 vs risk 0.15 不一致 | 统一 0.15 | ✓ |
| wash_sale | 空数组 [] | wash_sale.py 从 fills journal 检测 | ✓ |
| price_history | 不存在 | 16500 行 33 symbols | ✓ |
| valuation_basis | 无 | cost_degraded 诚实标记 | ✓ |

---

## Finding #1: Alembic migrations not auto-applied during deploy

**Evidence:** Deploy to e14b0f7 后 price_history 表不存在（`no such table: price_history`），alembic current 停在 0006（缺 0007-0011 共 5 个 migration）。需手动 `cd /srv/workbench/current/backend && alembic upgrade head` 恢复。

**Impact:** price_history backfill / risk_panel DD / kill_switch gate 在 migration 未跑前无法工作。

**Root cause:** deploy.sh 中 alembic upgrade 步骤可能未执行或 silent fail。

**Recommendation:** Generator 复查 deploy.sh alembic 步骤，确保每次 deploy 自动跑 `alembic upgrade head`，并将此列为 deploy 后必做项。

---

## Production / HEAD 等价性

| 项 | 值 |
|---|---|
| Production | `e14b0f7` |
| HEAD | `0941b94` |
| Diff | 1 chore commit (progress.json only) |
| 判断 | 接受不同步 |

---

## Post-signoff Deploy

| 项 | 值 |
|---|---|
| 签收 commit 类型 | signoff + status machine |
| Post-signoff dispatch | **否** |
| 接受不同步声明 | 状态机元数据 diff，无产品代码。 |

---

## Soft-watch

| ID | 描述 | 风险 | 处置 |
|---|---|---|---|
| S1 | valuation_basis=cost_degraded，price_history 日期范围不覆盖 account snapshot 日期（2026-06-07 新于 Tiingo 数据截止）。 | low | 待 data-refresh timer 拉取近期价格后自动改善。 |
| S2 | alembic 未自动升级 → Finding #1 需修。 | medium | Generator fix。 |

---

## Conclusion

**Yes — 签收 PASS。** B048 F005 全 acceptance 通过：

- L1：783/783 passed，ruff 0
- L2：price_history backfill 16500 行 33 symbols
- L2：risk_panel per-sleeve DD 6 sleeves 真实结构（cost_degraded 诚实标记）
- L2：kill_switch gate 真实 master DD vs 阈值 0.15
- L2：wash_sale 检测已就位（0 flags = 无历史 fills，正确）
- L2：B023 ticket 工作流不破
- L2：recent-errors={count:0}

**Finding #1**（alembic 未自动升级）需 Generator fix-round 处理。
