# B040 — Reports Robinhood-style 重构（Phase 3 / Stream 5.A）

> **状态：** planning（2026-06-06 起草）。
> **批次类型：** 新功能（Phase 3 S5.A，**真实新批次**，非 B037 复用 gap）。
> **配套权威设计：** `docs/product/positioning-2026-05.md` §1.1 + §UI 改造表（line 68）/ `docs/product/user-personas-and-journeys-2026-05.md` §7 UI 优先级。design-draft/ 空 → 以 positioning + personas 为权威。

---

## 1. 目标

把回测指标从 quant-jargon 表格重构为 **Robinhood-style 呈现：大数字 + 颜色编码 + 双语 tooltip**。专业术语（Sharpe / Sortino / Calmar / MDD / CAGR）**保留英文**，用**中文 tooltip 解释**。两个目标面（2026-06-06 用户已批「两个面都做」）：

1. **`/backtest` 回测页**：已有结构化 `BacktestMetrics`，做 Robinhood 化（前端为主，无脆弱解析）。
2. **`/reports/[slug]` Markdown 报告详情页**：后端从 Markdown 指标表解析结构化指标（graceful null）+ 前端大数字卡片，**不破 body_markdown**。

**定位边界（positioning §1.1）**：大数字展示的是**历史回测结果**（Sharpe/CAGR 是过去回测的统计），**不是预期收益预测**——不输出「预期年化 X%」。tooltip 是**术语教育性解释**（确定性手写），**非 AI 生成**（AI tooltip 文案是 B043，与本批联动但不在范围）。

---

## 2. 决策（2026-06-06 用户已批，★=拍板）

| 决策点 | 选择 | 说明 |
|---|---|---|
| 目标面 | ★ **两个面都做**（/backtest + /reports detail） | 覆盖最全 |
| tooltip 文案 | **确定性手写双语**（planner 决） | AI 文案是 B043；本批 Sharpe/Sortino/Calmar/MDD 中文解释手写固定 |
| Calmar 来源 | **派生 = CAGR / |MDD|**（planner 决） | 现 `BacktestMetrics` 无 Calmar 字段，由现有字段计算 |
| Markdown 保全 | **body_markdown 字节不变**（planner 决） | 大数字卡片是独立 section，MarkdownRenderer 不动；守门做 byte-identical 完整性断言 |
| reports 指标解析 | **后端 Option A：header-signature 匹配 + 同义词映射 + graceful null**（planner 决） | 多数异构报告无指标表→null→前端退回纯 Markdown；须对真实语料(B016/B030)验证 |
| per-sleeve vs Master | **现有 detail 页渲染任意报告（sleeve 或 Master），不新增路由**（planner 决） | 「单 sleeve / Master」指哪些报告受益，非要求新路由 |

---

## 3. 永久硬边界（继承）

- **no-execution UI**：Reports/backtest 页只读（无下单/执行按钮 + 中文禁词同级守门）。
- **定位 §1.1**：不输出预期收益数字；大数字=历史回测统计；tooltip=确定性术语解释非 AI 生成（不触 B036 生成式 / B032 red-team / ai-safety §2）。
- **i18n**：术语英文 + 中文 tooltip；en + zh-CN 双语齐 + 无禁词；手动 parity（不机翻 jargon）。
- **fixture vs real-data signal（v0.9.21）**：不新增基于 fixture 范围的脆弱指标断言；测试用固定 mock 指标验证渲染/颜色逻辑，不断言策略性能结论。

---

## 4. 技术架构

### 4.1 后端 — reports 指标结构化（仅 /reports 面需要）

- `schemas/reports.py` `ReportDetail` 加可选 `metrics: ReportMetrics | None`；新 `ReportMetrics`（sharpe/sortino/calmar/cagr/max_drawdown/volatility/turnover，全可选 float|None）。
- `services/reports.py` `get_report()` 扩：扫已解析的 `tables`，**header-signature 匹配**识别指标表（含 sharpe + max_drawdown 等关键列），**同义词映射**（annualized_return→cagr / annualized_volatility→volatility / mdd→max_drawdown），**计算 Calmar=cagr/|max_drawdown|**；无可识别表→`metrics=None`。
- **body_markdown 不变**（仅新增 metrics 字段，不改原文）；regen api.ts。
- pytest：对真实语料样本（B016 风格指标表）解析正确 + 同义词映射 + Calmar 派生 + 无表→null + body_markdown 完整性（解析不改原文）。

### 4.2 前端 — 共享 Robinhood 原语（两面共用）

- 抽取泛化 `components/metrics/MetricsDisplay.tsx`（源 `/backtest` 的 MetricsCard/Stat）：大数字网格 + label + 值。
- **颜色编码工具** `lib/metric-color.ts` `colorForMetric(name, value)`：
  - Sharpe/Sortino/Calmar：≥1.0 绿 / 0–1 琥珀 / <0 红
  - CAGR：>0 绿 / <0 红
  - Max Drawdown：>-0.05 绿 / -0.2~-0.05 琥珀 / <-0.2 红
  - Volatility/Turnover：中性（无色）
  - （阈值为初版默认，building 期可微调）
- **双语 tooltip**：每个指标 label 包 `Tooltip`（radix 现成）；i18n `metrics.tooltips.{sharpe,sortino,calmar,maxDrawdown,cagr,volatility,turnover}`——英文术语名 + 中文解释（手写，如 Sharpe=「风险调整后回报：每单位波动换来的超额收益，越高越好」）。

### 4.3 前端 — 两面接入

- **`/backtest` 页**：用 `MetricsDisplay`（颜色 + tooltip）替换/升级现有 MetricsCard（结构化 BacktestMetrics 现成，含派生 Calmar）。
- **`/reports/[slug]` 页**：`metrics` 非空时在 MarkdownRenderer **上方**渲染 `MetricsDisplay` 卡片；null 时跳过（graceful 纯 Markdown）；**MarkdownRenderer 不动 + body_markdown 不变**。

### 4.4 测试

- 前端 vitest：MetricsDisplay 渲染 + colorForMetric 边界（Sharpe -1/0/2.5、CAGR 正负、MDD 三档）+ tooltip i18n 双语 + /reports metrics 有/无两态 + body_markdown 完整性。
- Playwright：/backtest 跑后大数字+颜色可见；/reports 某含指标报告大数字卡片可见 + tooltip hover 出中文 + Markdown 仍在下方；双 locale。
- no-execution 守门覆盖新组件。

---

## 5. Feature 拆分

| ID | executor | 标题 |
|---|---|---|
| F001 | generator | 后端：`ReportDetail.metrics` 结构化解析（header-signature + 同义词 + Calmar 派生 + graceful null + body_markdown 不变）+ pytest |
| F002 | generator | 前端共享原语：`MetricsDisplay` 大数字卡 + `colorForMetric` 颜色工具 + 双语指标 tooltip（i18n）+ 接入 `/backtest` 页 + vitest |
| F003 | generator | 前端 `/reports/[slug]` 接入 MetricsDisplay（metrics 非空渲染 / null graceful）+ body_markdown 完整性守门 + vitest + Playwright（两面）|
| F004 | codex | L1 + L2 真 VM 验收（/backtest + /reports 大数字/颜色/双语 tooltip 浏览器手验 + Markdown 保全 + no-execution）+ signoff |

---

## 6. 不做的事（YAGNI）

- 不做 AI 生成 tooltip 文案（B043；本批确定性手写）。
- 不输出预期收益/预测数字（定位 §1.1 硬边界）。
- 不新增 per-sleeve 报告路由（现有 flat 列表 + detail 渲染任意报告）。
- 不改 body_markdown / MarkdownRenderer 渲染管线（仅上方加卡片）。
- 不触 Home 三段 / Recommendations(B041) / Risk(B042) 页。
- 不引入基于 fixture 范围的脆弱性能断言（v0.9.21）。

---

## 7. 验收门槛汇总

- **F001**：`ReportDetail.metrics` 解析（真实语料样本正确 + 同义词 + Calmar 派生 + 无表 null + body_markdown 完整性）；backend pytest ≥ baseline+≥8 / ruff 0 / mypy 0 / regen api.ts；不破既有 reports list/detail/table 提取契约。
- **F002**：`MetricsDisplay` + `colorForMetric`（边界单测）+ 双语 tooltip（i18n parity）接入 `/backtest`；frontend vitest ≥ baseline+ / lint 0 / typecheck / no-execution 守门覆盖；不破既有 backtest 页其他功能。
- **F003**：`/reports/[slug]` metrics 有/无两态渲染 + body_markdown byte-identical 完整性守门 + MarkdownRenderer 不变；vitest + Playwright（两面大数字/tooltip/Markdown 保全，双 locale）；不破既有 reports 渲染。
- **F004**：L1 全门禁 + secret grep 0；L2（真 VM）：health 200 + SHA≡main HEAD；recent-errors=0；**/backtest + /reports 浏览器手验**：大数字 + 颜色编码 + 英文术语 + 中文 tooltip（hover/tap）+ Markdown 报告仍完整 + 无下单按钮 + 双语切换；截图（两面 ≥2 PNG）；HEAD≡main；B026 absent。**本批纯前端 UI + 后端解析无新对外路由**（/reports/[slug] 既有路由，§23 标 N/A 或验既有路由 metrics 字段 200）；无新 timer（§24 N/A）。Signoff 用模板（§Production/HEAD + §Post-signoff Deploy）+ docs/screenshots/B040-reports-robinhood/ ≥2 PNG。

---

## 8. 参考文档

- 权威定位：`docs/product/positioning-2026-05.md` §1.1 + line 68（Reports UI 改造表）
- UI 优先级：`docs/product/user-personas-and-journeys-2026-05.md` §7
- 回测指标 schema：`workbench/backend/workbench_api/schemas/backtests.py`（BacktestMetrics）+ `docs/engineering/backtest-report-schema.md`
- Reports 现状：`routes/reports.py` / `schemas/reports.py` / `services/reports.py`（含 _extract_tables）/ `(protected)/reports/[slug]/page.tsx` / `MarkdownRenderer.tsx`
- 复用原语：`components/ui/tooltip.tsx`（radix）/ `(protected)/backtest/page.tsx` MetricsCard（line 59-89 模板）
- fixture vs real-data signal：v0.9.21 `docs/engineering/testing-and-fixture-policy.md`

---

## 9. 风险与缓解

| 风险 | 缓解 |
|---|---|
| reports Markdown 指标表异构→解析脆弱 | header-signature 匹配 + 同义词映射 + **graceful null**（无识别表退回纯 Markdown）；F001 对真实语料 B016/B030 验证 + 解析失败不抛错 |
| 大数字被误读为收益预测 | 定位 §1.1 硬边界：标注历史回测结果 + 不出「预期年化」；tooltip 强调「历史统计非预测」 |
| 破坏 body_markdown | 仅新增 metrics 字段；MarkdownRenderer 不动；body_markdown byte-identical 完整性守门 |
| 颜色阈值主观 | 初版默认阈值写 spec §4.2，building 期可与用户微调；颜色仅辅助非决策 |
| 双语 tooltip 机翻 jargon | 手写 zh/en parity；i18n 守门双存 |

---

## 10. 与既有批次的边界 + 后续

- **不改**：reports list/table 提取 / backtest 运行逻辑 / Home / Recommendations / Risk。
- **B043 联动**：本批 tooltip 是确定性手写；B043 加 LLM tooltip 文案「为什么这个数字重要」段（同期协调，不在 B040 范围）。
- 后续：B041 Recommendations UI / B042 Risk Panel / B043 AI 解释层 → 里程碑 C。
