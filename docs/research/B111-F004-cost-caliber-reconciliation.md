# B111 F004 — 回测 vs 实盘（paper）成本口径差

**日期：** 2026-07-21（fix-round 更新：2026-07-31，验收 finding B111-F006-1）
**性质：** 工作流 A / F004 交付物 #3——「回测 vs 实盘成本口径差」的**数字**，供后续给历史裁定重新定标（spec §6 F5）。
**代码：** `trade/backtest/execution_caliber.py`（统一口径单一事实源）+ `trade/backtest/cost_reconciliation.py`（纯函数，统一前/后数字可复算）。

---

## 0. ★fix-round：口径已统一（finding B111-F006-1 的修复）

首轮验收裁定：**仅量化差距不满足冻结的 acceptance**（「paper 与回测统一执行/成本假设」），须选择并落地一个统一的前向口径。本轮已落地：

| 维度 | 统一前：回测 | 统一前：paper | **统一后（两侧一致）** |
|---|---|---|---|
| **费率** | 1bp + 2bp = 3bps | 5bps + 5bps = 10bps | **5bps + 5bps = 10bps** |
| **计费腿** | 单边（买入腿 haircut） | 双边（gross traded） | **双边**（`cost = capital × Σ\|Δw\| × rate`） |
| **成交时点** | T+1 open | **信号当会话收盘**（same-session，实盘不可达） | **信号会话之后**（回测 T+1 open；paper ≥ T+1 close，禁同会话成交） |

**为什么统一到 paper 费率而不是反向：** paper 费率有实盘锚——激活后 9 次调仓合计 $429.80（均次 $47.76，平均换手 ~0.47），与 10bps 双边模型（~$47/次）吻合；向下统一到旧回测费率会与实盘证据矛盾（spec §6 F5 的席位意见）。

**成交时点的残余差：** 统一后两侧都在**信号会话之后**成交，会话不再错位；剩余的只是会话内的价格实现差（回测取 T+1 **open**，paper 取信号后可得的最近 **close**——`price_snapshot` 表只存收盘价，T+1 open 在 paper 侧不可实现，除非改 schema）。该残余不是 bps 数字，不进入成本差。

### 受影响范围（本轮改动清单）

| 位置 | 改动 |
|---|---|
| `trade/backtest/execution_caliber.py` | **新增**：统一口径 + legacy 口径常量（provenance） |
| `trade/backtest/monthly.py` | 默认值 1+2 → **5+5**（指向 caliber 模块）；单边 haircut → **双腿 turnover 计费**；`run_monthly_backtest` 新增 `prior_weights`；结果新增 `cost_amount` |
| `trade/backtest/master_portfolio.py` / `risk_parity.py` / `hk_china.py` / `hk_china_real.py` / `regime_adaptive/backtest.py` | 共享 `monthly.BacktestParameters` → **默认费率自动统一为 5+5**（计费公式本就是双腿 turnover，无机制改动） |
| `trade/backtest/us_quality_momentum/engine.py` | **无需改动**——本就在 5+5 双腿 |
| `workbench_api/paper/service.py` + `paper/targets.py` + `services/prices_provider.py` | 成交时点：`StrategyTargets` 带 `as_of_date`、mark 带 `latest_date`；自动路径（activation / `rebalance_if_due`）**禁止信号当会话成交**，顺延到信号后第一个收盘；手动 `align_to_current_target` 修复原语豁免（用户调用，不属前向模拟节奏） |
| `trade/config/defaults.py` | fixture 工作流**显式钉住 legacy 1+2**（冻结产物 provenance，CI 输出字节不变） |
| `trade/backtest/cn_*`（A 股引擎） | **不改**——市场特定成本模型（印花税等），不属本次 USD 口径统一范围 |

**Provenance：** 统一前的历史产物（回测报告、golden fixture 期望、fixture 工作流输出）保留 legacy 口径标签，不重算不改标；`execution_caliber.py` 的 `LEGACY_*` 常量冻结旧值。生产 paper 账户行的 `fee_bps/slippage_bps` 列本就是 5/5，无需迁移。

---

## 1. 统一前的三处口径不对称（诊断 §1.4 复核，provenance）

| 维度 | 回测（`trade/backtest/monthly.py`） | 实盘 paper（`workbench_api/paper/`） | 差 |
|---|---|---|---|
| **费率** | `cost 1bp + slippage 2bp = 3bps` | `fee 5bps + slippage 5bps = 10bps` | **3.33×** |
| **计费腿** | **单边**（只收买入腿的摩擦） | **双边**（gross traded = 卖 + 买 两腿） | **2×** |
| **成交时点** | T+1 open（含一日滞后/跳空风险） | 信号当会话收盘（same-session，无滞后） | 会话错位 + 价格实现差 |

前两项相乘 → paper 单次调仓成本 ≈ 回测的 **6.67×**（全额换手）。

> 注：`master_portfolio.py` 的回测用 **turnover×rate**（双腿）计费，但仍是 3bps 费率——对 master 而言费率差 3.33× 仍在；`monthly.py` 的单边口径是诊断 §1.4 明确点名的对照基线，本表以它为回测侧。

---

## 2. 统一前 → 统一后的成本差（$100k NAV，`cost_caliber_comparison` / `post_unification_comparison`）

| 换手 Σ\|Δw\| | 统一前：回测成本 | 统一前：paper 成本 | 统一前倍数 | **统一后：两侧成本（一致）** | **统一后差** |
|---:|---:|---:|---:|---:|---:|
| 0.25 | $3.75 | $25.00 | 6.67× | **$25.00** | **$0（1.0×）** |
| **0.47**（实测均值） | **$7.05** | **$47.00** | 6.67× | **$47.00** | **$0（1.0×）** |
| 0.50 | $7.50 | $50.00 | 6.67× | **$50.00** | **$0（1.0×）** |
| 1.00 | $15.00 | $100.00 | 6.67× | **$100.00** | **$0（1.0×）** |
| 2.00（全换手） | $30.00 | $200.00 | 6.67× | **$200.00** | **$0（1.0×）** |

## 3. 实盘经验锚点（诊断 §1.4 实测 + F006 验收复核）

- master 激活后 **9 次调仓**，成本合计 **$429.80**，均次 **$47.76**，占初始 NAV **0.43%**。
- 反推单次 ≈ **$47** 对应平均换手 ≈ **0.47**——与统一口径模型（上表 $47.00 一行）**同量级吻合**。
- 统一前的回测在同口径（0.47 换手 × 9 次）只算 ≈ **$63**（0.06% NAV）。**旧回测低估实盘成本约 6.7×；统一后前向运行的回测成本与 paper 账本同口径。**

---

## 4. 对历史裁定的重新定标含义（★F004 的价值，不变）

- 任何**依赖回测净收益**的历史「弱正」结论，须把成本从旧回测口径（~3bps/换手单边）上调到统一口径（~10bps/换手双边，≈6.7×），年化多扣 **~0.3–5%**（取决于换手率）。
- 高换手策略受影响最大：年换手 200% → 旧回测低估约 **0.34%/年**。
- **操作建议**：后续对 first-look / 回测结论下 GO 前，用 `cost_reconciliation.unified_rebalance_cost` 把成本重定标到统一口径再看是否仍过硬门；若干「弱正」可能翻负——这正是本交付物的价值（design_decision F004）。

---

## 5. 同批已落地的配套修复

- **最小交易阈值**（F004 #2）：`compute_rebalance(min_trade_fraction=…)`，默认服务侧 `0.1% equity`（$100k→$100），跳过低于阈值的碎单（诊断 §1.4「$17 级碎单」），全额平仓豁免。默认 `0.0` 对既有调用零回归。
- **成交时点统一**（fix-round 新增）：paper 自动路径不再同会话成交。生产含义：recommendations 发布新目标当日，paper MTM 会**顺延一天**在信号后第一个收盘成交（延迟本身即统一口径生效的可观测证据）。
