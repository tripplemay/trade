# B010 Risk Parity Backtest MVP Signoff 2026-05-13

> 状态：**Evaluator 首轮验收通过**（progress.json status=done）
> 触发：B010 F007 独立 L1 验收。

---

## 变更背景

B010 在 B006 Global ETF Momentum、B007 backtest hardening、B008 research data expansion、B009 public data snapshot workflow 之后，新增最小 Risk Parity / Volatility Target 回测研究路径。该批次保持 fixture/mock-first、显式 snapshot、research-only、no-live/no-secret/no-network-by-default/no-broker/no-paper/no-AI 边界。

---

## 变更功能清单

### F001：建立 Risk Parity 策略配置边界

**Executor：** generator

**验收结果：** PASS

### F002：实现收益率与波动率估计

**Executor：** generator

**验收结果：** PASS

### F003：实现逆波动率权重与无杠杆 exposure scaling

**Executor：** generator

**验收结果：** PASS

### F004：实现 Risk Parity 月度回测 workflow

**Executor：** generator

**验收结果：** PASS

### F005：输出 Risk Parity 报告与基础 benchmark 对比

**Executor：** generator

**验收结果：** PASS

### F006：补强 Risk Parity 安全 guard 与 workflow 回归

**Executor：** generator

**验收结果：** PASS

### F007：独立验收 B010 Risk Parity Backtest MVP

**Executor：** codex

**文件：**
- `docs/test-cases/B010-risk-parity-backtest-mvp-test-cases-2026-05-13.md`
- `docs/test-reports/B010-risk-parity-backtest-mvp-review-2026-05-13.md`
- `docs/test-reports/B010-risk-parity-backtest-mvp-signoff-2026-05-13.md`

**验收标准：**
- Evaluator 在 local/CI-safe 环境执行 L1 验收。
- 确认 B010 实现最小 risk parity backtest MVP。
- 确认报告显式 research limitations。
- 确认 snapshot/data-quality semantics 保留。
- 确认 no-live/no-secret/no-network-by-default/no-broker/no-paper/no-AI safety guards 保留。

**验收结果：** PASS

---

## 未变更范围

| 事项 | 说明 |
|---|---|
| Broker / Paper / Live | 未连接真实券商，未实现 paper/live broker，未提交或模拟真实订单。 |
| External network | Required L1 tests and evaluator smoke did not require public network access. |
| Secrets / Paid data | 未读取 `.env`、API key、secret manager、付费数据或真实账户导出。 |
| AI trading | 未新增 AI 下单、AI 调参或可执行交易指令路径。 |
| Frontend / Dashboard | 未引入 frontend dashboard、browser E2E、React/Next.js、Playwright 或 Cypress。 |
| Deployment / DB / Ops | 无 staging/prod 部署影响，无数据库 ops，无外部服务写入。 |
| Optimizers | 未实现 ERC、minimum variance 或 constrained optimizer；B010 明确只做 inverse volatility MVP。 |

---

## 预期影响

| 项目 | 改动前 | 改动后 |
|---|---|---|
| Core strategy paths | Global ETF Momentum only | Adds fixture-first Risk Parity / Vol Target research backtest path |
| Weighting | Momentum target weights | Deterministic inverse-volatility risk parity weights with no leverage |
| Backtest workflow | Momentum monthly T close / T+1 open | Risk parity monthly T close / T+1 open with rebalance trace, costs, turnover, weights |
| Reports | Momentum JSON/Markdown reports | Adds risk parity JSON/Markdown reports with metrics, limitations, snapshot references |
| Safety posture | No-live/no-secret/offline guards | Preserved and extended with risk-parity-specific regression tests |

---

## 类型检查 / CI

```text
./.venv/bin/python -m pytest
91 passed in 0.12s

./.venv/bin/ruff check .
All checks passed!

./.venv/bin/python -m compileall trade tests
PASS

./.venv/bin/mypy trade
Success: no issues found in 25 source files

env -i PATH="/usr/bin:/bin" HOME="$HOME" ./.venv/bin/python -m pytest \
  tests/unit/test_risk_parity_config.py \
  tests/unit/test_risk_parity_backtest.py \
  tests/unit/test_risk_parity_reports.py \
  tests/unit/test_risk_parity_safety_guards.py
29 passed in 0.04s
```

---

## L2 实测记录

| 项 | 证据 |
|---|---|
| Staging git_sha == main HEAD | N/A - B010 is a local/CI-safe research backtest batch with no staging deployment impact. |
| 端到端流验证 | Local temp-cwd smoke generated an explicit `data/public-cache` snapshot and manifest, loaded it through `load_snapshot_prices()`, ran `run_risk_parity_monthly_backtest()`, and generated JSON/Markdown risk parity reports. |
| 关键 invariant | Report referenced `snapshot:c6bd7b4d7e909147` and manifest `{path: data/public-cache/risk-parity-prices-manifest.json, snapshot_id: public:evaluator:risk-parity}`; strategy timing was `T close` / `T+1 open`; limitations included imported snapshot, public-best-effort, non-PIT, research-only, not-live-trading-ready; `no_leverage = true`. |
| 浏览器手动验 | N/A - no UI changes. |

---

## Ops 副作用记录

本批次无数据库 ops，无外部服务写入，无券商 API 调用，无真实资金操作。

---

## Harness 说明

本批次按 Harness 状态机完成首轮 Evaluator 验收。`progress.json` 已设置为 `status: "done"`，signoff 路径已填入 `docs.signoff`。

---

## Soft-watch

| ID | 描述 | 风险等级 | 建议处置 |
|---|---|---|---|
| S1 | The committed default fixture remains a Global ETF Momentum fixture and is not sized/symbolized for default B010 risk parity parameters. B010 passes through explicit B009-style snapshot and synthetic daily fixture coverage. | low | If risk parity becomes a user-facing workflow, add a first-class risk parity workflow config or committed research fixture covering the default universe and 120-day lookback. |
| S2 | B010 baseline comparison is structural (`static_equal_weight_multi_asset_placeholder`) rather than an independently calculated benchmark path. | low | Replace with a calculated benchmark in a later reporting/analytics hardening batch if needed. |

---

## Framework Learnings

本批次无 framework learnings。
