# B040 Reports Robinhood Signoff 2026-06-06

> 状态：**PASS**
> 触发：B040 F004 首轮验收通过

---

## 变更背景

B040 把两处回测指标展示从 quant-jargon 表格提升为 Robinhood-style 大数字卡：

- `/backtest` 继续使用结构化 `BacktestMetrics`，但前端改为大数字 + 颜色编码 + 双语 tooltip。
- `/reports/[slug]` 在不改 `body_markdown` 原文的前提下，从既有 Markdown 表格中解析 `metrics`，并把指标卡渲染在正文上方。

本批是前端 UI + 后端解析增强，无新对外路由、无调度器、无执行能力变化。

---

## 变更功能清单

### F001-F003：Generator 实现

**Executor：** generator

**结果：**
- backend `ReportDetail.metrics` 解析完成：header-signature + 同义词映射 + Calmar 派生 + graceful null。
- 前端 `MetricsDisplay` / `colorForMetric` / 双语 tooltip 已接入 `/backtest` 与 `/reports/[slug]`。
- `/reports/[slug]` 在 `metrics != null` 时显示 `report-metrics`，并保持 `body_markdown` 原样渲染在下方。
- CI handoff 全绿：backend `808` / `ruff 0` / `mypy 0`；frontend `lint 0` / `typecheck` / `vitest 233` / Playwright 绿。

### F004：Codex L1 + L2 验收与签收

**Executor：** codex

**文件：**
- `docs/test-reports/B040-reports-robinhood-signoff-2026-06-06.md`
- `docs/screenshots/B040-reports-robinhood/backtest-zh-CN.png`
- `docs/screenshots/B040-reports-robinhood/backtest-en.png`
- `docs/screenshots/B040-reports-robinhood/report-zh-CN.png`
- `docs/screenshots/B040-reports-robinhood/report-en.png`
- `docs/screenshots/B040-reports-robinhood/browser-check.json`
- `progress.json`
- `features.json`
- `.auto-memory/project-status.md`

---

## 未变更范围

| 事项 | 说明 |
|---|---|
| 新 API / 新路由 | 无；仍是既有 `/api/reports/{slug}`，仅 payload 新增 `metrics` 字段 |
| `body_markdown` 内容 | 不改原文；仅独立新增指标卡 section |
| Home / Recommendations / Risk | 本批不涉及 |
| 调度器 / timer | N/A |
| 任何执行 / 下单能力 | 无改动，仍是 research-only |

---

## 类型检查 / CI

```text
backend targeted pytest: 26 passed
  - workbench/backend/tests/unit/test_reports_metrics.py
  - workbench/backend/tests/unit/test_reports.py
  - workbench/backend/tests/unit/test_backtests.py
backend targeted ruff: 0 issues
backend targeted mypy: 0 issues

frontend targeted vitest: 48 passed
  - tests/unit/metric-color.spec.ts
  - tests/unit/metrics/MetricsDisplay.spec.tsx
  - tests/unit/page/backtest.spec.tsx
  - tests/unit/page/reports.spec.tsx
  - tests/unit/messages-key-parity.spec.ts
  - tests/safety/no-execution-buttons.spec.ts

local Playwright: 5 passed
  - tests/e2e/b040-metrics.spec.ts

generator handoff baseline:
  - backend 808 / ruff 0 / mypy 0
  - frontend lint 0 / typecheck pass / vitest 233 / Playwright green
```

---

## L2 实测记录

| 项 | 证据 |
|---|---|
| Production `/api/health` | `200`，`version=e9da1ef81dcf4f86e95765c7309d0c10dcc9aab5` |
| Production HEAD vs main HEAD | 签收前 `main HEAD=c2f200ce7841162dcbebf98c98bb7897aadcbe3f`；`git diff --name-only e9da1ef..HEAD` 仅 `.auto-memory/project-status.md`、`features.json`、`progress.json`，按 §Production/HEAD 接受等价不同步 |
| authenticated `/api/debug/recent-errors` | `{"count":0,"records":[]}` |
| authenticated `/api/reports/B016-risk-parity-hrp-comparison` | `200`，`metrics != null`，字段含 `cagr/calmar/max_drawdown/sharpe/sortino/turnover/volatility`，`sharpe=2.416838` |
| authenticated `/api/reports/B039-home-advisor-disclaimer-signoff` | `200`，`metrics = null` |
| anonymous `/api/reports/B016-risk-parity-hrp-comparison` | `401` |
| 浏览器手验 | `docs/screenshots/B040-reports-robinhood/browser-check.json`：zh-CN / en 两轮 `/backtest` 与 `/reports/B016-risk-parity-hrp-comparison` 均满足 `metricsVisible=true`、`buttonCount=0`、`syntheticBannerCount=0`、`oldDashboardCount=0`、`issues=[]` |
| tooltip 双语 | zh-CN tooltip 含“风险调整后回报”；en tooltip 含“Risk-adjusted return” |
| §1.1 非预测边界 | 两轮 `textHasExpectedReturn=false`、`textHas收益预测=false` |
| Markdown 完整性 | `/reports` 页面 `page-report-detail` 可见，`reportOrder` 显示 `report-metrics` 后仍有正文卡片，且正文文本含 `Summary` |

> 说明：本批无新路由、无新 timer，因此 v0.9.32 §23 和 v0.9.33 §24 在本批仅适用既有 `/api/reports/{slug}` payload 复核；新增 timer 验证为 N/A。

---

## Harness 说明

本批改动经 Harness 状态机完整流程（planning → building → verifying → done）交付。
本签收完成后，`progress.json` 已更新为 `status: "done"`，`docs.signoff` 已填入本报告路径。

---

## Production / HEAD 等价性

| 项 | 值 |
|---|---|
| Production version | `e9da1ef81dcf4f86e95765c7309d0c10dcc9aab5` |
| Main HEAD | `c2f200ce7841162dcbebf98c98bb7897aadcbe3f` |
| Diff (`git log --oneline <deployed>..HEAD`) | `c2f200c chore(B040): F001+F002+F003 done + CI green -> status=verifying (handoff to Codex F004)` |

**等价性判断：**

`git diff --name-only e9da1ef..c2f200c` 仅含状态机文件：

- `.auto-memory/project-status.md`
- `features.json`
- `progress.json`

无 `workbench/**`、`framework/**`、`docs/specs/**` 等产品或 deploy-impacting 改动，因此 production 与当前 HEAD 产品等价，不阻断签收。

---

## Post-signoff Deploy

| 项 | 值 |
|---|---|
| 签收 commit 类型 | `signoff + status machine + screenshots` |
| Post-signoff dispatch 是否需要 | **否** |
| 接受不同步声明 | 本次 signoff commit 仅新增验收报告、截图、browser-check 与状态机文件；不含产品代码或 deploy-impacting 改动，按 §Production/HEAD 接受不同步 |

---

## Decommission Checklist

| 检查项 | 状态 | 证据 |
|---|---|---|
| 旧 dashboard 未复活 | **是** | `browser-check.json` 中 `oldDashboardCount=0` |
| B026 synthetic banner 未复活 | **是** | `browser-check.json` 中 `syntheticBannerCount=0` |
| 指标卡无下单/执行按钮 | **是** | `browser-check.json` 中 `/backtest`、`/reports` 均 `buttonCount=0` |

---

## Framework Learnings

无新增 framework 沉淀。本批验证表明现有 v0.9.25 / v0.9.31 / v0.9.32 / v0.9.33 守门足以覆盖“既有路由增强 + 纯 UI 指标重构”场景。

---

## Conclusion

可以签收。B040 已在 production 上验证两处指标面都完成 Robinhood-style 重构：`/backtest` 与 `/reports/[slug]` 均展示大数字指标、双语 tooltip、无执行按钮，且 `/reports` 的正文 Markdown 仍完整保留在指标卡下方。
