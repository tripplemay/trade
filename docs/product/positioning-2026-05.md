# Workbench 产品定位（2026-05-25 draft）

> **状态：** draft，待用户审阅。本文档由 Planner 在 B025 done 阶段与用户 5 轮 Q&A 后撰写。
> **目的：** 在启动 B026 之前对齐"workbench 究竟为谁、做什么、不做什么"，让后续技术批次不再脱离产品 vision。
> **来源：** 用户在 done 阶段 5 轮 AskUserQuestion 答复，每个判断都有用户原话来源（引用见 §5）。

---

## 1. 一句话定位

> **Personal portfolio dashboard with quant brain inside.**
>
> 单人使用、辅助本人真实财产管理决策的私人投资 dashboard。后台有多策略量化研究框架（5 因子动量 + 风险平价 + satellite），前台呈现走 Robinhood-style 简化路线。永远不是 SaaS、永远不连券商、永远不自动下单。

## 2. 三层定义（research / paper / live）

| 层级 | 定义 | workbench 当前状态 | workbench 目标 |
|---|---|---|---|
| **Layer 0 — Synthetic research prototype** | 用合成 fixture 跑策略 / 回测，验证架构与交互，**所有数字都不能作为决策输入** | ✅ **当前位置**（B001-B025）。Master Portfolio 4 sleeve、5 因子评分、回测报告、Recommendations、Risk Panel 全部基于 synthetic data | 已完成；需在 UI 加 banner 显式声明（防止用户误用）|
| **Layer 1 — Real historical data research** | 接入真实历史价格 snapshot + point-in-time 基本面，**回测指标第一次有意义** | ❌ 未到达 | **下个里程碑**（用户在 done 阶段明确选择）|
| **Layer 2 — Paper trading** | 真实数据 + 模拟下单（仍 no-broker SDK） | ❌ 未到达 | 中期，价值未知（用户当前是手动 IBKR 实盘，paper 价值偏低）|
| **Layer 3 — Live trading（broker SDK 接入）** | 自动化下单 | ❌ 永不到达 | **永久边界**，不在产品 roadmap |

**关键：** Layer 0→1 是本年度最重要的产品里程碑。

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
- ❌ **AI 直接决策 / fit-predict 模型**（永久边界）
- ❌ **房产 / 保险 / 加密 资产管理**（不在 workbench 范围；保留在外部工具）
- ❌ **跟单 / 社区 / leaderboard**（个人工具）

## 7. 后续批次（基于本定位重新评估）

| Backlog | 在本定位下的价值评估 | 建议优先级 |
|---|---|---|
| **Real data ingest**（B009 snapshot 路径升级 + 全 sleeve 替换 fixture） | Layer 0→1 必经；让所有现有 sleeve 第一次有真实指标 | **新增 high**，应优先于 HK-China |
| **Home 页 dashboard 重构 + market context** | Daily engagement 核心；用户每日打开主要看 Home | **新增 high** |
| **Reports / Recommendations UI Robinhood-style 简化** | UI 重大改造但与 Layer 0→1 平行可做 | **新增 medium-high** |
| **UI synthetic-data banner**（轻量提示 + i18n）| 在 Layer 0 期间防止误用，应尽快做 | **新增 medium**，1 个轻量批次 |
| **BL-B011-S2 HK-China satellite**（原 high）| 仍是 fixture，不解决 Layer 0→1，价值有限 | **降级 medium**（等真数据接入后再做）|
| **BL-B010-S1 risk parity 专用 fixture**（原 low）| 同上，fixture 时代产物 | **不再做**（Layer 0→1 后自然过时）|
| **BL-B013-D1 / BL-B013-D2**（原 low）| vol-target / VIX overlay 研究 | **保持 low**，待真数据后再评估 |
| **BL-B023-S1 / BL-B023-S2**（原 low）| 生产冒烟演练 | **保持 low**，环境完成后做 |

## 8. 衍生 framework 议题（不立即处理，记账）

1. **永久边界增补建议：** 当前 framework v0.9.21-v0.9.27 都从技术维度定义边界（no broker / no live / Repository pattern），需要补**产品边界**（"不商业化 / 不替决策 / 全资产范围"）。建议下次 framework 沉淀加入"product boundary"层。
2. **测试断言风险：** 现有大量回测断言基于 fixture 范围（如 B025 "年化 [5%,25%] / Sharpe [0.3,1.5] / MDD<50%"）。Layer 0→1 切换时这些断言会全部失效，需提前规划 fixture vs real-data assertion 切换策略（v0.9.21 testing-and-fixture-policy 已部分覆盖，需扩展）。

## 9. Doc Lifecycle

- **当前状态：** draft（2026-05-25 Planner 撰写）
- **下一步：** 用户在 chat 中校正 → Planner 同 commit 修订 → 用户最终批准后改 status：approved
- **生效信号：** 后续所有批次 spec 第一节必须引用本 doc 当前位置（哪一层 + 目标层 + UI 是否符合 Robinhood-style 期望）

---

> 配套：`docs/product/user-personas-and-journeys-2026-05.md`（用户画像与每日工作流细化）
> 与 `docs/prd/mvp-prd.md` 关系：本 doc 是 PRD 的 **post-MVP supplement**，不替代 PRD。PRD 描述 MVP 范围（已完成），本 doc 描述下一里程碑产品 vision。
