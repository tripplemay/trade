"""Synthetic data generator for the US Quality Momentum fixture (B025).

This module produces deterministic synthetic CSVs covering universe, prices,
fundamentals, and earnings calendar for the B025 strategy.

All numerical fields are SYNTHETIC; ticker symbols are illustrative.
The fixture does not contain actual filings, broker data, or investment advice.

Run from repo root (committed CSVs are reproduced bit-for-bit with the same seed)::

    .venv/bin/python data/fixtures/us_quality_momentum/_generate.py --seed 42

Excluded from pytest CI path (see B025 F001 acceptance).
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

FIXTURE_DIR = Path(__file__).resolve().parent
DEFAULT_SEED = 42
START_DATE = date(2014, 12, 1)
END_DATE = date(2025, 12, 31)
REPORT_DATE_LAG_DAYS = 35  # >= 30 days after fiscal quarter end (spec §4.1)
EARNINGS_DATE_LAG_DAYS = 28  # <= report_date (28 < 35); generally before report


@dataclass(frozen=True)
class UniverseRow:
    ticker: str
    name: str
    exchange: str
    gics_sector: str
    gics_industry: str
    listing_date: str
    market_cap_initial: float
    # Per-ticker price simulation parameters (synthetic)
    init_price: float
    drift_annual: float
    sigma_annual: float
    base_volume_shares: int
    # Per-ticker fundamentals baseline (synthetic)
    roe_base: float
    gross_margin_base: float
    fcf_yield_base: float
    debt_to_assets_base: float
    earnings_yield_base: float
    pe_base: float
    pb_base: float
    ev_ebitda_base: float


# 30 illustrative tickers across all 11 GICS sectors (>=2 per sector).
# market_cap_initial in USD; init_price in USD. All values synthetic.
UNIVERSE_SPEC: tuple[UniverseRow, ...] = (
    UniverseRow("AAPL", "Apple Inc.", "NASDAQ", "Information Technology",
                "Technology Hardware, Storage & Peripherals", "1980-12-12",
                7.0e11, 110.0, 0.16, 0.27, 60_000_000,
                0.45, 0.42, 0.05, 0.32, 0.05, 22.0, 12.0, 16.0),
    UniverseRow("MSFT", "Microsoft Corporation", "NASDAQ", "Information Technology",
                "Systems Software", "1986-03-13",
                5.5e11, 45.0, 0.18, 0.25, 35_000_000,
                0.40, 0.69, 0.04, 0.30, 0.045, 25.0, 8.0, 18.0),
    UniverseRow("NVDA", "NVIDIA Corporation", "NASDAQ", "Information Technology",
                "Semiconductors", "1999-01-22",
                1.1e11, 20.0, 0.32, 0.42, 30_000_000,
                0.32, 0.62, 0.03, 0.18, 0.025, 35.0, 12.0, 28.0),
    UniverseRow("JNJ", "Johnson & Johnson", "NYSE", "Health Care",
                "Pharmaceuticals", "1944-09-25",
                4.0e11, 100.0, 0.05, 0.16, 8_000_000,
                0.28, 0.66, 0.06, 0.40, 0.055, 18.0, 6.0, 14.0),
    UniverseRow("UNH", "UnitedHealth Group Incorporated", "NYSE", "Health Care",
                "Managed Health Care", "1984-10-17",
                3.0e11, 100.0, 0.13, 0.21, 4_000_000,
                0.22, 0.24, 0.05, 0.36, 0.06, 17.0, 4.0, 12.0),
    UniverseRow("JPM", "JPMorgan Chase & Co.", "NYSE", "Financials",
                "Diversified Banks", "1969-03-05",
                4.5e11, 60.0, 0.09, 0.24, 15_000_000,
                0.13, 0.55, 0.04, 0.88, 0.085, 11.0, 1.5, 12.0),
    UniverseRow("BAC", "Bank of America Corporation", "NYSE", "Financials",
                "Diversified Banks", "1972-10-30",
                2.0e11, 18.0, 0.08, 0.26, 45_000_000,
                0.10, 0.52, 0.03, 0.89, 0.08, 12.0, 1.2, 13.0),
    UniverseRow("V", "Visa Inc.", "NYSE", "Financials",
                "Transaction & Payment Processing", "2008-03-19",
                3.0e11, 60.0, 0.13, 0.21, 8_000_000,
                0.30, 0.80, 0.05, 0.42, 0.04, 28.0, 9.0, 22.0),
    UniverseRow("AMZN", "Amazon.com, Inc.", "NASDAQ", "Consumer Discretionary",
                "Broadline Retail", "1997-05-15",
                4.0e11, 150.0, 0.18, 0.32, 35_000_000,
                0.12, 0.42, 0.03, 0.55, 0.02, 50.0, 10.0, 25.0),
    UniverseRow("HD", "The Home Depot, Inc.", "NYSE", "Consumer Discretionary",
                "Home Improvement Retail", "1981-09-22",
                3.0e11, 110.0, 0.12, 0.22, 4_500_000,
                0.45, 0.33, 0.06, 0.65, 0.05, 21.0, 100.0, 16.0),
    UniverseRow("GOOGL", "Alphabet Inc. Class A", "NASDAQ", "Communication Services",
                "Interactive Media & Services", "2004-08-19",
                5.0e11, 25.0, 0.14, 0.24, 25_000_000,
                0.22, 0.55, 0.04, 0.10, 0.05, 22.0, 5.0, 16.0),
    UniverseRow("META", "Meta Platforms, Inc.", "NASDAQ", "Communication Services",
                "Interactive Media & Services", "2012-05-18",
                3.0e11, 75.0, 0.16, 0.34, 20_000_000,
                0.24, 0.78, 0.05, 0.13, 0.045, 23.0, 6.0, 14.0),
    UniverseRow("HON", "Honeywell International Inc.", "NASDAQ", "Industrials",
                "Industrial Conglomerates", "1985-09-19",
                1.2e11, 95.0, 0.08, 0.20, 3_500_000,
                0.27, 0.32, 0.05, 0.55, 0.05, 20.0, 8.0, 15.0),
    UniverseRow("UPS", "United Parcel Service, Inc.", "NYSE", "Industrials",
                "Air Freight & Logistics", "1999-11-10",
                1.3e11, 100.0, 0.07, 0.22, 4_000_000,
                0.55, 0.21, 0.06, 0.70, 0.06, 16.0, 30.0, 12.0),
    UniverseRow("CAT", "Caterpillar Inc.", "NYSE", "Industrials",
                "Construction Machinery & Heavy Trucks", "1929-12-02",
                1.0e11, 90.0, 0.09, 0.26, 4_000_000,
                0.34, 0.32, 0.05, 0.66, 0.06, 17.0, 6.0, 11.0),
    UniverseRow("PG", "The Procter & Gamble Company", "NYSE", "Consumer Staples",
                "Personal Care Products", "1929-01-01",
                2.2e11, 85.0, 0.05, 0.15, 7_000_000,
                0.24, 0.51, 0.05, 0.50, 0.045, 23.0, 6.0, 17.0),
    UniverseRow("KO", "The Coca-Cola Company", "NYSE", "Consumer Staples",
                "Soft Drinks & Non-alcoholic Beverages", "1919-09-05",
                2.0e11, 42.0, 0.04, 0.14, 13_000_000,
                0.40, 0.60, 0.05, 0.65, 0.04, 24.0, 9.0, 18.0),
    UniverseRow("WMT", "Walmart Inc.", "NYSE", "Consumer Staples",
                "Consumer Staples Merchandise Retail", "1972-08-25",
                3.0e11, 85.0, 0.07, 0.17, 6_500_000,
                0.21, 0.25, 0.04, 0.60, 0.04, 26.0, 5.0, 14.0),
    UniverseRow("XOM", "Exxon Mobil Corporation", "NYSE", "Energy",
                "Integrated Oil & Gas", "1972-01-03",
                3.5e11, 90.0, 0.05, 0.25, 18_000_000,
                0.12, 0.32, 0.04, 0.45, 0.07, 14.0, 1.6, 10.0),
    UniverseRow("CVX", "Chevron Corporation", "NYSE", "Energy",
                "Integrated Oil & Gas", "1977-01-03",
                2.2e11, 110.0, 0.05, 0.24, 9_000_000,
                0.10, 0.35, 0.04, 0.40, 0.065, 15.0, 1.5, 11.0),
    UniverseRow("NEE", "NextEra Energy, Inc.", "NYSE", "Utilities",
                "Multi-Utilities", "1971-03-15",
                1.3e11, 50.0, 0.06, 0.16, 8_000_000,
                0.11, 0.40, 0.02, 0.60, 0.035, 28.0, 3.0, 16.0),
    UniverseRow("DUK", "Duke Energy Corporation", "NYSE", "Utilities",
                "Electric Utilities", "2006-04-03",
                7.5e10, 80.0, 0.04, 0.14, 3_500_000,
                0.08, 0.30, 0.02, 0.70, 0.04, 20.0, 1.6, 13.0),
    UniverseRow("PLD", "Prologis, Inc.", "NYSE", "Real Estate",
                "Industrial REITs", "1997-11-24",
                6.0e10, 50.0, 0.10, 0.22, 4_000_000,
                0.07, 0.78, 0.03, 0.42, 0.03, 32.0, 2.6, 22.0),
    UniverseRow("AMT", "American Tower Corporation", "NYSE", "Real Estate",
                "Telecom Tower REITs", "1998-06-05",
                8.5e10, 95.0, 0.09, 0.21, 3_000_000,
                0.18, 0.70, 0.03, 0.75, 0.025, 35.0, 12.0, 24.0),
    UniverseRow("LIN", "Linde plc", "NYSE", "Materials",
                "Industrial Gases", "2018-10-30",
                1.0e11, 140.0, 0.10, 0.18, 2_500_000,
                0.14, 0.43, 0.05, 0.42, 0.05, 21.0, 3.0, 16.0),
    UniverseRow("APD", "Air Products and Chemicals, Inc.", "NYSE", "Materials",
                "Industrial Gases", "1961-12-12",
                6.0e10, 145.0, 0.07, 0.19, 1_800_000,
                0.16, 0.31, 0.05, 0.45, 0.05, 22.0, 4.0, 15.0),
    UniverseRow("ECL", "Ecolab Inc.", "NYSE", "Materials",
                "Specialty Chemicals", "1957-11-25",
                5.5e10, 110.0, 0.08, 0.18, 1_500_000,
                0.18, 0.41, 0.04, 0.50, 0.04, 28.0, 7.0, 18.0),
    UniverseRow("ZQAI", "Synthetic Industrial Smallcap Co.", "NYSE", "Industrials",
                "Industrial Machinery & Supplies & Components", "2020-06-15",
                5.0e9, 30.0, 0.06, 0.30, 800_000,
                0.09, 0.22, 0.02, 0.55, 0.05, 19.0, 1.8, 13.0),
    UniverseRow("ZQPT", "Synthetic Penny Tech Holdings", "NASDAQ", "Information Technology",
                "Application Software", "2019-03-10",
                1.2e10, 8.0, 0.02, 0.40, 1_500_000,
                0.05, 0.40, 0.01, 0.30, 0.02, 45.0, 3.0, 30.0),
    UniverseRow("ZQLH", "Synthetic Light Volume Health Inc.", "NYSE", "Health Care",
                "Health Care Equipment", "2018-11-08",
                2.5e10, 60.0, 0.06, 0.22, 250_000,
                0.10, 0.55, 0.03, 0.35, 0.04, 27.0, 4.0, 19.0),
)


def _build_universe_dataframe() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ticker": [u.ticker for u in UNIVERSE_SPEC],
            "name": [u.name for u in UNIVERSE_SPEC],
            "exchange": [u.exchange for u in UNIVERSE_SPEC],
            "gics_sector": [u.gics_sector for u in UNIVERSE_SPEC],
            "gics_industry": [u.gics_industry for u in UNIVERSE_SPEC],
            "listing_date": [u.listing_date for u in UNIVERSE_SPEC],
            "market_cap_initial": [u.market_cap_initial for u in UNIVERSE_SPEC],
        }
    )


def _trading_days(start: date, end: date) -> pd.DatetimeIndex:
    return pd.bdate_range(start=pd.Timestamp(start), end=pd.Timestamp(end))


def _simulate_prices(
    universe: tuple[UniverseRow, ...],
    trading_days: pd.DatetimeIndex,
    seed: int,
) -> pd.DataFrame:
    """Geometric Brownian Motion per ticker with deterministic per-ticker streams."""
    dt = 1.0 / 252.0
    rows: list[pd.DataFrame] = []
    for ticker_index, row in enumerate(universe):
        # Each ticker gets an independent stream rooted at (seed, ticker_index).
        rng = np.random.default_rng(np.random.SeedSequence([seed, ticker_index]))
        n = len(trading_days)
        z = rng.standard_normal(n)
        drift = (row.drift_annual - 0.5 * row.sigma_annual**2) * dt
        diffusion = row.sigma_annual * np.sqrt(dt) * z
        log_returns = drift + diffusion
        log_prices = np.log(row.init_price) + np.cumsum(log_returns)
        close = np.exp(log_prices)

        # Intraday OHLC built deterministically off close.
        open_jitter = rng.normal(loc=0.0, scale=0.003, size=n)
        prev_close = np.concatenate(([row.init_price], close[:-1]))
        open_ = prev_close * (1.0 + open_jitter)
        intraday_range = np.abs(rng.normal(loc=0.0, scale=0.008, size=n))
        upper = np.maximum(open_, close) * (1.0 + intraday_range)
        lower = np.minimum(open_, close) * (1.0 - intraday_range)
        # adj_close == close: the synthetic fixture deliberately omits splits/dividends.
        adj_close = close

        # Volume drift around base; log-normal noise keeps positivity.
        vol_noise = rng.normal(loc=0.0, scale=0.25, size=n)
        volume = (row.base_volume_shares * np.exp(vol_noise)).astype(np.int64)

        ticker_rows = pd.DataFrame(
            {
                "date": trading_days.strftime("%Y-%m-%d"),
                "ticker": row.ticker,
                "open": np.round(open_, 2),
                "high": np.round(upper, 2),
                "low": np.round(lower, 2),
                "close": np.round(close, 2),
                "adj_close": np.round(adj_close, 2),
                "volume": volume,
            }
        )
        rows.append(ticker_rows)
    prices = pd.concat(rows, ignore_index=True)
    return prices.sort_values(["date", "ticker"]).reset_index(drop=True)


def _fiscal_quarter_ends(start: date, end: date) -> list[date]:
    quarters: list[date] = []
    year = start.year
    while True:
        for month, day in ((3, 31), (6, 30), (9, 30), (12, 31)):
            qend = date(year, month, day)
            if qend < start:
                continue
            if qend > end:
                return quarters
            quarters.append(qend)
        year += 1


def _quarter_label(qend: date) -> str:
    quarter = (qend.month - 1) // 3 + 1
    return f"{qend.year}Q{quarter}"


def _ticker_quarter_close(
    prices: pd.DataFrame, ticker: str, target_date: date
) -> float:
    """Return the most recent ticker close on/before target_date (or first close after)."""
    ticker_slice = prices[prices["ticker"] == ticker]
    on_or_before = ticker_slice[ticker_slice["date"] <= target_date.isoformat()]
    if not on_or_before.empty:
        return float(on_or_before.iloc[-1]["close"])
    return float(ticker_slice.iloc[0]["close"])


def _build_fundamentals(
    universe: tuple[UniverseRow, ...],
    prices: pd.DataFrame,
    quarter_ends: list[date],
    seed: int,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for ticker_index, row in enumerate(universe):
        rng = np.random.default_rng(np.random.SeedSequence([seed, 7919, ticker_index]))
        for qend in quarter_ends:
            report_date = qend + timedelta(days=REPORT_DATE_LAG_DAYS)
            noise = rng.normal(loc=0.0, scale=1.0, size=5)
            roe = max(0.0, row.roe_base + noise[0] * row.roe_base * 0.10)
            gross_margin = float(
                np.clip(row.gross_margin_base + noise[1] * 0.02, 0.05, 0.95)
            )
            fcf_yield = max(0.0, row.fcf_yield_base + noise[2] * 0.005)
            debt_to_assets = float(
                np.clip(row.debt_to_assets_base + noise[3] * 0.03, 0.05, 0.95)
            )
            earnings_yield = max(0.005, row.earnings_yield_base + noise[4] * 0.005)
            # Price-derived ratios pegged to actual fixture close at report_date approx.
            close_near_report = _ticker_quarter_close(prices, row.ticker, report_date)
            pe = round(1.0 / earnings_yield, 2)
            pb = round(row.pb_base * (close_near_report / row.init_price) ** 0.5, 2)
            ev_ebitda = round(
                row.ev_ebitda_base * (close_near_report / row.init_price) ** 0.5, 2
            )
            rows.append(
                {
                    "report_date": report_date.isoformat(),
                    "ticker": row.ticker,
                    "fiscal_quarter": _quarter_label(qend),
                    "fiscal_quarter_end": qend.isoformat(),
                    "roe": round(roe, 4),
                    "gross_margin": round(gross_margin, 4),
                    "fcf_yield": round(fcf_yield, 4),
                    "debt_to_assets": round(debt_to_assets, 4),
                    "pe": pe,
                    "pb": pb,
                    "ev_ebitda": ev_ebitda,
                    "earnings_yield": round(earnings_yield, 4),
                }
            )
    return (
        pd.DataFrame(rows)
        .sort_values(["report_date", "ticker"])
        .reset_index(drop=True)
    )


def _build_earnings_calendar(
    universe: tuple[UniverseRow, ...],
    quarter_ends: list[date],
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for row in universe:
        for qend in quarter_ends:
            earnings_date = qend + timedelta(days=EARNINGS_DATE_LAG_DAYS)
            rows.append(
                {
                    "ticker": row.ticker,
                    "earnings_date": earnings_date.isoformat(),
                    "fiscal_quarter": _quarter_label(qend),
                    "fiscal_quarter_end": qend.isoformat(),
                }
            )
    return (
        pd.DataFrame(rows)
        .sort_values(["earnings_date", "ticker"])
        .reset_index(drop=True)
    )


def main(seed: int = DEFAULT_SEED, output_dir: Path | None = None) -> None:
    target_dir = output_dir or FIXTURE_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    universe_df = _build_universe_dataframe()
    universe_df.to_csv(target_dir / "universe.csv", index=False)

    trading_days = _trading_days(START_DATE, END_DATE)
    prices_df = _simulate_prices(UNIVERSE_SPEC, trading_days, seed)
    prices_df.to_csv(target_dir / "prices_daily.csv", index=False)

    quarter_ends = _fiscal_quarter_ends(START_DATE, END_DATE)
    fundamentals_df = _build_fundamentals(UNIVERSE_SPEC, prices_df, quarter_ends, seed)
    fundamentals_df.to_csv(target_dir / "fundamentals.csv", index=False)

    earnings_df = _build_earnings_calendar(UNIVERSE_SPEC, quarter_ends)
    earnings_df.to_csv(target_dir / "earnings_calendar.csv", index=False)


def _cli() -> None:
    parser = argparse.ArgumentParser(
        description="Regenerate the B025 us_quality_momentum synthetic fixture."
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
        help=f"Deterministic RNG seed (default: {DEFAULT_SEED}).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Override output directory (default: this file's directory).",
    )
    args = parser.parse_args()
    main(seed=args.seed, output_dir=args.output_dir)


if __name__ == "__main__":
    _cli()
