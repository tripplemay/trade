# B029 — Fundamentals Snapshot（SEC EDGAR PIT XBRL parse）

> Status：active (planning → building)
> Owner：Generator (F001-F003) + Codex (F004)
> Predecessor：B028 (Real Data Backfill) — done 2026-05-26
> 估时：1-2 个中等批次（参考 Phase 1 第四个 batch；XBRL parse 复杂度 略高于 B028）
> 范围分类：post-MVP product alignment batch（Stream 1.C / Phase 1；属 implementation-path-2026-05.md §4 第四个 batch）

## 1. 目标

为 B025 us_quality_momentum 30-50 ticker backfill 10+ 年 point-in-time 财报（ROE / gross_margin / FCF Yield / debt_to_assets / PE / PB / EV/EBITDA / earnings_yield 8 ratio），数据源走 **SEC EDGAR 免费 + 自 parse XBRL**。继承 framework v0.9.27 §12.7.1（paths-trigger 已修） + v0.9.29 §12.8（pyproject runtime vs dev dep hygiene）。

**不做**：strategy 代码切真财务数据（留 B030）；非 US 公司财务（ADR/港股 proxy 用 SEC 20-F filings，覆盖 BABA/NIO 等）；财报 forecast / 预测（永久边界）；每日 EOD cron（推迟到 Phase 1 后期）。

## 2. 决策矩阵（2026-05-26 用户已批）

| 维度 | 决策 |
|---|---|
| 数据源 | **SEC EDGAR 免费自 parse XBRL**（data-source-evaluation §6.2 首选）|
| Backfill 范围 | **仅 B025 us_quality_momentum 30-50 ticker，10+ 年财报**（约 30-50 ticker × 40 季报 = 1200-2000 filings）|
| Schema 兼容 | **与 B025 fixture 严格一致**：`fundamentals.csv` 11 列（report_date / ticker / fiscal_quarter / roe / gross_margin / fcf_yield / debt_to_assets / pe / pb / ev_ebitda / earnings_yield）|
| Storage 路径 | 继承 B028 双层架构：`data/snapshots/fundamentals/{sec_edgar,unified}/` |
| PIT enforcement | **strict**：effective_date = report_date + 1 trading day（B025 spec §4.1 已定义）；`load_fundamentals(as_of)` 返回 `effective_date <= as_of` 中**每 ticker 最新 fiscal_quarter** |
| Master ETF + ADR proxy | **不 backfill fundamentals**（ETF 本身无 ratio；ADR 如 BABA/NIO 暂不入 B025 universe，等 HK-China satellite batch 再做）|
| Rate limit | SEC EDGAR 10 req/sec hard limit + User-Agent header required（违反会 ban IP）|
| 复杂 ratio 计算 | EV/EBITDA / FCF Yield 等需自行计算（SEC raw XBRL 不直接给）；按 strategy doc §6 公式实现 |
| F 拆分 | **4 features**：F001 parse / F002 backfill / F003 PIT loader / F004 codex（与 B028 一致）|
| Production deploy | 本批次纯离线 backfill + loader infra；不动 production 服务（与 B028 同）|
| Layer banner | 不动：B026 banner 仍 enable（B030 done 时关）|

## 3. 永久硬边界（B029 起继续 enforced）

继承 B012-B028 + framework v0.9.29 + v0.9.27 §12.7.1 全部边界：

- **系统层：** no-broker SDK / no live trading URL / no credential / no auto-execution / 多用户禁 / Cloud SQL 禁 / same-origin /api/* / auth-gated / Repository pattern
- **UI 层：** no-execution buttons + 中文等价禁词 / Order ticket Markdown 双语 disclaimer 永存 / B026 banner 保留
- **数据 / CI 层：** fixture-first 离线 CI / cloud-deploy workflow_dispatch（v0.9.27 §12.7）+ **paths-trigger 已含 trade/+scripts/+pyproject.toml（v0.9.27 §12.7.1）— B029 改 trade/data/loader.py + scripts/ 直接触发 CI/Deploy** / pyproject runtime vs dev dep hygiene（v0.9.29 §12.8）
- **AI 边界（v0.9.28，本批次不引入 AI）：** 5 子条
- **B027 起继续：** (f) API key 仅 backend 用 / (g) 月预算 cap（本批次无新 paid vendor，仍是 Tiingo $10 cap；SEC EDGAR 免费不计入）
- **新增产品边界（B029 起）：**
  - **(h) SEC EDGAR User-Agent 必须含联系邮箱**（SEC 政策要求；未来 ban IP 防御）— `User-Agent: workbench-trade research-only contact@example.com` 形式；不入 build artifact / log
  - **(i) Rate limit 严格 10 req/sec**（SEC hard limit；超 ban 30 天）— 用 ratelimit lib 或手写 sleep
  - **(j) Ratio 计算公式锁定 strategy doc §6**：不擅自改 formula；改公式要新 batch 走审批

## 4. 技术架构

### 4.1 文件结构

```
workbench/backend/workbench_api/data/                # 既有（B027/B028）
├── snapshot_loader.py                # PriceBar / SnapshotLoader（B027）
├── tiingo_loader.py                  # Tiingo（B027）
├── yfinance_loader.py                # yfinance（B028）
├── cost_guard.py                     # MonthlyBudgetGuard（B027）
├── fundamentals_loader.py            # 【新增 F001】FundamentalsRow + FundamentalsLoader 抽象
├── sec_edgar_loader.py               # 【新增 F001】SECEDGARFundamentalsLoader 实现
├── xbrl_parser.py                    # 【新增 F001】XBRL → ratio 计算
└── fixtures/
    ├── tiingo_responses/
    ├── yfinance_responses/
    └── sec_edgar_responses/          # 【新增 F001】抽样真实 SEC EDGAR filings JSON + XBRL XML

scripts/                                # 既有（B028）+ 新增
├── backfill_prices.py                # B028
├── validate_snapshot.py              # B028
├── universe_master.py                # B028
├── backfill_fundamentals.py          # 【新增 F002】SEC EDGAR backfill driver
├── universe_us_quality.py            # 【新增 F002】B025 us_quality 30-50 ticker → CIK 映射
└── ticker_to_cik.py                  # 【新增 F002】SEC ticker→CIK 公开映射

data/snapshots/                         # 既有（B028）+ 新增 fundamentals 实际数据
├── prices/
│   ├── tiingo/                       # B028
│   └── unified/                      # B028
├── fundamentals/                      # 【F002 填充】之前是空目录
│   ├── sec_edgar/                    # vendor raw filings + XBRL files
│   │   └── <CIK>/<accession>/        # 按 SEC 标准结构
│   │       ├── 10-K.xml / 10-Q.xml
│   │       ├── metadata.json         # filing_date / form / period_of_report / cik
│   │       └── parsed_ratios.json    # 自 parser 输出
│   └── unified/                      # fixture-shaped (B025 同 schema)
│       └── fundamentals.csv          # report_date,ticker,fiscal_quarter,roe,gross_margin,fcf_yield,debt_to_assets,pe,pb,ev_ebitda,earnings_yield

trade/data/                             # 既有 + 改
├── loader.py                         # 【改 F003】加 load_fundamentals(as_of_date) PIT enforcement
└── ...

pyproject.toml                          # 【F001 review】依赖 (lxml / requests 等若需要)
tests/safety/test_runtime_dependencies_pinned.py  # 【F001 update if any new dep】
```

### 4.2 FundamentalsLoader 抽象 + FundamentalsRow

```python
# workbench_api/data/fundamentals_loader.py
"""Abstract repository for company fundamentals snapshots.

Implementations:
- SECEDGARFundamentalsLoader (B029): SEC EDGAR free / XBRL parse
- (B029+ optional) EODHDFundamentalsLoader: paid downgrade if EDGAR parse cost > 3-5 days

Mirror the SnapshotLoader / PriceBar pattern from B027 (snapshot_loader.py).
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class FundamentalsRow:
    """One fiscal quarter's fundamentals for one ticker. PIT semantics enforced
    by report_date (when filed publicly; effective_date = report_date + 1 trading day).

    Schema matches B025 fixture fundamentals.csv exactly:
    report_date / ticker / fiscal_quarter / roe / gross_margin / fcf_yield
    / debt_to_assets / pe / pb / ev_ebitda / earnings_yield
    """
    ticker: str
    fiscal_quarter: str  # e.g. "2020-Q4"
    report_date: date    # filing date (when publicly visible)
    roe: float
    gross_margin: float
    fcf_yield: float
    debt_to_assets: float
    pe: float
    pb: float
    ev_ebitda: float
    earnings_yield: float


class FundamentalsLoader(ABC):
    @abstractmethod
    def fetch_quarterly_fundamentals(
        self,
        ticker: str,
        from_date: date,
        to_date: date,
    ) -> list[FundamentalsRow]:
        """Fetch all quarterly fundamentals filed in [from_date, to_date].

        PIT-correct: report_date is the filing date (not period_of_report).
        Caller can filter further by effective_date = report_date + 1 day.
        """
        ...

    @abstractmethod
    def health_check(self) -> bool:
        ...
```

### 4.3 SECEDGARFundamentalsLoader

```python
# workbench_api/data/sec_edgar_loader.py
"""SEC EDGAR XBRL fundamentals loader.

Endpoints:
- Company facts API: https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json
- Submissions: https://data.sec.gov/submissions/CIK{cik:010d}.json
- Raw filings: https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/...

Hard constraints:
- User-Agent header REQUIRED (SEC will ban IP without it)
  Format: 'Workbench Trade research-only <contact@example.com>'
- Rate limit: 10 req/sec hard (ratelimit lib or asyncio sleep)
- Use companyfacts API (pre-parsed XBRL JSON) when possible vs raw XML
"""
import os
from datetime import date
import httpx
from workbench_api.data.fundamentals_loader import FundamentalsLoader, FundamentalsRow
from workbench_api.data.xbrl_parser import compute_ratios


class SECEDGARFundamentalsLoader(FundamentalsLoader):
    BASE_URL = "https://data.sec.gov"

    def __init__(self, contact_email: str | None = None):
        # User-Agent 必含联系邮箱（永久边界 (h)）
        self.contact_email = contact_email or os.environ.get(
            "SEC_EDGAR_CONTACT_EMAIL"
        )
        if not self.contact_email:
            raise RuntimeError(
                "SEC_EDGAR_CONTACT_EMAIL missing; configure .env.production "
                "via GitHub Secret. SEC requires User-Agent with contact email "
                "(non-optional; ban IP otherwise)."
            )
        self._client = httpx.Client(
            timeout=30.0,
            headers={
                "User-Agent": f"Workbench Trade research-only {self.contact_email}",
                "Accept": "application/json",
            },
        )
        self._rate_limiter = SimpleRateLimit(10, period_sec=1.0)

    def fetch_quarterly_fundamentals(self, ticker, from_date, to_date):
        self._rate_limiter.wait()
        cik = ticker_to_cik(ticker)  # via scripts/ticker_to_cik.py
        # GET /api/xbrl/companyfacts/CIK{cik:010d}.json
        # parse companyfacts JSON → extract per-quarter facts → compute_ratios → list[FundamentalsRow]
        ...

    def health_check(self) -> bool:
        # GET /submissions/CIK0000320193.json (AAPL) → check 200
        ...
```

### 4.4 XBRL parser + ratio computation

```python
# workbench_api/data/xbrl_parser.py
"""Compute B025 fixture-required ratios from SEC companyfacts JSON.

8 ratios per ticker per fiscal_quarter:
  roe              = NetIncomeLoss / StockholdersEquity (avg)
  gross_margin     = (Revenues - CostOfGoodsAndServicesSold) / Revenues
  fcf_yield        = (CashFlowFromOperating - CapitalExpenditures) / MarketCap
  debt_to_assets   = LongTermDebt / Assets
  pe               = MarketCap / NetIncomeLoss_TTM
  pb               = MarketCap / StockholdersEquity
  ev_ebitda        = (MarketCap + LongTermDebt - Cash) / EBITDA
  earnings_yield   = NetIncomeLoss_TTM / MarketCap

Formulas locked per strategy doc §6 (永久边界 (j) — changes require new batch).
MarketCap source: latest Tiingo close × shares_outstanding from XBRL.
"""
```

### 4.5 ticker_to_cik 映射

```python
# scripts/ticker_to_cik.py
"""Map B025 us_quality_momentum 30-50 ticker → SEC CIK.

Source: SEC公开 ticker → CIK map at
https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&output=atom

Cache result in workbench_api/data/fixtures/sec_edgar_responses/ticker_cik_map.json
to avoid repeated fetches. Manual one-shot script run rebuilds the cache.
"""
```

### 4.6 backfill_fundamentals.py（主 driver）

```python
# scripts/backfill_fundamentals.py
"""One-shot historical backfill: SEC EDGAR → vendor + unified layers.

Usage: python scripts/backfill_fundamentals.py --from 2014-01-01 --to 2026-05-26 \
         --tickers <comma-sep> | --universe us_quality

Default universe = scripts/universe_us_quality.py (B025 us_quality 30-50 ticker).

For each ticker:
1. ticker → CIK (cached map)
2. Fetch companyfacts JSON via SECEDGARFundamentalsLoader (rate-limit 10/sec)
3. Write raw to data/snapshots/fundamentals/sec_edgar/{cik}/{accession}/...
4. Compute 8 ratios per quarter via xbrl_parser.compute_ratios
5. Append unified data/snapshots/fundamentals/unified/fundamentals.csv (sort + dedupe by (ticker, fiscal_quarter))

Validate: total rows = ≥ ticker_count × 40 quarters (10y).
"""
```

### 4.7 PIT fundamentals loader

```python
# trade/data/loader.py 改动（加在 B028 既有 PIT load_prices 旁）
def load_fundamentals(
    tickers: list[str],
    as_of_date: date,
) -> dict[str, FundamentalsRow | None]:
    """Load latest fundamentals visible at as_of_date for each ticker.

    PIT enforcement: for each ticker, return the most recent FundamentalsRow
    where report_date + 1 trading day <= as_of_date (= effective_date).
    If no such row, return None for that ticker.

    Source priority:
    1. data/snapshots/fundamentals/unified/fundamentals.csv if exists
    2. Fall back to B025 fixture path (existing test data)
    """
    source_path = Path("data/snapshots/fundamentals/unified/fundamentals.csv")
    if source_path.exists():
        df = pd.read_csv(source_path)
        df["report_date"] = pd.to_datetime(df["report_date"]).dt.date
        df["effective_date"] = df["report_date"].apply(
            lambda d: d + business_days(1)
        )
        df = df[df["effective_date"] <= as_of_date]  # PIT filter
        # for each ticker, keep latest by effective_date
        latest = df.sort_values("effective_date").groupby("ticker").tail(1)
        return {t: build_row(row) for t, row in latest.set_index("ticker").iterrows()}
    else:
        # fall back to B025 fixture
        ...
```

## 5. Feature 拆分

### F001 — SEC EDGAR client + XBRL parser + ratio computation（generator，3-4 天）

**Acceptance：**

(1) 新建 `workbench_api/data/fundamentals_loader.py`：抽象基类 `FundamentalsLoader` + dataclass `FundamentalsRow`（B025 11 列 schema 严格一致）

(2) 新建 `workbench_api/data/sec_edgar_loader.py`：`SECEDGARFundamentalsLoader`：
- BASE_URL = `https://data.sec.gov`
- User-Agent header 含 `SEC_EDGAR_CONTACT_EMAIL`（缺时 raise RuntimeError）
- `httpx.Client` 30s timeout
- `SimpleRateLimit(10, period_sec=1.0)` 限速
- `fetch_quarterly_fundamentals` 调 companyfacts API + parse JSON + compute_ratios → list[FundamentalsRow]
- `health_check` GET AAPL submissions 200

(3) 新建 `workbench_api/data/xbrl_parser.py`：8 ratio 计算 函数（公式锁定 strategy doc §6 + 永久边界 (j)）

(4) `workbench_api/config.py` 加 `SEC_EDGAR_CONTACT_EMAIL` 读取

(5) `.env.example` 加 `SEC_EDGAR_CONTACT_EMAIL=research@example.com`（注释说明 SEC 政策必含）

(6) 新建 `workbench_api/data/fixtures/sec_edgar_responses/`：
- `aapl_companyfacts.json` 抽样真实响应（AAPL 测试用）
- `nvda_companyfacts.json` 抽样真实响应（NVDA 测试用）
- `ticker_cik_map.json` B025 us_quality 30-50 ticker → CIK 映射 cache

(7) 若引入新 dep（如 `lxml` for XML parsing），按 v0.9.29 §12.8 加 `[project].dependencies` + `CRITICAL_RUNTIME_DEPS`（若仅用 stdlib `xml.etree.ElementTree` + `json` + `httpx` 则不需新 dep）

(8) `deploy.sh` 加 pre-flight check：`if [ -z "${SEC_EDGAR_CONTACT_EMAIL}" ]; then echo "SEC_EDGAR_CONTACT_EMAIL missing" && exit 1; fi`（v0.9.25 §12.5 模式）

(9) pytest 新增 ≥12 测试：
- `FundamentalsLoader` 抽象 instantiation 失败
- `SECEDGARFundamentalsLoader` 缺 contact email → raise RuntimeError 含修复指引
- `health_check` mock httpx 200 → True / 403 (无 UA) → False
- `fetch_quarterly_fundamentals` mock AAPL companyfacts → 解析 4 quarters
- mock 5xx → 3 次重试 + alert log
- mock 429 → rate limit 等待
- rate limiter 10/sec 强制（mock time，断言 11 个调用 > 1 sec）
- xbrl_parser 8 ratio 每个独立函数测试（用 AAPL 抽样数据）
- ratio 边界 case（零分母 → NaN / inf 处理；missing field → ValueError）
- ticker_cik_map.json 含 B025 universe 全部 30-50 ticker
- User-Agent header 含 SEC_EDGAR_CONTACT_EMAIL（mock httpx 拦截 header）
- FundamentalsRow dataclass frozen + slots + 11 字段

(10) Gates：
- `pytest tests` ≥304 baseline (B028) + ≥12 = ≥316 passed
- `ruff check .` exit=0
- `mypy workbench_api tests` exit=0
- frontend 不动 vitest ≥166 不破

(11) **不动**：
- B027/B028 既有 `tiingo_loader.py` / `yfinance_loader.py` / `cost_guard.py` / `snapshot_loader.py`
- strategy 代码 / B025 fixture
- B026 banner / production deploy

### F002 — Backfill driver + storage 填充 + universe 配置（generator，3-4 天）

**Acceptance：**

(1) 新建 `scripts/backfill_fundamentals.py`：
- argparse `--from --to --tickers | --universe us_quality`
- 默认 `--universe us_quality` 调用 `scripts/universe_us_quality.py`
- 对每 ticker 调 `SECEDGARFundamentalsLoader.fetch_quarterly_fundamentals`（rate limit 自动）
- 写 vendor raw：`data/snapshots/fundamentals/sec_edgar/<CIK>/<accession>/{10-K,10-Q,metadata.json,parsed_ratios.json}`
- append unified：`data/snapshots/fundamentals/unified/fundamentals.csv`（sort + dedupe by (ticker, fiscal_quarter) + atomic write）
- validate：行数 ≈ ticker_count × 40 quarters ± 10%

(2) 新建 `scripts/universe_us_quality.py`：固定 list 与 B025 fixture `data/fixtures/us_quality_momentum/universe.csv` ticker 列一致（30-50 ticker）

(3) 新建 `scripts/ticker_to_cik.py`：one-shot 脚本调 SEC `https://www.sec.gov/cgi-bin/browse-edgar?...` 拿 ticker → CIK 映射，cache 到 `workbench_api/data/fixtures/sec_edgar_responses/ticker_cik_map.json`

(4) **本批次手动跑一次 backfill**：`python scripts/backfill_fundamentals.py --from 2014-01-01 --to 2026-05-26 --universe us_quality`；产物 30-50 vendor 目录 + 1 unified fundamentals.csv（≥1200 行 = 30 ticker × 40 quarter）入 `data/snapshots/fundamentals/`（不入 git，commit message / signoff 记录 row count）

(5) **跑一次抽样 PIT 验证**：抽 3-5 ticker × 5 fiscal_quarter，断言：
- `fiscal_quarter end_date < report_date`（filing 在 quarter 结束后）
- `report_date >= fiscal_quarter_end + 30 days`（≥30d 披露延迟，B025 spec §4.1 enforcement）
- 报告存为 `docs/test-reports/B029-pit-validation-2026-MM-DD.md`

(6) pytest 新增 ≥10 测试：
- backfill_fundamentals argparse + 默认值
- universe_us_quality 含 ≥30 ticker（与 B025 fixture universe 一致 assertion）
- mock SECEDGARFundamentalsLoader → backfill 写 vendor + unified schema correct
- sort + dedupe by (ticker, fiscal_quarter)
- row count ≥ ticker_count × 40
- atomic write
- ticker_to_cik 输出 cache JSON schema
- partial unified 文件 merge 不重复
- PIT spot check：`report_date >= fiscal_quarter_end + 30d`
- B025 schema (11 列) 严格一致 assertion

(7) Gates：
- `pytest tests` ≥316 + ≥10 = ≥326 passed
- `ruff` + `mypy` 清
- 本机跑通 30-50 ticker backfill（SEC 10 req/sec 下 ~5-10 分钟跑完）
- PIT validation 报告通过

(8) **不动**：
- F001 已完成的接口
- B027/B028 既有 loader / scripts

### F003 — PIT fundamentals loader + strategy 读路径准备（generator，2-3 天）

**Acceptance：**

(1) 改 `trade/data/loader.py`：
- 加 `load_fundamentals(tickers: list[str], as_of_date: date) -> dict[str, FundamentalsRow | None]`
- PIT enforcement：`effective_date = report_date + 1 business day`；返回每 ticker 最新 `effective_date <= as_of_date` 的行
- 读 `data/snapshots/fundamentals/unified/fundamentals.csv` if exists；else fall back B025 fixture
- docstring 明示 PIT 语义 + effective_date 计算

(2) **不动** strategy 代码（B025 us_quality_momentum 5 因子 / Master Portfolio / 其他 sleeve；F003 仅准备 loader infrastructure；切换是 B030 责任）

(3) pytest 新增 ≥10 测试：
- `load_fundamentals(['AAPL'], as_of=2020-03-01)` 返回 2019-Q3 或之前（PIT spot check）
- `load_fundamentals(['NVDA'], as_of=2020-04-01)` 返回 2019-Q4（filing date < 2020-04-01）
- unified.csv 存在读 unified；不存在 fall back B025 fixture
- 既有 B025 us_quality_momentum 5 因子测试 全过（不破）
- as_of_date 未来 → 限到今天
- as_of_date < earliest data → 返回 dict 全 None
- 多 ticker 一次 load
- 某 ticker 完全缺数据 → 该 ticker = None，其他 ticker 正常
- effective_date 计算正确（business_days(1) 跳周末）
- PIT spot check 3-5 random (ticker, as_of_date) tuple

(4) Gates：
- `pytest tests` ≥326 + ≥10 = ≥336 passed
- `ruff` + `mypy` 清
- **B025 既有回测 deterministic 不变**（pytest 跑 us_quality_momentum 回测断言 fixture 路径下数字不变；B025 既有测试 100% 通过）

(5) **不动**：
- strategy 代码 / Backtest engine
- workbench backend endpoints
- Frontend / UI

### F004 — Codex L1 + L2 真 VM 验收 + signoff（codex，1-2 天）

**L1 (CI 内)：**

- F001-F003 全部 generator 验收脚本跑通：backend / trade pytest ≥336 / ruff / mypy / alembic up-down OK
- Frontend 不动既有 vitest ≥166 + Playwright ≥38 不破
- safety regression 全绿（含 v0.9.29 §12.8.1 `test_runtime_dependencies_pinned.py` 若 F001 加了 lxml 等新 dep 含之守门；若无新 dep 既有测试通过）
- artifact grep `SEC_EDGAR_CONTACT_EMAIL` value / SEC EDGAR endpoint 字面值 0 命中
- CI 完全离线：`pytest --no-network` 全过（mock fixture）

**L2 (真 VM)：**

1. Production VM 不动（本批次纯离线 backfill + loader infra）；本批次产品代码改动落 `trade/` + `workbench_api/data/` + `scripts/`，**全部已在 v0.9.27 §12.7.1 修复后的 paths-trigger 内**（workbench-backend.yml `paths: trade/** scripts/** workbench/backend/**`），自然触 CI → Deploy；不需 dispatch 兜底
2. `curl https://trade.guangai.ai/api/health` 仍 200 + version SHA 与 main HEAD 等价
3. `curl https://trade.guangai.ai/api/debug/recent-errors` 返回 `{"count":0,"records":[]}`
4. B026 banner 仍 enable 显示 不破
5. Backfill 数据本机验证：
   - `find data/snapshots/fundamentals/sec_edgar/ -type d -mindepth 1 -maxdepth 1 | wc -l` ≈ 30-50（CIK 目录数 = ticker 数）
   - `wc -l data/snapshots/fundamentals/unified/fundamentals.csv` ≥ 30 × 40 = 1200 rows
   - `python -c "from trade.data.loader import load_fundamentals; from datetime import date; r=load_fundamentals(['AAPL'], date(2026,5,1)); print(r['AAPL'].fiscal_quarter)"` 输出最近 quarter
   - PIT spot check：`load_fundamentals(['AAPL'], as_of=date(2020,3,1))` 返回 ≤ 2020-Q1 之前的某 quarter
6. PIT validation 报告通过（`docs/test-reports/B029-pit-validation-2026-MM-DD.md` 验 `report_date >= fiscal_quarter_end + 30d`）
7. Production HEAD ≡ main HEAD（v0.9.25 §Production/HEAD 等价性）+ Post-signoff Deploy 段（v0.9.27 / §12.7.1）

**Signoff：**

- `docs/test-reports/B029-fundamentals-snapshot-signoff-2026-MM-DD.md` 用 framework/templates/signoff-report.md
- `docs/screenshots/B029-fundamentals/` ≥3 PNG：data/snapshots/fundamentals/ ls 结构 + AAPL fundamentals.csv 抽样 + PIT validation 报告

**Framework 候选：**

预期无重大 framework learning（v0.9.29 §12.8 已守门新 dep；v0.9.27 §12.7.1 已修 paths-trigger）。若 fix-round 出现 SEC EDGAR User-Agent ban / XBRL schema 变化 / ratio 计算公式与 strategy doc §6 不符等意外，记录 signoff §Framework Learnings。

## 6. 不做的事（YAGNI）

- ❌ **strategy 代码切真数据**（留 B030）— B029 仅准备 loader infra
- ❌ **Master ETF / ADR proxy fundamentals**（ETF 本身无 ratio；ADR 走 SEC 20-F 后续可加，但本批次仅 B025 us_quality universe）
- ❌ **港股原生数据 / 非 SEC 财务源**（永久边界）
- ❌ **每日 EOD cron**（推迟）
- ❌ **forecast / 财务预测**（永久边界 + AI 边界）
- ❌ **Frontend / UI 改动**
- ❌ **新 alembic migration**（本批次不动 DB schema；与 B028 一样走文件系统 unified.csv）
- ❌ **Production redeploy 强制**（本批次产品代码改动 trade/ + scripts/ 在 paths-trigger 内自然触发 deploy；不强求 dispatch）
- ❌ **SEC Python SDK 引入**（仅 stdlib + httpx；XBRL parse 用 ElementTree 或 json companyfacts；避免 vendor SDK lock-in）
- ❌ **完整 XBRL schema validation**（仅 parse B025 需要的 8 ratio 涉及字段；其他 XBRL fact 不动）

## 7. 验收门槛汇总

| 门槛 | F# 责任 |
|---|---|
| `FundamentalsLoader` 抽象基类 + `FundamentalsRow` 11 列 schema 与 B025 fixture 严格一致 | F001 |
| `SECEDGARFundamentalsLoader` 实现 + User-Agent 含 contact email + rate limit 10/sec | F001 |
| `xbrl_parser.py` 8 ratio 计算公式锁定 strategy doc §6 | F001 |
| `.env.example` 含 SEC_EDGAR_CONTACT_EMAIL + deploy.sh secret check | F001 |
| ticker_cik_map.json 含 B025 universe 全部 30-50 ticker | F001 |
| 若引入新 dep（lxml 等）走 v0.9.29 §12.8 规约 | F001 + F004 |
| `scripts/backfill_fundamentals.py` driver + `universe_us_quality.py` | F002 |
| `data/snapshots/fundamentals/{sec_edgar,unified}/` 双层（继承 B028 架构）| F002 |
| 本机跑通 30-50 ticker × 10+ 年 backfill；≥1200 rows unified | F002 |
| PIT validation 报告（`report_date >= fiscal_quarter_end + 30d`）| F002 |
| `trade/data/loader.py` 加 `load_fundamentals(tickers, as_of)` PIT enforcement | F003 |
| pytest 总数 ≥336 + B025 既有回测 deterministic 不变 | F003 |
| Backend / trade pytest + ruff + mypy 清 | F001+F002+F003+F004 |
| Frontend 不破既有 vitest ≥166 + Playwright ≥38 | F004 |
| L2 backfill 数据本机验证（30-50 CIK 目录 + unified ≥1200 rows + PIT spot check）| F004 |
| Production HEAD ≡ main HEAD + Post-signoff Deploy 段；本批次因 paths-trigger 已修自然触发 deploy 不需 dispatch | F004 |
| `/api/debug/recent-errors` count=0 + B026 banner 仍 enable | F004 |
| Signoff 报告 framework/templates/signoff-report.md 全段 | F004 |

## 8. 参考文档

- `docs/product/implementation-path-2026-05.md` §4 Phase 1 / §7 永久边界 / §8 Planner 接续 checklist / §9 spec 撰写要点
- `docs/product/data-source-evaluation-2026-05.md` §4 财务数据源 / §6.2 SEC EDGAR 首选 + EODHD 降级
- `docs/product/roadmap-2026-05.md` Stream 1.C
- `docs/specs/B025-us-quality-momentum-satellite-spec.md` §4.1 fixture fundamentals.csv schema（B029 unified 与此严格一致）+ §6 8 因子计算公式（strategy doc §6）
- `docs/specs/B027-real-data-snapshot-foundation-spec.md` SnapshotLoader 抽象模式（B029 FundamentalsLoader 镜像）
- `docs/specs/B028-real-data-backfill-spec.md` storage 双层架构 + PIT loader pattern（B029 镜像）
- `docs/strategy/03-us-quality-momentum.md` §6 8 因子计算公式（**永久边界 (j) 锁定**）
- `framework/STRUCTURE.md` framework/ 目录语义
- `framework/harness/planner.md` §"AI 边界精细化（v0.9.28）" §"Cloud-deploy spec checklist v0.9.27 扩展 (e)"
- `framework/harness/generator.md` §10 GHA / §12.5-12.7 deploy + **§12.7.1 paths-trigger gap（B028 微沉淀）** / §12.8 pyproject runtime vs dev dep（v0.9.29）/ §14 FastAPI 运行时观测
- `framework/templates/signoff-report.md` v0.9.27 §Post-signoff Deploy
- SEC EDGAR API docs: https://www.sec.gov/edgar/sec-api-documentation
- SEC EDGAR User-Agent policy: https://www.sec.gov/os/accessing-edgar-data

## 9. 风险与缓解

| 风险 | 缓解 |
|---|---|
| SEC EDGAR User-Agent 缺失 / 错误 → ban IP 30 天 | F001 acceptance 强制 SEC_EDGAR_CONTACT_EMAIL env + RuntimeError 含修复指引 + deploy.sh pre-flight check |
| Rate limit 10/sec 违反 → ban IP | SimpleRateLimit lib 强制；测试断言 11 个调用 > 1 sec |
| XBRL schema 不稳定（SEC 历史 filings XBRL 格式有变迁）| 使用 companyfacts API（SEC 预 parse JSON 已统一）+ 异常 → ValueError 含 ticker/year context；少量失败 ticker 报警不阻塞批次 |
| Ratio 计算公式与 strategy doc §6 不符 → 数字漂移 | **永久边界 (j)** 锁定 strategy doc §6 公式；pytest 用 AAPL/NVDA 抽样数据验证每 ratio 与手算一致 |
| ticker → CIK 映射缺失 / 错误 | ticker_cik_map.json fixture 守门 + F002 acceptance 含 B025 全 universe assertion；CIK 错触发 SEC 404 → ValueError |
| effective_date business_days 计算复杂 | 用 `pandas.tseries.offsets.BusinessDay` 或 numpy busday_offset；单测覆盖周末 / 假期边界 |
| B025 fundamentals.csv schema 11 列严格一致 | F001+F002 acceptance 明示 assertion + 跑既有 B025 测试不破 |
| SEC EDGAR 偶发 5xx / 网络中断 | 3 次重试 + backoff（B027 既有 pattern 复用）+ atomic write 防部分写 |
| Master/ADR proxy 后续要 fundamentals | 本批次架构 vendor-agnostic（FundamentalsLoader 抽象）；后续加 ADR 仅需新 batch 扩 universe，不重构 |
| 新 dep (lxml) 引入触发 v0.9.29 §12.8 守门未通过 | F001 acceptance 明示走规约（若需引入）；若仅 stdlib + httpx 则不触 |

## 10. 与既有批次的边界

- 不动 B011 Master Portfolio / B025 us_quality_momentum 5 因子代码 + fixture / B013 regime adaptive / B016 HRP
- 不动 B023 manual execution / B022 workbench 6 表 / B021 cloud deploy
- 不动 B024 i18n / B025 双语 disclaimer
- **不动 B026 banner**（B030 done 时关）
- 不动 B027 既有 Tiingo loader / cost guard / tiingo_budget_log；本批次 SEC EDGAR 免费不计 budget guard
- 不动 B028 既有 yfinance loader / backfill_prices.py / universe_master.py / prices unified；本批次 fundamentals 独立路径
- 不动 strategy 代码 / Recommendations / Risk Panel / Reports / Frontend

## 11. 后续批次（不在 B029 范围）

按 implementation-path §4 顺序：

- **B030 = Phase 1 / Stream 1.D** 全 sleeve 切真数据（prices via B028 unified + fundamentals via B029 unified）+ Master/sleeve strategy 代码改读路径 + 回测重跑 + reports/ 加 fixture vs real 对比 → **里程碑 A Layer 0→1**

**B030 done 阶段**: by acceptance 修改 `.env.production` `NEXT_PUBLIC_SYNTHETIC_DATA_BANNER=false` 让 B026 banner 自然下线。

**B029 done 后可启动的并行 Stream**：
- Stream 2 News ingest（B033+）/ Stream 3 LLM gateway（B031+）与 Phase 1 完全并行（已有 implementation-path §3 依赖图）

---

> 本 spec 完成后，progress.json status=building，current_sprint=F001，Generator 接 FundamentalsLoader 抽象 + SEC EDGAR client + xbrl_parser 实现。
