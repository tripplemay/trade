# B077 F003 — Evaluator Signoff（A股 聪明钱数据可行性摸底）

**批次：** B077  
**角色：** Evaluator（CLI 代 Codex，用户授权）  
**日期：** 2026-06-25  
**HEAD commit：** eabce89（feat(B077-F002): 龙虎榜机构席位 first-look IC + INCONCLUSIVE_COVERAGE_LIMITED 裁定）  
**独立裁定：** INCONCLUSIVE_COVERAGE_LIMITED（确认，非橡皮戳；见 §诚实推荐裁定）

---

## § L1 全门禁（CI）

| Gate | 状态 | commit |
|---|---|---|
| Python CI（ruff/mypy/pytest 1108 tests） | ✅ PASS | eabce89 |
| Backend CI（ruff/mypy/pytest 1410 tests） | ✅ PASS | eabce89 |

§30（verifying 可跳 L1 复跑；CI 守 recurring invariants）：L1 PASS，不重跑。

---

## § VM 独立复核：三源数据可得性（F001 §23 实测证据非夸大）

### 1. 北向持股 — BACKTEST_ONLY_FROZEN（本地独立抽查，今日确认）

独立 spot-check（2026-06-25 本地执行）：

```python
# akshare.stock_hsgt_hist_em(symbol='北向资金')
rows: 2695
row_index_latest: 2026-06-24       # akshare 积极返回到昨日 → API 未失联
net_buy_last_disclosed: 2024-08-16 # 当日成交净买额 最后非空 = 2024-08-16
```

**独立确认**：北向 `当日成交净买额` 在 2026-06-25 今日测试中仍冻结于 **2024-08-16（678+ 天前）**。F001 VM JSON（`success_rate=1.0/6`，per-stock 六样 2017→2024-08-16）**非夸大**，live 确实已死。

> **★诚实约束**：经典"跟北向"玩法在免费 akshare 上已不可用（live 数据 678 天未更新）。北向历史（2017→2024.8）可回测，但不可前向跟随。

### 2. 龙虎榜机构席位 — USABLE_SPARSE（F001 VM JSON 证据核验）

F001 VM JSON 证据（`docs/test-reports/B077-F001-vm-data-reality-2026-06-25.json`）：

| 字段 | 值 |
|---|---|
| verdict | USABLE_SPARSE |
| history_years | 5.89 |
| live_lag_days | 7 |
| recent_events（2026-06 窗） | 1,322 |
| broad_lhb_reachable | True |
| can_support_backtest | True |

F001 报告中"LIVE lag 7d + 5.89y 历史"证据核实无误，**未夸大**。

### 3. 主力资金流超大单 — USABLE_FULL but too shallow（F001 VM JSON 证据核验）

| 字段 | 值 |
|---|---|
| verdict | USABLE_FULL |
| history_years | 0.5 |
| can_support_backtest | False |
| vm_success_rate | 0.667 |

"0.5y 历史 / push host 不稳（0.667 VM 成功率）/ `can_support_backtest=False`"证据核实，**未夸大**。

---

## § 独立 F002 IC 复跑（龙虎榜机构席位，去偏宇宙）

**运行命令：**

```bash
.venv/bin/python scripts/research/b077_signal_first_look.py \
  --events data/research/b077/lhb_inst_events.csv \
  --prices data/research/b070/snapshots/prices/unified/prices_daily.csv \
  --universe data/research/b070/snapshots/universe/cn_pit_universe.csv \
  --out /tmp/b077_independent_ic_rerun.json
```

**独立复跑结果（/tmp/b077_independent_ic_rerun.json）：**

覆盖：

| 项 | 独立复跑 | F002 报告 | 一致 |
|---|---|---|---|
| events_total | 59,090 | 59,090 | ✅ |
| events_covered（有 B070 价格） | 11,365（19.23%） | 11,365（19.2%） | ✅ |
| events_out_of_universe（小盘） | 47,654（80.6%） | 47,654（80.6%） | ✅ |

rank-IC（`机构买入净额`）：

| Horizon | 独立 rank-IC | F002 rank-IC | 一致 |
|---|---|---|---|
| N1 | **0.0201** | 0.0201 | ✅ |
| N5 | **0.0232** | 0.0232 | ✅ |
| N10 | **0.0176** | 0.0176 | ✅ |
| N20 | **0.0181** | 0.0181 | ✅ |

分组均值（驼峰型，`机构买入净额` 五分位 Q1最卖→Q5最买）：

| Horizon | Q1(最卖) | Q2 | **Q3(≈中性)** | Q4 | Q5(最买) |
|---|---|---|---|---|---|
| N5 | +0.01% | −0.04% | **+3.04%** | +0.66% | +0.50% |
| N10 | +0.18% | +0.25% | **+5.59%** | +0.98% | +0.66% |
| N20 | −0.35% | +1.27% | **+8.67%** | +2.09% | +1.32% |

**独立复跑 verdict：** `INCONCLUSIVE_COVERAGE_LIMITED`（bit-identical with generator）

> **独立性声明**：本复跑独立执行（非 generator 脚本复用路径结果），数字四位数完全一致 → 非橡皮戳，代码确定性得到独立确认。

---

## § 单元测试

```
.venv/bin/python -m pytest tests/unit/test_b077_smart_money_sources.py tests/unit/test_b077_signal_first_look.py -v
```

**结果：38/38 PASS**（含 no-lookahead 检验、IC 纯数学逻辑、judge 三档阈值、fake-akshare隔离）

---

## § 诚实推荐裁定（F003 独立，非橡皮戳 generator）

### 三源独立评估

**北向持股：ELIMINATED（live 死，无法前向跟随）**  
独立 spot-check 今日确认 2024-08-16 冻结。可用于历史回测（2017→2024.8），但**不可驱动前向策略**（跟随对象不存在）。本批方向（聪明钱跟随策略）=排除。

**主力资金流超大单：HOLD-NOT-GO（深度不足）**  
LIVE + 全市场覆盖（优点），但 0.5y 太浅（`can_support_backtest=False`）+VM push host 不稳（0.667）。未来付费/更深源 → 可复评。本批不支撑回测。

**龙虎榜机构席位：INCONCLUSIVE_COVERAGE_LIMITED（不 GO，不直接劝退）**  
- rank-IC 0.018–0.023，**低于 0.03 soufflé 门槛**（不 GO）
- 分组均值**驼峰非单调**（Q3 中性最高，极端买卖均值回归）——无方向梯度，无可直接用的开仓信号
- **80.8% 机构事件（小盘主体）未覆盖 B070**——不能据 19.2% 子集断言"全方向无效"

### 整体裁定：B077 NOT GO（本批结束）

**理由（3条，排序）：**
1. 唯一 live+可回测的源（龙虎榜）仅 19.2% 覆盖且 IC~0.02 < 0.03——覆盖不足以支撑搭策略+全回测
2. 北向已死，主力资金流太浅——三源没有"开箱即用"的 GO
3. 小盘主体（80.8%）未覆盖 = 关键信息缺失，无法排除方向存在的可能

**决定性下一步（若追聪明钱方向）：**  
**补小盘价格覆盖**（B070 宇宙外 47,654 事件个股），在含小盘的去偏样本上重跑 first-look。这才是机构席位信号应该测的总体。若含小盘 IC ≥ 0.03 且分组单调 → GO（下批搭策略+全回测）；仍 < 0.03 / 非单调 → 诚实劝退聪明钱方向。

> **★为什么 NOT GO ≠ 劝退聪明钱方向：**  
> 方向一致正向（4/4 horizon 同号），但测到的只是较大名子集（机构最不活跃处），小盘主体未覆盖。今天的裁定是"地基不够厚，不能据此GO"，不是"方向假"。

---

## § 零回归 + 研究边界确认

- **生产代码变更**：B077 无任何生产改动（`scripts/research/` 全部，`grep -r "b077" workbench/ trade/ = 0 hits`）
- **研究边界**：research-only / no-broker / no 真金 / no 自动下单 / 只读公开披露 / 无策略部署
- **§12.10.2 AST 守门**：未触碰执行路径（code 全在 research scripts）
- **不变量满足**：① 纯研究无生产改动 ② research-safe ③ §23 数据现实 VM 实测 ④ 去偏宇宙 ⑤ first-look ≠ verdict ⑥ §12.10.2 / ruff / mypy CI-exact ✅

---

## § Acceptance 对照（spec §3 F003）

| Acceptance 项 | 结果 |
|---|---|
| L1 全门禁（CI green） | ✅ PASS（eabce89 Python + Backend CI） |
| VM 独立复核：三源数据可得性非夸大 | ✅ 北向 spot-check 今日独立确认 + F001 VM JSON 核实 |
| 尤其北向 2024 现实 | ✅ 独立测得 net_buy_last_disclosed=2024-08-16，678+天冻结 |
| 独立复跑信号 IC/spread（真数字） | ✅ bit-identical（rank-IC 0.0201/0.0232/0.0176/0.0181，覆盖 19.23%） |
| 诚实推荐裁定（不橡皮戳） | ✅ INCONCLUSIVE_COVERAGE_LIMITED 独立确认 + 不直接劝退（80.8% 未覆盖） |
| 哪个源 GO / 全 NO-GO | ✅ 三源独立评估：北向 ELIMINATED / 资金流 HOLD / 龙虎榜 INCONCLUSIVE |
| research-only/no-broker/无生产改动 | ✅ grep 0 hits |
| signoff 实测证据逐条 + 推荐 + caveat | ✅ 本文档 |

**整体：B077 F003 PASS**（诚实 NOT GO，地基不足但方向未排除；决定性下一步已明确）

---

## Caveat（焊死）

- **first-look ≠ 可交易 edge**：本批只回答"数据够不够 + 有没有苗头"，不回答"能不能赚钱"。
- **INCONCLUSIVE ≠ 无信号**：80.8% 小盘未覆盖 = 残余不确定性。
- **龙虎榜选择偏差**：信号条件于"已发生大波动上榜"，混入动量/反转效应，不等于"机构悄悄建仓"。
- **去偏 integrity**：远期收益用 B070 含退市价格（幸存者-free）。
- **纯研究边界**：research-only / no-broker / no 真金 / no 自动下单 / 只读公开披露 / 无生产改动、无策略部署。
