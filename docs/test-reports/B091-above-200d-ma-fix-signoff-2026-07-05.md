# B091 — 修 above_200d_ma 多日历 MA bug Evaluator Signoff（2026-07-05）

> **裁定：全 PASS 2/2 → done。** F001（`trade/strategies/hk_china_momentum/factors.py` +23/−1 + 3 新单测 + 报告，generator，Workflow 建）+ F002（本独立验收，codex）。
> Evaluator 独立执行（代 Codex；授权 = 用户 /goal + B079–B090 先例），与实现完全隔离，最高怀疑度。
> 核心手段：**独立取修前(94f8172)与修后(HEAD)两版 `above_200d_ma` 对拍**——单日历 bit 级零回归（真 proxy 宇宙 16 季末 + 200 随机 fuzz 帧 + 边界，逐位吻合）；**从零自建 2-ticker 异日历样本**独立复现多日历修复；**真数据 24 季末 OLD-vs-NEW 全量对拍**（OLD above 恒 0 → NEW 5-30，regional_risk_off 9/24 翻 False）；**变异检查**（回退 fix → 单测 (a) 红）；**读 workflow journal** 复核 2 对抗验证 un-refuted；**只读 VM** 确认 prod 跑修复 commit。
> **被验收提交：`b35a638`**（feat B091-F001，3 文件：factors.py +23/−1、新单测 156 行、报告 30 行）+ `6653781`（mark done：features/progress，paths-ignore 不触发 CI）。
> **生产面：有**（与 B090 research-only 不同）。`factors.py` 是产品文件，随 workbench backend 部署链上生产。但零回归 = 生产 proxy 宇宙输出**逐位不变**，故部署安全、prod 行为无变化（已 VM 独立核实）。

## 0. 本批性质与命门

- **纯 bug-fix 批**：修 B090 发现并经 Codex F002 独立复现坐实的真根因——`above_200d_ma` 对**多交易日历 union** 宽表 `rolling(200, min_periods=200)` → 跨市日注 NaN → 任一票 200-row 窗内非 NaN < 200 → MA 恒 NaN → 读「below MA」→ `regional_risk_off` 每季触发 → 真个股 sleeve 100% 趴 SGOV。
- **修法**：新 helper `_latest_ma_own_calendar(col, ma_long)` = `col.dropna()` **前置** rolling（各票在**自身日历**上算 MA，取最新值；自身观测 < ma_long → NaN）；`above_200d_ma` 改 `wide.apply(...)` 逐列算 MA；`close = wide.iloc[-1]` / `(close > ma).fillna(False)` 语义 + `trend_pass` 接口不变。
- **★命门 = 零回归铁律**：live hk_china 生产宇宙 = `HK_CHINA_TICKERS = (MCHI, FXI, KWEB, ASHR)` 4 支 US-listed ETF（全 NYSE 单日历）+ SGOV 防守票。单日历列无缺口 → `dropna()` = **no-op** → 输出**逐位不变**。任何对单日历 proxy 路径的扰动 = FAIL。

## 1. 验收结论表

| 验收项（features.json F002 + team-lead 追加） | 裁定 | 证据（独立复算/复现） |
|---|---|---|
| **① 修复正确性（多日历 MA 有效）** | **PASS** | **(a) 自建独立样本**：AAA=Mon-Fri / BBB=Mon-Thu（异日历）+ 严格单调上涨、各 250 自观测 → union 帧 BBB 仅 160/200 non-NaN。修后（两票均落在最后 union 日）above_MA=**True**；旧 union 公式=**False**（bug in-test 复现）。**(b) 真数据 24 季末全量对拍**：OLD above-count 在**全部 24 个季末恒 = 0**（bug 饿死一切，正好复现 B090 real 25/25 全防守），NEW above-count = **5–30**；`regional_risk_off` 由 OLD 24/24 恒 True → NEW **9/24 翻 False**（real sleeve 从 0% 参与 → ~37% 参与）。**(c) 点名 acceptance 0700.HK**：真数据 as_of=2024-06-28，OLD=False → NEW=**True**（own_obs=4926，last_union_close 非 NaN）。修复确实解真根因 |
| **② 零回归铁律（proxy 单日历逐位不变）** | **PASS** | **结构性**：生产宇宙 4 支 US ETF 单 NYSE 日历 → dropna no-op。**bit 级实证**（独立取 94f8172 旧版对拍）：(i) 真 proxy 宇宙 MCHI/FXI/KWEB/ASHR/SGOV **16 个季末（2022–2025）NEW==OLD 逐位吻合**（0 mismatch）；(ii) **200 个随机单日历帧 fuzz → 0 处不吻合**（index+values+dtype 全等）；(iii) 单测 (b) `assert_series_equal(check_names=False)` + item 级恒等 PASS（唯一差异 = cosmetic Series `.name`，无 consumer 读）。**wired workbench 生产快照不受扰**：prod 行为 = proxy 输出逐位不变 → 下游推荐逐位不变（演绎必然 + bit 级实证双证）|
| **③ 语义保持 + 无前视** | **PASS** | <200 自观测 → NaN MA → **False**（单测 (c) + 我复现 SHORT/150obs 双版均 False）；`_wide_close` 仍 filter `date <= as_of`（未改，无前视）；`fillna(False)` 不变；`trend_pass` 接口签名不变 |
| **④ 变异检查（单测有牙）** | **PASS** | 独立把 `factors.py` 回退成 OLD union rolling → 新单测 **(a) FAIL**（`assert False is True`），(b)/(c) 仍 pass（设计上 OLD-兼容）→ 证 (a) 真守多日历修复，非空断言。已还原 factors.py 干净（git diff 空）|
| **⑤ 真数据变化如实呈现 + follow-up 去向** | **PASS** | real sleeve 全防守问题**大幅缓解**（regional_risk_off 恒 True → 9/24 翻 False），数字与 F001 报告方向一致。**决策级 real-vs-proxy 重跑本批未做**（正确——F001 = 仅修 bug，越界须独立 spec）；follow-up 记录于 B090 signoff §3 O2 + B091 F001 报告 §follow-up。见 §3 O2（缺离散 backlog 条目，软性）|
| **⑥ Workflow build + 2 对抗验证 un-refuted 复核** | **PASS** | journal `wf_2a2ea377-422`：1 fix agent（`aeb7e7f…`）+ **2 对抗验证者（`af021467…` / `ab48abbc…`）均 `refuted=false`**，`zero_regression_holds/multi_calendar_fixed/semantics_preserved/workbench_green/gates_green/blast_radius_ok`=true，issues 空。两验证者各以独立法证零回归（random-walk 12t/400d+边界 / 200 fuzz 帧）——与我独立复现逐位相符。fix agent summary **明确记录**「close still = wide.iloc[-1]」（O1 是知情保留非疏漏）|
| **⑦ 全套门禁 + CI 绿 + HEAD≡prod** | **PASS** | 触 `trade/` → **mypy trade = Success（103 文件）** + **ruff check . All passed**；root pytest hk_china 相关 **118 passed** + 新单测 **3 passed**；backend **test_strategies.py 13 passed**（backend venv 内 trade 快照含修复标记，实测非 stale）。**CI**：`b35a638` push → **Python CI 6m50s + Workbench Backend CI 8m49s + Workbench Deploy 3m34s 全 success**（自动链式部署）。**HEAD≡prod**：HEAD `6653781` 仅动 state JSON（`git diff b35a638..HEAD -- trade/ workbench/backend/` **字节空**）；VM current release symlink = `b35a63860e89…`（= 修复 commit），active `trade` 包 factors.py 含 `_latest_ma_own_calendar` 标记 ×3 → prod 跑修复码 |

## 2. 核心不变量复核（最高怀疑度）

**本批命门 = 零回归铁律，已四重独立坐实：**
1. **结构性**：生产 `HK_CHINA_TICKERS = (MCHI/FXI/KWEB/ASHR)` 全 NYSE 单日历 → `dropna()` 对无缺口列 = 数学 no-op → `above_200d_ma` 逐位不变。
2. **真数据 bit 级**：独立取修前(94f8172) vs 修后两版，对真 proxy 宇宙 16 个季末对拍，NEW==OLD 逐位吻合、0 mismatch。
3. **fuzz**：200 个随机单日历帧，NEW vs OLD 0 处不吻合。
4. **VM 实证**：prod current release = 修复 commit b35a638，active trade 包含修复标记。

**修复有效性**经真数据 24 季末全量对拍硬证（OLD above 恒 0 → NEW 5-30，regional_risk_off 9/24 翻 False）；**单测有牙**经变异检查硬证（回退 → (a) 红）；**2 对抗验证 un-refuted** 经 journal 复核 + 独立再现其零回归/多日历结论硬证。

## 3. 软观察（非阻断，供 follow-up 参考）

- **O1 — 残留 `close = wide.iloc[-1]` union-最后行 NaN（非本批引入、非回归、非 F001 范围）**：修复只改 MA（分母），`close`（分子）仍取 union 帧最后一行——**与修前完全相同**。若某票在**最后一个 union 交易日**未交易（节假日错配），其 `close`=NaN → `above_MA`=False，无论趋势。真缓存数据 24 季末中仅 **2 季触发**（2023-09-30 last-union=09-29 → 10 支 A 股 NaN；2024-03-31 last-union=03-29 Good Friday → 16 支 HK NaN）。**对生产无影响**（proxy 单日历每票每 union 日都交易，永不触发）。F001 acceptance = 修 MA rolling 饥饿，此项正交且先存。**须在 follow-up 决策级重跑中处理**（否则可能把 close-NaN 造成的伪防守季误记为真信号）。建议 Planner 登 backlog / 并入重跑 spec caveat。fix agent 已知情保留（journal 明载）。
- **O2 — 决策级 real-vs-proxy 重跑无离散 backlog.json 条目（软性文档 gap）**：F001 修复**解锁**了 B090 遗留的决策级重跑（我独立证 regional_risk_off 现 9/24 翻 False → real sleeve 真参与）。本批**正确地未跑**（越界）。但该 follow-up 仅记录于 B090 signoff §3 O2 + B091 F001 报告 §follow-up，**未在 backlog.json 立离散条目**。建议 Planner 补登，携 B090 O2 三 caveat（SGOV 2020-05 floor + 幸存者偏差 + matched top_n 未做）**及本 O1 close-NaN caveat**，方可下决策级 GO/NO-GO。

两项均非阻断，不撼动 F001 交付物（修 MA 饥饿 bug）与零回归命门。

## 4. 结论

**B091 修 above_200d_ma 多日历 MA bug 2 features 全 PASS → done。**
修复正确性经**从零自建 2-ticker 异日历样本**（旧 union=False bug 复现 → 修后 True）+ **真数据 24 季末全量对拍**（OLD above 恒 0 → NEW 5-30，regional_risk_off 9/24 翻 False，real sleeve 从 0% → ~37% 参与）+ 点名 0700.HK 真数据 OLD=False→NEW=True 三重硬证；**零回归铁律**（命门）经结构性（生产 4 US ETF 单日历 dropna no-op）+ 真 proxy 宇宙 16 季末 bit 级对拍（0 mismatch）+ 200 fuzz 帧（0 mismatch）+ 单测 assert_series_equal + VM prod 跑修复 commit 四重坐实；语义（<200 obs→False / 无前视 / trend_pass 接口）保持；**单测有牙**经变异检查（回退 → (a) 红）证；**2 对抗验证 un-refuted** 经 journal 复核属实 + 独立再现全 hold；门禁全绿（mypy trade 103 / ruff / root 118+3 / backend 13）+ **CI Python/Backend/Deploy 三绿（b35a638 自动链式）** + **HEAD 产品码 ≡ 部署 ≡ prod**。两项软观察（O1 残留 close-NaN 先存非回归、须 follow-up 处理；O2 决策级重跑无离散 backlog 条目、软性文档 gap）均**非阻断**，供后续 backlog 决策级重跑修复项参考。
