# B105 — inst_buy_net ranked 多空（IC 扣成本能否转化为可交易 edge）Signoff

> 状态：**Evaluator 验收通过 → done**（progress.json status=verifying → done）
> 触发：B105 F001（generator + Workflow build）交付 GO 裁定，F002 = 独立验收（本报告，代 Codex）
> 裁定：**全 PASS 2/2 → done**。GO（纸面 dollar-neutral L/S 扣成本净正）**算术为真且已逐位独立复现**；但我的**独立多空拆腿**揭示 **净收益 ~90–107% 来自 A 股不可行的空头腿，多头腿绝对收益≈0**——报告方向上诚实（已标短腿不可行 / 非 tradeable / 上界），但**未量化这一点**，我在本 signoff 补齐，作为对 ¥200 决策**最关键的一条**。
> Evaluator：独立验收，与实现完全隔离，最高怀疑度（授权=用户 /goal + B079–B104 先例）
> ⚠️ **前一个"B105 验收"是幻觉**（声称推了 `f4e2b1c` / NO-GO，但该 commit 在 git 中不存在、无 signoff、status 仍 verifying）。本报告从零重做，一切以 git 实际状态 + 磁盘产物为准，不信任何转述。

---

## 0. 一句话结论

F001 的 **inst_buy_net rank-weighted dollar-neutral 多空** first-look 是一次**数字真实、无前视、无 p-hacking、零产品回归**的交付，其 **GO 裁定在自己定义的窄命题上算术为真**（纸面 L/S 扣 30/40/50/80bp 全成本档在 5d/10d 均净正）。**报告全部数字我用完全独立的代码（自写平均秩 + 自写 Spearman，不 import 任何 b105 函数）在真实 485 对面板上复算，逐位吻合**：GROSS 5d cum **+0.6843 Sharpe 1.151 t 1.97** / 10d **+1.3322 Sharpe 1.612 t 2.75**；NET@40bp 5d **+0.4667 Sharpe 0.865** / 10d **+1.0334 Sharpe 1.364**；1d 负控制 GROSS flat（+0.027 t 0.28）→ NET 每档皆负；corr(cohort-IC, L/S-ret) 5d **0.879** / 10d **0.825**——与 committed `result.json` bit 级一致。

**★★但这次验收最有价值的产出是拆腿**：我把 dollar-neutral L/S 拆成多头腿 / 空头腿独立核算——**净收益几乎全来自空头腿**（5d 空头腿 = gross 的 **107%**，10d = **91%**），**多头腿绝对收益接近零甚至为负**（5d 多头腿 −0.0011/月 Sharpe −0.08；10d +0.0022/月 Sharpe 0.12）。根因：LHB 异动名整体在事件后**下漂 −2.7%（5d）/ −3.3%（10d）每月**，空头腿靠"做空机构没买/净卖的最差名（跌得最狠）"赚钱，多头腿（机构净买最多的名）只是**跌得比平均少**。**A 股散户无法融券做空这些小盘**——因此纸面 GO 里能落地的一侧恰恰是不赚钱的一侧。这比报告"long implementation materially weaker"的定性表述**严重得多**：不是"弱一点"，而是**绝对多头几乎无 edge**。

无前视沿用 B103/B094 已验机制，我另抽 4 个真实事件手核入场严格 T+1；无 p-hacking（horizon=B094 固定 1/5/10、成本 40bp 中心 + 预声明 30/50/80 敏感度、无 argmax/sweep/挑权重方案）；**产品码零 diff（研究纯）**、CI 双绿 + Deploy 成功、L1 **21 passed** / ruff 净。**签收 PASS 2/2。** 对 ¥200 的诚实判断见 §6（well-motivated 但已收窄——付费买不回市场结构性的做空限制）。

---

## 1. 批次与交付

| 项 | 值 |
|---|---|
| 批次 | B105 = inst_buy_net **ranked 多空**（测 B104 已独立验的 +0.15 IC 扣成本后能否转化为可交易 edge；解 B103 binary-follow 非正 ↔ B104 IC 正的张力：IC 在**排名**里，binary 丢弃了排名）|
| F001（executor:generator） | rank-weighted dollar-neutral L/S 组合层（复用 B103/B094 无前视 cohort，仅组合层为新）→ GROSS/NET/Sharpe → **GO（cost-surviving, survivorship-caveated）**。commit `09387c3`（impl）/ `8ed22ef`（mark done→verifying）|
| F002（executor:codex） | 本次独立验收 + signoff |
| 类型 | research-only（无生产码 / 无 broker / 无付费数据 / 无真金）|
| 交付物 | `scripts/research/b105_inst_net_longshort.py`（386 行，组合层）、`tests/unit/test_b105_inst_net_longshort.py`（21 测）、`docs/test-reports/B105-inst-net-longshort-first-look.md`；数据 `data/research/b105_longshort/result.json`|
| Evaluator 独立复算脚本 | `docs/test-cases/b105_independent_recompute.py`（自写平均秩 + Spearman + 拆腿 + long-only-vs-index，**不 import 任何 b105 函数**）|

---

## 2. 验收方法（不信任 generator 自报，也不信任前一次幻觉验收）

本机 B094/B103/B104 缓存齐全（`events.csv` 52,337 行 / `prices.csv` / `seats_expanded.csv` 1000 行）→ **在真实面板上独立复算，非 fixture-only**。

**独立性保证**：我的复算脚本只复用**前序批次已被 Codex 独立验收过的数据装载原语**（`b103.load_events` / `b103.build_cohorts` / `b094.load_prices` / `b094.forward_returns`——在 B094/B103/B104 三批已验无前视），**组合层的每一个数字（权重、GROSS、NET、Sharpe、CAGR、cohort-IC、corr、拆腿、long-only）全部用我自己的代码从头重写**：
- 平均秩用 `np.unique` inverse+counts 实现（与 b094 的 scan-loop 算法**不同**）；
- Spearman = 平均秩的 Pearson（不 import `b094.rank_ic`）；
- 权重、点乘、成本扣减、复利、sqrt(12) Sharpe、t 统计全部自写。

另额外做了 generator **没有做**的分析：多空拆腿、long-only-vs-index、long-only 绝对、universe drift、4 事件 PIT 手核。

---

## 3. 独立复算结果（自写代码，与 `result.json` 逐位吻合）

`inst_net_sampled_events = 1309`（复算 = 报告 1309 ✓）；`485 对 / 35 月 / avg 13.9 名`（✓ 与 B104 同一 universe）。

| Horizon | 指标 | 我的独立复算 | committed result.json | 一致 |
|---|---|---|---|---|
| **N5** | GROSS cum / Sharpe / t | **+0.6843 / 1.151 / 1.97** | +0.6843 / 1.151 / 1.97 | ✓ bit |
| | NET 30/40/50/80bp cum | +0.5184 / +0.4667 / +0.4167 / +0.2765 | 同 | ✓ |
| | NET 40bp Sharpe / 80bp Sharpe | 0.865 / 0.579 | 0.865 / 0.579 | ✓ |
| | mean cohort IC / corr(IC,ret) | +0.148 / 0.879 | 0.148 / 0.88 | ✓ |
| **N10** | GROSS cum / Sharpe / t | **+1.3322 / 1.612 / 2.75** | +1.3322 / 1.612 / 2.75 | ✓ bit |
| | NET 30/40/50/80bp cum | +1.1044 / +1.0334 / +0.9647 / +0.7719 | 同 | ✓ |
| | NET 40bp Sharpe / 80bp Sharpe | 1.364 / 1.116 | 1.364 / 1.116 | ✓ |
| | mean cohort IC / corr(IC,ret) | +0.1615 / 0.825 | 0.162 / 0.83 | ✓ |
| **N1** | GROSS cum / Sharpe / t | +0.0271 / 0.163 / 0.28 | 0.0271 / 0.163 / 0.28 | ✓ bit |
| | NET 40bp（负控制）| −0.1073（每档皆负）| 同 | ✓ |

**结论：committed 数字 100% 可复现，无任何编造。** GO 裁定的算术门（40bp 净正 & Sharpe≥0.5 & 50bp 净正，5d/10d 双 horizon）**成立**。

---

## 4. ★★命门 1 — GO 裁定真实性（独立复算，非 artifact）

- **① GROSS 真正吗？** 是。5d GROSS t=1.97（略低于 2）、10d t=2.75（扎实）；21/35（5d）、25/35（10d）月为正。10d 挑大梁，5d 边际。
- **② NET 真挺过每个成本档吗？** 是。5d/10d 在 30/40/50/80bp **全部净正**，即使 80bp 惩罚档 5d Sharpe 0.58 / 10d 1.12。年化成本拖累 ≈12×round-trip（40bp→~4.8%/yr），口径正确（每月一次 unit-gross round-trip，我核了 `net = gross − bp/1e4`）。
- **③ corr(IC, L/S-ret)=0.83–0.88 是真还是循环论证？** **数字为真（我独立复算 0.879/0.825），但它是近乎机械的一致性检验，不是独立盈利证据**。因为 L/S 权重按 sig 排名单调构造，L/S 收益本就是同一排名的单调泛函，与 cohort-IC 高相关是**设计使然**——它能排除"L/S 收益来自与排名无关的东西 / 编码 bug"，但**不能**当作 edge 强度的第二个独立证据。真正承重的数字是 GROSS 的 t-stat 本身。报告用它论证"portfolio 确实在货币化 rank-IC 而非 artifact"——这个用法**正确且克制**；但读者不应把 0.88 误读成"额外的统计显著性"。（见 §7 软观察 S2。）
- **④ 1d 负控制成立吗？** 成立。1d GROSS flat（cum +0.027, mean cohort IC −0.01, t 0.28）→ NET 每档皆负。证明 L/S 只在 IC 存在处（5–10d）赚钱、非普遍 artifact。**这是一个漂亮的证伪防线**：若 1d 也"赚"，就该怀疑是成本/构造 bug。

---

## 5. ★★命门 2 — 短腿不可行的严重性（本批对 ¥200 最关键，我补齐了 generator 没做的量化）

我把 dollar-neutral L/S（多头 w>0 合计 +0.5、空头 w<0 合计 −0.5）**拆成两腿独立核算**：

| Horizon | 多头腿贡献（月均 / cum / Sharpe） | 空头腿贡献（月均 / cum / Sharpe） | 空头腿占 GROSS |
|---|---|---|---|
| **N5** | **−0.0011 / −0.070 / −0.08** | +0.0172 / +0.781 / **1.74** | **107%**（多头 −7%）|
| **N10** | **+0.0022 / +0.008 / 0.12** | +0.0238 / +1.193 / **1.74** | **91%**（多头 9%）|

**根因（我实测 universe drift）**：这批 LHB 异动名事件后**整体下漂 −2.70%（5d）/ −3.29%（10d）每月**。空头腿靠做空排名最低（机构没买/净卖）、跌得最狠的名赚钱；多头腿（机构净买最多）只是**跌得比平均少**，绝对收益≈0。

**含义（对 ¥200 决定性）**：
1. **纸面 GO 里唯一 A 股可落地的一侧（多头）绝对收益≈0**。散户无法融券做空这些小盘（融券券源稀缺/贵/受限）——占纸面净收益 ~90% 的空头腿**结构性不可交易**。
2. 我另算了两个"可行"版本澄清"long-tilt 到底多弱"：
   - **long-only 绝对**（只买 top、不做空、不 benchmark）：5d −0.0022/月（负）、10d +0.0044/月（Sharpe≈0.12，约等于零）。→ **"跟机构买入并持有"几乎不赚钱**。
   - **long-only vs LHB-异动 universe（相对 alpha）**：5d 超额 Sharpe 净 40bp ~1.02、10d ~1.39——**看起来不弱，但这是相对"下跌的异动篮子"的超额，不是口袋里的绝对钱**，且需要以异动篮子为 benchmark（而非 CSI300）。它本质是把横截面 alpha 换个写法，**不构成 A 股散户能落地的绝对多头 edge**。
3. **幸存者限对空头腿的美化**：免费 akshare（2022–2024）漏退市名——最差、后来退市的名恰恰是空头腿该赚最多的。付费全史（含退市）会让**纸面空头腿更好看**，但这只会放大一个**本就不可交易**的腿；对**多头**的净影响才是 ¥200 真正能澄清的。

**裁定**：报告在**方向上诚实**（明写"短腿基本不可行 / long implementation materially weaker / upper bound / not tradeable"），但**把最决定性的一个数字（~90% 净收益在空头腿、多头绝对≈0）留在了定性表述里没量化**。这不构成 FAIL——GO 的窄命题（纸面 L/S 挺过成本）算术为真、诚实框架俱在——但它是本 signoff 必须替用户补上的一条，见 §6。

---

## 6. ★★命门 3 — 对 Tushare ¥200 的诚实 go/no-go

**信号本身**：REAL。inst_buy_net 是一个真的横截面**排名**信号（IC~0.15 挺过 B104 扩样 + 本批扣成本），是 24 批免费探索里**唯一没死的聪明钱线索**。这一点站得住。

**¥200 能解决什么**：
- 幸存者限（补回退市名）、更长窗（2005+，跨牛熊 regime）、~50× 样本（把 5d t=1.97 这种边际显著性收紧）、更干净席位识别；
- **决定性 confirm/kill** 这个排名信号在干净长数据上是否仍成立；
- 澄清 **long-only 相对 alpha** 在干净数据上是否 robust，以及是否存在某个 long-only 子策略（如 top-decile vs CSI300）有**任何绝对 edge**。

**¥200 解决不了什么（关键）**：
- **A 股融券做空限制是市场结构，付费买数据改不了**。占纸面净收益 ~90% 的空头腿，无论数据多干净都**无法落地**。
- 因此干净测的**最好结果**仍是：一个真的排名信号 + 一个**弱的（绝对≈0）long-only 可交易残值**。

**诚实判断（宁可 unclear 不轻易断言）**：
- ¥200 是 **well-motivated 但已收窄的确认**——motivated（信号真、rank-IC 货币化、纸面挺过成本、是最好免费线索）；收窄（B105 揭示可落地的多头 edge 弱、~90% 纸面利润在结构性关闭的空头腿）。
- **它不是"买一个已知可交易 edge"**。若用户目标 = "definitively 判定这个排名信号真假 + 是否有任何 long-only 绝对残值，并停止在薄免费数据上猜"→ **花 ¥200 合理**。若用户目标 = "必须找到一个能落地赚钱的绝对多头策略"→ **B105 已提示多头绝对≈0，且付费改不了做空限制，可省这 ¥200**（或至少把预期压到"确认+kill 用途"而非"买 edge"）。
- 报告的护栏（明标 upper bound / not tradeable / not survivorship-clean / ¥200 decisive）**没有误导用户白花，也没有误导白省**；本 signoff 补上的"多头绝对≈0"进一步让用户**知情**——最终仍是用户的知情决策。

---

## 7. 命门 4 — 无前视 / 无 p-hacking / 零回归 / CI / HEAD≡prod

| 检查 | 结果 |
|---|---|
| **无前视（PIT）** | 沿用 B103/B094 已验 `forward_returns`（`bisect_right` 严格 > T）。我另抽 **4 个真实事件**手核入场严格 T+1：`002443.SZ` T=2022-01-06→入场 01-07（inst_buy_net 27M）、`300943.SZ` T=2022-01-26→01-27（5.8M）、`002682.SZ` T=2023-12-26→12-27、`002862.SZ` T=2023-12-18→12-19。全部 entry_date 严格 > T。21 单测含 T+1 断言。|
| **无 p-hacking（挑 horizon）** | horizon = B094 固定 `HORIZONS=(1,5,10)`，非本批选择；三档全报告，1d 作负控制。无挑 horizon。|
| **无 p-hacking（挑成本）** | 40bp 中心 + 预声明 30/50/80 敏感度全报；连 80bp 惩罚档都净正——非挑最便宜档。`grep` 无 argmax/sweep/tune/for-seed/best/optimize。|
| **无 p-hacking（挑权重方案）** | 单一标准 rank-weighted demeaned unit-gross 方案，无多方案扫描后择优。verdict 门槛（Sharpe≥0.5 & 40&50bp 净正）在 `judge()` docstring **预声明**、确定性判定，非事后拟合。|
| **零产品回归** | `git diff 0666743^..HEAD -- trade workbench` = **空**。B105 仅动 `scripts/research/` + `tests/unit/` + `docs/` + 状态 JSON。research-only 确认。|
| **L1 门禁** | `pytest tests/unit/test_b105_inst_net_longshort.py` = **21 passed**；`ruff check` 净（我本机复跑，非信自报）。|
| **CI 绿** | Python CI + Workbench Backend CI 均 **success @ `09387c3`**（B105 F001 feat push，含全部代码）。HEAD `8ed22ef` 为 chore（仅状态/文档，paths-ignore 不触发 CI）。|
| **HEAD≡prod** | B105 **产品码 0 diff** → 生产部署面不受影响，对所有已部署 surface 平凡地 ≡HEAD。Deploy workflow success @ 2026-07-07T06:06。|

**软观察（非阻断）**：
- **S1（措辞）**：报告标题级裁定 "GO" 虽有 caveat，但"materially weaker"未量化"多头绝对≈0 / 空头腿占 ~90%"。本 signoff §5 已补齐——建议后续任何转述 GO 时必须附带这条，否则易被读成"可交易多头 edge"。
- **S2（corr 解读）**：corr(IC,ret)=0.88 是近乎机械的一致性检验（同源排名的单调泛函），非独立盈利证据；报告用法克制正确，但读者勿误读为额外显著性。
- **S3（样本承袭 B104 的薄）**：485 对里仅 **174（36%）真有 nonzero inst_buy_net**（约 5 名机构/月），其余 64% 为 0 值。横截面排名在薄有效样本上做出——承袭 B103/B104 已接受方法，非本批新问题，但 ¥200 干净扩样正对症。

---

## 8. 最终裁定

| Feature | Executor | 裁定 | 依据 |
|---|---|---|---|
| F001 | generator | **PASS** | GROSS/NET/Sharpe/corr/1d负控制 逐位独立复现；ranked 构造正确（dollar-neutral Σw=0 / unit-gross Σ\|w\|=1 / 单调，21 测 + 我复核）；成本口径 realistic 无乐观；诚实框架（upper bound / 短腿不可行 / ¥200 decisive）俱在；research-only 零产品码 |
| F002 | codex | **PASS** | 本独立验收完成：数字全复现、无前视（4 事件手核）、无 p-hacking（无 sweep/挑 horizon/挑成本/挑权重）、拆腿补齐、¥200 诚实判断、CI 绿、HEAD≡prod、signoff 交付 |

**全 PASS 2/2 → done。** GO 裁定在其窄命题上成立且已独立复现；**决定性补充：净收益 ~90% 在 A 股不可行的空头腿，多头绝对 edge≈0**——信号真、纸面挺过成本，但**实盘 long-only 落地弱**；¥200 = well-motivated 但收窄的干净 confirm/kill（付费买不回做空限制），仍待用户知情决策。

---

*Evaluator 独立验收（代 Codex），2026-07-07。所有数字可由 `docs/test-cases/b105_independent_recompute.py`（`./.venv/bin/python` 运行）复现。前一次"B105 验收"为幻觉（`f4e2b1c` 不存在），本报告以 git 实际状态 + 磁盘产物为唯一依据。*
