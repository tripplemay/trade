# B083 PEAD / 业绩预告事件 first-look — 独立验收 SIGNOFF（Evaluator，代 Codex）

**日期：** 2026-07-05（UTC）
**验收者：** 独立 Evaluator（无实现上下文，最高怀疑度；授权=用户 /goal + B079–B082 先例；与实现完全隔离）
**HEAD = 生产 release = `8b01d79`**（其后 `531bb2a`/`de5d2f3` 均 docs/chore，paths-ignore 不部署 → 部署代码 ≡ HEAD 代码，含 migration 0038）
**裁定：PASS → done**（3 features 全 PASS；INCONCLUSIVE 是合法结论，本次审的是**证据质量**而非结论方向）
**轮次：** verifying r1（本报告，round1 一轮闭环，无 fixing）

---

## 0. 裁定摘要

| 验收维度 | 结果 | 关键证据 |
|---|---|---|
| **前视/时点严谨（命门，最重）** | **PASS** | 独立复算 lookahead_violations=**0**；手工抽 3 事件全部 entry 严格 > 公告日；**用公告日非报告期末**进场 |
| **IC 数字从零重实现抽验** | **PASS** | numpy 独立 Spearman + 独立数据加载 + 独立 entry → 4 horizon × all/exec **全部 4 位小数精确吻合** |
| **盈余惊喜先验无扫参** | **PASS** | 单一先验公式 `(forecast−prior)/\|prior\|`；grep 无 grid/sweep/tune/argmax |
| **宇宙覆盖诚实披露** | **PASS** | 独立复算 **23.0% / 1152 标的**，与报告「~1152 名 23%」逐位吻合；涨跌停分层落实 |
| **INCONCLUSIVE 裁定一致性** | **PASS** | 数字确不达 GO 门槛（B077 纪律 IC≥0.03+单调）；证据质量高、caveat 诚实 |
| **migration 0038 生产落地** | **PASS** | deploy 链证明（migrate-before-flip + `set -euo pipefail` + Deploy success）|
| **L1 门禁 + CI 绿 + HEAD≡prod** | **PASS** | backend/root mypy+ruff 全绿；trial/migration 67 测 + b083 9 测过；main CI 三绿 |
| **零回归** | **PASS** | cn_attack / strategy_modes / dividend_lowvol 产品码改动 **0 行** |

---

## 1. 前视/时点严谨审计（命门，最重）

### 1.1 独立复算的 look-ahead 断言
独立脚本 `scripts/research/b083_evaluator_independent_ic.py`（不 import generator 脚本）对全部 8,235 定价事件独立计算 entry：
`entry = np.searchsorted(交易日, 公告日, side="right")`（第一个 strictly > 公告日的交易日）。
**`lookahead_violations = 0`（entry ≤ announce 的事件数 = 0）**。

### 1.2 手工抽 3 事件核对（announce vs entry vs 报告期末）

| 标的 | 报告期(期末) | 公告日(真发布日) | entry(进场) | entry>公告? | 备注 |
|---|---|---|---|---|---|
| 歌尔股份(002241) | 20190331 (03-31) | **2019-01-19** | 2019-01-21 | ✅ | 预告在期末**前**发布；进场用公告 T+1（01-19 周六→01-21 周一），**非期末** |
| 广汇能源(600256) | 20211231 (12-31) | **2022-01-05** | 2022-01-06 | ✅ | 公告 T+1 |
| 世纪华通(002602) | 20241231 (12-31) | **2025-04-12** | 2025-04-14 | ✅ | 04-12 周六→04-14 周一 T+1 |

**核心结论：** 事件日 = **公告日期（公告发布日）**，进场 = 公告日之后第一个交易日 open。报告期末（`report_period`）仅用于 PIT 去重分组，**从不用于进场**。歌尔案例证明即便预告在报告期末前数月发布，进场仍锁定发布日 T+1 → **无「财报期末前视」，无 look-ahead**。代码 `forward_returns` 中 `after = dates[dates > ad]`（strictly after）与单测 `test_forward_returns_entry_strictly_after_announcement` 已焊死此不变量。

### 1.3 PIT 时点核查（公告日是真发布日、非期末堆叠）
抽 3 报告期，公告日呈真实散布（如 2020Q3：2020-07-16..2020-12-29；2023Q3：2023-07-27..2024-01-22），非聚集在期末单日 → 确为 PIT 发布日。

---

## 2. IC 数字从零重实现抽验（独立复算）

独立脚本三处**不同代码路径**：(a) 直接读 `prices_daily.csv`（非 `trade.data.load_prices`）；(b) entry 用 `np.searchsorted right`（非 `dates[dates>ad]` 布尔索引）；(c) Spearman 用 numpy average-rank + `np.corrcoef`（非 generator 的 pandas `.rank().corr()` Pearson-of-ranks）。

| horizon | IC(all) 报告 | IC(all) 独立 | IC(exec) 报告 | IC(exec) 独立 |
|---|---|---|---|---|
| N1 | +0.0242 | **+0.0242** | +0.0211 | **+0.0211** |
| N5 | −0.0195 | **−0.0195** | −0.0209 | **−0.0209** |
| N10 | −0.0770 | **−0.0770** | −0.0758 | **−0.0758** |
| N20 | −0.0568 | **−0.0568** | −0.0570 | **−0.0570** |

`events_priced=8235`、`entry_limit_locked_frac=0.008` 亦逐位吻合。**三条独立路径收敛到同一数字（4 位小数）→ IC 计算正确、可复现。**

---

## 3. 盈余惊喜先验性（无扫参）

盈余惊喜定义 = 单一先验公式 `(forecast_value − prior_year_value) / |prior_year_value|`（`compute_surprise`，去 `|prior|==0` 与 inf/nan）。
grep `scripts/research/b083_pead_*.py` + `trial_backfill_b083.py`：**无 grid/sweep/optuna/optimal/best_param/tune/argmax/for-over-params 痕迹**。预告类型（预增/略增/…）仅作叙述分档，未参与 IC 数值优化。**先验定死、禁扫参 = 落实。**

---

## 4. 宇宙覆盖诚实性 + 涨跌停分层

- 独立复算覆盖率：38,595 事件 / 5,246 标的；事件∩B070 面板 = **8,878 事件 / 1,152 标的**；**事件级覆盖 = 23.0%**。与报告 caveat「B070=cn_attack 动量大盘宇宙(~1152 名, 事件覆盖仅 23%)」**逐位吻合**。此为诚实披露的**已知偏差**（PEAD/欠反应最强在小盘，大盘宇宙系统性低估 edge）——非过度归因、非掩盖（避免 B077 80.8% 未覆盖同款风险）。
- 涨跌停分层落实：entry 日 open vs 前收 ±band（300/688=20% else 10%）标记一字触板；locked_frac=0.008（预告是软信号，一字板占比仅 0.8%）；剔触板的「可执行 IC」独立复算亦吻合 → 纸面 vs 可执行 alpha 差已诚实揭示（本批可执行 ≈ 纸面）。

---

## 5. INCONCLUSIVE 裁定一致性（审证据质量非方向）

GO 门槛（spec §2 F002）= |IC| > ~0.03 **且** 跨 horizon 同号 **且** 分档单调。
实测（可执行）：N1 +0.021 / N5 −0.021 / N10 −0.076 / N20 −0.057。
- N1 |IC|=0.021 **< 0.03**（不达阈值）；
- 符号 +/−/−/− **不同号**（弱 pop 后反转，非 PEAD 正向持续漂移）；
- 跨 horizon **不单调**。
三条 GO 条件**均不满足** → **INCONCLUSIVE 是与数字一致的正确裁定**。非「数字达 GO 门槛却标 INCONCLUSIVE」，亦非反之。N10/N20 负 IC（|·|>0.03）为反转特征，报告未据此翻转为「做空 PEAD」GO（naive/偏差宇宙下不成立）——纪律得当。trial_registry 登记本 config（verdict=INCONCLUSIVE）计入 DSR N，诚实计已试配置。

---

## 6. migration 0038 生产落地 + 门禁 + 零回归

- **迁移链**：单一 head `0038_b083_pead_first_look_trial`（down_revision=0037，线性无分叉）。alembic heads 干净。
- **生产落地（VM 只读）**：部署 release symlink → `8b01d79`，其树中 `0038_*.py` + `trial_backfill_b083.py` 存在。deploy.sh 于 symlink flip **前**跑 `alembic upgrade head`（`set -euo pipefail`）→ Deploy success 证明 0038 已应用（失败会中止部署、symlink 不翻）。alembic current 直查因 DB 属 deploy 用户、只读账户无权打开而未能读取（权限限制，非迁移失败）。
- **bootstrap 幂等 + DSR N**：`_import_trials` 已接 `B083_TRIALS`；`test_bootstrap_cli._N_TRIALS` 已 `+ len(B083_TRIALS)`（B081「_N_TRIALS 需同步」教训落实）；trial id 为确定性 content-hash（重跑幂等）。
- **门禁**：backend mypy（313 files clean）+ ruff（passed）；root mypy trade（101 files clean）+ ruff（passed）；trial/migration 67 测过 + b083 fetch/ic/bootstrap 9 测过。main CI：Backend/Frontend/Python CI + Deploy 均 success。
- **零回归**：`git diff 55aeac0~1..HEAD` 对 cn_attack_momentum_quality / strategy_modes / dividend_lowvol 改动 **0 行**。pyproject +1 = 为 `trial_backfill_b083.py` 加 E501 忽略（与 B081/B082 同规，metric 字符串逐字转录防改数）；risk-banner.spec = 独立 CI flake 修复（test-only，非 B083 范围）。

---

## 7. 诚实边界 / 遗留

- **first-look 结论 = 证据一测，非可配资策略**（无 paper/红卡/生产模式，符合 spec §0#1）。
- **INCONCLUSIVE ≠「PEAD 在 A 股无效」**：三条 caveat（大盘宇宙偏差 / 预告≠实际财报快报 / SUE 用去年同期非分析师一致预期）各指向 edge 被系统性低估的机制；报告已诚实标注 backlog follow-up（全 A 宽宇宙 + 实际快报惊喜 + 分析师一致预期 SUE 重跑）。
- **F001 spec 偏差（已在 generator handoff 披露）**：spec F001 写 data_refresh 日刷接入，实交一次性 bulk 研究 fetch（`scripts/research/b083_pead_fetch.py`，gitignored 可复现）。first-look 用 bulk 历史快照即可，daily wiring 推迟到策略批（若 GO）——合理，non-blocking。

---

## 8. 结论

**B083 PEAD/业绩预告 first-look 3 features 全 PASS → done。** 命门（公告日 PIT、无财报期末前视）经独立复算（lookahead=0）+ 手工 3 事件核对通过；IC 三条独立路径 4 位小数精确吻合；惊喜口径单一先验无扫参；23.0% 覆盖率诚实披露且涨跌停分层落实；INCONCLUSIVE 是与数字一致、证据质量高的合法裁定；migration 0038 生产落地（deploy 链证明）+ 门禁全绿 + HEAD≡prod + 零回归。

复现物：`scripts/research/b083_evaluator_independent_ic.py`（独立 IC + look-ahead 断言）、`scripts/research/b083_evaluator_lookahead_coverage_audit.py`（手工前视 3 事件 + 覆盖率 + PIT）、本 signoff。
