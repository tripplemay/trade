"""B045 F001 — real-data refresh core.

Fetches real daily prices (Tiingo) + quarterly fundamentals (SEC EDGAR) for
the Master Portfolio universe and writes two unified CSVs in the exact schema
the ``trade`` loaders read:

- ``<data_root>/snapshots/prices/unified/prices_daily.csv`` — columns
  ``date,ticker,open,high,low,close,adj_close,volume`` (trade
  ``UNIFIED_REQUIRED_COLUMNS``).
- ``<data_root>/snapshots/fundamentals/unified/fundamentals.csv`` — columns
  ``report_date,ticker,fiscal_quarter,fiscal_quarter_end,roe,gross_margin,
  fcf_yield,debt_to_assets,pe,pb,ev_ebitda,earnings_yield`` (trade
  ``UNIFIED_FUNDAMENTALS_REQUIRED_COLUMNS``, exact order).

The loaders are injectable so tests drive fakes (no network/secret). On the VM
the timer sets ``--data-root /var/lib/workbench/data``; B045 F002 points the
trade loaders at the same root via ``WORKBENCH_DATA_ROOT``.

Universe = the Master sleeves' symbols: the ETF set (risk_parity 5 + the
momentum ETFs) + the B025 US Quality real equities (from the in-wheel
``equity_universe_tickers``; synthetic ZQ* tickers have no real filings and are
excluded). Fundamentals are fetched for equities only (ETFs have none).
"""

from __future__ import annotations

import csv
import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Protocol

from workbench_api.data.fundamentals_loader import FundamentalsRow
from workbench_api.data.snapshot_loader import PriceBar

logger = logging.getLogger(__name__)

# ETF set the Master needs: risk_parity universe (SPY/VEA/AGG/GLD/SGOV) + EEM
# (the global_etf_momentum sleeve trades the broad ETF set). ETFs have no SEC
# fundamentals, so they are priced-only.
ETF_UNIVERSE: tuple[str, ...] = ("AGG", "EEM", "GLD", "SGOV", "SPY", "VEA")

PRICES_RELPATH = ("snapshots", "prices", "unified", "prices_daily.csv")
FUNDAMENTALS_RELPATH = ("snapshots", "fundamentals", "unified", "fundamentals.csv")

PRICES_HEADER = ["date", "ticker", "open", "high", "low", "close", "adj_close", "volume"]
FUNDAMENTALS_HEADER = [
    "report_date",
    "ticker",
    "fiscal_quarter",
    "fiscal_quarter_end",
    "roe",
    "gross_margin",
    "fcf_yield",
    "debt_to_assets",
    "pe",
    "pb",
    "ev_ebitda",
    "earnings_yield",
]


class _PricesLoader(Protocol):
    def fetch_daily_bars(self, ticker: str, from_date: date, to_date: date) -> list[PriceBar]: ...


class _FundamentalsLoader(Protocol):
    def fetch_quarterly_fundamentals(
        self, ticker: str, from_date: date, to_date: date, sector: str | None = ...
    ) -> list[FundamentalsRow]: ...


@dataclass(frozen=True, slots=True)
class RefreshSummary:
    price_symbols: int
    price_rows: int
    fundamental_symbols: int
    fundamental_rows: int
    errors: int
    prices_path: str
    fundamentals_path: str


def equity_universe() -> tuple[str, ...]:
    """The B025 US Quality real equities.

    Sourced from ``workbench_api.news.ticker_match.equity_universe_tickers``
    (the in-package ``_UNIVERSE_NAMES`` constant — no repo-root read, no
    ``trade`` import, VM-safe; same source the B044 precompute / news CLI use).
    Synthetic ZQ* tickers are excluded (they aren't in that constant)."""

    from workbench_api.news.ticker_match import equity_universe_tickers

    return tuple(equity_universe_tickers())


def price_universe() -> tuple[str, ...]:
    """All symbols to price: ETFs + equities, sorted + de-duplicated."""

    return tuple(sorted(set(ETF_UNIVERSE) | set(equity_universe())))


def _prices_to_rows(bars: list[PriceBar]) -> list[list[object]]:
    return [
        [
            bar.bar_date.isoformat(),
            bar.ticker,
            bar.open,
            bar.high,
            bar.low,
            bar.close,
            bar.adj_close,
            bar.volume,
        ]
        for bar in bars
    ]


def _fundamentals_to_rows(rows: list[FundamentalsRow]) -> list[list[object]]:
    return [
        [
            row.report_date.isoformat(),
            row.ticker,
            row.fiscal_quarter,
            row.fiscal_quarter_end.isoformat(),
            row.roe,
            row.gross_margin,
            row.fcf_yield,
            row.debt_to_assets,
            row.pe,
            row.pb,
            row.ev_ebitda,
            row.earnings_yield,
        ]
        for row in rows
    ]


def _write_csv(path: Path, header: list[str], rows: list[list[object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


def run_refresh(
    *,
    data_root: Path,
    from_date: date,
    to_date: date,
    prices_loader: _PricesLoader,
    fundamentals_loader: _FundamentalsLoader,
) -> RefreshSummary:
    """Fetch prices + fundamentals for the Master universe and write the two
    unified CSVs under ``data_root``. Per-symbol failures are logged + counted
    (best-effort) so one bad symbol never aborts the whole refresh."""

    prices_path = data_root.joinpath(*PRICES_RELPATH)
    fundamentals_path = data_root.joinpath(*FUNDAMENTALS_RELPATH)

    errors = 0

    # --- prices (ETFs + equities) ---
    price_rows: list[list[object]] = []
    symbols = price_universe()
    for symbol in symbols:
        try:
            bars = prices_loader.fetch_daily_bars(symbol, from_date, to_date)
            price_rows.extend(_prices_to_rows(bars))
        except Exception:  # noqa: BLE001 — best-effort; skip a failing symbol
            errors += 1
            logger.exception("data_refresh_price_fetch_failure", extra={"symbol": symbol})
    _write_csv(prices_path, PRICES_HEADER, price_rows)

    # --- fundamentals (equities only; ETFs / synthetic tickers have none) ---
    fundamental_rows: list[list[object]] = []
    equities = equity_universe()
    for symbol in equities:
        try:
            rows = fundamentals_loader.fetch_quarterly_fundamentals(symbol, from_date, to_date)
            fundamental_rows.extend(_fundamentals_to_rows(rows))
        except ValueError:
            # Synthetic ZQ* ticker (CIK is None) — no real filing; skip, not an error.
            logger.info("data_refresh_fundamentals_skip_synthetic", extra={"symbol": symbol})
        except Exception:  # noqa: BLE001 — best-effort; skip a failing symbol
            errors += 1
            logger.exception("data_refresh_fundamentals_fetch_failure", extra={"symbol": symbol})
    _write_csv(fundamentals_path, FUNDAMENTALS_HEADER, fundamental_rows)

    summary = RefreshSummary(
        price_symbols=len(symbols),
        price_rows=len(price_rows),
        fundamental_symbols=len(equities),
        fundamental_rows=len(fundamental_rows),
        errors=errors,
        prices_path=str(prices_path),
        fundamentals_path=str(fundamentals_path),
    )
    logger.info(
        "data_refresh_done",
        extra={
            "price_rows": summary.price_rows,
            "fundamental_rows": summary.fundamental_rows,
            "errors": errors,
        },
    )
    return summary
