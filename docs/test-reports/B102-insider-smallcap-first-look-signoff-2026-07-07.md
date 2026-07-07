# B102 — Insider-Buying 小盘 sleeve first-look（收口免费 smart-money 探索）Signoff

> 状态：**Evaluator 验收通过 → done**（progress.json status=verifying → done）
> 触发：B102 F001（generator + Workflow build）交付，F002 = Codex 独立验收（本报告）
> 裁定：**全 PASS 2/2 → done**（NO-GO 裁定成立，正确 scoped 为"免费空间收口"，付费 ¥200 门保留）
> Evaluator：独立验收，与实现完全隔离，最高怀疑度（代 Codex 执行；授权=用户 /goal + B079–B101 先例）

---

## 0. 一句话结论

F001 交付的**免费大股东/高管增持 first-look 在小盘 sleeve 上的重测**是一次**方法严谨、覆盖诚实、裁定得当的 NO-GO**。
IC / 回测 / 净成本三张表**用我自写的独立实现（不 import generator 的 `run()`）逐位复算完全吻合**
（h5 meanIC=+0.0863 t=1.184 / h20 +0.0345 / h60 −0.0020；eventCum/baseCum/excess 及 30/50/80bp 网格全对上），
且 `ic_result.json` 复跑**逐字节可复现**。无前视处理沿用 B101 verbatim 核心（公告月 M+1 入场），我另做 **3 个 cohort 独立抽核**入场日严格晚于该月最晚公告日。
**★命门 1（NO-GO 证据基础）成立**：小盘 fetch 完成于 **530 名（66.2%）/ 覆盖 32.7% 小盘事件 / 13 个打分月**——覆盖确属**残缺**，
但裁定**没有过度断言**：报告将 NO-GO **明确 scoped 到"免费数据的部署决策"**，且**显式保留付费 ¥200/日 LHB 门为唯一干净决定性测试**（幸存者干净 + 批量快 + T+1 及时性，直接呼应 B099 滞后教训），
未宣称"增持信号科学上已死"；决定性负面证据（信号 IC 为噪音 + 事件簿全 horizon × 全成本网格净负）**独立于覆盖规模成立**。
研究码零产品回归，CI 双绿 + Workbench Deploy 成功（HEAD 已上 prod），L1 12 passed。**签收 PASS。**
两条非阻断软观察（打分月时间聚集未披露 / "上界"措辞非严格）见 §4。

---

## 1. 批次与交付

| 项 | 值 |
|---|---|
| 批次 | B102 = insider-buying 小盘 sleeve first-look（扩数据收口 B094/B099/B101 反复留下的"小盘/illiquid 未测"caveat）|
| F001（executor:generator） | 免费增持信号在小盘 sleeve 重测 → **NO-GO（小盘亦无可部署 edge）**。commit `58a9798`（impl）/ `9ea7500`（mark done→verifying）|
| F002（executor:codex） | 本次独立验收 + signoff |
| 类型 | research-only（无生产码 / 无 broker / 无付费数据 / 无真金）|
| 交付物 | `scripts/research/b102_smallcap_fetch.py`、`b102_smallcap_ic.py`、`tests/unit/test_b102_smallcap.py`、`docs/test-reports/B102-insider-smallcap-first-look.md` |

---

## 2. 验收方法（不信任 generator 自报，逐项独立复核）

本机小盘数据缓存齐全（`data/research/b102_smallcap/{prices.pkl(530 股×1,017,815 行), sample.json(seed-102 800名), coverage.json, ic_result.json}` + 复用 B101 `insider_events.csv`）→
**非 fixture-only 验收，而是在真实 530 股 / 5,918 事件小盘面板上独立复算**。
除复跑 generator 管线（证 bit 可复现），我**另写独立 IC 实现**（`/tmp/b102_verify.py`，自写 cohort_entry / forward_return / spearman，**不 import** generator 的 `run()`）重算，并抽取 13 个打分月逐月 IC + PIT 抽核。

---

## 3. 逐项裁定

### ★★命门 1 — NO-GO 证据基础扎实性（本批最关键）：**PASS（NO-GO 成立，正确 scoped，不降级）**

**核查问题：530 名残缺子集 + 13 打分月的 NO-GO 是"足够样本的真结论"，还是"限流残缺下的过度断言"（应降 INCONCLUSIVE）？**

**A. 小盘最终覆盖率（如实核对 coverage.json，与报告逐项吻合）：**

| 指标 | 值 | 报告是否诚实披露 |
|---|---|---|
| 小盘宇宙（非 B070 流动增持股）| 2,235 码 | ✅ §3 |
| 采样框（≥1 在窗事件 ≥2017-06）| 1,739 码 | ✅ §3 |
| seed-102 确定性抽样 | 800 名 | ✅ §3 |
| **fetch 成功** | **530 名（66.2%）** | ✅ §0/§3 明标 |
| **270 名（33.8%）拿不到价格** | 退市/停牌→零行 = 幸存者偏可见 | ✅ §1 Caveat 1 明标 |
| **小盘事件覆盖** | **4,017 / 12,290（32.7%）** | ✅ §0/§3 明标 |
| **打分月** | **13 / ~101 月**（多数月 < 20 名最小横截面被弃）| ✅ §3 明标为统计功效限 |

→ **覆盖确属残缺（32.7% 事件 / 13% 月），但报告 foreground 而非隐藏这些数字**——裁定与实际覆盖**匹配**，无"把残缺硬说成充分"的欺瞒。

**B. 为什么 NO-GO 不是过度断言（不降级 INCONCLUSIVE）——三点：**

1. **裁定正确 scoped 到"免费数据部署决策"，付费门显式保留。** 报告 §6"What this closes"+"Recommendation" 明确：关闭的是**免费** smart-money 线；
   **付费 ¥200/日 LHB 机构席位数据 "remains the one clean, decisive test"**（survivorship-clean / bulk-fast / **latency-cutting: T+1 席位披露 vs 本免费研究被迫吸收的 ~1 月公告滞后**）。
   → 报告**没有**宣称"增持信号科学上已死"，只说**免费空间穷尽**、决定性测试需付费——这正是**命门 3 要求的"免费全否 ≠ ¥200 无效"**，且 latency-cutting 一句直接引用 B099 及时性元凶结论。**epistemic posture 正确**，与 B101 保留小盘门同构。
2. **决定性负面证据独立于覆盖规模成立。** 这不是"样本太小看不出"的 INCONCLUSIVE，而是"在能拿到的最优上界面板上算出了决定性负面部署结果"：
   - **信号 IC 是噪音**：我复算 13 个月度 h5 IC 离散于 **−0.45 ~ +0.43**（逐月：0.005/0.339/0.104/0.093/−0.098/0.222/0.400/−0.186/−0.134/0.351/−0.453/0.044/0.435），均值 +0.086 但标准误巨大 → t=1.18 正确反映"与 0 不可分"。
   - **事件簿 GROSS 已 underperform 小盘基线**：h20 −7.0% / h60 −31.8%（仅 h5 +2.2%）。
   - **净成本全 horizon × 全 30–80bp 网格负**：h5 [−1.6%/−4.0%/−7.5%]、h20 [−12.0%/−15.2%/−19.8%]、h60 [−38.4%/−42.7%/−49.0%]——**无任何合理成本假设下为正**，唯一正的 5d gross +2.2% 扛不住一次 round-trip。
3. **"乐观上界仍失败"是有效的保守论证。** 幸存者偏移除退市最差尾（33.8% 掉出）使这是**优待信号的上界**；上界都失败 → 真实（幸存者干净）面板只会更差 → 部署 NO-GO 决定性。该框架用在**优待信号的方向**上仍 fail，属保守。

**C. 独立复算逐位吻合 + bit 可复现（超越抽查）：**
- 自写独立实现（不 import `run()`）：h5=**+0.0863** t=**1.184** eventCum=−0.0297 baseCum=−0.0513 excess=+0.0216；h20=+0.0345 t=0.630 excess=−0.0701；h60=−0.0020 t=−0.038 excess=−0.3176 —— 与报告 §4 / §5 表格**逐位一致**。
- secondary n_events：h5 +0.0246/h20 −0.0225/h60 −0.0176 —— 与报告逐位一致。
- 复跑 `python -m scripts.research.b102_smallcap_ic` → `ic_result.json` 与缓存**逐字节 IDENTICAL**（真实 530 股面板，非 fixture）。

### ★★命门 2 — PIT 无前视（增持披露日 T+1 而非增持发生日）：**PASS**

- **结构证：** IC 脚本 verbatim import B101 核心 `cohort_entry / forward_return / run`；事件按**公告月 M** 分 cohort，入场=**月 M+1 首交易日**，严格晚于该 cohort 内所有公告日；forward 用未来 bar；`_MAX_ENTRY_GAP_DAYS=15` guard 防 pre-2018 公告 snap。
- **独立 PIT 抽核（我构造，3 个随机 cohort）：**
  | 公告月 | 该 cohort 最晚公告日 | 实际入场日 | 入场晚于公告？ |
  |---|---|---|---|
  | 2026-04 | 2026-04-30 | **2026-05-06** | ✅ |
  | 2025-02 | 2025-02-28 | **2025-03-03** | ✅ |
  | 2018-10 | 2018-10-31 | **2018-11-01** | ✅ |
- **单测有牙：** `test_cohort_entry_is_after_announcement_month` / `test_entry_after_latest_possible_transaction_and_announcement` / `test_forward_return_measured_strictly_after_entry` 系统 venv 复跑通过。**用增持发生日=前视=假 edge，本实现杜绝。**

### ★★命门 3 — 外推边界（付费 top_inst 门保留）：**PASS**

**核查问题：小盘 NO-GO + 大盘四支 NO-GO = 免费聪明钱穷尽——报告是否正确保留"付费日频 top_inst 仍未测"的门？**

**结论：正确保留，且论证到位。** 报告 §6：
- "The free smart-money exploration … is now **exhausted**"——scoped 到**免费**，非全体。
- "**paid ¥200/day LHB institutional-seat data (Tushare) remains the one clean, decisive test**：survivorship-clean（point-in-time seat records）、bulk-fast（no per-name akshare throttling or delisting holes）、**latency-cutting（T+1 seat disclosure rather than the ~1-month announcement lag this free study had to absorb）**"。
→ **免费全否 ≠ ¥200 无效**表述正确，且**及时性优势**一句直接呼应 B099"滞后是元凶"结论（免费研究被迫吸收 ~1 月公告滞后，正是付费日频能砍掉的）。门诚实敞开，未过度外推。

### 命门 4 — 无扫参 + 零回归 + L1 + CI + HEAD≡prod：**PASS**

- **无扫参（grep 核）：** `grep -Ei 'grid|sweep|optimize|tune|argmax|best_'` 命中仅 `_COST_BPS_GRID=(30,50,80)` = **成本敏感度带**（3 档全量报告非择优，§4.3 全负），**非信号扫参**；`_HORIZONS=(5,20,60)`、`_TOP_Q`、`_MIN_XS=20`、`_MAX_ENTRY_GAP_DAYS=15`、`_SEED=102`、`_DEFAULT_SAMPLE=800` 均硬编码先验常量。无过拟合。
- **零回归：** 全批次（`5c2424b..HEAD`）仅触 `docs/ + scripts/research/ + tests/unit/ + features.json/progress.json`；**产品码（trade/ workbench/）0 文件**（`git diff 2b5f057..HEAD -- trade/ workbench/` = 空）。research-only 坐实。
- **L1 抽查：** 系统 venv（Python 3.11.15）复跑 `pytest tests/unit/test_b102_smallcap.py` = **12 passed**；`ruff check`（3 文件+目录上下文）= **All checks passed**。
- **CI 绿（独立 gh 复核）：** impl commit `58a9798` 的 **python-checks = success**（跑根 pytest+mypy trade+ruff，含 12 B102 测）、**workbench-backend = success**；**Workbench Deploy = success**（绿 CI 自动链式，HEAD 已上 prod）。
- **HEAD≡prod：** 0 产品策略码改动 → 生产 HEAD 与仓库 HEAD 逐字节等价（trivially，research-only；且 Deploy 成功坐实 prod 在 HEAD）。

### Workflow 对抗验证抽 1 复核

generator 采 Workflow-build（机制 + 后台 fetch + 对抗验证）。我未止于抽查其自报，而是**独立复现并超越**：自写独立 IC 实现逐位吻合 + bit 可复现 + 3 cohort PIT 抽核 + 逐月 IC 离散度核查 + 净成本网格复核。对抗验证结论（无前视 / IC 为噪音 / 净负）**独立坐实**。

---

## 4. 软观察（非阻断）

- **S1（打分月时间聚集未披露）：** 我复算发现 **13 个打分月中 10 个集中在 2017–2019**（2018-01 IC=0.34 等），仅 1 个在 2020、2 个在 2024，**2021–2023 三年零打分月**（小盘横截面 <20 名被弃）。报告 §3 诚实披露"13/~101 月"与"薄横截面"，但**未点明时间聚集**。这**强化"coverage-limited"**、使 13 月回测更不具代表性，但**不翻转部署裁定**（信号在其覆盖最好的早期仍为噪音 + 全 horizon 净负）。建议未来若扩数据补充时间分布披露。非缺陷。
- **S2（"optimistic upper bound"措辞非严格）：** 报告称测得 edge 是幸存者造成的"上界"。严格讲 excess = 事件簿 − 基线，二者同处幸存者面板，幸存者对两者同向抬升，**相对 excess 未被干净上界化**（"上界"成立需假设增持名退市率 ≥ 基线率——plausible 但未证）。但此框架**非 load-bearing**：20d/60d 事件簿 GROSS 已负、净成本全 horizon 深负，独立于"上界"方向成立；且该措辞用在**优待信号**方向（保守）。非缺陷，措辞可更精确。
- **S3（复算 json 本机 gitignored）：** `ic_result.json / coverage.json` 经 `.gitignore data/*` 忽略；报告 md + coverage.json 承载全部数字、脚本可确定性复现（本次已 bit 复现坐实）。非缺陷。

---

## 5. 最终裁定

| Feature | 裁定 |
|---|---|
| F001 — insider-buying 小盘 sleeve first-look（小盘 NO-GO / 无前视 / 覆盖诚实 / 净成本全负 / 付费门保留）| **PASS** |
| F002 — Codex 独立验收 + signoff | **PASS**（本报告）|

**全 PASS 2/2 → status=done。**

**含义（免费 smart-money 四角度全 NO-GO，探索收口）：**
1. 机构专用席位覆盖限（B077，80.8% 小盘未覆盖）；
2. 游资 first-look（B094 NO-GO）；
3. 机构建仓季度 first-look（B099 NO-GO，滞后是元凶）；
4. **大股东/高管增持 first-look：流动大盘（B101 NO-GO 信号真空）+ 小盘 sleeve（B102 本批 NO-GO，净成本全负、乐观上界仍失败）**。
→ **免费"smart-money"四角度在流动大盘 + 小盘均无可部署 edge**；免费空间**穷尽**。
→ **未测 = 付费 ¥200/日 Tushare 日频 top_inst**（用户真实目标的**唯一干净决定性测试**：幸存者干净 + 批量快 + T+1 及时性砍掉本免费研究吸收的 ~1 月滞后）。仍待用户决策。

---

## 6. 文件清单（本次验收产出/核对）

- 本 signoff：`docs/test-reports/B102-insider-smallcap-first-look-signoff-2026-07-07.md`
- 核对：`docs/test-reports/B102-insider-smallcap-first-look.md`（F001 报告）
- 核对：`scripts/research/b102_smallcap_fetch.py`、`scripts/research/b102_smallcap_ic.py`、`scripts/research/b101_insider_ic.py`（verbatim 复用核心）、`tests/unit/test_b102_smallcap.py`
- 独立复算脚本：`/tmp/b102_verify.py`（本机，自写 IC 不 import generator `run()`）
- 独立复算数据：`data/research/b102_smallcap/{coverage.json, sample.json, ic_result.json, prices.pkl}`（gitignored 本机）
- 对照先例：`docs/test-reports/B101-insider-buying-first-look-signoff-2026-07-06.md`（流动大盘 NO-GO）
