# MVP 完工声明 — 2026-05-20

> 触发：B023 (Workbench Phase 2 — Manual Execution UI) 签收完成
> 签收报告：`docs/test-reports/B023-workbench-phase2-signoff-2026-05-19.md`
> 完工范围：single-user manual-execution workbench，对应 PRD §10 / §11 / §12 全部成功指标 + 验收标准 + 里程碑。

## 1. 结论

**MVP substantively 完成。** 项目 B001-B023 全链路签收，完工范围严格落在 PRD 定义的 MVP 边界内（fixture-first、no-broker、no-live、no-paper-API、single-user、manual-execution）。

生产 workbench 位于 `https://trade.guangai.ai`，全部 12 页 + 6 表 + OAuth gating + 6 字段 health + daily backup + observability buffer 健康。Production HEAD = main HEAD = `d0ae21f`（v0.9.25 §Production/HEAD 等价性 规则强制）。

## 2. PRD §10 成功指标对照

| PRD §10 指标 | 实现批次 | 状态 |
|---|---|---|
| 工程基线可安装、可测试、CI 可运行 | B003-B004 | ✅ |
| 全球 ETF universe 可配置 | B005 | ✅ |
| 本地历史数据或 fixture 可加载 | B005 / B009 | ✅ |
| 数据质量检查可执行 | B009 | ✅ |
| ETF 动量信号可生成 | B006-B007 | ✅ |
| 月度回测可完成 | B005-B007 | ✅ |
| 绩效报告可生成 | B008 / B018 / B019 | ✅ |
| 回测可复现 | B009 snapshot + B019 retune | ✅ |
| 无真实 API key、无真实 broker、无真实资金依赖 | B012（BrokerAdapter ABC 永久 unwired）+ B021-B023 持续 enforced | ✅ |

## 3. PRD §11 验收标准对照

| PRD §11 验收标准 | 状态 | 证据 |
|---|---|---|
| B004 工程基线完成 | ✅ | B003-B004 签收 |
| B005 全球 ETF 回测 MVP 完成 | ✅ | B005-B007 签收 |
| 默认 CI 不依赖外部 API | ✅ | GitHub Actions 全 fixture-first；workbench-backend.yml/frontend.yml/deploy.yml 全绿 |
| 所有测试使用 fixture 或 mock | ✅ | 测试策略 `docs/dev/workbench-testing-strategy.md` 强制；Codex L1+L2 矩阵 |
| 报告明确数据源、参数和假设 | ✅ | B008/B018/B019 报告 schema 含 dataset_id / params / assumptions |
| 回测遵守 T 日信号、T+1 执行 | ✅ | B007 / B019 retune 持续 enforced |
| 策略不绕过风控 | ✅ | B011 master portfolio kill-switch + B023 F006 risk-panel real-time |
| 不存在 live trading 入口 | ✅ | B023 永久硬边界：no broker SDK / no execute buttons / Vitest grep + Playwright assert + L1 安全 regression |

## 4. PRD §12 里程碑对照

| PRD §12 里程碑 | 实际批次 | 状态 |
|---|---|---|
| B004 Core Engineering Foundation | B003-B004 | ✅ |
| B005 Global ETF Backtest MVP | B005-B007 | ✅ |
| B006 Risk Parity Backtest MVP | B010 + B019 retune | ✅ |
| B007 Portfolio Allocation and Risk | B011 | ✅ |
| B008 Paper Trading / Mock Broker | B012（BrokerAdapter ABC 永久 unwired，按用户决策永久 manual execution）| ✅ |
| B020 Workbench Dev Infrastructure | B020 | ✅ |
| B021 Workbench Cloud Deploy & Auth | B021 | ✅ |
| B022 Research Workbench (Phase 1) | B022 | ✅ |
| B023 Workbench Phase 2 (Manual Execution UI) | B023 | ✅（本批次完成）|

## 5. 项目实际批次链路（B001-B023）

| 批次 | 主题 | 签收 |
|---|---|---|
| B001 / B002 | 策略路线图 + 数据/broker 边界规划 | ✅ |
| B003 / B004 | 工程基线（Python pkg / CI / config / interface） | ✅ |
| B005 / B006 / B007 | Global ETF Backtest MVP（universe / 信号 / 回测 / 报告） | ✅ |
| B008 | 绩效 attribution + 报告 schema | ✅ |
| B009 | 数据 snapshot + 质量检查 | ✅ |
| B010 | Risk Parity Backtest MVP | ✅ |
| B011 | Master Portfolio + 多策略资金分配 + 账户级 kill-switch | ✅ |
| B012 | Paper Trading prep（BrokerAdapter ABC 永久 unwired）| ✅ |
| B013 / B015 / B016 | 策略 refinements（vol-target / cadence / universe） | ✅ |
| B017 / B018 | Cross-batch findings + P&L attribution | ✅ |
| B019 | Risk parity / master portfolio retune | ✅ |
| B020 | Workbench Dev Infrastructure | ✅ |
| B021 | Cloud Deploy + OAuth + SQLite + systemd + nginx + CI/CD + backup | ✅ |
| B022 | Workbench Phase 1（7 read-mostly 页 + 最小 write） | ✅ |
| B023 | Workbench Phase 2（5 execution workflow 页 + 3 表 + slippage analytics + risk panel） | ✅ |

## 6. 永久硬边界（MVP 完工后继续 enforced）

以下边界由 B012/B021/B022/B023 多批次 enforced，**MVP 完工后任何 post-MVP 批次必须继续遵守**：

- **No broker SDK**：无 ibapi / alpaca-py / interactive-brokers / tda-api 等 import；安全 regression 在 Codex L1 每次跑（禁 psycopg2/mysqlclient/pymongo/broker SDK）
- **No paper or live API URL**：源码内无 `paper-api.*` / `api.alpaca.*` / `api.tdameritrade.*` 字符串
- **No credential**：所有 secrets 走 GitHub vault → `/etc/workbench/workbench.env`，源码无凭证
- **No auto-execution**：任何按钮 labelled `execute` / `place order` / `send to broker` 禁（Vitest grep + Playwright assert L1 强制）
- **Single-user, no registration**：NextAuth 单 email allowlist；无注册 UI；无 multi-user 路径
- **No Cloud SQL / Postgres**：SQLite + persistent disk; daily GCS backup
- **Same-origin /api/*** (v0.9.24 #3)：前端无 `127.0.0.1:8723` 硬编码；build artifact regression 强制
- **Auth-gated**：所有 protected routes 通过 NextAuth middleware
- **Repository 读写非直 file**：DB 访问走 Repository pattern；不允许直接 file IO
- **Production HEAD 等价性** (v0.9.25)：每次 signoff 验证 `/api/health.version === git rev-parse HEAD`

## 7. Framework 资产（v0.9.21-v0.9.25）

MVP workbench 4 批次（B020-B023）共沉淀 **13 条 framework learnings**（v0.9.21-v0.9.25），全部归档到 `framework/archive/proposed-learnings-archive-v0.9.{21,22,23,24,25}.md`。

| 版本 | 主题 | 主要写入文件 |
|---|---|---|
| v0.9.21 | Fixture vs Real-Data Signal Reversal + Gap Attribution | engineering/testing-and-fixture-policy.md / role-context/evaluator.md / engineering/gap-attribution-methodology.md |
| v0.9.22 | Snapshot Tail Headroom for T+1 Execution + Non-Goals 解禁前端 | engineering/backtest-report-schema.md |
| v0.9.23 | Dev environment prerequisites + Python 编码 + GHA Node runtime | framework/harness/generator.md §9-11 |
| v0.9.24 | Cloud deploy 8 secrets + systemd/snap traps + Frontend SSR vs Browser context | framework/harness/planner.md + generator.md §12-13 |
| v0.9.25 | Cloud deploy hardening + Next.js dev rewrite parity + npm audit + FastAPI 观测 + Production/HEAD 等价性 | planner.md + generator.md §10/§12.5/§12.6/§14 + signoff-report.md 新 § |

B023 零新 framework learnings（signoff §Framework Learnings 明确「本批次无」）。框架版本停留 v0.9.25。

## 8. Post-MVP 路径

### 8.1 backlog 优先级

| ID | 优先级 | 主题 |
|---|---|---|
| **BL-B011-S2** | **high** | US Quality Momentum + HK-China ETF satellite 实现（两个独立 spec）|
| BL-B010-S1 | low | Risk parity 专用 fixture / workflow config |
| BL-B013-D1 | low | Smoothed / feedback volatility targeting |
| BL-B013-D2 | low | VIX-based tail risk overlay (ETN proxy) |
| BL-B023-S1 | low | 生产 recommendation-driven ticket 冒烟 |
| BL-B023-S2 | low | risk-panel kill-switch UI 演练 |

### 8.2 建议路线

1. **B024 = BL-B011-S2 拆解第一支 satellite**（US Quality Momentum 独立 spec 或 HK-China ETF 独立 spec，二选一先做）
2. 单 sleeve 接入 Master Portfolio → 跑 fixture backtest → 走 workbench Recommendations 验证可视化 → 签收
3. 第二支 satellite 同模式
4. 之后再讨论 BL-B013-D1 (smoothed vol) 或 BL-B013-D2 (VIX overlay) 等研究性 sleeve

### 8.3 仍要保留的非 MVP 边界

PRD §5 已划定的非 MVP 范围在 MVP 完工后仍然适用：
- 实际 broker API 接入（IBKR/Alpaca 等 live）
- 高频 / 衍生品策略
- 多用户 SaaS
- 外部资金委托
- AI 模型 fine-tune（仅用 inference for news/announcement 风控）

## 9. 致谢

MVP 完工是多 agent 协作的结果：
- **Claude CLI (Planner + Generator)**：23 批次需求拆解 + 全部代码实现 + 框架沉淀维护
- **Codex (Evaluator)**：23 批次测试设计 + 执行 + 签收报告 + 框架候选提案
- **用户**：方向决策 + 边界判断 + soft-watch 决议 + 框架候选裁决

---

> 本文档由 Planner 在 B023 done wrap-up 阶段写入。后续批次（B024+）属 post-MVP，归 satellite 实现路径。
