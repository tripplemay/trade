# B007 Backtest Quality Hardening Signoff 2026-05-12

> 状态：**Evaluator 验收通过**（progress.json status=done）
> 触发：B007 F006 独立验收 Backtest Quality Hardening。

---

## 变更背景

B007 在 B006 Global ETF Momentum Backtest MVP 基础上处理 signoff soft-watch：补充多次月度调仓 fixture、显式缺失 T+1 Open 策略、clean/warning 风险场景、强化 metrics/equity curve/report 不变量，并保持 no-live/no-secret/no-network/no-broker/no-AI safety guards。

---

## 变更功能清单

### F001：扩展多次月度调仓 fixture

**Executor：** generator

**验收结果：** PASS

### F002：配置化 T+1 Open 缺失处理策略

**Executor：** generator

**验收结果：** PASS

### F003：补充 clean 与 warning 风险场景

**Executor：** generator

**验收结果：** PASS

### F004：强化指标与 equity curve 报告

**Executor：** generator

**验收结果：** PASS

### F005：保持 workflow E2E 与安全 guard 回归

**Executor：** generator

**验收结果：** PASS

### F006：独立验收 B007 Backtest Quality Hardening

**Executor：** codex

**文件：**
- `docs/test-reports/B007-backtest-quality-hardening-review-2026-05-12.md`
- `docs/test-reports/B007-backtest-quality-hardening-signoff-2026-05-12.md`

**验收标准：**
- Evaluator 在 local/CI-safe 环境执行 L1 验收。
- 确认 pytest/ruff/compileall/mypy、multi-rebalance fixture workflow E2E、缺失 T+1 open 策略、clean/warning risk scenarios、report schema、no-live/no-secret/no-network/no-broker/no-AI guards 均符合 B001-B006 约束。

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
| B007 验收状态 | F006 pending | F006 independent L1 verification PASS |
| 回测质量 | B006 one-rebalance MVP | Multi-rebalance workflow with stronger metrics/equity curve/report invariants |
| 风险场景 | Warning path present but default report had warnings | Clean default workflow plus explicit warning tests/classification |
| Missing T+1 Open | Fallback existed | Explicit policy with fallback, skip, fail-closed coverage and report fields |

---

## 类型检查 / CI

```text
.venv/bin/python -m pytest
37 passed in 1.01s

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
| Staging git_sha == main HEAD | N/A - B007 is local/CI-safe L1 backtest hardening; no staging deployment impact. |
| 端到端流验证 | Local workflow E2E generated JSON and Markdown reports from committed fixture data under `/tmp/opencode/b007-f006/`. |
| 关键 invariant | Verified 3 rebalances, T close signal / T+1 open execution, explicit missing T+1 open policy, nonzero volatility/Sharpe, turnover, equity curve, clean warning flags, no paper/live claims, no network imports, no broker exports, and no AI trade authority. |
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
| S1 | Default clean workflow equity curve is monotonic, so max drawdown remains `0.0`. | low | Add deterministic drawdown workflow if future risk-hardening requires report-level drawdown warnings. |
| S2 | Missing T+1 open warning modes are unit-tested but not the default workflow path. | low | Add an expected-warning workflow/golden report if end-to-end warning-mode artifacts become required. |
| S3 | Synthetic fixture validates mechanics, not investable research quality. | medium | Future research-grade batches should add broader historical data while keeping fixture/mock CI defaults. |

---

## Framework Learnings

本批次无 framework learnings。
