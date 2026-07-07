# B101 — smart-money 大股东/高管增持 first-look（免费公开增持披露）Signoff

> 状态：**Evaluator 验收通过 → done**（progress.json status=verifying → done）
> 触发：B101 F001（generator + Workflow build）交付，F002 = Codex 独立验收（本报告）
> 裁定：**全 PASS 2/2 → done**
> Evaluator：独立验收，与实现完全隔离，最高怀疑度（代 Codex 执行；授权=用户 /goal + B079–B100 先例）

---

## 0. 一句话结论

F001 交付的**免费大股东/高管增持 first-look** 是一次**方法严谨、裁定诚实的 NO-GO/INCONCLUSIVE**。
无前视处理（公告日滞后入场）经独立审计 **83/83 cohort 0 违规**、3 个具体 cohort 手工核对；
IC 数字**用我自写的独立实现逐位复算一致**（h20 meanIC=−0.0358 t=−1.58 完全吻合）；
**外推边界正确**——结论明确限定在**流动大盘子集**，**小盘 sleeve 未测的 caveat 完整保留**，
没有过度外推为"大股东/高管增持信号全体无效"。我另构造 look-ahead 对照（作弊版=交易月入场），
**发现即便用披露前时点也无 edge** → 坐实流动大盘的 NO-GO 是真空信号、非滞后 artifact，
且报告未错误归因于滞后。研究码零产品回归，CI 双绿，HEAD≡prod。**签收 PASS。**

---

## 1. 批次与交付

| 项 | 值 |
|---|---|
| 批次 | B101 = smart-money 大股东/高管增持 first-look（免费 `ak.stock_ggcg_em(symbol='股东增持')`，用户真实目标"跟随大资金"的免费内部人版）|
| F001（executor:generator） | 免费公开增持披露 first-look → **NO-GO（流动大盘无 edge）**。commit `0472146`（impl）/ `21d8c3c`（mark done→verifying）|
| F002（executor:codex） | 本次独立验收 + signoff |
| 类型 | research-only（无生产码 / 无 broker / 无付费数据 / 无真金）|
| 交付物 | `scripts/research/b101_insider_fetch.py`、`b101_insider_ic.py`、`tests/unit/test_b101_insider.py`、`docs/test-reports/B101-insider-buying-first-look.md` |

---

## 2. 验收方法（不信任 generator 自报，逐项独立复核）

本机数据缓存齐全（`data/research/b101_insider/{insider_events.csv(33,400 事件), prices.pkl(998 股×1957425 行), coverage.json, ic_result.json}` +
B070/B081 价格 cache 169MB），故**不是 fixture-only 验收，而是在真实 998 股 / 12,249 事件面板上独立复算**。
除复跑 generator 管线（证 bit 可复现），我**另写独立实现**（不 import generator 模块）重算，并**新增 look-ahead 对照实验**。

---

## 3. 逐项裁定

### ★★命门 1 — PIT 无前视（增持披露日 T+1 而非增持发生日）：**PASS**

- **结构证：** 事件按**公告月 M** 分 cohort，`cohort_entry()` 入场 = **月 M+1 首个交易日**，严格晚于该 cohort 内所有公告日；
  `forward_return()` 严格用 `price[entry+H]/price[entry]−1`（未来 bar）。`_MAX_ENTRY_GAP_DAYS=15` guard 防 pre-2018 公告 snap 到 cache 起点。
- **独立 PIT 审计（自写实现，全 83 cohort）：** **0 违规**——每个 cohort 入场日严格晚于该月最晚公告日。抽 3 个具体 cohort 手核：
  | 公告月 | 实际入场日 | 该 cohort 最晚公告日 | 入场晚于公告？ |
  |---|---|---|---|
  | 2017-12 | **2018-01-02** | 2017-12-30 | ✅ |
  | 2022-03 | **2022-04-01** | 2022-03-29 | ✅ |
  | 2026-04 | **2026-05-06** | 2026-04-30 | ✅ |
- **原始事件滞后核对：** 全 33,400 事件 `announce_date >= txn_end_date`（min_lag=0，无负）；抽样 `600805` lag=82d、`000759` lag=1d、`600322` lag=3d ——
  披露滞后真实且重尾（median 3d / mean 60.1d / p90 183d，coverage.json 核实）。**用增持发生日=前视=假 edge，本实现杜绝。**
- **单测有牙：** 14 个 L1 单测（含 `test_cohort_entry_strictly_after_announcement_month`、`test_cohort_entry_none_for_pre_panel_month_does_not_snap_forward`、
  `test_run_entry_after_all_cohort_announcements`）系统 venv 独立复跑 **14 passed**。

### ★★命门 2 — 外推边界（本批最关键）：**PASS**

**核查问题：报告是否把"流动大盘无 edge"过度外推为"大股东/高管增持信号全体无效"？小盘 sleeve caveat 是否保留？**

**结论：没有过度外推，边界表述正确且严谨。** 报告将结论**明确限定在流动大盘子集**，并**完整保留小盘 sleeve 未测 caveat**：
- 报告 §Verdict（L4-9）：*"no deployable edge in the **liquid tradeable universe** … even this most-promising free angle shows no reliable edge once the announcement lag is respected **on A-share liquid names**."*
- 报告 §5.3（L104-108）：*"Honest limitation — liquid tilt: the tradeable universe is B070's **liquid** subset (998 of 3,233 = 30.9%). If insider-buying alpha concentrates in **small, illiquid names** (plausible …), this liquid-only test could be washing it out. The **small-cap sleeve is untested** here."*
- 报告 §6（L110-126）：*"a **NO-GO for the free, liquid version** … It is **not proof the whole angle is dead** — two honest open doors remain: the **small-cap sleeve** … is untested … the separate **paid ¥200/day LHB** … is a separate decision."*

报告正确区分了**信号是否有效**与**在哪个宇宙测过**两个维度：流动大盘（998 股）NO-GO ≠ 全体无效；
增持信号在**信息不对称更大的小盘**可能更强，而小盘价格 cache 未覆盖 → 该门**诚实敞开**。与 B077（机构席位 80.8% 小盘未覆盖）、
B094/B099（覆盖限制）一脉相承。**这个 caveat 直接影响用户是否投入扩数据成本，其正确性经我下方对照实验进一步核实。**

### ★★命门 3 — look-ahead 对照独立坐实归因（我构造，超越 generator）：**PASS（强证据）**

报告称流动大盘无 edge 因"buy magnitude 无截面信息 + event tilt faint/非稳健"。我**独立构造对照**：把合规的**公告月入场**换成**交易月（变动截止日）入场**
（=能在公告前看到增持=作弊/前视版），复用同一价格面板对比：

| horizon | **COMPLIANT（公告月, PIT）** | **CHEAT（交易月, 前视）** |
|---|---|---|
| h20 | meanIC=**−0.0358** t=−1.58 excess=+0.0008 | meanIC=**−0.0179** t=−0.83 excess=+0.0018 |
| h60 | meanIC=**+0.0026** t=+0.12 excess=−0.0027 | meanIC=**−0.0006** t=−0.03 excess=−0.0004 |

**解读（关键，且与 B099 相反）：** 与 B099（作弊版 t>2 揭示"滞后杀死了活 edge"）不同，**这里即便作弊/前视时点也 meanIC≈0（|t|<1）**——
说明 magnitude 信号在流动大盘**本身就是真空**，NO-GO **不是滞后 artifact**。这有两重意义：
1. **佐证报告归因正确**：报告把 null 归于"magnitude 无截面信息 + tilt 非稳健"，**没有错误甩锅给滞后**（若甩锅给滞后=暗示砍延迟就能救活，会误导）。
2. **不冲击小盘 caveat**：我的对照只测流动大盘内的**时点**维度，小盘是**覆盖**维度、正交——对照既不证实也不证伪小盘门 → 小盘 sleeve 仍是合法未测门。

### 命门 4 — IC 独立复算 + 单调性 + GO 门槛纪律：**PASS**

- **自写独立实现逐位吻合：** 我**不 import** generator 的 b101 模块，用自己的 groupby/cohort-entry/forward-return 逻辑重算 h20 primary：
  meanIC=**−0.0358** t=**−1.580** eventExcessMean=**0.0008** hit=**0.518** —— 与报告表格**逐位一致**。
- **bit 可复现：** 复跑 generator 管线，输出与缓存 `ic_result.json` **逐字节 IDENTICAL**（真实 998 股面板，非 fixture）。
- **GO 门槛纪律（IC≥0.03 且 |t|≥2 且单调）：** 6 组（2 信号×3 horizon）max|meanIC|=**0.0358**，但 primary IC 5/20/60=[−0.019, −0.036, +0.003] **非单调（翻号）**、全 |t|<2 →
  **无一达标 → NO-GO/INCONCLUSIVE 是唯一正确裁定。**
- **措辞与数字匹配：** IC 全为**噪音级 ≈0**（|t|<2），报告用"no reliable edge / IC ≈ 0"措辞**准确**，未夸大为负 alpha。
- **event tilt 横向不一致诚实披露：** event excess 5/20/60=[+0.10%, +0.08%, −0.27%]，**60d 翻负**；magnitude book（按买入规模 top-quintile）全 horizon **LOSES**（−0.31%/−0.75%/−0.61%）。
  报告正确判定"真 edge 不该随 horizon 翻号 → 短窗噪音，扛不住成本"。诊断诚实。

### 命门 5 — 宇宙覆盖诚实披露 + 信号先验无扫参：**PASS**

- **覆盖诚实：** 增持宇宙 3,233 股 / 33,400 事件；∩ B070 流动子集 = **998 股（30.9%）**、12,249 可交易事件——报告**明确披露**这是 large/liquid tilt、小盘欠采样。
  价格宇宙由 B070 按 size/liquidity/quality 选取，**独立于增持信号** → 不构成信号偏倚。coverage.json 数字与报告逐项吻合。
- **信号口径先验性：** PRIMARY `buy_pct` = 每股当月 **占总股本比例** 之和（增持规模/信心）；SECONDARY `n_events` = 当月增持笔数（近退化，如实标 N/A）。
  来源 `ak.stock_ggcg_em(symbol='股东增持')`（买入-only feed，含变动截止日 + 公告日双日期）。先验 IC~+0.02..+0.05 在 docstring **声明一次**、写入 json `prior` 字段，**未回调到回测**。
- **无扫参（grep 核）：** 无 grid/sweep/optimize/tune/argmax；`_HORIZONS=(5,20,60)`、`_TOP_Q=0.20`、`_RET_SANITY=6.0`、`_MIN_XS=20`、`_MAX_ENTRY_GAP_DAYS=15` 均为**硬编码先验常量**；
  6 组全量报告非择优。无过拟合。

### 命门 6 — Workflow 对抗验证抽 1 复核 + 零回归 + L1 + CI + HEAD≡prod：**PASS**

- **对抗验证独立复现（超越抽查）：** 我未止于抽查 generator 的"2 对抗验证 CONFIRMED"记录，而是**独立复现并超越**：
  (a) 自写独立 IC 实现逐位吻合；(b) PIT 审计 83/83 cohort 0 违规 + 3 cohort 手核；(c) **新增** look-ahead 交易月对照（命门 3，generator 未做的定量证据）；(d) bit 可复现；(e) 原始事件滞后核对。
- **零回归：** F001 commit `0472146` 仅触 `docs/ + scripts/research/ + tests/unit/`，**产品码（trade/ workbench/）0 文件**（`git diff 43dcd9f..HEAD -- trade/ workbench/` = 空）；
  全仓 grep 无 b101 生产消费者；`.github/workflows` 无接线。research-only 坐实。
- **L1 抽查：** 系统 venv（Python 3.11）独立复跑 `pytest tests/unit/test_b101_insider.py` = **14 passed**；`ruff check`（3 文件）= **All checks passed**。
- **CI 绿（独立 gh 复核）：** `0472146` 的 **python-checks = success**（跑根 pytest+mypy trade+ruff，含 14 B101 测；scripts/tests 不在 paths-ignore→确实触发 Python CI）、**workbench-backend = success**。
- **HEAD≡prod：** 0 产品策略码改动 → 生产 HEAD 与仓库 HEAD 逐字节等价（trivially，research-only）。

---

## 4. 软观察（非阻断）

- **S1（小盘 sleeve 未测门真敞开）：** 价格 cache 为 B070 流动子集（69% 增持股=小盘/illiquid 未覆盖）。这是报告**自身诚实 caveat**，正确保留。
  要给"大股东/高管增持信号"下**全体**定论，需扩取小盘 qfq 价格重测——独立于本批的未来工作。非缺陷。
- **S2（look-ahead 对照为验收侧新增证据）：** 我的交易月 vs 公告月对照（坐实流动大盘 NO-GO 非滞后 artifact、佐证归因正确）是**验收侧新增**，未写入 F001 交付脚本。
  与 B099 命门 3 恰好互补（B099 揭示滞后杀活 edge；B101 揭示流动大盘信号本身真空）。非缺陷，为增益线索。
- **S3（复算 json 本机 gitignored）：** `ic_result.json` 经 `.gitignore:22 data/*` 忽略；报告 md 承载全部数字、脚本可确定性复现（本次已 bit 复现坐实）。非缺陷。

---

## 5. 最终裁定

| Feature | 裁定 |
|---|---|
| F001 — 免费大股东/高管增持 first-look（流动大盘 NO-GO / 无前视 / 小盘 sleeve 未测 caveat）| **PASS** |
| F002 — Codex 独立验收 + signoff | **PASS**（本报告）|

**全 PASS 2/2 → status=done。**

**含义（smart-money 免费信号四支已测尽）：**
1. 机构专用席位覆盖限（B077，LHB 免费席位噪/可马甲，80.8% 小盘未覆盖）；
2. 游资 first-look（B094 NO-GO）；
3. 机构建仓季度 first-look（B099 NO-GO，滞后是元凶）；
4. **大股东/高管增持 first-look（B101 NO-GO，流动大盘信号真空；小盘 sleeve 未测）**。
→ **四支免费"smart-money"角度在流动大盘均无可靠 edge**；未测=**小盘 sleeve**（需扩数据）+ 付费 **¥200/日 Tushare 日频 top_inst**（用户真实目标的决定性测试，仍待用户决策）。

---

## 6. 文件清单（本次验收产出/核对）

- 本 signoff：`docs/test-reports/B101-insider-buying-first-look-signoff-2026-07-06.md`
- 核对：`docs/test-reports/B101-insider-buying-first-look.md`（F001 报告）
- 核对：`scripts/research/b101_insider_fetch.py`、`scripts/research/b101_insider_ic.py`、`tests/unit/test_b101_insider.py`
- 独立复算数据：`data/research/b101_insider/{coverage.json, ic_result.json}`（gitignored 本机）
