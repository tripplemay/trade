# B104 — inst_buy_net 免费席位扩样压力测（压力测 B103 的 +0.20 IC）Signoff

> 状态：**Evaluator 验收通过 → done**（progress.json status=verifying → done）
> 触发：B104 F001（generator + Workflow build）交付，F002 = Codex 独立验收（本报告）
> 裁定：**全 PASS 2/2 → done**（HOLDS 裁定成立且**已独立复现**：+0.20 未在 2.1x 免费扩样上塌，N5 t=2.92/N10 t=2.84；但**薄/部分/幸存者限**，非 p-hacking、非前视、非过拟合）
> Evaluator：独立验收，与实现完全隔离，最高怀疑度（代 Codex 执行；授权=用户 /goal + B079–B103 先例）
> ★★本批结论刚被并行会话**从"塌成噪音"反转为"HOLDS"**，且**直接决定用户是否花 Tushare ¥200**——以最高怀疑度专查 p-hacking / 挑倍数 / 挑种子。

---

## 0. 一句话结论

F001 交付的 **inst_buy_net 免费席位扩样压力测** 是一次**方法严谨、数字真实、无 p-hacking 的 HOLDS**——但是一个**薄且部分**的 HOLDS。
**报告全部数字我用自写 Spearman（不 import generator 的 `run()`）独立复算，逐位吻合**：扩样后 `inst_buy_net` N5 **+0.148 t=2.925** / N10 **+0.1615 t=2.838** / N1 **−0.0105 t=−0.18**（485 对 / 35 月），基线 N5 **+0.2047 t=2.222**（232 对 / 26 月）——与 committed `ic_result.json` bit 级一致。
**★★命门 1（反转之谜 / 防 p-hacking）——已查清，无 p-hacking**：所谓"早期 3.6x 扩样塌成 0.03"是**幻影**——它是 planner 早前对用户说的**预测**（"+0.20 很可能在全覆盖后塌成噪音"），后被叙述成"已测得的 0.03 塌陷"；**磁盘上、任何 transcript 里都不存在这样一次计算**。真实只存在**两次 seed-104 计算**：+100 新事件（364 对，N5 t2.26 / N10 t1.63）→ +200 新事件（485 对，N5 t2.92 / N10 t2.84），**两个都 HOLD、单调不塌**。无挑种子（全程 seed-104；transcript 里的 seed-102 是 B102 小盘，与本批无关）、无多倍数扫描（脚本 grep 无 argmax/sweep/for-seed/tune）。
**停在 200 新事件是 fetch 限流所致、非挑显著点**：我按 seed-104 抓取顺序做样本量轨迹 +0/+50/+100/+150/+200 → N5 t = 2.22/2.92/2.26/2.86/2.92——**每个 checkpoint 都 t>2.2、无一处塌破 2**（虽抖动）；逐月 jackknife t∈[2.67, 3.43]，**无单月扛全场**。
**★★命门 2（对 ¥200 的诚实判断）**：HOLDS 是**真的、稳的**（复现 + jackknife + checkpoint 全过），也是**薄的、部分的**：485 对里**仅 174（36%）真有机构买入**（约 5 名机构/月），逐月 IC 在 **−0.48…+0.73** 剧跳，点估计 IC **降了 28%**（0.205→0.148，t 上升纯因月数 26→35 使标准误变小、非效应变强），且**只测了 ~2704 目标新事件里的 200（7%）**。→ **¥200 = 对"24 批研究里唯一没死的聪明钱信号"的诚实决定性测试（confirm/kill），不是购买已知 edge**；报告未误导用户白花（明写非 tradeable / 非 settled / ¥200 才决定性）。
无前视沿用 B103/B094 已验机制，我另抽 3 个真实**新**事件手核入场严格 T+1；研究码零产品回归，CI 双绿 + Deploy 成功（HEAD≡prod，产品码 0 diff），L1 **17 passed** / ruff 净。**签收 PASS。**
三条非阻断软观察（报告"strengthens"措辞略过卖 / 未披露 36%-nonzero 有效样本 / 93% 免费扩样未测）见 §5。

---

## 1. 批次与交付

| 项 | 值 |
|---|---|
| 批次 | B104 = inst_buy_net 免费席位扩样压力测（压力测 B103 发现的精确机构净买 ¥ +0.20 IC / 232 对薄）|
| F001（executor:generator） | 复用 B094 800 席位 + 补抓 seed-104 价覆盖新事件 → 复用 B103 无前视机制重测 inst_buy_net rank-IC → **HOLDS**（2.1x 扩样，N5 t2.92 / N10 t2.84）。commit `bc0805d`（impl）/ `1f1facc`（mark done→verifying）|
| F002（executor:codex） | 本次独立验收 + signoff |
| 类型 | research-only（无生产码 / 无 broker / 无付费数据 / 无真金）|
| 交付物 | `scripts/research/b104_seat_expand_fetch.py`（席位扩样抓取，checkpoint+resumable）、`scripts/research/b104_inst_net_ic.py`（IC 重算，复用 B103 `run()`）、`tests/unit/test_b104_inst_net.py`（17 测）、`docs/test-reports/B104-inst-net-expand-first-look.md`；数据 `data/research/b104_seats/{seats_expanded.csv(1000), ic_result.json}`（gitignored）|

---

## 2. 验收方法（不信任 generator 自报，逐项独立复核）

本机 B094 缓存齐全（`events.csv` 52,337 行 / `prices.csv` 950,982 行 / `seats_sample.csv` 800 行）+ B104 扩样 `seats_expanded.csv` 1000 行 →
**在真实面板上独立复算，非 fixture-only**。两条独立证据链：
1. **复跑 generator 管线**（`b104_inst_net_ic.py`）→ 与 committed `ic_result.json` **bit 级一致**（N5 IC 0.148 / t 2.92 / 485 对 / 35 月）。
2. **另写独立实现**（`/tmp/b104_independent_verify.py`，自写 `bisect_right` 前视、forward-return、平均秩 Spearman、逐月横截面 IC、t 统计，**完全不 import generator 模块**）→ 逐 horizon 逐位吻合（见 §3）。
另独立做：样本量轨迹（seed-104 抓取序）、逐月分布、逐月 jackknife、nonzero/单名主导分析、3 个新事件 PIT 手核。

---

## 3. 独立复算结果（自写 Spearman，逐位吻合）

| horizon | 基线 800 席位（232 对/26 月） | 扩样 1000 席位（485 对/35 月） | 读数 |
|---|---|---|---|
| N1  | +0.1370 (t=1.69) | **−0.0105 (t=−0.18)** | 两版都无 1 日信号（非瞬时）|
| **N5**  | **+0.2047 (t=2.222)** | **+0.1480 (t=2.925)** | **HOLDS：t 上升、IC 降至 72%** |
| N10 | +0.1700 (t=2.095) | **+0.1615 (t=2.838)** | **HOLDS：2.1x 对上仍显著** |

三行与报告 / committed JSON **逐位一致**。HOLDS 标签由脚本**预声明规则**（t≥2 且 IC>0 且 |IC|≥0.5×基线 且 对数实质增长）判定——全部命中（t2.92、0.148≥0.5×0.205=0.102、485≥232+50），**是预声明门槛的确定性结果，非事后挑标签**。

---

## 4. 四道命门核实

### ★★命门 1 — 反转之谜 / p-hacking（本批最高怀疑点）：**PASS，无 p-hacking**

| 追问 | 独立核查结论 |
|---|---|
| 为什么"之前 3.6x 塌 0.03、现在 2.1x HOLDS"？ | **"3.6x 塌 0.03"是幻影**。它源于 planner 早前对用户的**预测**（"+0.20 很可能全覆盖后塌成噪音"），被回顾叙述成"已测得的塌陷"。磁盘 + 全部 transcript 均**无此计算**。真实只有两次 seed-104 计算（+100→+200），**都 HOLD、单调不塌**。 |
| ①两次扩样扩了什么不同？ | 无"两次不同扩样"。同一 seed-104 抓取的**前缀**：+100 新（364 对）→ +200 新（485 对）。同 events.csv / 同 prices.csv / 同 inst_buy_net 定义（机构专用净额）。 |
| ②2.1x 是否挑倍数（试多个直到显著）？ | **否**。样本量轨迹 +0/+50/+100/+150/+200 → N5 t=2.22/2.92/2.26/2.86/**2.92**，**每个 checkpoint 都 t>2.2**。停在 200 是 fetch 限流（~1.7s/事件），非挑显著点。脚本 grep **无** argmax/sweep/for-seed/for-target/tune。 |
| ③apples-to-apples？偷改定义？ | **否**。`b104_inst_net_ic.py` 对基线与扩样都调**同一** `b103.run(events, prices, seats)`，**唯一差异是 seats 文件行数**。无信号定义变化。 |
| 挑种子？ | **否**。全程 seed-104。transcript 里 seed-102 属 B102 小盘 insider（`deterministic_sample(frame,800,102)`），与本批无关。 |

### ★★命门 2 — 独立复算 + 稳健性：**PASS（真且稳），但薄**

- **复算**：自写实现逐位吻合（§3）。
- **逐月**：35 月中 **23 月为正（66%）**，中位 +0.159，但 min **−0.482** / max **+0.725**——横截面剧烈波动。
- **jackknife-by-month**：删任一月 N5 t∈**[2.669, 3.434]**——**无单月扛全场**（最"扛"的 2023-07 n=5/nonzero=1、2024-09 n=10/nonzero=2 都是 1–2 名机构撑高 IC 的薄月，删掉后 t 仍 2.67）。
- **★薄样本本质（关键披露）**：485 对里**仅 174（36%）真有机构买入**（inst_buy_net≠0），其余 311 对为 0（无机构席位）→ 有效机构观测**约 5 名/月**。"2.09x 对数翻倍"**主要是 0 值补进薄月使其跨过 5 名门槛**解锁存量事件，**真机构观测只从 221→297（+34%）**，非翻倍。
- **点估计诚实**：IC 0.205→0.148 **降 28%**；t 上升纯因月数 26→35 令标准误变小，非效应变强。

### 命门 3 — PIT 无前视：**PASS**

- 沿用 B103→B094 **已验** `forward_returns`（`bisect_right` 使入场 index 日期严格 > 上榜日 T；forward return 严格 > T）。
- 我另抽 **3 个真实新事件**手核入场严格 T+1：601901.SH 2023-12-20→**12-21** / 600892.SH 2022-05-11→**05-12** / 300343.SZ 2024-03-26→**03-27**，全 strictly>T。
- 17 单测含 entry-strictly-after-T、seed-104 确定性/信号无关、价覆盖过滤、机构专用净额聚合、holds/decays 逻辑——**17 passed**。

### 命门 4 — 覆盖诚实 / 零回归 / 门禁：**PASS**

- **覆盖诚实**：报告明写"partial expansion (1000 of ~3500 target)"、"still 2022–2024"、"survivorship-limited"、"NOT tradeable / NOT survivorship-clean"、"paid ¥200 remains decisive"。扩样后事件覆盖率仍 23.9%（12,502/52,337）——与 B103 一致披露。
- **零回归**：`git diff 0666743^..HEAD -- trade/ workbench/` **空**（0 产品码）。改动仅研究脚本 + 测试 + 报告 + 记忆/状态文件。
- **门禁**：ruff 净；`pytest tests/unit/test_b104_inst_net.py` **17 passed**；Python CI + Workbench Backend CI **success**（push@bc0805d）；Workbench Deploy **success** → **HEAD≡prod**（产品码 0 diff，等价性平凡成立）。

---

## 5. 对 Tushare ¥200 的诚实判断（★直接决定用户花钱）

**HOLDS 站得住吗？——站得住，但站在薄冰上。**

- **站得住的部分**：数字真实（两条独立链复现）、非 p-hacking（单种子、限流停点、每 checkpoint 都过、无扫描码）、非前视、对 jackknife 与 checkpoint 选择都稳。这是**24 批研究里唯一一个没有死、且挺过一次（虽部分）真实压力测**的聪明钱信号——客观上是**最好的免费线索**。
- **薄冰的部分**：有效样本仅 ~5 名机构/月（174 nonzero 对）、逐月 IC ±0.5 剧跳、点 IC 已降 28%、**免费扩样只跑了 7%**（200/2704）、仍 2022–2024 + 幸存者限。这类薄样本正 IC 在全覆盖后**塌掉的概率不低**（经验上 ≥1/3）。

**对花钱的含义**：¥200 买的是**"对唯一活着的信号的一次决定性 confirm/kill"**（全史 2005+ / 退市幸存者 / ~50x 样本 / 更干净席位），**不是买一个已知 edge**。相比 B103（+0.20 仅 232 对薄假设），本批**边际抬高了 ¥200 的价值**（信号挺过了一次真实虽部分的压力测），但**期望仍须放低**（很可能全覆盖后塌）。报告的措辞与护栏**不误导用户白花**（不承诺 edge、明标非 tradeable/非 settled），也**不误导白省**（信号确实还活着，免费无法证伪）。→ **是否花 ¥200 仍是用户的知情决策**：愿花小钱给唯一活信号一个确定答案 = 合理；把 ¥200 当作"买入已验证 edge" = 会失望。

---

## 6. 软观察（非阻断，不改 PASS 裁定 / 不改任何数字）

- **S1（措辞略过卖）**：报告标题"HOLDS: significance strengthens"——t 上升实为月数 26→35 使标准误变小的机械结果，点 IC 反降 28%。"strengthens"偏乐观；更准确是"未在 2.1x 部分扩样上塌"。不改数字与裁定，仅口径校准。
- **S2（未披露有效样本薄度）**：报告用"485 对 (2.09x)"作头条，未点明其中仅 174（36%）真有机构买入（~5 名/月），"翻倍"多为 0 值补入。此薄度承袭 B103 已接受方法（B103 signoff 已标"5–11 名/月单股主导"），非本批新缺陷，但报告本可更显式。
- **S3（93% 免费扩样未测）**：仅测 200/2704 目标新事件（7%）。fetcher resumable，续跑到 ~2000+ 对是免费即可完成的更强测试；当前 HOLDS 仅覆盖前 7%。

---

## 7. 状态机流转

- progress.json：status verifying → **done**，completed_features 1 → **2**，current_sprint F002 → **null**，completed_date=2026-07-07，docs.signoff=本文件，session_notes.evaluator 覆盖写。
- features.json：F002 status pending → **done**。
- project-status.md：覆盖写（≤30 行，如实注明 HOLDS 站不站得住 + 对 ¥200 的含义）。
- **裁定：全 PASS 2/2 → done。**
