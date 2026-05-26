# B028 — Real Data Backfill（Tiingo + yfinance cross-check + Storage 双层 + PIT loader）

> Status：active (planning → building)
> Owner：Generator (F001-F003) + Codex (F004)
> Predecessor：B027 (Real Data Snapshot Foundation) — done 2026-05-26
> 估时：1 个中等批次（参考 Phase 1 第二个 batch 定位）
> 范围分类：post-MVP product alignment batch（Stream 1.B / Phase 1；属 implementation-path-2026-05.md §4 第三个 batch）

## 1. 目标

利用 B027 已落地的 `TiingoSnapshotLoader` + cost guard，把 Master 4 sleeve ETF + B025 us_quality_momentum 30-50 ticker + US-listed ADR proxy（合计 **50-80 ticker**）的 **10+ 年历史日线 OHLCV** backfill 到本地 fixture-shaped unified 层 + 加 yfinance cross-check 抽样验证 + 加 PIT loader enforcement。

继承 framework v0.9.29（**含 §12.8 pyproject runtime vs dev dep hygiene + safety regression test pattern**）。本批次新增 `yfinance` dep 必须走 §12.8 规约。

**不做**：strategy 代码切真数据（留 B030）、财务 snapshot（留 B029）、每日 EOD cron（推迟到 Phase 1 后期或 B030+）。

## 2. 决策矩阵（2026-05-26 用户已批）

| 维度 | 决策 |
|---|---|
| Backfill 范围 | **Master 4 sleeve 全部 ETF + B025 30-50 ticker + US-listed ADR proxy**（约 50-80 ticker × 10+ 年；Tiingo Starter 60 req/hour 下 1-2 小时跑完）|
| yfinance cross-check | **抽样验证**（3-5 ticker × 5 随机日期，误差 <0.5%）；`scripts/validate_snapshot.py` 一次性跑 + 报告；**不进 CI**（CI 离线约束）|
| Storage 路径 | **`data/snapshots/{prices,fundamentals}/{vendor,unified}/` 双层**（继承 data-source-evaluation §7.1）；vendor-specific raw 保留可追溯 + fixture-shaped unified 为 strategy 代码读路径 |
| PIT 验证 | **loader 层 enforcement + pytest spot check**（`trade/data/loader.py` 接 `as_of_date` 参数过滤 unified.date <= as_of_date；pytest 加 3-5 spot check 如 `as_of=2020-03-01 不应看到 2020-04 数据`）|
| Master / B025 strategy 代码切换 | **本批次不切**（B030 责任）；新增 unified storage 与既有 fixture 同 schema，B030 仅改 loader 读路径 |
| 每日 EOD cron | **本批次不上线**；backfill 脚本一次性手动跑 + 入仓后 cron 留 B030 或独立 Phase 1.5 batch |
| Tiingo API key | **B027 已配置**；本批次复用 |
| 月预算 | B027 cap $10 USD/月（v0.9.29 §12.8 + B027 §3）；本批次 backfill 总 req ≤200 在 60/hour 下 1-2 小时跑完；budget 使用率约 5% cap |
| Production deploy | **本批次不接 production 服务**（backfill 是 offline 本机一次性脚本）；CI 仍跑（pytest / ruff / mypy / safety regression 含新 §12.8 ast walker test）|
| Layer banner | **不动**：本批次仍是 Layer 0（strategy 仍读 fixture）；B026 banner 保留 |

## 3. 永久硬边界（B028 起继续 enforced）

继承 B012-B027 + framework v0.9.29 全部边界：

- **系统层：** no-broker SDK / no live trading URL / no credential（Tiingo API key 走 secret）/ no auto-execution / 多用户禁 / Cloud SQL 禁 / same-origin /api/* / auth-gated / Repository pattern
- **UI 层：** no-execution buttons + 中文等价禁词 / Order ticket Markdown 双语 disclaimer 永存 / B026 banner 保留
- **数据 / CI 层：** **fixture-first 离线 CI**（本批次新加：CI 不调 live Tiingo / 不调 yfinance；测试用 mock fixture）/ cloud-deploy workflow_dispatch + chore commit 后 dispatch deploy（v0.9.27 §12.7）/ **`pyproject` runtime vs dev dep hygiene + safety regression test 守门（v0.9.29 §12.8；本批次 yfinance 必须走规约）**
- **AI 边界（v0.9.28，本批次不引入 AI）：** 5 子条 spec 列入但本批次不触
- **B027 新增（继续）：** (f) Tiingo API key 仅 backend 用永不入前端/build/log + (g) 月预算 cap $10 USD enforced

## 4. 技术架构

### 4.1 文件结构

```
workbench/backend/workbench_api/data/                # 既有（B027）
├── snapshot_loader.py                # 抽象基类（B027）
├── tiingo_loader.py                  # Tiingo 实现（B027）
├── yfinance_loader.py                # 【新增 F001】yfinance 备源
├── cost_guard.py                     # MonthlyBudgetGuard（B027）
└── fixtures/                         # mock 响应（B027 起）
    ├── tiingo_responses/
    └── yfinance_responses/           # 【新增 F001】

scripts/                                # 【新增 F002】backfill 脚本
├── backfill_prices.py                # 主 driver：用 TiingoSnapshotLoader backfill 50-80 ticker × 10+ 年到 unified 层
└── validate_snapshot.py              # 【新增 F001】yfinance cross-check 抽样验证

data/snapshots/                         # 【新增 F002】生产数据目录（git-ignored 大文件 / 留 README）
├── prices/
│   ├── tiingo/                       # vendor-specific raw
│   │   ├── SPY-2014-2026.csv
│   │   ├── QQQ-2014-2026.csv
│   │   └── ...（50-80 ticker × 1 file）
│   └── unified/                      # fixture-shaped
│       └── prices_daily.csv          # 与 B025 fixture 同 schema (date,ticker,open,high,low,close,adj_close,volume)
└── fundamentals/                      # 留空目录（B029 填）
    ├── sec_edgar/
    └── unified/
data/snapshots/.gitignore              # 【新增 F002】大文件 gitignore，仅 README + schema sample 入仓
data/snapshots/README.md               # 【新增 F002】schema + 重新生成步骤

trade/data/                             # 既有 fixture-only loader
├── loader.py                         # 【改 F003】加 as_of_date 参数 + PIT enforcement + 读 unified.prices_daily.csv 若存在否则回退 fixture
└── ...

pyproject.toml                          # 【改 F001】[project].dependencies 加 yfinance>=0.2
tests/safety/test_runtime_dependencies_pinned.py  # 【F001 update】CRITICAL_RUNTIME_DEPS 加 yfinance
```

### 4.2 yfinance loader（cross-check 备源）

```python
# workbench_api/data/yfinance_loader.py
"""yfinance SnapshotLoader implementation for cross-check validation.

Per data-source-evaluation §6.1, yfinance is a free non-official wrapper used
only for cross-check (sample assertion vs Tiingo); not in production EOD path.

Per v0.9.29 §12.8: yfinance is in [project].dependencies because it's imported
by workbench_api/data/yfinance_loader.py (source tree).
"""
from __future__ import annotations
from datetime import date
import yfinance as yf
from workbench_api.data.snapshot_loader import SnapshotLoader, PriceBar


class YFinanceSnapshotLoader(SnapshotLoader):
    """Non-official Yahoo Finance wrapper; cross-check only, not production main."""

    def fetch_daily_bars(self, ticker, from_date, to_date):
        # yf.Ticker(ticker).history(start=from_date, end=to_date)
        # parse → list[PriceBar]
        # No cost guard (yfinance free / no key)
        ...

    def health_check(self) -> bool:
        # yf.Ticker("SPY").info dict not empty → True
        ...
```

### 4.3 validate_snapshot.py（cross-check 抽样）

```python
# scripts/validate_snapshot.py
"""One-shot validation: assert Tiingo unified data matches yfinance within 0.5%.

Sample strategy:
- 3-5 random tickers from universe
- 5 random trading days each
- Assert |tiingo_close - yfinance_close| / yfinance_close < 0.005

Run after `scripts/backfill_prices.py` completes.
Output: pass/fail summary table; not part of CI.
"""
import random
from workbench_api.data.tiingo_loader import TiingoSnapshotLoader
from workbench_api.data.yfinance_loader import YFinanceSnapshotLoader


def main():
    tickers = random.sample(load_universe(), 5)
    dates = random.sample(load_trading_days(), 5)
    discrepancies = []
    for tk in tickers:
        for d in dates:
            tiingo_close = tiingo_loader.fetch_daily_bars(tk, d, d)[0].close
            yf_close = yf_loader.fetch_daily_bars(tk, d, d)[0].close
            err = abs(tiingo_close - yf_close) / yf_close
            if err >= 0.005:
                discrepancies.append((tk, d, tiingo_close, yf_close, err))
    if discrepancies:
        print(f"FAIL: {len(discrepancies)} discrepancies > 0.5%")
        for d in discrepancies:
            print(f"  {d}")
        sys.exit(1)
    print(f"PASS: 25 samples cross-checked, all within 0.5%")
```

### 4.4 backfill_prices.py（主 driver）

```python
# scripts/backfill_prices.py
"""One-shot historical backfill: Tiingo → vendor + unified layers.

Usage: python scripts/backfill_prices.py --from 2014-01-01 --to 2026-05-26

For each ticker in universe:
1. Fetch from Tiingo via TiingoSnapshotLoader (cost guard active)
2. Write raw to data/snapshots/prices/tiingo/{ticker}-{from}-{to}.csv
3. Append to unified data/snapshots/prices/unified/prices_daily.csv
4. Validate row count + schema + non-negative
"""
```

### 4.5 PIT loader enforcement

```python
# trade/data/loader.py 改动
"""Existing fixture loader extended with as_of_date PIT enforcement.

After B028: if data/snapshots/prices/unified/prices_daily.csv exists,
read from unified; else fall back to existing fixture.

PIT contract: caller passes as_of_date; loader filters unified.date <= as_of_date.
Tests assert: as_of=2020-03-01 must not return rows with date >= 2020-03-02.
"""
def load_prices(
    tickers: list[str],
    as_of_date: date,
    from_date: date | None = None,
) -> dict[str, list[PriceBar]]:
    """Load daily price bars with strict PIT enforcement.

    Args:
        tickers: list of ticker symbols
        as_of_date: PIT cutoff; rows with date > as_of_date are filtered out
        from_date: optional lower bound (defaults to earliest available)

    Returns: {ticker: [PriceBar...]} sorted by date ascending.
    """
    source_path = Path("data/snapshots/prices/unified/prices_daily.csv")
    if source_path.exists():
        df = pd.read_csv(source_path)
        df["date"] = pd.to_datetime(df["date"]).dt.date
        df = df[df["date"] <= as_of_date]  # PIT filter
        df = df[df["ticker"].isin(tickers)]
        if from_date:
            df = df[df["date"] >= from_date]
        # parse → dict[str, list[PriceBar]]
        ...
    else:
        # fall back to existing fixture path（B009 path）
        ...
```

## 5. Feature 拆分

### F001 — yfinance loader + cross-check script + v0.9.29 §12.8 走规约（generator，2-3 天）

**Acceptance：**

(1) `pyproject.toml` 加 `yfinance>=0.2.40` 到 **`[project].dependencies`**（不是 dev extras；v0.9.29 §12.8 规约）

(2) `tests/safety/test_runtime_dependencies_pinned.py` 已存在（v0.9.29 §12.8.1）；`CRITICAL_RUNTIME_DEPS` 加 `yfinance`；既有测试通过

(3) 新建 `workbench_api/data/yfinance_loader.py`：`YFinanceSnapshotLoader` 继承 `SnapshotLoader`；`fetch_daily_bars` 调 `yfinance.Ticker(t).history(start, end)` parse → list[PriceBar]；`health_check` 调 `yf.Ticker("SPY").info` 非空

(4) 新建 `workbench_api/data/fixtures/yfinance_responses/spy-sample.json` 等 mock 响应；测试用 mock 不调网络

(5) 新建 `scripts/validate_snapshot.py`：抽样 3-5 ticker × 5 随机日期 cross-check Tiingo vs yfinance；误差 <0.5% PASS / else FAIL；输出 summary 表 + 详细 discrepancy 列表；exit code 0/1

(6) pytest 新增 ≥8 测试覆盖：
- `YFinanceSnapshotLoader` mock yfinance.Ticker(...).history → list[PriceBar] 正确解析
- mock yfinance 返回空 → ValueError 含 context
- `health_check()` happy + fail（mock Ticker info empty）
- validate_snapshot 抽样逻辑（mock Tiingo + yfinance 返回 same / close → PASS）
- validate_snapshot 抽样误差 ≥0.5% → FAIL
- v0.9.29 safety regression test (`test_runtime_dependencies_pinned.py`) 含 yfinance 仍 pass
- v0.9.29 critical deps pinned test 含 yfinance

(7) Gates：
- `pytest tests` ≥277 baseline (B027) + ≥8 = ≥285 passed
- `ruff check .` exit=0
- `mypy workbench_api tests` exit=0
- frontend 不动 vitest ≥166 不破

(8) **不动**：
- B027 既有 `tiingo_loader.py` / `cost_guard.py` / `snapshot_loader.py`
- B025 fixture / strategy 代码
- B026 banner
- production deploy（本 F001 仅本机 / CI）

### F002 — Backfill driver + Storage 双层 + universe 配置（generator，3-4 天）

**Acceptance：**

(1) 新建 `data/snapshots/` 目录结构 + `data/snapshots/.gitignore`（仅 README + schema sample 入仓；CSV 数据大文件 gitignore）+ `data/snapshots/README.md`（schema + 重新生成步骤）

(2) 新建 `scripts/backfill_prices.py`：
- 接受 `--from YYYY-MM-DD --to YYYY-MM-DD --tickers <comma-sep> | --universe master`
- 默认 `--universe master` = Master 4 sleeve ETF + B025 us_quality + US-listed ADR proxy（list 维护在 `scripts/universe_master.py`，一份 source of truth）
- 对每个 ticker 调 `TiingoSnapshotLoader.fetch_daily_bars(ticker, from, to)`（B027 cost guard 自动激活）
- 写 vendor raw：`data/snapshots/prices/tiingo/{ticker}-{from}-{to}.csv`
- append unified：`data/snapshots/prices/unified/prices_daily.csv`（先 sort + dedupe by (ticker, date) 后 atomic write）
- validate：行数 = expected trading days × ticker count（±0.5%）+ price 非负 + volume 非负 + schema match B025 fixture column 顺序

(3) 新建 `scripts/universe_master.py`：固定 list 含 SPY/QQQ/IEF/SGOV/GLD/IWM/EFA/EEM/TLT + B025 us_quality 30-50 ticker + ADR (FXI/MCHI/KWEB/EWH/BABA/PDD/NTES/TCEHY/NIO/XPEV/LI) 等总 50-80 ticker

(4) **本批次手动跑一次 backfill** 入仓：`python scripts/backfill_prices.py --from 2014-01-01 --to 2026-05-26 --universe master`；产物 50-80 vendor 文件 + 1 unified 文件入 `data/snapshots/`（不入 git 大文件，但 spec acceptance 要求文件存在于本机 + 在 commit message / signoff 记录 row count）

(5) **跑一次 `scripts/validate_snapshot.py`** cross-check；输出 PASS + 抽样 25 (ticker, date) 对比表存为 `docs/test-reports/B028-cross-check-2026-MM-DD.md`

(6) pytest 新增 ≥10 测试覆盖：
- backfill_prices.py argparse + 默认值
- universe_master.py 含 50-80 ticker (count assertion)
- backfill 写入 vendor raw 文件 schema correct (mock TiingoSnapshotLoader)
- backfill append unified 文件 sort + dedupe correct
- backfill row count 计算（trading days × ticker count）
- backfill 负数 / missing field validation raise ValueError
- atomic write（写入临时文件 + rename）防止部分写中断
- `data/snapshots/.gitignore` 含 *.csv 不含 README.md
- universe_master 含 必需 Master sleeve ETF (SPY/QQQ/IEF/SGOV)
- backfill on existing partial unified 文件 → merge 不重复

(7) Gates：
- `pytest tests` ≥285 + ≥10 = ≥295 passed
- ruff + mypy 清
- backfill 本机跑通 50-80 ticker × 10+ 年（Tiingo budget 使用率 ≈ 5% cap）
- validate_snapshot 抽样 25 (ticker, date) cross-check 全 PASS（误差 <0.5%）

(8) **不动**：
- F001 已完成的 yfinance loader
- B027 既有 budget guard / tiingo loader 接口
- strategy 代码 / B025 fixture（仍是 fall-back 路径）

### F003 — PIT loader enforcement + strategy 读路径 unified 切换准备（generator，2-3 天）

**Acceptance：**

(1) 改 `trade/data/loader.py`：
- 加 `as_of_date: date` 参数到 `load_prices` 等公共函数
- 加 unified 层读取：若 `data/snapshots/prices/unified/prices_daily.csv` 存在则读 unified；else 回退 既有 fixture 路径（B009）
- PIT enforcement：unified 路径返回前 filter `df.date <= as_of_date`
- docstring 明示 PIT 语义 + 数据来源（real vs fixture）

(2) **不动** strategy 代码（B011 Master / B025 us_quality / B013 regime adaptive 等不切实际读路径；F003 仅准备 loader infrastructure；切换是 B030 责任）

(3) pytest 新增 ≥10 测试覆盖：
- `load_prices(as_of=2020-03-01)` 不返回 date > 2020-03-01 的行（PIT spot check）
- `load_prices(as_of=2026-01-01)` 含 2025 末数据
- unified.csv 存在 → 读 unified；不存在 → 读 fixture
- 既有 B011/B025 fixture-based 测试 全过（B028 不破既有）
- as_of_date in future（>today）→ 限到今天
- as_of_date < earliest data → 返回空 list[PriceBar]
- 多 ticker 一次性 load 返回 dict[str, list]
- B025 fixture path 调用（如 us_quality_momentum）仍读 fixture 不破
- unified.csv schema mismatch → 清晰 ValueError 含修复指引
- PIT spot check：3-5 random (ticker, as_of_date) tuple

(4) Gates：
- `pytest tests` ≥295 + ≥10 = ≥305 passed（trade pytest 部分也覆盖；具体数视 trade vs workbench_api 分布）
- ruff + mypy 清
- **B025 既有回测 deterministic 不变**（pytest 跑 us_quality_momentum 回测断言 fixture 路径下数字不变）

(5) **不动**：
- strategy 代码（Master / sleeve / signal / construction）
- Backtest engine
- workbench backend endpoints
- Frontend / UI

### F004 — Codex L1 + L2 真 VM 验收 + signoff（codex，1-2 天）

**L1 (CI 内)：**

- F001-F003 全部 generator 验收脚本跑通：backend / trade pytest ≥305 / ruff / mypy / alembic up-down OK（本批次无 alembic 改动 但既有不破）
- Frontend 不动既有 vitest ≥166 + Playwright ≥38 不破
- safety regression 全绿（含 v0.9.29 §12.8.1 `test_runtime_dependencies_pinned.py` 含 yfinance 守门）
- artifact grep `TIINGO_API_KEY` / yfinance API endpoint 字面值 0 命中
- **CI 完全离线**：`pytest` 在 `--no-network` / 无网络环境下全过（mock fixture）

**L2 (真 VM)：**

1. Production VM 不动（本批次纯离线 backfill + loader infra；不部署 production）
2. `curl https://trade.guangai.ai/api/health` 仍 200 + version SHA 与 main HEAD 等价（仅状态机 metadata diff 接受）
3. `curl https://trade.guangai.ai/api/debug/recent-errors` 返回 `{"count":0,"records":[]}`（本批次不引入新 endpoint）
4. B026 banner 仍 enable 显示 不破
5. **Backfill 数据本机验证**（Evaluator 在本机跑）：
   - `ls data/snapshots/prices/tiingo/ | wc -l` ≈ 50-80
   - `wc -l data/snapshots/prices/unified/prices_daily.csv` ≥ 50 × 2500 (trading days × ticker) = 125K rows
   - `python -c "from trade.data.loader import load_prices; print(len(load_prices(['SPY'], date(2026,5,1))['SPY']))"` ≥ 2500（~10 年 SPY trading days）
   - PIT spot check：`load_prices(['SPY'], as_of=date(2020,3,1))['SPY']` 最大 date <= 2020-03-01
6. `scripts/validate_snapshot.py` 抽样 cross-check 报告通过（docs/test-reports/B028-cross-check-2026-MM-DD.md）
7. Production HEAD ≡ main HEAD（v0.9.25 §Production/HEAD 等价性）+ Post-signoff Deploy 段（本批次产品代码改动有限，仅 loader.py + 新文件；触发 Backend CI 但不强求 production redeploy）

**Signoff：**

- `docs/test-reports/B028-real-data-backfill-signoff-2026-MM-DD.md` 用 framework/templates/signoff-report.md（v0.9.27/v0.9.28 模板含 §Production/HEAD 等价性 + §Post-signoff Deploy 双段；§Ops 副作用记录 含 backfill 50-80 ticker × 10+ 年 入仓 row count）
- 本批次跑过 backfill 的 Tiingo budget 使用率 ≈ 5%（远低于 $10 cap）;signoff 记录 budget_log 现值
- `docs/screenshots/B028-backfill/` ≥3 PNG：data/snapshots/ ls 结构 + validate_snapshot 输出 + Master sleeve SPY 历史价格 spot check

**Framework 候选：**

预期无重大 framework learning（v0.9.29 §12.8 已守门 yfinance dep；§7.1 storage 架构已 doc 定）。若 fix-round 出现意外（如 Tiingo split-adjusted vs yfinance close discrepancy / dedup 边角），记录 signoff §Framework Learnings；否则留空。

## 6. 不做的事（YAGNI）

- ❌ **strategy 代码切真数据**（留 B030）— B028 仅准备 loader infra
- ❌ **每日 EOD cron**（留 B030 或独立 Phase 1.5）— B028 仅一次性 backfill
- ❌ **财务 / 基本面数据**（留 B029）— B028 仅价格 OHLCV
- ❌ **港股原生数据**（永久边界）— ADR proxy 走 Tiingo
- ❌ **实时 / intraday tick**（永久边界）— EOD `/tiingo/daily/{ticker}/prices` only
- ❌ **PIT replay 严格测试** 每 (ticker, date) tuple（爆炸 125K assertions）— 仅 spot check
- ❌ **多 vendor 并行调用 cross-check 入仓**（双倍 storage + budget）— 仅抽样验证
- ❌ **Frontend / UI 改动**
- ❌ **新 alembic migration**（本批次不动 DB schema）
- ❌ **Production redeploy**（本批次产品代码改动有限，CI 触发自然 deploy 即可；不强求 dispatch）
- ❌ **Tiingo / yfinance Python SDK 引入**：yfinance 是 wrapper 本身就是 SDK，无避；Tiingo 仍 httpx 直接 REST（B027 既定）

## 7. 验收门槛汇总

| 门槛 | F# 责任 |
|---|---|
| `pyproject.toml` 加 yfinance 到 `[project].dependencies` + v0.9.29 §12.8 守门 | F001 |
| `YFinanceSnapshotLoader` 实现 + mock 测试 | F001 |
| `scripts/validate_snapshot.py` 抽样 cross-check（3-5 ticker × 5 日期 误差<0.5%）| F001 |
| `scripts/backfill_prices.py` driver + universe_master.py | F002 |
| `data/snapshots/{prices,fundamentals}/{vendor,unified}/` 双层 + .gitignore + README | F002 |
| 本机跑通 50-80 ticker × 10+ 年 backfill；Tiingo budget 使用率 ≈ 5% | F002 |
| validate_snapshot 抽样 25 (ticker, date) cross-check PASS（误差 <0.5%）+ 报告落盘 docs/test-reports/B028-cross-check-*.md | F002 |
| `trade/data/loader.py` 加 `as_of_date` 参数 + unified 读 + PIT enforcement | F003 |
| pytest 总数 ≥305 + 既有 B011/B025 测试不破 + B025 us_quality 回测 deterministic | F003 |
| safety regression `test_runtime_dependencies_pinned.py` 含 yfinance 守门通过 | F001 + F004 |
| Backend / trade pytest ≥305 + ruff + mypy 清 | F001+F002+F003+F004 |
| Frontend 不破既有 vitest ≥166 + Playwright ≥38 | F004 |
| L2 backfill 数据本机验证（50-80 vendor 文件 + unified ≥125K rows + PIT spot check）| F004 |
| Production HEAD ≡ main HEAD + Post-signoff Deploy 段 | F004 |
| `/api/debug/recent-errors` count=0 + B026 banner 仍 enable | F004 |
| Signoff 报告 framework/templates/signoff-report.md 全段 | F004 |

## 8. 参考文档

- `docs/product/implementation-path-2026-05.md` §4 Phase 1 / §7 永久边界 / §8 Planner 接续 checklist / §9 spec 撰写要点
- `docs/product/data-source-evaluation-2026-05.md` §3 / §6.1 Tiingo 首选 / §6.2 财务降级 / §7 双层存储架构 / §10 验证 + cross-check
- `docs/product/roadmap-2026-05.md` Stream 1.B
- `docs/specs/B027-real-data-snapshot-foundation-spec.md` Tiingo adapter + cost guard + budget log
- `docs/specs/B025-us-quality-momentum-satellite-spec.md` §4.1 fixture schema（B028 unified 层与之同 schema）
- `docs/specs/B011-master-portfolio-allocation-spec.md`（Master 4 sleeve ETF list 来源）
- `framework/STRUCTURE.md` framework/ 目录语义
- `framework/harness/planner.md` §"AI 边界精细化（v0.9.28）" §"Cloud-deploy spec checklist v0.9.27 扩展 (e)"
- `framework/harness/generator.md` §10 GHA / §12.5-12.7 deploy / **§12.8 pyproject runtime vs dev dep hygiene（v0.9.29）** / §14 FastAPI 运行时观测
- `framework/templates/signoff-report.md` v0.9.27 §Post-signoff Deploy
- Tiingo API docs: https://www.tiingo.com/documentation/end-of-day
- yfinance docs: https://github.com/ranaroussi/yfinance

## 9. 风险与缓解

| 风险 | 缓解 |
|---|---|
| Tiingo backfill 中断 / rate limit | 重试 3 次 + backoff（B027 既有）+ atomic write 防止部分写 |
| Tiingo split/dividend adjustment 与 yfinance 不一致 | abs 误差 <0.5% threshold 容忍小差异；>0.5% 报告但不阻塞 backfill（人工 review）|
| yfinance 被 Yahoo 限流 / 数据缺失 | 仅抽样 cross-check 不入生产；fail 时 validate_snapshot exit 1 触发人工 review；不阻塞 strategy 代码 |
| unified.csv 大文件 git tracking | `data/snapshots/.gitignore` 仅入 README + sample；本机生成 + 重新跑 script 重生 |
| PIT enforcement 性能（每次 load 都过滤）| pandas date filter O(n)；50-80 ticker × 10y ≈ 125K rows 单次 filter < 100ms 可接受 |
| 既有 B025 us_quality 回测 deterministic 破坏 | F003 acceptance 明示 strategy 代码不切；既有 fixture path 仍是回退；测试断言数字不变 |
| Universe master list 与 B025 fixture / B011 Master 配置漂移 | F002 scripts/universe_master.py 是 source of truth；引用 B025 + B011 list；pytest 加一致性 assert |
| yfinance dep 引入触发 v0.9.29 §12.8 守门未通过 | F001 acceptance 明示加入 `[project].dependencies` + `CRITICAL_RUNTIME_DEPS`；既有 test_runtime_dependencies_pinned.py 守门 |
| Tiingo 突然 rebrand / 服务变化 | B027 spec §12 已记录备选（Massive $29 / EODHD $30 / yfinance free）；Repository pattern 允许零成本切换 |

## 10. 与既有批次的边界

- 不动 B011 Master Portfolio 配置 + 既有 fixture / B025 us_quality_momentum 5 因子 + fixture / B013 regime adaptive / B016 HRP
- 不动 B023 manual execution flow / B022 workbench 6 表 / B021 cloud deploy 基础设施
- 不动 B024 i18n / B025 双语 disclaimer
- **不动 B026 banner**（本批次仍是 Layer 0；B030 done 时关 banner）
- 不动 B027 既有 `tiingo_loader.py` / `cost_guard.py` / `snapshot_loader.py` / `tiingo_budget_log` schema（仅复用）
- 不动 strategy 代码 / Recommendations / Risk Panel / Reports / Frontend

## 11. 后续批次（不在 B028 范围）

按 implementation-path §4 顺序：

- **B029 = Phase 1 / Stream 1.C** 财务 snapshot（SEC EDGAR PIT 自 parse XBRL；Tiingo 不含 fundamentals 所以走 SEC EDGAR）
- **B030 = Phase 1 / Stream 1.D** 全 sleeve 切真数据（loader.py 已在 B028 准备好；B030 仅改 strategy 代码读路径切到 unified）+ 回测重跑 + reports/ 加 fixture vs real 对比 → **里程碑 A Layer 0→1**

**B030 done 阶段**: by acceptance 修改 `.env.production` `NEXT_PUBLIC_SYNTHETIC_DATA_BANNER=false` 让 B026 banner 自然下线。

**B028 done 后可启动的并行 Stream**：
- Stream 2 News ingest（B033+；依赖 B028 unified storage 不强但建议一起设计）
- Stream 3 LLM gateway / AI advisory（B031+；与 B028 完全独立）

---

> 本 spec 完成后，progress.json status=building，current_sprint=F001，Generator 接 yfinance loader + validate_snapshot 实现。
