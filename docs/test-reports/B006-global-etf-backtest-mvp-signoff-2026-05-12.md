# B006 Global ETF Backtest MVP Signoff 2026-05-12

> 状态：**Evaluator 验收通过**（progress.json status=done）
> 触发：B006 F008 独立验收 Global ETF Backtest MVP。

---

## 变更背景

B006 是首个实现批次，目标是在 B001-B005 已签收的策略、数据、PRD、工程基线和架构裁决基础上，实现 fixture/mock-first 的 Global ETF Momentum 回测 MVP。Evaluator 本次执行 L1 本地验收，验证 Python 工具链、fixture workflow、T+1 Open 回测、报告 schema 和安全 guard tests。

---

## 变更功能清单

### F001：创建 Python package 骨架与 CI 工具链

**Executor：** generator

**验收结果：** PASS

### F002：实现 fixture 数据加载与 snapshot metadata

**Executor：** generator

**验收结果：** PASS

### F003：实现 Global ETF Momentum 信号生成

**Executor：** generator

**验收结果：** PASS

### F004：实现月度回测引擎与 T+1 Open 成交

**Executor：** generator

**验收结果：** PASS

### F005：实现基础风险检查与 PM-compatible 输出

**Executor：** generator

**验收结果：** PASS

### F006：实现 JSON/Markdown 回测报告

**Executor：** generator

**验收结果：** PASS

### F007：实现 Python workflow E2E 与安全 guard tests

**Executor：** generator

**验收结果：** PASS

### F008：独立验收 B006 Global ETF Backtest MVP

**Executor：** codex

**文件：**
- `docs/test-reports/B006-global-etf-backtest-mvp-review-2026-05-12.md`
- `docs/test-reports/B006-global-etf-backtest-mvp-signoff-2026-05-12.md`

**验收标准：**
- Evaluator 在 localhost/CI-safe 环境执行 L1 验收。
- 确认 pytest、ruff、compileall、mypy、fixture workflow E2E、T+1 Open、report schema、no-live/no-secret/no-network guards 均符合 B001-B005 约束。

**验收结果：** PASS

---

## 未变更范围

| 事项 | 说明 |
|---|---|
| Broker / Live 操作 | 未连接真实券商，未使用 API key，未执行 paper/live broker 或真实资金测试。 |
| External API | Required tests and workflow use committed fixtures only; no required network or data-vendor dependency was introduced. |
| Frontend / Browser E2E | 未引入 frontend dashboard、React/Next.js、Vitest、Playwright、Cypress 或浏览器 E2E。 |
| OMS / Tax / AI trading | 未实现 OMS、税务优化、税务建议、AI 新闻分析、AI 下单或 AI 改参数。 |
| CD / Deployment / Database | 未引入 CD、部署配置、数据库 schema 或 migrations。 |

---

## 预期影响

| 项目 | 改动前 | 改动后 |
|---|---|---|
| B006 验收状态 | F008 pending | F008 independent L1 verification PASS |
| 回测能力 | 文档约束已签收 | 可运行 fixture/mock-first Global ETF Momentum MVP |
| 安全边界 | B001-B005 文档要求 | L1 guard tests 覆盖 no-secret/no-network/no-broker/no-live/no-AI-trade |

---

## 类型检查 / CI

```text
.venv/bin/python -m pytest
28 passed in 0.84s

.venv/bin/python -m ruff check .
All checks passed!

.venv/bin/python -m compileall trade tests
PASS

.venv/bin/python -m mypy --install-types --non-interactive trade
Success: no issues found in 19 source files
```

---

## L2 实测记录

| 项 | 证据 |
|---|---|
| Staging git_sha == main HEAD | N/A - B006 is local/CI-safe L1 backtest MVP; no staging deployment impact. |
| 端到端流验证 | Local workflow E2E generated JSON and Markdown reports from committed fixture data under `/tmp/opencode/b006-f008/`. |
| 关键 invariant | Verified T close signal / T+1 open execution, fixture data snapshot, parameter hash, PM-compatible output, risk flags, no paper/live claims, no network imports, no broker exports, and no AI trade authority. |
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
| S1 | One-rebalance fixture metrics are structurally valid but analytically shallow; volatility and Sharpe are `0.0`. | medium | Extend multi-period return series in later research-grade backtest batches. |
| S2 | Missing T+1 open fallback is flagged but currently falls back to signal close. | medium | Add configurable fail-closed or skip-trade behavior for missing execution prices in later batches. |
| S3 | Default fixture report intentionally surfaces position-limit violations. | low | Keep as risk-flag evidence; add a clean no-warning fixture scenario later if needed. |

---

## Framework Learnings

本批次无 framework learnings。
