# Workbench 用户画像与每日工作流（2026-05-25 draft）

> **状态：** draft，待用户审阅。本文档由 Planner 在 B025 done 阶段与用户 5 轮 Q&A 后撰写。
> **配套：** `docs/product/positioning-2026-05.md`（产品定位 + 三层定义）
> **目的：** 把"用户每天怎么用 workbench"具象化，作为后续 UI / 功能优先级判断依据。

---

## 1. Primary Persona — "Yixing"（你本人，唯一用户）

| 维度 | 值 |
|---|---|
| 角色 | Workbench 创建者 + 唯一使用者 |
| 投资经验 | 中等（实际持有美股 + ETF + 现金，但缺乏系统化工具）|
| 量化背景 | 较浅（不熟 Sharpe / Sortino / Calmar / MDD，需 tooltip / 解释）|
| 技术背景 | 高（能写代码，但 workbench 使用时不希望工程师 mindset 主导）|
| 资产规模 | 个人投资资产全部（具体数额由用户私有；workbench 不强制 hard-code）|
| 资产类别 | 股票 + ETF + 现金；潜在 multi-currency（USD + 可能 HKD / RMB）|
| 实盘渠道 | **手动 IBKR**（个人券商账户）|
| 决策态度 | 保留全部决定权；workbench 提供方向 + 数据，用户判断 + 下单 |
| 使用频率 | **每天**（高频 monitoring，类似看股价）|
| 调仓节奏 | **每季度**（Master Portfolio quarterly cadence）+ kill-switch 触发时即时响应 |
| 心智模型 | "Workbench 是我的投资决策大脑助手，每天看一眼，帮我判断是否需要操作" |
| 工具替代史 | **无前置工具**（workbench 是首个系统化工具，前面是 ad-hoc / 凭感觉 / 朋友推荐）|

---

## 2. Daily Journey — 工作日 9:30 AM 美东市场开盘后

**触发：** 用户起床后习惯性打开 workbench（mobile or desktop）。

```
┌─────────────────────────────────────────────────────────┐
│                  Home Page Dashboard                    │
│                                                         │
│  📊 Total NAV: $XXX,XXX (+0.45% / +$X,XXX today)        │
│                                                         │
│  🟢 Portfolio status: Normal · Next rebalance in 12d    │
│                                                         │
│  📰 Today's market context:                             │
│  • S&P 500 +0.3% · QQQ +0.5% · 10y yield 4.21%         │
│  • Fed minutes released (sentiment: neutral hawkish)    │
│  • TSMC reports Q1 earnings beat                        │
│  • [Industry news affecting your sleeves...]            │
│                                                         │
│  4 Sleeve Snapshot:                                     │
│  ├─ Momentum (40%)     +0.6% today  ✅                  │
│  ├─ Risk Parity (30%)  +0.2% today  ✅                  │
│  ├─ US Quality (20%)   +0.8% today  ✅                  │
│  └─ HK-China (10%)     -0.1% today  ✅                  │
│                                                         │
│  No actions needed today. ✓                             │
└─────────────────────────────────────────────────────────┘
```

**用户行为流：**

1. **0-5 秒**：扫一眼总 NAV + 今日涨跌 + 状态绿灯 → 满意 / 关闭页面 / 继续看
2. **5-30 秒（若有时间）**：浏览今日市场新闻 + 4 sleeve breakdown，了解资产为什么涨/跌
3. **30 秒-2 分钟（若有 alert）**：点击 alert（如 sleeve drawdown > 5% / kill-switch warning），看详情决定是否调仓

**90% 的日子用户停在 0-5 秒** —— "看一眼放心，关掉"。
**10% 的日子用户进入 30 秒-2 分钟** —— 真实关注 alert 或好奇 sleeve 表现。
**3 个月一次（季度日）用户深入使用** —— 调仓决策。

## 3. Quarterly Journey — 季度调仓日（每年 4 次）

**触发：** Master Portfolio rebalance date 到达（系统自动提示 + Home 页显示 "Rebalance day"）。

**用户行为流：**

1. 打开 Recommendations 页 → 看 satellite_us_quality / momentum / risk_parity 各自 target positions
2. 对比当前持仓 → 计算 deltas（buy XX / sell YY）
3. 点击 "Generate ticket" → 系统输出 Markdown checklist
4. 用户带 ticket 切到 IBKR → **逐条人工下单**（系统不连券商）
5. 成交后回到 workbench → 上传 CSV 或手动填 fills → 系统 reconcile
6. 系统 update journal → 用户在 Home 页看到下个 rebalance date

**这一流程已在 B023 完整落地，无需重做。**

## 4. Triggered Journey — Kill-switch 触发（罕见但关键）

**触发：** Master Portfolio drawdown 触发 kill-switch 阈值（>15% MDD）。

**用户行为流：**

1. Home 页变 **🔴 红灯**：`Portfolio drawdown 16.2% - Kill-switch activated`
2. 用户点击 alert → 进入 Risk Panel 看详情
3. Risk Panel 显示：哪个 sleeve 主要责任 / 历史回撤对比 / 建议处置（defensive ticket）
4. 用户选择：**继续观察** / **生成 defensive ticket（清仓到 SGOV）** / **手动调整**
5. 若选 defensive → 同 quarterly journey 后半段（generate ticket → IBKR → CSV 回填）

**这一流程也已在 B023 落地。**

## 5. Ad-hoc Journey — 用户研究 / 试验新策略想法

**触发：** 用户读到一篇研究 / 听到一个想法 / 想尝试一个参数。

**用户行为流：**

1. （未来）用户进入 Strategies 页修改参数（如 momentum top_n 5→10）
2. 跑回测看历史表现
3. 与现有 sleeve 对比 → 决定是否替换现有参数

**这一流程目前未实现**（参数是 frozen dataclass，UI 不暴露修改入口）。属于 Layer 0→1 之后可能的产品方向，**本批次不做**。

## 6. Anti-Journeys（用户**不会**这样用）

| 反场景 | 为什么不做 |
|---|---|
| 每天调仓 | Master Portfolio quarterly cadence；用户认同低频 actuation |
| 在 workbench 下单 | 永久边界 no broker；用户认同手动 IBKR |
| 用 workbench 选股 | 用户接受 Master Portfolio 系统化框架，不做主观个股选择 |
| 用 workbench 直接看 LLM 建议 | 永久边界 no AI fit/predict |
| 给朋友看 workbench | 单用户 allowlist；如有分享需求是另一种产品（不在范围内）|
| 跟其他用户社区互动 | 个人工具，无社区 |

## 7. UI 优先级（基于上述 journey）

| 页面 | 每日打开重要性 | 现状质量 | 改造优先级 |
|---|---|---|---|
| **Home 页**（含 NAV / 今日 / market context / sleeve breakdown） | ⭐⭐⭐⭐⭐ | ❌ 当前是 quant dashboard，不含 market context | **极高**（这是用户每日打开 90% 时间停留的地方）|
| Reports | ⭐⭐ | ⚠️ 当前 Sharpe/Sortino 表格，需 Robinhood-style 简化 | 中等（每季度看 1-2 次）|
| Recommendations | ⭐⭐⭐ | ⚠️ 季度日重度使用，需简化 + "为什么这样建议" | 中等（每季度 1-2 周高频）|
| Risk Panel | ⭐⭐⭐⭐ | ✅ 已较简化，但仍有 jargon | 低-中等 |
| Strategies | ⭐⭐ | ⚠️ 显示用，不修改 | 低 |
| Position-diff / Ticket / Fills / Journal-history / Account | ⭐⭐⭐（季度日）| ✅ B023 已落地，工作流顺畅 | 不动 |

## 8. 决策度量（不是技术 KPI）

| 度量 | 当前值 | 目标值 |
|---|---|---|
| 用户每周打开 workbench 次数 | 未度量 | ≥5 次（与"每日看股价"对齐）|
| 用户在 Home 页停留时间 | 未度量 | 0-5 秒（理想）/ 30 秒（中等）|
| 用户依赖 workbench 做投资决策的比例 | 未度量 | ≥80%（季度调仓 100% 走 workbench）|
| 误用 synthetic data 风险事件 | 未发生 | 0（UI banner + Layer 0→1 接入真数据后归零）|
| 用户主动跳出 workbench 看其他工具 | 未度量 | 减少（market context 接入后应进一步降低）|

## 9. Doc Lifecycle

- **当前状态：** draft（2026-05-25 Planner 撰写）
- **下一步：** 用户在 chat 中校正 → Planner 同 commit 修订 → 用户最终批准后改 status：approved

---

> 配套：`docs/product/positioning-2026-05.md`（产品定位 + 三层定义 + backlog 重排）
