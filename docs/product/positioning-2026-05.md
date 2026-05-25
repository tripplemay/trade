# Workbench 产品定位（2026-05-25 draft）

> **状态：** **approved**（2026-05-25 用户批准）。本文档由 Planner 在 B025 done 阶段与用户 6 轮 Q&A 后撰写。
> **目的：** 在启动 B026 之前对齐"workbench 究竟为谁、做什么、不做什么"，让后续技术批次不再脱离产品 vision。
> **来源：** 用户在 done 阶段 5 轮 AskUserQuestion 答复，每个判断都有用户原话来源（引用见 §5）。

---

## 1. 一句话定位

> **AI-augmented personal portfolio decision support tool, built on a quant-strategy chassis.**
>
> 单人使用，辅助本人真实财产管理决策。**Quant 策略框架（Master Portfolio + 5 因子 + risk parity + satellite）做底层规则评分；AI 层叠加在 quant 之上，整合真实市场数据 + 新闻/宏观/行业信息，给出综合投资建议**。前台呈现走 Robinhood-style 简化路线。AI 不替代 quant 评分（避免幻觉直驱决策），不输出"预期收益"数字（避免误导），最终决策权与执行权 100% 在用户手上。永远不是 SaaS、永远不连券商、永远不自动下单。

## 1.1 AI 角色与边界（B025 done 阶段用户明确）

| AI 可做 | AI 不可做 |
|---|---|
| 解释 quant signal 含义（"为什么 Master 推荐这个 sleeve"）| 替代 quant signal（不能跳过 Master 评分直接给 buy/sell）|
| 整合新闻 / SEC filings / 宏观数据 → 与 quant signal 协同的 context | 直接基于自然语言"我觉得 TSLA 要涨"给建议 |
| Robinhood-style 简化文案（把 Sharpe / Sortino 翻成大白话）| 输出"预期年化 X%" / 任何收益预测数字 |
| 给 actionable buy/sell 建议（基于 quant signal + news 综合）| 自动下单 / 连接 broker（永久硬边界）|
| 给建议的可解释引用（哪条 quant signal + 哪条 news → 为什么建议这样）| 给无引用的黑盒建议（必须可追溯）|
| 多语言（zh + en，继承 B024）| 跨用户分享建议（单用户 allowlist）|
| 解释历史回撤归因 | 替代风控规则（kill-switch 仍由规则触发，不由 AI 判断）|

**核心原则：AI 是 quant 与用户之间的翻译/整合层，不是策略本身。**

## 2. 三层定义（research / paper / live）

| 层级 | 定义 | workbench 当前状态 | workbench 目标 |
|---|---|---|---|
| **Layer 0 — Synthetic research prototype** | 用合成 fixture 跑策略 / 回测，验证架构与交互，**所有数字都不能作为决策输入** | ✅ **当前位置**（B001-B025）。Master Portfolio 4 sleeve、5 因子评分、回测报告、Recommendations、Risk Panel 全部基于 synthetic data | 已完成；需在 UI 加 banner 显式声明（防止用户误用）|
| **Layer 1 — Real historical data research** | 接入真实历史价格 snapshot + point-in-time 基本面，**回测指标第一次有意义** | ❌ 未到达 | **核心里程碑 #1**（与 Home/UI 改造同等重要并行推进，用户 done 阶段明确）|
| **Layer 1.5 — AI-augmented advisory (新增)** | quant signal + real data + news/macro context → AI 综合投资建议（含可解释引用，不含预期收益）| ❌ 未到达 | **核心里程碑 #2**（与 Layer 1 平行；Layer 1 为前提）|
| **Layer 2 — Paper trading** | 真实数据 + 模拟下单（仍 no-broker SDK） | ❌ 未到达 | 中期，价值未知（用户当前是手动 IBKR 实盘，paper 价值偏低）|
| **Layer 3 — Live trading（broker SDK 接入）** | 自动化下单 | ❌ 永不到达 | **永久边界**，不在产品 roadmap |

**关键：** Layer 0→1（real data） + Layer 0→1.5（AI advisory）+ Home/UI 简化重构 三件大事**并行推进**，本年度产品 roadmap 中心。

## 3. 目标用户（仅 1 人）

| 维度 | 值 |
|---|---|
| 用户数 | **1**（你本人） |
| 商业化 | 永不（不走 SaaS / 不收费 / 不公开注册） |
| 多租户 | 永不（单 email allowlist 永久强制） |
| 资产范围 | **全部投资资产**（股票 + ETF + 现金；潜在 multi-currency） |
| 量化背景 | 较浅（不熟 Sharpe/Sortino/Calmar 等术语）→ **UI 必须 Robinhood-style 简化** |
| 现有工具 | **无**（workbench 是用户首个系统化投资管理工具，前无 Excel / Notion / Bloomberg / 量化平台）|
| 使用频率 | **每天打开，类似看股价**（高频 monitoring + 低频 actuation）|
| 实盘渠道 | 用户**手动 IBKR**（workbench export Markdown ticket → 人工下单 → 回填 journal）|
| 决策角色 | workbench 是辅助决策工具，**用户保留所有决定权**；workbench 不替用户决策、不自动下单 |

**衍生约束：**

1. **每日打开** → Home 页必须有"每日值得看一眼"的内容（不能只展示季度调仓 cadence 的静态信息）
2. **量化术语简化** → Reports / Strategies / Risk panel 现有 quant-jargon 表格需要重大改造（参考 Robinhood / Public.com 而非 Bloomberg）
3. **真实财产管理** → synthetic data 误用风险极高，UI 必须显式标注数据来源
4. **首个系统化工具** → 不需要 import from Excel / migration 路径；workbench 是绿地（greenfield）

## 4. 当前形态 vs 期望形态 gap（启发 backlog 重排）

| 维度 | 现有形态（B001-B025） | 期望形态（用户答复） | gap 等级 |
|---|---|---|---|
| Home 页内容 | static research dashboard（4 sleeve summary） | **市场 / 行业 / 宏观新闻聚合** + 每日 NAV / Day P&L | **重大** |
| 数据来源 | 100% synthetic fixture | 真实历史价格 + 真实基本面 | **重大**（已在 BL backlog）|
| Reports 页 UI | Sharpe / Sortino / Calmar / MDD 表格 | Robinhood-style 大数字 + 颜色 + 简短文案 | **中等** |
| Recommendations 页 UI | target positions 专业表格 | 简化呈现 + tooltip 解释 + "为什么这样建议" | **中等** |
| Risk Panel | drawdown / kill-switch 状态 | 类似（已是简化版，但仍有专业术语）| 小 |
| Manual execution 流（B023） | Markdown ticket export → IBKR → CSV 回填 | 不变 | ✅ 对齐 |
| 季度调仓 cadence（B011） | quarterly + kill-switch | 不变 | ✅ 对齐 |
| 双语（B024）| zh-CN + en | 不变 | ✅ 对齐 |
| 永久边界（no broker / no live）| enforced | 不变 | ✅ 对齐 |

**结论：** workbench 后端架构与永久边界与用户期望对齐；**最大 gap 在 Home 页内容形态 + 数据真实性 + UI 简化呈现**。

## 5. 产品价值主张（用户答复原话）

| 主张 | 用户原话来源 |
|---|---|
| 不替你决策、辅助你决策 | "财产管理决策辅助工具" |
| 单人使用，永远不商业化 | "只你本人个人用 (Recommended)" |
| 真实数据是下个核心目标 | "Research with real historical data (下个里程碑)" |
| 简化呈现，不要 quant jargon | "需要产品类似销售 Robinhood 那样简化" |
| 每日打开高频使用 | "每天看，类似看股价" |
| Home 页是新闻聚合 | "市场 / 行业 / 宏观新闻 聚合" |
| 全部投资资产范围 | "全部投资资产（股票 + ETF + 现金）" |
| 这是首个系统化工具 | "还没现有工具，workbench 是首个系统化上台工具" |

## 6. 明确不做的事（YAGNI）

- ❌ **SaaS 商业化**（永远）
- ❌ **多用户 / 注册流 / billing**（永远）
- ❌ **自动下单 / broker SDK 接入**（永远）
- ❌ **GDPR / SOC2 / compliance certifications**（不商业化所以不需要）
- ❌ **paper trading 自动化**（你已经手动 IBKR 实盘，paper 价值低）
- ❌ **AI 替代 quant 评分直接给 buy/sell**（保持 quant 作为基础规则层；AI 是叠加层而非替代层）
- ❌ **AI 输出"预期收益"数字 / 任何收益预测**（防止误导）
- ❌ **AI 触发 kill-switch / 自动风控决策**（kill-switch 仍由规则触发，AI 不接管风控）
- ❌ **房产 / 保险 / 加密 资产管理**（不在 workbench 范围；保留在外部工具）
- ❌ **跟单 / 社区 / leaderboard**（个人工具）

## 6.1 永久边界更新（B025 done 阶段，待 framework 沉淀）

原 framework v0.9.21-v0.9.27 永久边界中的 `no-AI fit/predict` 在产品定位明确后应**精细化**为：

| 旧表述（v0.9.21-v0.9.27）| 新表述（待 framework v0.9.28 沉淀）|
|---|---|
| `no-AI fit/predict` 一刀切 | (a) `no-AI auto-execution`（永久）<br>(b) `no-AI 收益预测数字输出`（永久）<br>(c) `no-AI 替代 quant 评分作为唯一决策依据`（永久）<br>(d) `AI 必须基于 quant signal + real data + 可引用 news` 才能输出建议（永久）<br>(e) AI 解释 / summarize / translate / context aggregation **允许** |

## 7. 后续批次（基于本定位重新评估）

| Backlog | 在本定位下的价值评估 | 建议优先级 |
|---|---|---|
| **Real data ingest**（B009 snapshot 路径升级 + 全 sleeve 替换 fixture） | Layer 0→1 必经；让所有现有 sleeve 第一次有真实指标；AI advisory 的硬前置 | **新增 critical**（与下两条并行 #1）|
| **News / market context / SEC filings ingest** | Layer 0→1.5 AI advisory 的信息源；Home 页 daily engagement 内容 | **新增 critical**（与上下并行 #2）|
| **AI advisory engine**（LLM 接入 + prompt template + cache + safety + 可解释引用） | Layer 0→1.5 核心；用户原本期望 + 路径 B 落地 | **新增 critical**（依赖前两条；可与其早期并行设计）|
| **Home 页 dashboard 重构**（NAV + Day P&L + news context + 4 sleeve breakdown + AI 综合建议） | Daily engagement 核心；用户每日打开主要看 Home | **新增 high**，与 critical 三件平行 |
| **Reports / Recommendations UI Robinhood-style 简化** | UI 重大改造；与 critical 三件平行可做 | **新增 medium-high** |
| **UI synthetic-data banner**（轻量提示 + i18n）| Layer 0 期间防止误用；Layer 0→1 完成前必装 | **新增 medium**，1 个轻量批次 |
| **Framework v0.9.28 永久边界精细化** | 把 `no-AI fit/predict` 一刀切改为本 doc §6.1 5 子条 | **新增 medium**，1 个轻量批次 |
| **BL-B011-S2 HK-China satellite**（原 high）| 仍是 fixture，不解决 Layer 0→1 / 0→1.5，价值有限 | **降级 low**（等真数据接入 + AI advisory 框架成型后再做）|
| **BL-B010-S1 risk parity 专用 fixture**（原 low）| fixture 时代产物 | **不再做**（Layer 0→1 后自然过时）|
| **BL-B013-D1 / BL-B013-D2**（原 low）| vol-target / VIX overlay 研究 | **保持 low**，待真数据后再评估 |
| **BL-B023-S1 / BL-B023-S2**（原 low）| 生产冒烟演练 | **保持 low**，环境完成后做 |

## 8. 衍生 framework 议题（不立即处理，记账）

1. **永久边界精细化（v0.9.28 候选）：** 把当前 `no-AI fit/predict` 一刀切改为本 doc §6.1 5 子条；同时新增"product boundary"层（不商业化 / 不替决策 / 全资产范围）。
2. **测试断言风险：** 现有大量回测断言基于 fixture 范围（如 B025 "年化 [5%,25%] / Sharpe [0.3,1.5] / MDD<50%"）。Layer 0→1 切换时这些断言会全部失效，需提前规划 fixture vs real-data assertion 切换策略（v0.9.21 testing-and-fixture-policy 已部分覆盖，需扩展）。
3. **AI advisory safety pattern（新议题）：** LLM 接入框架在 framework 中尚无任何沉淀。Layer 0→1.5 需要：(a) prompt template 版本管理；(b) cache 策略（同 quant signal + 同 news context → 同建议，可缓存）；(c) cost 控制（用户每日查 1 次 vs 每天 100 次的 cost 量级差）；(d) safety eval（红队测 AI 给"预期收益"、给 buy/sell 而无引用、跟单 hallucination 的失败率）；(e) human review fallback（AI 不确定时升级给用户判断）。
4. **数据来源选型议题：** 真实价格数据有多种来源（Polygon / Alpha Vantage / yfinance / IEX / EODHD / SEC EDGAR）；基本面 point-in-time 更受限（Polygon / FactSet / Refinitiv 付费）。Layer 0→1 第一批次需做选型 + 评估 + 决策。
5. **AI provider 选型议题：** Anthropic / OpenAI / Gemini / local LLM 各有权衡（cost / quality / latency / context length）。Layer 0→1.5 第一批次需做选型 + 评估。

## 9. Doc Lifecycle

- **当前状态：** **approved**（2026-05-25 用户批准）
- **生效信号：** 后续所有批次 spec 第一节必须引用本 doc 当前位置（哪一层 + 目标层 + UI 是否符合 Robinhood-style 期望 + AI 是否触及 §1.1 / §6.1 边界）
- **修订流程：** 重大产品方向变更（如 AI 边界放宽到路径 C / 商业化决策）需新 doc 替代本 doc，本 doc 改 status: superseded-by-<new-doc-name>；小修订（typo / 字段补充）直接 commit

---

> 配套：`docs/product/user-personas-and-journeys-2026-05.md`（用户画像与每日工作流细化）
> 与 `docs/prd/mvp-prd.md` 关系：本 doc 是 PRD 的 **post-MVP supplement**，不替代 PRD。PRD 描述 MVP 范围（已完成），本 doc 描述下一里程碑产品 vision。
