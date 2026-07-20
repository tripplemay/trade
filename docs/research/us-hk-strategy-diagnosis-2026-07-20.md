# 美/港股策略诊断与重构设计 — 2026-07-20

**性质：** 用户指派的独立研究任务（策略研究员视角），不属于任何批次；只读诊断，未改任何产品代码/生产状态。
**范围：** 生产 paper 实盘的两个 USD 策略 — `master_portfolio`（live）与 `regime_adaptive`（research）。
**数据来源：** deploysvr 生产 DB（sqlite 只读）、VM 统一价格/基本面快照（只读拷贝）、本仓 HEAD 代码、历史 signoff 文档、外部文献（含第二来源核验）。

---

## 0. TL;DR

**当前生产运行的不是被验证过的那个策略。** 三个相互独立的缺陷叠加，使 master_portfolio 实际形态变成「40% 押注两只个股 + 44% 现金 + 16% 稀释版风险平价」：

| # | 缺陷 | 影响仓位 | 性质 |
|---|---|---|---|
| P0-1 | momentum sleeve 的 3/6/9「期」参数按**月线**设计，生产喂**日线** → 实际是 3/6/9 **天**动量；且候选池被 27 只个股污染（设计是纯 ETF 轮动） | 40% | 实现 bug，已端到端复现 |
| P0-2 | us_quality sleeve 自 A 股行情并入统一 CSV 后**静默死亡**：中美交易日历并集在滚动窗口打出 NaN 空洞，`low_vol`/`trend` 因子全 NaN → 复合分全空 → 0 持仓 → 回落 SGOV；元数据却仍报 `scored`/`real` | 20% | 实现 bug，已在 VM 复现根因 |
| P0-3 | regime_adaptive 目标权重冻结在 **2026-05-29**：6-12 手动刷新 4 连败（QQQ 缺历史），B107 迁移错过 7 月月度 timer，下次 8-1 才跑 | 100%（regime 账户） | 运维缺陷 |

5.5 周 paper 实盘结果与之相符：master **-2.28%**（同期 SPY +0.78%，超额 **-3.06%**），regime -0.85%（超额 -1.06%）。监控体系（B080）只覆盖 A 股三策略，**美/港股两账户零监控**，以上问题全部无告警。

**结论：** 先修 P0（恢复「被验证的设计」本身），再谈更好的策略。第 7 节给出基于外部证据的重构设计（单一趋势/动量核心 + 按资产的绝对动量防守，替代现在三条 sleeve 各自为政的 SGOV 瀑布），附验证协议与开批建议。

---

## 1. 实盘现状（生产 DB 实测，截至 2026-07-20）

### 1.1 账户绩效

| 账户 | 区间 | NAV | 基准(SPY) | 超额 | 年化波动 | 最大回撤 |
|---|---|---|---|---|---|---|
| master_portfolio (live) | 06-12 → 07-20 | **-2.28%** | +0.78% | **-3.06%** | 7.5% | -3.24% |
| regime_adaptive (research) | 06-13 → 07-20 | -0.85% | +0.21% | -1.06% | 7.0% | -1.85% |

### 1.2 master 当前持仓（07-20）

SGOV 44.3% ｜ HD 20.3%（**-5.2%**）｜ CAT 19.1%（**-11.1%**）｜ AGG 5.8% ｜ SPY 5.0% ｜ VEA 3.4% ｜ GLD 2.1%。

亏损几乎全部来自 CAT/HD 两只个股——它们是 P0-1 的直接产物（见下）。

### 1.3 目标权重快照（recommendation_snapshot, as_of 2026-06-30）

| sleeve | 计划权重 | 实际内容 |
|---|---|---|
| momentum | 0.40 | **CAT 0.20 + HD 0.20（两只个股！设计是 ETF 轮动）** |
| risk_parity | 0.30 | AGG/SPY/VEA/GLD 共 0.162 + **SGOV 0.138**（逆波动率给近零波动的 SGOV 46% sleeve 内权重） |
| satellite_us_quality | 0.20 | **SGOV 1.00**（0 持仓回落） |
| satellite_hk_china | 0.10 | **SGOV 1.00**（区域风险闸触发） |

SGOV 快照行 0.4381 = 0.20 + 0.10 + 0.30×0.46，三处防守回落互相叠加。上一季（03-31）同构：momentum 选了 GLD+**JNJ**（又是个股），us_quality 同样 SGOV。**至少连续两个季度，实际组合 ≈ 40% 两只个股 + 44% 现金。**

### 1.4 交易成本

master 5 周内 9 次调仓事件，成本合计 **$419 ≈ 0.42% NAV**（年化 ~5%）。回测假设 cost 1bp + slippage 2bp 单边（`trade/backtest/monthly.py:23-28`），paper 引擎收 5+5 bps（`paper/engine.py`），且信号 T→T+1 open vs paper 当日收盘成交——**回测与实盘的成本/执行模型不对称**，回测系统性乐观。

---

## 2. P0-1：momentum sleeve 的「月线参数 × 日线数据」bug（40% 仓位）

### 机制

- `MomentumParameters` 默认 `momentum_windows = 3/6/9 期（权重 0.4/0.3/0.3）`、`trend_window=3`（`trade/strategies/global_etf_momentum.py:28-33`）。窗口按 **bar 计数**（`_lookback_return` 取 `history[-periods-1]`，`:182-185`）。策略文档 `docs/strategy/01-global-etf-momentum-rotation.md` 的设计语义是 3/6/9 **个月**；本地/CI 的 fixture 恰好是**月线**，所以回测语义正确。
- 生产 `_load_scoring_records`（`workbench/backend/workbench_api/recommendations/precompute.py:223`）喂的是**日线**统一 CSV → 生产语义变成 **3/6/9 天动量 + 3 天均线过滤**，一个从未被任何回测验证过的高噪声信号，还按季度持有。
- 第二重污染：records = `price_universe()` = 15 ETF ∪ 27 个股（`data_refresh/refresh.py:199`），而 `generate_momentum_signal` 对传入的**所有** symbol 排名（`global_etf_momentum.py:96-101`，无 universe 过滤）→「全球 ETF 轮动」实际在 42 只混合标的里选 Top-2。

### 端到端复现（探针脚本见附录）

| 信号日 | 生产实际（日线+污染池） | 生产快照实录 | 设计行为（月线+ETF 池） |
|---|---|---|---|
| 2026-03-31 | **GLD + JNJ** | GLD + JNJ ✓ | DBC + SGOV |
| 2026-06-30 | **CAT + HD** | CAT + HD ✓ | EEM + QQQ |

复现与生产快照**逐符号一致**，bug 坐实。事后（06-30→07-17）：CAT/HD 均值 **-10.63%**；设计行为应选的 EEM/QQQ 均值 -6.53%（本窗口同样为负——修复的意义不在本季运气，而在于**现在跑的东西从未被验证过**，且 9 天动量在文献里更接近短期反转的负预测区）。

---

## 3. P0-2：us_quality sleeve 被 A 股数据静默毒死（20% 仓位）

### 机制（已在 VM 逐级定位）

1. B06x 起 A 股行情（1490 只）与美股共用一份统一 prices CSV；us_quality 的 `load_prices` 读**全文件**（VM 实测 1,774,428 行 / 1556 ticker）。
2. 因子在全 ticker 集上计算并 pivot 成宽表 → 日期索引是**中美交易日历的并集** → 美股列在 A 股独有交易日上是 NaN。
3. `low_vol`（`rolling(window, min_periods=window).std()`，`factors.py:183`）与 `trend`（`rolling(min_periods=ma_long)`，`:298-299`）要求满窗无洞 → **全 NaN**。VM 实测：`low_vol non-nan=0`、`trend non-nan=0`（momentum/quality/value 尚存活，但 percent-rank 是在 1500+ 只混合市场标的里排的，语义也已错误）。
4. 复合分全 NaN → top-N 空 → `_resolve_child_weights` 的 superset/空值兜底回落 `{SGOV: 1.0}`（`master_portfolio.py:508-518`）——**兜底路径不算异常**，`sleeve_status` 照样写 `scored`，`data_source` 照样写 `real`。

### 交叉验证

- 本地镜像 VM 同一份 fundamentals + **仅美股 42 只**的 prices → 两个信号日均正常产出 **15 只持仓**；low_vol/trend 各 42 个非 NaN。
- VM 原环境（代码 md5 与 HEAD 逐文件一致、pandas 同版本）→ **0 持仓**。唯一差异就是数据里的 A 股行。
- 反事实成本：该 15 股篮子 06-30→07-17 **+3.39%**，而 sleeve 实际蹲在 SGOV +0.20%。

**这个 sleeve 的「实现验证」（B025 PASS）是在合成 fixture 上做的；真实数据管道上线后它没有一天正常工作过的证据，也没有任何监控能发现它死了。**

---

## 4. P0-3 与其他运维缺陷

1. **regime_adaptive 目标冻结在 2026-05-29**：快照表里该策略只有一天数据；6-12 四次手动刷新全部 `missing price history for required asset QQQ`；月度 timer（每月 1 日）因 B107 迁移（timer 07-13 才装上）错过 7 月档期，下次 2026-08-01。一个卖点是「危机检测」的策略，7 周没看过一次市场。55% SGOV 的防守姿态是 5 月末的旧判断。
2. **监控盲区**：`monitoring_metric` 只有 cn_* 三策略（且 rolling_ic 全 NULL）；master/regime 无任何指标。B080 监控体系未覆盖 USD 账户 → 本报告的所有问题均无告警可见。
3. **workbench-advisor.service 持续 failed**（LLM advisor 402/配额，已知遗留），推荐页的 AI 解释层长期缺失；`recommendation_snapshot.rationale` 由 LLM 生成，全是「权重反映了已计算评分结果」式模板话术，**没有暴露 sleeve 回落 SGOV 的真实原因**——rationale 层在给错误行为刷合理性。
4. **hk_china 区域闸设计缺陷（非 bug）**：闸门只看 KWEB/MCHI/FXI 三个 proxy（`hk_china_momentum/factors.py:30,137`）。06-30 三者确实全破 200D MA → 整个 sleeve 进 SGOV；但 **ASHR 复合动量 +19.9%、r6m +10.7%、远在 200D MA 上方**，因不在 proxy 集合里被连坐。事后 FXI +8.0%、KWEB +9.6%。B063 早已记录该闸让 real 版「20/20 个季度全程压在现金里」——一个结构性几乎永远防守的 sleeve 不是 sleeve，是 10% 的死权重。

---

## 5. 即使全部修好，设计层还有什么问题

1. **没有任何组件在真实数据上证明过 edge**：B025 PASS = 合成 fixture；B092 US attack 真数据 first-look OOS Sharpe 1.45 < 等权 1.54（INCONCLUSIVE）；B093 hk_china 真个股 NO-GO；B106 组合层杠铃 NO-GO。master 基线回测 10.46%/Sharpe 1.222（116 月）依赖 fixture/proxy 混合与幸存者池。
2. **幸存者偏差**：us_quality 的 27 股 universe 是手挑的当今赢家（`data/fixtures/us_quality_momentum/universe.csv`）；B092 已确认此类池对动量类策略产生系统性高估。
3. **Top-2 集中度**：40% 仓位只押 2 个标的，单标的 20% —— 即使按设计运行，特异性风险也过大。
4. **三条独立的 SGOV 瀑布**：momentum 的趋势过滤、us_quality 的兜底、hk_china 的区域闸互不知情，叠加出 44-55% 的常态现金仓——防守决策应该在组合层做一次，而不是三处各做一次。
5. **逆波动率池里放 SGOV**：近零波动资产在 inverse-vol 里必然吃掉 sleeve 近半权重，「稳定器」实际是现金增强。SGOV 应是残差资产，不应参与逆波动率分配。

---

## 6. 修复方案（建议批次 A：纯修复，不引入新策略）

优先级排序，全部有明确验收判据：

| # | 修复 | 要点 |
|---|---|---|
| F1 | momentum sleeve 数据语义 | 给 `generate_momentum_signal` 喂月末重采样序列（或把窗口换算成交易日 63/126/189 + 200D 趋势过滤，二选一、按原设计文档语义定）；**显式传入 ETF universe 白名单**，拒绝个股混入。加回归测试：日线输入下 3/6/9 月语义不变。 |
| F2 | us_quality 数据隔离 | 因子管道先按 universe 过滤再 pivot（27 股票池），滚动窗口对孔洞给出显式策略（US 日历重索引）；**空持仓回落 SGOV 时必须把 `sleeve_status` 标成 `fallback` 并告警**，禁止再报 `scored`。 |
| F3 | regime 刷新 | 补跑 regime precompute（QQQ 历史已具备，vintage 数据 data_end=07-17）；月度 timer 加 `Persistent=true` 校验 + 失败告警；危机检测信号改**每日评估**（调仓仍月度，评估≠交易）。 |
| F4 | 监控扩到 USD 账户 | B080 指标（NAV vs 基准、滚动超额、回撤、sleeve 现金占比、目标 staleness 天数）覆盖 master/regime；`as_of_date` 超过 45 天未前进 → 告警。 |
| F5 | 成本对齐 | paper 与回测统一执行/成本假设；调仓加最小交易阈值（drift band 已有，补 min-trade），杜绝 $17 级碎单。 |

批次 A 是**恢复已验证行为**，不需要新的策略裁定，工作量小、确定性高，应先行。

---

## 7. 更好的策略：研究与设计（批次 B 提案）

### 7.1 外部证据基线（每条经第二来源核验，样本内数字已打折看待）

| 策略族 | 证据 | 关键数字（净成本口径） | 启示 |
|---|---|---|---|
| GTAA / 趋势过滤资产配置（Faber 2007） | 2006-2025.03 **纯 OOS** 延伸测试（10bps 成本 + T+1 滞后） | OOS Sharpe **0.68**、CAGR 6.05%、MaxDD **-11.7%**（样本内 0.81/11.7%/-9.5%） | 衰减后依然稳健；**卖点是回撤控制而非跑赢 SPY**。这是诚实的天花板参照。 |
| GEM 双动量（Antonacci 2014） | 出版后 2014-2021 实测 | 5.89%/年、MaxDD -33.7%，2014-2022 **输给 S&P 买入持有** | **全进全出的单资产切换是脆性来源**——正是当前 hk_china 闸/三重 SGOV 瀑布的教训的文献版。 |
| HAA（Keller 2023，TIP 金丝雀） | 1971 回测 16.2%/Sharpe 1.49（**样本内**，出版仅 3 年） | 2022 类通胀市中金丝雀结构优于 GEM | 结构可借鉴（用通胀敏感资产做风险闸），数字不可信到那个量级；需自测。 |
| 波动率管理（Moreira-Muir 2017） | 103 策略大样本复制 | **OOS 无系统性 Sharpe 提升**，多数情形更差 | vol-target 只作为风控约束用，不作为 edge 假设（现有 regime_adaptive 的 target_vol 定位正确）。 |

诚实结论：这个约束集（advisory-only、无杠杆、无做空、月频、免费数据）下**不存在「稳定盈利」的免费午餐**；能拿到的是「牛市吃到大部分 β + 熊市把回撤压到 -10%~-15%」的风险管理型收益。任何承诺更高的候选都应先怀疑样本内过拟合。

### 7.2 设计提案：单核心「US-HK 防守型动量轮动 v2」

用**一个**连贯的核心替代现在四条互相踩脚的 sleeve：

- **Universe（8+1，全部现有免费数据）**：SPY、QQQ、VEA、VWO、MCHI（HK/中国敞口以 proxy 并入普通候选，落实 B093 永久边界）、IEF、TLT、GLD、DBC；防守残差 SGOV。
- **信号（月末，月线语义）**：复合动量 = 等权 blend(1/3/6/12 月收益)（13612 结构，降低单窗口过拟合）；**按资产**绝对动量过滤：复合动量 > 同期 SGOV 收益才可持有——防守是逐资产的连续量，不是全组合的二元闸（直接吸收 GEM 2014-2022 与 hk_china 20/20 蹲现金的教训）。
- **组合**：过滤后 Top-3~4，**逆波动率加权但排除 SGOV 参与分配**（修复 §5.5），未过滤部分自然落入 SGOV；单资产上限 35%。
- **执行**：月末信号、T+1 执行、3% tolerance band + 最小交易额，预期年换手 ~150-250%，5+5bps 下成本 ~0.2-0.3%/年。
- **风控**：保留账户级 15% kill-switch；vol-target 仅作上限约束（依据 §7.1 第 4 行，不指望它加 Sharpe）。
- **us_quality 卫星的处置**：B092 已证明选股不敌等权 → 修好 F2 后把 sleeve 降为**质量筛选池等权**（放弃 top-15 排名的伪精度）或直接并回核心，二选一交由对照回测裁定；不再投入选股因子调参。

### 7.3 验证协议（沿用本仓已沉淀的纪律）

1. ETF 数据无幸存者问题（B092 的付费数据前置条件不适用于此设计，可零成本推进）。
2. 回测 2007-2026（含 GFC/COVID/2022），成本对称（paper 同口径 5+5bps + T+1）；**全新 seed holdout**（B108 纪律：不得在看过的窗口调参）。
3. 硬门（沿 B092 先例）：**OOS Sharpe 必须 > 同 universe 等权 + 趋势过滤的朴素基线**，且 MaxDD < 60/40 基线；达不到就诚实 NO-GO，保持修复后的现状。
4. 通过后先替换 regime_adaptive 的 research 槽位 paper 跑 ≥1 季，再谈动 master。

### 7.4 建议开批清单（待用户确认，当前 B109 在跑，不撞车）

| 批次 | 内容 | 前置 |
|---|---|---|
| A（修复批） | §6 F1-F5 | 无，建议立即 |
| B（first-look） | §7.2 设计的 IC/回测探针 + 对照（等权、GTAA、现 master 修复版） | A 完成 |
| C（可选） | HAA 金丝雀结构（TIP 动量闸）作为 B 的变体对照 | B 同批可带 |

---

## 8. 附录：复现方法

- 探针脚本：`/private/tmp/claude-501/.../scratchpad/momentum_probe.py`（会话级目录，逻辑已完整记录于 §2）；输入数据 = VM `prices_daily.csv` 的 42 只美股子集。
- us_quality 复现：本地 `WORKBENCH_DATA_ROOT=<镜像目录>` 下调 `trade.strategies.us_quality_momentum.signal.generate_signal(params, date(2026,6,30))`（美股-only 数据 → 15 持仓）；VM 上同调用（全量数据 → 0 持仓）；因子级定位 `low_vol_score`/`trend_score` 的 `dropna()` 计数。
- 生产 DB 查询均为 `sqlite3 'file:...?mode=ro'` 只读；关键表：`paper_nav_history`、`paper_rebalance`、`recommendation_snapshot`（含 `master_meta.sleeve_status`）、`target_refresh_job`、`monitoring_metric`。
- 外部证据来源：Allocate Smartly（GTAA OOS 延伸）、dualmomentum.net 与第三方回测（GEM 出版后表现）、Keller & Keuning SSRN 4346906（HAA）、Moreira & Muir (JF 2017) 与 Cederburg et al. (JFE 2020) 103 策略复制。
