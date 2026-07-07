# B106 F002 — Master 组合层 uplift A/B 报告(防守腿杠铃 + 权重方案对照)

**批次：** B106（组合层落地 · 阶段 A 最高杠杆）· Feature F002（generator）
**日期：** 2026-07-07
**runner：** `scripts/research/b106_portfolio_uplift_ab.py`
**原始数字：** `data/research/b106/ab_results.json`（可复现）
**边界：** research-only / advisory-only / 不碰真金

---

## 0. TL;DR — 裁定 **NO-GO（保持现状）**

在**统一 USD 口径**下，把已验证的红利低波（cn_dividend_lowvol）防守腿并入 Master 组杠铃、
并用风险加权（risk_parity / HRP / vol-target）替换固定 40/30/20/10，**没有任何一个方案在
预登记双门槛（ΔSharpe ≥ +0.15 且 ΔMaxDD ≥ +3pp）下显著优于现状基线**。最好的方案
（barbell + risk_parity）仅把 Sharpe 从 **1.222 → 1.234（+0.012）**、MaxDD 从 −8.3% → −7.0%
（+1.3pp），却把 CAGR 从 **10.46% 拖到 7.93%（−2.5pp）**。**诚实保持现状 default 4-sleeve fixed**
（B069/B076 先例：提升不显著不硬上）。

**核心机理（本批最大方法学发现）：** spec 依据的「红利低波与动量负相关、削回撤」是
**A股内部**现象（红利低波 vs **A股动量**，2024-02 A股踩踏）。但 Master 组的进攻腿是
**美股/全球动量（USD）**，不是 A股动量。对一个 USD 全球组合而言，红利低波是一条
**跨市场 + 跨币种**的腿——① 市场不匹配：即使按 CNY 原生口径，红利低波与美股/全球进攻腿也是
**弱正相关（+0.11 ~ +0.41）**，不是负相关；② 币种不匹配：CNY→USD 汇率与全球 risk-off 同向
（risk-off 时 A股跌、美股跌、人民币贬值三杀），FX 换算把相关性进一步**推正**（+0.19 ~ +0.48），
并把防守腿的 USD 波动率抬到 15.8%、MaxDD 恶化到 −31.8%。**分散收益在跨市场组合里蒸发了。**

---

## 1. 口径声明（★ 本批最大方法学陷阱，显式处理）

### 1.1 为什么不能天真混算一个 Sharpe

- **进攻腿（4 条）** 是 **USD** 计价：momentum(global ETF)/risk_parity/us_quality/hk_china，
  数据源 tiingo 复权收盘（adj_close，含息总收益）。
- **防守腿（cn_dividend_lowvol）** 是 **CNY** 计价：H20269 全收益指数（2005+）。
- 直接把 CNY 价格和 USD 价格塞进同一个 NAV = **币种错配的伪数字**。本报告的 **PRIMARY 口径
  是 USD 统一**：防守腿的 CNY 收益按 **USD/CNY 汇率（CNY per USD，data/research/b090_hk/fx_daily.csv）**
  换算成「一个 USD 投资者实际拿到的收益」= `(1+r_cny)·fx_prev/fx_now − 1`。并单列 **CNY-native**
  口径作对照，使 FX 拖累显式可分离。

### 1.2 为什么不跑生产 Master 引擎

`run_master_portfolio_quarterly_backtest` 给所有 sleeve **喂同一个 `records`**，但各 sleeve 需要
**不兼容的 K 线频率**：global_etf_momentum 的 3/6/9「periods」按*可用观测数*度量（为月末 bar 设计），
而 risk_parity_vol_target 需要 **120 个日频观测**算波动率。引擎是 fixture 标定的，无法诚实地在
同一份原始真实数据上同时跑对两条腿。**故采用 sleeve-return 层重构**：每条腿在各自原生频率下
独立生成收益序列，再在月度 sleeve-return 层组合——一个内部自洽、只隔离「杠铃效应」的 A/B。

### 1.3 窗口对齐

- sleeve 面板共同窗口 **2015-03 ~ 2026-04（122 月）**（受 tiingo 起点 2014-01 + 动量/波动率预热
  与 tiingo 终点约束）。
- 5 方案**公平对齐窗口 2015-09 ~ 2026-04（116 月）**：风险加权方案（③④⑤）有 6 个月滚动预热，
  故所有方案统一裁到共同交集再算指标/裁定（否则基线被多算的 6 个月惩罚，会虚高杠铃的相对提升——
  这个对齐修正把 risk_parity 的 ΔSharpe 从虚假的 +0.128 修正为真实的 +0.012）。
- 成本：每次月度调仓按 turnover × **10bps**（佣金+滑点量级）计。

### 1.4 诚实边界

- 绝对 Sharpe 水平（基线 1.22）偏高，因 sleeve-return 模型（月度调仓、adj_close 总收益、
  动量 top-2 + AGG 防守回落）平滑了部分真实摩擦；**结论建立在方案间的相对比较上**，不声称
  绝对 alpha。动量宇宙用了一个记录在案的全球 ETF 宇宙（SPY/QQQ/EFA/EEM/IWM/TLT/IEF/GLD/AGG），
  防守腿裁定对进攻宇宙的确切构成**稳健**（相对比较）。

---

## 2. ★★ 5 方案对照（USD 统一口径，对齐窗口 2015-09 ~ 2026-04，116 月）

| # | 方案 | CAGR | 年化波动 | **Sharpe** | **MaxDD** | 回本涨幅 | 期末 NAV | ΔSharpe | ΔMaxDD |
|---|---|---|---|---|---|---|---|---|---|
| ① | **baseline 4-sleeve fixed（现状）** | **10.46%** | 8.46% | **1.222** | **−8.3%** | +9.1% | 2.615 | — | — |
| ② | barbell + fixed | 9.33% | 8.13% | 1.141 | −8.1% | +8.8% | 2.369 | −0.081 | +0.2pp |
| ③ | barbell + risk_parity | 7.93% | 6.37% | **1.234** | −7.0% | +7.6% | 2.092 | **+0.012** | +1.3pp |
| ④ | barbell + hrp | 6.91% | 5.88% | 1.168 | −6.7% | +7.2% | 1.908 | −0.054 | +1.6pp |
| ⑤ | barbell + vol_target(8%) | 8.24% | 7.54% | 1.092 | −8.1% | +8.8% | 2.151 | −0.130 | +0.2pp |

**读法：**
- **只有 ③ risk_parity 的 Sharpe 略高于基线（+0.012），远低于 +0.15 门槛**，且靠的是砍波动
  （8.46%→6.37%），代价是 **CAGR 掉 2.5pp**。这是「降风险」而非「加 alpha」。
- ②④⑤ Sharpe 全部**低于**基线。加防守腿在 fixed/vol-target 下纯粹是稀释了高 Sharpe 的
  us_quality/momentum 腿。
- 所有杠铃方案 MaxDD 仅小幅改善（+0.2 ~ +1.6pp），未过 +3pp 门槛。

### 各 sleeve 独立画像（USD，116 月）

| sleeve | CAGR | 年化波动 | Sharpe | MaxDD | 备注 |
|---|---|---|---|---|---|
| momentum(global ETF) | 9.19% | 13.12% | 0.737 | −16.9% | 核心趋势引擎 |
| risk_parity | 4.61% | 4.05% | 1.135 | −6.4% | 低波稳定腿 |
| satellite_us_quality | **17.73%** | 13.87% | **1.253** | −17.0% | ★ 最强腿 |
| satellite_hk_china | 4.90% | 17.65% | 0.358 | −35.3% | ★ 拖累腿（已知） |
| **cn_dividend_lowvol（防守，USD）** | 4.64% | **15.82%** | 0.365 | **−31.8%** | FX 换算后波动/回撤双高 |

> 注意防守腿 **USD 波动率 15.82%**——对一条「低波」策略而言高得离谱，正是 FX 注入的额外波动
> （见 §4）。inverse-vol/HRP 会因此**低配**它，而 fixed 20% 则是把一条 Sharpe 0.37 的腿
> 硬塞进一个平均 Sharpe > 1 的组合，必然稀释。

---

## 3. 相关性——分散前提**不成立**（证据）

| 防守腿 vs 进攻腿 | **USD 换算**（USD 组合实际经历） | CNY 原生（市场错配） |
|---|---|---|
| cn_dividend_lowvol ~ momentum | **+0.270** | +0.178 |
| cn_dividend_lowvol ~ risk_parity | **+0.296** | +0.220 |
| cn_dividend_lowvol ~ us_quality | **+0.195** | +0.114 |
| cn_dividend_lowvol ~ hk_china | **+0.478** | +0.407 |

- **CNY 原生**下防守腿 vs 美股/全球进攻腿是 **+0.11 ~ +0.41 弱正相关**——spec 引用的「负相关」
  是 vs **A股动量**（2024-02 A股踩踏），本组合不持 A股动量，**前提不迁移**（市场错配）。
- **FX 换算**再把每条相关性**推正约 +0.08**（币种错配）：risk-off 三杀同向。
- hk_china 与防守腿相关性最高（+0.41 ~ +0.48）——两者都含中国 β，叠加是**加集中而非分散**。

---

## 4. FX 拖累量化（防守腿 CNY-native vs USD-converted，116 月）

| 口径 | CAGR | 年化波动 | Sharpe | MaxDD |
|---|---|---|---|---|
| CNY-native（一个 CNY 投资者） | 5.76% | 13.60% | 0.480 | −27.8% |
| **USD-converted（Master 是 USD 组）** | **4.64%** | **15.82%** | **0.365** | **−31.8%** |

**2015→2024 人民币兑美元 6.19 → 7.17（贬值 ~15%）**：FX 独立地把防守腿 CAGR 削 1.1pp、
波动抬 2.2pp、Sharpe 从 0.48 压到 0.37、MaxDD 从 −27.8% 恶化到 −31.8%。**对 USD 组合，防守腿
自带一层币种风险，且这层风险与全球 risk-off 同向——这是杠铃分散收益蒸发的直接原因。**

---

## 5. 回撤窗口 + 回撤复利

| 方案 | 2022 全年 收益 / MaxDD | 2024-01~02 收益 / MaxDD |
|---|---|---|
| ① baseline | −5.7% / −6.9% | +5.6% / 0.0% |
| ② barbell fixed | −5.4% / −8.1% | +6.2% / 0.0% |
| ③ barbell risk_parity | **+3.0% / −0.2%** | +2.3% / 0.0% |
| ④ barbell hrp | **+3.9% / −0.1%** | +1.0% / 0.0% |
| ⑤ barbell vol_target | −5.4% / −8.1% | +5.4% / 0.0% |

- **2022**：risk_parity/HRP 杠铃确实缓冲（+3~4% vs 基线 −5.7%）——但这是**低波配置整体降险**
  的结果（大量权重进了低波 risk_parity + 现金），不是防守腿的负相关分散。
- **2024-01~02**：所有方案 MaxDD ≈ 0——因为这是一次 **A股内部**踩踏，**USD 全球组合根本没被波及**；
  spec 预期的「2024-02 杠铃缓冲」**对 USD 组合不成立**（进一步印证市场错配）。
- **回撤复利**：基线 MaxDD −8.3% → 需 +9.1% 回本；最优杠铃 risk_parity −7.0% → 需 +7.6% 回本。
  节省 1.5pp 回本涨幅，但用 2.5pp CAGR 换——**不划算**。

---

## 6. Verdict-gating（预登记门槛 + 裁定）

**门槛（预登记，诚实）：** 某杠铃方案「显著优于基线」当且仅当
**ΔSharpe ≥ +0.15 且 ΔMaxDD ≥ +3pp**（风险调整后收益与回撤须同时实质改善）。

| 方案 | ΔSharpe | ΔMaxDD | 过门槛？ |
|---|---|---|---|
| ③ barbell risk_parity | +0.012 | +1.3pp | ✗ |
| ④ barbell hrp | −0.054 | +1.6pp | ✗ |
| ② barbell fixed | −0.081 | +0.2pp | ✗ |
| ⑤ barbell vol_target | −0.130 | +0.2pp | ✗ |

### ★ 裁定：**NO-GO — 保持现状（default 4-sleeve fixed）**

无方案过双门槛。红利低波防守腿对一个 **USD 全球 Master 组合**：既不提供负相关分散
（市场 + 币种双错配 → 弱正相关），又自带 FX 波动/回撤惩罚，纯粹稀释了高 Sharpe 的进攻腿。
risk_parity 唯一的 Sharpe 微增（+0.012）来自砍波动而非防守腿，代价是 2.5pp CAGR——**不落地。**

### 后续（不在本批，供负责人决策）

1. **风险加权本身值得单独测**（不含 CNY 防守腿）：③ 的 Sharpe 微增+波动大降提示，**只对现有
   4 条 USD 腿做 risk_parity/HRP**（尤其压低 hk_china 的 17.65% 波动权重）可能才是真杠杆。
   本批 5 方案未含「4-sleeve risk_parity（无防守腿）」——建议下一批补测以隔离效应。
2. **替换拖累的 hk_china**（Sharpe 0.358 / MaxDD −35.3%）比加防守腿更直接。
3. **红利低波留在 A股本土组合**（CNY 计价的 A股 sleeve 组合）才能兑现它的负相关分散——
   跨进 USD 组是把它放错了市场。
4. 若坚持要一条防守腿，应找 **USD 计价、与美股/全球 risk-off 负相关**的资产（长久期美债 TLT/IEF、
   黄金 GLD 已在动量/risk_parity 宇宙里），而非跨币种的 A股红利。

---

## 7. 复现性 + trial registry

- **基线复现：** 无历史「Master over 真实数据」金值存在（生产 Master 仅 fixture 测过，且引擎无法
  跑真实长数据——见 §1.2）。故基线 = **生产 default 配置（40/30/20/10）的确定性重跑**，由已提交的
  runner + 冻结数据（tiingo / b082 / b090_hk FX）逐字节可复现。
- **一键复现：** `.venv/bin/python scripts/research/b106_portfolio_uplift_ab.py` → 覆盖写
  `data/research/b106/ab_results.json`。
- **单测：** `tests/unit/test_b106_portfolio_uplift_ab.py`（15 项，覆盖指标数学 / 口径换算 /
  组合（含 vol-target no-normalize 真 bug 回归）/ 相关性 / 滚动权重派生 / verdict 门槛）。
- **trial registry：** 登记为 `master_portfolio_defensive_barbell` 的组合层试验，verdict=NO-GO
  （`workbench/backend/workbench_api/monitoring/trial_backfill_b106.py` + migration 0042），计入 DSR N。

## 8. 门禁

- `mypy trade`：0 err（零回归）。
- `ruff check .`：全绿。
- pytest 零回归子集（master/portfolio/risk_parity/dividend + 新 15 单测）：**102 passed**。
- F001 字节级金值守门单测（parameter_hash 726f9ce6…）：未触及，绿。
