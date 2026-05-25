# Workbench Roadmap（2026-05-25）

> **状态：** **approved**（2026-05-25 用户批准）
> **配套：** `docs/product/positioning-2026-05.md`（产品定位 + 三层定义）+ `docs/product/user-personas-and-journeys-2026-05.md`（用户画像）
> **目的：** 把"3 件 critical 并行"具象化为可执行的批次依赖图与子批次拆分。**不画时间线（用户偏好）**，只画顺序与依赖。

---

## 1. 一句话目标

把 workbench 从 **Layer 0（synthetic prototype）** 推进到 **Layer 0.5（real data + AI-augmented advisory）**，包含：

1. **Real data ingest**（必先）— 让所有现有 sleeve 第一次有真实指标
2. **News / market context ingest**（real data 之后并行）— Home 页 daily engagement 内容源 + AI advisory 信息源
3. **AI advisory engine**（real data 之后与 news 并行）— LLM 接入 + prompt + cache + safety eval + 可引用建议
4. **Home 页 dashboard 重构**（前 3 件任一推进时可并行）— Robinhood-style + market context 整合
5. **UI 简化 Robinhood-style**（前 4 件任一推进时可并行）— Reports / Recommendations 改造
6. **UI synthetic-data banner**（轻量 lead-in 批次）— Layer 0 期间防误用

## 2. 约束（不变量）

- **永久硬边界 v0.9.28**（含 AI 5 子条；继承 positioning §6.1 + project-status.md §永久硬边界）
- **单用户**：永远不商业化、不多租户、不收费
- **手动 IBKR 实盘**：永远不连 broker / 不自动下单
- **Cost 预算 ¥500-2000/月**（2026-05-25 用户确认）— 含 Polygon Starter 等价（$30 USD ≈ ¥200）+ LLM API（¥500-1500）+ 可选 EODHD / 备用数据源
- **fixture-first 离线 CI**：CI 不连任何外部 API（real data 通过 snapshot 路径，AI 通过 mock provider）
- **不画时间线**（2026-05-25 用户偏好）— 只画依赖与顺序

## 3. 依赖图

```
                          ┌─────────────────────────────────┐
                          │ 0. UI synthetic-data banner    │
                          │ (轻量批次，无依赖，可立即做)    │
                          └─────────────────────────────────┘
                                        │
                                        │ 不阻塞，可独立完成
                                        │
                          ┌─────────────────────────────────┐
                          │ 1. Real data ingest             │
                          │ (必先；Layer 0→1 单一前置)      │
                          └─────────────────────────────────┘
                                        │
                          ┌─────────────┴──────────────┐
                          │                            │
                          ▼                            ▼
            ┌──────────────────────┐      ┌──────────────────────┐
            │ 2. News / market     │      │ 3. AI advisory engine│
            │    context ingest    │      │                      │
            └──────────────────────┘      └──────────────────────┘
                          │                            │
                          │  (News 接入后 AI advisory   │
                          │   可整合 news context)     │
                          └─────────────┬──────────────┘
                                        │
                                        ▼
                          ┌─────────────────────────────────┐
                          │ 4. Home 页 dashboard 重构        │
                          │ (整合 1+2+3 输出到主界面)        │
                          └─────────────────────────────────┘
                                        │
                                        │ 并行可做
                                        ▼
                          ┌─────────────────────────────────┐
                          │ 5. UI 简化 Robinhood-style       │
                          │ (Reports / Recommendations 改造) │
                          └─────────────────────────────────┘
```

**关键观察：**

- **Stream 0（UI banner）** 完全独立，可在任何阶段插入；建议作为 Layer 0 期间的第一个 lead-in 批次
- **Stream 1（Real data）** 是唯一的 hard prerequisite — 必须先完成，其他全部依赖它
- **Stream 2 + 3（News + AI）** 在 Stream 1 完成后可并行；初期 AI advisory 可用 fixture news 做原型验证（避免被 News 接入卡住）
- **Stream 4（Home 重构）** 整合前 3 件输出；最早能动手是 1 完成 + 2/3 有最小可用版本
- **Stream 5（UI 简化）** 与 Stream 4 平行；改 Reports / Recommendations 页样式，不依赖 real data 或 AI 的成熟度

## 4. 子批次拆分（每件 critical → N 个 batch）

### Stream 0 — UI synthetic-data banner（轻量 lead-in）

| Batch | 目标 | 输入 | 输出 |
|---|---|---|---|
| **B026?** | 在生产环境所有页面加持久 banner / footer 提示 "Research only with synthetic data"；双语；可关闭一次后下次仍显示（除非永久关闭按钮）| 当前 workbench；B024 i18n 模块 | 加 messages.synthetic_banner.* + Home / Reports / Recommendations 顶部 banner + Playwright 双 locale 测试 |

**预估：** ~1 个轻量 batch。可作为下一个批次直接做。

### Stream 1 — Real data ingest（核心前置）

| Batch | 目标 | 输入 | 输出 |
|---|---|---|---|
| **S1.A** | 数据源选型 + B009 snapshot 路径增强 | doc D（data-source-evaluation）approved | 选定数据源；snapshot 路径加 real provider adapter；CI 仍离线 |
| **S1.B** | 历史价格 snapshot（覆盖现有所有 sleeve universe）| S1.A | 历史日线 OHLCV 全量入库 fixture-shaped + point-in-time guard |
| **S1.C** | 基本面 snapshot（point-in-time 财报数据）| S1.B；可选付费数据源（如 EODHD / Polygon Fundamentals） | B025 us_quality_momentum + 未来 satellite 用真实财务数据替换合成 fixture |
| **S1.D** | 所有 sleeve 切换到真数据 + 回测重跑 + 指标对比 | S1.B + S1.C | Master + Momentum + RP + US Quality + (HK-China stub) 全部跑真数据；reports/ 新增对比报告 |

**预估：** 4 个 batch。可能因数据质量边界条件多再拆。

### Stream 2 — News / market context ingest

| Batch | 目标 | 输入 | 输出 |
|---|---|---|---|
| **S2.A** | News source 选型 + ingest 框架 | doc D（部分覆盖）；RSS / SEC EDGAR / 公开 API 评估 | 选定 news source（建议 SEC EDGAR + 1-2 公开 RSS）；workbench_api/news/ 模块；schema 落库 |
| **S2.B** | News 与现有 sleeve / ticker 关联（topic tagging / ticker mention extraction） | S2.A | News→ticker 反向索引；Recommendations 页可显示"影响本 sleeve 的近期 news" |
| **S2.C** | 宏观 / 行业 / 市场指数实时（或日级）摘要 | S2.A；Alpha Vantage / FRED / yfinance 公开端 | Home 页 market context 卡片（S&P / QQQ / 10y / VIX 等关键指标）|

**预估：** 3 个 batch。

### Stream 3 — AI advisory engine

| Batch | 目标 | 输入 | 输出 |
|---|---|---|---|
| **S3.A** | LLM provider 选型 + 接入 framework（prompt template + cache + cost guard） | doc C（llm-provider-evaluation）approved | LLM gateway 抽象（可切 Anthropic / OpenAI / Gemini） + cache + monthly budget guard + log all calls |
| **S3.B** | AI safety eval framework（红队 dataset + automated check） | doc F（ai-safety-evals）approved | 3 大 fail 型检测（收益预测 / 无引用 / 越界）+ pass/fail 阈值 + CI smoke 红队跑通 |
| **S3.C** | AI advisor MVP — 整合 quant signal + (fixture or real) news → 出文本建议含引用 | S3.A + S3.B；S1 部分完成 | Home 页 AI Advisor 段（原型可用 fixture news）；建议必带 quant_signal SHA + news URL 引用 |
| **S3.D** | AI 解释层（Sharpe / Sortino 等 tooltip + Reports 解释 + 双语 summarize） | S3.A | UI tooltip + Reports 页"为什么这个数字重要"的 LLM 文案；UI 改造可与 Stream 5 协调 |

**预估：** 4 个 batch。

### Stream 4 — Home 页 dashboard 重构

| Batch | 目标 | 输入 | 输出 |
|---|---|---|---|
| **S4.A** | Home 页架构改造（NAV + Day P&L + 4 sleeve breakdown 块） | S1 已切真数据；现有 UI 形态 | 新 Home page；保留旧 Home 入口为 /admin/legacy-home 直到验证稳定 |
| **S4.B** | Home 整合 market context（来自 S2.C） | S2.C + S4.A | Home 页第三段：market 指标卡片 |
| **S4.C** | Home 整合 AI Advisor（来自 S3.C） | S3.C + S4.A | Home 页第二段：AI 一句话建议 + 引用 + disclaimer |

**预估：** 3 个 batch。

### Stream 5 — UI 简化 Robinhood-style

| Batch | 目标 | 输入 | 输出 |
|---|---|---|---|
| **S5.A** | Reports 页 Robinhood-style 重构（大数字 + 颜色 + tooltip） | S3.D 可用时建议联动；不依赖 real data | 单 sleeve / Master 回测报告页改 UI 风格；专业术语保留英文 + 中文 tooltip |
| **S5.B** | Recommendations 页 Robinhood-style 重构 | 同上 | target positions table → simplified card + "为什么这样建议"（联动 S3.D）|
| **S5.C** | Risk panel 微调（已较简化） | 现有 | drawdown / kill-switch indicator 颜色 / 字体一致化 |

**预估：** 3 个 batch。

## 5. 实际启动顺序建议

按依赖图，**第一个推荐启动的批次 = B026 Stream 0 UI banner**（独立、轻量、立即降低误用风险，且可在做 doc D 时穿插）。

实际启动路径：

```
B026 (Stream 0 banner)
  │
  └─→ docs/product/data-source-evaluation-2026-05.md (doc D)
       │
       └─→ B027 = Stream 1.A real data 选型 + snapshot 框架
             │
             ├─→ B028 = Stream 1.B 历史价格 snapshot
             │     │
             │     └─→ B029 / B030 Stream 1.C + Stream 1.D 完成 Layer 0→1
             │
             └─→ (并行) docs/product/llm-provider-evaluation-2026-05.md (doc C)
                  │
                  └─→ docs/product/ai-safety-evals-2026-05.md (doc F)
                       │
                       └─→ Stream 3 AI advisor batches 启动
                            │
                            └─→ (与 Stream 2 News 平行) Stream 4 Home 重构
```

## 6. 已退场或推迟的 backlog（来自 positioning §7）

- **BL-B011-S2 HK-China satellite**：仍是 fixture；等 Stream 1 完成 + Stream 2 News 框架成型后再启动（可能 B032+）
- **BL-B010-S1 risk parity 专用 fixture**：Stream 1 后自然过时，**不再做**
- **BL-B013-D1 / BL-B013-D2 vol-target / VIX overlay**：保持 low，等 Stream 1 后再评估
- **BL-B023-S1 / BL-B023-S2 生产冒烟**：保持 low，环境就绪后做

## 7. Roadmap 演进规则

- **不画时间线**（用户偏好；2026-05-25 确认）。本 doc 不写"Q1 / Q2 / Y-end"等月份估时
- **依赖顺序固定**：Stream 1 必先；Stream 0 可任何时间插入
- **Stream 2 / 3 可并行**：建议 Stream 3 先以 fixture news 做原型（不阻塞）
- **每个 batch 启动时仍按 spec-driven 流程**：planner 写 spec + 用户批准 + features.json + status 流转
- **重大方向变更（如 AI 边界放宽 / 商业化 / 多用户）需重新画 roadmap**：本 doc 修订为 superseded-by-<new-roadmap-name>

## 8. Doc Lifecycle

- **当前状态：** **approved**（2026-05-25 用户批准）
- **生效信号：** 后续所有批次 spec 第一节必须引用本 roadmap 的所在 Stream（如 "本批次属 Stream 1.B"）
- **修订流程：** 同 positioning-2026-05.md / user-personas-and-journeys-2026-05.md

---

> 配套：
> - `docs/product/positioning-2026-05.md`（一句话定位 + 4 层定义 + AI 角色与边界）
> - `docs/product/user-personas-and-journeys-2026-05.md`（用户画像 + Daily Journey + UI 优先级）
> - 待写：`docs/product/llm-provider-evaluation-2026-05.md`（Stream 3.A 前置）
> - 待写：`docs/product/data-source-evaluation-2026-05.md`（Stream 1.A 前置）
> - 待写：`docs/product/ai-safety-evals-2026-05.md`（Stream 3.B 前置）
> - 待写：`docs/product/success-metrics-2026-05.md`（长期演进依据）
