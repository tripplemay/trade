# B093 — hk_china 真个股 vs proxy 决策级重跑 Evaluator Signoff（2026-07-05）

> **裁定：全 PASS 2/2 → done。裁定 = NO-GO（保 ETF-proxy）成立。** F001（`trade/strategies/hk_china_momentum/factors.py` +12/−2 close-NaN 修 + 新单测 137 行 + 决策脚本 247 行 + 报告 196 行，generator，Workflow 建）+ F002（本独立验收，codex）。
> Evaluator 独立执行（代 Codex；授权 = 用户 /goal + B079–B092 先例），与实现完全隔离，最高怀疑度。
> **核心手段：从缓存快照独立重跑整条决策**——(1) 独立复现报告全部数字（matched top_n=2 + reference top_n=6 逐格 bit 级吻合）；(2) **独立重算 matched real 指标并证 fixed-vs-buggy bit 级恒等**（close-NaN 修 immaterial to verdict 硬证）；(3) **独立定位 close-NaN 逐季逐票 flip**（恰 2 票/1 季，均不在 top-rank）；(4) **独立坐实 proxy 单日历零回归**（25 信号日 0 mismatch，bit 级 BYTE-IDENTICAL）；(5) **独立解 B091-O1「2024-03 Good Friday」悬念**（shared 信号日 = 03-28 落在假日前 → 0 NaN 0 flip）；(6) git diff 坐实 research-only（trade/ 仅 factors.py）；(7) 门禁全绿复跑 + CI 三绿 + HEAD≡prod。
> **被验收提交：`b5c9a10`**（feat B093-F001，7 文件含 factors.py close-NaN 修 + 单测 + 决策脚本 + 报告 + state）+ `2ba60de`（mark done：features/progress，paths-ignore 不触发 CI）。
> **生产面：有**（factors.py 是产品文件，随 backend 部署链上生产）。但零回归 = 生产 proxy 宇宙输出**逐位不变**（25 信号日 bit 级对拍 0 mismatch），故部署安全、prod 行为无变化。

## 0. 本批性质与命门

- **决策级重跑批（B091 解锁后首次真测 real vs proxy）**：B091 修 above_200d_ma 多日历 MA 饥饿 → 真 sleeve 参与 0%→72%。B093 = 携四 caveat 逐一落实 + 修 B091-O1 close-NaN 残留 + matched top_n 公平对照 → 下 **GO/NO-GO**（闸控 BL-B011-S2 Batch 3 激活 hk_china real live Master）。诚实先验：SGOV floor 25 季单牛熊窗 + 幸存者偏 → NO-GO/INCONCLUSIVE 合法，红线 = 把 breadth artifact 粉饰成 GO。
- **★命门 =（i）close-NaN 修零回归**（proxy 单日历逐位不变，任何扰动 = FAIL）+**（ii）四 caveat 诚实落实**（SGOV floor / 幸存者方向性 / matched top_n 真对照 / close-NaN 残留修）+**（iii）NO-GO 与数字一致**（B069/B076 verdict-gating：real 更优却判 NO-GO 或反之才是 issue）。

## 1. 验收结论表

| 验收项（features.json F002 + team-lead 追加） | 裁定 | 证据（独立复算/复现） |
|---|---|---|
| **① close-NaN 修正确性 + 零回归铁律** | **PASS** | 修法：`close = wide.iloc[-1]` → `wide.ffill().iloc[-1]`（各票自身最后有效 close，分子；B091 已修分母 MA）。**★零回归 bit 级独立坐实**：对生产 proxy 宇宙（MCHI/FXI/KWEB/ASHR/SGOV 全 NYSE 单日历）在 **25 个 scored 信号日**逐日 fixed-vs-buggy `assert_series_equal` → **0 mismatch = BYTE-IDENTICAL**；proxy 末行 NaN 季 = **0**（单日历无缺口 → ffill 数学 no-op，演绎必然 + 实证双证）。5 新/旧单测复跑 5 passed（含 `test_single_calendar_gap_free_is_byte_identical`） |
| **② close-NaN 残留逐季逐票定位 + 受影响 2 季处理正确** | **PASS** | **独立探针逐 25 季对拍**：flip 恰 **2 票 / 1 季 = 2023-09-29**（`600900.SH`/`601398.SH` 均 buggy=False→fixed=True；该季 union 末行 09-29 = A股黄金周休 → 10 支 NaN）。**★team-lead 标记的 2024-03 Good Friday 悬念独立解**：B093 用 `shared_quarterly_signal_dates`（proxy∩real 交易日历交集）→ 2024-Q1 信号日 = **2024-03-28**（落在 Good Friday 03-29 **之前**）→ union 末行 NaN=**0**、above_MA flips=**0**。B091-O1 当初按 raw 季末 03-31→末日 03-29 预测的伪防守，在实际 shared 信号日方案下**根本不进入** → 报告「仅 1 季」正确、非漏报。两票 rank=n/a（连动量可选集都不在，top2=[0883.HK,0941.HK]/top6 全港股）→ 翻信号 immaterial to selection |
| **③ matched top_n 真对照落实（真/proxy 同选股数）** | **PASS** | 独立复跑 `selection_top_n`：matched 组 **proxy=2 / real=2**（proxy 引擎 design §8.2 硬 cap {1,2} → 2 是唯一可公平匹配的 breadth），reference 组 proxy=2/real=6 显式标「breadth gap, NOT fair」。**★matched real 指标独立重算**：CAGR **+2.97%**(0.02966228)/Sharpe **0.437**(0.43699448)/vol **7.27%**/MaxDD **−9.20%**(−0.09202964)/defensive 7 —— 与报告 §3a 逐格吻合；proxy +2.75%/0.5216/−3.87% 亦吻合。非各自默认口径混淆 |
| **④ SGOV floor + 幸存者方向性 + close-NaN 四 caveat 诚实** | **PASS** | **(a) SGOV floor**：独立复算 floor=**2020-05-28** → 25 scored 季（2020-06-30..2026-06-30），报告 §5 caveat 1 如实标单牛熊窗、n=25 薄、Sharpe delta<0.1 在噪声内。**(b) 幸存者方向性★**：26 名今日流动宇宙 → 上偏美化 real；报告 §5 caveat 2 正确论述「即便有此顺风 real 仍不胜 proxy → strengthens NO-GO」——幸存者美化 real 而 NO-GO 在美化宇宙下**反更可信**（真值更悲观），未把幸存者当有利因素。**(c) matched**：§5 caveat 3 = top_n=2 双侧，top6 显式贴现为 artifact。**(d) close-NaN**：§5 caveat 4 = 已修 + 独立证 immaterial（§2/①②） |
| **⑤ 真 vs proxy 数字重算 + NO-GO 裁定纪律一致性** | **PASS** | **★fixed-vs-buggy 决策不变性独立硬证**：matched top_n=2 real (cagr,sharpe,vol,mdd,def) fixed = buggy = (0.02966228, 0.43699448, 0.07267638, −0.09202964, 7) **BYTE-IDENTICAL** → close-NaN 修 immaterial to verdict 坐实。**★裁定一致性（verdict-gating B069/B076）**：公平 matched 上 real **不胜** proxy——CAGR 平（+0.22pp）但 Sharpe **更差**（0.437<0.522）、vol 更高、MaxDD **2.4× 更深**（−9.20 vs −3.87）→ NO-GO 与数字**一致**（非 real 更优却判 NO-GO、非反向 manufactured GO）。唯一有利读数（top6 Sharpe 0.616）经 matched 消失，报告正确归因 breadth artifact 非 data-source edge |
| **⑥ 闸控含义（NO-GO → Batch3 不激活）如实记录闭环** | **PASS** | 报告 §6 明载「Do NOT activate real individual-stock hk_china for BL-B011-S2 Batch 3. Keep the ETF proxy.」+ 永久边界「hk_china stays ETF-proxy for LIVE」。**backlog.json** 中 hk-china-real-vs-proxy 条目**已移除**（batch-open b4b3cc2 并入 B093），剩 3 条无关条目 → 悬案（B063 以来）闭合、闸控闭环如实。research-only 未碰 Master live wiring（git diff 证 §⑧） |
| **⑦ Workflow build + 2 对抗验证 un-refuted** | **PASS（journal 不可及，独立复算超越）** | generator_handoff 载 Workflow 3 子代理（1 build + 2 对抗验证 un-refuted，close-NaN 零回归/matched/真不胜 proxy/NO-GO 纪律）。journal 文件在本机可访问路径**未找到**（generator 的 Workflow 在独立 session，transcript 已不可及）——**非阻断**：evaluator 铁律 4 的最强验证是我**从零独立重算全部关键数字**（§①-⑤，比信任 workflow 验证者更强的证据），结论与 handoff 逐项相符 |
| **⑧ research-only 零回归 + 全套门禁 + CI 三绿 + HEAD≡prod** | **PASS** | **research-only scope**：全批 `git diff b4b3cc2^..HEAD -- trade/ workbench/` 仅 **factors.py**（+12/−2 授权 close-NaN 修），无 workbench 产品码；批次余动 = scripts/research×1（新）+ tests/unit×1（新）+ docs×1 + backlog/features/progress。**门禁**：ruff `All checks passed`（3 文件）+ **mypy trade Success 103 文件** + root pytest 新/旧单测 **5 passed** + **backend test_strategies.py 13 passed**（backend venv trade 快照实测含 ffill 修，非 stale）。**CI**：`b5c9a10` push → **Python CI success 7m18s + Workbench Backend CI success 8m27s + Workbench Deploy success 3m33s**（自动链式）。**HEAD≡prod**：`git diff b5c9a10..HEAD -- trade/ workbench/` **字节空**（mark-done 2ba60de 仅动 state JSON）→ HEAD 产品码 ≡ 部署 feat commit |

## 2. 核心不变量复核（最高怀疑度）

**本批命门三重，已从零独立坐实：**
1. **close-NaN 修零回归（★命门）**：proxy 单日历 25 信号日 fixed-vs-buggy bit 级 0 mismatch + 末行 NaN 季 = 0 + ffill no-op 演绎必然 + 单测 pin。
2. **close-NaN 修 immaterial to verdict**：matched real 指标 fixed = buggy bit 级恒等（CAGR/Sharpe/vol/MaxDD/def 五项逐位相等）；flip 恰 2 票/1 季且均不在 top-rank。
3. **NO-GO 与数字一致（verdict-gating）**：公平 matched 上 real 不胜 proxy（Sharpe 更差 + MaxDD 2.4× 深），且幸存者顺风只会美化 real → NO-GO 在美化宇宙下反更稳。唯一有利 top6 读数经 matched 消失 = breadth artifact，报告正确归因未 spin 成 GO。

**四 caveat 逐一落实**（SGOV floor 2020-05-28 独立复算 / 幸存者方向性论述正确 / matched top_n 真同选股数 2v2 / close-NaN 残留修 + immaterial 双证）——无一被当作有利因素，NO-GO 只会偏保守。

## 3. 软观察（非阻断，供 follow-up 参考）

- **O1 — 报告未显式点出「2024-03 无 flip 是因 shared 信号日 03-28 早于 Good Friday」**：报告 §2 数值正确（"exactly one quarter — 2023-09-29"），但未解释 B091-O1 预测的第二季（2024-03 Good Friday）为何在 B093 未触发（答案 = shared_quarterly_signal_dates 交集取 03-28 而非 raw 季末 03-31，避开假日错配）。文档 gap 非缺陷——实质正确，我已独立坐实（§1 ②）。建议若再修订报告可补一句溯源。
- **O2 — proxy sleeve 本身弱基准**（报告 §5 已诚实注）：proxy CAGR +2.75%/Sharpe 0.52 于单熊窗本就低。real 对低基准仍不胜 → NO-GO 结论稳，但两侧绝对表现均弱，非 real 独差。非阻断，报告已披露。
- **O3 — 决策级窗口不可扩**（报告 §6 已注）：25 季 SGOV-floored 单 regime + 幸存者偏 = 结构性天花板，无 PIT 无偏宇宙 + 更长窗则永不可 clean GO。这是数据现实非本批缺陷，报告如实标为「若重访需 (a) PIT survivorship-controlled universe + (b) 更长/regime-diverse 窗」。

三项均非阻断，不撼动 F001 交付（close-NaN 修正确 + 零回归 + matched 对照 + 四 caveat 诚实 + NO-GO 纪律）与命门。

## 4. 结论

**B093 hk_china 真个股 vs proxy 决策级重跑 2 features 全 PASS → done。裁定 = NO-GO（保 ETF-proxy）。**

close-NaN 修正确性经**结构性**（proxy 4 US ETF 单日历 ffill no-op）+ **25 信号日 bit 级对拍 0 mismatch** + 单测 pin 三重坐实零回归命门；修的 flip 经**独立逐季探针**定位为恰 2 票/1 季（2023-09-29，均不在 top-rank）、**team-lead 标记的 2024-03 Good Friday 悬念**经独立复算解为 shared 信号日 03-28 避开假日 → 0 flip；close-NaN 修 **immaterial to verdict** 经 matched real 指标 fixed-vs-buggy **bit 级恒等**硬证；matched top_n 真对照（proxy 2/real 2 同选股数）+ 真 vs proxy 数字（real +2.97%/0.437/−9.20% 不胜 proxy +2.75%/0.522/−3.87%）**独立重算逐格吻合**；**NO-GO 与数字一致**（公平 matched 上 real Sharpe 更差 + MaxDD 2.4× 深，幸存者顺风只美化 real 使 NO-GO 反更稳，唯一有利 top6 读数 = breadth artifact 正确归因，无 manufactured GO，守 B069/B076 verdict-gating）；四 caveat（SGOV floor / 幸存者方向性 / matched / close-NaN）逐一诚实落实无一当有利因素；门禁全绿（ruff / mypy trade 103 / root 5 单测 / backend 13）+ **CI Python/Backend/Deploy 三绿（b5c9a10 自动链式）** + **HEAD 产品码 ≡ 部署 ≡ prod**；research-only（trade/ 仅授权 factors.py 修，未碰 Master live）。三项软观察（O1 报告未溯源 2024-03 shared-date 机制 / O2 proxy 本身弱基准 / O3 窗口结构性不可扩）均**非阻断**，报告已诚实标 NO-GO。

**★闸控含义：BL-B011-S2 Batch 3（激活 hk_china real individual-stock live Master）NOT 推进——保 ETF-proxy 永久边界。hk_china real-stock 悬案（B063 以来「真 sleeve 全防守」→ B090 发现 factor bug → B091 修 → B093 决策级重跑）自此闭合 = NO-GO。**
