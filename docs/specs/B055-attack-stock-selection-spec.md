# B055 — 进攻型「单市场个股选股」新交易模式（Phase 1：美股引擎 + 独立回测验证）

> **批次类型：** 混合批次（3 generator + 1 codex，P1）
> **状态：** 草案（待 B054 done 后转 planning→building；本会话 2026-06-11 与用户讨论定案）
> **来源：** 2026-06-11 用户讨论确认新方向 + backlog B055。Phase 4 策略深化（进攻方向）。
> **非交易 gate：** 独立于 Master，排在 B054 中文化 + 用户开始真实交易之后。

---

## 1. 愿景（与 Master 的分工）

一个**独立的进攻型交易模式**，与 Master 并行：

| | Master Portfolio | B055 进攻模式 |
|---|---|---|
| 性质 | 稳健核心仓（综合 4 策略一个组合）| 进攻卫星（单策略个股选股）|
| 标的 | 多为 ETF | **个股** |
| 市场 | 全球 ETF/ADR | **单市场**（美股先行，扩充每市场一份不交叉）|
| 频率 | 季度 | **月度** |
| 目标 | 风控复利 | 追更高收益（接受更深回撤）|
| 资金 | 用户核心账户 | **独立一笔钱/独立账户**（自己的现金+持仓+推荐+回测，与 Master 分开）|

**用户确认决策（2026-06-11）：** 风格=**动量+质量**；市场=**美股先行**；频率=**月度**；集中=**top 15**；资金=**独立账户**；落地=**分期（先回测验证）**。

**诚实原则（贯穿，写进实现）：** 收益来自「个股 + 集中 + 进攻因子」非频率；高频追收益最易过拟合 → **必须 walk-forward 样本外验证**；research-only / no 收益预测边界不变。

---

## 2. Phase 规划（分期）

| Phase | 内容 | 本 spec |
|---|---|---|
| **P1（本批）** | 美股动量+质量选股引擎 + 股票池/数据扩充 + **独立回测**（用户在回测页验证疗效）| ✅ |
| P2（未来批）| 进攻模式**推荐 surface**（独立账户 account_snapshot + 月度推荐→diff→ticket→执行闭环）| ⏳ |
| P3（未来批）| **多市场扩展**（非美市场用纯价格动量，无财报源；每市场一份不交叉）| ⏳ |

**P1 的意义：** 让用户**先在回测页看到这个策略的历史表现 + 样本外验证**，确认值得再上 P2 实盘 surface——「先看疗效再吃药」。P1 **不含实盘推荐/执行**（research-only 验证）。

---

## 3. P1 Feature 分解

| id | executor | 标题 |
|---|---|---|
| F001 | generator | 美股选股 universe + 数据扩充（流动性大盘股池，prices+fundamentals，预算感知）|
| F002 | generator | 动量+质量选股引擎（trade/，质量过滤+动量排名→top 15 等权，月度）|
| F003 | generator | 独立回测接线（B050 分发 + adapter + report，回测页可跑，walk-forward）|
| F004 | codex | 回测验证 L1+L2——非退化 + 样本外合理性 + 无过拟合红旗 + signoff |

## 4. F001 — 美股选股 universe + 数据（generator）

1. **股票池定义**：流动性大盘美股集合（如 S&P 100/500 成分或按市值+成交额筛 top-N）；**预算感知**——Tiingo 价格 + SEC EDGAR 财报对 N 只股票的拉取量须在 tiingo_budget/月 cap 内、data-refresh 时长可接受。planning 决池大小（建议 P1 先 ~100-200 流动性最好的，可后续扩；不必一上来 500）。
2. **data-refresh 扩展**：把选股池 symbol 纳入 data-refresh universe（复用 B045 pipeline），拉真实 prices+fundamentals；§12.10/§12.10.3 自包含不破。
3. **池可配置**：universe 来源（静态清单 vs 动态筛）generator 定并文档化；池变更不污染 Master sleeve universe。
4. **测试**：universe 加载 + 数据拉取覆盖 + 预算守门。
5. Gates：backend pytest ≥ baseline+ / ruff / mypy 0 / Tiingo budget 不破。

## 5. F002 — 动量+质量选股引擎（generator，触 trade/）

1. **新策略**：`trade/strategies/us_momentum_quality/`（或就近）：**质量过滤**（复用 us_quality 因子：盈利能力/杠杆/质量打分，剔除低质/高杠杆）→ 在合格池里**动量排名**（如 6 月收益 skip 最近 1 月，generator 定窗口并注明）→ 取 **top 15** → **等权**（默认；动量/波动加权留 P2 可选）。
2. **月度 cadence**：信号日=月末（复用/新增 monthly signal dates 工具，区别于 Master quarter-end）。
3. **结果结构**：兼容 B050 回测 adapter（equity_curve/rebalance/fills/weights），便于 F003 接线。
4. **research-only**：纯研究信号，no 收益预测；引擎不接执行（P1）。
5. **mypy trade 自检**：改 trade/ 须本地 `mypy trade`（environment.md，B050 教训）。
6. **测试**：质量过滤+动量排名+top15 等权+月度信号+边角（池不足 15/数据缺）。
7. Gates：backend+trade pytest ≥ baseline+ / ruff / mypy(workbench+trade) 0。

## 6. F003 — 独立回测接线（generator）

1. **B050 分发注册**：新 strategy_id（如 `us-momentum-quality`）入 `_DISPATCH` + 结果 adapter + report builder（双语，沿用 B054 报告中文）。
2. **回测页可跑**：用户在 Backtest 页选该策略→月度回测→真实美股数据→非退化结果。
3. **walk-forward 强调**：报告/文档体现样本外验证理念（至少标注 in-sample 风险；若可行加 out-of-sample 段对比）——防过拟合。
4. **测试**：回测产非退化结果 + 异于 Master/其它策略 + 月度 cadence。
5. Gates：同 F002。

## 7. F004 — Codex 回测验证 + signoff（codex）

L1 全门禁。L2 真 VM：在 Backtest 页跑 `us-momentum-quality` over 真实美股池→**非退化结果**（equity 多点/有交易/metrics 真实）；**合理性核查**——选出的是合理的大盘股、月度换手合理、表现 plausible **非明显过拟合**（如夏普高得离谱要存疑）；若可行做 **in-sample vs out-of-sample 对比**（walk-forward 验证）；回归 B050-B054 不破。**§25 适用**：须正面真机回测证据。Signoff `docs/test-reports/B055-...-signoff.md`（§回测表现 + §样本外/过拟合评估 + §合理性）。**P1 结论=该策略是否值得进 P2 实盘 surface 的研究判定。**

## 8. 风险与缓解

| 风险 | 缓解 |
|---|---|
| 过拟合（高频追收益重灾区）| walk-forward 样本外；F004 合理性+过拟合红旗核查；夏普离谱存疑 |
| 数据预算（扩池拉 N 只）| F001 预算感知，P1 先中等池（~100-200）可后扩 |
| 个股暴雷/动量崩盘 | 质量过滤减轻；P1 仅回测不实盘，风险在 P2 上实盘前充分验证 |
| 触 trade/ 包 CI 严 | 本地 mypy trade 自检（B050 教训）|

## 9. Core Acceptance（P1 一句话）

美股「动量+质量月度 top15 选股」引擎建成、接入独立回测，用户能在回测页看到它的真实历史表现 + 样本外合理性，据此判定是否进 P2 实盘——**先验证再上实盘**。

---

## 10. 未来 Phase（不在本批，记录方向）

- **P2**：进攻模式推荐 surface——独立账户 account_snapshot（自己的现金+持仓，与 Master 分开）；月度推荐→position-diff→ticket→fills→reconcile→journal（复用执行闭环，按模式隔离）；新页或 Recommendations 加模式选择器。
- **P3**：多市场扩展——非美市场用纯价格动量（无财报源）；每市场独立 universe+推荐，不交叉选股；数据按市场参数化。
