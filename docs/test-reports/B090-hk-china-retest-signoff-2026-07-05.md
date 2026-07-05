# B090 — HK/China 真数据重测（200D warmup 方法学修 + 真个股 vs proxy）Evaluator Signoff（2026-07-05）

> **裁定：全 PASS 2/2 → done。** F001（`scripts/research/b090_hk_china_{fetch,retest}.py` + 10 单测 + 报告 `docs/test-reports/B090-F001-hk-china-retest.md`，generator）+ F002（本独立验收，codex）。
> Evaluator 独立执行（代 Codex；授权 = 用户 /goal + B079–B089 先例），与实现完全隔离，最高怀疑度。
> 核心手段：**独立重跑 retest 脚本**逐数字复现（warmup 25/25 两侧一致 + proxy/real 全指标 + 根因探针）；**从零构造最小 2-ticker 样本**独立复现 calendar-misalignment bug 并证单日历无害；**独立 FX 方向抽点**（7.8 HKD→0.999 USD）；**读 workflow journal** 复核 2 对抗验证 un-refuted 并抽结论独立再验。
> **被验收提交：`0a8e21d`**（feat B090-F001，4 文件 794 行，**零产品策略码**）+ `c9c36e8`（mark done：features/progress/backlog）。HEAD `0c0f5d0` = chore(backlog) 单文件 paths-ignore 不触发 CI。
> **生产面：无。** F001 全部落在 `scripts/research/` + `tests/` + `docs/`，`trade/` 产品包 diff **字节为空**（`git diff 93493a3..HEAD -- trade/` 空）→ 无部署面、无 VM 核实项（如实标注）。发现的 factor bug **未在本批修**（修需碰产品码 → 正确推 backlog 走独立 spec→build→verify）。

## 0. 本批性质与诚实边界

- **纯研究/负结论批**：目标 = 检验 B063「真个股 sleeve 全防守」是否为 200D-MA warmup 缺失所致（planner 预判大概率 NO-GO，但把假设**真测到**=有效结论）。
- **核心交付 = 诚实负结论 + 真根因发现**：warmup 假设**证伪**；真根因 = 共享因子 `above_200d_ma` 在真·多日历个股宇宙上的 **calendar-misalignment bug**（200-row 窗 × 3 交易日历 union → MA 恒 NaN → `regional_risk_off` 每季触发 → 真 sleeve 100% 趴 SGOV）。
- **role-context「Fixture-only ≠ 策略性能 conclusion」适用性核对**：本批在**真·akshare 价格 snapshot**（31 标的 130,371 行 qfq）上跑，非合成 fixture。但因 factor bug，真 sleeve **一股未持** → 报告如实标注 **INCONCLUSIVE**：真个股 vs proxy 的原始诉求（BL-B011-S2）**这次仍未真正测到**，未越界宣称任何真-vs-proxy edge。诚实合规。
- **spec 点名最大陷阱 = 把 real Sharpe~1.0 误读为真 sleeve 跑赢** → 报告 §5 已焊死：real 曲线 = 100% SGOV 现金 carry（vol~0），⚠️ 明标「artifact, not an edge, must NOT be read as outperforming」。未吹 edge。

## 1. 验收结论表

| 验收项（features.json F002 + team-lead 追加） | 裁定 | 证据（独立复算/复现） |
|---|---|---|
| **① warmup 假设证伪独立复核** | **PASS** | 独立重跑 `b090_hk_china_retest`（缓存真数据）：**NO-WARMUP（history 截到 2020-05-28）real defensive 25/25、avg_holdings 0.00**；**WITH-WARMUP（全 history 回 2001–2004）real defensive 25/25、avg_holdings 0.00**。warmup 令 real defensive 变化 **+0**。关键佐证 warmup **确被施加**：avg_scored **19.36→23.12**（全 history 确让更多名字有历史可打分），**然持股仍 0** → 卡点在 scoring **下游**（regional_risk_off 门），非 warmup 饥饿。证伪逻辑链（warmup 修好→仍全防守→故非 warmup 之罪）**成立**。逐数字与报告 §4 相等 |
| **② factor bug 真根因独立确认（最小可复现）** | **PASS** | **从零构造 2-ticker 样本**（不复用被验脚本探针）：AAA=Mon–Fri、BBB=Mon–Thu（**故意异日历**），二者价格**严格单调上涨**（最新 close 必远高于 MA）。喂 `above_200d_ma`：union 帧最后 200 行 BBB 仅 **160/200 non-NaN → above_MA = False（错，应 True）**；AAA 200/200 → True。机理独立坐实：`min_periods=200` 的 200-row 窗遇 union 日历 → 跨市场空缺注 NaN → 窗内非 NaN <200 → MA 恒 NaN → `close>NaN`=False→`fillna(False)`。真数据探针亦独立复现（0700.HK 188/200 union=False HK-only=True；9988.HK 188/200；600519.SH 184/200），reason breakdown `regional_risk_off`=25/25，全与报告 §6 逐位相等 |
| **③ 单日历 proxy 无害（backlog 零回归前提）** | **PASS** | 同 2-ticker 样本置于**单一日历**（AAA/BBB 同 Mon–Fri，如 US ETF 同 NYSE）：BBB 200/200 non-NaN → **above_MA = True（正确）**。→ bug **仅在真·多日历宇宙触发，单日历无害**。真数据侧独立佐证：**proxy sleeve defensive = 12/25（非 25/25）**——proxy（MCHI/FXI/KWEB/ASHR + SGOV 全 NYSE 单日历）MA 正常计算、并非每季防守。这坐实 backlog 修复项「零回归铁律 = proxy 逐位不变」的前提成立 |
| **④ 真个股 vs proxy 是否真测到（诚实度）** | **PASS** | 报告 §7 **如实标 INCONCLUSIVE**：因 factor bug，real 25/25 全防守、**一股未持** → 本次「真-vs-proxy」**仍未真正测到**（B063 曾因全防守 0 选股没测到，本次同样卡在 bug）。报告未夸大：显式写「the real strategy never actually participated, so this run yields no clean evidence either way」，且 bias_notes 标 real edge 为「UPPER BOUND / 需 matched top_n 再跑隔离 data-source」。测到程度**如实说明**，无过度声称 |
| **⑤ adj_close 口径 caveat 诚实标注** | **PASS** | 用 **qfq 近似**（非真 Tiingo adj）。代码 `_normalize_frame` 将 `close` 与 `adj_close` 同置为 qfq 收盘；报告 §8.1 明标「qfq ≈ adj_close, not identical to Tiingo... direction/momentum preserved but not the exact total-return series the live flagship uses」。口径与 caveat **诚实焊死**，未冒充真 adj |
| **⑥ FX 方向正确（HKD/USD 未倒置）** | **PASS** | 独立抽点：`FxConverter.to_usd(7.8 HKD, 2024-06-28)` = **0.99894 USD**。原始 DEXHKUS@2024-06-28 = **7.8083**（peg 带 7.75–7.85 内），7.8/7.8083≈0.999 → 方向 = **除以 rate（local/rate=USD）正确**，非倒置（倒置会得 7.8×7.8≈60）。CNY/HKD 两币种均载入 |
| **⑦ Workflow build + 2 对抗验证 un-refuted 复核** | **PASS** | 定位 workflow journal `wf_8b114995-355`：build agent 产出数字（proxy cagr 0.0275/sharpe 0.5216、real cagr 0.0003/sharpe 0.9973、defensive 25/25）与我复现**逐位相等**；**2 个对抗验证者均 `refuted=false`**（un-refuted 属实），各项 `adj_close_ok/fx_direction_ok/warmup_filter_ok/recompute_matches/zero_regression/gates_green/verdict_honest`=true。抽 3 条结论独立再验：fx_direction_ok（我 ✓）、recompute_matches（我全 retest 复现 ✓）、root-cause 日历错位（我最小样本复现 ✓）——全 hold |
| **⑧ 零回归 + L1 + Gates + CI 绿 + HEAD≡prod** | **PASS** | **零回归**：F001 feat `0a8e21d` 仅动 **4 文件**（fetch 230 + retest 322 + 单测 140 + 报告 102），`git diff 93493a3..HEAD -- trade/` **字节空**，产品策略码 **0 行**；`above_200d_ma` bug 被**发现未修**（推 backlog）。**L1/Gates**：`ruff check`（3 文件）All passed；**10 单测本地实跑 10 passed**；`mypy trade` = **Success（103 文件）**。**CI**：含 F001 代码的 push（tip `c9c36e8`）**Python CI 6m49s + Workbench Backend CI 8m52s + Deploy 3m44s 全绿**。HEAD `0c0f5d0` = chore(backlog) 单文件 paths-ignore 合法不触发。**HEAD≡prod**：research-only 无生产面/无部署项，如实标注 |

## 2. 核心不变量复核（最高怀疑度）

**本批核心 = 假设证伪 + 真根因发现的证据质量，已三重独立坐实：**
1. **warmup 假设证伪**（独立重跑，非引用报告）：NO/WITH-warmup 均 25/25 全防守、0 持股，defensive 变化 +0；avg_scored 19→23 证 warmup 确被施加却不改结局 → 卡点非 warmup。
2. **真根因 = calendar-misalignment bug**（从零最小 2-ticker 样本独立复现）：严格上涨的异日历 ticker 在 union 帧被误判「below MA」（160/200 non-NaN→MA=NaN），单日历同数据正确（200/200→True）；真数据探针 0700/9988/600519 逐位复现。
3. **单日历无害 = backlog 零回归前提**（独立证 + 真数据 proxy 12/25 佐证）：bug 只在多日历触发，生产 proxy（US ETF 同 NYSE）不受影响。

**FX 方向**经独立抽点硬证（0.999 USD，非倒置）；**qfq caveat** 经代码 + 报告 §8.1 硬证诚实；**零回归**经 4 文件 diff + `trade/` 空 diff + 产品码 0 行硬证；**2 对抗验证 un-refuted** 经 journal 复核 + 抽 3 结论独立再验硬证。

## 3. 软观察（非阻断，供后续批参考）

- **O1 — 3 个新研究脚本未被 mypy 覆盖**（非阻断）：Python CI 仅跑 `mypy trade`（产品包），不覆盖 `scripts/` + `tests/`。独立对 3 文件直跑 mypy 仅暴露**调用层 artifacts**（`akshare` 无 py.typed stub 的 import-untyped；`scripts.research` 双模块名解析告警），**非真类型缺陷**。两个对抗验证者已注此点。research-only，非阻断；后续如把 research 脚本纳 CI 类型门可补 `--explicit-package-bases`。
- **O2 — 可跑窗口短且偏**（非阻断，报告已披露）：即便 factor bug 修好，可跑窗仅 **25 季（2020-06…2026-06）**，被 SGOV 上市（2020-05-28）floor 住，样本重压 2021–24 中国股灾；且 26 名真宇宙为「今日流动」名单（幸存者偏差，真 edge 为乐观上界）。报告 §8 已如实注 caveat 2/3/5。→ 真-vs-proxy 的**决策级**结论须待 (a) factor bug 修（backlog）+ (b) 更长/无偏窗 + matched top_n 再跑，方可下 GO/NO-GO。本批如实标 INCONCLUSIVE 已正确。

## 4. 结论

**B090 HK/China 真数据重测 2 features 全 PASS → done。**
warmup 假设经**独立重跑**证伪（NO/WITH-warmup 均 25/25 全防守 0 持股，defensive 变化 +0；avg_scored 19→23 证 warmup 确施加却不改局）；真根因 `above_200d_ma` calendar-misalignment bug 经**从零最小 2-ticker 样本**独立复现（异日历严格上涨 ticker 被误判 below MA）并证**单日历无害**（backlog 零回归前提成立，真数据 proxy 12/25 佐证）；真个股 vs proxy 因 bug **仍未真正测到**、报告如实标 INCONCLUSIVE 未夸大；qfq 口径 + caveat 诚实焊死；FX 方向经独立抽点正确（7.8 HKD→0.999 USD 非倒置）；「Workflow build + 2 对抗验证 un-refuted」经 journal 复核属实 + 抽 3 结论独立再验全 hold；零回归 = 4 文件 diff + `trade/` 空 diff + **产品策略码 0 行**（bug 发现未修、正确推 backlog）+ Gates 全绿（ruff/10 单测/mypy trade clean）+ **Python CI/Backend CI/Deploy 绿（c9c36e8）**；**无生产面**（research-only，HEAD≡prod 无部署项，如实标注）。两项软观察（O1 脚本未纳 mypy CI / O2 窗口短偏 → 决策级结论待 bug 修 + 无偏窗再跑）均**非阻断**，报告已诚实标 INCONCLUSIVE，供后续 backlog 修复项与真策略集成参考。
