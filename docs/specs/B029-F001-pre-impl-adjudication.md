# B029 F001 · Pre-Implementation Adjudication 请求

> **发起者：** Generator (Claude CLI)
> **日期：** 2026-05-26
> **触发：** B029 F001 开工前审计，按 `framework/harness/pre-impl-adjudication.md` §2 范式
> **状态：** 等待 Planner 明确回复，**未收到前不开工**

## 1. 背景 & 目标

实现 B029 F001：`FundamentalsLoader` 抽象 + `FundamentalsRow` dataclass + `SECEDGARFundamentalsLoader` + `xbrl_parser` 8 ratio 计算 + fixtures + settings/env/deploy.sh 接线 + pytest ≥12。

Spec：`docs/specs/B029-fundamentals-snapshot-spec.md` §4 + §5 F001。

读完所有参考文档后（spec / B025 fixture / B027 tiingo_loader / B028 yfinance_loader / framework/harness/generator.md §12.8 / strategy doc §6 / settings.py / .env.example / deploy.sh），发现 3 处需要 Planner 裁决的决议点。

## 2. 跨源比对 · 三个决议点

### 决议点 #1 — `FundamentalsRow` schema 列数（11 vs 12）

| 来源 | 描述 |
|---|---|
| spec §4.2 FundamentalsRow Python 草案 | **11 字段**：`ticker / fiscal_quarter / report_date / roe / gross_margin / fcf_yield / debt_to_assets / pe / pb / ev_ebitda / earnings_yield` |
| spec §4.4 (4.4 Schema 描述行) | 11 列（同上罗列） |
| F001 acceptance §(1) | "B025 fixture 11 列 schema 严格一致" |
| **B025 fixture 实际** | **12 列**：`report_date,ticker,fiscal_quarter,fiscal_quarter_end,roe,gross_margin,fcf_yield,debt_to_assets,pe,pb,ev_ebitda,earnings_yield`（`wc -L` 验证；`head -1 | awk -F, '{print NF}'` = 12） |
| F002 acceptance §(5) PIT validation | 显式要求 `fiscal_quarter_end_date < report_date` — 依赖 `fiscal_quarter_end` 列存在 |

**矛盾本质：** spec §4.2/§4.4 文字漏列了 `fiscal_quarter_end`（fixture 与 F002 PIT validation 都需要它）。多数派依据（fixture authoritative + F002 acceptance）指向 12 列。

| # | 决议点 | A 方案 | B 方案 | 多数派参考 | Generator 建议 |
|---|---|---|---|---|---|
| 1 | `FundamentalsRow` 字段数 | **12 字段（含 `fiscal_quarter_end: date`）**，与 fixture 严格一致 | 11 字段（按 spec §4.2 文字），F002 PIT validation 改用 `fiscal_quarter` 反推 `fiscal_quarter_end`（如 `"2014Q4"` → `2014-12-31`） | fixture 12 列 + F002 §(5) PIT 显式 enforcement | **A** — fixture 是 source of truth，acceptance §(1) "与 B025 fixture 严格一致" 原文已隐含 12 列；A 方案让 F002 PIT validation 直接读列、不引入字符串反推逻辑 |

### 决议点 #2 — `fiscal_quarter` 字段格式

| 来源 | 描述 |
|---|---|
| spec §4.2 docstring | `# e.g. "2020-Q4"`（带短横线） |
| **B025 fixture 实际** | `2014Q4`（无短横线，紧凑形式） |

| # | 决议点 | A 方案 | B 方案 | 多数派参考 | Generator 建议 |
|---|---|---|---|---|---|
| 2 | `fiscal_quarter` 格式 | **`2014Q4`（无短横线）**，与 fixture 一致 | `2020-Q4`（带短横线），与 spec §4.2 docstring 一致 | fixture 1350 行实际数据 + acceptance §(1) "与 B025 fixture 严格一致" | **A** — fixture 是数据源真实形式，B025 既有 strategy 代码（5 因子测试）已读这个格式；改格式会破 B025 既有回测 deterministic 不变（F003 硬要求） |

### 决议点 #3 — `ticker_cik_map.json` 是否含 3 个 synthetic ticker

| 来源 | 描述 |
|---|---|
| F001 acceptance §(6) | "ticker_cik_map.json B025 us_quality 30-50 ticker → CIK 映射 cache" |
| F001 pytest 测试 §(9) 第 10 条 | "ticker_cik_map.json 含 B025 universe 全部 30-50 ticker" |
| **B025 universe.csv 实际** | 30 行 ticker，其中 3 个为合成（synthetic）虚构公司：`ZQAI`（Synthetic Industrial Smallcap Co.）/ `ZQPT`（Synthetic Penny Tech Holdings）/ `ZQLH`（Synthetic Light Volume Health Inc.）—— **不存在于 SEC EDGAR**（无 CIK） |

| # | 决议点 | A 方案 | B 方案 | C 方案 | Generator 建议 |
|---|---|---|---|---|---|
| 3 | synthetic ticker 处理 | **30 条全入 map，27 真 CIK + 3 synthetic 映射 `null`**；`SECEDGARFundamentalsLoader.fetch_quarterly_fundamentals` 拿到 `null` CIK 时 raise `ValueError("Synthetic ticker X has no SEC filing; skip in backfill driver")`；F002 backfill driver catch 该异常 + log warn + skip 不阻塞批次 | 仅 27 真 ticker 入 map（弃掉 3 synthetic）；F002 universe_us_quality 同步 filter synthetic | 30 条全入 map，synthetic 映射特殊 sentinel `"SYNTHETIC"` 字符串 | **A** — acceptance §(9) test 10 字面读"含全部 30 ticker"成立；`null` 是清晰的"无 CIK"语义，pytest 覆盖；synthetic ticker 本质是 B025 fixture 用于回测的虚构样本，未来不会有真实 fundamentals（永久边界） |

## 3. 额外确认（不阻塞，但请 Planner 一并确认）

### 确认 #4 — 是否引入新 dep（lxml 等）

| 来源 | 描述 |
|---|---|
| spec §4.3 SECEDGARFundamentalsLoader 文档 | "Use companyfacts API (pre-parsed XBRL JSON) when possible vs raw XML" |
| spec §6 YAGNI 第 8 条 | "❌ SEC Python SDK 引入（仅 stdlib + httpx；XBRL parse 用 ElementTree 或 json companyfacts；避免 vendor SDK lock-in）" |
| F001 acceptance §(7) | "若引入新 dep（如 lxml for XML parsing），按 v0.9.29 §12.8 加 [project].dependencies + CRITICAL_RUNTIME_DEPS；**若仅用 stdlib `xml.etree.ElementTree` + `json` + `httpx` 则不需新 dep**" |

**Generator 实现计划：** 走 companyfacts API（`https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json`）返回 pre-parsed JSON。仅用 stdlib（`json` / `datetime` / `os` / `abc` / `dataclasses` / `typing`）+ 既有 `httpx`（已在 `[project].dependencies`）。

**不引入新 dep** → `pyproject.toml` 不动，`CRITICAL_RUNTIME_DEPS` 不动，`tests/safety/test_runtime_dependencies_pinned.py` 不动，v0.9.29 §12.8 dep promotion 流程不触发。

**请 Planner 确认：A = 不引入新 dep（推荐） / B = 预先引入 lxml 防御未来 raw XBRL 需求**

| # | 决议点 | A 方案 | B 方案 | Generator 建议 |
|---|---|---|---|---|
| 4 | 是否引入新 dep | **A：仅 stdlib + httpx，不引入新 dep** | B：预先引入 lxml + 走 v0.9.29 §12.8 规约 | **A** — YAGNI；spec §6 第 8 条明确 stdlib 已够；companyfacts JSON 路径不需 XML 解析；未来真需 lxml 走新 batch 走规约 |

## 4. 原型 bug / 已知漂移追加

- spec §4.2 FundamentalsRow Python 草案中 docstring `fiscal_quarter: str  # e.g. "2020-Q4"` 与 fixture `2014Q4` 不一致（决议 #2 已覆盖）
- spec §4.4 "11 ratio 列" 文字 vs fixture 12 列（决议 #1 已覆盖）
- 上述漂移建议 Planner 在裁决时**同步修订 spec §4.2 / §4.4**

## 5. 开工条件

收到 Planner 对 #1 #2 #3 #4 的明确回复后，Generator 将：

1. 按决议实现 7 个新文件：
   - `workbench/backend/workbench_api/data/fundamentals_loader.py`
   - `workbench/backend/workbench_api/data/sec_edgar_loader.py`
   - `workbench/backend/workbench_api/data/xbrl_parser.py`
   - `workbench/backend/workbench_api/data/fixtures/sec_edgar_responses/aapl_companyfacts.json`
   - `workbench/backend/workbench_api/data/fixtures/sec_edgar_responses/nvda_companyfacts.json`
   - `workbench/backend/workbench_api/data/fixtures/sec_edgar_responses/ticker_cik_map.json`
   - `workbench/backend/tests/unit/test_fundamentals_loader.py`（实际 ≥12 用例可能拆 3 个文件：test_fundamentals_loader.py / test_sec_edgar_loader.py / test_xbrl_parser.py）
2. 修改 3 个既有文件：
   - `workbench/backend/workbench_api/settings.py`（加 `SEC_EDGAR_CONTACT_EMAIL`）
   - `workbench/backend/.env.example`（加 `SEC_EDGAR_CONTACT_EMAIL=research@example.com`）
   - `workbench/deploy/scripts/deploy.sh`（加 pre-flight check）
   - `workbench/backend/tests/safety/test_settings_env_allowlist.py`（同步 `EXPECTED_ALLOWLIST`）
3. 走 F001 闸门：
   - `.venv/bin/python -m pytest workbench/backend/tests` ≥316（B028 baseline 304 + ≥12 = 316）
   - `.venv/bin/python -m ruff check workbench/backend` exit=0
   - `.venv/bin/python -m mypy workbench/backend/workbench_api workbench/backend/tests` exit=0
   - `cd workbench/frontend && npm test` ≥166 不破（不动）
4. commit message `feat(B029-F001): SEC EDGAR fundamentals loader + XBRL JSON parser`
5. push origin main → 检查 CI (`gh run list --limit 3 --branch main`)

**未收到明确回复前不开工。**

## 6. 估算开工时长

| 环节 | 预估 |
|---|---|
| `fundamentals_loader.py`（抽象 + dataclass）| 20 分钟 |
| `sec_edgar_loader.py`（含 SimpleRateLimit + Protocol DI + retry）| 60 分钟 |
| `xbrl_parser.py`（8 ratio compute_ratios + 单 ratio 函数 + edge case）| 80 分钟 |
| fixtures（companyfacts JSON 真实抽样 + ticker_cik_map）| 60 分钟（含 CIK 手工查表） |
| settings.py / .env.example / deploy.sh / allowlist test | 25 分钟 |
| pytest ≥12（实际目标 14-18）| 120 分钟 |
| 本地 gates + commit + push + CI 检查 | 30 分钟 |
| **总计** | **~6.5 h** |

## 7. 相关文档

- `docs/specs/B029-fundamentals-snapshot-spec.md`（spec 本体）
- `docs/specs/B027-real-data-snapshot-foundation-spec.md`（SnapshotLoader 抽象模式 / Protocol DI 设计参考）
- `docs/specs/B028-real-data-backfill-spec.md`（yfinance_loader 类似 second-vendor 模式 / Protocol-based ticker factory）
- `docs/specs/B025-us-quality-momentum-satellite-spec.md` §4.1 + §6（fixture schema + 8 ratio 来源）
- `docs/strategy/03-us-quality-momentum.md` §6（ratio 公式权威 — 永久边界 (j)）
- `data/fixtures/us_quality_momentum/fundamentals.csv`（12 列 fixture authoritative）
- `data/fixtures/us_quality_momentum/universe.csv`（30 ticker 含 3 synthetic）
- `framework/harness/generator.md` §12.8（pyproject runtime vs dev hygiene）
- `framework/harness/pre-impl-adjudication.md` §2.2（本审计模板来源）
- `workbench/backend/workbench_api/data/tiingo_loader.py`（Protocol DI + retry 参考）
- `workbench/backend/workbench_api/data/yfinance_loader.py`（ticker_factory Protocol 参考）

---

## 8. Planner 裁决（待填）

> 待 Planner 在此追加 `#1:A/B #2:A/B #3:A/B/C #4:A/B` + 逐条理由 + 同步 spec §4.2 / §4.4 修订清单。
