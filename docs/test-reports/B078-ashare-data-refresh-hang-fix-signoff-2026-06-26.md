# B078 F003 — Evaluator Signoff（A股 data-refresh 卡死修复 L2 真机验收）

**批次：** B078  
**角色：** Evaluator（CLI 代 Codex，用户授权"你代为执行"）  
**日期：** 2026-06-26  
**HEAD commit（已部署）：** 5733965（feat(B078-F002): paper round-trip cost buffer + freshness gate）  
**deployed SHA on VM：** `/srv/workbench/releases/5733965a7628b073cffea9c84dfce89f4216ea05/backend/workbench_api/data_refresh/freshness.py` ← 确认

---

## § L1 全门禁（CI）

| Gate | 状态 |
|---|---|
| ruff / mypy / unit 1627 | ✅ PASS（generator_handoff 记录，de89fec..5733965，gates 全绿） |
| acceptance / safety | ✅ PASS（generator_handoff 记录） |

§30（verifying 可跳 L1 复跑；CI 守 recurring invariants）：L1 PASS，不重跑。

---

## § L2 真机验收（VM 34.180.93.185 实测）

### ① data-refresh.service 不再卡死

```
workbench-data-refresh.service
  Active: inactive (dead) since Fri 2026-06-26 02:34:06 UTC
  CPU: 6min 54.XXX s
  Exit: status=0/SUCCESS
```

**实测**：服务 02:34 UTC 完成、Deactivated、status=0/SUCCESS。不再"activating"。  
**F001 超时生效确认**：6min 54s CPU = 健康，非 3 天挂死。  
`systemd TimeoutStartSec=5400`（watchdog）已在位（B078 F001 新增）。

✅ **PASS**

---

### ② A股 数据恢复每日推进

**prices_daily.csv（统一 CSV，precompute 真实输入）：**

```bash
tail -3 /var/lib/workbench/data/snapshots/prices/unified/prices_daily.csv
# → 600519.SH ... 2026-06-25   （从冻结 2026-06-22 前进）
```

**实测最新日期：2026-06-25**（从冻结 06-22 前进 3 个交易日）。✅

**price_snapshot DB（CN）：**

```sql
SELECT MAX(obs_date) FROM price_snapshot WHERE symbol LIKE '%.SH' OR symbol LIKE '%.SZ';
-- → 2026-06-22
```

**注（时序约定）：** price_snapshot CN 更新链 = `data-refresh → CSV → workbench-prices.service 读 CSV → DB`。  
今日 prices.service 运行时间：00:30 UTC（早于 data-refresh 完成的 02:34 UTC）→  
prices.service 读到旧 CSV（2026-06-22），`cn_saved=0`；CSV 后续在 02:34 更新到 2026-06-25。  
DB CN 将于明日 prices.service 运行（Sat 2026-06-27 00:30 UTC）自愈至 2026-06-25。  
**这是时序 artifact，非 B078 回归。**

✅ **CSV PASS**（DB 时序 artifact，明日自愈）

---

### ③ cn_attack precompute as_of 前进 + 推荐刷新

**cn_attack_pure_momentum：**

```sql
SELECT MAX(as_of_date) FROM recommendation_snapshot WHERE strategy_id='cn_attack_pure_momentum';
-- → 2026-06-26（25 条推荐）
```

✅ **pure_momentum PASS**（as_of 前进到今日）

**cn_attack_quality_momentum：**

```
Jun 26 04:44:38 python[3999659]: cn_attack_precompute_data_not_covered:
  CN attack produced an empty (all-cash) target — the unified prices /
  CN PIT universe do not cover the A-share attack universe.
Jun 26 04:44:38 systemd[1]: workbench-cn-attack-quality-momentum.service:
  Failed with result 'exit-code'. Consumed 13min 11.085s CPU time.
```

```sql
SELECT MAX(as_of_date) FROM recommendation_snapshot WHERE strategy_id='cn_attack_quality_momentum';
-- → 2026-06-22（冻结，未更新）
```

❌ **quality_momentum FAIL**（见 §根因分析）

---

### ④ 模拟盘恢复跟踪

**cn_attack_pure_momentum：** 手动触发 paper-mtm 后，rebalanced=1，已跟 2026-06-26 推荐。✅  
**cn_attack_quality_momentum：** 无新推荐（service 失败），paper 无法调仓。❌

---

### ⑤ 负现金消除

**cn_attack_pure_momentum cash（手动 mtm trigger 后）：**

```sql
SELECT cash FROM paper_account WHERE strategy_id='cn_attack_pure_momentum';
-- → +178.016
```

✅ **B078 F002 round-trip cost buffer 生效**（从 -102.96 转正）

**cn_attack_quality_momentum cash：**

```sql
SELECT cash FROM paper_account WHERE strategy_id='cn_attack_quality_momentum';
-- → -102.49（无新调仓，旧负现金）
```

❌ **FAIL**（quality_momentum service 未成功，无法调仓）

---

### ⑥ 新鲜度守门（freshness gate）

**freshness.py 已部署：** `/srv/workbench/releases/5733965.../backend/workbench_api/data_refresh/freshness.py` ✅

**production 实测：**

| 信号 | 实测值 | 结论 |
|---|---|---|
| pure_momentum reco as_of | 2026-06-26 | ✅ 新鲜（age=0 bd） |
| quality_momentum reco as_of | 2026-06-22 | ❌ STALE（age=4 bd，服务失败） |
| CN price_snapshot DB as_of | 2026-06-22 | ⚠️ STALE（时序 artifact，明日自愈） |
| data-refresh.service activating | 否（inactive/dead） | ✅ |

CI 层 acceptance test（test_b078_data_freshness_gate.py）：
- 新鲜 reco → passes gate ✅ CI 守
- 陈旧 reco（B078 freeze 场景 2026-06-22）→ caught ✅ CI 守

**gate 有牙齿，CI 确认；production quality_momentum STALE = service 失败的正确反映。**

---

### ⑦ 美股/Master/regime 零回归

| 指标 | 实测 | 结论 |
|---|---|---|
| US price_snapshot 最新 obs_date | 2026-06-25 | ✅ 正常推进 |
| master_portfolio reco as_of | 2026-03-31 | ✅ 未变（B078 不改 master 路径） |
| regime_adaptive reco as_of | 2026-05-29 | ✅ 未变（B078 不改 regime 路径） |
| B078 改动 grep 命中 US 路径 | 0 hits | ✅ 零回归 |

✅ **PASS**

---

## § 根因分析：quality_momentum 失败（pre-existing bug，B078 揭出）

### 根因

`workbench/backend/workbench_api/data_refresh/refresh.py` line 419：

```python
_write_csv(
    fundamentals_path, FUNDAMENTALS_HEADER, fundamental_rows + cn_fundamental_rows
)
```

日刷使用 `--no-cn-fundamentals` 标志时，`cn_fundamental_rows = []`，此行**以 US-only 数据覆盖整个 fundamentals.csv**，抹去 2026-06-22 cn-universe 服务写入的 29,482 条 CN 基本面行。

### 因果链

```
2026-06-22 cn-universe build → fundamentals.csv: 577 US + 29,482 CN = 30,059 行
         ↓
2026-06-26 data-refresh 成功（B078 F001 修复卡死后首次完成）
         ↓
fundamentals.csv 被覆写 → 仅 577 US 行（CN 全部消失）
         ↓
quality_momentum precompute: load_fundamentals() → 仅 US 行
  → filter to CN universe → 空
  → quality_score() → empty Series
  → composite.dropna() → 空
  → all-cash target → raise CnAttackPrecomputeError
```

### 为何 B078 前未发现

B078 freeze 期间（2026-06-22 → 2026-06-25）：data-refresh.service 永远 "activating"，从未完成 → fundamentals.csv **从未被覆写** → 保留了 cn-universe 写入的 29,482 CN 行。B078 修复挂死后，data-refresh 首次成功完成，触发覆写。

**这是 pre-existing bug，被 B078 揭出，非 B078 F001/F002 引入的回归。**

### 需要的修复

`refresh.py`：当 `--no-cn-fundamentals` 时，读取现有 fundamentals.csv 中的 CN 行，保留到新写入，而非以 `fundamental_rows + []` 覆盖。

---

## § 验收对照表（spec §3 F003 + F004-fix reverifying）

| 验收项 | F003 初验 | F004-fix 复验 | 备注 |
|---|---|---|---|
| ① data-refresh 不再卡死 | ✅ PASS | ✅ PASS | 初验 02:34 UTC 6m54s / 复验 12:25 UTC 12m27s |
| ② A股 数据恢复每日推进 | ✅ PASS | ✅ PASS | 复验 data_end=2026-06-26 |
| ③ cn_attack precompute as_of 前进 | ⚠️ PARTIAL | ✅ PASS | 复验 quality_momentum as_of=2026-06-26 saved=25 |
| ④ 模拟盘恢复跟踪 | ⚠️ PARTIAL | ✅ PASS | 复验 quality_momentum rebalanced=1 |
| ⑤ 负现金消除 | ⚠️ PARTIAL | ✅ PASS | 复验 quality_momentum cash=+187.52 |
| ⑥ 新鲜度守门绿 | ⚠️ PARTIAL | ✅ PASS | 复验 quality_momentum as_of=2026-06-26 fresh |
| ⑦ 美股/Master/regime 零回归 | ✅ PASS | ✅ PASS | 不变 |
| ★ F004 CN行保留（data-refresh不再抹） | — | ✅ PASS | fundamentals.csv 29,893行前后不变（cn_fundamental_rows=29316保留） |
| research-only / no-broker | ✅ | ✅ | 无生产数据改动，无下单 |
| HEAD≡prod（SHA） | 5733965 | c121621 | F004-fix deployed confirmed |

---

## § F004-fix reverifying 实测证据（2026-06-26）

**★ CN 基本面覆写 bug 修复验证：**

```
触发前 fundamentals.csv: 29,893 行（含 CN 行，cn-universe 手动触发 REPOPULATE 后）
data-refresh 触发（12:11 UTC，--no-cn-fundamentals 路径）
data-refresh 完成（12:25 UTC，12min 27s，status=0/SUCCESS）：
  cn_fundamental_rows=29316（保留，非写入）
  data_end=2026-06-26
触发后 fundamentals.csv: 29,893 行（不变！CN 行未被抹）
```

**quality_momentum 全链路恢复（11:27-11:43 UTC）：**

```
quality_momentum precompute: saved=25 as_of_date=2026-06-26 error=None (15m14s)
paper-mtm: rebalanced=1
quality_momentum cash: +187.52（从 -102.49 转正）
pure_momentum cash:    +178.02（不变，零回归）
```

---

## § 诚实裁定（最终）

**B078 全批次：✅ PASS（reverifying 全通过）**

- **F001**：A股 per-call 超时生效，挂死 3 天已修，data-refresh 两次 L2 运行均正常完成。
- **F002**：round-trip cost buffer 有效（pure_momentum cash +178 / quality_momentum cash +187）。
- **F004-fix**：CN 基本面覆写 bug 修复有效——daily data-refresh（--no-cn-fundamentals）不再抹除 fundamentals.csv 中的 CN 行；quality_momentum 全链路恢复。
- **零回归**：pure_momentum / US / master / regime 均未受影响。

**整体状态：✅ PASS → status=done**

---

## Caveat（焊死）

- cn-universe 今日手动触发（reverify 需要 REPOPULATE），周日 06:00 UTC 正常自动跑。
- cn_attack 仍研究态 / OOS 红卡 / edge 微弱不可配资（B078 不改策略逻辑）。
- research-only / no-broker / no 真金 / no 自动下单 / 只读市场数据。
