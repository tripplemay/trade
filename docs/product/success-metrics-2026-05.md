# Success Metrics（2026-05-25）

> **状态：** **approved**（2026-05-25 用户批准）
> **配套：** `docs/product/positioning-2026-05.md` §8 决策度量 + `docs/product/user-personas-and-journeys-2026-05.md` §8
> **目的：** 在不引入自动追踪的前提下，提供"用户有意愿时翻阅"的指标 checklist + 触发条件，避免产品迭代凭直觉走偏。
> **范围：** 候选指标 + 手动周报模板 + review 触发条件。**不含**：telemetry 实施 / 自动采集架构 / KPI 周期。

---

## 1. 选型约束（用户已批 2026-05-25）

| 维度 | 用户偏好 | 含义 |
|---|---|---|
| 收集机制 | **手动周报**（不自动采集）| workbench 不加 telemetry / event tracking / analytics SDK |
| Synthetic data 误用追踪 | **不追踪，依靠用户自侦** | 不量化 INSUFFICIENT_GROUNDING / banner 出现频率 |
| Review 周期 | **不设周期，有意愿时才看** | 不强制 monthly 或 quarterly review；触发型 |
| 隐私 | 全部数据不出本机 | 即使未来加 telemetry 也只走 local SQLite，不发任何外部 SaaS |

**核心原则：** workbench 是单人 personal use，不需要 PostHog / Plausible / Sentry 等专业 analytics。这份 doc 是**梳理指南**而非 dashboard。

## 2. 候选指标 Checklist（用户有意愿时翻阅）

### 2.1 使用强度信号

| 指标 | 自侦方法 | 健康范围 |
|---|---|---|
| 每周打开 workbench 次数 | 自己回想 / Git history `last 7 day commit count` 大致代理 | ≥5 次（"每天看股价"对齐）|
| Daily Journey 实际时长 | 自己回想最近 1 周 | 0-5 秒占多数；偶尔 30 秒-2 分钟即正常 |
| 是否在非季度日仍打开 | 自检 | 是 = 产品 daily engagement 达成 |

### 2.2 决策依赖信号

| 指标 | 自侦方法 | 健康范围 |
|---|---|---|
| 季度调仓是否 100% 走 workbench | 自检：本季度有无凭感觉跳过 workbench 直接下单 | 季度内 100% 走 = portfolio brain 角色达成 |
| AI 建议是否被实际采纳 | 季度调仓后回看 ticket vs 当时 AI 建议 | 部分采纳 / 全部参考 = AI 价值达成；全部忽略 = AI 价值未达 |
| Risk Panel 是否真的被看 | kill-switch 触发时是否第一时间打开 Risk Panel | 触发即看 = Risk 决策辅助达成 |

### 2.3 产品形态信号

| 指标 | 自侦方法 | 健康范围 |
|---|---|---|
| Home 页是否仍是首页 | workbench 打开后第一眼是否落在 Home | 是 = Home 重构成功；否（直接跳 Reports / Recommendations）= Home 内容不到位 |
| 是否跳出 workbench 看其他工具 | 自检：本周看 IBKR app / Yahoo Finance / 其他 app 的频次 | 减少 = workbench 覆盖度提升 |
| 是否对某些数字心存疑虑（"这指标我都不知道是什么意思"）| 自检 | 减少 = Robinhood-style 简化成功 |

### 2.4 边界与安全信号

| 指标 | 自侦方法 | 健康范围 |
|---|---|---|
| 是否曾误用 synthetic data 数字做实盘决策 | 自检（**用户负主要侦察责任**）| 0 次 = 边界守护成功 |
| 是否在 Layer 0 期间真的注意到 banner | 自检 | 是 = banner 设计有效 |
| 是否 AI 建议给过明显违反 5 子条边界的输出 | 自检（季度回看 AI 建议历史）| 0 次 = Stream 3.B CI eval + prompt 设计有效 |

### 2.5 不要量化的（明确放弃）

- ❌ 用户净值变化（与产品价值不强相关；策略本身就有随机性）
- ❌ 回测 Sharpe 数字本身（与"产品是否好用"无关）
- ❌ 任何"竞品对比"指标（无竞品，单人 personal use）
- ❌ "App engagement score" / "DAU" 等 SaaS-style metric

## 3. 手动周报 / 月报模板（Notion / Excel / 纸笔均可）

**模板可放在 user 本地 Notion / Apple Notes / Markdown 都行。本 doc 不强制位置。**

```markdown
# Workbench Self-Review YYYY-MM-DD

## 使用强度
- 本周打开 workbench 次数（估计）：
- 单次打开最长停留：
- 本周非季度日是否仍有打开：

## 决策依赖
- 本周有没有凭感觉跳过 workbench 做投资决策：
- AI advisor 给过哪些建议被采纳：
- AI advisor 给过哪些建议被忽略 / 觉得不准：

## 产品形态
- 现在打开 workbench 第一眼想看哪一页：
- 本周看 IBKR / Yahoo / 其他工具几次：
- 哪些数字 / 标签仍不理解：

## 边界
- 本周是否觉得 AI 建议靠不住 / 数据靠不住：
- 本周 banner / INSUFFICIENT_GROUNDING 是否注意到：

## 改进想法
- 本周想到的产品改进：
- 优先级：

## 下周关注重点
- ...
```

## 4. Review 触发条件（替代周期）

**用户主动 review 的建议触发：**

1. **季度调仓日**：调仓后回顾本季度 AI 建议是否对齐 / quant signal 是否说服
2. **kill-switch 触发**：触发后 1 周内回顾 Risk Panel 是否真的帮助决策
3. **新批次启动前**：spec 起草时 review 上批次的"使用强度"+"决策依赖"信号，判断方向
4. **半年自然 milestone**：2026 年中 / 年底各 1 次轻量梳理（即使没特别触发）
5. **明显异常**：发现自己一周没打开 workbench / 发现自己开始凭感觉决策 / 发现自己跳过 workbench → 触发 review

**用户没有义务在固定周期 review。** 本 doc 不创造 KPI 压力。

## 5. 不做的事

- ❌ **自动采集 telemetry** — workbench 不加 event tracking / analytics SDK
- ❌ **接 PostHog / Plausible / Mixpanel** — 与"永不商业化 / 永不多用户"产品边界不匹配
- ❌ **强制 monthly review cadence** — 用户偏好"有意愿时才看"
- ❌ **量化 synthetic data 误用率** — 依靠用户自侦
- ❌ **AB test 产品功能** — 单人 product，无 AB
- ❌ **leaderboard / 对比 SaaS 平均水平** — 无社区
- ❌ **Sentry / 错误监控 SaaS** — 现有 `/api/debug/recent-errors`（B022）足够
- ❌ **A/B test 不同 LLM provider** — 单人决策，不需多对比

## 6. 未来扩展（如果偏好改变）

如果未来你觉得想要更量化的视图（不是 SaaS-grade，但比手动周报更结构化）：

- **轻量 telemetry 表**（FastAPI middleware → SQLite `telemetry` 表）：记录每次 endpoint access / page view / AI 建议生成。所有数据本地不上云。批次预估 1 个 light batch
- **Reports 页 product metrics view**：基于 telemetry 表渲染图表（每周打开次数、AI 建议采纳率等）。批次预估 1-2 个 batch

**触发条件：** 用户在某次 review 时主动说"想看更结构化的指标"。**本 doc 不预设这些扩展为 backlog**；只 leave a hook。

## 7. Doc Lifecycle

- **当前状态：** **approved**（2026-05-25 用户批准）
- **生效信号：** 用户在做产品决策（如启动 / 跳过某 batch）时可引用本 doc §2 candidate checklist
- **修订流程：** 用户偏好改变（如想要自动 telemetry）时新 doc 替代；本 doc 改 status: superseded-by-<new>

---

> 配套：positioning §8 决策度量 + user-personas-and-journeys §8 决策度量 + roadmap 不画时间线（同样反 KPI 化倾向）
