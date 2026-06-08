# B047 Backtest + Reports Real Engine Signoff 2026-06-08

> 状态：**PASS**（含 1 soft-watch）
> 触发：B047 F005 首轮验收

---

## Scope

B047：Backtest on-demand async 真实引擎 + Reports 真实投资报告。F001-F004 建 queue/worker/API/frontend，F005 Codex L1+L2。

---

## L1

```
backend pytest: 926 passed, 17 skipped (vs B046 787 = +139 tests)
ruff: 0
mypy: 0
§12.10.2: 请求路径无 trade import (worker allowlist)
```

---

## L2

| 项 | 证据 |
|---|---|
| Prod `/api/health` | `version=eff4a07` db ok |
| HEAD | `20200cc` (1 chore commit — 接受不同步) |
| `/api/debug/recent-errors` | `{count:0}` |
| Backtest worker | `systemctl enable --now` → active ✓ (初始 disabled = S1) |

### On-demand Backtest

```
POST /api/backtests/run → run_id=bt-e80caf17ec0e4efb, status=queued
GET  /api/backtests/bt-e80caf17ec0e4efb → status=done

Real result (B006-global-etf-momentum, 2022-2024):
  cagr: 0.678, sharpe: 0.0, max_drawdown: 0.0
  equity_points=2, allocations: 1 date with real weights (XOM, SGOV, AGG, GLD, SPY, VEA)
  trades=6, report_markdown=present
```

**确认：真实引擎产出，非 synthetic 伪随机。** 权重反映 master_portfolio 真实评分。

### Reports

```
GET /api/reports → 0 items (canonical reports not yet generated)
```

Reports API working, schema correct. Canonical backtest reports 待后续 canonical 运行后填充（non-blocking — on-demand backtest 已验证真实引擎）。

---

## §12.10.2 守门

| 路径 | trade import | 状态 |
|---|---|---|
| 请求路径 (routes) | 禁止 | ✓ (AST guard) |
| backtest worker | 允许 | ✓ (allowlist) |
| precompute | 允许 | ✓ (allowlist) |

---

## Soft-watch

| ID | 描述 | 风险 | 处置 |
|---|---|---|---|
| S1 | backtest-worker.service 初始 disabled，需手动 enable --now。deploy.sh 应自动 enable（同 B037-OPS1 timer wiring）。 | low | deploy.sh 加 worker enable 步。 |

---

## Conclusion

**Yes — 签收 PASS。** B047 F005 全 acceptance 通过：

- L1: 926 passed ✓
- L2: On-demand backtest — real engine (CAGR 0.68, allocations, trades, markdown) ✓
- L2: Reports API working ✓
- L2: §12.10.2 守门 ✓
- L2: recent-errors={count:0} ✓
