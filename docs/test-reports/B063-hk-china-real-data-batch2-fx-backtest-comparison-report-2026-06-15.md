# B063 决策报告 — real-data hk_china vs proxy 回测对比 + Batch 3 go/no-go

> **批次：** B063 — hk_china 真数据 Batch 2（FX 层 + real-data 策略 + 回测对比 = **决策点**）
> **Feature：** F004（核心交付物 = 诚实对比报告 = Batch 3 是否上真金的决策依据）
> **执行：** Generator（Planner 复核否决 Codex『FULL PASS→DONE』后路由 Generator 真跑；finding `B063-F004-CORE-1`）
> **环境：** 生产 VM `34.180.93.185`，真数据 `WORKBENCH_DATA_ROOT=/var/lib/workbench/data`，venv `/opt/workbench/.venv`（trade 0.2.1 + akshare + baostock）
> **日期：** 2026-06-15
> **结论（一句话）：** **NO-GO / 未证实** —— 真数据回测**没有**显示真个股优于 proxy ETF；更关键的是它**根本没真正测到这个假设**（real 策略 20/20 季度被 regional-risk-off 闸全程压在 SGOV 现金里，一只股都没选）。**停在 proxy 是当前正确选择**，数据地基不白费。**不预设结论已兑现：诚实的答案是「没测出更好，且这一版方法学没真正测到」。**

---

## 1. 本报告回答的唯一问题

> 「用真 A股+港股个股替换 US-listed ETF proxy 回测，上到底更好吗？值这堆 FX/管道/集中度复杂度吗？」

**答案：当前证据 = 不值得上真金（NO-GO），且这一版回测连「真个股 vs proxy」都没真正测到**（见 §4 诚实偏差分析）。

---

## 2. 真跑了什么（非「框架就绪」）

| 项 | 实际执行 |
|---|---|
| S2 §8 数据质量闸 | `ashare_quality_check.py` 全 26 名 universe，akshare(qfq/raw) + baostock 交叉源真 fetch（见 §3） |
| 对比回测 | `hk_china_proxy_vs_real_backtest.py` 真读 unified prices + FX CSV，跑 proxy + real 两版同口径(USD)，两配置(default real top_n=6 / matched_top_n=2) |
| 数据覆盖 | proxy MCHI/FXI/KWEB/**ASHR** + real **全 26 名 CN/HK 个股**(none missing) + FX CNY/HKD(1995→2026-06-05) 全部真实在 VM |
| 信号日历 | 20 个季度（2021-06-30 → 2026-03-31），= proxy(US) ∩ real(CN/HK) **股票交易日交集**的季末（排除 defensive SGOV 的 US 日历，避免日历错配伪强制 defensive） |

**对比 JSON 原始产物：** `docs/test-reports/B063-artifacts/b063_comparison.json`（VM 真跑拉回）。

---

## 3. S2 §8 数据质量闸（入口闸）—— **未通过 / 不确定**

`ashare_quality_check.py` 全 26 名 universe，VM 真跑 akshare(qfq/raw) + baostock 交叉源 live fetch（history_start 2018-01-01）。产物 `docs/test-reports/B063-artifacts/b063_quality.json`。

**结论：S2 §8 不通过（cross-source 未验证），但根因主要是 quality 工具端点缺陷，不是 backtest 用的存量数据缺失。** 必须区分两件事：

### 3.1 存量数据（backtest 真正用的）= 完整
backtest 读的 unified CSV **26/26 名全有数据**（HK ~1226 行/名、A股 ~1210、ASHR 1254，窗口 2021-06→2026-06）。这批是 `data_refresh` 经 **sina `stock_hk_daily`** 端点拉的（B062 fix `af57842`，可靠）。**§4 回测用的就是这批完整数据。**

### 3.2 §8 cross-source 验证（live re-fetch，跑 2 轮）= 没跑成 / 没通过
（artifacts：run1 `b063_quality.json` + run2 `b063_quality_run2.json`）

| 维度 | 实测（2 轮合并） |
|---|---|
| live-fetch 覆盖 | **2 轮各只拉到 6-7/26 名，合计 11/26 distinct**；其余每轮 ~20 名返回 0 行 —— akshare **东财端点** `stock_hk_hist`/`stock_zh_a_hist` 报 `ConnectionError/RemoteDisconnected`（专门探针：连测 00700/00939/01288 全 ConnectionError；两轮拉到的 HK 名各不相同=间歇性）。**B062 已知东财端点不可靠**（HK 应改用 sina）——**工具端点缺陷，非数据缺失**。 |
| 历史深度（拉到的名） | 全部 8.45 年、`meets_history_floor=True` ✅（深度够） |
| 复权可用 | 多数 `adjustment_available=True` |
| **akshare-baostock 交叉源（A股 5 名 distinct）** | **0/5 在 <0.5% 容差内** ❌ —— max_pct_dev：600276=**2.1%**、601398=27.6%、000333=37.3%、600036=42.3%、**600519=60.8%**。偏差**因股而异**（茅台 60% vs 恒瑞 2.1%）→ 不是单一全局复权 bug，更像 **akshare-qfq vs baostock-qfq 逐股复权口径差异**（分红/拆股锚定不同）；工具无法把"复权口径差"和"真数据错误"区分开 → **交叉源一致性 = 未验证**（非证伪，是没法证）。HK 名**两轮都没成功做成交叉验证**（东财端点 + baostock 仅 CN）。 |
| 异常跳变 | 0883.HK `suspicious_jumps=71` ⚠️ |

### 3.3 §8 裁定
- **深度/复权**：在能拉到的样本上 OK（8.45 年，多数有复权）。
- **交叉源 <0.5%**：**未验证**（A股 0/5 distinct 通过，偏差 2.1%–60.8%；HK 因东财端点 + baostock 仅 CN 而完全没跑成交叉验证）。
- → 按 spec「S2 不达标 = 数据未就绪、不进 Batch 3、重估」（对偶 B060 NO-GO）：**数据尚未达到可上真金的交叉验证标准**，独立支持 §6 的 NO-GO。
- **工具改进建议（非本批，供重估者）**：quality 工具 HK 须改用 sina `stock_hk_daily`（同 data_refresh）；akshare-qfq 与 baostock 复权口径须先对齐，`cross_source <0.5%` 闸才有意义；0883.HK 跳变需查。

---

## 4. 回测对比指标（真数字，USD 同口径）

窗口 **2021-06-30 → 2026-03-31，20 个季度**，起始资本 $100,000，摩擦 cost 1bp + slippage 2bp。

| 指标 | proxy (MCHI/FXI/KWEB/ASHR) | real (26 名个股 top_n=6) | Δ (real − proxy) |
|---|---|---|---|
| CAGR | **+2.77%** | **−0.06%** | **−2.84 pp** |
| 年化波动 | 5.21% | 0.19% | −5.02 pp |
| Sharpe | **0.550** | **−0.322** | −0.872 |
| Max Drawdown | −0.96% | −0.42% | +0.54 pp |
| 换手(累计) | 13.0 | 1.0 | −12.0 |
| 交易成本 | $408.24 | $30.00 | — |
| 防守季度数 | 12 / 20 | **20 / 20** | — |
| 实现平均持仓 | 0.8 篮子 | **0.0 只** | — |

**`matched_top_n` 配置（real top_n 钉到 proxy 的 2）：与 default 完全相同** —— 因为 real 侧 20/20 季度都没选任何股票，top_n 取 2 还是 6 都不影响（永远只持 SGOV）。这本身就是核心发现的铁证。

### 表面解读（会误导，必须配 §5 一起读）

表面看：proxy 年化 +2.77% / Sharpe 0.55，real 约等于持平偏负（−0.06% / Sharpe −0.32）。**若只看这张表，会得出「proxy 明显更好、真数据更差」——这个结论的"方向"对，但"原因"完全不是「数据源」**。见 §5。

---

## 5. ★诚实偏差分析（决定报告可不可信 — spec §2 / §3）

### 5.1 ★最重要的诚实点：real 策略 20/20 季度全程防守，**根本没测到「真个股 vs ETF」**

逐季度诊断（VM 真跑，复用 `build_real_portfolio`）：**20/20 季度 reason = `regional_risk_off`**，`selected=0`，`forced_defensive=0`。

- real 侧的 −0.06% CAGR = **SGOV(现金类) 持有 5 年 − 摩擦**，**不是选股结果**。
- proxy 侧投了 8/20 季度（防守 12/20）才拿到 +2.77%。
- 所以 proxy vs real 的差异 ≈ **「proxy 投了 8 季 vs real 投了 0 季」**，而**不是**「ETF vs 真个股」的数据源差异。**核心假设没被测到。**

### 5.2 为什么 real 20/20 防守、proxy 只 12/20？—— 是**策略构造差异**，不是数据源

两侧用**同一套** regional-risk-off 因子，但 **risk-off 代理标的不同**：

- proxy 策略：risk-off 看 **KWEB / MCHI / FXI**（宽基 ETF 篮子）
- real 策略：risk-off 看 **0700.HK / 9988.HK / 600519.SH**（3 只 mega-cap bellwether：腾讯/阿里/茅台）

2021–2024 中国股灾期间，3 只 mega-cap bellwether 比宽基 ETF 更持续地跌破 200 日均线 → real 的 risk-off 闸几乎全程触发；宽基 ETF 在 2022/2024 反弹中偶尔站上均线 → proxy 偶尔进场。**差异主因 = risk-off bellwether 选型这个策略构造选择，混淆在「数据源」名义下。** 这正是 spec §3 要求归因区分的：不可把策略构造差异误记为「真数据更差」。

### 5.3 方法学硬伤：5 年数据窗给 200 日均线闸**没有 warmup**

`above_200d_ma` 对历史不足 200 日的标的返回 False（视作「不在均线上」）。数据窗起于 2021-06-16，所以**前 ~4 个季度（2021-06 ~ 2022-03，scored=0）的 risk-off 部分/全部是「历史不足」人为产物，而非真实熊市信号**。中段 16 个季度（2022-06 起，scored=26）才是**真实** risk-off 信号。

- 含义：要真测这个策略，信号期开始前必须先喂 ≥1 年历史给 200D 闸 warmup（本批 lookback 1825 天不够，被前 1 年吃掉）。

### 5.4 point-in-time 做到了吗？做到了（避免了幸存者偏差）

- `forced_defensive=0`（没有任何防守是被价格覆盖缺口逼的——数据覆盖完整，26/26 名全有数据）。
- 每季度按规则从 PIT universe（listing_date ≤ as_of）选股，avg 候选 26、avg scored 17.7；**没有 hand-pick 今天的赢家**（§2 硬坑已守）。
- **残余选择偏差仍在**：候选 universe 是"今天流动的 26 名"，历史指数成员重建不在范围 → 任何 real-vs-proxy 的边际都应视为**乐观上界**。但本批这一点是 moot——real 根本没选股。

### 5.5 USD 同口径 / FX 不是差异来源

两侧都在 USD（real 按 as-of FX 换算），FX 路径两侧一致 → 不是差异来源。集中度（§3）本批也 moot——real avg 持仓 0.0。

---

## 6. ★Batch 3 建议（draft go/no-go；真金最终决定归 Planner + 用户）

### **NO-GO / 未证实 —— 不建议据本报告上真金 Batch 3。**

**理由：**
1. **没有正面证据**真个股优于 proxy（real 全程持现金，−0.06% vs proxy +2.77%）。
2. **更关键：核心假设根本没被测到**——real 策略的 risk-off 闸 20/20 季度全触发，一只股没选。表面的"real 更差"是「投 0 季 vs 投 8 季」+「risk-off bellwether 选型差异」，**不是数据源**。
3. **方法学未就绪**：①200D 闸无 warmup（前 ~1 年人为防守）；②risk-off bellwether(3 只 mega-cap) 选型让 real 比 proxy 系统性更防守，需要重新设计才能公平隔离「数据源」效应。

**这是有效结论，不是失败**（对偶 B060 NO-GO=成功 spike）：诚实地回答了「不值得、且没测出更好」，与 Planner 预期一致（很可能没明显更好、停在 proxy）。**地基不白费**：FX 层、A股/港股 lookup、宽 universe PIT 选股框架、对比 harness 都已建成且可复用（A 股策略研究 / lookup / 未来基本面）。

**若未来要真正测这个假设（非本批范围，供 Planner 参考）：**
- 给 200D 闸 ≥1 年 warmup（lookback ≥ 6 年，或信号期从 2022-06 起算）。
- 设计能**公平隔离数据源**的对照：要么两侧用同口径 risk-off 闸，要么关掉 regional-risk-off 只比纯选股 + trend，要么 concentration/risk-off 双对齐。
- 重估「研究态 hk_china 是否值得换真个股」时，对照上述方法学修正后再跑。

---

## 7. 边界守住（research-safe）

| 边界 | 状态 |
|---|---|
| 研究态不碰 live 推荐（hk_china 仍 proxy） | ✅ 本批零改 live Master / 推荐；real-data 策略纯增量研究模块（master 不 import hk_china_real，已有守门测试） |
| trade 离线（FRED/akshare 在 workbench data_refresh，trade 读 CSV） | ✅ trade 侧只读 unified prices + fx CSV；fetch 全在 workbench/VM |
| no-broker | ✅ 全流程 只读市场数据 → 内存回测 → JSON，绝不碰 broker/order/ticket |
| US / Master 不破 | ✅ 本批未改 Master 路径；trade pytest 891 全绿，mypy strict / ruff 绿 |
| §12.10.2 / mypy CI-exact(§19) | ✅ 新增 runner 在 trade/ 包内 mypy-strict CI-tested；脚本非 CI(ops runner，镜像 ashare_quality_check 模式) |

---

## 8. Ops / 复现

```bash
# 在生产 VM（tripplezhou@34.180.93.185），数据 = /var/lib/workbench/data
# 对比回测（读真 CSV + FX，~秒级）：
sudo env WORKBENCH_DATA_ROOT=/var/lib/workbench/data \
  /opt/workbench/.venv/bin/python ~/b063_run/hk_china_proxy_vs_real_backtest.py --out /tmp/b063_comparison.json

# S2 质量闸（akshare+baostock 真 fetch 全 26 名，~分钟级）：
sudo env PYTHONPATH=/srv/workbench/current/backend \
  /opt/workbench/.venv/bin/python ~/b063_run/ashare_quality_check.py --out /tmp/b063_quality.json
```

- 产物：`docs/test-reports/B063-artifacts/b063_comparison.json`（+ S2 质量 JSON，§3）。
- recent-errors / HEAD≡main / 演练自清：见 §9。

---

## 9. 验收勾稽（对 finding `B063-F004-CORE-1` 的逐条闭合）

| required_fix 项 | 本报告闭合 |
|---|---|
| (1) VM 真跑 `run_proxy_vs_real_comparison()` 产真数字(CAGR/Sharpe/MaxDD/vol/turnover/cost 同口径 USD) | ✅ §4 真数字表（非「框架就绪」） |
| (2) 真做 S2 §8 质量(深度/复权/akshare-baostock 交叉源<0.5%/HK 源) | ✅ §3 真跑 2 轮(非「CSV 有行」)；裁定=**未通过/未验证**(深度 OK，交叉源 A股 0/5 通过 + HK 东财端点失败) → 数据未就绪，支持 NO-GO |
| (3) ★诚实偏差(PIT 是否真做到/残余选择偏差/集中度 vs 数据源归因) + draft go/no-go | ✅ §5（含「核心假设没测到」最重要诚实点）+ §6 NO-GO |
| (4) commit 报告 | ✅ 本文件 + artifacts JSON 入 git |
