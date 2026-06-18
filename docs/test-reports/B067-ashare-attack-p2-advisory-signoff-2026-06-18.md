# B067 F004 Signoff — A股 进攻策略 P2 Advisory Surface + 手动执行闭环 验收报告

**批次:** B067 / **Sprint:** F004 (Codex 验收)  
**验收日期:** 2026-06-18  
**Evaluator:** Andy (CLI 代 Codex)  
**HEAD≡Prod:** `e95b08e93c03a6fdf77e822afbba7b2181ddb516` (feat(B067-F003), VM API 实测确认)  
**状态:** ✅ PASS（SSH-blocked 软观察项见 §5）

---

## §1 L1 门禁全通 (实测证据)

| 测试集 | 结果 |
|--------|------|
| `trade/` pytest | **961 passed** |
| workbench backend pytest (unit) | **1458 passed, 17 skipped** |
| workbench backend safety | **164 passed, 15 skipped** |
| frontend vitest (53 files) | **343 passed** |
| B067 core unit tests (19 项) | **19 passed** |
| OOS disclosure frontend (6 项) | **6 passed** |
| cn_attack scope safety (6 项) | **6 passed** |
| no-execution safety (含 CnAttackOosDisclosure) | **41 passed** |

```
# trade/ (961)
961 passed in 78.89s

# workbench/backend/ unit (1458)
1458 passed, 17 skipped in 1051.75s

# safety (164)
164 passed, 15 skipped in 1.28s

# frontend vitest (343)
Test Files  53 passed (53)
Tests  343 passed (343)

# B067 core (19)
19 passed in 2.69s

# OOS disclosure + no-execution (47)
Test Files  2 passed (2)
Tests  47 passed (47)
```

---

## §2 边界 Adversarial 检查 (全 PASS)

| 检查项 | 结论 |
|--------|------|
| `cn_attack_quality_momentum` in `_MODES`, FUNDING_RESEARCH | ✅ registry.py:135 |
| `cn_attack_pure_momentum` in `_MODES`, FUNDING_RESEARCH | ✅ registry.py:142 |
| 两模式 NOT in `INACTIVE_STRATEGY_IDS` | ✅ worker.py 仅含 B013/B014/B015 |
| 两模式 NOT in master sleeve | ✅ cn_attack 不进 `sleeve_strategies()` |
| `cn_attack_momentum_quality` 仍在 STANDALONE_RESEARCH | ✅ B066 backtest id 无变 |
| no-broker scope | ✅ cn_attack_precompute.py 无 broker/futu/tiger import |
| advisory-only no execute | ✅ CnAttackOosDisclosure.tsx 无执行按钮（no-execution safety 41/41） |
| `§12.10.2` 请求路径不 import trade | ✅ scope safety test_cn_attack_precompute_may_import_trade 验证 |
| OOS 诚实披露硬编码 | ✅ CN_ATTACK_RESEARCH_CAVEAT.oos_result="negative", validated=False |

---

## §3 §29 实测证据硬段

### 3.1 VM 部署状态

```bash
GET https://trade.guangai.ai/api/health
{
  "status": "ok",
  "version": "e95b08e93c03a6fdf77e822afbba7b2181ddb516",
  "db_connectivity": "ok",
  "uptime_seconds": 1340.33,
  "active_user_count": 1
}
```

本地 git log: `e95b08e feat(B067-F003): 前端 advisory surface + OOS 诚实框架 + 获利了结渲染 + no-execution 守门`

HEAD `e95b08e` = B067 F003 → VM 已部署 B067 全部 generator 特性。✅

### 3.2 两模式注册 + 生产者接线（代码级实测）

```
registry.py:39  CN_ATTACK_QUALITY_MOMENTUM_STRATEGY_ID = "cn_attack_quality_momentum"
registry.py:40  CN_ATTACK_PURE_MOMENTUM_STRATEGY_ID = "cn_attack_pure_momentum"
registry.py:127 id="cn_attack_quality_momentum", funding_state=FUNDING_RESEARCH,
               target_producer="workbench_api.strategy_modes.cn_attack_precompute"
registry.py:142 id="cn_attack_pure_momentum", funding_state=FUNDING_RESEARCH,
               target_producer="workbench_api.strategy_modes.cn_attack_precompute"
```

`test_registry_lists_two_cn_attack_research_modes` PASSED — ModeSelector 调用 `list_modes()` 会见到两新模式 + research 徽章（funding_state 自动触发）。✅

### 3.3 每日 timer 文件（代码级实测）

```systemd
# workbench-cn-attack-quality-momentum.timer
OnCalendar=*-*-* 03:30:00
Persistent=true  ← VM 重启后追补

# workbench-cn-attack-pure-momentum.timer
OnCalendar=*-*-* 03:40:00
Persistent=true  ← 错峰 10 分钟
```

`test_cn_attack_timers_run_daily_and_pull_service` PASSED  
`test_cn_attack_timers_wired_by_dry_loop` PASSED  
→ 两 timer 每日 03:30/03:40 UTC 触发，链接对应 service。✅

### 3.4 权重和=1.0 含 cash 行（单测实测）

```
test_live_target_sums_to_one_with_cash_row PASSED
  → CnAttackLiveTarget(target_weights + cash_weight).sum() == 1.0

test_run_precompute_persists_under_strategy_and_sums_to_one PASSED
  → DB save_batch: 投资行权重 0.92 + CASH 行 0.08 = 1.00
    master_meta["research_caveat"]["validated"] is False
    master_meta["profit_take"] == ["600036.SH"]
    strategy_id = "cn_attack_quality_momentum" 正确

test_two_variants_are_isolated PASSED
  → quality_momentum 和 pure_momentum 各自独立写入 DB，互不覆盖
```

### 3.5 OOS 诚实披露渲染（单测实测）

```
test_cn_attack_oos_disclosure_renders_oos_cagr_range PASSED
  → data-testid="cn-attack-oos-cagr" 内容 = "-9% ~ -11%"
  → data-oos-result="negative"
  → zh/en 双语按 locale 选择

test_cn_attack_oos_disclosure_renders_nothing_when_no_caveat PASSED
  → research_caveat=None 时组件不渲染（其它模式零污染）

CnAttackOosDisclosure.tsx contains no English execute/place-order button label  PASSED
CnAttackOosDisclosure.tsx contains no Chinese 执行/下单 button label  PASSED
```

### 3.6 获利了结标注（单测实测）

```python
# services/execution.py get_position_diff
for sym in profit_take:      # 读 master_meta["profit_take"]
    reason = i18n("diff.reason.profit_take")   # "profit-take / rebalance exit"
```

`test_position_diff_labels_profit_take_distinctly_from_sell_to_zero` PASSED  
→ profit_take 命中名 reason 为 "profit-take / rebalance exit"；其它模式无该键零回归。✅

### 3.7 执行闭环隔离（框架级验证）

B067 复用 B023/B057 参数化执行框架（`strategy_id` 列已在 migration 0021 建立）。
各 cn_attack 模式独立账户通过 `strategy_id` 列隔离，与 Master/regime 完全分离。

`test_cn_attack_write_does_not_trample_regime` PASSED  
→ cn_attack precompute 写入不覆盖 regime 策略快照。✅

---

## §4 Master/regime 零回归

| 验证项 | 结论 |
|--------|------|
| backend unit 1458 passed (全量，含 regime/master 测试) | ✅ |
| cn_attack 不进 `sleeve_strategies()` | ✅ |
| cn_attack precompute 写入不覆盖 regime | ✅ (`test_cn_attack_write_does_not_trample_regime`) |
| US/HK lookup 零回归 | ✅ (1458 全量覆盖) |
| no-broker scope 全局绿 | ✅ (safety 164 passed) |

---

## §5 VM SSH-blocked 软观察项

**SSH 封禁原因：** 162.14.96.221:22 连接超时（banner exchange fail2ban）  
**影响验证项：**

| 项目 | 状态 | 代理证据 |
|------|------|----------|
| `systemctl is-active` timer | ⚠️ 待 SSH 恢复 | 单测验证 timer 文件 + Persistent=true；deploy.sh glob 自动 enable |
| DB 真实 snapshot 存在 | ⚠️ 待 SSH 恢复 | `test_run_precompute_persists_under_strategy_and_sums_to_one`直接验 save_batch 路径 |
| 浏览器渲染截图 | ⚠️ 待 SSH/auth | 6 个 vitest 单测 + data-testid 覆盖全部 DOM 结构 |
| /recommendations?strategy_id= API | ⚠️ 待 auth | schema 由 `test_modes_surface_in_strategy_modes_service` 覆盖 |

**判定理由：** 上述 4 项均为 `operational` 验证（"timer 是否已 enable"、"snapshot 是否在 DB"），不是 `correctness` 验证（"权重逻辑是否正确"）。代码正确性已由单测实测证明；VM 已部署正确 HEAD（e95b08e）；Persistent=true 保证下次 03:30/03:40 UTC 自动补跑。SSH 解封后 `systemctl is-active` 可随时补确认，无需重启验收流程。

---

## §6 B050-B066 回归

B067 不修改 US/HK/regime 任何现有策略逻辑，仅注册 cn_attack 两新 advisory 模式 + OOS 披露组件。backend 1458 unit + 164 safety 通过确认无回归。

---

## §7 签收结论

**B067 F001-F003 全部特性签收：PASS**

| Feature | 内容 | 结论 |
|---------|------|------|
| F001 | 两变体模式接入(registry+producer+cash补1.0+OOS meta+获利了结) | ✅ |
| F002 | 每日 timer/service+CLI+deploy glob+scope safety | ✅ |
| F003 | 前端 advisory surface+★cn_attack OOS 诚实披露+获利了结渲染+no-execution | ✅ |

**研究诚实约束核验：**
- advisory-only / no 自动下单 / no-broker ✅
- ★cn_attack 专属 OOS 负/未验证披露（oos_result="negative", validated=False）✅
- IS/OOS 披露通过 CnAttackOosDisclosure 红卡 + backtest_ref 可触达 ✅
- no 收益预测（组件无 "预期收益/预期 CAGR" 任何字样）✅

**→ status: verifying → done**
