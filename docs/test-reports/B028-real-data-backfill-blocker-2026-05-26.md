# B028 Real Data Backfill Blocker 2026-05-26

> 状态：**L1 PASS / L2 FAIL**
> 触发：F004 首轮验收

## 结论

`B028 F004` 当前不能签收，已退回 `fixing`。

本地 L1 与功能性 L2 均通过，但 production `/api/health.version` 与当前 `main` HEAD 不等价，且 diff 含产品代码文件，不属于 metadata-only 差异。按 v0.9.25 §Production/HEAD 等价性，这一条是硬 blocker。

## 已通过项

### L1

- backend `pytest`: `304 passed, 2 skipped`
- backend `ruff check .`: pass
- backend `mypy workbench_api tests`: pass
- trade `mypy .`: pass
- trade `pytest -q`: 当前 `trade/` 目录无 pytest 用例，返回 `no tests ran in 0.01s`；记为结构现状，不构成新增回归
- frontend `vitest`: `166 passed`
- frontend `next build`: pass
- frontend Playwright: `38 passed`
- `npm audit --omit=dev --audit-level=high`: 无 high severity，仍仅 4 个 `moderate`
- artifact grep：未命中 `TIINGO_API_KEY`、Tiingo/Yahoo 真实 endpoint 泄漏到 `.next`

### backfill / PIT spot-check

- `data/snapshots/prices/tiingo/`: `52` 个 vendor CSV
- `data/snapshots/prices/unified/prices_daily.csv`: `153386` 行（含 header）
- `docs/test-reports/B028-cross-check-2026-05-26.md`: `25/25 PASS`，全部在 `<0.5%` 容差内
- `load_prices(['SPY'], as_of_date=2026-05-01)`：`len=3101`，最大日期 `2026-05-01`
- `load_prices(['SPY'], as_of_date=2020-03-01)`：`len=1550`，最大日期 `2020-02-28`，PIT 过滤正确

### L2 功能面

- `https://trade.guangai.ai/api/health` 返回 `200`
- authenticated `https://trade.guangai.ai/api/debug/recent-errors` 返回 `{"count":0,"records":[]}`
- authenticated `https://trade.guangai.ai/strategies` 仍命中 B026 banner 文案 `研究原型 · 仅含合成数据 · 不构成投资决策依据`

## 硬 blocker

### Production HEAD ≠ main HEAD，且 diff 含产品代码

当前值：

- production `/api/health.version`: `8338fc05d2fde18a487d11eb8c240c6bcbbaebb0`
- local `git rev-parse HEAD`: `e730a0b498d5c0171414d549a7cb1ac17d0fcd5c`

差异文件：

```text
docs/test-reports/B028-cross-check-2026-05-26.md
features.json
progress.json
scripts/validate_snapshot.py
tests/unit/test_pit_load_prices.py
trade/data/loader.py
```

其中至少以下路径属于产品/行为差异，不能按 metadata-only 接受：

- `trade/data/loader.py`
- `scripts/validate_snapshot.py`

因此虽然 production 功能面当前未见异常，但它运行的不是本轮最终验收的代码版本，不能签收。

## Generator 下一步

需要做的只有一件：

1. 让 production 追到当前 `main` HEAD（正常 deploy 或按项目规则触发对应 workflow）。

deploy 完成后，Codex 复验重点只需重新确认：

- `/api/health.version == main HEAD`
- `/api/debug/recent-errors == 0`
- B026 banner 仍显示

本地 L1、backfill 文件数、cross-check 报告和 PIT spot-check 不需要重做全量，除非修复过程中又引入代码变更。

## 产物

- 本报告：`docs/test-reports/B028-real-data-backfill-blocker-2026-05-26.md`
