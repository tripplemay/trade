# 界面英文文字全面审计——AI/动态文字本地化（2026-06-10）

> **作者：** Planner（用户 2026-06-10：「界面大量 AI 文字还是英文，想做完整 i18n 让我准确读懂交易建议」）。
> **方法：** 3 路并行只读审计（LLM 生成文字 / 后端硬编码英文串 / 前端漏译）。
> **用户决策：** LLM 生成文字**只生成中文**（单语，最简，不追双语 parity）。
> **背景：** B024 只 i18n 了「界面固定文字」（next-intl translation key）；本审计发现**动态/AI/后端生成**的文字大量绕过 i18n、显示英文。
> **用途：** 下一批次 B054 的 spec 依据（用户要求 B053 之后、正式交易前做）。

---

## 1. 三个家族总览

| 家族 | 内容 | 当前 | 处理方式 |
|---|---|---|---|
| **① LLM 生成文字** | 推荐 rationale / 回测解释 / 风险解释 / advisor 建议 | 英文（prompt 无语言指令，单列单语存储）| 加中文指令 + 重生成（用户选只生成中文）|
| **② 后端硬编码英文串** | 策略说明 / 门控详情 / 订单清单 markdown / 执行 reason / 风险防御说明 / 首页持仓汇总 | 英文硬编码，前端原样渲染 | i18n-key 化（双语）或改中文 |
| **③ 前端漏译 + 报告正文** | fills 页 buy/sell、zh-CN.json 残留英文、报告整段 markdown | 英文 | 前端补 key / 报告正文需后端出中文 |

---

## 2. 家族 ① — LLM 生成文字（用户主诉「标的下面的介绍」在此）

| LLM 文字 | 生成位置 | prompt 语言指令 | 存储 | 前端显示 |
|---|---|---|---|---|
| **推荐 rationale**（=用户说的「介绍」）| `services/explanation/service.py:37-63` SYSTEM_PROMPT + `recommendations/rationale.py:25-29` | ❌ 无 | `recommendation_snapshot.rationale` 单列 | Recommendations 表 rationale 列 / PositionCards |
| **回测 explanation** | `backtests/explanation.py:24-29` | ❌ 无 | `backtest_run.explanation` 单列 | Backtest 页 `page.tsx:438` |
| **风险 explanation** | `services/risk_explanation.py:34-38` | ❌ 无 | `risk_explanation_snapshot.explanation` 单列 | RiskBanner.tsx:208 |
| **advisor 建议 advice+rationale** | `advisor/service.py:54-84` SYSTEM_PROMPT + `:154` | ❌ 无 | `advisor_recommendation.advice_json` | Home AdvisorSection.tsx:97-99 |
| **降级占位**（LLM 不可用）| `recommendations/rationale.py:35-37` deterministic placeholder | — | — | 英文 |

**根因**：所有 SYSTEM_PROMPT + REQUEST_LINE 全英文、**无任何「用中文回复」指令** → LLM 默认输出英文。
**修复（用户选只生成中文）**：prompt 加中文输出指令 + 占位文案改中文 + **重生成现存解释**（重跑 precompute/触发 timer）使生产立即变中文。单列存储不变（不追双语）。
**注**：news 摘要=源语言抓取（非 LLM）；topic 标签已是中文（确定性规则）——不在本批。

## 3. 家族 ② — 后端硬编码英文串（30+ 处，前端原样渲染）

| 类别 | 位置 | 示例 | 前端页 |
|---|---|---|---|
| **策略说明 note ×8** | `services/strategies.py:101/133/159/192/223/256/278/296` | "Master core_trend_engine sleeve (planning_weight=0.40)... Research-only advisory — not a return forecast." | Strategies 页详情 |
| **门控详情** | `services/recommendations.py:229-236` | "Master drawdown 0.0197 ≤ threshold 0.15" / "Account equity = 50000.00" | Recommendations 门控面板 |
| **订单清单 markdown ×10**（大块）| `services/tickets.py:99-211` | "Manual review checklist. The system does NOT place orders. You are the executor." / "place LIMIT orders only" / 列头 / "at market" | Ticket 页全屏 |
| **执行 reason** | `services/execution.py:253` + `tickets.py:271/289/308` | "held but no longer in target — sell to zero" / "Defensive rotation — ..." | Position diff / Ticket reason 列 |
| **风险防御说明**（大块）| `services/risk_panel.py:84-94/173` | "Kill switch tripped — rotate fully into the defensive sleeve..." | Risk 防御票 rationale |
| **首页持仓汇总** | `services/home.py:169-172` | "1 position" / "{n} positions" | Home sleeve 分解 |

**已 OK（不改）**：error_kind 已有前端 i18n 映射（B047-OPS2）；ticket disclaimer 已双语（DISCLAIMER_LITERAL + _ZH）。

## 4. 家族 ③ — 前端漏译 + 报告正文

| 项 | 位置 | 处理 |
|---|---|---|
| fills 页 buy/sell 选项 | `fills/page.tsx:401-402` | 前端补 t() key（快修）|
| fills 时间戳 placeholder | `fills/page.tsx:425` | 前端补 key（快修）|
| zh-CN.json 残留英文 | `messages/zh-CN.json:149` "synthetic data, not actual filings" | 改中文译文（快修）|
| **报告正文整段 markdown**（最大块）| `reports/[slug]/page.tsx:95` `<MarkdownRenderer body={body_markdown}/>` | **投资报告 markdown 由 trade/reporting/ 生成全英文**——前端无法译，需**后端出中文**（generate 中文 or 模板 i18n）|

---

## 5. B054 scope 与设计决策（留 planning 拍）

**确定：**
- 家族 ①：prompt 加中文指令 + 重生成（只生成中文，用户已定）。
- 家族 ③ 前端快修（3 处）+ zh-CN.json 修。

**留 planning 决策：**
1. **家族 ② 用 i18n-key（双语）还是改中文**？项目 B024 是双语 parity 架构——i18n-key 化更一致但工作量大（30+ 串挪 message bundle + 参数化）；改中文最简但破双语。鉴于用户要中文优先，建议**参数化 + i18n-key**（既中文又不破架构），但门控/reason 这类「数值+模板」串参数化较繁。
2. **报告正文 markdown（最大块）怎么出中文**？trade/reporting/ 生成的投资报告/回测报告整段英文。选项：(a) 报告 builder 出中文（动 trade/ 包）；(b) 报告分段 i18n 模板（重构 builder）；(c) 本批先不动报告正文、只做 ①②+前端（报告正文留子批）。**建议 (c)**——报告正文是独立大块，先把高频的 rationale/解释/策略说明/门控/ticket 做掉，报告正文单列子批。
3. **重生成成本**：LLM 重生成所有解释一次 + 日常中文生成，在 $200/月 cap 内，无忧。

**建议分 feature**：F001 LLM 文字中文化（①，prompt+重生成，高频用户主诉）；F002 后端硬编码串 i18n（②策略说明/门控/ticket/reason/home）；F003 前端快修（③ fills/zh-CN.json）；F004 报告正文中文（最大块，可选/可拆子批）；F005 codex 真 VM 全页面中文核验 + signoff。

---

## 6. 一句话

界面英文 = LLM 生成文字（prompt 无中文指令）+ 后端 30+ 硬编码英文串 + 报告整段 markdown 三大家族；B054 按用户「只生成中文」做完整本地化，优先高频的推荐/解释/策略说明，报告正文作最大块可拆子批。
