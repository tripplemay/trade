# B004 Core Engineering Foundation Signoff 2026-05-12

> 状态：**Evaluator 验收通过**（progress.json status=done）
> 触发：B004 F007 独立审查工程基线与组合级风控边界文档一致性。

---

## 变更背景

B004 为 AI 量化交易系统 MVP 的核心工程基线与组合级风控边界文档批次。该批次在 B001 策略路线图、B002 数据/券商/环境规格、B003 MVP PRD 和独立策略审核报告基础上，定义 B005 实现前必须遵守的 Python 包结构、配置/环境、测试/fixture、no-live 安全、组合级资金分配、账户级风控和回测报告 schema。

---

## 变更功能清单

### F001：编写 B004 工程基线总规格

**Executor：** generator

**文件：**
- `docs/specs/B004-core-engineering-foundation-spec.md`

**验收结果：** PASS

### F002：定义 Python 包结构与模块边界

**Executor：** generator

**文件：**
- `docs/engineering/python-package-boundary.md`

**验收结果：** PASS

### F003：定义配置、环境与 no-live 安全策略

**Executor：** generator

**文件：**
- `docs/engineering/config-and-environment-policy.md`
- `docs/engineering/no-live-safety-guards.md`

**验收结果：** PASS

### F004：定义测试与 fixture 策略

**Executor：** generator

**文件：**
- `docs/engineering/testing-and-fixture-policy.md`

**验收结果：** PASS

### F005：定义组合级资金分配与账户级风控边界

**Executor：** generator

**文件：**
- `docs/strategy/00-master-portfolio-allocation.md`
- `docs/engineering/portfolio-allocation-boundary.md`

**验收结果：** PASS

### F006：定义回测报告 schema 与 B005 交接边界

**Executor：** generator

**文件：**
- `docs/engineering/backtest-report-schema.md`

**验收结果：** PASS

### F007：独立审查 B004 文档一致性

**Executor：** codex

**文件：**
- `docs/test-reports/B004-core-engineering-foundation-review-2026-05-12.md`
- `docs/test-reports/B004-core-engineering-foundation-signoff-2026-05-12.md`

**验收标准：**
- 确认 B004 文档与 B001/B002/B003/独立策略审核报告一致。
- 确认没有引入 live trading、真实 broker、外部 API 硬依赖、隐藏 secret 依赖或正式 frontend app 实现范围。

**验收结果：** PASS

---

## 未变更范围

| 事项 | 说明 |
|---|---|
| 产品实现代码 | 未创建或修改 `src/`、Python package scaffold、CI 配置、数据库 schema、migration 或部署配置。 |
| Broker / Live 操作 | 未连接真实券商，未使用 API key，未执行 paper/live broker 或真实资金测试。 |
| Frontend app | 未创建正式 frontend dashboard、React 或 Next.js app。 |
| 外部 API | 未执行真实数据供应商 API 调用，未引入 required CI 外部服务依赖。 |

---

## 预期影响

| 项目 | 改动前 | 改动后 |
|---|---|---|
| B004 验收状态 | F007 pending | F007 independent review PASS |
| B005 handoff | 工程边界待签收 | 可按 fixture/mock-first、no-live、JSON/Markdown report schema 进入 B005 |
| 风控边界 | 策略级文档为主 | 新增 master portfolio allocator、account-level drawdown kill switch 和 guard-test 要求 |

---

## 类型检查 / CI

```text
N/A - documentation-only evaluator review. No product code, test runner, CI config, frontend app, or build artifact was changed.
JSON validation executed for state-machine files after updates.
```

---

## L2 实测记录

| 项 | 证据 |
|---|---|
| Staging git_sha == main HEAD | N/A - documentation-only batch, no staging deployment impact. |
| 端到端流验证 | N/A - no executable product flow was introduced. |
| 关键 invariant | Documentation review confirmed no product code, no live trading, no real broker calls, no required external API/network/secrets, no formal frontend app, and no AI order/parameter authority. |
| 浏览器手动验 | N/A - no UI changes. |

---

## Ops 副作用记录

本批次无数据库 ops，无外部服务写入，无券商 API 调用，无真实资金操作。

---

## Harness 说明

本批次按 Harness 状态机完成独立 Evaluator 验收。`progress.json` 已设置为 `status: "done"`，signoff 路径已填入 `docs.signoff`。

---

## Soft-watch

| ID | 描述 | 风险等级 | 建议处置 |
|---|---|---|---|
| S1 | B004 guard requirements are documentation-only until B005 implements tests. | medium | B005 must include L1 no-live/no-secret/no-network/no-broker-call/AI no-buy guard tests. |
| S2 | Optional public data scripts are allowed later if scoped, but can become hidden API dependencies. | medium | Keep required CI fixture/mock-only and disable optional scripts by default. |
| S3 | `mypy` may be staged in B005. | low | If deferred, document the staged adoption plan in B005 spec. |

---

## Framework Learnings

本批次无 framework learnings。
