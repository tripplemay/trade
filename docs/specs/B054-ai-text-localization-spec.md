# B054 — AI/动态文字完整中文化（界面所有英文 → 中文，交易前 gate）

> **批次类型：** 混合批次（4 generator + 1 codex）
> **状态：** planning → building
> **trading_gate：** 用户硬约束——**B054 生产部署完成前不开始真实交易**。
> **来源：** 用户 2026-06-10 报「界面大量 AI 文字仍英文，影响准确读懂交易建议」+ 全面审计 `docs/product/ai-text-localization-audit-2026-06.md`（三家族完整 file:line 清单）。
> **用户决策：** LLM 生成文字**只生成中文**（单语）；范围**全部纳入**（含报告正文，一次做完）。

---

## 1. 背景与根因

B024 那轮 i18n 只覆盖「界面固定文字」（next-intl key）。但**动态/AI/后端生成**的文字大量绕过 i18n、显示英文。三家族（详见审计 doc，本 spec 不重复 file:line 全表）：

| 家族 | 内容 | 根因 | 修复方向 |
|---|---|---|---|
| **① LLM 生成文字** | 推荐 rationale（用户主诉「标的下面的介绍」）/ 回测解释 / 风险解释 / advisor 建议 | prompt 无任何中文指令（`services/explanation/service.py:37`、`advisor/service.py:54`）→默认英文；单列单语存储 | prompt 加中文指令 + 占位改中文 + **重生成现存解释** |
| **② 后端硬编码英文串 30+** | 策略说明 note×8 / 门控详情 / 订单清单 markdown×10 / 执行 reason / 风险防御说明 / 首页持仓汇总 | 硬编码英文，前端原样渲染 | i18n-key 化（双语，不破 B024 架构） |
| **③ 前端漏译 + 报告正文** | fills buy/sell / zh-CN.json:149 残留英文 / **投资+回测报告整段 markdown** | 前端硬编码 / 报告由 trade/reporting 生成英文 | 前端补 key + zh-CN 修 + **报告模板中文化** |

---

## 2. 范围与原则

**做：** 三家族全部中文化（含报告正文，用户拍板一次做完）。
- LLM 文字（①）：**只生成中文**（单列，用户已定，不追双语）。
- 后端硬编码串（②）+ 前端（③前半）：**i18n-key 双语**（en+zh-CN，保持 B024 parity 架构，cheap 且正确）。
- 报告正文（③后半，最重）：模板级中文化（trade/reporting 段标题/标签出中文；数值/日期语言中性）。

**不做：** 不改策略/评分/回测/风控算法；不改数值（symbol/权重/股数语言中性）；news 源文本（抓取的，非本批）。永久硬边界（§12.10.2 / no-AI / cost_guard cap）不破——加中文指令仍是 summarize/translate，no-AI 边界内。

---

## 3. Feature 分解

| id | executor | 标题 |
|---|---|---|
| F001 | generator | LLM 文字中文化（① prompt 加中文指令 + 占位改中文 + 重生成）+ 测试 |
| F002 | generator | 后端硬编码英文串 i18n 化（② 策略说明/门控/ticket markdown/reason/risk/home，双语 key）+ 测试 |
| F003 | generator | 前端快修（③ fills buy/sell + placeholder + zh-CN.json 残留英文）+ 测试 |
| F004 | generator | 报告正文中文化（投资/回测报告 markdown 模板级中文，trade/reporting）+ 测试 |
| F005 | codex | L1+L2 真 VM——全页面中文核验（无残留英文）+ 回归 + 演练自清 + signoff |

---

## 4. F001 — LLM 文字中文化（generator）

1. **prompt 加中文输出指令**：`services/explanation/service.py` SYSTEM_PROMPT + 三个 REQUEST_LINE（rationale/backtest/risk）+ `advisor/service.py` SYSTEM_PROMPT+REQUEST 加「用简体中文回复（zh-CN）」指令；保持 no-AI 5 规则不变（中文版同样禁收益预测/执行/替代 quant）。
2. **降级占位改中文**：`recommendations/rationale.py:35-37` deterministic placeholder 改中文。
3. **重生成现存解释**：部署后重跑 recommendations/advisor/risk precompute + 触发 risk timer + （可选）重 enqueue 一次 backtest，使生产现存解释立即变中文（不等季度/日常自然刷新）。
4. **§12.10.2 不破**：生成仍在 precompute/worker off 请求路径；references/sentinel 护栏中文版仍生效。
5. **测试**：mock gateway 验 prompt 含中文指令 + 占位中文 + 护栏（中文拒答 sentinel）不破。
6. Gates：backend pytest ≥ baseline+ / ruff 0 / mypy 0 / §12.10.2 守门 / cost_guard 不绕过。

## 5. F002 — 后端硬编码英文串 i18n（generator）

1. **挪 message bundle + 参数化**（双语 en+zh-CN）：策略说明 note×8（strategies.py）/ 门控 detail（recommendations.py:229-236，参数化 dd/threshold/equity）/ 订单清单 markdown×10（tickets.py:99-211 含 disclaimer/列头/"at market"）/ 执行 reason（execution.py:253 + tickets.py defensive rotation）/ 风险防御 rationale（risk_panel.py:84-94/173）/ 首页持仓汇总（home.py:171-172）。
2. **机制**：后端返回 i18n key+params（前端 t() 组装）或后端按请求 locale 出文案（复用 B024 detect_locale/t）——generator 按各串性质二选一注明（数值模板串倾向后端 t()，整段 markdown 倾向 key 化分段）。
3. **已 OK 不动**：error_kind 已有前端 i18n（B047-OPS2）；ticket disclaimer 已双语。
4. **测试**：各串中英 parity + 参数化正确 + i18n parity 守门。
5. Gates：backend pytest ≥ baseline+ / frontend vitest/tsc/lint / i18n parity / api.ts drift 0（若 schema 变）/ ruff/mypy 0。

## 6. F003 — 前端快修（generator）

1. fills 页 `page.tsx:401-402` buy/sell option + `:425` timestamp placeholder → t() key。
2. `messages/zh-CN.json:149` 残留英文「synthetic data, not actual filings」→ 中文译文。
3. 全量 i18n parity 扫描：en.json vs zh-CN.json 缺 key / zh-CN 值仍英文的条目补齐。
4. 测试：vitest + i18n parity 守门。
5. Gates：frontend vitest/tsc/lint / i18n parity 0 缺。

## 7. F004 — 报告正文中文化（generator，触 trade/）

1. **报告模板中文**：`trade/reporting/` 生成的投资报告 + 回测报告 markdown 的**段标题/标签/说明文字**出中文（数值/日期/symbol 语言中性保留）；若报告含 LLM 生成 prose，走 F001 中文生成。
2. **机制**：模板级 i18n（reporting builder 出中文文案）——generator 定（trade/reporting 直接中文 vs 参数化）；注意 CI `mypy trade` 严格（改 trade/ 须本地 `mypy trade` 自检，见 environment.md）。
3. **前端**：Reports `[slug]/page.tsx:95` + Backtest 报告 MarkdownRenderer 渲染中文 markdown，无需前端改。
4. **测试**：报告 markdown 含中文段标题、数值正确、trade 包单测。
5. Gates：backend + trade pytest ≥ baseline+ / ruff / mypy(workbench+trade) 0。

## 8. F005 — Codex L1+L2 真 VM + signoff（codex）

L1 全门禁（含 i18n parity / api.ts drift / mypy trade）。L2 真 VM：**全页面逐页中文核验**——Home/Recommendations（rationale 中文）/Risk（解释中文+防御文案）/Strategies（说明中文）/Backtest（解释+报告中文）/Reports（报告正文中文）/Execution（diff reason+ticket 清单中文）/门控面板中文；**无残留英文**（截图/文本核）；LLM 解释仍守 no-AI 边界（中文版 adversarial 抽验）；回归 B050-B053 不破 + recent-errors=0 + HEAD≡main；**演练自清**（drill_cleanup）。Signoff `docs/test-reports/B054-...-signoff-2026-MM-DD.md` 用模板 + §逐页中文核验证据。更新 progress.json status→done。**core acceptance（§25）**：用户主诉「推荐 rationale 中文」须正面证据（真机截图中文 rationale）。

## 9. 重生成成本

LLM 重生成所有解释一次 + 日常中文生成，在月 cap $200 内（haiku，短文本），无忧。

## 10. Core Acceptance（一句话）

界面所有用户可见英文（LLM 解释 + 后端硬编码串 + 报告正文）全部中文化，用户能准确读懂交易建议——满足交易前 gate。
