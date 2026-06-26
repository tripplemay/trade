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
from collections.abc import Sequence
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
from workbench_api.data_refresh.call_timeout import call_with_timeout
from workbench_api.symbols.symbol_ref import SymbolRef

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

# B062 F002 / B063 F002 — candidate A-share + HK universe (the real underlying
# exposure the hk_china proxy ETFs stand in for). akshare fetches these in the
# workbench data_refresh job and appends them as NEW rows to the unified prices
# CSV; the existing US universe rows are UNTOUCHED (US-zero-regression). trade/
# stays offline — it only reads the CSV, and Master scoring (load_prices)
# requests only its US tickers, so these rows are inert for the funded
# strategies (live Master still trades the USD proxy ETFs).
#
# B062 first shipped only the seven mega-cap winners; B063 F002 WIDENS this to a
# multi-sector ~26 set so the real-data research strategy can SELECT names
# point-in-time by rule rather than backtesting hand-picked winners (spec §2
# survivorship/hindsight bias). This list MUST stay in sync with the trade-side
# authority ``trade.data.hk_china_real_universe.REAL_HK_CHINA_UNIVERSE`` (the
# two are separate copies only because the offline ``trade`` engine cannot
# import this workbench module). Best-effort per symbol: a name akshare can't
# fetch is skipped + counted, not fatal.
CN_HK_UNIVERSE: tuple[str, ...] = (
    # Hong Kong (HKD)
    "0700.HK",
    "9988.HK",
    "3690.HK",
    "1810.HK",
    "9618.HK",
    "9999.HK",
    "0941.HK",
    "0939.HK",
    "1398.HK",
    "1288.HK",
    "2318.HK",
    "2628.HK",
    "1299.HK",
    "0883.HK",
    "0386.HK",
    "0388.HK",
    # Mainland A-share (CNY)
    "600519.SH",
    "000858.SZ",
    "000333.SZ",
    "300750.SZ",
    "601012.SH",
    "601318.SH",
    "600036.SH",
    "601398.SH",
    "600900.SH",
    "600276.SH",
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


class _CnFundamentalsLoader(Protocol):
    """B065 F002 — A-share CAS fundamentals → unified ``fundamentals.csv`` rows."""

    def fetch_fundamentals_rows(
        self, ticker: str, from_date: date, to_date: date
    ) -> list[dict[str, Any]]: ...


@dataclass(frozen=True, slots=True)
class RefreshSummary:
    price_symbols: int
    price_rows: int
    fundamental_symbols: int
    fundamental_rows: int
    errors: int
    prices_path: str
    fundamentals_path: str
    cn_hk_symbols: int = 0
    cn_hk_rows: int = 0
    # B065 F001 — A-share universe superset price extension (new rows beyond the
    # CN_HK proxy set; only symbols not already priced are fetched).
    cn_universe_price_symbols: int = 0
    cn_universe_price_rows: int = 0
    # B065 F002 — A-share CAS fundamentals appended to fundamentals.csv (new rows
    # after the US SEC rows; US rows untouched).
    cn_fundamental_symbols: int = 0
    cn_fundamental_rows: int = 0
    # B075 F001 — per-symbol failures isolated to the WIDE A-share blocks (price
    # extension + CAS fundamentals). They are also summed into ``errors`` (one
    # error contract), but tracked separately so the CLI can tolerate a bounded
    # tail of failures over a ~1500-name universe (delisted / suspended names are
    # expected) without failing the whole timer, while US/CN_HK failures stay
    # strict. Partial-failure 优雅 (不炸整轮): the survivors are still written.
    cn_universe_price_errors: int = 0
    cn_fundamental_errors: int = 0


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


def currency_for_symbol(symbol: str) -> str:
    """Display currency derived from the canonical ticker (US→USD / CN→CNY /
    HK→HKD), via :class:`SymbolRef`.

    The unified prices CSV carries currency **implicitly via the ticker suffix**
    (``600519.SH`` / ``0700.HK`` / bare US) — no currency column is added.
    Adding one would rewrite every existing US row (breaking US-zero-regression)
    and widen trade's ``UNIFIED_REQUIRED_COLUMNS`` schema. P1 only needs the
    marker; cross-currency aggregation / FX is Batch 2 (B062 §2)."""

    return SymbolRef.parse(symbol).currency


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


# A-share canonical tickers carry a .SH / .SZ suffix; the unified fundamentals
# CSV's only non-US rows are these CN CAS rows (HK carries no fundamentals).
_CN_FUNDAMENTAL_TICKER_SUFFIXES: tuple[str, ...] = (".SH", ".SZ")


def _read_existing_cn_fundamental_rows(path: Path) -> list[list[object]]:
    """Existing A-share (.SH / .SZ) fundamental rows from ``path`` (``[]`` if absent).

    B078 F004 — the daily refresh runs with ``--no-cn-fundamentals`` (the heavy CN
    CAS fetch is decoupled to the weekly cn-universe job, B075 F002), yet the
    fundamentals.csv write is UNCONDITIONAL. Without preserving them, the daily run
    would overwrite the file with US-only rows and WIPE the ~29k CN rows the weekly
    job wrote → quality_momentum's quality_score empties → all-cash → service
    failure (the pre-existing bug B078 F001 exposed once the daily job started
    completing again). Re-reading the file lets the daily write refresh US while
    leaving CN untouched until the weekly job refetches it.

    US rows are intentionally dropped here (they are re-fetched fresh every run, so
    re-adding them would duplicate). An unexpected/legacy header preserves nothing
    (the weekly job rewrites the whole file) rather than risk mis-parsing. Rows are
    returned in :data:`FUNDAMENTALS_HEADER` column order, ready to append."""

    if not path.is_file():
        return []
    ticker_idx = FUNDAMENTALS_HEADER.index("ticker")
    preserved: list[list[object]] = []
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        if next(reader, None) != FUNDAMENTALS_HEADER:
            return []
        for row in reader:
            if len(row) > ticker_idx and row[ticker_idx].endswith(
                _CN_FUNDAMENTAL_TICKER_SUFFIXES
            ):
                preserved.append(list(row))
    return preserved


def run_refresh(
    *,
    data_root: Path,
    from_date: date,
    to_date: date,
    prices_loader: _PricesLoader,
    fundamentals_loader: _FundamentalsLoader,
    cn_hk_prices_loader: _PricesLoader | None = None,
    cn_extra_price_symbols: Sequence[str] | None = None,
    cn_fundamentals_loader: _CnFundamentalsLoader | None = None,
    cn_fundamentals_symbols: Sequence[str] | None = None,
    cn_fetch_timeout_seconds: float | None = None,
) -> RefreshSummary:
    """Fetch prices + fundamentals for the Master universe and write the two
    unified CSVs under ``data_root``. Per-symbol failures are logged + counted
    (best-effort) so one bad symbol never aborts the whole refresh.

    When ``cn_hk_prices_loader`` is provided (B062 F002), the candidate A-share
    + HK universe is fetched and **appended as new rows** after the US rows; the
    US rows themselves are produced by the unchanged loop above, so the US data
    is byte-identical (US-zero-regression). ``None`` (the default) keeps the
    US-only behaviour fully backward-compatible.

    When ``cn_extra_price_symbols`` is provided (B065 F001), the A-share universe
    superset members **not already priced** above are fetched via the same
    ``cn_hk_prices_loader`` and appended as a third block of new rows (so the
    point-in-time universe builder has prices for turnover). US + CN_HK rows stay
    untouched; ``None`` is fully backward-compatible.

    When ``cn_fundamentals_loader`` + ``cn_fundamentals_symbols`` are provided
    (B065 F002), CAS quarterly fundamentals for those A-shares are mapped to the
    unified schema and **appended after the US SEC rows** in fundamentals.csv (the
    US rows are produced by the unchanged loop above, so they are byte-identical —
    US-zero-regression). ``None`` keeps the US-only fundamentals behaviour.

    ``cn_fetch_timeout_seconds`` (B078 F001) bounds each per-symbol A-share fetch
    (CN_HK prices + universe price extension + CAS fundamentals) to a wall-clock
    deadline so a single hung ``akshare`` call cannot wedge the whole loop (the
    2026-06-22 3-day stuck-``activating`` hang). A timeout fails just that symbol
    (counted as a §34 partial-failure) and the loop advances. ``None`` / 0 runs
    each fetch inline (byte-identical to pre-B078), so the US loop and every
    existing caller are unaffected — the US Tiingo loop is never wrapped."""

    prices_path = data_root.joinpath(*PRICES_RELPATH)
    fundamentals_path = data_root.joinpath(*FUNDAMENTALS_RELPATH)
    # B078 F001 — 0 / None disables the bound (call_with_timeout runs inline).
    cn_timeout = cn_fetch_timeout_seconds or 0.0

    errors = 0

    # --- US prices (ETFs + equities) — UNCHANGED (US-zero-regression) ---
    price_rows: list[list[object]] = []
    symbols = price_universe()
    for symbol in symbols:
        try:
            bars = prices_loader.fetch_daily_bars(symbol, from_date, to_date)
            price_rows.extend(_prices_to_rows(bars))
        except Exception:  # noqa: BLE001 — best-effort; skip a failing symbol
            errors += 1
            logger.exception("data_refresh_price_fetch_failure", extra={"symbol": symbol})

    # --- B062 F002: A-share + HK prices — NEW rows appended after the US rows
    # (the US rows above are untouched). akshare lives only in this workbench
    # job; trade/ stays offline + only reads the CSV. Best-effort per symbol.
    cn_hk_rows: list[list[object]] = []
    cn_hk_symbols = 0
    if cn_hk_prices_loader is not None:
        cn_hk_symbols = len(CN_HK_UNIVERSE)
        for symbol in CN_HK_UNIVERSE:
            try:
                bars = call_with_timeout(
                    cn_timeout,
                    cn_hk_prices_loader.fetch_daily_bars,
                    symbol,
                    from_date,
                    to_date,
                )
                cn_hk_rows.extend(_prices_to_rows(bars))
            except Exception:  # noqa: BLE001 — best-effort; skip a failing/hung symbol
                errors += 1
                logger.exception("data_refresh_cn_hk_fetch_failure", extra={"symbol": symbol})

    # --- B065 F001: A-share universe superset price EXTENSION — NEW rows for the
    # curated wide universe the point-in-time builder ranks. Only symbols NOT
    # already priced above are fetched (deduped against US + CN_HK), so US +
    # CN_HK rows are byte-identical (US-zero-regression). Best-effort per symbol.
    cn_universe_rows: list[list[object]] = []
    cn_universe_price_symbols = 0
    cn_universe_price_errors = 0
    if cn_extra_price_symbols and cn_hk_prices_loader is not None:
        already = set(symbols) | set(CN_HK_UNIVERSE)
        extra = [s for s in dict.fromkeys(cn_extra_price_symbols) if s not in already]
        cn_universe_price_symbols = len(extra)
        for symbol in extra:
            try:
                bars = call_with_timeout(
                    cn_timeout,
                    cn_hk_prices_loader.fetch_daily_bars,
                    symbol,
                    from_date,
                    to_date,
                )
                cn_universe_rows.extend(_prices_to_rows(bars))
            except Exception:  # noqa: BLE001 — best-effort; skip a failing/hung symbol
                errors += 1
                cn_universe_price_errors += 1
                logger.exception("data_refresh_cn_universe_fetch_failure", extra={"symbol": symbol})

    _write_csv(prices_path, PRICES_HEADER, price_rows + cn_hk_rows + cn_universe_rows)

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

    # --- B065 F002: A-share CAS fundamentals — NEW rows appended after the US
    # SEC rows (the US loop above is untouched → US-zero-regression). Each CN row
    # is keyed by the same FUNDAMENTALS_HEADER, so the trade quality/value factors
    # work on A-shares with no change. Best-effort per symbol.
    cn_fundamental_rows: list[list[object]] = []
    cn_fundamental_symbols = 0
    cn_fundamental_errors = 0
    if cn_fundamentals_loader is not None and cn_fundamentals_symbols:
        cn_fundamental_symbols = len(cn_fundamentals_symbols)
        for symbol in cn_fundamentals_symbols:
            try:
                cn_rows = call_with_timeout(
                    cn_timeout,
                    cn_fundamentals_loader.fetch_fundamentals_rows,
                    symbol,
                    from_date,
                    to_date,
                )
            except Exception:  # noqa: BLE001 — best-effort; skip a failing/hung symbol
                errors += 1
                cn_fundamental_errors += 1
                logger.exception(
                    "data_refresh_cn_fundamentals_fetch_failure", extra={"symbol": symbol}
                )
                continue
            cn_fundamental_rows.extend(_fundamentals_dict_to_row(row) for row in cn_rows)
    else:
        # B078 F004 — not fetching CN fundamentals this run (the daily refresh's
        # --no-cn-fundamentals). The write below is unconditional, so preserve the
        # existing CN rows rather than clobber the file to US-only (which emptied
        # quality_momentum → all-cash → service failure). The weekly cn-universe
        # job is the authoritative CN refresh; the daily job just must not wipe it.
        cn_fundamental_rows = _read_existing_cn_fundamental_rows(fundamentals_path)

    _write_csv(
        fundamentals_path, FUNDAMENTALS_HEADER, fundamental_rows + cn_fundamental_rows
    )

    summary = RefreshSummary(
        price_symbols=len(symbols),
        price_rows=len(price_rows),
        fundamental_symbols=len(equities),
        fundamental_rows=len(fundamental_rows),
        errors=errors,
        prices_path=str(prices_path),
        fundamentals_path=str(fundamentals_path),
        cn_hk_symbols=cn_hk_symbols,
        cn_hk_rows=len(cn_hk_rows),
        cn_universe_price_symbols=cn_universe_price_symbols,
        cn_universe_price_rows=len(cn_universe_rows),
        cn_fundamental_symbols=cn_fundamental_symbols,
        cn_fundamental_rows=len(cn_fundamental_rows),
        cn_universe_price_errors=cn_universe_price_errors,
        cn_fundamental_errors=cn_fundamental_errors,
    )
    logger.info(
        "data_refresh_done",
        extra={
            "price_rows": summary.price_rows,
            "cn_hk_rows": summary.cn_hk_rows,
            "cn_universe_price_rows": summary.cn_universe_price_rows,
            # Currency is derived from the canonical ticker (no CSV column).
            "cn_hk_currencies": sorted({currency_for_symbol(s) for s in CN_HK_UNIVERSE}),
            "fundamental_rows": summary.fundamental_rows,
            "cn_fundamental_rows": summary.cn_fundamental_rows,
            "errors": errors,
        },
    )
    return summary
