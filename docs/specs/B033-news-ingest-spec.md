# B033 — News Ingest Framework（Phase 2 / Stream 2.A）

> Status：active (planning → building)
> Owner：Generator (F001-F003) + Codex (F004)
> Predecessor：B032 (AI Safety Eval Framework) — done 2026-05-28
> 估时：1 个中型批次（4 features）
> 范围分类：post-MVP product alignment batch（**Phase 2 / Stream 2.A**；属 `docs/product/implementation-path-2026-05.md` §4 第八个 batch；本批次属 Layer 1.5 News ingest 基础设施）

## 1. 目标

为 Stream 2 News→AI advisor 整合打基础：把两条免费 + 高质量 news source（SEC EDGAR filings + Yahoo Finance RSS）以 **fixture-first / metadata-only schema** 接入 workbench backend，提供统一 `NewsRepository` + 两个 source adapter + CLI 手动入仓入口。

**不做**：
- FRED 宏观指标（B035 Stream 2.C 统一处理；FRED 不是 news，属 market context）
- News ↔ ticker 关联 / topic tagging / Cohere embedding（B034 Stream 2.B）
- Recommendations / Reports 页 news 渲染（依赖 B034 后续 UI 批次）
- Scheduled cron / FastAPI APScheduler / GitHub Actions scheduled workflow（仅 CLI manual trigger；自动 cron 等 B034 上线 news↔ticker 后再决议）
- 内联 raw filing/article text 入 DB（仅 metadata + snapshot path；防表膨胀）
- AI advisor endpoint / safety eval runtime check（B032 已 CI gate / B036 整合）
- Bloomberg RSS / NewsAPI / Tiingo News（`data-source-evaluation-2026-05.md` §5 候选；本批次仅二源起步）

## 2. 决策矩阵（2026-05-28 用户已批）

| 维度 | 决策 |
|---|---|
| Source 范围 | **2 source**：SEC EDGAR filings + Yahoo Finance RSS（FRED 留 B035 Market Context） |
| SEC EDGAR form types | **10-K / 10-Q / 8-K + Form 4**（季报 / 年报 / 重大事件 + 内部人交易） |
| Ticker universe | **B025 US Quality 27 real tickers + 4 master ETFs (SPY / QQQ / EFA / EEM)**；synthetic ZQ* tickers (3) 跳过（与 B029 同 pattern） |
| Ticker association | **不做** — 留 B034 embedding 时统一处理；schema 预留 `ticker_mentions JSONB` 字段但本批次留空 / `ticker` 单列存 primary ticker |
| Production ingest | **Adapter + CLI manual trigger**；不上 cron / APScheduler / GitHub Actions scheduled workflow；生产用 `python -m workbench_api.news.cli fetch --source edgar/yahoo --since YYYY-MM-DD` 手动跑 |
| Schema 调度 | **Metadata + snapshot path** — DB 只存 metadata 列；raw filing/article body 落 `data/snapshots/news/{source}/{YYYY-MM-DD}/{filing_id}.{json,htm,xml}` |
| Feature 拆分 | **4 features**：F001 schema + Repository + migration / F002 SEC EDGAR adapter / F003 Yahoo RSS adapter + CLI / F004 codex L1+L2+signoff |
| Secret | **不引入新 secret**；复用 `SEC_EDGAR_CONTACT_EMAIL`（B029）用于 EDGAR User-Agent；Yahoo Finance RSS 无需 key |
| CI 策略 | **fixture-first 离线**：CI 用 `data/fixtures/news/edgar-sample-*.json` + `yahoo-sample-*.xml`；不调外部 API |
| Cost | **¥0/月**（SEC EDGAR + Yahoo RSS 均免费；rate limit respect 即可）|
| Layer 1.5 准备 | 仅是 news raw ingest infra；不触 AI logic（永久边界 v0.9.28 5 子条本批次不触发） |
| 新增产品边界 | **(p)** News raw text 仅落 snapshot path 不内联 DB / **(q)** News ingest 默认 production-disabled（无 cron / 无 scheduler module） |

## 3. 永久硬边界（B033 起继续 enforced）

继承 B012-B032 + framework v0.9.31 全部边界：

- **系统层：** no-broker SDK / no live trading URL / no-credential（`SEC_EDGAR_CONTACT_EMAIL` 走 secret）/ no-auto-execution / 多用户禁 / Cloud SQL 禁 / same-origin `/api/*` / auth-gated / Repository pattern
- **UI 层：** no-execution buttons + 中文等价禁词 / Order ticket Markdown 双语 disclaimer / B026 banner decommissioned（v0.9.31 §16 守门）
- **数据 / CI 层：** fixture-first 离线 CI（**本批次：fixture EDGAR JSON + Yahoo RSS XML；CI 不调真 endpoint**）/ pyproject runtime-vs-dev hygiene（v0.9.29 §12.8 — feedparser 必须 runtime dep）/ paths-trigger 已含 `trade/` + `scripts/` + `pyproject.toml`（v0.9.27 §12.7.1，本批次新增 `workbench/backend/workbench_api/news/**` + `data/fixtures/news/**`）
- **AI 边界（v0.9.28，本批次不触发但 spec 列出）：** 5 子条（a-e）；本批次仅是 news raw ingest infra，不触发任何 LLM 调用；B034 起 news→Cohere embedding 才首次触发
- **B027/B029/B030/B031/B032 继续 enforced**
- **B030 起 (k) Layer 状态不可逆向滑落**：本批次保持 Layer 1.5；不引入回滑
- **B031 起 (l)(m) / B032 起 (n)(o) 继续**
- **新增产品边界（B033 起）：**
  - **(p) News raw text 仅落 snapshot path 不内联 DB：** `news` 表只存 metadata（id / source / source_id / url / title / summary / ticker / form_type / published_at / fetched_at / snapshot_path / content_sha256 / ticker_mentions）；raw filing/article body 文件落 `data/snapshots/news/{source}/{YYYY-MM-DD}/`，永远不入 DB column。守门 pytest（`tests/safety/test_news_schema_metadata_only.py`）通过 `inspect(News.__table__).columns` + `sqlalchemy.types.TEXT` 检查 `news` 表 schema 不含 `raw_text` / `body` / `content` TEXT column；migration 加新 raw text column 必走 PR review。
  - **(q) News ingest 默认 production-disabled：** 本批次不上 cron / 不上 scheduled FastAPI job / 不上 GitHub Actions scheduled workflow；生产仅 CLI manual trigger 入口。`workbench_api/news/scheduler.py` 不存在；APScheduler 不引入；存在即守门测试（`tests/safety/test_news_no_scheduler.py`）fail。B034 上线 news↔ticker 后再决议是否启用 cron。

## 4. 技术架构

### 4.1 文件结构

```
workbench/backend/workbench_api/
├── db/
│   ├── models/news.py                       # NEW
│   └── repositories/news.py                 # NEW
├── db/migrations/versions/
│   └── 0005_b033_news.py                    # NEW (alembic up/down)
└── news/                                    # NEW module
    ├── __init__.py
    ├── adapters/
    │   ├── __init__.py
    │   ├── base.py                          # NewsAdapter Protocol + NewsItem DTO
    │   ├── sec_edgar.py                     # SEC EDGAR (10-K/10-Q/8-K + Form 4)
    │   └── yahoo_rss.py                     # Yahoo Finance RSS
    ├── snapshot.py                          # NewsSnapshotWriter
    └── cli.py                               # python -m workbench_api.news.cli ...

data/
├── fixtures/news/                           # NEW (CI fixture)
│   ├── README.md
│   ├── edgar-sample-10k-AAPL.json
│   ├── edgar-sample-8k-NVDA.json
│   ├── edgar-sample-form4-MSFT.json
│   ├── yahoo-sample-AAPL.xml
│   └── yahoo-sample-SPY.xml
└── snapshots/news/                          # NEW (生产 raw text 落地；CI 不写入；.gitignore 已含 snapshots/)
    ├── README.md
    ├── sec_edgar/
    └── yahoo_rss/

workbench/backend/tests/
├── unit/
│   ├── test_news_repository.py              # NEW (F001)
│   ├── test_news_adapter_edgar.py           # NEW (F002)
│   ├── test_news_adapter_yahoo.py           # NEW (F003)
│   ├── test_news_snapshot.py                # NEW (F001)
│   └── test_news_cli.py                     # NEW (F003)
└── safety/
    ├── test_news_schema_metadata_only.py    # NEW (F001 — 永久边界 (p) 守门)
    └── test_news_no_scheduler.py            # NEW (F003 — 永久边界 (q) 守门)
```

### 4.2 News 表 schema

| 字段 | 类型 | 约束 | 备注 |
|---|---|---|---|
| `id` | UUID | PK | `uuid4()` in Python (服务端生成) |
| `source` | String(32) | NOT NULL, indexed | `"sec_edgar"` / `"yahoo_rss"` |
| `source_id` | String(128) | NOT NULL | EDGAR accession_number / Yahoo RSS GUID |
| `url` | String(512) | NOT NULL | canonical URL |
| `title` | String(512) | NOT NULL | filing/article title |
| `summary` | Text | NULL | RSS 含；EDGAR 取自 cover page |
| `ticker` | String(16) | NULL, indexed | 单 primary ticker（B033 单 ticker；多 ticker 留 ticker_mentions JSONB） |
| `form_type` | String(16) | NULL | `"10-K"` / `"10-Q"` / `"8-K"` / `"4"` / `null`（Yahoo RSS）|
| `published_at` | DateTime(tz=True) | NOT NULL, indexed | source 报告 publish time |
| `fetched_at` | DateTime(tz=True) | NOT NULL | 落库 time (server_default=now()) |
| `snapshot_path` | String(512) | NOT NULL | `data/snapshots/news/{source}/{YYYY-MM-DD}/{filing_id}.{json,htm,xml}` 相对项目根 |
| `content_sha256` | String(64) | NOT NULL | snapshot file body sha256 hex |
| `ticker_mentions` | JSONB | NULL | 本批次留空；B034 embedding 后填充 |

**Unique constraint:** `uq_news_source_source_id` over (`source`, `source_id`) — 同一 EDGAR accession 或 Yahoo RSS GUID 不重复入库。

**Indexes:**
- `ix_news_source` (`source`)
- `ix_news_ticker` (`ticker`)
- `ix_news_published_at` (`published_at`)
- + PK index on `id`

### 4.3 NewsAdapter Protocol

```python
# workbench_api/news/adapters/base.py
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

@dataclass(frozen=True, slots=True)
class NewsItem:
    source: str
    source_id: str
    url: str
    title: str
    summary: str | None
    ticker: str | None
    form_type: str | None
    published_at: datetime
    raw_body: bytes   # 待写 snapshot
    raw_ext: str      # "json" / "htm" / "xml"

class NewsAdapter(Protocol):
    source: str
    def fetch(self, *, ticker: str, since: datetime) -> Iterable[NewsItem]: ...
```

### 4.4 SEC EDGAR adapter（F002）

- 复用 B029 `SECEDGARFundamentalsLoader` 同款 User-Agent header（`SEC_EDGAR_CONTACT_EMAIL` 来源）+ rate limit（10 req/sec global token bucket）
- 用 universe loader（`scripts.universe_us_quality.US_QUALITY_REAL_TICKERS` + master ETFs hardcoded list — 4 ETFs 与 master portfolio universe 同步）
- Endpoint：`https://data.sec.gov/submissions/CIK{cik:010d}.json` 列 filings → 按 form_type 过滤 `{"10-K", "10-Q", "8-K", "4"}`
- 每条 filing fetch 主文档（10-K/10-Q/8-K = `.htm`；Form 4 = `.xml`）保存至 `data/snapshots/news/sec_edgar/{YYYY-MM-DD}/{accession_no}.{htm,xml}`
- Synthetic ZQ* ticker：log warn + skip（与 B029 §3 pattern 一致）
- 落库通过 `NewsRepository.save_if_new`（idempotent by `(source, source_id)`）

### 4.5 Yahoo Finance RSS adapter（F003）

- Endpoint：`https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US`
- 用 **feedparser**（runtime dep；F003 pyproject.toml 加入；遵循 v0.9.29 §12.8 runtime-vs-dev hygiene；若 type stubs 缺则 `# type: ignore[import-untyped]` 模仿 B032 yaml 处理）
- Yahoo RSS 无需 secret；User-Agent 通用即可
- 写 snapshot 到 `data/snapshots/news/yahoo_rss/{YYYY-MM-DD}/{sha256(guid)[:16]}.xml`
- 落库通过 `NewsRepository.save_if_new`

### 4.6 CLI 入口（F003）

```bash
# 全 source / 全 universe
python -m workbench_api.news.cli fetch --source all --since 2026-04-01

# 单 source / 单 ticker
python -m workbench_api.news.cli fetch --source edgar --ticker AAPL --form-types 10-K,10-Q
python -m workbench_api.news.cli fetch --source yahoo --ticker SPY --since 2026-04-01
```

argparse 入口；不依赖 FastAPI / scheduler。CLI 启动时 `mkdir -p data/snapshots/news/{source}/`。

### 4.7 Fixture（CI 离线）

`data/fixtures/news/` 含：
- ≥3 EDGAR sample：10-K (AAPL) + 8-K (NVDA) + Form 4 (MSFT)
- ≥2 Yahoo RSS sample：1 stock (AAPL) + 1 ETF (SPY)

Adapter test 用 `responses` 或 `respx` mock httpx 输入 fixture，断言落库正确 + snapshot 写入正确 + content_sha256 等价。

### 4.8 安全 / regression test 矩阵

| 测试 | 守门内容 |
|---|---|
| `tests/safety/test_news_schema_metadata_only.py` | 永久边界 (p) — `inspect(News.__table__).columns` 不含 `raw_text` / `body` / `content` TEXT column |
| `tests/safety/test_news_no_scheduler.py` | 永久边界 (q) — `workbench_api/news/scheduler.py` 不存在 / `workbench_api/news/` 下任意文件不 import `apscheduler` / `aiocron` / `schedule` |
| `tests/safety/test_critical_runtime_deps_pinned.py`（既有，B027 §12.8） | 扩集加 `feedparser`（F003 加入 runtime deps 时同步加 ast walker 检测） |
| `tests/safety/test_runtime_dependencies_pinned.py`（既有） | 同上 |

## 5. Feature 拆分

### F001 — News schema + Repository + migration（generator，1-2 天）

**Acceptance：**
1. `workbench_api/db/models/news.py`：`News` SQLAlchemy 2.0 declarative 模型按 §4.2 schema；`__tablename__ = "news"`；frozen/`__repr__` 与既有 `LLMBudgetLog` / `TiingoBudgetLog` 同款。
2. `workbench_api/db/repositories/news.py`：`NewsRepository(Repository[News, UUID])`，含：
   - `save_if_new(item: NewsItem, snapshot_path: str, content_sha256: str) -> News | None`（idempotent by `(source, source_id)`；已存在返回 None）
   - `list_by_ticker(ticker: str, *, since: datetime | None = None, limit: int = 100) -> list[News]`
   - `list_by_source(source: str, *, since: datetime | None = None, limit: int = 100) -> list[News]`
   - `get_by_source_and_source_id(source: str, source_id: str) -> News | None`
3. `workbench_api/db/migrations/versions/0005_b033_news.py`：alembic up/down `create_table news` + 3 indexes + uniqueconstraint；`down_revision = "0004_b031_llm_budget_log"`；`alembic upgrade head` 后 `alembic downgrade -1` 可逆。
4. `workbench_api/news/__init__.py` 模块 stub + `workbench_api/news/snapshot.py`：`NewsSnapshotWriter(root: Path = "data/snapshots/news")` 写文件 + 返回 relative path + content_sha256（`hashlib.sha256` of body bytes）。
5. `workbench_api/news/adapters/base.py`：`NewsItem` dataclass(frozen, slots) + `NewsAdapter` Protocol。
6. pytest ≥10：
   - `NewsRepository` CRUD + `save_if_new` 幂等性测试（连续两次同 `(source, source_id)` 第二次返回 None）
   - `list_by_ticker` / `list_by_source` 过滤 + since 过滤 + limit
   - `NewsSnapshotWriter` 写文件正确 + sha256 计算正确 + mkdir -p 行为
   - **永久边界 (p) 守门：** `tests/safety/test_news_schema_metadata_only.py` 通过 inspect News.__table__.columns 断言无 `raw_text` / `body` / `content` TEXT column
   - alembic up/down 测试（既有 `tests/unit/test_alembic_*` 模式）
7. Gates：backend pytest ≥528（B032 baseline 513 + ≥15）/ ruff exit=0 / mypy exit=0 / alembic upgrade head OK + downgrade -1 OK；frontend 不动 vitest ≥172 / Playwright ≥38 不破。
8. 不动：既有 B025-B032 表 / endpoint / strategy / Frontend / B026 banner decommissioned / AI Safety Eval workflow（无 paths overlap）。

### F002 — SEC EDGAR adapter（generator，2-3 天）

**Acceptance：**
1. `workbench_api/news/adapters/sec_edgar.py`：`SECEdgarNewsAdapter(NewsAdapter)`，`source = "sec_edgar"`。
2. `fetch(ticker, since)` 实现：
   - User-Agent 复用 `SEC_EDGAR_CONTACT_EMAIL`（B029 既有 pattern，从 `workbench_api.config.settings` 读）
   - Rate limit 10 req/sec（token bucket；复用 B029 `_sec_edgar_throttle` helper 或独立 module）
   - 调 `https://data.sec.gov/submissions/CIK{cik:010d}.json` 列 filings
   - 按 form_type ∈ {`"10-K"`, `"10-Q"`, `"8-K"`, `"4"`} + `published_at >= since` 过滤
   - 每条 filing 调主文档 fetch（`.htm` 或 `.xml`）→ build `NewsItem(raw_body=bytes, raw_ext="htm"/"xml")`
   - Synthetic ZQ* ticker：log warn + 返回空 iterator（与 B029 §3 一致）
3. CIK lookup：复用 B029 既有 cik resolver；本批次不重复实现。
4. `data/fixtures/news/edgar-sample-*.json`：≥3 fixture（10-K AAPL / 8-K NVDA / Form 4 MSFT），fixture 含 submissions JSON + 至少一份主文档 raw body sample。
5. pytest ≥8：
   - adapter mock httpx 返回 fixture → 落库（通过 NewsRepository）+ snapshot 正确写入
   - form type filter（fixture 含 13F / S-1 等 noise；断言被过滤）
   - rate limit respect（mock + 时间断言 ≥0.1s 间隔）
   - User-Agent header 含 `SEC_EDGAR_CONTACT_EMAIL`
   - Synthetic ZQ* ticker skip + log warn 断言
   - since 过滤：published_at < since 不入库
6. Gates：backend pytest ≥536（F001 后 528 + ≥8）/ ruff / mypy / **不引入新 secret**（grep `.env.example` / `config.py` / `deploy.sh` / `bootstrap-env.yml` 无新增条目）。
7. 不动：F001 schema / Yahoo adapter（留 F003）/ B029 既有 `SECEDGARFundamentalsLoader`（本批次走独立 `/submissions/...` endpoint，不修改 fundamentals 代码路径）/ B032 AI Safety Eval workflow。

### F003 — Yahoo Finance RSS adapter + CLI 入口（generator，2 天）

**Acceptance：**
1. `workbench_api/news/adapters/yahoo_rss.py`：`YahooRSSNewsAdapter(NewsAdapter)`，`source = "yahoo_rss"`。
2. `fetch(ticker, since)`：调 `https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US`；`feedparser.parse(httpx.get(...).content)`；published_at 来自 RSS `<pubDate>`。
3. `workbench/backend/pyproject.toml` runtime deps 加 `feedparser>=6.0,<7`（**v0.9.29 §12.8 runtime-vs-dev hygiene**：因 `workbench_api/news/adapters/yahoo_rss.py` 模块顶层 import）。
4. `tests/safety/test_critical_runtime_deps_pinned.py`：扩集加 `feedparser`（ast walker 已支持；只需 `_pinned` 字典加条目）。
5. `workbench_api/news/cli.py`：argparse `fetch` subcommand：
   - `--source` ∈ {`edgar`, `yahoo`, `all`}（默认 `all`）
   - `--ticker` 单 ticker 或省略（=全 universe）
   - `--since YYYY-MM-DD`（默认 30 天前）
   - `--form-types` 逗号分隔（仅 edgar 用；默认 `10-K,10-Q,8-K,4`）
   - Dispatch 到 `SECEdgarNewsAdapter.fetch` / `YahooRSSNewsAdapter.fetch`；落库 + snapshot
   - 启动时 `mkdir -p data/snapshots/news/{source}/`
6. `data/fixtures/news/yahoo-sample-*.xml`：≥2 fixture（AAPL + SPY）。
7. `data/snapshots/news/README.md`：说明目录用途 + 不入 git（`.gitignore` 已含 `data/snapshots/`，验证）+ 生产 CLI 入口说明 + B034 后续 cron 决议。
8. pytest ≥8：
   - Yahoo adapter mock httpx + feedparser fixture → 落库正确
   - CLI argparse 各 flag 解析
   - CLI dispatch `--source=all` 跑两 adapter
   - CLI dispatch `--source=edgar --form-types 10-K` 只过 10-K
   - **永久边界 (q) 守门：** `tests/safety/test_news_no_scheduler.py`：
     - `workbench_api/news/scheduler.py` 文件不存在
     - `workbench_api/news/` 下任意 `.py` 文件 import 不含 `apscheduler` / `aiocron` / `schedule`
   - feedparser deps test extended（`test_critical_runtime_deps_pinned`）
9. Gates：backend pytest ≥544（F002 后 536 + ≥8）/ ruff / mypy / **不引入新 secret** / Frontend 不动。
10. 不动：F001 schema / F002 EDGAR adapter / 既有 strategy / B031 LLMGateway / B032 AI Safety Eval workflow。

### F004 — Codex L1 + L2 真 VM 验收 + signoff（codex，1 天）

**Acceptance：**

**L1（CI 内）：**
- F001+F002+F003 全 generator 验收脚本跑通 — backend pytest ≥544 / ruff / mypy / alembic up/down OK
- 永久边界 (l)(m)(n)(o) 守门全过
- **永久边界 (p)(q) 守门全过：** `test_news_schema_metadata_only.py` + `test_news_no_scheduler.py`
- Frontend 不动 vitest ≥172 + Playwright ≥38 不破
- AI Safety Eval workflow 不破（本批次未触 LLM module，paths-trigger 不命中）
- safety regression 全绿（含 v0.9.29 §12.8 runtime deps + v0.9.30 §12.9 secret + v0.9.31 §16 §22）
- artifact grep `SEC_EDGAR_CONTACT_EMAIL` value / `AIGC_GATEWAY_API_KEY` value / 任何 raw filing text 泄漏 = 0 命中

**L2（真 VM）：**
1. Production VM 不动（本批次仅 schema migration alembic up + CLI 不上 cron）
2. `curl https://trade.guangai.ai/api/health` 200 + version SHA 与 `main` HEAD 等价
3. `curl https://trade.guangai.ai/api/debug/recent-errors` 返回 `{"count":0,"records":[]}`
4. B026 banner 仍 decommissioned 不破（HTML grep `'研究原型' / 'SyntheticDataBanner'` 0 hits in `/strategies` `/reports` `/recommendations` `/risk`）
5. **Production DB alembic head = `0005_b033_news`**（VM ssh + `alembic current` 验证）
6. Production HEAD ≡ `main` HEAD（v0.9.25 §Production/HEAD 等价性）
7. **Production VM 没有 `workbench_api/news/scheduler.py`** + crontab 无 news fetch entry + systemd 无 news fetch unit（永久边界 (q) L2 验证）
8. **Production VM `data/snapshots/news/` 目录存在但为空**（deploy 后 `mkdir -p`；本批次不跑 CLI fetch）
9. Post-signoff Deploy 段（v0.9.27 §21）

**Signoff：** `docs/test-reports/B033-news-ingest-signoff-2026-MM-DD.md` 用 `framework/templates/signoff-report.md`（含 v0.9.27 §Post-signoff Deploy + v0.9.31 §Decommission Checklist「本批次不含 decommission」 + §Production/HEAD 等价性）；`docs/screenshots/B033-news-ingest/` ≥2 PNG（CLI fetch dry-run 输出 + alembic current 显示 `0005_b033_news`）。

**Framework 候选：** 预期无重大；若 fix-round 出现 schema/migration / feedparser 类型 stubs / Yahoo RSS endpoint drift 等坑，记 signoff §Framework Learnings。更新 progress.json status→done / docs.signoff / evaluator_feedback。

## 6. 不做的事（YAGNI）

- FRED 宏观（B035 处理）
- News ↔ ticker / sleeve 关联 / topic tagging / Cohere embedding（B034）
- Recommendations / Reports 页 news 渲染（依赖 B034 后续 UI 批次）
- Scheduled cron / FastAPI APScheduler / GitHub Actions scheduled workflow（B034 上线后再决议）
- 内联 raw filing/article text 入 DB（永久边界 (p) 禁止）
- AI advisor endpoint / runtime safety check（B032 / B036）
- Bloomberg RSS / NewsAPI / Tiingo News（候选；本批次仅 2 source 起步）
- Form types 扩展（S-1 / 13F / Form D / 14A / 其他）— 后续按需补
- HK-China ADR ticker 扩展（BL-B011-S2 上线后再决议）
- News 表 partition / 历史 archive 策略（数据量 < 10K 行起步 不需要）
- News full-text search index（embedding 走 B034 vector index 路径，不走 PostgreSQL FTS）

## 7. 验收门槛汇总

| 维度 | 阈值 |
|---|---|
| backend pytest | ≥544（B032 baseline 513 + F001 ≥15 + F002 ≥8 + F003 ≥8）|
| ruff | exit=0 |
| mypy | exit=0 |
| alembic | upgrade head OK + downgrade -1 OK |
| frontend vitest | ≥172（不动）|
| frontend Playwright | ≥38（不动）|
| 永久边界 (l)(m)(n)(o) 守门 | 既有 grep tests 全过 |
| 新增永久边界 (p)(q) 守门 | `tests/safety/test_news_schema_metadata_only.py` + `tests/safety/test_news_no_scheduler.py` |
| 新增 runtime dep `feedparser` 守门 | `tests/safety/test_critical_runtime_deps_pinned.py` 含条目 |
| Production HEAD ≡ main HEAD | F004 L2 §Production/HEAD 等价性 |
| Production DB alembic head | F004 L2 = `0005_b033_news` |
| Production VM 无 scheduler | F004 L2 永久边界 (q) 检查 |
| /api/debug/recent-errors count | =0 |

## 8. 参考文档

- `docs/product/data-source-evaluation-2026-05.md` §5 News（Stream 2 范围 简提）+ §6.3 News（Stream 2 简定）
- `docs/product/roadmap-2026-05.md` §Stream 2 News / market context ingest §S2.A
- `docs/product/implementation-path-2026-05.md` §4 Phase 2 第八个 batch + §5 关键依赖图
- `docs/product/positioning-2026-05.md` §1.1 AI 角色与边界 5 子条 / §6.1 永久硬边界
- `docs/product/ai-safety-evals-2026-05.md` §2 β 无引用样本（B033 ingest 必须为 B036 advisor 提供可 cite 的 news_urls）
- `docs/specs/B029-fundamentals-snapshot-spec.md`（SEC EDGAR User-Agent + rate limit 模式 + synthetic ZQ* skip）
- `docs/specs/B031-llm-gateway-spec.md`（secret 三处接线 / Repository pattern 模式）
- `docs/specs/B032-ai-safety-eval-spec.md`（fixture-first / safety regression test 模式 / feedparser-style import 处理参照 yaml）
- `framework/STRUCTURE.md`
- `framework/harness/planner.md` / `generator.md` / `evaluator.md`
- `framework/templates/signoff-report.md`
- `framework/archive/proposed-learnings-archive-v0.9.29.md`（pyproject runtime-vs-dev hygiene §12.8）
- `framework/archive/proposed-learnings-archive-v0.9.30.md`（secret 三处接线）
- `framework/archive/proposed-learnings-archive-v0.9.31.md`（decommission checklist）

## 9. 风险与缓解

| 风险 | 严重度 | 缓解 |
|---|---|---|
| Yahoo Finance RSS endpoint deprecate / drift | M | Adapter 隔离 + 守门 fixture-first 离线 CI 不依赖真 endpoint；生产 fallback 仅是 manual CLI 不阻断 deploy；后续 B034 若发现 endpoint drift 由当时 batch fix |
| SEC EDGAR rate limit 触发 | L | 复用 B029 已验过的 rate limiter（10 req/sec）；本批次目标 universe ≤32 ticker × 4 form types × 季度 ≈ 128 req 总量；30s 内跑完 |
| feedparser deps 加入引起 mypy type stubs 缺失 | L | `# type: ignore[import-untyped]`（参考 B032 yaml 处理）；feedparser 是 ML 社区主流稳定库 |
| News 表 schema 后续 B034 ticker_mentions 改成多对多表 | M | F001 schema `ticker_mentions JSONB nullable`；B034 决议时若改 schema 不影响 production 数据（仍 backward compat 读 JSONB） |
| Synthetic ZQ* ticker skip 漏洞 | L | F002 测试覆盖；与 B029 §3 同 pattern |
| Production VM 已部署 没有 `data/snapshots/news/` 目录 | M | F003 CLI 启动时 `mkdir -p`；F004 L2 §8 验证目录存在 + 空 |
| feedparser 引入 LGPL 协议风险 | L | feedparser BSD 协议（不冲突）；F003 加 dep 时确认 license |
| 第三方 API 真实 endpoint 与 spec 假设漂移（参 B031 §F003 fix-round 1） | M | F002 实施时建议 generator 至少手 hit 一次真实 `https://data.sec.gov/submissions/CIK0000320193.json`（AAPL）+ Yahoo RSS feed 验证 JSON / XML envelope；写守门 unit test 锁住关键字段路径 |

## 10. 与既有批次的边界

- **不破 B029 SEC EDGAR Fundamentals：** 本批次 News adapter 复用 SECEDGARFundamentalsLoader User-Agent + rate limit 模式，但走独立 endpoint（`/submissions/CIK*.json` vs `/api/xbrl/...`）；不修改既有 B029 fundamentals 代码。
- **不破 B025 universe：** `scripts/universe_us_quality.py` 27 real + 3 synthetic 不动；News adapter 用同款 universe loader（避免 hardcode duplicate list）。
- **不破 B031 LLM Gateway：** 本批次 news ingest 不调 LLM；B034 News→Cohere embedding 时通过 `LLMGateway(task="news_embed")` 接入。
- **不破 B032 Safety Eval：** 本批次不触 LLM；AI Safety Eval workflow paths-trigger 不涉及 `workbench_api/news/`，不会触发。
- **不破 B026 banner decommissioned：** 本批次未改 frontend；HTML 4 protected pages 仍 BANNER_ABSENT。
- **不破 B027 Tiingo budget guard：** 本批次不调 Tiingo；不引入新 budget log 表（news 免费）。

## 11. 后续批次（不在 B033 范围）

- **B034（Stream 2.B）：** News ↔ ticker / sleeve 关联；Cohere multilingual embedding via `LLMGateway(task="news_embed")`；topic tagging；`ticker_mentions` JSONB 字段填充；Recommendations 页 news 列表渲染；本批次的 fixture / snapshot 可直接被 B034 测试套利用
- **B035（Stream 2.C）：** FRED 宏观（10y / VIX / CPI）+ Alpha Vantage free 指数（SPY / QQQ / DXY）；不同 source；不属 news；Home 页 market context 卡片
- **B036（Stream 3.C）：** AI advisor MVP；整合 B033 news + B034 ticker mention + B035 market context + B031 LLMGateway → 文本建议含 `news_urls` 引用；通过 B032 红队 15 样本（β 类样本 "无引用 hallucinate" 必依赖本批次 ingest）
- **后续 Decommission：** 本批次不含 decommission（无既有功能下线；v0.9.31 §Decommission Checklist 标「本批次不含 decommission」）
- **Cron 启用决议：** 等 B034 上线 news↔ticker 后再决议本批次的 ingest 是否上 GitHub Actions scheduled workflow（每日 8am UTC）。届时若启用须新增一条永久边界放宽 (q)。
