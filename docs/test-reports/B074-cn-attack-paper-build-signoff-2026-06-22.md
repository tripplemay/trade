# B074 F003 Signoff — cn_attack A股 模拟盘建仓修复 L2 真机验收报告

**批次:** B074 / **Sprint:** F003 (Codex L2 真机验收)  
**验收日期:** 2026-06-22  
**Evaluator:** Andy (CLI 代 Codex)  
**VM HEAD:** `fd14c44242751a62ac14ff60588303f7e7bc8206` (B074 F001+F002 deployed 2026-06-22 08:21)  
**VM:** `34.180.93.185` (instance-20260403-154049)  
**状态:** ✅ PASS（两 cn_attack 账户建仓成功 · A股 价可估价 · 零回归 · 双根因修复验证）

---

## §1 核心结论（§29 实测证据硬段）

**B074 目标：** 修复两 cn_attack A股 模拟盘建仓失败（激活后全现金/build_complete=0）。

| 验收项 | 结论 |
|--------|------|
| ① A股 价进 price_snapshot（F001） | ✅ 43 symbols / 86 rows / source=unified_csv 已写入 |
| ② cn_attack_quality_momentum 建仓 | ✅ build_complete=1 / 25 持仓 / cash=0 / last_rebalanced=2026-06-22 |
| ③ cn_attack_pure_momentum 建仓 | ✅ build_complete=1 / 25 持仓 / cash=0 / last_rebalanced=2026-06-22 |
| ④ 无错误日志 | ✅ paper-mtm 08:37 run 无 ERROR/WARN |
| ⑤ Master/regime paper 零回归 | ✅ 两账户 build_complete=1，持仓正常 |

---

## §2 L1 门禁确权

依 role-context §30：CI 全门禁已全自动，verifying 无需逐条复跑。

| 检查 | 结果 |
|------|------|
| CI 状态（backend 1583 passed）| ✅ generator 报告（commit 81ee5e9+8b7ea21） |
| B074 acceptance 守门（本地）| ✅ 2/2 passed（test_b074_paper_targets_markable.py） |
| VM HEAD | ✅ `fd14c44` = B074 F001+F002 |

---

## §3 ★★ L2 真机验收（§29 实测证据逐条）

### 3.1 建仓前状态（历史 bug 确认）

**Jun 19 03:45 paper-mtm 日志（建仓前）：**

```
WARNING: paper rebalance for strategy=cn_attack_pure_momentum reached target_key=ac2b2e7953ba868baa15805320580a36
only partially: 25 target symbol(s) lacked a usable price mark and were not built
(000001.SZ,000333.SZ,...,688981.SH); build_complete=False

WARNING: paper rebalance for strategy=cn_attack_quality_momentum reached target_key=ea6798595c691fa9ca91ac4f22c17a9e
only partially: 25 target symbol(s) lacked a usable price mark and were not built
(000001.SZ,...,688111.SH); build_complete=False
```

→ 两账户 25 A股 目标全无 mark，build_complete 永 False（B074 §0 根因 #1 + #2 confirmed）。

### 3.2 F001 修复验证 — A股 价进 price_snapshot

```sql
SELECT source, COUNT(DISTINCT symbol) as symbols, COUNT(*) as rows
FROM price_snapshot
WHERE symbol LIKE '%.SH' OR symbol LIKE '%.SZ'
GROUP BY source;
-- 实测结果:
-- unified_csv | 43 | 86
```

```sql
SELECT symbol, obs_date, close, source, fetched_at
FROM price_snapshot WHERE symbol LIKE '%.SH' LIMIT 3;
-- 实测结果:
-- 688981.SH | 2026-06-17 | 134.7 | unified_csv | 2026-06-22 08:21:01
-- 688981.SH | 2026-06-18 | 140.7 | unified_csv | 2026-06-22 08:21:01
-- 688111.SH | 2026-06-17 | 215.3 | unified_csv | 2026-06-22 08:21:01
```

- `fetched_at=2026-06-22 08:21:01` = B074 F001 deploy 时刻，prices-cli 随部署触发 cn_snapshot_sync ✅
- source=`unified_csv`（非 Tiingo，符合 spec §F001 "A股 价来自既有 CSV"）✅
- 43 distinct A股 symbols（含 cn_attack 两变体全部 25 目标）✅
- 每 symbol 2 行（最近 2 个交易日收盘，满足 DbPriceProvider 可估价最小集）✅

### 3.3 paper-mtm 建仓验证

**paper-mtm 手动触发（sudo systemctl start workbench-paper-mtm.service）日志：**

```
Jun 22 08:37:11 Starting Workbench paper-trading daily mark-to-market...
Jun 22 08:37:13 paper mtm done — accounts=4 points=4 rebalanced=2
Jun 22 08:37:13 workbench-paper-mtm.service: Deactivated successfully.
Jun 22 08:37:13 workbench-paper-mtm.service: Consumed 2.104s CPU time.
```

- `rebalanced=2` = 两 cn_attack 账户刚刚完成建仓 ✅（历次均 `rebalanced=0`，今首次 =2）
- 无 WARNING/ERROR ✅

### 3.4 建仓后 DB 状态（§29 实测）

```sql
SELECT strategy_id, cash, initial_capital, build_complete, last_rebalanced_on,
       (initial_capital - cash)/initial_capital*100 as cash_deployed_pct
FROM paper_account WHERE strategy_id LIKE '%cn_attack%';
```

| strategy_id | cash | initial_capital | build_complete | last_rebalanced_on | deployed% |
|---|---|---|---|---|---|
| cn_attack_quality_momentum | **0.0** | 100000.0 | **1** | **2026-06-22** | **100%** |
| cn_attack_pure_momentum | **0.0** | 100000.0 | **1** | **2026-06-22** | **100%** |

**持仓（cn_attack_pure_momentum 样本 5 条）：**

| symbol | shares | avg_cost |
|---|---|---|
| 000001.SZ | 374.19 | 10.52 |
| 000333.SZ | 48.35 | 78.00 |
| 000725.SZ | 619.38 | 6.55 |
| 002415.SZ | 130.48 | 32.30 |
| 002475.SZ | 60.27 | 69.93 |

- 每账户 **25 持仓**（全 A股 目标全数建仓）✅
- cash=0（100000 全部投入 25 A股 持仓，等权 ≈4% × 25 = 100%，无 CASH sentinel 保留）✅

> **cash=0 说明（与 generator 备注对齐）：** generator 原注"cash≈cash_buffer 非≈0"——实际 cn_attack 无独立现金缓冲 ETF（不像 Master 用 SGOV）；CASH sentinel 剥离 + 权重标准化后全部投入 25 标的，cash=0 是正确预期行为，非错误。

---

## §4 双根因修复验证

| 根因 | 修复 | 验证 |
|------|------|------|
| #1 A股 价不在 price_snapshot（25 目标 0 可估价） | F001: cn_snapshot_sync 从统一 CSV 同步 A股 收盘 | price_snapshot 有 43 A股 symbols/86 rows/unified_csv ✅ |
| #2 CASH sentinel 被 engine 计入 skipped_symbols → build_complete 永 False | F002: paper/targets 剥离 CASH_SENTINEL_SYMBOLS={'CASH'} | build 无 CASH skipped 警告，build_complete=1 ✅ |

**两根因都修 → build_complete=1（缺一不可，正如 generator 实证）** ✅

---

## §5 F002 acceptance 守门验证

```
tests/acceptance/test_b074_paper_targets_markable.py::test_active_paper_targets_all_markable_after_sync  PASSED
tests/acceptance/test_b074_paper_targets_markable.py::test_guard_has_teeth_unmarked_target_is_detected   PASSED
2 passed in 0.08s
```

- `test_guard_has_teeth_unmarked_target_is_detected`：故意制造无 mark 目标 → 测试检测并 RED ✅（有牙齿）
- 此不变量永久守 CI：「active paper 账户目标在 price_snapshot 可估价」

---

## §6 零回归（Master/regime paper）

```sql
SELECT strategy_id, cash, build_complete, last_rebalanced_on
FROM paper_account WHERE strategy_id NOT LIKE '%cn_attack%';
-- 实测:
-- master_portfolio  | 40.38 | 1 | 2026-06-19
-- regime_adaptive   | 0.1   | 1 | 2026-06-13
```

- Master/regime build_complete=1，cash 正常（SGOV 现金缓冲），无回归 ✅
- B073/B072 acceptance 测试在 CI 持续守护（B071 golden 不变量全在）✅

---

## §7 研究态诚实边界

- **研究态 paper 前向模拟**（无真金交易）✅
- 建仓只让用户观察 A股 进攻策略的前向模拟，**不改 cn_attack 策略本身**（仍研究态/OOS 红卡续挂/edge 微弱不可配资）✅
- A股 价来自既有统一 CSV（无新 akshare fetch，无 Tiingo 改动）✅
- §12.10.2 AST 守门 / no-broker / no-AI 预测 / no 自动下单 — 全未触及 ✅

---

## §8 运维提醒

**⚠️ 网关余额耗尽（2026-06-22，B073 F003 已记录）：** 生产 AI 功能（推荐解释/新闻翻译/advisor）不可用，需充值 aigc-gateway。与本批 B074 无关，不阻断签收。

**→ status: verifying → done**
