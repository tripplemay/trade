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

## 8. Planner 裁决（2026-05-26）

> **裁决人：** Planner（Claude CLI）
> **日期：** 2026-05-26
> **依据：** `framework/harness/planner.md` §"Planner 裁决职责"（规则 P1 / P3 / P5）+ `framework/harness/pre-impl-adjudication.md` §2.2 范式
> **事实核查：** Planner 用 `awk -F, 'NR==1 {print NF}' fundamentals.csv` 实测 12 列；`head -1 | tr ',' '\n'` 第 4 列确实是 `fiscal_quarter_end`；`fiscal_quarter` 实际值 `2014Q4` 无短横线；`grep "ZQAI\|ZQPT\|ZQLH" universe.csv` 命中 3 个 synthetic 行。**Generator 的 3 个事实性断言 100% 准确**。

### 8.1 决议结果（一行汇总）

**#1: A  #2: A  #3: A  #4: A**

Generator 4 项建议**全部采纳**。理由如下。

### 8.2 逐条裁决

#### 决议 #1 — `FundamentalsRow` schema 12 字段（含 `fiscal_quarter_end: date`）

**裁决：A 方案（12 字段）**

理由：
1. **Fixture 是 source of truth**：B029 F001 acceptance §(1) 明文要求"与 B025 fixture 严格一致"；fixture 12 列是事实。spec §4.2 草案 / §4.4 文字漏列 `fiscal_quarter_end` 是 spec 文字漂移，应以 fixture 为准修订 spec。
2. **F002 PIT validation §(5) 显式依赖 `fiscal_quarter_end`**：`fiscal_quarter_end < report_date` + `report_date >= fiscal_quarter_end + 30d` 是 hard assertion；若走 11 字段方案让 F002 字符串反推 fiscal_quarter_end（如 `"2014Q4"` → `2014-12-31`），引入额外文本解析逻辑 + 假节假日 / 财年偏移等 edge case，不必要。
3. **PIT loader F003 简化**：12 字段方案让 `effective_date = report_date + 1 business day` 仍只依赖 `report_date` 列，但 PIT validation 与回溯交叉验证可直接读 `fiscal_quarter_end` 列。
4. **历史漂移记录**：B025 spec §4.1 文字描述同样漏 `fiscal_quarter_end`（B025 已 done，spec 不修订；B029 spec 修订后即权威）。

#### 决议 #2 — `fiscal_quarter` 格式 `2014Q4`（无短横线）

**裁决：A 方案（`2014Q4`）**

理由：
1. **Fixture 1350 行实际数据**：是 source of truth。spec §4.2 docstring `"2020-Q4"` 是 spec 草案文字漂移。
2. **B025 既有回测 deterministic 不变（F003 acceptance 硬要求）**：若改格式破坏 B025 既有 strategy 代码读 fixture 路径，违反 F003 acceptance §(4)。
3. **历史漂移记录**：B029 spec §4.2 docstring + §10 ratio fixtures 段需同步修订。

#### 决议 #3 — 30 条全入 `ticker_cik_map.json`（27 真 CIK + 3 synthetic 映射 `null`）+ `ValueError` raise + F002 driver catch skip

**裁决：A 方案（30 条全入 + null + ValueError + catch skip）**

理由：
1. **acceptance §(9) 测试 10 字面读"含全部 30 ticker"成立**：A 方案精确匹配测试。
2. **`null` 是清晰的"无 CIK"语义**：JSON `null` 比 sentinel 字符串 `"SYNTHETIC"` 类型更清晰，pytest 覆盖也更直接（`assert cik is None`）。
3. **Synthetic ticker 本质是 B025 fixture 回测虚构样本**：永久边界不会有 real SEC filings；B025 既有 strategy 测试已使用，不能从 universe 中剔除（违反 F003 acceptance "B025 既有回测 deterministic 不变"）。
4. **F002 backfill driver catch ValueError + log warn + skip 不阻塞批次** 是 fail-safe 设计；本批次预期 backfill ≈ 27 真 ticker × 40 quarters ≈ 1080 rows（达成 acceptance §(6) row count ≥1200 略不达，调整 acceptance 阈值至 ≥1000 — 见 §8.3 修订）。

#### 决议 #4 — 仅 stdlib + httpx，不引入新 dep

**裁决：A 方案（不引入新 dep）**

理由：
1. **YAGNI**：spec §6 YAGNI 第 8 条明确 "stdlib 已够；XBRL parse 用 ElementTree 或 json companyfacts"。
2. **companyfacts API 走 JSON**：SEC 已预 parse，stdlib `json` 模块足够。
3. **未来真需 lxml**（如降级到 raw XBRL XML parse）：走新 batch + v0.9.29 §12.8 规约，不在本批次预留。
4. **v0.9.29 §12.8 守门 + `CRITICAL_RUNTIME_DEPS`** 不动；本批次 dep 边界稳定。

### 8.3 spec 同步修订清单（Planner 同 commit 完成）

按 planner.md §P3 "修 acceptance 必须扫全文消除矛盾"，本裁决落地时 Planner 同步修订 **B029 spec + features.json** 全文：

| 修订点 | 来源 | 改为 |
|---|---|---|
| spec §4.2 `FundamentalsRow` Python 草案 | 11 字段 | **12 字段：`ticker / fiscal_quarter / fiscal_quarter_end / report_date / roe / gross_margin / fcf_yield / debt_to_assets / pe / pb / ev_ebitda / earnings_yield`** |
| spec §4.2 docstring `fiscal_quarter: str  # e.g. "2020-Q4"` | `"2020-Q4"` | **`"2014Q4"`** |
| spec §4.4 "Schema matches B025 fixture fundamentals.csv exactly: ... 11 字段" | 11 字段列表 | **12 字段列表（加 `fiscal_quarter_end`）** |
| spec §4.7 `load_fundamentals` docstring schema 注释 | 11 列 | **12 列** |
| spec §5 F001 acceptance §(1) "11 列 schema 严格一致" | 11 列 | **12 列 schema 严格一致** |
| spec §5 F002 acceptance §(6) row count `≥1200` | `≥1200`（30 × 40）| **`≥1000`**（27 真 ticker × 40 + 3 synthetic null 跳过）|
| spec §5 F002 acceptance §(9) PIT spot check `fiscal_quarter_end` 描述 | 反推 | **直接读 fixture / unified 第 4 列** |
| spec §5 F001 acceptance §(9) 测试 10 "30-50 ticker → CIK 映射" | "30-50 ticker → CIK" | **"30 ticker → CIK（27 真 + 3 synthetic 映射 null）"** |
| spec §10 不破 B025 fundamentals.csv 既有 schema | 隐含 | **明示 12 列；synthetic ticker 不入 SEC backfill** |
| features.json F001 acceptance | 同步以上所有改动 | 同上 |

### 8.4 开工许可

Generator 收到本裁决后**可立即开工 B029 F001**，按 §8.2 各决议 + §8.3 修订后的 spec 实现。

预计 ~6.5 h（按 §6 估算）。完成后走 §5 F001 闸门 + commit + push + CI 检查。

### 8.5 后续注意点

- B025 spec §4.1 文字同样漏 `fiscal_quarter_end`（B025 已 done，本裁决不修 B025 spec；B029 spec 修订后即 fundamentals.csv schema 的权威文档）。
- 若 F002 实施时发现 SEC 对某真实 ticker 也无 CIK（如某 ticker 改名 / 退市 / 上市后改 ticker），按决议 #3 模式：log warn + skip 不阻塞 batch。
- 决议 #3 的 catch skip 模式是 fail-safe；F002 acceptance §(6) row count 阈值已下调 ≥1000 reflect 27 真 ticker × 40 quarter 期望。
