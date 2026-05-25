# US Quality Momentum — Synthetic Fixture (B025)

> **synthetic data, not actual filings**
> All numerical fields below — prices, volumes, market caps, fundamental ratios,
> earnings dates — are **synthetic**. Ticker symbols are illustrative.
> This fixture is **not** investment advice, **not** point-in-time production data,
> and **not** live-trading ready. Research/CI use only.

## Purpose

Powers the B025 `us_quality_momentum` strategy (5-factor US equity satellite sleeve)
end-to-end test suite, backtest, and workbench UI demo without any external data
dependency. Loaded by `trade.data.us_quality_universe` (Repository pattern,
point-in-time).

## Files

| File | Rows | Description |
|------|------|-------------|
| `universe.csv` | 30 | Ticker metadata: `ticker, name, exchange, gics_sector, gics_industry, listing_date, market_cap_initial` |
| `prices_daily.csv` | ~86,800 | Daily OHLCV: `date, ticker, open, high, low, close, adj_close, volume`. 2014-12-01 → 2025-12-31 (~11 years × 30 tickers × business days). Prices rounded to 2 decimals. `adj_close == close` (no synthetic splits/dividends). |
| `fundamentals.csv` | 1,350 | Quarterly fundamentals: `report_date, ticker, fiscal_quarter, fiscal_quarter_end, roe, gross_margin, fcf_yield, debt_to_assets, pe, pb, ev_ebitda, earnings_yield`. 30 tickers × 45 quarters (2014Q4 → 2025Q4). |
| `earnings_calendar.csv` | 1,350 | Earnings announcements: `ticker, earnings_date, fiscal_quarter, fiscal_quarter_end`. One row per (ticker, quarter). |
| `_generate.py` | — | Deterministic regenerator script (see below). |
| `README.md` | — | This file. |

### Point-in-Time Rules

- `report_date = fiscal_quarter_end + 35 days` (satisfies spec §4.1 "≥ 30 days").
- `earnings_date = fiscal_quarter_end + 28 days` (always strictly before `report_date`).
- Loaders in `trade/data/us_quality_universe.py` filter both prices and fundamentals
  by `as_of` so factor calculations never see future data.

### Universe Coverage

30 tickers across all 11 GICS sectors (≥2 per sector):

| Sector | Tickers |
|--------|---------|
| Information Technology | AAPL, MSFT, NVDA, ZQPT |
| Health Care | JNJ, UNH, ZQLH |
| Financials | JPM, BAC, V |
| Consumer Discretionary | AMZN, HD |
| Communication Services | GOOGL, META |
| Industrials | HON, UPS, CAT, ZQAI |
| Consumer Staples | PG, KO, WMT |
| Energy | XOM, CVX |
| Utilities | NEE, DUK |
| Real Estate | PLD, AMT |
| Materials | LIN, APD, ECL |

Tickers prefixed `ZQ*` are clearly synthetic by name (e.g., "Synthetic Penny Tech
Holdings") and exist to exercise liquidity-filter boundary conditions:

- `ZQPT` — low share price (typically <$10) and low dollar volume.
- `ZQAI` — small market cap (~$5B initial) and late listing date (2020-06-15).
- `ZQLH` — very low daily share volume.

The remaining 27 tickers use real S&P 500 / Nasdaq 100 symbols as identifiers
only; their numerical fields (prices, fundamentals, volumes, market caps) are
synthetic.

## Regeneration

```bash
.venv/bin/python data/fixtures/us_quality_momentum/_generate.py --seed 42
```

Default seed: `42`. Output is byte-identical between runs of the same seed.

Generator excluded from pytest collection path (lives outside `tests/` and any
Python package). Run only when intentionally rebuilding fixture.

### Synthetic Model

- **Prices**: per-ticker Geometric Brownian Motion. Each ticker has independent
  `numpy.random.default_rng(SeedSequence([seed, ticker_index]))` so individual
  ticker price paths can be reproduced without regenerating others.
- **OHLC**: open/high/low jitter derived deterministically off the simulated close.
- **Volume**: log-normal noise around a per-ticker base share volume.
- **Adjusted close**: equals `close` (no synthetic splits or dividends in fixture).
- **Fundamentals**: per-ticker sector-typical baseline + quarterly Gaussian noise
  on `roe, gross_margin, fcf_yield, debt_to_assets, earnings_yield`. Price-derived
  ratios (`pe, pb, ev_ebitda`) anchored to actual fixture close near `report_date`.
- **Earnings/report cadence**: rigid 28d/35d offsets from each fiscal quarter end.

## File Size Note

`prices_daily.csv` is ~4.6 MB. The B025 spec §4.1 suggests a 2 MB upper bound,
but the spec's other constraints (`≥30 tickers × ≥10 years × 8 daily OHLCV fields`)
yield a CSV of roughly 4–5 MB at 2-decimal precision. Substantive constraints
take precedence over the size hint; the data remains tiny by ML/quant standards
and is checked into git for full offline reproducibility (no LFS).

## Hard Boundaries (B025 §3, continued)

- No real broker / paper / live API URLs touched at any point.
- No paid data source (FactSet / Refinitiv / Bloomberg / EODHD) used.
- No ML model artifacts; `sklearn` is **not** imported by the generator or loader.
- Fixture is the sole data source for B025 CI; tests must pass with no network.

## Lineage

- Created by: B025-F001 Generator (2026-05-25)
- Spec: `docs/specs/B025-us-quality-momentum-satellite-spec.md` §4.1, §5 F001
- Loaded by: `trade/data/us_quality_universe.py` (Repository pattern)
