# B082 红利低波防守腿 — 独立验收 verifying r1（Evaluator，代 Codex）

**日期：** 2026-07-05（VM 时区 UTC）
**验收者：** 独立 Evaluator（无实现上下文，最高怀疑度；授权=用户 /goal + B079–B081 先例）
**被验收提交：** F001 `f7854e8`/`4048f8e`、F002 `5f82bee`/`0c11175`/`307e0c4`、F003 `9950e5f`/`c772cfb`/`9d2b3d4`/`71764e4`
**HEAD = 生产 release = `71764e4`**
**裁定：FIXING（1 项实质问题：生产 live 数据从未落地 → 模式在生产端非功能态）。代码与回测审计全面 PASS，唯生产端到端不可验证。**

---

## 0. 裁定摘要

| 维度 | 结论 |
|---|---|
| F002 回测数字（研究员级审计，核心） | **PASS**（独立重实现逐位复现） |
| 利差三档阈值先验性（不变量①，禁扫参） | **PASS**（无 grid/optimise 路径，单一 param bundle） |
| TR−PR 股息率反推手算对照 | **PASS** |
| 2024-02 口径更正核实 | **PASS**（真 HS300 −6.1% 独立复算证实） |
| 探针抽验（独立重 fetch） | **PASS**（512890/CN10Y 深度逐一对上） |
| 单测 + 门禁 + CI | **PASS**（27 trade + 34 backend + 68 safety；CI 三绿；deploy success） |
| 卡片/registry/migration（生产 DB） | **PASS**（alembic 0037 / trial B082=6 / OOS card validated=0·mixed） |
| B081 carried soft-watch | **DB 卡片已资本条件化（修复到位）**；live 快照待 03:40 timer 自愈（保留） |
| 零回归（cn_attack/master/regime） | **PASS**（B082 未触 cn_attack 产品码；cohort 单测锁定字节不变） |
| no-execution 守门 | **PASS** |
| **生产模式端到端（快照/paper/live 档位）** | **FAIL — 不可验证**：F001 akshare CSV 从未落地生产（见 §7） |

---

## 1. F002 回测数字研究员级审计（核心，B081 教训重点）

**方法：** 用独立脚本 `scripts/research/b082_evaluator_independent_audit.py`（纯 pandas，**不 import** `trade.backtest` 引擎，从零重实现股息率反推/利差/三档规则/T+1 月度模拟/窗口回撤），读同一冻结快照 `data/research/b082/`，与 generator 引擎 + 报告三方对照。

**结果：逐位一致。**

| 指标 | generator 报告 | 我独立重实现 |
|---|---|---|
| 主口径 三档策略 CAGR | 7.49% | **7.4859%** |
| 主口径 三档策略 MaxDD | −40.5% | **−40.5072%** |
| 主口径 买入持有 CAGR | 10.64% | **10.6402%** |
| 主口径 买入持有 MaxDD | −66.2% | **−66.1655%** |
| tier counts（235 月末） | 79/32/124 | **79/32/124** |
| 2022 DD 策略/持有/HS300 | −12.4%/−13.5%/−28.7% | **−12.36%/−13.54%/−28.65%** |
| 2024-02 DD 策略/持有/HS300 | −5.4%/−5.4%/−6.1% | **−5.39%/−5.39%/−6.10%** |

同时 generator 脚本原样重跑（读冻结快照）→ 输出与 `backtest_results.json` 及报告表格逐位吻合。

**结论一致性：** 策略 CAGR 7.49% < 持有 10.64%（**规则无收益增量**为真），MaxDD −40.5% vs −66.2%（**全周期削尾部 +25.7pp** 为真）。`oos_result=mixed`、卡片文案「规则减回撤不增收益」忠实于数字。✅

### 1.2 阈值先验性（不变量①，本批最硬）
- `trade/strategies/cn_dividend_lowvol/parameters.py`：三档阈值 2.5%/1.5% + 权重 0.25/0.5/1.0 为**模块常量**（frozen dataclass 默认值），`__post_init__` 强制 tier 单调，无任何搜索。
- grep `sweep|optimise|grid|search|scan|tune|argmax|maximize` 命中仅：docstring（声明"无扫参"）、`engine.py` "per-capital scan（10万/100万）"（本金双跑非阈值搜索）、`np.searchsorted`（T+1 日期映射）。**无阈值优化路径。** ✅
- 回测/producer 全程只构造一个 `CnDividendLowvolParameters()`（默认），从不变 `saturated_spread_pct`/`half_spread_pct`。

### 1.3 TR−PR 股息率反推手算（一点对照）
2026-07-03：TR(H20269) 23568.76→21943.08（−6.8976%），PR(H30269) 11532.38→10195.28（−11.5943%）；additive divy = (−6.8976)−(−11.5943) = **4.6967%**（series 值一致）；利差 = 4.697 − 1.746(10Y) = **2.950%** → 满配（与 `spread_latest 2.95` / `target 1.0` 一致）。✅

### 1.4 2024-02 口径更正核实
报告更正 spec 引用「2024-02 HS300 −11.2%」为小盘（中证500/1000）踩踏口径，真 HS300(sh000300) 同窗 −6.1%。**独立从冻结 hs300.csv 复算 = −6.1046%，证实更正本身正确。** ✅

---

## 2. 探针抽验（独立重 fetch，对照 F001）

本机 akshare 1.18.64（与探针同版本）独立重 fetch：

| 序列 | F001 报告 | 我独立重 fetch |
|---|---|---|
| 512890 ETF(sina) | 1805 行，2019-01-18→2026-07-03 | **1805 行，2019-01-18→2026-07-03（完全一致）** |
| CN 10Y(chinabond) | ≥5y，最新 2026-07-03 | **latest 1.7463**（与冻结快照 spread 用的 1.746 一致） |

（CN10Y 端点原始起点 2002-01-04/6119 行 vs 报告 "2005-01 起/5375 行"——报告为可用窗口口径的行数差异，深度 ≫5y、最新值一致，GO gate 稳健。软记，不影响裁定。）✅

---

## 3. 单测 + 门禁 + CI

- `tests/unit/test_cn_dividend_lowvol_{parameters,signal,engine}.py`：**27 passed**（三档边界/阈值不可变/TR−PR 手算/手数取整/T+1 无前视）。
- backend `test_cn_dividend_lowvol.py`+`test_b082_dividend_lowvol_card.py`+`test_cn_dividend_lowvol_mode.py`：**34 passed**（含 `test_paper_build_succeeds_once_etf_marked`、`test_monitored_cohort_adds_dividend_lowvol_keeps_master_regime_out`、`test_cli_env_guard_blocks_before_run`）。
- safety `test_snapshots_request_self_contained.py`+`test_market_scheduler_scope.py`：**68 passed**（no-execution / scheduler scope）。
- CI（HEAD `71764e4`）：Workbench Backend CI ✅ / Frontend CI ✅ / Deploy ✅。

---

## 4. 生产 DB（VM 只读，sqlite `/var/lib/workbench/db/workbench.db`）

- alembic head = **`0037_b082_dividend_lowvol_card`** ✅
- `trial_registry` B082 = **6 行**（主口径 策略/持有 + 可实施双本金 × 策略/持有）；抽 1 行 metrics 与报告逐位吻合（CAGR 7.49%/Sharpe 0.590/MaxDD −40.5%/OOS_CAGR 6.34%/OOS_DD −18.1%/turnover 42.95/rebal 166/CPCV-lite K4 [−5.8%,16.8%,14.1%,8.5%]/DD2022 −12.4%/DD2024Feb −5.4%）✅
- `oos_verification_card` cn_dividend_lowvol = **validated=0 · oos_result=mixed · source=seed**；卡片文案诚实（「规则减回撤不增收益」「阈值 spec 先验、禁回测扫参」「−66%→−41%」「2022 −12% vs HS300 −29%」「这两窗口防守主要来自品种本身、非利差规则」「研究态、不可配资」）✅

---

## 5. B081 carried soft-watch（顺带核查）

- 生产 DB 权威卡片 cn_attack_pure/quality = **source=`b081_f005_capital_conditioned`**，`oos_cagr_range = "-16.0% @10万 / +27.1% @100万 (B081 纯保真 PIT)"` + 容量下限文案 → **资本条件化修复已在 DB 到位。** ✅
- 但 cn_attack **live 快照** master_meta.research_caveat 仍为旧文案（`-9%~-11%`/B066 ref）——因 03:40 UTC 自愈 timer 尚未触发（VM 时 01:55，timer 03:40）。**保留 soft-watch：DB 卡片正确，live 快照将于下次 03:40 timer 自愈。**

---

## 6. 零回归

- `git diff` B082 全程 **未触** `cn_attack_precompute.py` / `cn_attack_paper.py`。改动仅 `monitoring/metrics_job.py`（cohort 泛化）、`monitoring/tracking.py`、`paper/service.py`（PAPER_STRATEGIES 派生）、`strategy_modes/registry.py`（append）。
- `test_monitored_cohort_adds_dividend_lowvol_keeps_master_regime_out` 锁定 cohort=(quality, pure, dividend_lowvol)、Master/regime 排除 → cn_attack 两模式字节不变。
- 生产 recommendation_snapshot：cn_attack ×202 行(2026-07-03)、master(2026-06-30)、regime(2026-05-29) 均为 B082 前日期，未被扰动。✅

---

## 7. ★ISSUE-1（HIGH）— 生产 live 数据从未落地，模式在生产端非功能态

**现象：** VM `/var/lib/workbench/data/snapshots/dividend_lowvol/` **目录不存在**；`snapshots/` 下仅 benchmark/fundamentals/fx/market-context/news/prices/universe。因此 03:50 UTC 的 cn_dividend_lowvol precompute timer 将命中 `data_not_covered`（无 live 快照 / 无 paper 建仓 / 无 live 利差档位）。

**根因（代码+运维双证）：**
1. VM journal **全历史** 无 `dividend/lowvol/512890/h20269` 任何记录——dividend_lowvol refresh 步骤**从未在生产执行过**。07-03/07-04 的 data-refresh 虽 `data_refresh_done` 成功，但均无 dividend 步骤（wiring 今日随 B082 才部署）。
2. `data_refresh/cli.py::fetch_main`：`run_refresh(...)`（US/CN Tiingo 价格）在 **L237 无 try/except**；dividend_lowvol（akshare A股序列，与 Tiingo 无关）排在其**下游 L277**。fx/benchmark/universe 同样全在 run_refresh 之后。
3. 今日 01:30 UTC **首次带 wiring** 的 data-refresh 撞上 Tiingo 429 风暴，`run_refresh` 反复 429 backoff，服务 `ActiveState=activating` 已 25min+ 未结束——尚未到达 dividend_lowvol 步骤。若 run_refresh 最终抛错则整轮 abort，dividend_lowvol 今日不执行。

**影响：** F004 acceptance「生产模式端到端实测(快照/paper/面板/红卡)」中 **live 快照/paper/档位无法验证**（红卡本身已在生产 DB 且经 B080 机制渲染；registry 模式/timer/migration 均已部署可见）。

**代码正确性已被独立证实（问题仅在数据落地）：** 本机把**真实冻结快照**放入临时 data root，跑真生产 producer `score_cn_dividend_lowvol_target(as_of=2026-07-04)` → `{512890.SH: 1.0}`、sum=1.0、tier=full、spread 2.7589%、monitor 2026-07-03 2.95% full、caveat.validated=False。**给数据即工作端到端。**

**性质与右尺寸（供 Planner 裁定）：**
- 部分**环境性**：Tiingo 429 为 transient（07-03/04 正常）；正常 Tiingo 日 dividend_lowvol 会落地→模式自愈。
- 但**真实健壮性缺口**：A股防守腿数据不应依赖 US Tiingo 健康。Tiingo 故障日整个下游（含 dividend_lowvol）被静默跳过。
- **建议修复（generator）：** 将 akshare CN 系列（dividend_lowvol，建议连同 fx/benchmark/universe）与 `run_refresh` 失败隔离——把 run_refresh 调用包 best-effort try/except，或将独立于 Tiingo 的 CN 系列排在 run_refresh 之前，确保 A股数据在 US 价格源不健康时仍刷新。
- **备选（Planner 可选）：** 若判定纯环境性、接受 day-1 延迟，可观察下一个 Tiingo-健康刷新日 dividend_lowvol 落地 + 03:50 timer 产出 live 快照/paper 后由 evaluator 复验关闭（不改码）；排序脆弱性至少入 backlog。

---

## 8. 复现物

- 独立审计脚本：`scripts/research/b082_evaluator_independent_audit.py`（纯 pandas 重实现，读 `data/research/b082/`）。
- generator 回测脚本原样重跑：`scripts/research/b082_dividend_lowvol_backtest.py`（逐位复现报告）。
- 本机真实数据 producer 端到端：临时 data root + `score_cn_dividend_lowvol_target`（§7）。
