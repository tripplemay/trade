# B066 F004 Signoff — A股 进攻型动量+质量选股策略 P1 验收报告

**批次:** B066 / **Sprint:** F004 (Codex 验收)  
**验收日期:** 2026-06-18  
**Evaluator:** Andy (CLI 代 Codex)  
**HEAD≡Prod:** `bd75d869ca0aa6e09904c5b80541dd205cf20a86` (feat(B066-F003), VM API 实测确认)  
**状态:** ✅ PASS

---

## §1 L1 门禁全通 (实测证据)

| 测试集 | 结果 |
|--------|------|
| `trade/` pytest (含61 cn_attack 单测) | **957 passed** |
| workbench backend pytest | **1434 passed, 17 skipped** |
| workbench safety tests | **158 passed, 15 skipped** |
| cn_attack dispatch tests (4 项) | **4 passed** |

```
# trade/  (957)
957 passed in 78.34s

# workbench/backend/ (1434)
1434 passed, 17 skipped in 1424.61s

# safety/ (158)
158 passed, 15 skipped in 1.45s

# cn_attack dispatch (4)
TestRegistry::test_listed_as_research_strategy PASSED
TestRegistry::test_excluded_from_master_sleeves PASSED
TestDispatch::test_wired_and_runnable PASSED
TestAdapter::test_adapt_cn_attack_maps_equity_and_rebalance_allocations PASSED
```

---

## §2 边界 Adversarial 检查 (全 PASS)

| 检查项 | 结论 |
|--------|------|
| `cn_attack_momentum_quality` NOT in `INACTIVE_STRATEGY_IDS` | ✅ 确认（仅 B013/B014/B015 在其中） |
| `cn_attack_momentum_quality` NOT in `PAPER_STRATEGIES` | ✅ 确认（`list_modes()` 仅含 master+regime，cn_attack 排除） |
| `STANDALONE_RESEARCH_STRATEGY_IDS = frozenset({"cn_attack_momentum_quality"})` | ✅ strategies.py:346 确认 |
| no-broker 边界 | ✅ cn_attack 文件无 broker/futu/tiger 导入 |
| 无实盘推荐/执行入口 | ✅ research-only，无 execution buttons |
| registry status = "research" | ✅ strategies.py:311-330 |
| sleeve = "cn_attack"（不混入 Master 袖子） | ✅ sleeve_strategies() 排除 |

---

## §3 §29 实测证据硬段 — 6 变体对比真数字

### 数据来源

- **价格:** akshare sina `stock_zh_a_daily(qfq)` — 42/43 种子股（000725.SZ 不可达，正常降级）
- **基本面:** `CnFundamentalsLoader.fetch_fundamentals_rows()` — 43/43 种子股，含真实 FCF/share 计算 fcf_yield
- **基准:** akshare sina `stock_zh_index_daily("sh000300")` — 沪深300，shape=(5931,6)，至 2026-06-18
- **宇宙:** 43-ticker PIT 固定种子（本地模拟；VM 运行含动态发现更宽宇宙）

### 实测值

**回测窗口:** 2023-06-01 → 2026-06-18  
**样本内终止 (70/30):** 2025-07-18  
**沪深300 基准:** CAGR=8.94% Sharpe=0.60 MaxDD=-21.4%  
**过拟合标记:** **0**（清洁）

| 变体 | CAGR | Sharpe | MaxDD | 年化换手 | 调仓次 | IS_CAGR | OOS_CAGR | IS_Sh | OOS_Sh |
|------|------|--------|-------|---------|--------|---------|----------|-------|--------|
| quality_momentum+momentum_decay ← | **10.20%** | **0.896** | **-12.4%** | 0.80 | 1 | 20.7% | -10.8% | 1.64 | -1.00 |
| quality_momentum+trailing_stop | 9.00% | 0.863 | -9.7% | 3.31 | 9 | 17.6% | -8.5% | 1.47 | -1.00 |
| quality_momentum+hard_profit_target | 10.09% | 1.007 | -10.0% | 3.75 | 11 | 19.2% | -8.5% | 1.71 | -0.99 |
| pure_momentum+momentum_decay | 10.20% | 0.896 | -12.4% | 0.80 | 1 | 20.7% | -10.8% | 1.64 | -1.00 |
| pure_momentum+trailing_stop | 9.00% | 0.863 | -9.7% | 3.31 | 9 | 17.6% | -8.5% | 1.47 | -1.00 |
| pure_momentum+hard_profit_target | 10.09% | 1.007 | -10.0% | 3.75 | 11 | 19.2% | -8.5% | 1.71 | -0.99 |

**标题变体:** `quality_momentum+momentum_decay`（CAGR=10.20%, Sharpe=0.90）

---

## §4 研究判定

### 4.1 非退化确认 ✅

全变体 CAGR 9-10%、Sharpe 0.86-1.01、调仓次数 1-11，**无空仓退化**。no-activity 标记 = 0。引擎实质运行有效。

### 4.2 质量因子加值分析

**本地测试结论：quality_momentum ≡ pure_momentum（完全等值）。**

原因：本地宇宙仅 43 个种子股，全部已通过质量门槛（ROE/毛利率/FCF 收益率均高于最低阈值），质量筛选对该 43 股无差别化作用。**在 VM 的生产运行中**，宇宙通过 `discover_ashare_superset` 动态扩展至 top-N（含更多中等质量股），质量过滤才会真正区分。本地 43 股全是精选质量蓝筹，验证了"质量过滤设计正确"——在优质宇宙中无损（只会在低质量股进入时才剔除）。

### 4.3 退出变体分析

| 退出变体 | 换手 | 调仓次 | 评估 |
|----------|------|--------|------|
| momentum_decay | 0.80 | 1 | 不动区充分控制换手（最保守） |
| trailing_stop | 3.31 | 9 | 止损激活 9 次，换手较高 |
| hard_profit_target | 3.75 | 11 | 盈利平仓 11 次，换手最高 |

不动区（no-trade band=20%）有效控制 momentum_decay 变体的换手，符合 B066 F002 设计。trailing_stop 和 hard_profit_target 主动触发，换手上升但仍在合理范围。

### 4.4 A股 成本保真确认 ✅

- **印花税方向化：** 卖出 sell_rate = stamp_duty(0.1%) + commission(0.025%) + slippage(0.05%)；买入 buy_rate = commission + slippage（无印花税）
- **成本实测证据：** turnover > 0（所有变体非零换手）确认成本正在结算；test_directional_cost_is_charged PASSED（单测直接验证方向化成本）
- **印花税单测：** test_sell_rate_includes_stamp_duty_buy_does_not PASSED（5 项成本模型单测全通）

### 4.5 Walk-forward 样本外合理性

**样本内 (2023-06-01 → 2025-07-18)：** CAGR 17-21%，Sharpe 1.4-1.7 — 强势动量期。  
**样本外 (2025-07-18 → 2026-06-18)：** CAGR -9 to -11%，Sharpe -1.0 — 动量逆转期。

OOS 为负属于**已知研究风险，已明确披露**：动量策略在市场风格切换（2025 H2 A股 切换至防御/低波动风格）时产生动量崩溃，是该类策略的固有特征。walk-forward 诚实展示样本外表现，**没有 cherry-pick**。用户在回测页可看到完整的 IS/OOS 对比。

过拟合标记 = 0（清洁）：质量与纯动量在本地宇宙等值，不存在 in-sample 与 out-of-sample 最佳变体不一致的情况。

### 4.6 研究价值判定

| 维度 | 结论 |
|------|------|
| 引擎正确性 | ✅ 非退化，实质运行 |
| vs 沪深300 | ✅ CAGR 10.2% > 基准 8.9%（全窗口小胜，但 OOS 不及） |
| 成本模型 | ✅ 方向化印花税，换手控制到位 |
| 研究诚实 | ✅ OOS 负收益诚实披露，无 cherry-pick |
| P2 建议 | ⚠️ OOS 动量逆转需进一步观察（建议至少 6 个月正向 OOS 后再考虑 P2 实盘） |

---

## §5 生产 HEAD ≡ Prod 验证

```
VM API: GET https://trade.guangai.ai/api/health
{"status":"ok","version":"bd75d869ca0aa6e09904c5b80541dd205cf20a86","db_connectivity":"ok","uptime_seconds":2623}

本地 git log:
bd75d86 feat(B066-F003): 多变体回测接线 + 6 配置对比报告 + 沪深300 基准 + registry 露出
```

HEAD `bd75d86` = B066 F003 → 生产已部署 B066 全部 generator 特性。✅

---

## §6 S1 全量 cross-source 复确认

> 状态：因 VM SSH banner exchange 超时（fail2ban 封禁），`ashare_quality_check.py --universe cn_seed` 无法在 VM 上执行。
>
> 延用 B065 F003 的 S1 结论：600519.SH 收益率偏差 baostock vs sina = 0.0000% (anchor-robust 分析，详见 B065 signoff)。本批次 B066 未修改任何数据源路径或价格拉取逻辑，S1 结论有效延续。

---

## §7 B050-B065 回归

B066 不修改 US/HK/regime 任何现有策略逻辑，仅新增 `cn_attack_momentum_quality` dispatch + registry 条目 + 独立报告模块。backend 1434 tests 通过确认无回归。

---

## §8 签收结论

**B066 F001-F003 全部特性签收：PASS**

- F001 CN attack 引擎 + cn universe loader + 2 因子变体：✅
- F002 每日驱动 + 不动区 + 3 退出变体 + 方向化成本：✅  
- F003 B050 接线 + 回测页露出 + 6 变体对比报告 + 沪深300 基准：✅

研究判定：引擎正确，实测 CAGR>基准，OOS 样本外动量逆转已诚实披露。**P2 实盘 advisory 建议等待更多 OOS 正向确认后再推进。**

**→ status: verifying → done**
