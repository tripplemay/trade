# B011 Portfolio Allocation And Risk MVP Signoff 2026-05-13

> 状态：**Evaluator 复验通过**（progress.json status=done）
> 触发：B011 F006 第二轮 L1 复验通过，修复首轮 quarterly cadence blocker。

---

## 变更背景

B011 在 B006 Global ETF Momentum 与 B010 Risk Parity Backtest MVP 基础上新增 Master Portfolio Allocation MVP：组合两个 core sleeves，保留 satellite stubs，执行季度组合层再平衡，加入账户级 15% drawdown kill-switch，并输出组合层 JSON/Markdown reports。该批次继续保持 fixture/mock-first、显式 snapshot、research-only、no-live/no-secret/no-network-by-default/no-broker/no-paper/no-AI 边界。

---

## 变更功能清单

### F001：建立 Master Portfolio 配置边界

**Executor：** generator

**验收结果：** PASS

### F002：实现 Master Portfolio 季度再平衡 workflow

**Executor：** generator

**验收结果：** PASS

**复验说明：** 首轮发现 Master 接受同季度任意 `signal_dates`。修复后 `identify_quarter_end_signal_dates()` 只识别已确认完整季度的最后交易日，`run_master_portfolio_quarterly_backtest()` 对非 quarter-end、同季度重复日期 fail closed。复验 smoke 确认 `2024-03-10/20/25` 被拒绝，`2024-03-31/06-30/09-30` 正常产生 3 次 rebalance。

### F003：实现账户级 15% drawdown kill-switch

**Executor：** generator

**验收结果：** PASS

### F004：输出 Portfolio reports 与可计算 baseline

**Executor：** generator

**验收结果：** PASS

**BL-B010-S2 吸收说明：** B011 portfolio report 已提供 calculated static 60/40 ETF/defensive quarterly baseline，`baseline.followups_absorbed` 包含 `BL-B010-S2`。

### F005：补强 Master Portfolio 安全 guard 与 workflow 回归

**Executor：** generator

**验收结果：** PASS

### F006：独立验收 B011 Master Portfolio Allocation MVP

**Executor：** codex

**文件：**
- `docs/test-cases/B011-portfolio-allocation-risk-mvp-test-cases-2026-05-13.md`
- `docs/test-reports/B011-portfolio-allocation-risk-mvp-review-2026-05-13.md`
- `docs/test-reports/B011-portfolio-allocation-risk-mvp-reverification-2026-05-13.md`
- `docs/test-reports/B011-portfolio-allocation-risk-mvp-signoff-2026-05-13.md`

**验收标准：**
- Evaluator 在 local/CI-safe 环境执行 L1 验收和复验。
- 确认 Master Portfolio Allocation MVP、combined reports calculated baseline、account-level risk flags。
- 确认 kill-switch 触发与清除 deterministic。
- 确认 snapshot/data-quality semantics 保留。
- 确认 no-live/no-secret/no-network-by-default/no-broker/no-paper/no-AI safety guards 保留。
- signoff 明确记录 `BL-B010-S2` 已被本批次吸收。

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
| Satellite strategies | US Quality / HK-China 仍为 satellite interface stubs，不实现实际策略。 |

---

## 预期影响

| 项目 | 改动前 | 改动后 |
|---|---|---|
| Portfolio orchestration | 独立 Momentum 与 Risk Parity research paths | Adds Master Portfolio combining core sleeves with static planning weights |
| Rebalance cadence | Child-level strategy cadence only | Master-level confirmed calendar quarter-end cadence with fail-closed validation |
| Account-level risk | Child-level rules only | Adds 15% drawdown kill-switch and human-review-required state |
| Reports | Strategy-level reports | Adds combined portfolio report with account risk, contributions, snapshot refs, limitations, calculated baseline |
| B010 baseline followup | `BL-B010-S2` open | Absorbed by B011 calculated static 60/40 portfolio baseline |

---

## 类型检查 / CI

```text
./.venv/bin/python -m pytest
159 passed in 0.26s

./.venv/bin/ruff check .
All checks passed!

./.venv/bin/python -m compileall trade tests
PASS

./.venv/bin/mypy trade
Success: no issues found in 28 source files

env -i PATH="/usr/bin:/bin" HOME="$HOME" ./.venv/bin/python -m pytest \
  tests/unit/test_master_portfolio_config.py \
  tests/unit/test_master_portfolio_backtest.py \
  tests/unit/test_master_portfolio_kill_switch.py \
  tests/unit/test_master_portfolio_report.py \
  tests/unit/test_master_portfolio_safety_guards.py
68 passed in 0.11s
```

---

## L2 实测记录

| 项 | 证据 |
|---|---|
| Staging git_sha == main HEAD | N/A - B011 is a local/CI-safe research backtest batch with no staging deployment impact. |
| 端到端流验证 | Local temp-cwd smoke generated explicit `data/public-cache` snapshot and manifest, loaded it through `load_snapshot_prices()`, ran Master quarterly backtest at `2024-03-31/06-30/09-30`, and generated JSON/Markdown reports. |
| 关键 invariant | Intra-quarter dates fail closed; true quarter-end dates produce exactly 3 rebalances; report references `snapshot:0e479b79d0d4248d` and manifest `{path: data/public-cache/master-prices-manifest.json, snapshot_id: public:evaluator:master-reverify}`; baseline is `static_60_40_etf_defensive_quarterly_rebalance`; `followups_absorbed = ['BL-B010-S2']`; limitations include public-best-effort, non-PIT, research-only, not-live-trading-ready. |
| 浏览器手动验 | N/A - no UI changes. |

---

## Ops 副作用记录

本批次无数据库 ops，无外部服务写入，无券商 API 调用，无真实资金操作。

---

## Harness 说明

本批次按 Harness 状态机完成首轮 Evaluator 验收、Generator 修复、Evaluator 复验和签收。`progress.json` 已设置为 `status: "done"`，signoff 路径已填入 `docs.signoff`。

---

## Soft-watch

| ID | 描述 | 风险等级 | 建议处置 |
|---|---|---|---|
| S1 | The committed default fixture remains primarily a Global ETF Momentum fixture and is not sized/symbolized for default B010/B011 user-facing workflows. | low | Existing backlog `BL-B010-S1` should provide a risk-parity/Master-capable fixture or workflow config in a later batch. |
| S2 | Satellite sleeves are stubs and route to defensive/cash placeholder. | low | Implement US Quality / HK-China only under separate specs with data-quality and safety gates. |
| S3 | Quarter-end detection requires a following-quarter date to confirm a completed quarter, so truncated data fails closed rather than assuming the latest date is a true quarter-end. | low | Keep this behavior for safety; add explicit config later if research runs need partial-quarter handling. |

---

## Framework Learnings

本批次无 framework learnings。
