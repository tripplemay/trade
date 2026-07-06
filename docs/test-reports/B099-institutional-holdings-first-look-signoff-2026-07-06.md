# B099 — smart-money 机构建仓 first-look（免费季度机构持股）Signoff

> 状态：**Evaluator 验收通过 → done**（progress.json status=verifying → done）
> 触发：B099 F001（generator + Workflow build）交付，F002 = Codex 独立验收（本报告）
> 裁定：**全 PASS 2/2 → done**
> Evaluator：独立验收，与实现完全隔离，最高怀疑度（代 Codex 执行；授权=用户 /goal + B079-B098 先例）

---

## 0. 一句话结论

F001 交付的**免费季度机构建仓 first-look** 是一次**方法严谨、裁定诚实的 NO-GO/INCONCLUSIVE**。
无前视处理（披露滞后入场）经独立审计 20/20 季 0 违规；IC 数字独立逐位复算一致；**"滞后是元凶"
的归因经我构造的 look-ahead 对照实验独立坐实**（作弊版 t=+2.44 显著 vs 合规 PIT 版 t≈0）；
且报告的**外推边界正确**——明确不把免费季度 NO-GO 过度外推为"¥200 日频 top_inst 也无效"。
研究码零产品回归，CI 三绿，HEAD≡prod。**签收 PASS。**

---

## 1. 批次与交付

| 项 | 值 |
|---|---|
| 批次 | B099 = smart-money 机构建仓 first-look（免费季度 `stock_institute_hold`，用户真实目标的免费季度版）|
| F001（executor:generator） | 免费季度机构持股变化 first-look → **NO-GO**。commit `d3fc880`（impl）/ `77c7247`（mark done→verifying）|
| F002（executor:codex） | 本次独立验收 + signoff |
| 类型 | research-only（无生产码 / 无 broker / 无付费数据 / 无真金）|
| 交付物 | `scripts/research/b099_inst_fetch.py`、`b099_inst_ic.py`、`tests/unit/test_b099_inst.py`、`docs/test-reports/B099-inst-building-first-look.md` |

---

## 2. 验收方法（不信任 generator 自报，逐项独立复核）

本机数据缓存齐全（`data/research/b099_inst/{inst_panel.csv, prices.pkl, coverage.json, ic_result.json}` +
B070/B081 价格 cache），故**不是 fixture-only 验收，而是在真实 20 季面板上独立复算**。

---

## 3. 逐项裁定

### ★★命门 1 — PIT 无前视（季报披露滞后入场）：**PASS**

- **结构证：** `entry_floor()` 把入场推到**披露截止日次月 1 日**（Q1→5/1、Q2→9/1、Q3→11/1、Q4/年报→次年 5/1），
  即合规披露 deadline 之后**再加整月**的保守下限；`forward_return()` 严格用 `price[entry+H]/price[entry]−1`（未来 bar）。
- **独立审计（抽 3+ 事件手工核对披露日 vs 入场日，实为 20/20 全审）：**
  | 季度 | 报告期末 | 披露截止 | 实际入场日 | 晚于截止？ |
  |---|---|---|---|---|
  | 2020Q1 | 03-31 | 2020-04-30 | **2020-05-06** | ✅ |
  | 2021Q1 | 03-31 | 2021-04-30 | **2021-05-06** | ✅ |
  | 2024Q2 | 06-30 | 2024-08-31 | **2024-09-02** | ✅ |
  | …全 20 季… | | | | **0 违规** |
  用报告期末入场=严重前视 → 本实现**杜绝**。审计脚本独立复现 `entry_after_deadline` 全 True。
- **单测有牙：** `test_entry_floor_strictly_after_disclosure_deadline_all_quarters` 等 12 测独立复跑 **12 passed**。

### ★★命门 2 — 外推边界（本批最关键）：**PASS**

**核查问题：报告是否把"免费季度 NO-GO"过度外推为"¥200 Tushare 日频 top_inst 机构席位也无效"？**

**结论：没有过度外推，边界表述正确且严谨。** caveat "不证伪 ¥200 日频" 真实存在于报告**两处**：
- 报告 §Honest frame（L21-27）：*"does **not** condemn the ¥200 daily version: the daily LHB feed
  is a genuinely different, much-lower-latency signal. The failure here is largely attributable to
  the **disclosure lag**, which the paid daily version specifically shortens."*
- 报告 §Verdict（L137-142）：*"lowers the prior that a cheap free-data path can capture … alpha,
  but does **not** refute the daily version — daily latency is a materially different (and testable)
  regime … a bounded paid trial."*

报告正确区分了**两个不同信号**：免费季度（滞后 45+ 天、低频）vs 付费日频 top_inst（T+1、LHB 机构专用席位）。
它把失败明确归因于**滞后**，而日频版恰恰砍掉滞后 → 免费季度 NO-GO 反而**佐证"及时性是关键"**，
不构成对日频版的证伪。**这个 caveat 直接影响用户是否花 ¥200，其论证经我下方对照实验进一步坐实。**

### ★★命门 3 — "滞后是元凶"归因独立坐实（我构造 look-ahead 对照）：**PASS（强证据）**

报告称"最可能的元凶=披露滞后"。我不满足于接受这一定性断言，**独立构造对照实验**：复用 F001 的
IC 管线，仅替换入场下限——把合规的"披露滞后入场"换成**报告期末入场（Q-end，用了尚未公开的持仓=作弊/前视版）**，
两版 IC 对比：

| 信号 | horizon | **PIT（合规滞后入场）** | **CHEAT（报告期末入场，look-ahead）** |
|---|---|---|---|
| 持股比例增幅（primary） | 63td（1季）| meanIC **−0.007**, t=**−0.59**（无 edge）| meanIC **+0.031**, t=**+2.44**（统计显著）|
| 持股比例增幅（primary） | 21td（1月）| meanIC +0.006, t=+0.70 | meanIC **+0.028**, t=**+2.32**（显著）|
| 机构数变化（secondary）| 63td | meanIC +0.007, t=+0.50 | meanIC +0.019, t=+1.35 |
| 机构数变化（secondary）| 21td | meanIC +0.006, t=+0.51 | meanIC +0.013, t=+1.20 |

**解读：** 当能在报告期末即看到持仓（无滞后），主信号有**统计显著 edge（t>2，IC≈+0.03，恰好命中 code
里写的先验 +0.03）**；但一旦按合规披露滞后入场，edge **完全消失（IC≈0）**。→ **归因坐实**：信号本身携带
真实信息，是**披露滞后吃掉了可交易性**，而非信号本身无信息。这既证明 F001 归因正确，又**独立强化外推边界**——
正因为"短延迟版有 edge、滞后杀死它"，砍延迟的 ¥200 日频版**确实不能被证伪**，反而值得一测。

### 命门 4 — IC 独立复算 + 单调性 + GO 门槛纪律：**PASS**

- **逐位复算一致：** 独立读 `ic_result.json` 并重跑 IC 管线，四组（2 信号 × 2 horizon）meanIC/t/hit
  与报告表格逐位吻合（primary h63 = −0.0072 / t=−0.586；per-quarter IC ∈ [−0.087, +0.148]，与报告一致）。
- **GO 门槛纪律（IC≥0.03 且 |t|≥2 且单调）：** 四组**无一达标**（最优 secondary h63 IC=+0.0069 远低于 0.03，
  t=0.50<2）→ **NO-GO 是唯一正确裁定**。
- **措辞与数字匹配：** 结果是**噪音级 ≈0**（|t| 全 <1），非"显著为负"→ 报告用"no reliable edge / rank-IC≈0"
  措辞**准确**，未夸大为负 alpha。
- **回测 +49% 幻觉诚实诊断（独立确认）：** primary h63 mean IC **为负（−0.007）**却有 **+49% 累计超额** +
  excess hit rate=0.45（掷硬币）。负截面 IC **不可能**产生持续的 long-only 正超额 → 报告正确判定为
  **beta/size tilt 幻觉（牛市季 long-only 漂移），非 skill**。诊断诚实。

### 命门 5 — 宇宙覆盖诚实披露 + 信号先验无扫参：**PASS**

- **覆盖诚实：** 20/20 季、49,193 行、4,995 股面板；价格宇宙 = B070/B081 无幸存者偏 PIT cache 交集
  = 1,267 股 = **25.4%（大盘/流动性 tilt）**——报告**明确披露**这是 large/liquid tilt、小盘欠采样，
  且诚实说明近零 IC 跨季对称翻号，不像覆盖 artifact。2024Q4 仅 346 股（部分披露）亦如实标注。
  价格宇宙由 B070 按 size/liquidity/quality 选取，**独立于机构建仓信号**→ 不构成信号偏倚。
- **无扫参（grep 核）：** `_HORIZONS=(21,63)`、`_PRIMARY/_SECONDARY`、`_TOP_Q=0.20` 均为**硬编码先验常量**；
  两 horizon、两信号是**全量报告非择优**（无 grid/sweep/optimize/tune/argmax）；先验 IC~+0.03 在 docstring
  声明一次、`prior` 字段写入 json，**未回调到回测**。无过拟合。

### 命门 6 — Workflow 对抗验证抽 1 复核 + 零回归 + L1 + CI + HEAD≡prod：**PASS**

- **对抗验证独立复现：** 我未止于抽查 generator 的"2 对抗验证 CONFIRMED"记录，而是**独立复现**三项关键对抗——
  (a) 无前视审计 20/20 季 0 违规；(b) 滞后归因 look-ahead 对照（上文命门 3）；(c) 回测幻觉负 IC+正超额矛盾。
  三项结论均与 generator 记录一致，且命门 3 的对照实验**新增了 generator 未做的定量证据**。
- **零回归：** F001 commit `d3fc880` 仅触 `docs/ + scripts/research/ + tests/`，**产品码（trade/ workbench/）0 文件**；
  全仓 grep 无 b099 生产消费者（uv.lock 命中为哈希子串误报）；`.github/workflows` 无接线。research-only 坐实。
- **L1 抽查：** 系统 venv（Python 3.11.15）独立复跑 `pytest tests/unit/test_b099_inst.py` = **12 passed**；
  `ruff check`（3 文件）= **All checks passed**。
- **CI 绿（独立 gh 复核）：** `d3fc880` 的 **Python CI = success**（跑根 pytest+mypy trade+ruff，含 12 B099 测）、
  **Workbench Backend CI = success**、**Workbench Deploy = success**（绿 CI 自动链式部署）。
- **HEAD≡prod：** 0 产品策略码改动 → 生产 HEAD 与仓库 HEAD 逐字节等价（trivially）。

---

## 4. 软观察（非阻断）

- **S1（覆盖 tilt）：** 价格宇宙 25.4% 为大盘 tilt，小盘机构建仓欠采样。报告已诚实披露，且近零 IC 的跨季对称翻号
  使其**不像**覆盖 artifact；但若未来要给日频版定论，全宇宙 qfq 重取会更稳。非本批缺陷。
- **S2（对照实验未入交付）：** 我的 look-ahead 对照（坐实滞后归因、量化 fresh 信号 t>2）是**验收侧新增证据**，
  未写入 F001 交付脚本。若用户决定推进 ¥200 日频决策，可把此对照沉淀为"latency-sensitivity probe"的雏形
  （报告 §Verdict 已建议此下一步）。非缺陷，为增益线索。
- **S3（先验 +0.03 与作弊版巧合）：** code 里写的先验 IC~+0.03 恰好命中**作弊版** fresh 信号 IC（+0.028/+0.031），
  而非出货的滞后版（≈0）。这**不是过拟合**——先验是对"机构信息 edge"的期望且显式声明"滞后会把它压到近零"，
  出货结果（≈0）低于先验即诚实的 no-edge 发现；作弊版命中先验反而说明先验本身准确。已核，无问题。

---

## 5. 最终裁定

| Feature | 裁定 |
|---|---|
| F001 — 免费季度机构建仓 first-look（NO-GO/滞后元凶/不证伪日频）| **PASS** |
| F002 — Codex 独立验收 + signoff | **PASS**（本报告）|

**全 PASS 2/2 → status=done。**

**含义（smart-money 免费信号三支已测尽）：**
1. 机构专用席位覆盖限（LHB 免费席位噪/可马甲）；
2. 游资 first-look（B094 NO-GO）；
3. **机构建仓季度 first-look（B099 NO-GO，滞后是元凶）**。
→ **免费路径三支均无可靠 edge**；用户真实目标的**决定性测试仍是付费 ¥200 Tushare 日频 top_inst**——
本批**不证伪**它，反而（经 look-ahead 对照）**佐证及时性是关键 → 值得一次有界的付费试验**。待用户决策。

---

## 6. 文件清单（本次验收产出/核对）

- 本 signoff：`docs/test-reports/B099-institutional-holdings-first-look-signoff-2026-07-06.md`
- 核对：`docs/test-reports/B099-inst-building-first-look.md`（F001 报告）
- 核对：`scripts/research/b099_inst_fetch.py`、`scripts/research/b099_inst_ic.py`、`tests/unit/test_b099_inst.py`
- 独立复算数据：`data/research/b099_inst/{coverage.json, ic_result.json}`（gitignored 本机）
