# B030 — Real Data Cutover（Layer 0→1 里程碑 A）

> Status：active (planning → building)
> Owner：Generator (F001-F003) + Codex (F004)
> Predecessor：B029 (Fundamentals Snapshot) — done 2026-05-26
> 估时：1-2 个中等批次（**Phase 1 终点；最大单批 — strategy 代码切真**）
> 范围分类：post-MVP product alignment batch（Stream 1.D / Phase 1 终点；属 implementation-path-2026-05.md §4 第五个 batch）
>
> **🎯 里程碑 A — Layer 0→1 达成**：本批次完成后 workbench 进入「research with real historical data」阶段，回测指标第一次有真实意义。

## 1. 目标

利用 B028 unified prices + B029 unified fundamentals（含本批次 F001 per-sector aliases 补完的全量），把 Master Portfolio 4 sleeve + B025 us_quality_momentum 的 **strategy 代码读路径**从 fixture 切到 unified 真数据，跑 fixture vs real 对比回测报告，关 B026 synthetic banner。

完成后达成 **里程碑 A Layer 0→1**：Production 上展示的 NAV / sleeve breakdown / Recommendations / Risk Panel / Reports 第一次基于真实历史数据，回测指标可作为真实参考。

## 2. 决策矩阵（2026-05-26 用户已批）

| 维度 | 决策 |
|---|---|
| 6 sector-structural 缺数据 ticker（BAC/JPM/V/LIN/NEE/PLD）| **B030 F001 同期加 per-sector ratio model + alias 细化** 补 backfill（B029 Soft-watch S1 解决路径）|
| Strategy 切换范围 | **Master Portfolio 4 sleeve + B025 us_quality_momentum 5 因子**全切；trade/data/loader.py 已在 B028 (load_prices) + B029 (load_fundamentals) 准备好读 unified |
| B026 banner 关闭 | **B030 F003 by acceptance 改 .env.production `NEXT_PUBLIC_SYNTHETIC_DATA_BANNER=false`**（按 **v0.9.30 §12.9** 三处接线规约：.env.example + .env.production + bootstrap-env.yml frontend env file）|
| F 拆分 | **4 features**：F001 per-sector aliases + 重跑 backfill / F002 sleeve strategy 切真 / F003 fixture-vs-real 对比 + banner 关 / F004 codex |
| Fixture vs real 对比报告 | **Master 4 sleeve + B025 us_quality 各独立 5 份报告**（Master 总 + momentum + risk_parity + us_quality + hk_china 各一份；含 fixture 回测指标 vs real 数据回测指标并排）|
| Fall back 策略 | **strategy 代码切到 unified；unified 缺数据时 fall back B025 fixture**（不破 既有 deterministic；trade/data/loader.py 已有 fall back 逻辑）|
| Production deploy | 本批次产品代码动 `trade/` + `workbench_api/data/` + `scripts/`（v0.9.27 §12.7.1 paths-trigger 内）+ `.env.production` 改（frontend redeploy 触发） |
| Layer banner 关闭后保留 disclaimer | B024 既有双语 disclaimer（Markdown reports）保留；只关 banner |

## 3. 永久硬边界（B030 起继续 enforced）

继承 B012-B029 + framework v0.9.30 全部边界：

- **系统层：** no-broker SDK / no live trading URL / no-credential / no-auto-execution / 多用户禁 / Cloud SQL 禁 / same-origin /api/* / auth-gated / Repository pattern
- **UI 层：** no-execution buttons + 中文等价禁词 / Order ticket Markdown 双语 disclaimer 永存 / **B026 banner 在本批次 by acceptance 关闭（仅 Layer 0→1 完成时关；若回退 Layer 0 须重开）**
- **数据 / CI 层：** fixture-first 离线 CI / pyproject runtime-vs-dev hygiene（v0.9.29 §12.8）/ cloud-deploy workflow_dispatch + chore commit 后 dispatch deploy（v0.9.27 §12.7 + §12.7.1 paths-trigger 已修）/ **production secret 三处接线铁律（v0.9.30 §12.9）— 本批次 banner env var 走 4 处接线**
- **AI 边界（v0.9.28，本批次不引入 AI）：** 5 子条
- **B027 起 (f)(g) + B029 起 (h)(i)(j)** 继续 enforced
- **本批次新增**：**(k) Layer 状态转换不可逆向滑落** — B030 done 后 Layer 1 状态稳定，若发现真数据严重 unreliable（如 SEC EDGAR 大范围 ratio 错误）必须新批次 spec 决议（不能 silent rollback fixture / 不能 silent 重开 banner）

## 4. 技术架构

### 4.1 文件结构

```
workbench/backend/workbench_api/data/                # 既有（B027/B028/B029）
├── snapshot_loader.py                # PriceBar / SnapshotLoader（B027）
├── tiingo_loader.py                  # B027
├── yfinance_loader.py                # B028
├── cost_guard.py                     # B027
├── fundamentals_loader.py            # B029
├── sec_edgar_loader.py               # B029
├── xbrl_parser.py                    # B029 — 【改 F001】加 SEC_CONCEPT_NAMES per-sector aliases
└── fixtures/                         # B029

scripts/                                # 既有（B028/B029）
├── backfill_prices.py                # B028
├── validate_snapshot.py              # B028
├── universe_master.py                # B028
├── backfill_fundamentals.py          # B029
├── universe_us_quality.py            # B029
├── ticker_to_cik.py                  # B029
└── compare_fixture_vs_real.py        # 【新增 F003】生成 fixture-vs-real 对比报告

data/snapshots/                         # 既有 + 本批次重跑
├── prices/{tiingo,unified}/          # B028
└── fundamentals/{sec_edgar,unified}/  # B029 — 【F001 重跑后 27 → 27（含 6 sector ticker 补全）】

trade/strategies/                       # 【改 F002】
├── master_portfolio.py               # 4 sleeve 配置 read path 切 unified
├── momentum.py                       # sleeve 改 load_prices unified
├── risk_parity.py                    # 同上
├── us_quality_momentum/              # 【改 F002】5 因子读 unified fundamentals
│   ├── factors.py                    # 改：读 unified fundamentals.csv via load_fundamentals
│   ├── signal.py                     # 改：load_prices unified
│   └── ...
└── hk_china_proxy.py                 # 同上

trade/portfolio/                        # 【改 F002 if needed】
├── master.py                         # Master Portfolio 4 sleeve 组合 / read unified
└── ...

reports/                                # 【新增 F003】
├── fixture_vs_real/
│   ├── master_portfolio_2026-MM-DD.md / .json
│   ├── momentum_2026-MM-DD.md / .json
│   ├── risk_parity_2026-MM-DD.md / .json
│   ├── us_quality_momentum_2026-MM-DD.md / .json
│   └── hk_china_proxy_2026-MM-DD.md / .json

workbench/frontend/.env.production       # 【改 F003】NEXT_PUBLIC_SYNTHETIC_DATA_BANNER=false
workbench/frontend/.env.example          # 【改 F003】保留 =true 注释默认值（本机 dev 仍 enable banner）
.github/workflows/bootstrap-env.yml      # 【改 F003】NEXT_PUBLIC_SYNTHETIC_DATA_BANNER=false 写入 production frontend env file
```

### 4.2 Per-sector ratio model + alias 细化

```python
# workbench_api/data/xbrl_parser.py 改动
"""B029 sector-structural 缺数据原因：金融 / 公用事业 / REIT 三类 sector
的 SEC XBRL concept 与一般工业/科技/消费/医疗 sector 不同。例如：

| 一般 sector | 金融 sector (BAC/JPM/V) | 公用事业 sector (NEE/LIN) | REIT (PLD) |
|---|---|---|---|
| LongTermDebt | LongTermDebt 或 LongTermDebtTotal | LongTermDebtNoncurrent | LongTermDebtCurrentAndNoncurrent |
| Revenues | InterestAndDividendIncomeOperating | Revenues | Revenues |
| CostOfGoodsAndServicesSold | InterestExpense | CostOfGoodsAndServicesSold | OperatingExpenses |
| StockholdersEquity | StockholdersEquity | StockholdersEquity | StockholdersEquity |

per-sector 应基于 universe.csv 的 gics_sector 列动态选 concept alias chain。
"""

# 加 SEC_CONCEPT_ALIASES per-sector 多层 fallback
SEC_CONCEPT_ALIASES_PER_SECTOR: dict[str, dict[str, list[str]]] = {
    "Financials": {
        "Revenues": ["InterestAndDividendIncomeOperating", "Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax"],
        "CostOfGoodsAndServicesSold": ["InterestExpense", "CostOfGoodsAndServicesSold"],
        "LongTermDebt": ["LongTermDebt", "LongTermDebtTotal", "LongTermDebtNoncurrent"],
        # ... 8 ratio 涉及的 concept 都加
    },
    "Utilities": {
        "LongTermDebt": ["LongTermDebtNoncurrent", "LongTermDebt", "LongTermDebtCurrentAndNoncurrent"],
        # ...
    },
    "Real Estate": {
        "LongTermDebt": ["LongTermDebtCurrentAndNoncurrent", "LongTermDebt"],
        "Revenues": ["Revenues", "RealEstateRevenueNet"],
        "CostOfGoodsAndServicesSold": ["OperatingExpenses", "CostOfGoodsAndServicesSold"],
        # ...
    },
    # 一般 sector 走默认 SEC_CONCEPT_NAMES（B029 既有）
}

def get_concept_alias_chain(ticker: str, concept: str, sector: str) -> list[str]:
    """Return concept alias chain to try in order. Falls back to default if sector
    not in PER_SECTOR map."""
    sector_aliases = SEC_CONCEPT_ALIASES_PER_SECTOR.get(sector, {})
    return sector_aliases.get(concept, [SEC_CONCEPT_NAMES.get(concept, concept)])
```

### 4.3 Strategy sleeve 切真路径

```python
# trade/strategies/us_quality_momentum/factors.py 改动示意
"""F003 (B028) trade/data/loader.py 已加：
- load_prices(tickers, as_of_date) 读 unified.prices_daily.csv else fixture
- load_fundamentals(tickers, as_of_date) 读 unified.fundamentals.csv else B025 fixture

B030 F002 改 strategy 代码读路径：
- from trade.data.loader import load_prices, load_fundamentals
- 之前直接读 data/fixtures/us_quality_momentum/*.csv → 改读 load_prices/load_fundamentals
- as_of_date 由调用方传（Recommendations / Backtest engine 已支持 as_of_date 参数）
"""

# 既有（B025 fixture-only path）
def compute_roe(ticker: str, as_of_date: date) -> float:
    df = pd.read_csv("data/fixtures/us_quality_momentum/fundamentals.csv")
    # ... filter ticker + as_of_date
    return roe_value

# B030 后（unified-first + fixture fallback）
def compute_roe(ticker: str, as_of_date: date) -> float:
    from trade.data.loader import load_fundamentals
    row = load_fundamentals([ticker], as_of_date).get(ticker)
    if row is None:
        # fall back to fixture if no real data (sector-structural ticker etc.)
        return _compute_roe_from_fixture(ticker, as_of_date)
    return row.roe
```

### 4.4 Fixture vs real 对比报告

```python
# scripts/compare_fixture_vs_real.py
"""Generate fixture-vs-real backtest comparison reports.

For each sleeve (Master + momentum + risk_parity + us_quality + hk_china):
1. Run backtest with FORCE_FIXTURE_PATH=1 → fixture results
2. Run backtest with FORCE_FIXTURE_PATH=0 (default unified-first) → real results
3. Render side-by-side comparison table:
   | Metric         | Fixture | Real   | Δ (real - fixture) |
   |---------------|---------|--------|---------------------|
   | Annual Return | 12.4%   | 11.8%  | -0.6 pp             |
   | Volatility    | 18.2%   | 17.6%  | -0.6 pp             |
   | Sharpe        | 0.68    | 0.67   | -0.01               |
   | Sortino       | 1.02    | 0.98   | -0.04               |
   | Calmar        | 0.55    | 0.53   | -0.02               |
   | Max Drawdown  | -22.5%  | -22.3% | +0.2 pp             |
   | Turnover      | 1.8x/yr | 1.7x/yr| -0.1                |
4. Write .md + .json to reports/fixture_vs_real/<sleeve>_2026-MM-DD.{md,json}
"""
```

### 4.5 B026 Banner 关闭（v0.9.30 §12.9 4 处接线遵守）

| 接线位置 | 改动 |
|---|---|
| `.env.example`（frontend） | 保留 `NEXT_PUBLIC_SYNTHETIC_DATA_BANNER=true` 注释（本机 dev 默认 enable banner） |
| `config.py` | N/A（NEXT_PUBLIC_* 是 frontend build-time env，不入 backend） |
| `deploy.sh` pre-flight check | N/A（NEXT_PUBLIC_* 不是 secret，缺时 next build 默认 undefined → banner enable 倒退默认 true，安全）|
| **`bootstrap-env.yml`**（**v0.9.30 §12.9 核心**）| **加一行 `NEXT_PUBLIC_SYNTHETIC_DATA_BANNER=false` 写入 production VM frontend env file**（如 `/etc/workbench/workbench-frontend.env`）|
| `workbench/frontend/.env.production` | 加 `NEXT_PUBLIC_SYNTHETIC_DATA_BANNER=false`（VM build-time inject） |

## 5. Feature 拆分

### F001 — Per-sector ratio aliases + 重跑 backfill 补 6 ticker（generator，3-4 天）

**Acceptance：**

(1) 改 `workbench_api/data/xbrl_parser.py`：
- 新增 `SEC_CONCEPT_ALIASES_PER_SECTOR: dict[str, dict[str, list[str]]]` 覆盖 3 sector（Financials / Utilities / Real Estate）每个含 8 ratio 涉及 concept 的 alias chain
- 新增 `get_concept_alias_chain(ticker, concept, sector)` helper 函数
- 改 `compute_ratios` 接收 `sector` 参数 + 用 alias chain fallback try 每个 alias 直到找到 fact

(2) 改 `workbench_api/data/sec_edgar_loader.py`：
- `fetch_quarterly_fundamentals` 接收 `sector` 参数（来自 universe_us_quality.py 查表）
- 传 `sector` 到 `xbrl_parser.compute_ratios`

(3) 改 `scripts/universe_us_quality.py`：每 ticker 加 `sector` 字段（与 B025 fixture universe.csv 的 `gics_sector` 列一致）

(4) **重跑 backfill**：`python scripts/backfill_fundamentals.py --from 2014-01-01 --to 2026-05-26 --universe us_quality`；产物：
- 27 CIK 目录（既有）+ 6 sector ticker 现在写真实 parsed_ratios.json（不再 0-row）
- unified.fundamentals.csv 行数从 685 → **≥1000**（spec floor 达成；27 真 ticker × 40 quarter）

(5) **跑 cross-check**：抽 6 sector ticker × 5 fiscal_quarter 验证：
- 8 ratio 全部非 zero / non-NaN
- ratio 数值合理（如 BAC ROE 在 [0.05, 0.20] 范围；NEE debt_to_assets 在 [0.45, 0.65] 范围 — utilities 通常高 debt）

(6) 更新 `docs/test-reports/B030-pit-validation-2026-MM-DD.md`（B029 PIT validation 报告基础上加 6 sector 补 backfill 之后的新行）

(7) pytest 新增 ≥10 测试：
- `SEC_CONCEPT_ALIASES_PER_SECTOR` Financials / Utilities / Real Estate 3 sector 含 8 ratio 涉及 concept
- `get_concept_alias_chain` 一般 sector → 默认 SEC_CONCEPT_NAMES
- `get_concept_alias_chain` Financials → InterestAndDividendIncomeOperating 优先
- mock XBRL 一般 sector + 金融 sector + 公用事业 sector + REIT 各 ratio 计算 happy path
- universe_us_quality 30 ticker 含 sector 字段（与 B025 fixture 一致）
- 重跑 backfill 后 6 sector ticker (BAC/JPM/V/LIN/NEE/PLD) row count > 0（mock）
- alias chain fallback 第 1 个 None → 第 2 个找到值

(8) Gates：
- `pytest tests` ≥361 baseline (B029) + ≥10 = ≥371 passed
- `ruff` + `mypy` 清
- frontend 不动 vitest ≥166 不破
- 本机重跑 backfill 数据本机存在；docs/test-reports/B030-pit-validation 报告通过

(9) **不动**：B027/B028 既有 loader / scripts；B025 fixture；strategy 代码（留 F002）；B026 banner（留 F003）；production deploy（本 F001 是本机 backfill）

### F002 — Master Portfolio 4 sleeve + B025 us_quality 5 因子 strategy 代码切真（generator，4-5 天）

**Acceptance：**

(1) 改 `trade/strategies/momentum.py`：
- 从直接 `pd.read_csv("data/fixtures/...")` → 改用 `trade.data.loader.load_prices(tickers, as_of_date)`
- `load_prices` 既有 unified-first + fixture fallback；strategy 代码无需关心 source

(2) 改 `trade/strategies/risk_parity.py`：同上

(3) 改 `trade/strategies/us_quality_momentum/factors.py` + `signal.py`：
- factors.py 8 ratio 计算 from `load_fundamentals` + price-derived ratio 从 `load_prices`
- signal.py 整体 pipeline 用 loader-injected 数据

(4) 改 `trade/strategies/hk_china_proxy.py`（若 B011 已实现 stub；本批次切到 unified prices via load_prices）

(5) 改 `trade/portfolio/master.py`：
- Master Portfolio 4 sleeve 组合逻辑切到 unified prices via load_prices
- 既有 as_of_date 参数透传

(6) 重要：**不动 trade/data/loader.py 现有逻辑**（B028 F003 + B029 F003 已写好 unified-first + fixture fallback；本 F002 仅改 strategy 代码消费方）

(7) pytest 新增 ≥20 测试：
- 每 sleeve（momentum / risk_parity / us_quality / hk_china）从 unified 路径读 PriceBar / FundamentalsRow 成功
- unified 缺数据时 fall back fixture（mock unified 不存在场景）
- B025 us_quality 5 因子在 unified 数据下计算的 ratio 与 fixture 路径数值差异落合理范围（±10% 容忍 — fixture vs real 不强 deterministic 但行为 deterministic）
- Master Portfolio 4 sleeve 组合 unified-first 完整跑通
- 既有 B011 / B025 / B013 strategy 测试若有 "fixture-deterministic" 假设需重审：**优先保 既有测试 100% 通过**（fall back 路径仍 fixture）；若必须破，明示标 "B030 cutover" 注释 + 同 commit 改测试

(8) 重要：**B025 us_quality_momentum 既有回测在 fixture path 数字不变** — `FORCE_FIXTURE_PATH=1` env var 强制 fixture 路径时，既有 deterministic 测试 100% 通过（保 B025 acceptance §F003 §(4)）

(9) Gates：
- `pytest tests` ≥371 + ≥20 = ≥391 passed
- `ruff` + `mypy` 清
- `FORCE_FIXTURE_PATH=1 pytest tests` 强制 fixture 路径全过（不破 既有 deterministic）
- `pytest tests` 默认（unified-first）全过（验真数据路径可用）
- frontend 不动 vitest ≥166 不破

(10) **不动**：trade/data/loader.py（B028+B029 已就位）；workbench backend endpoints；Frontend / UI；B026 banner（留 F003）；reports/ 对比报告（留 F003）

### F003 — Fixture-vs-real 对比报告 + B026 banner 关闭（生产 deploy）（generator，3-4 天）

**Acceptance：**

(1) 新建 `scripts/compare_fixture_vs_real.py`：
- 对每 sleeve（Master + momentum + risk_parity + us_quality + hk_china_proxy 共 5 个）跑两次 backtest：`FORCE_FIXTURE_PATH=1` vs default
- 输出并排对比表：Annual Return / Volatility / Sharpe / Sortino / Calmar / MDD / Turnover / Win Rate 等
- 写 `.md` + `.json` 到 `reports/fixture_vs_real/<sleeve>_2026-MM-DD.{md,json}`
- 跑出来后**总结 1 个 high-level overview**：`reports/fixture_vs_real/overview_2026-MM-DD.md`

(2) **本批次跑 compare_fixture_vs_real.py**：5 份对比报告生成入 `reports/fixture_vs_real/`（commit message + signoff 记录 row count）

(3) B026 banner 关闭（**v0.9.30 §12.9 4 处接线遵守**）：
- `workbench/frontend/.env.example` 保留 `NEXT_PUBLIC_SYNTHETIC_DATA_BANNER=true` 注释（本机 dev 默认 enable）
- `workbench/frontend/.env.production` 加 `NEXT_PUBLIC_SYNTHETIC_DATA_BANNER=false`
- `.github/workflows/bootstrap-env.yml` 加一行 inject `NEXT_PUBLIC_SYNTHETIC_DATA_BANNER=false` 到 production frontend env file
- frontend redeploy 后 production HTML/JS bundle 不含 banner DOM

(4) 不动 B026 既有 banner 组件代码（`SyntheticDataBanner.tsx`）：保留可在 Layer 0 重启时通过 env var 重新 enable（v0.9.X §"Layer 状态不可逆向滑落" 边界）

(5) pytest 新增 ≥10 测试：
- compare_fixture_vs_real.py 5 sleeve 对比表 schema correct
- fixture vs real Δ 落合理范围（mock backtest 数据）
- `NEXT_PUBLIC_SYNTHETIC_DATA_BANNER=false` 时 SyntheticDataBanner 不渲染（既有 B026 vitest 测试覆盖；本 F003 加 1 个新测试断言 `process.env.NEXT_PUBLIC_SYNTHETIC_DATA_BANNER === 'false'` 时 component returns null）
- bootstrap-env.yml 含 `NEXT_PUBLIC_SYNTHETIC_DATA_BANNER` 行
- .env.production 含 `NEXT_PUBLIC_SYNTHETIC_DATA_BANNER=false`
- .env.example 保留 `NEXT_PUBLIC_SYNTHETIC_DATA_BANNER=true` 注释

(6) Gates：
- `pytest tests` ≥391 + ≥10 = ≥401 passed
- frontend vitest ≥166 不破 + Playwright ≥38 不破
- `ruff` + `mypy` 清
- `npm run build` 成功生成 production bundle（NEXT_PUBLIC_* build-time inject）
- 5 份 fixture vs real 对比报告生成入 reports/fixture_vs_real/
- bootstrap-env.yml 守门 v0.9.30 §12.9 三处接线（grep 验证）

(7) **不动**：strategy 代码（F002 已切完）；trade/data/loader.py；B026 banner 组件代码；workbench backend endpoints

### F004 — Codex L1 + L2 真 VM 验收 + signoff = 里程碑 A Layer 0→1（codex，2-3 天）

**L1 (CI 内)：**

- F001-F003 全部 generator 验收脚本跑通：backend / trade pytest ≥401 / ruff / mypy / alembic up-down OK
- Frontend vitest ≥166 (+至少 1 个 banner=false 渲染测试) + Playwright ≥38 + build OK
- safety regression 全绿（含 v0.9.29 §12.8.1 + v0.9.30 §12.9 bootstrap-env.yml grep）
- artifact grep 无 secret 泄漏
- **`FORCE_FIXTURE_PATH=1 pytest tests` 强制 fixture 路径全过**（保 既有 deterministic）

**L2 (真 VM)：**

1. Frontend redeploy 触发：`workbench-frontend.yml` paths 含 `.env.production` 改动 → 自然触 frontend CI → Workbench Deploy → production VM 拿到新 frontend bundle（NEXT_PUBLIC_SYNTHETIC_DATA_BANNER=false 已 build-time inject）
2. `curl https://trade.guangai.ai/api/health` 200 + version SHA 与 main HEAD 等价
3. `curl https://trade.guangai.ai/api/debug/recent-errors` 返回 `{"count":0,"records":[]}`
4. **B026 banner 已下线**：浏览器访问 https://trade.guangai.ai/strategies / /reports / etc 看不到 banner DOM；HTML grep 不命中 `研究原型 · 仅含合成数据`
5. **Recommendations / Reports / Backtest 页面展示真实数据指标**（VM 上拉 production / api 数据，看 sleeve breakdown / NAV / target positions 数字）
6. **5 份 fixture vs real 对比报告本机存在且可读**（reports/fixture_vs_real/ 各 .md 文件）
7. Production HEAD ≡ main HEAD（v0.9.25 §Production/HEAD 等价性）+ Post-signoff Deploy 段（v0.9.27 / §12.7.1 / §12.9）

**Signoff：**

- `docs/test-reports/B030-real-data-cutover-signoff-2026-MM-DD.md` 用 framework/templates/signoff-report.md
- **🎯 Signoff 明示 "里程碑 A Layer 0→1 达成"**：含 fixture vs real 对比 5 报告链接 + production banner 已关 + 5 sleeve 真数据回测指标 summary
- `docs/screenshots/B030-cutover/` ≥5 PNG：production 无 banner 截图 + fixture vs real overview 截图 + 各 sleeve real 数据指标截图

**Framework 候选：**

预期无重大 framework learning（v0.9.30 §12.9 已守门 banner env 三处接线；v0.9.29 §12.8 已守门新 dep；v0.9.27 §12.7.1 已修 paths-trigger）。若 fix-round 出现意外（如 strategy 切真后某 sleeve 回测指标爆炸 / unified.csv 与 strategy 代码读取假设不一致 / fall back 逻辑失效），记录在 signoff §Framework Learnings。

## 6. 不做的事（YAGNI）

- ❌ **新增 strategy / sleeve**（B011 Master Portfolio 4 sleeve + B025 us_quality 已是全集；HK-China satellite 仍 stub fall back）
- ❌ **修改 strategy 公式**（v0.9.X §"AI 边界"+"Ratio 公式锁定 strategy doc §6"硬约束）
- ❌ **每日 EOD cron 上线**（推迟到 Phase 1 之后 / Phase 2 LLM advisory 同期）
- ❌ **修复 fixture vs real Δ 不合理 outlier**（生成报告即可；具体改进留下 batch；本批次只完成数据 cutover）
- ❌ **AI 自动解释 fixture vs real 差异**（永久边界 + Phase 2 LLM gateway 后再做）
- ❌ **Frontend / UI 重大改造**（仅关 banner；其他 UI 不动）
- ❌ **新 production secret 引入**（本批次仅改 banner env var，不引入新 secret；若引入按 v0.9.30 §12.9 四处接线走）
- ❌ **新 alembic migration**（本批次不动 DB schema）

## 7. 验收门槛汇总

| 门槛 | F# 责任 |
|---|---|
| Per-sector aliases 覆盖 Financials / Utilities / Real Estate 3 sector × 8 ratio 涉及 concept | F001 |
| 重跑 backfill 后 unified.fundamentals.csv ≥1000 行（27 真 ticker × 40 quarter）| F001 |
| 6 sector ticker (BAC/JPM/V/LIN/NEE/PLD) 8 ratio 全部非 zero/NaN + 数值合理范围 | F001 |
| Master Portfolio 4 sleeve + B025 us_quality 5 因子 strategy 代码 read path 切到 unified | F002 |
| trade/data/loader.py 不动（B028+B029 已就位）| F002 |
| `FORCE_FIXTURE_PATH=1 pytest` 强制 fixture 路径全过（保 B025 既有 deterministic）| F002 |
| 5 份 fixture vs real 对比报告生成入 reports/fixture_vs_real/ | F003 |
| **B026 banner 关闭** by v0.9.30 §12.9 4 处接线（.env.example / .env.production / bootstrap-env.yml frontend env / 不需 deploy.sh check）| F003 |
| Backend / trade pytest ≥401 + ruff + mypy 清 | F001+F002+F003+F004 |
| Frontend vitest ≥166 + Playwright ≥38 + build OK | F003+F004 |
| Production frontend redeploy + banner 在生产 HTML 不再出现 | F004 |
| 5 份对比报告本机 + production HTML 真实数据指标可见 | F004 |
| **🎯 Signoff 明示 "里程碑 A Layer 0→1 达成"** + 5 sleeve real 数据回测指标 summary | F004 |
| Production HEAD ≡ main HEAD + Post-signoff Deploy 段 | F004 |

## 8. 参考文档

- `docs/product/implementation-path-2026-05.md` §4 Phase 1 终点 / §6 里程碑 A
- `docs/product/data-source-evaluation-2026-05.md` §6 数据源 + §7 双层 storage
- `docs/product/roadmap-2026-05.md` Stream 1.D
- `docs/specs/B028-real-data-backfill-spec.md` unified prices storage
- `docs/specs/B029-fundamentals-snapshot-spec.md` unified fundamentals storage + §F003 PIT loader
- `docs/specs/B026-synthetic-data-banner-spec.md` banner 组件 + env flag
- `docs/specs/B025-us-quality-momentum-satellite-spec.md` §4.1 fixture schema + §6 8 ratio 公式
- `docs/specs/B011-master-portfolio-allocation-spec.md` Master Portfolio 4 sleeve
- `docs/strategy/03-us-quality-momentum.md` §6（**ratio 公式权威 — 永久边界 (j)**）
- `framework/STRUCTURE.md` framework/ 目录语义
- `framework/harness/planner.md` §"AI 边界精细化（v0.9.28）" §"Cloud-deploy spec checklist v0.9.27 扩展 (e)"
- `framework/harness/generator.md` §10 GHA / §12.5-12.7 deploy / §12.7.1 paths-trigger（已修）/ §12.8 pyproject runtime vs dev / **§12.9 production secret 三处接线铁律（v0.9.30）**
- `framework/templates/signoff-report.md` v0.9.27 §Post-signoff Deploy

## 9. 风险与缓解

| 风险 | 缓解 |
|---|---|
| Per-sector aliases 不全覆盖（某 sector 某 ratio 缺）| F001 acceptance 明示 3 sector × 8 ratio 全集；alias chain 多层 fallback；spot check 6 ticker 数值合理性 |
| Strategy 切真后 fixture-deterministic 测试破 | F002 acceptance 硬要求 `FORCE_FIXTURE_PATH=1 pytest` 全过；既有 测试保 fixture path 不变 |
| B025 us_quality 5 因子在 real 数据下数值差异爆炸（>10%）| F002 acceptance 容忍 ±10% Δ；超 alert + signoff 记 但不阻塞（数据本身 fact 而非 bug）|
| fixture vs real 对比报告 outlier 让用户疑虑 | F003 acceptance 不做 outlier 修复；只生成报告；具体改进留下 batch（不阻塞 milestone A）|
| B026 banner 关闭后 production 还显示 | F003 acceptance v0.9.30 §12.9 4 处接线全部完成；F004 L2 HTML grep 验证；若 fail 走 v0.9.27 §12.7 dispatch deploy |
| Frontend `NEXT_PUBLIC_*` build-time inject 失败 | bootstrap-env.yml frontend env file workflow 必触；F004 L2 验证；fail 时按 §12.7 dispatch 兜底 |
| Layer A 后用户发现真数据严重 unreliable | 本批次新增永久边界 (k) "Layer 状态不可逆向滑落"：必须新批次 spec 决议；不 silent rollback fixture / 不 silent 重开 banner |
| Master Portfolio 4 sleeve unified 路径有性能问题（每次 backtest 都过 153K rows）| F002 acceptance unified-first 是默认；性能本身留 Phase 2 优化 |

## 10. 与既有批次的边界

- 不动 trade/data/loader.py 现有 load_prices + load_fundamentals 接口（B028+B029 已就位；本批次仅 strategy 代码消费方改路径）
- 不动 B025 fixture（仍是 fall back source；strategy 代码 unified-first + fixture fallback）
- 不动 B027 既有 Tiingo loader + cost guard / B028 既有 backfill scripts / B029 既有 SEC EDGAR loader + xbrl_parser 既有接口（**仅 F001 扩 per-sector aliases**）
- 不动 B026 banner 组件代码（仅改 env var；保留 banner 可重新 enable 路径）
- 不动 B024 i18n / B025 双语 disclaimer / B023 manual execution / B022 workbench / B021 cloud deploy 基础设施
- 不动 workbench backend endpoints / Recommendations / Risk Panel / Reports 页面 component 代码（仅展示数据从 fixture → real 切换；UI 不动）
- 不动 strategy 公式（永久边界 (j) ratio 公式锁定 strategy doc §6）

## 11. 后续批次（不在 B030 范围）

按 implementation-path §4 Phase 2 起：

- **🎯 里程碑 A Layer 0→1 达成后** Phase 2 / Stream 3 LLM advisory（B031+）可启动
- **B031 = Phase 2 / Stream 3.A** LLM gateway（按 llm-provider-evaluation §5.1 aigc-gateway 主选）+ 守门 v0.9.30 §12.9 三处接线（多个 LLM API key 引入）
- **B032 = Phase 2 / Stream 3.B** AI safety eval framework（按 ai-safety-evals §3 红队 dataset）
- **B033+ = Phase 2 / Stream 2** News / market context ingest
- **Phase 3 / Home + UI 重构** 与 Phase 2 部分并行

**Phase 1 完成 (B030 done)**：implementation-path §4 milestone A 达成；workbench 进入「research with real historical data」阶段；Layer 0 状态结束。

---

> 本 spec 完成后，progress.json status=building，current_sprint=F001，Generator 接 per-sector aliases + 重跑 backfill。
