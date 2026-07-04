# B082 — 红利低波防守腿（评审 P1 排序 1）Spec

**批次定位：** 新策略族（防守腿）落地（混合批次 3 generator + 1 codex）。评审报告 §3.4 个人可实施策略排序第 1；直接解决「cn_attack 红卡期无可配置策略」的空档。**低换手、稳健、advisory-only**——与项目原则同向。

**来源：** 2026-07-03 用户立项（backlog `B0XX-dividend-lowvol-defense`）← 评审报告 §3.4/§5；立项前调研 `docs/research/next-batch-prep-dividend-lowvol-defense.md`（并行会话 B081 等待期完成，5c5a1e2）。

**Planner 默认决策（/goal 授权，预研文档 4 个开放问题的裁定，可推翻）：**
1. **范围 = 纯 ETF 持有先行**：本批只做红利低波类 ETF（512890 等）持有 + 利差配置信号；成分轻度增强不做（工程大 + B081 教训的手数取整风险在成分层，留 follow-up 评估）。
2. **市场 = A 股优先**：不铺 US 对照（留后）。
3. **组合关系 = 独立研究态模式**：按 B057 框架注册新 strategy mode（`cn_dividend_lowvol`），自带 target/paper/surface，研究态不配资；不并 Master。
4. **数据地基 = 本批自带 spike**：A股 ETF 日线 + 股息率/国债收益率序列 via akshare（F001 含可得性探针，数据不可得 → 诚实 NO-GO 停批，不硬上）。

**证据与时点（评审已核验）：** 2022–24 三年调整市全收益 +42.6%；2024-02 踩踏期最大回撤仅 5.4%（同期 HS300 −11.2%）；自 2013-12 发布年化 ~12.9%。已知风险：2025 AI 牛中大幅跑输（全收益约 +6%）、被动资金 2022→24 增 20 倍拥挤；2025Q4 股息率回升 5%+ vs 十年国债 1.66%。**防守腿的核验重点是回撤控制（2022/2024-02 型窗口），不是绝对收益。**

---

## 0. 设计要点（焊死）

- **标的**：红利低波 ETF 候选池（512890 中证红利低波动 ETF 为主候选；F001 探针确认 akshare 覆盖后定 1-2 只）。ETF 层无个股幸存者偏差/退市问题；上市时间（512890≈2018 末）决定回测窗口上限——**窗口诚实标注**，可用标的指数（H30269 中证红利低波动指数）更长历史作 secondary 佐证（指数无成本，标注口径差异）。
- **信号**：① 基线 = 持有（buy-and-hold 防守腿）；② 配置信号 = **股息率−十年国债利差** monitor（利差宽→满配、窄→减配的阶梯规则，阈值在 spec 定死禁止扫参：参考评审建议「利差 <2% 降配」，档位 = 利差≥2.5% 满配 100% / 1.5-2.5% 半配 50% / <1.5% 低配 25%——三档规则先验设定，回测披露但**不以回测优化阈值**（防过拟合，评审 §2 纪律））。日频监控月度执行 + 不动区。
- **回测**：复用 `trade/backtest/` 骨架（T+1 open 执行 + 成本模型 + WF 70/30 + CPCV-lite）。**B081 修真开关全带上**（ETF 手数=100 份/手同样取整；停牌/涨跌停对 ETF 罕见但开关在）。本金口径 10 万 + 100 万双跑（B081 教训：容量下限须显式）。ETF 成本口径：无印花税（ETF 免），佣金 2.5bp + 滑点 5bp——**成本模型须区分 ETF 与个股**（现 costs.py 是 A 股个股口径，直接复用会多算 5bp 卖出印花税）。
- **红黄绿卡**：沿用 oos_verification_card（B080 基建），新 strategy_id 行；`validated=False` 起步；防守腿卡片口径 = 回撤控制指标（2022/2024-02 窗口 DD vs HS300）+ 全样本/OOS 双披露。
- **模式注册**：B057 框架 append `StrategyMode` 行（`cn_dividend_lowvol`，FUNDING_RESEARCH，月度 cadence）+ target producer + paper 账户 + B080 监控面板自动覆盖（monitoring_metric 按 strategy_id 泛化——确认 B080 实现是否 cn_attack 硬编码，若是则本批顺带参数化）。
- **数据地基**（F001 探针定 GO/NO-GO）：akshare ETF 日线（`fund_etf_hist_em` 等）、股息率（中证指数或 akshare 指数估值接口）、十年国债收益率（akshare bond 接口）。探针纪律照 B060/B077：真实 fetch 实测覆盖与深度，报告落盘，不可得 → NO-GO 停批诚实交代。

## 1. 复用清单

| 资产 | 位置 | 用法 |
|---|---|---|
| 数据接入模式 | B059 provider 抽象 + B065 data_refresh 管线 | F001 ETF/利率序列接入 |
| 回测骨架 | trade/backtest/cn_attack_momentum_quality（引擎修真开关 B081） | F002（成本口径改 ETF） |
| 模式框架 | workbench_api/strategy_modes/registry + precompute + refresh_worker | F003 注册新模式 |
| 红黄绿卡 | oos_verification_card（B080） | F002/F003 卡片 |
| 监控面板 | workbench_api/monitoring/（B080） | F003 新 strategy_id 接入 |
| paper 引擎 | workbench_api/paper/（B074/B080 修复后） | F003 paper 账户 |
| 探针纪律 | B077 F001 数据现实报告模式 | F001 |

## 2. Feature 拆解（4：3 generator + 1 codex）

### F001 (g) — A股 ETF 数据地基 spike + 接入（含 GO/NO-GO 探针）
1. 探针：akshare 实测 512890（+备选红利低波 ETF）日线深度/复权口径、红利低波指数（H30269）历史、股息率序列、十年国债收益率序列——真实 fetch，覆盖/深度/新鲜度落 `docs/test-reports/B082-F001-data-reality.md`（B077 模式）。**任一关键序列不可得或 <5y → NO-GO 停批**（利差信号需要利率历史）。
2. GO 则接入：ETF 日线 + 指数 + 利差序列进 data_refresh 管线（新 CSV/复用 unified，B065 模式；日刷 wiring + 超时纪律 v0.9.54）。
**Acceptance：** 探针报告落盘（真实数字）；GO 时序列落地生产数据根可查、日刷含新序列且超时守门；NO-GO 时诚实停批报告。Gates：backend pytest/ruff/mypy + 若触 trade/ 则 mypy trade + root pytest（B081 教训）。

### F002 (g) — 策略实现 + 回测 + 卡片
1. `trade/strategies/cn_dividend_lowvol/`：持有基线 + 三档利差配置规则（阈值 spec 定死）；月度执行 + 不动区。
2. 回测：ETF 成本口径（无印花税）+ B081 修真开关 + 10 万/100 万双本金 + WF 70/30 + CPCV-lite；**重点输出 2022 全年与 2024-02 窗口的 DD 对照（vs HS300 与 vs cn_attack）**；ETF 窗口（~2018 起）+ 指数 secondary（更长）双口径诚实标注。
3. 红黄绿卡写 oos_verification_card（validated=False；防守腿口径）+ trial_registry 登记全部配置试验。
**Acceptance：** 回测报告落盘（真实数字、双本金、双窗口口径、回撤对照表）；利差阈值未经扫参优化（spec 先验规则，代码 grep 无阈值搜索路径）；卡片+registry 落地。Gates 同 F001 + mypy trade + root pytest。

### F003 (g) — 模式注册 + advisory surface + paper + 监控接入
1. registry append `cn_dividend_lowvol`（FUNDING_RESEARCH/月度）+ target producer（日频监控月度目标 + 利差档位进 master_meta）+ refresh_worker 分发 + timer。
2. paper 账户（10 万 CNY、CSI300 基准——B080 F004 per-strategy 基准直接受益）+ 前端模式选择器自动出现（B057 框架）+ B080 监控面板覆盖新 strategy_id（若 B080 实现 cn_attack 硬编码则参数化）。
3. 快照带研究态 disclaimer + 红卡（读 DB 卡片，B080 机制）。
**Acceptance：** 生产新模式端到端（timer→target→推荐快照→paper 建仓→面板显示）；no-execution safety 守门不破；Master/cn_attack/regime 零回归。Gates 全套 + Playwright e2e。

### F004 (codex) — 独立验收 + signoff
- L1 全门禁 + 新单测抽查。L2 真机：探针报告数字抽验（独立重 fetch 1-2 个序列对照）；回测报告数字复核（抽 1 组重跑）；利差阈值先验性审计（无扫参路径）；生产模式端到端实测（快照/paper/面板/红卡）；回撤对照表与评审报告引用数字一致性；零回归（cn_attack/master paper 与 B080 监控不破）；HEAD≡prod。
- **验收重点提示（B081 教训）：对 F002 回测数字做研究员级审计**——防守腿最容易的美化是窗口挑选与阈值隐性优化。

## 3. 状态流转 + 不变量
- `planning → building(F001→F002→F003) → verifying(F004) → done`；F001 探针 NO-GO 则停批走 done（诚实结论也是交付）。
- **不变量**：① 利差阈值先验设定禁止回测扫参优化；② validated=False 起步、摘卡走人工；③ advisory-only/no-execution/research-only/no-broker；④ Master/cn_attack/regime/B080 监控零回归；⑤ B081 修真开关默认开（partial_rebalance 除外——默认 False 不变量）；⑥ 全门禁含 trade/-edit 三件套（B081 教训）。
- **诚实边界**：① ETF 窗口 ~2018 起偏短（含 2018 熊尾/2019-21 牛/2022-24 调整/2025 跑输——风格周期覆盖尚可但仅一轮）；② 指数 secondary 无成本口径差异标注；③ 2025 跑输与拥挤度风险写进卡片 detail；④ 回撤控制是设计目标而非承诺。
- **后续（不在本批）**：成分轻度增强（需 B081 手数教训评估）；US 红利低波对照；与 ETF 趋势批次共享数据地基。
