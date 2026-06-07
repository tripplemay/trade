# Implementation Path（2026-05-25）

> **状态：** **approved**（2026-05-25 用户批准）
> **目的：** 给未来其他 planner（可能未参与本次会话）一份**实施层路径地图**，从 roadmap stream-level 依赖图翻译为可顺序启动的 batch 序列，附 phase 划分、依赖关系、关键决策点与接续 checklist。
> **角色：** 本 doc 不替代每个 batch 自己的 spec；只列骨架 + acceptance 方向 + 引用 docs。新 planner 启动某个 batch 时，仍需起 spec、走 Planner done 阶段的需求拆解流程。

---

## 1. 用途与读法

**未来 planner 接手时的读法（推荐顺序）：**

1. 先读 `harness-rules.md`（项目根，状态机规则）+ `framework/STRUCTURE.md`（目录语义）
2. 读 `.auto-memory/MEMORY.md` → `project-status.md` → `environment.md`（T0 必读）
3. 读对应角色 `.auto-memory/role-context/planner.md`（T1）
4. **读本 doc 找到下一个该做的 batch**
5. 顺藤摸瓜读引用的 product docs（5 份 approved doc）
6. 起 spec → 与用户对齐 → features.json → status 流转

**本 doc 不替代什么：**

- 不替代 `roadmap-2026-05.md`（stream 级依赖图）
- 不替代每个 batch 自己的 `docs/specs/B0XX-*.md`
- 不替代 framework/harness/ 规则知识库

## 2. 当前位置（B025 done 之后 — 2026-05-25）

| 项 | 值 |
|---|---|
| B001-B025 状态 | 全部签收 |
| Production | `https://trade.guangai.ai` live with B024 双语 + B023 manual execution + B025 US Quality satellite（fixture 数据）|
| Framework | v0.9.28（含 AI 5 子条边界 / 结构澄清 / chore-deploy / Playwright lsof / signoff post-deploy）|
| Workbench Layer | **Layer 0**（synthetic prototype）— 所有 sleeve / 回测 / Recommendations / Risk Panel 基于 fixture data |
| 产品 docs | 5 份 approved（positioning / personas / roadmap / LLM eval / data source eval / AI safety evals / success metrics）|

## 3. 目标（Layer 0.5 完整交付）

> **AI-augmented personal portfolio decision support tool, built on a quant-strategy chassis.**

完成 Layer 0.5 后用户每日打开 workbench 看到：

- 真实总 NAV + Day P&L + 状态灯（Layer 1 real data 支撑）
- AI Advisor 一句话建议 + 引用（Layer 1.5 AI advisory）+ 永无收益预测数字
- 市场 / 行业 / 宏观新闻聚合（Stream 2）
- 4 sleeve breakdown 基于真数据（Stream 1 完成）
- Reports / Recommendations 走 Robinhood-style 简化呈现（Stream 5）
- **用户交易闭环可用（2026-06-07 用户拍板新增）**：真实评分 → 真实 target vs current diff → order ticket（系统出"指示"）→ 用户手动 IBKR 下单 → fills → reconcile → journal 端到端跑通（B023 框架 + 真实评分喂入）。系统全程不下单、不连券商。

参见 `docs/product/positioning-2026-05.md` §1 / `user-personas-and-journeys-2026-05.md` §2 Daily Journey + §3 Quarterly Journey / `docs/product/progress-review-2026-06.md`（里程碑 C 重定义 + 交易闭环剩余工作序列）。

## 4. 4 Phase 划分

### Phase 0 — Lead-in 防误用（1 batch，独立可立即启动）

**目标：** 在 Layer 0 期间防止用户 / 你 / 任何看到 workbench 的人误把 synthetic data 数字当作真实投资依据。
**关键里程碑：** 防误用 banner 上线，UI 显式标注 "research only with synthetic data"。

| Batch | Stream | 关键 acceptance 骨架 | 依赖 doc |
|---|---|---|---|
| **B026** | Stream 0 | 持久 banner / footer 在 Home / Reports / Recommendations / Risk / Strategies 顶部；双语（继承 B024 i18n）；不可一次性关闭（仅本会话隐藏）；Playwright 双 locale 覆盖；可通过 messages bundle 灵活更新文案 | positioning §1 / user-personas §7 UI 优先级 / framework B024 i18n §15 |

**Phase 0 完成后：** UI 误用风险降到底。可与 Phase 1 同时启动（Phase 1 不依赖 Phase 0）。

### Phase 1 — Real Data 落地（4 batch，严格顺序内部）

**目标：** 让所有现有 sleeve（Master Portfolio 4 sleeve + B025 US Quality）从 fixture 切换到真实历史价格 + 真实 point-in-time 财务数据。
**关键里程碑 A：** Layer 0→1 达成。回测指标第一次有真实意义；Master target weights 可信。

| Batch | Stream | 关键 acceptance 骨架 | 依赖 doc |
|---|---|---|---|
| **B027** | S1.A | Polygon.io Starter $30/月 接入 + `trade/data/polygon_loader.py` Repository；B009 snapshot 路径增强（双层存储 raw + unified fixture-shaped）；CI 仍离线；PIT enforcement at loader layer；cost guard | data-source-evaluation §6.1 / §7 / §9 |
| **B028** | S1.B | 历史价格 backfill 10+ 年覆盖 Master 4 sleeve 全部 ticker + B025 us_quality_momentum 30-50 ticker + US-listed ADR proxy（FXI / KWEB / BABA 等）；行数 / 跨度 / cross-check yfinance 抽样验证；每日 EOD 增量 cron（生产 VM，CI 不跑）| data-source §6.1 / §7.2 / §10 |
| **B029** | S1.C | 财务 snapshot：首选 SEC EDGAR 自 parse XBRL（免费 + 最严 PIT），降级条件触发时切 Polygon Fundamentals（已含 Starter）或 EODHD $30-100；fixture schema 与 B025 `data/fixtures/us_quality_momentum/fundamentals.csv` 一致；report_date ≥ fiscal_quarter_end + 30d enforcement | data-source §4 / §6.2 |
| **B030** | S1.D | Master + Momentum + RP + US Quality 全部 sleeve 切真数据；既有 fixture 测试保留作 baseline；新增 fixture vs real 对比报告；既有 backtest 断言（如 B025 "年化 [5%,25%] / Sharpe [0.3,1.5] / MDD<50%"）从范围断言改为 "real run + sanity range"；reports/ 加新文件 | positioning §6.1 PIT / B025 §4.1 fixture schema 复用 |

**Phase 1 完成后里程碑 A：** Layer 0→1 达成。可启动 Phase 2 + Phase 3。

### Phase 2 — AI + News 引擎（6 batch，部分并行）

**目标：** LLM gateway 基础设施 + News ingest + AI advisor MVP。
**关键里程碑 B：** AI advisory 框架可用。AI 给的建议必带引用 + 永无收益预测数字 + Safety eval CI gate 兜底。

| Batch | Stream | 关键 acceptance 骨架 | 依赖 doc |
|---|---|---|---|
| **B031** | S3.A | aigc-gateway 接入：`workbench_api/llm/gateway.py` 抽象层 + provider routing（Sonnet 主力 / Haiku 高频 / Flash news / Opus quarterly）+ cost guard（月 ¥1500 cap → fallback Haiku）+ Anthropic prompt caching + log 全请求；不直接 import provider SDK；CI 用 mock provider | llm-provider-evaluation §3 / §5 / §6 / §7 / §8 |
| **B032** | S3.B | Safety eval framework：`data/safety-evals/red-team-dataset.jsonl` 15 样本（α 收益预测 / β 无引用 / γ 越界各 5）+ Sonnet judge prompt + `tests/safety/test_ai_advisor_red_team.py` pytest gate + CI workflow `.github/workflows/ai-safety-eval.yml`；100% 拦截才 deploy | ai-safety-evals §2 §3 §4 §5 |
| **B033** | S2.A | News ingest 框架：`workbench_api/news/` 模块 + 首批 source SEC EDGAR filings + Yahoo Finance RSS + FRED；schema 落库；CI 用 fixture news；不调外部 API | roadmap Stream 2 / data-source §5 简提 |
| **B034** | S2.B | News ↔ ticker / sleeve 关联：Cohere multilingual embedding 接入 aigc-gateway；topic tagging + ticker mention extraction；Recommendations 页可显示 "影响本 sleeve 的近期 news" | llm-provider §4 embedding 选型 / ai-safety §2 (β) 无引用样本测试 |
| **B035** | S2.C | Market context：FRED 宏观（10y / VIX / CPI）+ Alpha Vantage free 指数（SPY / QQQ / DXY）拉取 + 每日更新；Home 页 market context 卡片 数据源 | data-source §5 |
| **B036** | S3.C | AI advisor MVP：整合 quant signal + real data + news → 文本建议含 quant_signal_sha + news_urls 引用；JSON schema 输出；Home 页 AI Advisor 段呈现；INSUFFICIENT_GROUNDING fallback；通过 Stream 3.B 全部 15 红队样本 | positioning §1.1 / ai-safety §3 §4 §6 / roadmap S3.C |

**Phase 2 完成后里程碑 B：** AI advisory 框架可用。生产环境 AI 给的建议可信度有 CI gate 兜底。

**Phase 2 并行可能性：**
- B031 + B033 完全独立（LLM gateway 与 news 框架可同期）
- B032 依赖 B031
- B034 依赖 B033 + B031（需要 embedding）
- B035 独立于 B031-B034
- B036 依赖 B031 + B032 + 部分 B033/B034/B035（fixture news 可代替）

### Phase 3 — Home + UI 重构（7 batch，部分并行）

**目标：** Home 页 daily-engagement 中心 + Reports / Recommendations / Risk Panel 走 Robinhood-style 简化。
**关键里程碑 C：** Layer 0.5 完整交付。每日 Home 高频可用 + UI 简化让用户看 quant 数字不再迷茫。

| Batch | Stream | 关键 acceptance 骨架 | 依赖 doc |
|---|---|---|---|
| **B037** | S4.A | Home 页架构改造：NAV + Day P&L + 4 sleeve breakdown 三段；保留旧 Home 入口为 `/admin/legacy-home` 直到稳定；双语 + Playwright | user-personas §2 Daily Journey mockup |
| **B038** | S4.B | Home 整合 market context（来自 B035）：Home 第三段渲染 market 指标卡片 | user-personas §2 / roadmap S4.B |
| **B039** | S4.C | Home 整合 AI Advisor（来自 B036）：Home 第二段渲染 AI 一句话建议 + 引用 + disclaimer；INSUFFICIENT_GROUNDING 时段位置保留但内容降级 | user-personas §2 / ai-safety §6 fallback UI |
| **B040** | S5.A | Reports 页 Robinhood-style 重构：单 sleeve / Master 回测报告页大数字 + 颜色编码 + tooltip；专业术语保留英文 + 中文 tooltip 解释（Sharpe / Sortino / Calmar / MDD 等）；不破 Markdown 报告本身 | positioning §1.1 / user-personas §7 UI 优先级 |
| **B041** | S5.B | Recommendations 页 Robinhood-style 重构：target positions table → simplified card + "为什么这样建议"（联动 B043 AI 解释层）；保留专业 view toggle | user-personas §7 |
| **B042** | S5.C | Risk Panel 微调：drawdown / kill-switch indicator 颜色 + 字体一致化；专业术语 tooltip | user-personas §7 |
| **B043** | S3.D | AI 解释层：Sharpe / Sortino / 因子贡献 等数字的 LLM tooltip 文案（一次性生成 + cache）；Reports 页 "为什么这个数字重要" 段；双语 summarize；与 B040 / B041 联动 | positioning §1.1 / llm-provider §5.2 路由 / ai-safety §2 (α) 不含预测数字样本 |

**Phase 3 并行可能性：**
- B037 必先（其他 Home 整合 batch 依赖）
- B038 / B039 依赖 B037 + 各自上游（B035 / B036）
- B040 / B041 / B042 / B043 互相独立，依赖 Phase 2 完成
- B043 与 B040 / B041 联动协调（tooltip 文案同期）

**Phase 3 完成后里程碑 C：** Layer 0.5 完整交付。用户每日 Home 0-5 秒扫一眼放心；季度调仓时 AI 帮解释；Reports 不再让用户迷茫。

### Phase 4 — Long-tail backlog（按需做）

**目标：** 完成 Layer 0.5 后续 marginal value 功能；由用户真实使用反馈驱动。

| Batch（id 待定）| 描述 | 触发条件 |
|---|---|---|
| HK-China satellite (BL-B011-S2 剩余) | 用 US-listed ADR/ETF proxy 实现 HK-China sleeve 从 stub → implemented；类似 B025 模式 | Layer 0.5 完成 + 用户主动想扩 satellite |
| Smoothed vol-target (BL-B013-D1) | proportional-control / variational smoothing vol-targeting 替代 open-loop | 用户读完文献 + 主动想做 |
| VIX tail risk overlay (BL-B013-D2) | VIXY / VXX ETF proxy 做 tail risk overlay 研究 | 用户主动 + 2020 / 2022 stress window 想验证 |
| B023 prod recommendation 冒烟 (BL-B023-S1) | 非 defensive 路径 prod 端到端冒烟 | operator 例行演练前 |
| Risk-panel red 演练 (BL-B023-S2) | 准备 staging 风险样本演练 red banner UI | 用户主动 |
| Runtime AI safety check（Stream 3.E） | 在 prod runtime 加 AI 输出实时 safety check | AI advisor MVP 上线后若发现违反边界 ≥3 次 / 月 |
| 轻量 telemetry 表 | 本地 SQLite 自动采集打开次数 / Home 停留 / AI 采纳率 | 用户主动说"想看更结构化指标"（参见 success-metrics §6）|

**永不到达：** Layer 3 live trading（broker SDK 接入 + 自动下单）— 永久边界 v0.9.21-v0.9.28。

## 5. 关键依赖图（线性化版本）

```
B026 (Phase 0 banner) ──── 独立可立即做
                                              │
B027 → B028 → B029 → B030 (Phase 1 Real Data，严格顺序)
                                              │  🎯 里程碑 A
                       ┌──────────────────────┼─────────────────────┐
                       │                                            │
                B031 → B032          B033 → B034              B035
              (LLM gateway        (News ingest +              (Market
               + safety eval)      embedding)                  context)
                       │                  │                       │
                       └──────────────────┼───────────────────────┘
                                          ▼
                                     B036 (AI advisor MVP)
                                          │  🎯 里程碑 B
                       ┌──────────────────┼─────────────────────┐
                       │                  │                     │
                B037 (Home 架构)    B040 (Reports UI)      B043 (AI 解释)
                       │                  │                     │
                B038 (Home market)  B041 (Rec UI)
                       │                  │
                B039 (Home AI)      B042 (Risk Panel)
                       │
                       ▼  🎯 里程碑 C: Layer 0.5 完整交付
                       │
                Phase 4 backlog（按需做）
```

## 6. 关键里程碑速览

| 里程碑 | 完成条件 | 价值释放 | 触发的下游 |
|---|---|---|---|
| **A — Layer 0→1** | Phase 1 全 4 batch；全 sleeve 真数据**进回测** | 回测指标第一次可信（注：真实评分进**线上推荐**归里程碑 C，见 progress-review §4）| 可启动 Phase 2 + Phase 3 |
| **B — AI advisory 框架** | Phase 2 全 6 batch；AI MVP + safety eval | AI 建议必带引用 + 永无预测数字 + CI gate | 可整合到 Home（B039）|
| **C — Layer 0.5 完整交付（2026-06-07 重定义）** | Phase 3 UI（B037-B043）+ **真实评分基础（B044/B045/B046）** + **交易安全/风控/合规层真实化（B048 F011 根因：kill-switch/risk-panel/wash-sale 去占位）** + **用户交易闭环端到端可用（真实评分+真实安全层→mark-to-market diff→ticket→fills→reconcile→journal，BL-B023-S1 生产冒烟）** + **HK-China 实现（BL-B011-S2，Master 4/4 真实）** + **回测页接真实引擎（B047，去合成 stub）** | 每日 Home 高频可用 + UI 简化 + **可按系统指示手动交易（含真实风控）** + 回测可信 | 进入 Phase 4 长尾按需 |

## 7. 永久边界（贯穿全程，继承 framework v0.9.28）

继承 `framework/harness/planner.md` §"产品 / Cloud / i18n / AI 边界" 全集：

- **系统层：** no-broker SDK / no live URL / no credential / no auto-execution / 多用户禁 / Cloud SQL 禁 / same-origin `/api/*` / auth-gated / Repository pattern
- **UI 层：** no-execution buttons（含中文禁词 v0.9.26）/ Order ticket Markdown 双语 disclaimer 永存
- **数据 / CI 层：** fixture-first 离线 CI / cloud-deploy 批次 workflow_dispatch + chore-commit dispatch（v0.9.27）
- **AI 边界 5 子条（v0.9.28）：**
  - (a) no AI auto-execution
  - (b) no AI 收益预测数字输出
  - (c) no AI 替代 quant 评分作为唯一决策依据
  - (d) AI 输出必须基于 quant signal + real data + 可引用 news
  - (e) AI 做解释 / summarize / translate / context aggregation 允许
- **预算：** ¥500-2000/月（Polygon ¥200 + LLM ¥500-1500 + 可选 EODHD ¥200-700）
- **产品边界：** 永不商业化 / 永不多用户 / 永不替决策 / 全资产范围

## 8. Planner 接续 Checklist（启动每个 batch 前必读）

**所有 batch 共有：**

- [ ] `harness-rules.md`（项目根，状态机规则）
- [ ] `framework/STRUCTURE.md`（目录语义）
- [ ] `.auto-memory/MEMORY.md` + `project-status.md` + `environment.md`（T0）
- [ ] `.auto-memory/role-context/planner.md`（T1 active 行为规范）
- [ ] `framework/harness/planner.md` §当前批次涉及的章节（按需查阅；不是 always-loaded）
- [ ] 本 doc 找到下一个 batch + 引用的具体 product docs
- [ ] `progress.json` + `features.json` + `backlog.json`（确认状态）
- [ ] `docs/test-reports/user_report/`（有无新反馈）

**按 batch 类型差异化：**

| Batch 类型 | 额外必读 |
|---|---|
| 含数据接入（Phase 1）| `data-source-evaluation-2026-05.md` 全文 |
| 含 LLM 调用（Phase 2 / B043）| `llm-provider-evaluation-2026-05.md` + `ai-safety-evals-2026-05.md` 全文 |
| 含 UI 改造（Phase 0 / 3）| `user-personas-and-journeys-2026-05.md` §2 Daily Journey + §7 UI 优先级 + `positioning-2026-05.md` §1.1 AI 角色 |
| Cloud 部署相关 | `framework/harness/generator.md` §12（部署）+ §12.7 workflow_dispatch + `framework/templates/signoff-report.md` §Post-signoff Deploy |

## 9. 每个 batch spec 撰写要点

无论哪个 batch，spec 第一节必含：

1. **本批次所在 phase + stream**（如 "本批次属 Phase 2 / Stream 3.A LLM gateway"）
2. **依赖的前置 batch**（如 "依赖 B027-B030 Phase 1 已完成；不依赖 Phase 2 其他 batch"）
3. **本批次后续解锁的 batch**（如 "完成后解锁 B032 safety eval + B036 AI advisor MVP"）
4. **永久硬边界继承段**（继承 framework v0.9.28 + 本 phase 特有约束）
5. **引用的 product docs**（具体到章节）

## 10. 异常处理

**如果某个 batch 进入 fix-round ≥4 轮（参考 B025 教训）：**

- 触发 framework v0.9.27 §12.7 chore-deploy 检查
- 触发 framework v0.9.27 §20 lsof 检查
- 由 planner 在 reverifying 阶段裁决：是否拆分 batch / 是否升级到 framework 沉淀

**如果 cost / data source / LLM provider 出现重大变化：**

- 暂停启动 batch；启动 product doc 修订流程（如 `llm-provider-evaluation-2026-08.md` 替代当前 `-2026-05.md` 版本）
- 修订完成后重 review 本 doc 引用是否需要更新

**如果用户在某次 review 改变产品方向：**

- 暂停所有未启动 batch
- 启动新一轮 positioning doc 修订
- 本 doc 改 status: superseded-by-<new-implementation-path-doc>

## 11. Doc Lifecycle

- **当前状态：** **approved**（2026-05-25 用户批准）
- **生效信号：** 后续所有 batch spec 第一节必须引用本 doc §4 当前批次所在 phase + stream（如 "本批次属 Phase 1 / B028 / Stream 1.B"）
- **修订流程：**
  - 小修订（如 batch 顺序微调 / 新增 long-tail backlog 条目）：直接 commit
  - 中修订（如某 phase 完成后下游 batch 拆分调整）：commit + 在 §11 加 changelog 条目
  - 大修订（如产品方向变更 / framework 大版本变更 / AI 边界放宽）：新 doc 替代，本 doc 改 status: superseded-by-<new>

## 12. 引用 docs 索引（一次性全收）

| Doc | 文件路径 | 用途 |
|---|---|---|
| Positioning | `docs/product/positioning-2026-05.md` | 一句话定位 + 4 层定义 + AI 角色与边界 + backlog 重排 |
| User Personas & Journeys | `docs/product/user-personas-and-journeys-2026-05.md` | Daily Journey + UI 优先级 + Anti-Journeys |
| Roadmap | `docs/product/roadmap-2026-05.md` | Stream 0-5 依赖图 + 子批次拆分（stream level）|
| LLM Provider Evaluation | `docs/product/llm-provider-evaluation-2026-05.md` | aigc-gateway / model routing / embedding / cost |
| Data Source Evaluation | `docs/product/data-source-evaluation-2026-05.md` | Polygon / SEC EDGAR / 双层存储 / PIT |
| AI Safety Evals | `docs/product/ai-safety-evals-2026-05.md` | 红队 dataset / LLM judge / fallback |
| Success Metrics | `docs/product/success-metrics-2026-05.md` | 手动周报 / 触发型 review |
| **Implementation Path（本 doc）** | `docs/product/implementation-path-2026-05.md` | **Phase / Batch 序列 + Planner 接续 checklist** |
| Framework STRUCTURE | `framework/STRUCTURE.md` | framework/ 目录语义 + 加载流 |
| Framework Planner role | `framework/harness/planner.md` | Planner 角色规则（含 AI 边界精细化 v0.9.28）|
| Framework Generator role | `framework/harness/generator.md` | Generator 角色规则 |
| Framework Evaluator role | `framework/harness/evaluator.md` | Evaluator 角色规则 |

---

> 本 doc 的"未来 planner"包括：(a) 同一 Claude CLI agent 在新会话；(b) 其他 Claude CLI agent；(c) 任何接续本项目的工程师 / agent。
> 撰写假设：读者**没有**经历本次 B025 done 阶段会话；读者**有**完整 framework v0.9.28 + 5 份 product docs 上下文。
