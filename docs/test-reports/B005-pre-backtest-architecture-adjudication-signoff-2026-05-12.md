# B005 Pre-Backtest Architecture Adjudication Signoff 2026-05-12

> 状态：**Evaluator 验收通过**（progress.json status=done）
> 触发：B005 F006 独立审查架构裁决与 B001-B004 及两份独立分析报告的一致性。

---

## 变更背景

B005 在 Global ETF Backtest MVP 实现前吸收独立 PRD/架构审计意见，将 Portfolio Manager、T+1 Open 默认成交假设、PIT 财务数据降级、Tax-lot/OMS 边界和 AI filing prefilter 规则固化为 B006 前置约束。

---

## 变更功能清单

### F001：裁决 Portfolio Manager 架构边界

**Executor：** generator

**文件：**
- `docs/specs/B005-pre-backtest-architecture-adjudication-spec.md`
- `docs/engineering/python-package-boundary.md`
- `docs/engineering/portfolio-allocation-boundary.md`

**验收结果：** PASS

### F002：裁决 B006 回测成交价格假设

**Executor：** generator

**文件：**
- `docs/specs/B005-pre-backtest-architecture-adjudication-spec.md`
- `docs/engineering/backtest-report-schema.md`

**验收结果：** PASS

### F003：裁决 PIT 财务数据与多因子降级策略

**Executor：** generator

**文件：**
- `docs/engineering/pit-data-degradation-policy.md`

**验收结果：** PASS

### F004：补充 Tax-lot 与 OMS 边界

**Executor：** generator

**文件：**
- `docs/engineering/oms-tax-lot-boundary.md`

**验收结果：** PASS

### F005：补充 AI filing prefilter 架构规则

**Executor：** generator

**文件：**
- `docs/engineering/ai-filing-prefilter-policy.md`

**验收结果：** PASS

### F006：独立审查 B005 架构裁决一致性

**Executor：** codex

**文件：**
- `docs/test-reports/B005-pre-backtest-architecture-adjudication-review-2026-05-12.md`
- `docs/test-reports/B005-pre-backtest-architecture-adjudication-signoff-2026-05-12.md`

**验收标准：**
- 确认 B005 裁决与 B001-B004、两份独立分析报告一致。
- 确认没有引入 live trading、真实 broker、外部 API 硬依赖、正式前端或实盘税务建议。

**验收结果：** PASS

---

## 未变更范围

| 事项 | 说明 |
|---|---|
| 产品实现代码 | 未创建或修改 `src/`、Python package scaffold、CI 配置、数据库 schema、migration 或部署配置。 |
| Broker / Live 操作 | 未连接真实券商，未使用 API key，未执行 paper/live broker 或真实资金测试。 |
| Frontend app | 未创建正式 frontend dashboard、React 或 Next.js app。 |
| 外部 API | 未执行真实数据供应商 API 调用，未引入 required CI 外部服务依赖。 |
| 税务建议 | 仅保留 tax-lot/OMS 接口边界，不提供实盘税务建议或税务优化实现。 |

---

## 预期影响

| 项目 | 改动前 | 改动后 |
|---|---|---|
| B005 验收状态 | F006 pending | F006 independent review PASS |
| B006 回测约束 | B006 尚未实现 | 必须 fixture/mock-first、T+1 Open 默认成交、PM-compatible output、no-live/no-secret/no-network |
| 架构裁决 | 审计建议待吸收 | 已固化 PM、PIT 降级、tax-lot/OMS、AI prefilter 边界 |

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
| 关键 invariant | Documentation review confirmed no product code, no live trading, no real broker calls, no required external API/network/secrets, no formal frontend app, and no tax advice. |
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
| S1 | B006 是首个实现批次，必须把 B005 文档约束转成可执行 L1 guard tests。 | high | B006 acceptance 明确 no-live/no-secret/no-network/no-broker-call、T+1 Open 和 PM-compatible output 测试。 |
| S2 | 缺失 T+1 open 时的 fallback 规则尚未实现。 | medium | B006 定义确定性 fallback 并在报告中显式标记。 |
| S3 | PIT 降级规则允许探索性非 PIT 基本面，后续可能被误读。 | medium | 因子批次报告必须强制显示 PIT/degraded 状态；B006 避免 fundamentals。 |

---

## Framework Learnings

本批次无 framework learnings。
