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
from typing import Any, Protocol

from workbench_api.data.fundamentals_sync import (
    get_ticker_sector,
    load_close_prices,
    raw_companyfacts_to_parsed_ratios,
)
from workbench_api.data.snapshot_loader import PriceBar

logger = logging.getLogger(__name__)

# ETF set the Master needs: risk_parity universe (SPY/VEA/AGG/GLD/SGOV) + EEM
# (the global_etf_momentum sleeve trades the broad ETF set) + the BL-B011-S2
# HK-China satellite ETFs (MCHI/FXI/KWEB/ASHR — US-listed Phase 1, USD-priced).
# ETFs have no SEC fundamentals, so they are priced-only.
ETF_UNIVERSE: tuple[str, ...] = (
    "AGG",
    "ASHR",
    "DBC",  # B057 F001 — regime-adaptive universe (broad commodities)
    "EEM",
    "FXI",
    "GLD",
    "IEF",  # B057 F001 — regime-adaptive universe (US treasury 7-10y)
    "KWEB",
    "MCHI",
    "QQQ",  # B057 F001 — regime-adaptive universe (US growth)
    "SGOV",
    "SPY",
    "TLT",  # B057 F001 — regime-adaptive universe (US treasury 20y+)
    "VEA",
    "VWO",  # B057 F001 — regime-adaptive universe (emerging markets)
)

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
    @property
    def ticker_cik_map(self) -> dict[str, int | None]: ...

    def fetch_raw_companyfacts(self, ticker: str) -> dict[str, Any]: ...


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


def _fundamentals_dict_to_row(row: dict[str, Any]) -> list[object]:
    """Order a synthesised ratios dict into the unified CSV column order.

    ``raw_companyfacts_to_parsed_ratios`` emits dicts keyed exactly by
    :data:`FUNDAMENTALS_HEADER`, so this is a pure projection."""

    return [row[column] for column in FUNDAMENTALS_HEADER]


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
    # Synthesise the eight quarterly ratios from live SEC companyfacts using the
    # same logic the offline B029 backfill uses (workbench_api.data.
    # fundamentals_sync — hoisted into the deploy artifact for B045 F004 #1).
    # MarketCap-dependent ratios need close prices, sourced from the prices CSV
    # we just wrote (so report-date closes resolve for the equities priced above).
    close_prices = load_close_prices(prices_path)
    fundamental_rows: list[list[object]] = []
    equities = equity_universe()
    cik_map = fundamentals_loader.ticker_cik_map
    for symbol in equities:
        # A true synthetic ticker (CIK None / absent) has no SEC filing — skip,
        # not an error. Only genuine fetch failures on a real CIK count as errors
        # (the F004 #1 fix: never mask a real failure as a benign synthetic skip).
        if cik_map.get(symbol) is None:
            logger.info("data_refresh_fundamentals_skip_synthetic", extra={"symbol": symbol})
            continue
        try:
            payload = fundamentals_loader.fetch_raw_companyfacts(symbol)
        except Exception:  # noqa: BLE001 — best-effort; a real fetch failure is an error
            errors += 1
            logger.exception("data_refresh_fundamentals_fetch_failure", extra={"symbol": symbol})
            continue
        rows, skips = raw_companyfacts_to_parsed_ratios(
            symbol, payload, prices=close_prices, sector=get_ticker_sector(symbol)
        )
        if not rows:
            logger.warning(
                "data_refresh_fundamentals_no_rows",
                extra={"symbol": symbol, "skips": skips[:5]},
            )
        fundamental_rows.extend(_fundamentals_dict_to_row(row) for row in rows)
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
