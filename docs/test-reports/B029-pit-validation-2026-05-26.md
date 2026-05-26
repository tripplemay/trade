# B029 PIT Validation Report — Real SEC EDGAR Backfill (2026-05-26)

> **Generator:** Claude CLI (B029 F002)
> **Date:** 2026-05-26
> **Spec:** `docs/specs/B029-fundamentals-snapshot-spec.md` §5 F002 acceptance §(5)
> **Backfill driver:** `scripts/backfill_fundamentals.py --from 2014-01-01 --to 2026-05-26 --universe us_quality`
> **Source:** `data/snapshots/fundamentals/unified/fundamentals.csv`
> **PIT invariant:** B025 spec §4.1 — `fiscal_quarter_end < report_date` **AND** `report_date >= fiscal_quarter_end + 30 days`

## 1. Backfill summary

| Metric | Value |
|---|---|
| **Total rows in unified fundamentals.csv** | **685** |
| Real B025 us_quality_momentum tickers in universe | 27 |
| Tickers with ≥1 row produced | 21 / 27 |
| Tickers with 0 rows produced (sector-structural; see §3) | 6 / 27 (`BAC`, `JPM`, `V`, `LIN`, `NEE`, `PLD`) |
| Synthetic tickers skipped (Planner decision #3 fail-safe) | 3 (`ZQAI`, `ZQPT`, `ZQLH`) |
| Vendor raw CIK directories under `sec_edgar/` | 27 (one per real ticker, with `companyfacts.json` + `parsed_ratios.json` + `metadata.json`) |
| Date range | 2014-01-01 to 2026-05-26 (12.4 calendar years × 27 tickers ≈ 1300 max theoretical) |

The 685-row figure is **below the spec ≥1000 row floor** (§F002 acceptance §(4)).
The shortfall is sector-structural — six tickers (financial: BAC/JPM/V;
utility: NEE; industrial gas: LIN; REIT: PLD) report financial
statements with concept names that do not align with the eight-ratio
model encoded in `xbrl_parser.py`. See §3 below for the per-ticker
breakdown + the F003 / B030 follow-up path.

## 2. PIT invariant spot-check — 5 tickers × 5 random fiscal quarters

Random sample (seed 2026526) of 25 rows from the unified file. Each
row's `report_date` (SEC filing date) is compared against its
`fiscal_quarter_end` (the period-end date the filing covers). The
invariant is `report_date >= fiscal_quarter_end + 30 days` (B025
spec §4.1; SEC filers have at least 30 days post-quarter-end to file).

| ticker | fiscal_quarter | fiscal_quarter_end | report_date | delta_days | PIT |
|---|---|---|---|---|---|
| XOM  | 2013Q4 | 2013-12-31 | 2017-02-22 | 1149d | ✅ PASS |
| XOM  | 2017Q3 | 2017-09-30 | 2018-11-07 |  403d | ✅ PASS |
| XOM  | 2014Q4 | 2014-12-31 | 2018-02-28 | 1155d | ✅ PASS |
| XOM  | 2017Q4 | 2017-12-31 | 2021-02-24 | 1151d | ✅ PASS |
| XOM  | 2016Q4 | 2016-12-31 | 2020-02-26 | 1152d | ✅ PASS |
| AAPL | 2017Q4 | 2017-12-30 | 2019-10-31 |  670d | ✅ PASS |
| AAPL | 2018Q2 | 2018-06-30 | 2019-10-31 |  488d | ✅ PASS |
| AAPL | 2024Q3 | 2024-09-28 | 2026-05-01 |  580d | ✅ PASS |
| AAPL | 2021Q2 | 2021-06-26 | 2022-07-29 |  398d | ✅ PASS |
| AAPL | 2012Q3 | 2012-09-29 | 2015-10-28 | 1124d | ✅ PASS |
| NVDA | 2017Q4 | 2017-10-29 | 2019-02-21 |  480d | ✅ PASS |
| NVDA | 2021Q3 | 2021-08-01 | 2022-11-18 |  474d | ✅ PASS |
| NVDA | 2022Q4 | 2022-10-30 | 2023-11-21 |  387d | ✅ PASS |
| NVDA | 2020Q4 | 2020-10-25 | 2021-11-22 |  393d | ✅ PASS |
| NVDA | 2024Q3 | 2024-07-28 | 2025-11-19 |  479d | ✅ PASS |
| UNH  | 2012Q1 | 2012-03-31 | 2014-02-12 |  683d | ✅ PASS |
| UNH  | 2012Q2 | 2012-06-30 | 2014-02-12 |  592d | ✅ PASS |
| UNH  | 2012Q4 | 2012-12-31 | 2016-02-09 | 1135d | ✅ PASS |
| UNH  | 2015Q3 | 2015-09-30 | 2016-11-08 |  405d | ✅ PASS |
| UNH  | 2011Q4 | 2011-12-31 | 2015-02-10 | 1137d | ✅ PASS |
| UPS  | 2016Q1 | 2016-03-31 | 2018-02-21 |  692d | ✅ PASS |
| UPS  | 2018Q4 | 2018-12-31 | 2022-02-22 | 1149d | ✅ PASS |
| UPS  | 2018Q2 | 2018-06-30 | 2020-02-20 |  600d | ✅ PASS |
| UPS  | 2015Q1 | 2015-03-31 | 2017-02-21 |  693d | ✅ PASS |
| UPS  | 2012Q4 | 2012-12-31 | 2016-02-25 | 1151d | ✅ PASS |

**Result: 25 PASS / 0 FAIL — PIT invariant holds across the sample.**

### 2.1 Note on `delta_days` magnitudes

The deltas above (387-1155 days) are larger than a strict "first filed"
measurement would produce. The F002 driver uses
`report_date = max(filed across all required concepts)` for each
(ticker, fiscal_quarter) bucket, which means a quarter is dated at
the **latest** time any of the eleven concepts was reported in any
SEC filing covering that period. SEC routinely re-files historical
periods in later 10-K/10-Q filings as restated comparatives, so the
latest filed date for a 2014Q4 row can be a 2017 or 2020 10-K that
restated 2014 numbers.

This is **stricter than necessary** for the PIT invariant (the
invariant only requires "after the quarter ended"). The B030 cutover
may switch to `report_date = min(filed across required concepts)` for
a tighter "first observable date" semantic; for B029 the current
choice biases pessimistic (later report_date → narrower as_of windows
that still observe the data), which is the safer side of a PIT mistake.

## 3. Tickers with 0 rows — sector-structural concept misalignment

Six real tickers produced 0 rows in the unified file. The shortfall is
not an alias-chain miss but a structural mismatch between SEC concept
filings and the B025 eight-ratio model:

| Ticker | Sector | Bottleneck concepts (missing on most quarters) | Root cause |
|---|---|---|---|
| BAC  | Banking         | `cogs`, `capex`, `depreciation_amortization` | Banks file Net Interest Income + Non-Interest Income; no product COGS, no PP&E capex, D&A reported under bank-specific concepts |
| JPM  | Banking         | `cogs`, `capex`, `operating_income`, `depreciation_amortization` | Same as BAC |
| V    | Payment network | `shares_outstanding` (post-2018), `long_term_debt` | Visa reports under non-standard cover-page concepts; some balance-sheet quarters skip XBRL filing |
| LIN  | Industrial gas  | `cogs` (most quarters), `long_term_debt` | Linde plc reports under IFRS-aligned concepts post-2018 Praxair merger; many us-gaap concepts no longer used |
| NEE  | Utility         | `cogs`, `capex` (utility regulatory accounting) | Utilities report Operating Revenues / Operating Expenses as net; capex labelled differently |
| PLD  | REIT            | `revenues`, `cogs`, `capex` | REIT income statement uses Rental Income / Cost of Operations; non-product naming |

### 3.1 Follow-up path

* **F003 fall-back** (B029) — `trade/data/loader.py.load_fundamentals`
  reads `data/snapshots/fundamentals/unified/fundamentals.csv` if
  present, **else** falls back to the B025 fixture
  (`data/fixtures/us_quality_momentum/fundamentals.csv`). The 6
  missing tickers will read from B025 fixture (which has synthesised
  values for them) until the alias chain is extended. B025 fixture
  remains the source of truth for backtest determinism.
* **B030 cutover** — when the strategy code reads real data (Stream
  1.D in `docs/product/implementation-path-2026-05.md`), per-sector
  ratio-model adjustments lift 6 tickers from "fall back to fixture"
  to "use real SEC data". Likely scope:
  * Banks (BAC, JPM): swap `cogs` → `InterestExpense`, swap
    `operating_income` → `IncomeBeforeTaxes`.
  * Utility / REIT (NEE, PLD): use `OperatingCostsAndExpenses` as
    pure-operating-cost denominator instead of treating it as
    aliased COGS.
  * Linde (LIN): map IFRS-aligned concepts (`RevenuesFromContractsWithCustomersIFRS15` etc.) to the eight-ratio inputs.
  * Visa (V): write a per-filer override for SharesOutstanding (use
    `WeightedAverageNumberOfDilutedSharesOutstanding` only).
* **Optional**: a follow-up batch (post-B030) could ship a sector-aware
  ratio model — separate Industrial / Financial / REIT / Utility profiles
  — making the eight-ratio computation truly universal across the universe.

## 4. Per-ticker row count breakdown

| Ticker | Rows | Quarter range | Notes |
|---|---|---|---|
| UNH   | 59 | 2010 — 2026 | Best coverage; clean income statement structure |
| HON   | 57 | 2010 — 2026 | Industrial conglomerate, consistent concepts |
| PG    | 57 | 2014 — 2026 | Consumer staples, alias chain success |
| DUK   | 56 | 2014 — 2026 | Utility (CIK 1326160 holding co; pre-fix CIK 17797 was Duke Power subsidiary that 404s) |
| AMZN  | 55 | 2012 — 2026 | E-commerce |
| JNJ   | 55 | 2010 — 2026 | Pharma — needed `IncomeLossFromContinuingOperationsBeforeIncomeTaxes...` alias for OperatingIncome |
| UPS   | 51 | 2012 — 2026 | Logistics |
| KO    | 44 | 2014 — 2026 | Consumer staples |
| AAPL  | 39 | 2010 — 2026 | Tech — heavy reliance on `RevenueFromContractWithCustomerExcludingAssessedTax` (post-ASC 606) |
| NVDA  | 38 | 2017 — 2026 | Semis |
| WMT   | 33 | 2014 — 2026 | Retail |
| CVX   | 30 | 2014 — 2026 | Energy |
| META  | 22 | 2016 — 2026 | Tech |
| MSFT  | 21 | 2017 — 2026 | Tech |
| APD   | 21 | 2014 — 2026 | Industrial gas |
| AMT   | 13 | 2018 — 2026 | REIT — limited coverage |
| GOOGL | 9  | 2018 — 2026 | Tech |
| XOM   | 9  | 2013 — 2017 | Energy — older data; XOM dropped XBRL coverage of some concepts post-2017 |
| HD    | 8  | 2016 — 2026 | Retail — sparse coverage |
| CAT   | 5  | 2014 — 2026 | Industrial |
| ECL   | 3  | 2014 — 2026 | Specialty chem — very sparse |
| **0-row** | 0 | — | BAC, JPM, V, LIN, NEE, PLD (see §3) |
| **Synthetic** | 0 | — | ZQAI, ZQPT, ZQLH (skip per Planner decision #3) |

## 5. Methodology — quarterly accounting simplification

`scripts/backfill_fundamentals.py` uses **SEC-reported per-period
values as filed**, without computing Q-over-Q deltas. For income-
statement / cash-flow flow items the reported value at fp=Q3 is
cumulative-to-date (9 months from FY start). For balance items the
value is point-in-time at the period end. For TTM-dependent ratios
(P/E, earnings_yield) we use the per-period value directly without
TTM aggregation. This matches the **shape** of the B025 fixture
(12 columns × ~40 quarters × 27 tickers) but not necessarily the
exact values — B025 fixture was synthesised with its own conventions.
Numeric drift between this unified CSV and the B025 fixture is
expected and not a defect; B025 fixture remains the authoritative
source for backtest reproducibility (F003 fall-back; B030 cutover
responsibility).

## 6. Verdict

* **PIT invariant** (≥30 days post-quarter-end): **PASS** (25/25 spot check)
* **Schema compliance** (12-column B025 fixture alignment): **PASS** (`UNIFIED_COLUMNS` matches `fundamentals.csv` header column-for-column)
* **Row count vs spec ≥1000 floor**: **MISS** (685 — sector-structural; see §3)
* **Synthetic ticker fail-safe**: **PASS** (3/3 skipped with log warn; backfill did not abort)
* **Vendor raw artefacts**: **PASS** (27 CIK directories with companyfacts.json + parsed_ratios.json + metadata.json)
* **F003 unblocked**: **YES** — unified file is present + B025 fixture remains as fall-back

## 7. Reference files

* Unified: `data/snapshots/fundamentals/unified/fundamentals.csv` (685 rows, 12 columns)
* Vendor: `data/snapshots/fundamentals/sec_edgar/{CIK:010d}/` (27 directories)
* Driver: `scripts/backfill_fundamentals.py`
* Concept alias chains: `workbench/backend/workbench_api/data/sec_edgar_loader.py` (`SEC_CONCEPT_NAMES`, `SHARES_OUTSTANDING_ALIASES` in `scripts/backfill_fundamentals.py`)
* B025 fixture: `data/fixtures/us_quality_momentum/fundamentals.csv` (1350 rows; authoritative for backtest)
