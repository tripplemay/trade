# B094 — 游资 (hot-money) 席位 follow-signal first-look Evaluator Signoff（2026-07-06）

> **裁定：全 PASS 2/2 → done。裁定 = NO-GO（跟游资反而亏，significant NEGATIVE）成立。** F001（`scripts/research/b094_youzi_fetch.py` 416 行 + `b094_youzi_ic.py` 459 行 + `tests/unit/test_b094_youzi.py` 224 行 + 报告 166 行，generator，Workflow 建）+ F002（本独立验收，codex）。
> Evaluator 独立执行（代 Codex；授权 = 用户 /goal + B079–B093 先例），与实现完全隔离，最高怀疑度。
> **核心手段：从缓存快照用我自己的独立代码从零重算整条决策**——(1) IC 脚本在缓存数据上逐格重现报告；(2) **我自己的独立 forward-return + rank-IC + follow-backtest 代码 bit 级吻合**（不复用其脚本）；(3) **去重对抗检验**（剔 7,979 重复 (date,ticker) 行）证 NO-GO immaterial；(4) 手工 PIT 核对 3 真实事件无前视；(5) 独立坐实 §2(c) 141/141 交叉验证；(6) git diff 证 research-only 零产品码；(7) 门禁全绿复跑 + CI 三绿 + HEAD≡prod。
> **被验收提交：`013f681`**（feat B094-F001，7 文件含 2 研究脚本 + 单测 + 报告 + state）+ `85f8c3f`/`b7675e2`（mark done + backlog 标注，paths-ignore 不触发 CI）。
> **生产面：无**（全部新代码在 `scripts/research/` + `tests/unit/`，无 workbench/ 产品码，无 trade 包改动，无 ¥200 付费数据）。

## 0. 本批性质与命门

- **免费 first-look 批（backlog smart-money 第二支）**：游资/打板 = 龙虎榜盘后公开披露的**已知拥挤族**（异动条件、滞后、可马甲）。诚实先验期望 NO-GO/INCONCLUSIVE。这是**次要信号非用户首要 institutional 目标**（后者需付费 Tushare ¥200 全覆盖机构席位，本批**故意未买**，保留给用户）。
- **★命门 =（i）无前视**（上榜日 T 盘后披露 → 入场严格 T+1）+**（ii）覆盖诚实**（游资偏小盘异动 → 须如实披露覆盖率、正确论述负 IC 在覆盖偏差下的可信度方向，对照 B077 机构席位 80.8% 未覆盖致 INCONCLUSIVE_COVERAGE_LIMITED 的纪律）+**（iii）NO-GO 与数字一致**（B069/B076 verdict-gating：负得显著才可称「亏」，噪音级负应称「无 edge」；席位识别口径先验、非事后挑赢家）。

## 1. 验收结论表

| 验收项（features.json F002 + team-lead 追加） | 裁定 | 证据（独立复算/复现） |
|---|---|---|
| **① 无前视（上榜日 T 披露 → 入场 T+1）** | **PASS** | 上榜日 = 龙虎榜盘后披露日，信号 known at close T；入场 = `bisect_right(dates, T)` 首个**严格 > T** 的交易 bar；fwd ret over T+1..T+1+N。**手工核对 3 真实覆盖事件**：`002349.SZ`(T=2022-01-20→entry 2022-01-21)、`603137.SH`(T=2023-08-23→entry 2023-08-24)、`603686.SH`(T=2024-12-25→entry 2024-12-26)——event-day close 从不作为 entry，`assert dates[entry] > T` 三例全过。可见 3 例中 2 例 event-day 异动后 follow-day 回落，与负 IC 机制一致。单测 pin：`test_forward_return_enters_strictly_after_event_date` / `test_event_exactly_on_a_bar_uses_next_bar_not_same_bar`（bisect_right 精确匹配日跳过回归锁） |
| **② 宇宙覆盖诚实披露（最重）+ 负 IC 外推边界正确** | **PASS** | 覆盖 = **12,502/52,337 = 23.89%**（35 月），独立复算逐格吻合报告 23.9%。报告 §1/§7 caveat 焊死。**★关键纪律核验**：价格宇宙是 seed-94 **uniform-random 1,500-ticker 子样**（非 B077 的结构性大盘-only 宇宙）→ 覆盖是**随机聚类子样**，故 t=-4.10 的显著负号**在方向上可外推到总体**（幅度不确定 = first-look 估计），报告如实标「sign and significance robust across 12,502 events/35 months, magnitude is partial-universe」。**与 B077 的合法区别**：B077 是结构性大盘-only 覆盖 + 仅**微弱正**信号 → 无法断言「无信号」→ INCONCLUSIVE_COVERAGE_LIMITED；B094 是随机子样 + **显著负** → NO-GO（决策=不追）成立且保守（即便较好行为的覆盖子集跟游资也亏）。报告将结论如实限定为「跟游资比裸买所有 LHB 还差」的 follow-vs-baseline 承重比较，未过度外推为全宇宙可交易负 edge |
| **③ IC / 收益独立复算（我自己的代码）+ 措辞与数字匹配** | **PASS** | **★我自己的独立 forward-return + avg-rank Spearman + monthly-cohort IC + follow-backtest 代码**（非复用其脚本）逐格 bit-match：youzi_flag IC N1 **−0.0084**(t=−0.80) / N5 **−0.0434**(t=−4.10) / N10 **−0.0426**(t=−3.16)；follow edge N1 −0.00037(t=−0.24, 17/35) / N5 **−0.01003**(t=−2.92, 12/35) / N10 −0.00767(t=−1.47, 13/35)；baseline lhb-net IC N1 +0.0164/N5 −0.0133/N10 −0.0202 —— 全部与报告表 §4/§5 吻合。**★措辞-数字匹配核验（team-lead #3）**：负号在 N5/N10 IC（\|t\|=4.10/3.16, 非噪音）+ N5 follow-edge（−1.00%, t=−2.92, 显著）成立；N1/N10 follow-edge 不显著。报告 §5 精确标「significantly so at N=5」并逐 horizon 透明贴 t-stat →「跟游资反而亏」= 有显著 N5 edge + 显著 N5/N10 IC 支撑的校准表述，非过度声张；且「亏」的语义 = follow 劣于 all-LHB baseline（非绝对亏 tradeable 主张），报告正确框为 follow-vs-baseline，honest |
| **④ 信号定义先验 + 无扫参 + 席位识别口径来源** | **PASS** | **无扫参 grep**：脚本无 param-grid / argmax / best-of / for-over-thresholds 构造；阈值全先验标准常量（`_STRONG_IC=0.03` `_FAINT_IC=0.015` `\|t\|≥2` horizons 固定 `(1,5,10)`）= 因子研究教科书值，非为数据显著性调参。**席位识别先验/第三方**：primary 信号 youzi_flag = EastMoney **解读「实力游资买入」编辑标签**（披露时第三方赋予、close T 可得、非作者事后挑赢家）；`classify_branch` 用交易所标签「机构专用」/「股通」（客观文档惯例）；频率启发式**事后浮出拉萨天团（东财拉萨营业部群）= 教科书打板天团**作为验证（非用于选赢家）。**★§2(c) 交叉验证独立坐实**：seats_sample 800 行中 tagged=**141**，141/141(100%) youzi_buy_net > 0 且 youzi_top ≥ inst_net，tagged 均值 **¥141M** vs untagged **¥74M**（~2×）—— 逐格吻合报告，证廉价 flag 是「游资席位为 top 净买家」的可靠代理。已披露局限（少数总部/分公司混淆）诚实 |
| **⑤ 打板短线族张力 + 选择偏差 caveat 保留** | **PASS** | 报告 §7 caveat 3 保留选择偏差（异动条件 → 均值回归拖累全截面，承重比较是 follow-vs-baseline）；honest frame（§顶部）明述游资/打板 = chasing limit-ups 的已知拥挤高换手族。低频偏好张力经 NO-GO 而 moot（本不采纳），非缺陷。caveat 5 亦诚实标无幸存者-free 宇宙（退市名长 horizon → None，非完整幸存者处理） |
| **⑥ Workflow 对抗验证 + 零回归 + L1 + CI + HEAD≡prod** | **PASS（journal 不可及，独立复算超越）** | generator_handoff 载 Workflow 3 子代理（1 build + 2 对抗验证 un-refuted）。journal 在本机可访问路径未找到（独立 session transcript 已散）——**非阻断**：铁律 4 最强验证 = 我**从零用自己的代码独立重算全部关键数字 + 去重对抗检验**（§①-④），比信任 workflow 验证者强，结论与 handoff 逐项相符。**research-only 零回归**：`git diff 9a2ff54^..HEAD` = scripts/research×2（新）+ tests/unit×1（新）+ docs×1 + backlog/features/progress，**无 workbench/ 产品码、无 trade 包改动**。**门禁**：ruff `All checks passed`（3 文件）+ pytest `22 passed`。**CI**：`013f681` push → **Python CI success 7m25s + Workbench Backend CI success 8m30s + Workbench Deploy success 3m24s**（自动链式）。**HEAD≡prod**：无产品码变更 → HEAD 产品码 ≡ prod 平凡成立（无需部署） |

## 2. 核心不变量复核（最高怀疑度）

**本批命门三重，已从零用我自己的独立代码坐实：**
1. **无前视（★命门）**：上榜日 T = 盘后披露日，入场严格 T+1（bisect_right）；3 真实事件手工核对 `dates[entry] > T` 全过；单测双 pin（含精确匹配日回归锁）。
2. **覆盖诚实 + 外推边界正确**：23.89% 随机子样（seed-94 uniform，非 B077 结构性偏），显著负号方向可外推到总体、幅度 first-look；NO-GO（决策=不追）保守且成立；报告限定为 follow-vs-baseline 承重比较，未过度外推。
3. **NO-GO 与数字一致（verdict-gating）**：judge() 的 GO 需 `≥2 strong 正 IC` **且** `显著正 edge`——`strong_pos` 只收 ic>0，显著负 IC 入 `sig_neg` 永不入 GO 通道 → **负数据无法制造 GO**；实测 strong_positive_ic_horizons=0、best_edge=−0.00037≤0、2 显著负 IC → NO-GO 触发正确。措辞「反而亏」经措辞-数字匹配核验校准（显著 N5 edge + 显著 N5/N10 IC 支撑，非噪音级）。

**去重对抗检验（关键补充）**：events.csv 有 **6,901 个重复 (date,ticker) 键 / 7,979 多余行**（同股同日多个上榜原因，akshare 返回多行；fetch docstring「one row per stock per 上榜日」不准确、未去重）。**独立重算 dedup 后（唯一 date-ticker，OR 游资 flag）**：N5 IC **−0.0420**(t=−3.95) / N10 IC **−0.0450**(t=−3.27) / N5 edge **−0.00926**(t=−2.65) —— **NO-GO 稳健**，N10 IC 去重后反略强。→ 重复键 **immaterial to verdict**，属文档 gap 非缺陷。

## 3. 软观察（非阻断，供 follow-up 参考）

- **O1 — events.csv 重复 (date,ticker) 键未去重 + fetch docstring 措辞不准**：同股同日多上榜原因产生 7,979 多余行（15.2%），fetch docstring 称「one row per stock per 上榜日」不准确。**immaterial to verdict**（去重对抗检验 N5 IC −0.042 t=−3.95 仍显著 NO-GO，N10 反略强）。建议若再修订可去重并订正 docstring。文档/健壮性观察非缺陷。
- **O2 — §1 caveat「small-cap names sit outside the subset」措辞略欠精确**：1,500-ticker cap 是 **uniform-random 子样**（sign 无偏），此措辞易被误读为 B077 式结构性排除。实际随机性**加固** NO-GO（sign 可外推），报告未显式作此有利论证但结论保守限定，故非阻断。建议可补一句「random subsample → sign extrapolatable」。
- **O3 — priced tickers 实际 1,279（非满 1,500）**：guard/fetch 失败后可用价格 ticker 1,279；覆盖 23.89% 与此一致，报告披露口径无误。数据现实非缺陷。
- **O4 — 仅 N5 follow-edge 显著负**：N1/N10 follow-edge 不显著（N10 t=−1.47、N1 t=−0.24）；报告逐 horizon 透明贴 t-stat 且明标「significantly so at N=5」，故「反而亏」校准无过声张。非阻断。

四项均非阻断，不撼动 F001 交付（无前视 + 覆盖诚实 + IC/收益逐格独立复算 + 席位识别先验第三方 + NO-GO 纪律）与命门。

## 4. 结论

**B094 游资席位 follow-signal first-look 2 features 全 PASS → done。裁定 = NO-GO（跟游资反而亏，significant NEGATIVE）。**

无前视经**手工核对 3 真实事件**（上榜日 T 盘后披露 → 入场严格 T+1，bisect_right）+ 单测双 pin 坐实命门；覆盖 **23.89%** 经独立复算 + 核实为 **seed-94 uniform-random 子样**（非 B077 结构性偏）→ 显著负号方向可外推、幅度 first-look，NO-GO（决策=不追）保守成立、报告限定为 follow-vs-baseline 承重比较；IC/收益经**我自己的独立代码 bit 级吻合**（youzi_flag IC N5 −0.0434/t=−4.10、N10 −0.0426/t=−3.16；follow edge N5 −1.00%/t=−2.92）+ **去重对抗检验证 immaterial**（dedup N5 IC −0.042/t=−3.95 仍显著）；信号定义**无扫参**（阈值先验标准常量、horizons 固定）、席位识别**先验第三方**（EastMoney 解读标签 + 交易所标签，非事后挑赢家）、**§2(c) 141/141 交叉验证独立坐实**；**NO-GO 与数字一致**（judge() 负数据无法制造 GO，措辞「反而亏」经措辞-数字匹配校准 = 显著 N5 edge + 显著 N5/N10 IC 支撑非噪音，守 B069/B076 verdict-gating）；选择偏差 + 打板拥挤 caveat 诚实保留；门禁全绿（ruff 3 文件 + pytest 22）+ **CI Python/Backend/Deploy 三绿（013f681 自动链式）** + **HEAD 产品码 ≡ prod（零产品码）** + research-only（无 workbench/、无 trade 包、无 ¥200 付费数据）。四项软观察（O1 重复键未去重+docstring 措辞 / O2 caveat 措辞欠精确 / O3 priced 1,279 / O4 仅 N5 edge 显著）均**非阻断**。

**★含义：smart-money backlog 免费两支信号均已测尽 = 机构席位 first-look（B077）INCONCLUSIVE_COVERAGE_LIMITED + 游资席位 follow（B094）NO-GO（跟游资反而亏）。用户首要 institutional-following 目标仍需付费 Tushare ¥200 全覆盖机构席位，本批故意未买，保留给用户。**
