# B043 — AI 解释层（Recommendations / Backtest / Risk 的「为什么」富解释）

> **批次类型：** 混合批次（4 generator + 1 codex）
> **状态：** planning → building
> **里程碑：** 里程碑 C 后唯一明确剩批——给已干净全真实的系统加 LLM「为什么这样建议」解释。
> **前置：** 里程碑 C 达成（B049）+ B050 修复 + B031 LLM gateway + B036 advisor + B032 ai-safety-eval 全 done。
> **来源：** 路线图 B043 + 用户 2026-06-09/10 拍板（3 surfaces + 简洁 per-position rationale）+ Explore 接入面核查。

---

## 1. 背景与目标

里程碑 C 已让所有页面接真实引擎、无占位。`recommendations/precompute.py:280` 的 rationale 现是**确定性占位**（注释明确「rich "why" is B043」）。B043 = 给 **Recommendations / Backtest / Risk** 三个页面加 LLM 生成的**简洁「为什么」解释**，**grounded 在真实计算值上**（sleeve 权重/因子/信号/回测数字/风险 DD），受 no-AI 硬边界约束。

**用户拍板（2026-06-09/10）：** 三页面全覆盖 + 简洁 per-position rationale（非长篇 narrative）。

---

## 2. 永久硬边界（no-AI，复用 B036/B032）

解释层是「grounded explanation layer」，**复用 advisor/service.py 的 5 规则系统 prompt + 护栏链**：
- (a) 不指示/暗示自动 buy/sell/下单执行；
- (b) **不输出收益预测数字**（X% / $ 目标 / 未来 Sharpe）；
- (c) 不以 AI 替代 quant signal 作为买卖唯一依据；
- (d) **每条引用必须来自提供的输入集**（grounded，可引用真实值）；
- (e) 允许 explain / summarize / translate / aggregate。
- 违规 / grounding 不足 / 解析失败 / 越界引用 → 输出 `INSUFFICIENT_GROUNDING_SIGNAL` → 降级。

**护栏复用清单**：`llm/gateway.py advise()` + `llm/routing.py ROUTING_TABLE`（task→model）+ `llm/cost_guard.py`（月度 cap $200）+ `llm/judge.py INSUFFICIENT_GROUNDING_SIGNAL` + `advisor/schema.py references_valid/_strip_code_fence`。

---

## 3. 架构（确定性默认，planner 定）

| 原则 | 决定 |
|---|---|
| **生成位置（off 请求路径，§12.10.2）** | A：recommendations precompute 时同步生成；B：backtest worker 生成结果时同步生成；C：**新建 risk 解释 precompute job**（risk_panel 是请求路径只读，禁塞 LLM）|
| **存储** | A：`recommendation_snapshot.rationale`（现有列）；B：`backtest_run` 新列 `explanation`（或复用 report）；C：**新表 `risk_explanation_snapshot`** |
| **请求路径** | 只读已生成的解释；解释缺失→graceful（显确定性占位/空态，不阻塞）|
| **降级** | LLM 不可用 / budget 超 / 拒答 / 解析失败 → 回退确定性占位文案（诚实，不伪造）|
| **model / 温度** | 默认 Haiku 4.5（对齐 B036 daily_advisor，最廉价层够用）+ temperature 0.2（稳定可复现）；generator 可调 |
| **grounding 引用** | 复用 references_valid **模式**，按各注入点适配 citation schema（rationale 引 sleeve/weight/signal_date/data_source；backtest 引 metrics/trades 真实数字；risk 引 master_dd/per_sleeve_dd/阈值）|

---

## 4. Feature 分解

| id | executor | 标题 |
|---|---|---|
| F001 | generator | 共享解释基建 + Recommendations rationale（注入 A，核心）+ 降级 + 测试 |
| F002 | generator | Backtest 结果解释（注入 B，worker 生成时）+ 测试 |
| F003 | generator | Risk 解释（注入 C，新表 + 新 precompute job + risk_panel 读 snapshot）+ 测试 |
| F004 | generator | 前端——3 页面 surface 解释 + 空态/降级态 + i18n + 测试 |
| F005 | codex | L1+L2 真 VM——3 页面 grounded 解释 + ★no-AI 边界 adversarial 验证 + 降级 + signoff |

---

## 5. F001 — 共享解释基建 + Recommendations rationale（generator）

1. **共享解释生成器**：新建 `services/explanation/`（或就近）——复用 `gateway.advise(ChatRequest(task=…))` + 护栏链（sentinel 拒答 + references_valid 适配 + cost_guard）；3 个新 routing task 加 `routing.py ROUTING_TABLE`（`recommendation_rationale`/`backtest_explanation`/`risk_explanation` → haiku-4.5）+ PRICE_TABLE 对应。
2. **Recommendation rationale prompt**：复用 advisor 5 规则系统 prompt，user content = grounding（per-symbol：sleeve / target_weight / planning_weight / sleeve_status / data_source / signal_date，来自 `MasterTargetResult.master_meta`，precompute.py:67-76/182-191 手上即有）。输出简洁 per-position「为什么这个权重」（1-2 句，grounded 引 sleeve 组成 + 信号日）。
3. **注入 precompute**：`recommendations/precompute.py:280` 占位 rationale 改为调解释生成器；**幂等**（同 as_of_date 已生成则跳过，对齐 advisor precompute）；**降级**：拒答/budget/异常 → 回退现确定性占位文案（不阻断 precompute 写库）。
4. **§12.10.2**：解释生成在 precompute（已 import trade allowlist），请求路径 `services/recommendations.py` 只读 rationale 不变。
5. **测试**：grounding 组装 + 解释生成（mock gateway）+ references_valid 适配（引用越界→拒答）+ 降级回退占位 + 幂等 + routing task 注册。
6. **Gates**：backend pytest ≥ baseline+ / ruff 0 / mypy 0（本机 + `mypy trade` 若动 trade/，见 environment.md）/ §12.10.2 守门 / cost_guard 不被绕过。

---

## 6. F002 — Backtest 结果解释（generator）

1. **Backtest explanation prompt**：grounding = 真实 metrics（cagr/sharpe/max_dd/turnover）+ trades 数 + equity 点数 + 策略名 + 日期范围（worker 生成结果时手上即有，worker.py:240-278）。输出简洁「为什么这个 Sharpe/回撤是这样」（explain 真实历史输出，**不预测未来**、不给调参建议）。
2. **注入 worker**：`backtests/worker.py` 各 runner 返回 / `process_next` save_result 前同步生成 explanation；存 `backtest_run.explanation` 新列（migration）或并入 report_markdown（generator 定，建议独立列便于前端分区）。**降级**：拒答/budget/异常 → explanation=None（前端显报告不显解释，不阻断回测结果落库）。
3. **§12.10.2**：worker 已 off 请求路径 + import trade allowlist；请求路径 `services/backtests.py` 只读不变。
4. **测试**：explanation 生成（mock gateway，grounded 真实 metrics）+ no-预测边界（断言不含未来收益语）+ 降级 None + migration。
5. **Gates**：同 F001 + alembic head（若加列）。

---

## 7. F003 — Risk 解释（generator，架构关键）

1. **新表 + migration**：`risk_explanation_snapshot`（as_of_date / master_dd / state / explanation / created_at）。
2. **新 precompute job**：`services/risk_explanation.py` —— grounding = master_dd / per_sleeve_dd / kill_switch 阈值 / state / slippage / valuation_basis / degraded_symbols（risk_panel.py:117-150 算法复用，**只读**计算后喂 LLM）；输出简洁「当前风险现状 + 为什么（哪些头寸贡献 DD）」（explain 当前态，**不预测恢复、不给卖出建议**）。daily job（可单独 timer 或并入现有）。降级同上。
3. **risk_panel 读 snapshot**：`services/risk_panel.py get_risk_panel` 加读 `risk_explanation_snapshot` 最新解释（**请求路径只读，不调 LLM**）；无解释→graceful（不显解释面板/确定性占位）。response schema 加 explanation 字段。
4. **§12.10.2**：LLM 调用在新 precompute job（off 请求路径）；risk_panel 请求路径仍只读。
5. **测试**：risk grounding + 解释生成 + risk_panel 读 snapshot + 无解释 graceful + 降级 + migration。
6. **Gates**：同 F001 + alembic head + api.ts drift（risk schema 加字段则同步）。

---

## 8. F004 — 前端 3 页面 surface 解释（generator）

1. **Recommendations**：per-position 显示 rationale（rich「为什么」，复用 B041 Robinhood UI 的 rationale 槽）；空/降级态显确定性占位或留白，不破。
2. **Backtest**：结果区显 explanation（与报告分区）；无 explanation 时只显报告。
3. **Risk**：风险面板显 explanation；无则不显解释块。
4. **i18n**：解释文本本身由 LLM 按 locale 生成 or 后端存双语？——**本批 prompt 按当前 locale 生成解释**（generator 定：grounding 时传 locale 让 LLM 出对应语言，或先英文后端不译）；UI 框架文案（「为什么」「AI 解释」标签）双语 parity。
5. **测试**：vitest（3 页面渲染解释 / 空态 / 降级态）+ i18n parity + api.ts drift 0。
6. **Gates**：frontend vitest ≥ baseline+ / lint 0 / tsc 0 / api.ts drift 0 / no-execution 守门。

---

## 9. F005 — Codex L1+L2 真 VM + 安全验证（codex）

**L1**：F001-F004 全门禁 + §12.10.2 守门（解释生成不在请求路径）+ cost_guard 不被绕过 + i18n parity + api.ts drift 0 + alembic head + artifact secret=0。

**L2（真 VM）**：
1. **3 页面 grounded 解释**：Recommendations per-position rationale / Backtest explanation / Risk explanation 真机显示**真实 LLM 解释**，**引用真实值**（sleeve/weight/signal_date / 真实 metrics / 真实 DD），非占位串。
2. ★**no-AI 边界 adversarial 验证**（evaluator.md §25 + 复用 B032 judge）：抽样生成的解释，核**无收益预测数字 / 无自动执行指示 / 无替代 quant / 引用都在输入集内**；可用 `llm/judge.py` safety_judge 跑样本，或人工核 N 条。**任一条违边界 → blocker**。
3. **降级**：模拟 LLM 不可用 / budget 超 → 3 页面 graceful 回退确定性占位/空态，不报错、不漏原始异常。
4. **回归**：B050 回测分发不破 / 推荐 diff 不破 / recent-errors=0 / HEAD≡main / B023 闭环不破。
5. **Signoff**：`docs/test-reports/B043-ai-explanation-layer-signoff-2026-MM-DD.md` 用模板（§Production/HEAD + §Post-signoff Deploy + **§3 页面 grounded 解释样例 + §no-AI 边界 adversarial 结果**）。更新 progress.json status→done。

---

## 10. 风险与缓解

| 风险 | 缓解 |
|---|---|
| LLM 输出越 no-AI 边界（收益预测等）| 复用 B036 5 规则 prompt + sentinel + references_valid；F005 adversarial judge 抽验；违规即 blocker |
| 解释「幻觉」引用不存在的值 | references_valid 适配各注入点 citation schema；引用越界→拒答→降级 |
| risk_panel 请求路径误塞 LLM（§12.10.2 破）| F003 强制 risk 解释走新 precompute job + 新表，risk_panel 只读 snapshot |
| 成本失控 | cost_guard 月 cap $200 不被绕过；Haiku 最廉价；幂等避免重复生成；F005 核 cost_guard 生效 |
| LLM 不可用阻断核心功能 | 降级=回退确定性占位，解释是增强非依赖；precompute/worker 不因解释失败而不写核心结果 |

---

## 11. Core Acceptance（一句话）

Recommendations / Backtest / Risk 三页面显示 LLM 生成的**简洁、grounded 在真实计算值上**的「为什么」解释，**严守 no-AI 硬边界**（无收益预测/无替代 quant/可引用），LLM 不可用时优雅降级回确定性占位——给已全真实的系统加可信的解释层。
