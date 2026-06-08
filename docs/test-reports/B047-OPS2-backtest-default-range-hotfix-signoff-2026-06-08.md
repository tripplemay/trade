# B047-OPS2 Backtest Default Range Hotfix Signoff 2026-06-08

> 状态：**PASS**
> 触发：B047-OPS2 F003 首轮验收

---

## Scope

B047-OPS2 hotfix：回测页默认范围开箱即坏 + 数据深度不足。L1 动态有效默认 + L2 API data-range + L3 structured error-kind + L4 deep backfill 1825 天。

---

## L1

```
backend pytest: 959 passed, 17 skipped (vs B047 926 = +33 tests)
ruff: 0
mypy: 0
§12.10.2: data-range 请求路径只读 DB 无 trade import
```

---

## L2

### Data range

```
GET /api/backtests/data-range:
  data_start: 2021-06-09
  data_end: 2026-06-05
  min_usable_start: 2022-04-10 (lookback window margin)
```

### Default range Run (非退化)

```
POST /api/backtests/run (B006, 2024-12→2025-12):
  status=done, cagr=0.25, sharpe=3.16, max_dd=0.0, turnover=4.58
  equity=6 points, trades=112, report_md=1075 chars
```

**vs B047 R2**: equity 3→6 points, trades 12→112 — deep backfill (18463 rows, 37 symbols) 大幅改善数据深度。

### Invalid range (友好错误)

```
POST /api/backtests/run (2019-01→2019-06, 数据覆盖外):
  status=error, error_kind=no_signal_dates
  "no quarter-end signal dates available in the requested date range"
```

### Regression

| 检查项 | 结果 |
|---|---|
| `/api/debug/recent-errors` | {count:0} |
| HEAD vs prod | f05d913 (diff: 2 state-machine commits — 接受不同步) |

---

## Hotfix 四层效果

| 层 | 修复 | 状态 |
|---|---|---|
| L1 | 动态默认范围（去硬编码） | ✓ |
| L2 | data-range API + picker 钳制 | ✓ |
| L3 | structured error-kind → 友好提示 | ✓ |
| L4 | 1825 天深回填 | ✓ |

---

## Conclusion

**Yes — 签收 PASS。** B047-OPS2 F003 全通过：

- L1: 959 passed ✓
- L2: data-range real (2021-2025) ✓
- L2: 默认范围 Run non-degenerate (6 points, 112 trades, sharpe 3.16) ✓
- L2: 无效范围友好错误 (error_kind=no_signal_dates) ✓
- L2: recent-errors={count:0} ✓
