# B027 — Real Data Snapshot Foundation（Polygon adapter + Repository + cost guard）

> Status：active (planning → building)
> Owner：Generator (F001-F002) + Codex (F003)
> Predecessor：B026 (Synthetic Data Banner) — done 2026-05-26
> 估时：1-2 个轻量批次（参考 Phase 1 起点定位）
> 范围分类：post-MVP product alignment batch（Stream 1.A / Phase 1；属 implementation-path-2026-05.md §4 第二个 batch）

## 1. 目标

为 Stream 1 Real Data 接入打地基：把 **Polygon.io Starter** 数据源接入 backend Repository 抽象层 + 加 cost guard + log，**不做** backfill / 不切换 sleeve 数据源。B028 backfill / B029 财务 / B030 全 sleeve 切换都依赖本批次架构。

继承 framework v0.9.28 + B021 cloud deploy / B026 banner，**保持 banner 显示**（Layer 0 期间 banner 仍 enable，directly 因为本批次只接入 framework 不切数据）。

## 2. 决策矩阵（2026-05-26 用户已批）

| 维度 | 决策 |
|---|---|
| 数据源 | **Polygon.io Starter $30/月**（data-source-evaluation §6.1 主选）|
| API key 管理 | **方案 A：`.env.production` + GitHub Secrets**（与 B021 OAuth / DB password 同机制；新 secret `POLYGON_API_KEY`）|
| Batch 范围 | **轻**：仅 Polygon adapter + Repository 抽象 + cost guard + log；**不做** backfill（留 B028） |
| Cross-check fallback | **不在本批次**（Polygon 5xx 时仅报 alert log；yfinance / Alpha Vantage 留 B028 backfill 时接入）|
| Repository 抽象 | 新建 `trade/data/snapshot_loader.py` 抽象基类 + `trade/data/polygon_loader.py` 实现；既有 `trade/data/loader.py`（fixture）保留不动；Strategy 代码不动 |
| Cost guard | 月预算 cap $30 USD（Starter tier 含 unlimited 历史 + 5 req/min）；写 monthly usage log + 接近上限时报 alert（不自动 fallback；B027 还没 fallback）|
| CI / 离线约束 | **CI 完全离线**：mock Polygon SDK 在 test fixture；strategy 代码不依赖 polygon-api-client；离线 pytest 全过 |
| Layer banner | **不动**：本批次纯架构，不切数据；banner 仍 enable（Phase 1 全 4 batch 完成后才关）|
| Production deploy | 新 GitHub Secret `POLYGON_API_KEY` 注入 systemd EnvironmentFile；deploy.sh 含 secret check（B022 v0.9.25 §12.5 经验）|

## 3. 永久硬边界（B027 起继续 enforced）

继承 B012-B026 + framework v0.9.28 全部边界：

- **系统层：** no-broker SDK / no live trading URL / no credential（**Polygon API key 走 secret 不入代码**）/ no auto-execution / 多用户禁 / Cloud SQL 禁 / same-origin /api/* / auth-gated / Repository pattern
- **UI 层：** no-execution buttons + 中文等价禁词 / Order ticket Markdown 双语 disclaimer 永存 / B026 banner 保留
- **数据 / CI 层：** **fixture-first 离线 CI**（本批次必须保持，CI 不调 live Polygon）/ cloud-deploy workflow_dispatch + chore commit 后 dispatch deploy（v0.9.27 §12.7）
- **AI 边界（v0.9.28，本批次不引入 AI）：** 5 子条 spec 列入但本批次不触
- **新增产品边界（本批次启动起）：**
  - **(f) Polygon API key 仅 backend 用 / 永不入前端 / 永不入 build artifact / 永不入 log（key 字面值禁 grep 命中）**
  - **(g) 月预算 cap $30 USD enforced**：单月 Polygon call 次数 / cost 接近 cap 时（≥80%）写 alert log（`/api/debug/recent-errors` 可见），并自动停止后续 EOD cron（B028 之后才有 cron；B027 仅准备机制）

## 4. 技术架构

### 4.1 文件结构

```
workbench/backend/workbench_api/data/                # 新建子模块
├── __init__.py
├── snapshot_loader.py                # 抽象基类 SnapshotLoader（接口）
├── polygon_loader.py                 # Polygon 实现
├── cost_guard.py                     # MonthlyBudgetGuard
└── fixtures/                         # CI / 测试用 mock
    └── polygon_responses/            # 抽样真实 Polygon API 响应 JSON

trade/data/                            # 现有 fixture-only loader（不动）
├── loader.py                         # B009 fixture 读取（保持原样）
└── ...

workbench/backend/.env.example         # 加 POLYGON_API_KEY 注释行
workbench/backend/workbench_api/config.py  # 加 POLYGON_API_KEY 读取
```

### 4.2 SnapshotLoader 抽象

```python
# workbench_api/data/snapshot_loader.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class PriceBar:
    """Daily OHLCV bar with PIT semantics."""
    ticker: str
    bar_date: date
    open: float
    high: float
    low: float
    close: float
    adj_close: float
    volume: int


class SnapshotLoader(ABC):
    """Abstract repository for real market data snapshots.

    Implementations:
    - PolygonSnapshotLoader (B027): live Polygon.io API
    - YFinanceSnapshotLoader (B028, planned): yfinance fallback / cross-check
    - AlphaVantageSnapshotLoader (B028, planned): another cross-check source
    """

    @abstractmethod
    def fetch_daily_bars(
        self,
        ticker: str,
        from_date: date,
        to_date: date,
    ) -> list[PriceBar]:
        """Fetch daily OHLCV bars [from_date, to_date] inclusive.

        Must be PIT-correct: never returns data that wasn't publicly available
        at to_date. Adjustments (split/dividend) applied per source convention.
        """
        ...

    @abstractmethod
    def health_check(self) -> bool:
        """Verify API key validity + connectivity. Returns True on 200."""
        ...
```

### 4.3 Polygon 实现 + cost guard

```python
# workbench_api/data/polygon_loader.py
import os
from datetime import date
import httpx
from workbench_api.data.snapshot_loader import SnapshotLoader, PriceBar
from workbench_api.data.cost_guard import MonthlyBudgetGuard


class PolygonSnapshotLoader(SnapshotLoader):
    def __init__(self, api_key: str | None = None, guard: MonthlyBudgetGuard | None = None):
        self.api_key = api_key or os.environ.get("POLYGON_API_KEY")
        if not self.api_key:
            raise RuntimeError(
                "POLYGON_API_KEY missing; configure .env.production via GitHub Secret"
            )
        self.guard = guard or MonthlyBudgetGuard.default()
        self._client = httpx.Client(timeout=30.0)

    def fetch_daily_bars(self, ticker, from_date, to_date):
        self.guard.check_and_increment()  # 触发 cost guard
        # ... HTTP call to /v2/aggs/ticker/{ticker}/range/1/day/...
        # parse 响应 → list[PriceBar]
        ...

    def health_check(self) -> bool:
        # GET /v3/reference/tickers?limit=1
        ...
```

### 4.4 cost_guard.py

```python
# workbench_api/data/cost_guard.py
from datetime import date
from dataclasses import dataclass
from workbench_api.repositories import budget_log  # 抽象 SQLite 表


@dataclass(frozen=True, slots=True)
class MonthlyBudgetGuard:
    monthly_cap_usd: float = 30.0  # Polygon Starter tier
    alert_threshold_ratio: float = 0.80
    estimated_cost_per_call_usd: float = 0.0001  # 5 req/min × 30 days × est

    @classmethod
    def default(cls) -> "MonthlyBudgetGuard":
        return cls()

    def check_and_increment(self) -> None:
        """Called before every Polygon API call. Raises BudgetExceeded if cap hit;
        logs alert at ≥80% utilization."""
        current = budget_log.get_month_total_calls(date.today())
        estimated_used = current * self.estimated_cost_per_call_usd
        if estimated_used >= self.monthly_cap_usd:
            raise BudgetExceeded(
                f"Monthly Polygon budget cap ${self.monthly_cap_usd} hit "
                f"({current} calls used)"
            )
        if estimated_used >= self.alert_threshold_ratio * self.monthly_cap_usd:
            logger.warning(
                "polygon_budget_near_cap",
                extra={"used_calls": current, "estimated_usd": estimated_used},
            )
        budget_log.increment(date.today())


class BudgetExceeded(RuntimeError):
    """Raised when Polygon monthly cap is hit; backend caller must alert + halt."""
```

### 4.5 部署集成

- `.env.example` 加 `POLYGON_API_KEY=your_key_here` 注释行 + 链接到 Polygon dashboard
- `.env.production`（VM）：通过 GitHub Secrets 注入 `POLYGON_API_KEY`（手工预先在 GitHub repo Settings 加 secret）
- `deploy.sh` 加 pre-flight check：若 `POLYGON_API_KEY` empty 则 abort（参考 B021 SSH_KEY check 模式）
- `systemd/workbench-backend.service` EnvironmentFile 已含 `.env.production` 不需改

### 4.6 Cost log 落盘

新建 SQLite 表 `polygon_budget_log`（schema：date + month_year + call_count + total_cost_usd_est）；workbench-backend 启动时 alembic migration 自动建。

`/api/debug/recent-errors`（B022 v0.9.25 既有）会自然捕获 `polygon_budget_near_cap` 与 `BudgetExceeded` 日志。

## 5. Feature 拆分

### F001 — Polygon adapter + Repository 抽象（generator，2-3 天）

**Acceptance：**

(1) 新建 `workbench_api/data/__init__.py` + `snapshot_loader.py`：抽象基类 `SnapshotLoader` + dataclass `PriceBar`（含 PIT semantics docstring）

(2) 新建 `workbench_api/data/polygon_loader.py`：`PolygonSnapshotLoader` 继承 `SnapshotLoader`；使用 httpx；`api_key` 从 `os.environ["POLYGON_API_KEY"]` 读；缺时 raise `RuntimeError` 含修复指引（"配置 .env.production via GitHub Secret"）

(3) `fetch_daily_bars(ticker, from_date, to_date)`：HTTP GET Polygon `/v2/aggs/ticker/{ticker}/range/1/day/{from}/{to}` + parse 响应 → list[PriceBar]；处理 5xx / rate limit / network fail（重试 3 次 + 报 alert log）

(4) `health_check()`：GET `/v3/reference/tickers?limit=1`；返回 True / False

(5) **不动** 现有 `trade/data/loader.py`（fixture）+ 不切任何 strategy 数据源（B028+ 责任）

(6) `workbench_api/config.py` 加 `POLYGON_API_KEY` 读取（如已有 BaseSettings 模式则扩，否则 plain os.environ）

(7) `.env.example` 加 `# Polygon.io Starter API key for B027+ real data ingest` `POLYGON_API_KEY=`

(8) `deploy.sh` 加 pre-flight check：`if [ -z "${POLYGON_API_KEY}" ]; then echo "POLYGON_API_KEY missing" && exit 1; fi`（不阻塞 B021-B026 部署 — 仅在 B027 deploy 时验）

(9) pytest 新增 ≥10 测试覆盖：
- `SnapshotLoader` 抽象 instantiation 失败
- `PolygonSnapshotLoader` 缺 API key → raise RuntimeError
- mock httpx response → fetch_daily_bars 返回 list[PriceBar] 正确解析
- mock 5xx → 3 次重试 + alert log
- mock 429 rate limit → 重试 + backoff
- health_check happy path + auth fail
- PriceBar dataclass frozen + slots
- PIT semantic edge case（to_date 在未来 → 应限制到今天）
- Polygon 响应 missing field → ValueError 含 context
- 多 ticker 并发 fetch（顺序）

(10) Gates：
- `pytest tests` ≥320 baseline + ≥10 新 = ≥330 passed
- `ruff check .` exit=0
- `mypy workbench_api tests` exit=0
- frontend 不动 不破

(11) **不动**：
- B024 i18n / B025 us_quality_momentum / B026 banner
- DB schema（cost log 表在 F002 加）
- strategy / Master Portfolio / Recommendations / Risk Panel
- Frontend / UI

### F002 — Cost guard + budget log + Production secret deploy（generator，2-3 天）

**Acceptance：**

(1) 新建 `workbench_api/data/cost_guard.py`：`MonthlyBudgetGuard` dataclass（cap=30.0 / threshold=0.80 / estimated_cost_per_call=0.0001）+ `check_and_increment()` + `BudgetExceeded` exception

(2) 新建 `workbench_api/repositories/budget_log.py`：SQLite 表 `polygon_budget_log` (date PRIMARY KEY, month_year TEXT, call_count INT, total_cost_usd_est REAL)；CRUD: `get_month_total_calls(date)` / `increment(date)`

(3) alembic migration `add_polygon_budget_log_table.py`：CREATE TABLE 模板（参考 B022 既有 migration 模式）；不破既有 schema

(4) `PolygonSnapshotLoader.__init__` 接收 `guard: MonthlyBudgetGuard | None`（默认 `MonthlyBudgetGuard.default()`）；`fetch_daily_bars` 入口调 `guard.check_and_increment()`

(5) `/api/debug/recent-errors`（B022 既有）确认能捕获 `polygon_budget_near_cap` warning + `BudgetExceeded` raise log

(6) GitHub repo Settings 加 `POLYGON_API_KEY` secret（**Planner 在 spec lock 时已检查用户已注册 Polygon 账号 + 拿到 key**；secret 配置由 Generator 在实施时通过 user 协助完成；本批次默认 Generator 在 fix-round 1 时遇到 secret missing 触发 user 加 secret）

(7) `deploy.sh` 同 F001 (8) 已加 pre-flight；F002 加额外 schema-assert（v0.9.25 §12.6）确认 `polygon_budget_log` 表存在

(8) pytest 新增 ≥10 测试：
- `MonthlyBudgetGuard.default()` 默认值正确
- `check_and_increment()` 月内首次 → 通过
- `check_and_increment()` 接近 80% → log warning（capture log）
- `check_and_increment()` ≥100% → raise BudgetExceeded
- budget_log SQLite CRUD（fixture DB）
- 月份切换（5 月 → 6 月 calls 归零）
- alembic migration upgrade + downgrade（在 fixture DB）
- `PolygonSnapshotLoader` 集成 cost_guard（mock guard.check_and_increment → fetch_daily_bars 成功 / BudgetExceeded → 不调 HTTP）
- BudgetExceeded 异常包含修复指引文本
- `polygon_budget_log` 表 schema 一致性 assert

(9) Gates：
- `pytest tests` ≥340 passed
- `ruff` + `mypy` 清
- alembic migration up/down 在 fixture DB 验证
- Frontend 不动

(10) **不动**：
- F001 已完成的 PolygonSnapshotLoader / SnapshotLoader 接口
- 其他 backend endpoint / strategy 代码

### F003 — Codex L1 + L2 真 VM 验收 + signoff（codex，1-2 天）

**L1 (CI 内)：**

- F001 + F002 全部 generator 验收脚本跑通：backend pytest ≥340 / ruff / mypy / alembic up-down OK
- Frontend 不动既有 vitest ≥166 不破
- Playwright 既有 ≥33 不破
- safety regression 全绿（API key 字面值不入 build artifact + log）
- `grep` 整 build artifact + log 文件搜 `POLYGON_API_KEY` value 0 命中

**L2 (真 VM)：**

1. Generator 在实施期间已在 GitHub repo Settings 加 `POLYGON_API_KEY` secret（用户协助）；deploy workflow inject 成功
2. Production VM `cat /etc/workbench/.env.production | grep POLYGON_API_KEY` 存在（值脱敏）
3. `curl https://trade.guangai.ai/api/health` 返回 200 + version SHA 与 main HEAD 等价
4. `curl https://trade.guangai.ai/api/debug/recent-errors` 返回 `{"count":0,"records":[]}`（B027 不应产生新 error）
5. Production backend log（systemd journal）含 alembic migration `add_polygon_budget_log_table` 成功记录
6. SSH 到 VM 跑 `sudo -u postgres sqlite3 ... "SELECT name FROM sqlite_master WHERE type='table' AND name='polygon_budget_log'"` 返回 1 行
7. **smoke API test**（Evaluator 临时跑一次，绕过 strategy 代码）：production backend 触发一次 health_check → Polygon 返回 200 / budget_log 增 1 行
8. Production HEAD ≡ main HEAD（v0.9.25 §Production/HEAD 等价性）+ Post-signoff Deploy 段（v0.9.27 §Post-signoff Deploy）
9. B026 banner 仍 enable 显示（确认不被本批次影响）

**Signoff：**

- `docs/test-reports/B027-real-data-snapshot-foundation-signoff-2026-MM-DD.md` 用 framework/templates/signoff-report.md（v0.9.27/v0.9.28 模板）
- `docs/screenshots/B027-snapshot-foundation/` ≥2 PNG：production /api/health 响应 + budget_log 表存在

**Framework 候选：**

预期无重大 framework learning。若 fix-round 出现 cost guard race / secret 注入失败等意外问题，按 framework v0.9.X 模式记录在 signoff §Framework Learnings；否则留空。

## 6. 不做的事（YAGNI）

- ❌ **历史 backfill**（留 B028）— B027 仅架构 + cost guard
- ❌ **strategy 代码切真数据**（留 B030）— B027 不动 Master / sleeve / Recommendations
- ❌ **每日 EOD cron**（留 B028）— B027 不跑 scheduled job
- ❌ **yfinance / Alpha Vantage cross-check**（留 B028）— B027 仅 Polygon
- ❌ **财务数据 / SEC EDGAR**（留 B029）— B027 仅价格
- ❌ **港股原生数据**（永久边界）— US-listed ADR proxy 走 B028 同 polygon endpoint
- ❌ **实时 WebSocket / intraday**（永久边界）— B027 仅 EOD `/v2/aggs/ticker/.../1/day/...`
- ❌ **Cost auto-fallback**（B028 时再加 yfinance fallback）— B027 hit cap 仅 alert + halt
- ❌ **多 provider gateway 抽象**（aigc-gateway 风格的统一 data gateway）— Repository pattern 已足
- ❌ **Frontend / UI 改动**
- ❌ **PIT 严格化测试**（B028 backfill 时验证；B027 只在 docstring 标 PIT 语义）

## 7. 验收门槛汇总

| 门槛 | F# 责任 |
|---|---|
| SnapshotLoader 抽象基类 + PriceBar dataclass | F001 |
| PolygonSnapshotLoader 实现 + httpx + 5xx/rate limit 重试 | F001 |
| .env.example 含 POLYGON_API_KEY + deploy.sh secret check | F001 |
| MonthlyBudgetGuard + BudgetExceeded + budget_log SQLite 表 + alembic migration | F002 |
| Backend pytest ≥340 + ruff + mypy 清 | F001+F002 |
| Frontend 不破既有 vitest ≥166 + Playwright ≥33 | F001+F002+F003 |
| GitHub Secret POLYGON_API_KEY 配置 + .env.production 注入 | F002 + F003（VM 端）|
| L2 deploy 成功 + alembic migration 成功 + budget_log 表存在 | F003 |
| L2 smoke API health_check 一次 Polygon 调用成功 + budget_log +1 | F003 |
| Production HEAD ≡ main HEAD + Post-signoff Deploy 段 | F003 |
| `/api/debug/recent-errors` count=0 + API key 不入 build artifact / log | F003 |
| B026 banner 仍 enable 显示 不破 | F003 |
| Signoff 报告 framework/templates/signoff-report.md 全段 | F003 |

## 8. 参考文档

- `docs/product/implementation-path-2026-05.md` §4 Phase 1 / §7 永久边界 / §8 Planner 接续 checklist / §9 spec 撰写要点
- `docs/product/data-source-evaluation-2026-05.md` §6.1 Polygon 首选 / §7 双层存储架构 / §9 不做的事 / §10 验证 + cross-check
- `docs/product/roadmap-2026-05.md` Stream 1.A
- `docs/specs/B021-cloud-deploy-auth-spec.md` GitHub Secrets 注入机制
- `docs/specs/B022-workbench-phase1-spec.md` alembic migration 模式 + `/api/debug/recent-errors` 观测
- `docs/specs/B026-synthetic-data-banner-spec.md` 上一批次（banner 不破）
- `framework/STRUCTURE.md` framework/ 目录语义
- `framework/harness/planner.md` §"AI 边界精细化（v0.9.28）" §"Cloud-deploy spec checklist v0.9.27 扩展 (e)"
- `framework/harness/generator.md` §10 GHA / §12 systemd + deploy / §12.5/12.6 deploy.sh source env + post-alembic schema-assert / §12.7 chore-only commit dispatch deploy / §14 FastAPI 运行时观测 + /api/debug/recent-errors
- `framework/templates/signoff-report.md` v0.9.27 §Post-signoff Deploy

## 9. 风险与缓解

| 风险 | 缓解 |
|---|---|
| Polygon API key 泄漏（入代码 / log / build artifact） | F001+F002 acceptance 明示 grep 检查 + F003 L1 整 build artifact + log 文件搜 0 命中 |
| Polygon 5xx / rate limit 频繁 → cost guard 误触发 | 3 次重试 + backoff；cost guard 仅 alert 不 raise；BudgetExceeded 仅在 ≥100% cap 触发 |
| GitHub Secret 配置错误 / 部署 fail | deploy.sh pre-flight check + F003 L2 验证 .env.production 实际存在 |
| alembic migration 在 production 跑 fail | B022 v0.9.25 §12.5/12.6 经验：deploy.sh source env + post-alembic schema-assert |
| `polygon_budget_log` 表与生产数据冲突 | F002 acceptance 明示 alembic up-down 在 fixture DB 验证 |
| B027 接入后 B026 banner 受影响 | F003 L2 acceptance 显式验证 banner 仍 enable 显示 |
| Cost guard 在 fix-round 时阻塞测试（cap=$30 hit） | 测试用 mock budget_log + raise threshold；production cap 仅在 production 路径生效 |

## 10. 与既有批次的边界

- 不动 B011 Master Portfolio / B025 us_quality_momentum / B013 regime adaptive / B016 HRP
- 不动 B023 manual execution flow / B022 workbench 6 表 / B021 cloud deploy 基础设施（仅扩 `.env.production` 加 secret）
- 不动 B024 i18n / B025 双语 disclaimer
- **不动 B026 banner**（本批次不切数据，banner 仍应显示）
- 不动 `trade/data/loader.py`（fixture loader 继续 active）
- 不动 strategy 代码 / Recommendations / Risk Panel / Reports

## 11. 后续批次（不在 B027 范围）

按 implementation-path §4 顺序：

- **B028 = Phase 1 / Stream 1.B** 历史价格 snapshot backfill（接入 yfinance / Alpha Vantage cross-check + 10+ 年 SPY/QQQ/IEF/SGOV 等 ETF + B025 us_quality 30-50 ticker + US-listed ADR proxy）
- **B029 = Phase 1 / Stream 1.C** 财务 snapshot（SEC EDGAR PIT 自 parse XBRL）
- **B030 = Phase 1 / Stream 1.D** 全 sleeve 切真数据 + 回测重跑 + reports/ 加 fixture vs real 对比 → **里程碑 A Layer 0→1**

**B030 done 阶段**: by acceptance 修改 `.env.production` `NEXT_PUBLIC_SYNTHETIC_DATA_BANNER=false` 让 B026 banner 自然下线。

---

> 本 spec 完成后，progress.json status=building，current_sprint=F001，Generator 接 SnapshotLoader 抽象 + Polygon adapter 实现。
