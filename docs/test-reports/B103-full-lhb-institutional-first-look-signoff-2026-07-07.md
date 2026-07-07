# B103 — 全 LHB 机构买入 (institutional-buying) first-look（用户 PRIMARY 信号）Signoff

> 状态：**Evaluator 验收通过 → done**（progress.json status=verifying → done）
> 触发：B103 F001（generator + Workflow build）交付，F002 = Codex 独立验收（本报告）
> 裁定：**全 PASS 2/2 → done**（INCONCLUSIVE 裁定成立：粗糙免费 tag ≈ NO-GO，精确机构净买 ¥ +0.20 IC 正但薄 → ¥200 成**定向确认**测试，非 fishing）
> Evaluator：独立验收，与实现完全隔离，最高怀疑度（代 Codex 执行；授权=用户 /goal + B079–B102 先例）
> ★本批直接触及用户首要目标（日频 LHB 机构席位=聪明钱）且对 Tushare ¥200 采购决策有直接影响，验收格外扎实。

---

## 0. 一句话结论

F001 交付的**免费全 LHB 机构买入 first-look**（复用 B094 缓存 52,337 事件，补上 B094 只测游资、B077 只测 b070 大盘 19% 的双缺口）是一次**方法严谨、覆盖诚实、裁定得当且 nuanced 的 INCONCLUSIVE**。
**报告全部数字用我独立复跑逐位吻合**（我直接跑 probe 并解析 JSON，非信 generator 自报）：覆盖 12,502/52,337=**23.9%** / 35 月；粗糙 `inst_buy_flag` 全 horizon 平（|t|<0.6）；`inst_count`（有符号家数）N5/N10 **显著负**（t=**−2.74/−3.49**）；精确 `inst_buy_net` N5 **+0.205 t=2.22** 但仅 **232 对 / 26 月 / ~9 名/月**；follow 回测 edge 全非正（N10 −0.76% t=−1.70）；crosscheck 方向一致率 89.3% / rank-IC(count,net)=+0.368——**全部对上，逐位复现**。
无前视沿用 B094 verbatim 已验机制（`bisect_right` 严格晚于上榜日 T），我另抽 3 个真实事件手核入场日严格 > T。
**★★命门 1（覆盖 vs B077 + Tushare 含义）成立**：这次免费**仍是覆盖受限**（23.9%，非近全覆盖），故 ¥200 全覆盖仍是决定性未测；但**粗糙 N家机构 tag 的问题这次已被回答（NO-GO）**——¥200 不是重测粗糙 tag，而是**定向 confirm/kill 精确 inst_buy_net 的 +0.20**（免费只凑出 232 对薄样本）。报告对"免费 INCONCLUSIVE 对 ¥200 意味着什么"的表述**诚实、既不误导用户白花也不误导白省**（见 §3 命门 1）。
我另做**独立 fragility 压测**：+0.20 由 5–11 名/月的横截面构成，逐月 IC 在 ±0.9 间剧烈跳动，**26 月仅 15 月为正**——**证实报告"treat §2c as hypothesis, not result"的诚实定性**。
研究码零产品回归，CI 双绿 + Workbench Deploy 成功（HEAD 已上 prod），L1 **16 passed**。**签收 PASS。**
三条非阻断软观察（B099 及时性层未显式讨论 / 程序化 verdict 只吃 flag 未吃 count+net / 复算 json 未落盘）见 §4。

---

## 1. 批次与交付

| 项 | 值 |
|---|---|
| 批次 | B103 = 全 LHB 机构买入 first-look（用户 PRIMARY 信号=日频 LHB 机构专用席位净买；复用 B094 缓存补 B094 只测游资 / B077 只测 b070 19% 的双缺口）|
| F001（executor:generator） | 免费机构信号在全 LHB 上重测 → **INCONCLUSIVE**（粗糙 tag ≈ NO-GO，精确 ¥ +0.20 IC 薄）。commit `34767a4`（impl）/ `851a0f2`（mark done→verifying）|
| F002（executor:codex） | 本次独立验收 + signoff |
| 类型 | research-only（无生产码 / 无 broker / 无付费数据 / 无真金）|
| 交付物 | `scripts/research/b103_lhb_inst_ic.py`、`tests/unit/test_b103_lhb_inst.py`、`docs/test-reports/B103-lhb-institutional-first-look.md`（复用 B094 缓存 `data/research/b094_youzi/{events,prices,seats_sample}.csv`，无重 fetch）|

---

## 2. 验收方法（不信任 generator 自报，逐项独立复核）

本机 B094 缓存齐全（`events.csv` 52,337 行 / `prices.csv` 950,982 行 / `seats_sample.csv` 800 行）→
**在真实 52k 事件面板上独立复算，非 fixture-only**。我直接 `.venv/bin/python` 跑 probe 并解析其 JSON 输出，逐表与报告核对（bit 级吻合）；
另**独立实现**逐月 IC / board 覆盖分解 / +0.20 fragility 压测 / 3 事件 PIT 手核，不依赖 generator 自报。
无前视核心（`forward_returns` 的 `bisect_right` 严格晚于 T）**沿用 B094 已验模块**（B094 signoff 已锁），B103 只加机构 tag 解析层。

---

## 3. 逐项裁定

### ★★命门 1 — 覆盖率 vs B077 + 对 Tushare ¥200 决策的含义（本批最关键）：**PASS**

**核查问题：B103 免费这次解决了 B077 的覆盖缺口吗？免费 INCONCLUSIVE 是否让 ¥200 变得不值得 / 或已回答 PRIMARY 信号无 edge？**

**A. 覆盖率如实核对（我独立复跑，与报告逐项吻合）：**

| 指标 | B077（付费等价先例）| **B103（本批免费）** | 报告是否诚实披露 |
|---|---|---|---|
| 事件宇宙 | b070 去偏（大中盘 only）| 全 LHB akshare 52,337（全 A 股 2022-2024）| ✅ §1 |
| **价格覆盖率** | **19.2%** | **23.9%（12,502/52,337）** | ✅ §1/§5/§6 明标 |
| 覆盖缺口性质 | **结构性**：小盘 physically 不在 b070 去偏价格里 | **部分 fetch**：仅 B094 抓取的 1,279/5,167 只 ticker 有价 | 报告述"cached prices covers B094-fetched subset"✅ |
| 覆盖子集 cap 分布 | 大中盘倾斜（漏 zz1000/微盘）| **跨全板**（SH主板 418 / SZ主板 392 / ChiNext 216 / STAR 134，含小/中盘）| 未显式分解板块（软观察外，非阻断）|
| 打分月 | — | **35 月**（粗糙信号）/ **26 月**（精确 ¥ 薄）| ✅ §2 |

**我独立核对的板块分解（报告未列，我补算）**：covered 1,279 ticker 横跨 SH主板/SZ主板/ChiNext/STAR，**非** B077 那种"大盘 only"结构偏；uncovered 3,888 ticker 亦横跨全板（含 BJ/NEEQ 231，covered 0）。→ **B103 的 24% 比 B077 的 19% 更具代表性**（含小/中盘），但**仍只 ~24%**，且**免费 feed 仍漏退市名（幸存者偏）+ BJ 全缺**。

**B. 精确 ¥ 信号的覆盖是决定性薄点（我复跑坐实）**：`inst_buy_net`（唯一酷似付费产品的信号）只有 **232 对 / 26 月 / ~9 名/月**——因它只存在于 800 事件 seats 样本 ∩ 有价月。粗糙 `flag`/`count` 则覆盖 12,502 事件 / 35 月（其中机构买入事件 covered 2,711）=**样本充分**。

**C. ★对 Tushare ¥200 决策的诚实含义（本批验收核心把关）：**
- **属团队 lead 情形 (b) 的精修版**：B103 **仍覆盖受限**（~24%，非近全覆盖），故 ¥200 的**全覆盖 + 退市幸存者 + 全史 2005+ 仍是决定性未测**——免费没有、也无法有近全覆盖。**报告未夸称"已解决覆盖"**（§1/§5/§6 三处 foreground 23.9%）。
- **但有关键精修**：**免费的"粗糙 N家机构 tag"这条路这次已被回答 = NO-GO**（binary 平 + count 显著负 t=−2.74/−3.49，follow edge 全非正）。所以 **¥200 不是去重测粗糙 tag**（那已否），而是**定向 confirm/kill 精确 inst_buy_net 的 +0.20**（免费只凑 232 对薄样本、方向且与粗糙 count 相反）。
- **报告表述诚实、双向不误导**：
  - **不误导白花**：报告明写 +0.20 "statistically fragile (n≈232)"、"treat §2c as a hypothesis, not a result"、"This does not settle it"——**不承诺 ¥200 会找到 edge**，只说结局真实不确定、唯付费能仲裁。我的独立 fragility 压测（26 月仅 15 月正、逐月 IC ±0.9 剧烈跳、每月仅 5–11 名）**坐实这份薄弱定性无夸大**。
  - **不误导白省**：报告**不宣称 PRIMARY 信号已死**——因唯一酷似付费产品的精确 ¥ 信号在覆盖子集上是**正向**的，免费数据无法据此劝退。
- **裁定**：INCONCLUSIVE（而非干净 NO-GO）**符合覆盖-门控原则**（thin-coverage 的决定性信号不得断言无效）。¥200 的独立价值 = **精确席位 ¥（~50× 样本）+ 全覆盖（含当前 ~76% 无价事件）+ 退市幸存者**，定向验 inst_buy_net——这正是报告 §5 的表述，**与实测吻合，不误导**。

### 命门 2 — PIT 无前视：**PASS**

- 机制：`forward_returns` 中 `entry = bisect_right(dates, event_date)` = 严格晚于 T 的首个交易日；`exit = entry+N`；forward ret 严格 > T。上榜名单 T 盘后披露→tag 于 T 收盘已知→T+1 入场，**无前视**。沿用 B094 已验模块。
- 单测：`test_entry_is_strictly_after_event_date` / `test_entry_uses_close_after_event_not_on_event_day` / `test_event_after_last_bar_yields_none` / `test_build_cohorts_entry_strictly_after_T`（只有 ≤T 数据的事件→零覆盖）全过。
- **我独立抽 3 个真实机构买入事件手核**：`000498.SZ` T=2022-01-27→entry 01-28（严格>T ✓）；`000530.SZ` T=2022-01-11→entry 01-12（✓，出现两次=events.csv 同日重复触发行，报告 §4 已注）。**入场严格晚于上榜日，无当日/前视**。

### 命门 3 — 与 B099 及时性发现的关系：**PASS（含软观察 S1）**

- B099 证机构**建仓季度滞后**是元凶（免费研究吸收时信号已陈）。B103 测的**日频 LHB=及时**对照。
- **本批实证回答**：日频（及时）的**粗糙**机构 tag 仍 **NO-GO**（binary 平 + count 显著负）→ **及时性单靠免费粗糙 tag 不能救**这条假设；但**精确 ¥（及时+精确）** 的 +0.20 薄正**留住** ¥200（及时+精确+全覆盖）这条待验路径。
- **软观察 S1（非阻断）**：报告 §5 关系表只列 B077/B094/B103，**未显式接上 B099 的"季度滞后 vs 日频及时"这层**。这不改 INCONCLUSIVE 裁定与任何数字，但对用户 ¥200 决策而言，若明写"及时性只在配精确 ¥ 时才可能救、单靠免费粗糙 tag 的及时性无 edge"会更完整。记为软观察，不阻断签收。

### 命门 4 — 禁扫参 / 零回归 / L1 / CI / HEAD≡prod / 对抗验证：**PASS**

| 子项 | 证据 |
|---|---|
| 禁扫参（无择优）| grep probe 无 grid/threshold-list/arange/linspace/product/for-thr 等扫参；固定 HORIZONS=(1,5,10) + 固定 IC 门槛（复用 B094 常量）|
| 零产品回归 | `git diff 81bad04^..HEAD -- trade/ workbench/` **空**；F001 commit 仅 3 文件（报告+probe+测试，791 insertions），全 research-only |
| L1 单测 | `pytest tests/unit/test_b103_lhb_inst.py -q` → **16 passed**（含 3 PIT + 5 tag 解析 + rank-IC + crosscheck + judge NO-GO/GO 门）|
| CI 绿 | F001 commit `34767a4`：Python CI **success** + Workbench Backend CI **success**；HEAD `f67332e` Python CI success |
| HEAD≡prod | Workbench Deploy **success**（无产品码变更，prod 与 HEAD 无产品发散；研究文件不部署）；Prod Canary success |
| 对抗验证抽复核 | generator handoff 报 2 对抗验证 CONFIRMED survived；**我独立复跑每一数字 bit 级吻合**（coverage/4 组 IC/follow/crosscheck/verdict 全对上）+ 独立 fragility 压测坐实 +0.20 薄弱——对抗结论成立 |

---

## 4. 非阻断软观察（记录，不影响签收）

- **S1（及时性/B099 层）**：报告未显式接上 B099"机构建仓季度滞后=元凶"与 B103"日频及时"的对照。实证已回答（及时粗糙 tag 仍 NO-GO；及时精确 ¥ 薄正留住 ¥200），但显式讨论会更利用户 ¥200 决策。不改裁定/数字。
- **S2（程序化 verdict 口径）**：`judge()` 的 INCONCLUSIVE 只吃 `ic_flag`（binary）+ follow-edge，**不吃**显著负的 `ic_count` 与正的 `ic_net`。程序化标签因此**比正文薄**；但报告正文正确 foreground 了 count 显著负与 net 正的分歧——**正文比机械 verdict 更诚实**，非缺陷，仅记口径。
- **S3（复算 json 未落盘）**：probe 无 `--out` 落盘的 json 进 git；报告 .md 承载全部数字，我已 bit 复现（直接跑 probe 解析 JSON）。与 B102-S3 同族。

---

## 5. 裁定与状态机

**全 PASS 2/2 → done。** INCONCLUSIVE 裁定成立且 nuanced 得当：粗糙免费机构 tag ≈ NO-GO（binary 平 + count 显著负 + follow edge 全非正），精确机构净买 ¥ +0.20 IC 正但薄（232 对 / 26 月，我压测坐实 fragile），免费无法仲裁 → ¥200 成**定向确认 inst_buy_net** 的干净测试（~50× 样本 + 全覆盖 + 退市幸存者），**非 fishing**。

**★对 Tushare ¥200 决策的一句话诚实含义（供用户）**：免费全 LHB 这次**仍只 ~24% 覆盖**（比 B077 的 19% 更跨板但仍非近全），所以 **¥200 的全覆盖仍是决定性未测**；不同的是**粗糙"N家机构"这条免费路已被否（NO-GO）**，¥200 的独立价值已收窄为**精确席位 ¥ 在全覆盖 + 退市 + 全史上定向 confirm/kill 那条 +0.20 的薄正信号**——**这 ¥200 既没被免费结论证明白花（+0.20 是活的待验假设），也没被证明可省（免费无法否定精确 ¥）**。用户若追 PRIMARY 信号，¥200 仍是唯一干净决定性一测。

**后续状态机**：progress.json status=done / completed_features=2 / current_sprint=null / completed_date=2026-07-07；features.json F002=done；project-status.md 覆盖写。

---

## 6. 复现命令

```bash
# 独立复跑 probe（本机 B094 缓存）
.venv/bin/python scripts/research/b103_lhb_inst_ic.py | python -m json.tool
# L1 单测
.venv/bin/python -m pytest tests/unit/test_b103_lhb_inst.py -q   # 16 passed
# 零产品回归确认
git diff --stat 81bad04^..HEAD -- trade/ workbench/              # 空
```

**Gates:** `ruff check` clean（F001 报告述）；`pytest` 16 passed（我复跑）；Python CI + Workbench Backend CI + Workbench Deploy 全 success。
