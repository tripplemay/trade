# B084 A股 ETF 时序趋势 first-look — 独立验收 SIGNOFF（Evaluator，代 Codex）

**日期：** 2026-07-05（UTC）
**验收者：** 独立 Evaluator（无实现上下文，最高怀疑度；授权=用户 /goal + B079–B083 先例；与实现完全隔离）
**HEAD = `ee59c07`；生产 release = `7d30073`**（`ee59c07` 仅改 features.json/progress.json，paths-ignore 不部署 → **部署代码 ≡ HEAD 代码**，含 migration 0039 + trial_backfill_b084 + F002 全部研究码）
**裁定：PASS → done**（3 features 全 PASS；**INCONCLUSIVE（LEAN-GO）确认** —— 本次审的是**证据质量**而非结论方向；数字全部独立复现，裁定与数字一致且偏保守）
**轮次：** verifying r1（本报告，round1 一轮闭环，无 fixing）

---

## 0. 裁定摘要

| 验收维度 | 结果 | 关键证据 |
|---|---|---|
| **趋势数字从零重实现抽验** | **PASS** | 独立脚本（groupby 面板 + 显式 shift + ddof=1）不 import 我方码 → full/OOS CAGR/Sharpe/MaxDD + 2022/2024 窗 + avg_n_held **全部逐位（4 位小数）吻合** |
| **震荡损耗口径核实（命门，最重）** | **PASS（+软观察 S1）** | 年度窗吻合；但**更细子窗独立复算揭示报告「未见震荡损耗」叙述偏乐观**——紧 2024-02 与 2022 年初趋势跑输持有（详 §1）。非阻断：与保守 INCONCLUSIVE 同向 |
| **参数先验无扫参** | **PASS** | 单一 `_LOOKBACK_M = 12`；grep 无 grid/sweep/loop/多窗备选 |
| **LEAN-GO→INCONCLUSIVE 映射一致性** | **PASS** | 趋势全面胜持有但 OOS Sharpe 1.14>full 0.566=窗口落位 → INCONCLUSIVE 为与数字一致的**保守**裁定；映射语义诚实、代码内注明 |
| **数据完整性 + 复权口径披露** | **PASS** | 13,359 行无重/负/NaN；**独立重 fetch 512890 = 逐行 0 差**；非复权（原始价）4 处诚实标注（B082 教训已接） |
| **migration 0039 生产落地** | **PASS** | 生产 DB `alembic_version=0039_b084_etf_trend_trial`；B084 trial 行 `bf-d68e1e96d89a0fc1 / INCONCLUSIVE` 已落 |
| **L1 门禁 + CI 绿 + HEAD≡prod + bootstrap lockstep** | **PASS** | root/backend ruff+mypy 全绿；b084 3 测 + bootstrap/trial 10 测过；main CI 三绿 + Deploy success；`_N_TRIALS + len(B084_TRIALS)` 同步 |
| **零回归** | **PASS** | cn_attack / dividend_lowvol / PEAD / strategy_modes 产品码改动 **0 行**；全部新增为研究脚本 + trial 播种基建 |

**软观察（非阻断，均已并入 LEAN-GO 强制要求的严验后续批）：** S1（报告「未见震荡损耗」叙述过强，子窗见趋势跑输）+ S2（换手/turnover 未显式量化，仅 avg_n_held 代理）。

---

## 1. 震荡损耗口径核实（命门，最重）

### 1.1 全部头条数字独立复现（不 import 我方脚本）
独立脚本 `scripts/research/b084_evaluator_independent_verify.py` 采**三处不同代码路径**：
(a) 月末面板用 `groupby(period).last()`（非 generator 的 `pivot_table`/`resample`）；
(b) 前向收益用显式 `panel.shift(-1)/panel - 1`（非 `pct_change().shift(-1)`）；
(c) Sharpe 用 `std(ddof=1)`。结果与 `trend_result.json` / `docs/test-reports/B084-etf-trend-ic.md` **逐位吻合**：

| | full CAGR | full Sharpe | full MaxDD | OOS Sharpe | OOS MaxDD |
|---|---|---|---|---|---|
| 趋势（报告） | 0.1794 | 0.566 | −0.459 | 1.139 | −0.0765 |
| 趋势（独立） | **0.1794** | **0.566** | **−0.459** | **1.139** | **−0.0765** |
| 持有（报告/独立） | 0.1415 | 0.478 | −0.5322 | 0.488 | −0.2494 |

`months=163`、`OOS_n=49`、`avg_n_held=2.24`、`whipsaw_2022 {trend −0.0599, hold −0.0843}`、`whipsaw_2024H1 {trend 0.0711, hold 0.0739}` 亦逐位吻合。**趋势数字计算正确、可复现。**

### 1.2 前视/时点核查
`fwd = panel.shift(-1)/panel − 1`（t→t+1 前向）× `mom = panel/panel.shift(12) − 1`（≤t 已知）→ 信号用 ≤t 价、收益取 t+1，**无前视**。手工抽第 24 月核对：`mom(<=t)` 与 `fwd(t->t+1)` 取值来自不同时点，无交叠。前视单测 `test_b084_etf_trend`（signal≤t·收益 t+1·退现金）独立复跑 3 测全过。

### 1.3 ★震荡损耗——子窗独立复算揭示叙述偏乐观（软观察 S1）
报告结论段称「**未见评审警告的震荡损耗——月度 12-月动量是慢信号，whipsaw 小**」。年度/半年窗确实如此（2022 全年趋势减亏、2024H1 近平）。但 spec 命门点名的是 **2022 / 2024-02 型震荡切换期**——独立复算**更细子窗**后，损耗确实存在，只是被年度聚合抹平：

| 子窗 | 趋势累计 | 持有累计 | 趋势−持有 | 机制 |
|---|---|---|---|---|
| **2024-01..02（紧 2024-02 震荡，spec 点名）** | **+6.17%** | **+10.89%** | **−4.7pp** | 趋势平均仅持 1/5 ETF（半退现金）→ **踏空 2024-02 急反弹**（机会成本型损耗） |
| **2022-01..04（22 年初 whipsaw）** | **−14.01%** | **−8.97%** | **−5.0pp** | 慢信号滞后于 regime 切换、**带仓杀入下跌**再被甩打 |
| 2022 全年（年度聚合） | −5.99% | −8.43% | +2.4pp | 后半年退现金修复 → **净胜，掩盖上半年 whipsaw** |

**裁定：非阻断软观察。** 理由：(1) 全部数字诚实可复现，报告**并未隐藏**这些窗（2022/2024H1 原始数字在报，只是解读句偏乐观）；(2) 正式登记裁定 = **INCONCLUSIVE（保守）**，本子窗发现**与之同向**（进一步证据反对「强 GO」），不构成「数字达 GO 却标 INCONCLUSIVE」的方向性矛盾；(3) first-look = 证据一测非可配资。**建议并入严验后续批：分子年度/月度窗报震荡损耗，勿以年度聚合定论。**

---

## 2. 参数先验性（无扫参）

时序动量口径 = 单一先验 `price_t / price_{t-12m} − 1 > 0 → 持有否则退现金`，月度调仓。
`grep` `scripts/research/b084_etf_trend_ic.py`：仅 `_LOOKBACK_M = 12` 一个常量，**无 grid / sweep / optuna / best / argmax / 多窗 for-loop / MA 备选**。回看窗与入出场规则**先验定死、禁扫参 = 落实**。trial_registry 仅登记这一 config（DSR N=+1），未夹带未登记的候选窗。

---

## 3. LEAN-GO → INCONCLUSIVE 映射一致性（审证据质量非方向）

- **数字**：趋势在收益/夏普/回撤**全口径**胜等权买入持有（full Sharpe 0.566 vs 0.478，MaxDD −45.9% vs −53.2%）→ 满足 spec§2 F002「夏普>买入持有」的 GO **方向**。
- **未达 definitive GO 的硬证据**：OOS Sharpe **1.14 > full 0.566** ——OOS（后 30%≈2022–2026）恰含 2022 熊市，趋势防守正落此窗 → **窗口落位假象**（同 B070 教训），OOS>IS **非稳健证据**。叠加样本小（5 ETF/163 月/平均持 2.24）、非复权、full edge 温和（0.566 vs 0.478）。
- **映射语义诚实**：有效裁定集只含 `GO/NO_GO/INCONCLUSIVE/NA`；LEAN-GO（真实正向/防守 lean 但未达定论）→ **INCONCLUSIVE**，代码内（`trial_backfill_b084._build` 注释）明写理由，metrics summary 保留「LEAN-GO=推荐独立策略批严验再判可配」的 lean。**非「数字达强 GO 却压成 LEAN」，亦非「弱数字硬标 GO」——裁定与数字一致且偏保守。**

---

## 4. 数据完整性 + 复权口径披露

- **完整性**：`prices.csv` = 13,359 行 / 5 ETF（510300 2012- / 510500 2013- / 159915 2011- / 512890 2019- / 588000 2020-）。独立校验：`(date,ticker)` 重复 **0**、`close≤0` **0**、NaN **0**。与 F001 data-reality 报告「13,359 行 / 2011-12-09..2026-07-03」一致。科创 588000 短史（2020-11）诚实标注。
- **独立重 fetch 对照**：独立经 akshare `fund_etf_hist_sina('sh512890')` 重取 512890 → **1,805 行、区间 2019-01-18..2026-07-03、与本地缓存逐行 max abs diff = 0.0、0 处 mismatch**。数据落盘忠实反映 Sina 源。
- **复权口径**：Sina = **原始价（非 qfq 复权）**，在 IC 报告 caveat 3、F001 data-reality、trial params + caveat **共 4 处诚实标注**；报告注明「ETF 分红小、方向不受影响、绝对收益略偏」并将**复权口径列为严验后续批必做**（**B082 教训「ETF 价不含分红会低估」已接**）。first-look 用原始价算趋势方向合理。

---

## 5. migration 0039 生产落地 + 门禁 + HEAD≡prod + 零回归

- **迁移正确性**：`0039_b084_etf_trend_trial`（down_revision=`0038`，线性无分叉）。fresh sqlite `alembic upgrade head` → rc0，链 0038→0039，播种 **恰 1 条** B084 trial（`bf-d68e1e96d89a0fc1 / cn_etf_trend_first_look / INCONCLUSIVE / source_ref=docs/test-reports/B084-etf-trend-ic.md`）。幂等 guard `if t["id"] not in existing`；`downgrade` 反删。
- **生产落地（VM 只读 sudo 查证）**：生产 DB `/var/lib/workbench/db/workbench.db` → `alembic_version = 0039_b084_etf_trend_trial`；`trial_registry` 中 B084 行 = `bf-d68e1e96d89a0fc1 | B084 | INCONCLUSIVE`，**与本地 fresh-DB 确定性 id 逐字相同**。迁移已上生产。
- **HEAD≡prod**：生产 release symlink → `7d3007325...`（=`7d30073`，末个可部署 F002 commit，含 0039）；HEAD=`ee59c07` 仅 features/progress（paths-ignore 不触 CI/部署）→ **部署代码 ≡ HEAD 产品码**。
- **bootstrap lockstep**：`_import_trials` 已接 `B084_TRIALS`（`created_at=B084_TRIAL_STAMP`）；`test_bootstrap_cli._N_TRIALS` 已 `+ len(B084_TRIALS)`（B081「_N_TRIALS 需同步」教训落实）；trial id 确定性 content-hash（重跑幂等）。
- **门禁（本地复跑）**：root ruff `All checks passed` + b084 3 测过；backend ruff `All checks passed` + b084 模块 mypy `no issues` + bootstrap/trial 10 测过；migration 0039 fresh-apply rc0。main CI：Backend CI + Frontend CI + Python CI + Deploy 均 **success**（`7d30073`/`ecd891f` 推送）。
- **零回归**：`git diff 6ec88ca~1..ee59c07` 全部改动 = 研究脚本（`b084_etf_fetch.py` / `b084_etf_trend_ic.py`）+ 单测 + trial 基建（`0039` / `trial_backfill_b084.py` / bootstrap +9 行 / `_N_TRIALS` +1）+ pyproject `E501` 忽略（为新 trial 文件逐字 metrics 串，与 B081/B082/B083 同规）+ docs + 状态机 JSON。**cn_attack / dividend_lowvol / PEAD / strategy_modes 产品码 0 行改动。**

---

## 6. 诚实边界 / 遗留（并入严验后续批）

- **first-look = 证据一测，非可配资策略**（无 paper/红卡/生产模式，符合 spec§0）。**INCONCLUSIVE ≠「A 股 ETF 趋势无效」**——真实防守型 edge（减回撤为主）存在，但当前证据不足以定论可配。
- **软观察 S1（震荡损耗叙述）**：报告「未见震荡损耗」偏乐观；紧 2024-02（趋势 +6.2% vs 持有 +10.9%）与 2022 年初（趋势 −14.0% vs 持有 −9.0%）子窗趋势跑输。→ 后续批**分子年度窗**报损耗。
- **软观察 S2（换手未量化）**：spec F002 命门为「假信号损耗**+换手**」；报告报了分窗口损耗与 `avg_n_held=2.24`，但**未显式量化换手率/切换成本**。→ 后续批**量化 turnover + 施加切换交易成本**（ETF 无印花税但有佣金/冲击）。
- **严验后续批清单（LEAN-GO 触发）**：CPCV-lite + 更多 ETF（行业/更多宽基）+ **复权口径** + 更长/多 OOS 窗 + **分子窗震荡损耗 + turnover 成本**，确认 OOS>IS 非纯窗口落位后再判可配。

---

## 7. 结论

**B084 A股 ETF 时序趋势 first-look 3 features 全 PASS → done。** 趋势数字经**独立异路径**从零重实现，full/OOS/分窗口全部 4 位小数吻合；参数单一先验无扫参；数据 13,359 行完整、独立重 fetch 逐行 0 差、非复权诚实披露（B082 教训已接）；migration 0039 生产落地（生产 DB alembic=0039 + B084 INCONCLUSIVE 行落地实测）+ 门禁全绿 + HEAD≡prod + bootstrap lockstep + 零回归。**INCONCLUSIVE（LEAN-GO）为与数字一致且偏保守的合法裁定。** 命门（震荡损耗）经独立子窗复算：报告叙述偏乐观但数字未隐藏、且方向与保守裁定同向 → **软观察非阻断**，并入严验后续批。

复现物：`scripts/research/b084_evaluator_independent_verify.py`（独立异路径复算 + 子窗震荡损耗 + 前视核查）、本 signoff。
