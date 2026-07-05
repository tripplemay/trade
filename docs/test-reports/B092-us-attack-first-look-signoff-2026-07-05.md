# B092 — US Attack (concentrated momentum+quality) FIRST-LOOK Evaluator Signoff（2026-07-05）

> **裁定：全 PASS 2/2 → done。** F001（`scripts/research/b092_us_universe_fetch.py` + `b092_us_attack_backtest.py` + 18 单测 + 报告，generator，Workflow 建）+ F002（本独立验收，codex）。
> Evaluator 独立执行（代 Codex；授权 = 用户 /goal + B079–B091 先例），与实现完全隔离，最高怀疑度。
> **核心手段：从缓存快照独立重跑整条回测**——9 个指标格逐格 bit 级复现（STRATEGY full 26.53%/1.36/−19.2%；★OOS 策略 Sharpe 1.45 < EW 1.54）；**独立验证 2017 floor 是真数据边界非调参**（pre-2017 1018 个不可能月度 vs 2017+ 仅 19；UNH pre-2017 +2845% 坐实报告 "+2800%"）；**独立复核 missing-6 财报名单**（PNC/PG/CAT/ITW/VZ/T 逐字吻合）；**读 workflow journal** 复核 2 对抗验证 un-refuted（均 recompute_matches=true / oos_edge_real=false / refuted=false）；**git diff 坐实零回归**（trade/+workbench/ 空）；ruff + 18 单测 fresh 复跑绿；CI 三绿。
> **被验收提交：`b285566`**（feat B092-F001，4 文件：universe_fetch 335 行、backtest 391 行、18 单测 294 行、报告 146 行）+ `4c97eb9`（mark done：features/progress）。
> **生产面：无**（research-only，与 B090 同）。批次全程 0 行产品/trade/Master 码，快照数据 gitignored；prod 行为与 B092 前完全一致。

## 0. 本批性质与命门

- **纯 research-only first-look（低承诺可行性探针）**：回答「US 集中动量+质量选股对**正确基线**（同宇宙等权）是否有**样本外**风险调整 edge」——在承诺全 4-feature P1 build **之前**。诚实先验：A 股姊妹（cn_attack）已 OOS-negative/幸存者偏差（B070），默认怀疑。**INCONCLUSIVE/NO-GO 是合法答案；红线是把样本内过拟合 winner 粉饰成 GO。**
- **★命门 = 数字诚实性 + first-look 纪律**：(1) 报告的对照数字须可独立复现且与裁定一致（不得达 GO 门槛却标 INCONCLUSIVE 或反之，B077/B085 纪律）；(2) 幸存者/单牛市/A股姊妹三重悲观 caveat 须诚实；(3) 先验因子定义无扫参（过拟合红旗）；(4) 推论边界不得从「不建全 P1」外推为「美股选股永久无效」。

## 1. 验收结论表

| 验收项（features.json F002 + team-lead 追加） | 裁定 | 证据（独立复算/复现） |
|---|---|---|
| **① 对照数字独立复算 + 非退化 + 裁定一致性** | **PASS** | 从缓存快照（461912 行价格/101 票 + 3262 行财报/94 票）**独立重跑整条回测**，**9 个指标格逐格 bit 级吻合**：STRATEGY full 26.53%/1.36/−19.2%、in-samp 26.75%/1.30、oos 26.87%/**1.45**；EW full 21.44%/1.14、oos 24.20%/**1.54**；SPY full 17.08%/0.98。诊断亦吻合（114 月/median qualified 63/selected 15/min 15/universe 100/窗 2017-02-28..2026-07-02/split 68-46）。**非退化**（有交易、选合理大盘股、Sharpe 1.3-1.45 合理非离谱）。**★裁定一致性**：对正确基线（同宇宙 EW）——策略样本内 CAGR 胜（26.75 vs 20.02）、OOS 微胜（+2.67pt）**但 OOS 风险调整 edge 为负（策略 Sharpe 1.45 < EW 1.54）**→ GO 门槛（OOS Sharpe 胜 EW）**未达** → INCONCLUSIVE 是纪律裁定，非「达 GO 却标保守」亦非反向。B077/B085 first-look 纪律守 |
| **② 幸存者偏差披露 + 方向性正确** | **PASS** | 宇宙 = 今日 S&P-100 幸存者 → 上偏**同时**美化 strategy 与 EW。报告正确论述：strategy-vs-EW（共享宇宙）**部分**抵消幸存者偏 → 薄/负的 OOS Sharpe delta 才是要看的数字。**★方向性**：幸存者偏美化收益 → 无偏真值只会**更悲观** → INCONCLUSIVE 在幸存者宇宙下**反而更可信/更保守**（若已美化仍无 edge，则真相更是 NO-GO）。报告方向论述正确，未把幸存者偏当作有利因素 |
| **③ 因子定义先验性（无扫参）+ 模块关系如实** | **PASS** | 先验为模块级冻结常量（`TOP_N=15`/`LOOKBACK_MONTHS=6`/`SKIP_MONTHS=1`/`QUALITY_DROP_QUANTILE=0.25`/`COST_PER_TURNOVER=0.0010`），**代码无 grid/sweep/optimize/best_/itertools.product**（grep 清）；docstring 明载「priors chosen ONCE — no parameter tuning to the backtest」。**模块关系**：本批为**新独立构造**（quality-filter → 纯动量 rank → top-15，2 层 filter-then-rank），**不同于**生产 `us_quality_momentum`（B025 5 因子 composite 35/30/15/10/10）→ research 隔离合理、契合 B055 spec 的 filter-then-rank 设计；报告**未虚称复用**生产模块（诚实，见 §3 O1 微 gap） |
| **④ 数据源口径诚实** | **PASS** | akshare qfq，**明标 `adj_close` = qfq close 非真 vendor adj_close**（B090 caveat 沿用）；SEC EDGAR companyfacts 真 PIT 财报，**94/100**（missing-6 = **PNC/PG/CAT/ITW/VZ/T** 独立复核逐字吻合，非标准 XBRL 标签）；PIT 经 `filed <= t` 门（代码 + 单测 `test_quality_asof_is_point_in_time` 双证，无前视）。**★2017 floor 独立验证为真数据边界非调参**：cleaned 月度上 pre-2017 有 **1018** 个不可能月度移动（\|ret\|>阈）vs 2017+ 仅 **19**；UNH pre-2017 max **+2845.5%**（坐实报告 "UNH +2800%"）、MSFT +616%、BLK +224% → floor 是 data-availability 边界，移动它不利于 performance（保守方向） |
| **⑤ 无过拟合红旗 + 诚实裁定** | **PASS** | Sharpe 1.30-1.45 对集中 15 票美股动量在 2017-26 强牛可信，**非 >2.5 离谱过拟合签名**；EW/SPY 基线 Sharpe ~1.0-1.6 亦在 sane 区（plumbing 诚实）；早期退化跑（pre-2017 glitch 致 EW "CAGR" 56-820%）已被抓修（本身即 pipeline 现正常的证据）。**★过拟合正解**：样本内选股胜 EW（1.30 vs 0.97）**OOS 反转/消失**（1.45 < 1.54）= 典型 edge-decay，报告**如实命名非 spin 成 GO**。裁定 INCONCLUSIVE + 明列 pre-conditions（付费无偏 vendor + OOS Sharpe 须胜 EW）合法 |
| **⑥「B055 全 P1 不推荐建」推论边界** | **PASS** | 报告措辞：「evidence does not support committing to the full 4-feature P1 attack build... weak/ambiguous edge, not a GO」+ 明确 pre-conditions（若仍追须付费幸存者-free vendor 延窗至 pre-2017 含退市名 + 重测须 OOS Sharpe 胜 EW）→ **有界结论**，**未**外推为「美股选股永久无效」。commit「B055 全 P1 不推荐建」= 有界（不在此证据基础上建全 P1），非绝对否定 |
| **⑦ Workflow build + 2 对抗验证 un-refuted 复核** | **PASS** | journal `wf_0478a172-465`：1 build agent（`a53a3bbf…`，输出与报告逐字吻合）+ **2 对抗验证者（`a4f5791b…` / `a4c6018f…`）均 `refuted=false`**，且 `recompute_matches/oos_edge_real=false/sharpe_plausible/priors_not_tuned/non_degenerate/no_look_ahead/baseline_honest/research_only/verdict_honest` 全 true；两者 issues = 报告的诚实 caveat（幸存者未量化/单牛市/adj_close 保真/floor 保守）。a4c6 独立佐证「2017 floor 是 defensible 数据边界非 backtest-maximizing」——与我独立复算相符 |
| **⑧ research-only 零回归 + L1 + CI + HEAD≡prod** | **PASS** | **零回归 git 级坐实**：`git diff 0374b32..HEAD -- trade/ workbench/` **字节空**；批次仅动 `scripts/research/`×2 + `tests/unit/`×1 + `docs/`×1 + state JSON；快照数据 `git check-ignore` 命中（不入 git）。**L1**：ruff `All checks passed` + `pytest test_b092_us_attack.py` **18 passed**（fresh 复跑）。**CI**：`b285566` push → **Python CI success（5m28s）+ Workbench Backend CI success（8m43s）+ Workbench Deploy success（3m39s）**。**HEAD≡prod**：无产品码变更 → prod 行为与 B092 前逐位一致（research 脚本永不部署）|

## 2. 核心不变量复核（最高怀疑度）

**本批命门 = 数字诚实性 + first-look 纪律，已多重独立坐实：**
1. **数字可复现**：从缓存快照独立重跑，9 指标格逐格 bit 级吻合报告；无 cherry-pick、无隐藏参数。
2. **裁定与数字一致**：OOS 风险调整 edge 为负（1.45 < 1.54）→ GO 门槛未达 → INCONCLUSIVE 是纪律裁定（非达标却保守、非反向）。
3. **先验无扫参**：常量冻结、grep 无 grid/optimize、docstring 明载 no tuning。
4. **floor 非调参**：pre-2017 数据 1018 个不可能移动独立坐实，floor 是数据边界。
5. **零回归**：git diff trade/+workbench/ 空、快照 gitignored、CI 绿。
6. **2 对抗验证 un-refuted**：journal 复核属实 + 独立再现其「无 OOS edge / 诚实裁定」结论。

**方向性红线守住**：幸存者偏 + 单牛市窗 + A股姊妹 OOS-negative 三重悲观 caveat 使 INCONCLUSIVE 只会偏保守（真相更可能 NO-GO）——报告未把任一 caveat 当作有利因素。

## 3. 软观察（非阻断，供 follow-up 参考）

- **O1 — 报告未显式点名生产 `us_quality_momentum` 模块关系（文档 gap，非缺陷）**：本批新构 filter-then-rank research 策略，**不同于**生产 B025 5 因子 composite。报告**诚实未虚称复用**，且 standalone 对 research 隔离是合理选择（避免触生产 plumbing、契合 B055 spec）。但报告未用一行说明「为何新构而非复用生产模块」。**非阻断**（不影响数字与裁定），建议未来 P1 spec 若推进时明确二者取舍。
- **O2 — 成本非对称（strategy 付 10bps turnover，EW 基线不付）**：`period_return` 对 strategy 扣 turnover 成本、EW 基线未扣。此为**保守-against-strategy**（令 edge 更难显现）→ **不撼动**怀疑向 INCONCLUSIVE 裁定（方向正确）。但未来决策级 P1 重测宜用完全成本对称对照更干净。**非阻断**。
- **O3 — 2017 floor 略保守（验证者 a4c6 称 2016 已 0 极端移动，我复算 cleaned 月度 2016 仍 ~13）**：阈值/是否 spike-clean 致精确计数差异，**不 material**；floor 无论如何是 defensible 数据边界，且保守方向（不利 performance）。**非阻断**。

三项均非阻断，不撼动 F001 交付物（诚实 INCONCLUSIVE first-look）与命门（数字诚实 + 零回归）。

## 4. 结论

**B092 US 进攻选股 first-look 2 features 全 PASS → done。**
对照数字经**从缓存快照独立重跑整条回测**硬证（9 指标格逐格 bit 级吻合，STRATEGY full 26.53%/1.36、★OOS 策略 Sharpe **1.45 < EW 1.54**）；**裁定一致性**（OOS 风险调整 edge 为负 → GO 门槛未达 → INCONCLUSIVE 纪律裁定，B077/B085 守）；**幸存者偏差方向性**正确（美化收益 → 无偏真相更悲观 → INCONCLUSIVE 更可信）；**先验无扫参**（常量冻结 + grep 清 + docstring 明载）**且模块关系如实**（新构 filter-then-rank ≠ 生产 5 因子 composite，未虚称复用）；**数据源口径诚实**（akshare qfq adj_close caveat + SEC EDGAR 94/100 missing-6 逐字复核 + PIT filed-date 门无前视 + **2017 floor 独立坐实为真数据边界非调参**，pre-2017 1018 不可能移动 vs 2017+ 19，UNH +2845% 坐实 "+2800%"）；**推论边界有界**（不建全 P1 ≠ 美股选股永久无效，明列 pre-conditions）；**2 对抗验证 un-refuted** 经 journal 复核属实 + 独立再现全 hold；**research-only 零回归** git 级坐实（trade/+workbench/ diff 空、快照 gitignored）+ **L1 全绿**（ruff + 18 单测 fresh）+ **CI Python/Backend/Deploy 三绿**（b285566 自动链式）+ **HEAD 产品码 ≡ prod**（无产品码变更）。三项软观察（O1 模块关系文档 gap、O2 成本非对称保守方向、O3 floor 略保守）均**非阻断**。

**含义（承接 F001）：B055 全 P1 攻击选股在当前证据基础上不推荐建**——集中选股相对同宇宙等权无样本外风险调整 edge；若未来追进须付费幸存者-free vendor + 重测 OOS Sharpe 须胜 EW。
