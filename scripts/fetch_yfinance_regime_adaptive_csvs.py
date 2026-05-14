#!/usr/bin/env python3
"""Opt-in yfinance CSV fetcher for the Regime-Adaptive 9-asset universe.

This helper is the only B014 module that performs network I/O. It is research-only,
public-best-effort, and non-PIT. It fetches daily OHLCV records for SPY, QQQ, VEA, VWO,
IEF, TLT, GLD, DBC, and SGOV via the `yfinance` package (Yahoo Finance public historical
endpoint) and writes one ``<SYMBOL>.csv`` per ticker into a caller supplied output
directory. The script is gated behind the explicit
``--i-understand-this-is-manual-research-data`` flag, runs only on demand (never invoked
by default CI), uses ``yfinance.Ticker.history(auto_adjust=True, actions=False,
raise_errors=True)`` so that returned ``Close`` is split- and dividend-adjusted (mapped
directly to the output ``adjusted_close`` column), and fails closed on yfinance
exceptions, empty results, schema mismatches, or insufficient coverage for non-SGOV
tickers. SGOV's documented inception on 2020-05-28 is treated as the only allowed
short-history case by default. The artifact never authorizes any paper or live trading.

This module replaces the previous Stooq-based fetcher after the upstream Stooq /q/d/l/
endpoint introduced an apikey gate that blocked the Codex F003 real-acquisition step;
the planner directed a pivot to yfinance (free, no API key, pip-installed).
"""

from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import yfinance as yf

from trade.strategies.regime_adaptive.snapshot import REQUIRED_TICKERS

DEFAULT_USER_AGENT = "trade-regime-adaptive-stress-validation/0.2 (research-only)"
MANUAL_CONFIRM_FLAG = "--i-understand-this-is-manual-research-data"
EXPECTED_YF_COLUMNS: tuple[str, ...] = ("Open", "High", "Low", "Close", "Volume")
OUTPUT_CSV_HEADER: tuple[str, ...] = (
    "date",
    "open",
    "high",
    "low",
    "close",
    "adjusted_close",
    "volume",
)
SHORT_HISTORY_INCEPTIONS: dict[str, date] = {
    "SGOV": date(2020, 5, 28),
}
COVERAGE_THRESHOLD = 0.95
DEFAULT_DATE_FROM = date(2018, 1, 1)
DEFAULT_DATE_TO = date(2025, 12, 31)
DEFAULT_ALLOW_SHORT_HISTORY: frozenset[str] = frozenset({"SGOV"})
RESEARCH_ONLY_DISCLAIMER = (
    "research-only public-best-effort non-PIT snapshot; not a trading instruction"
)


class YFinanceFetcherError(RuntimeError):
    """Raised when the opt-in yfinance fetch cannot complete deterministically."""


@dataclass(frozen=True, slots=True)
class FetchRequest:
    output_dir: Path
    date_from: date = DEFAULT_DATE_FROM
    date_to: date = DEFAULT_DATE_TO
    manual_confirmation: bool = False
    allow_short_history: frozenset[str] = DEFAULT_ALLOW_SHORT_HISTORY


@dataclass(frozen=True, slots=True)
class TickerFetchResult:
    ticker: str
    row_count: int
    first_date: date
    last_date: date
    expected_business_days: int
    coverage_ratio: float
    output_file: Path
    short_history_exempt: bool


@dataclass(frozen=True, slots=True)
class FetchSummary:
    output_dir: Path
    date_from: date
    date_to: date
    results: tuple[TickerFetchResult, ...]


@dataclass(frozen=True, slots=True)
class _ParsedRow:
    date: date
    open: float
    high: float
    low: float
    close: float
    adjusted_close: float
    volume: int


def _fetch_ticker_history(symbol: str, start: date, end: date) -> Any:
    """Thin yfinance wrapper kept at module top level so tests can monkeypatch it.

    yfinance's ``end`` parameter is exclusive (pandas slicing convention); we shift it
    forward by one day to keep ``end`` inclusive at the public API surface.
    """

    end_exclusive = end + timedelta(days=1)
    ticker = yf.Ticker(symbol)
    return ticker.history(
        start=start.isoformat(),
        end=end_exclusive.isoformat(),
        auto_adjust=True,
        actions=False,
        raise_errors=True,
    )


def fetch_yfinance_regime_adaptive_csvs(request: FetchRequest) -> FetchSummary:
    """Run the opt-in fetch and return a structured summary.

    The fetch is research-only and never authorizes paper or live trading.
    """

    if not request.manual_confirmation:
        raise YFinanceFetcherError(
            "manual confirmation flag required; yfinance fetcher is opt-in research-only"
        )
    if request.date_to < request.date_from:
        raise YFinanceFetcherError(
            f"date_to {request.date_to.isoformat()} precedes date_from "
            f"{request.date_from.isoformat()}"
        )
    output_dir = request.output_dir.expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)

    results: list[TickerFetchResult] = []
    for ticker in REQUIRED_TICKERS:
        results.append(_fetch_single_ticker(ticker, request, output_dir))
    return FetchSummary(
        output_dir=output_dir,
        date_from=request.date_from,
        date_to=request.date_to,
        results=tuple(results),
    )


def _fetch_single_ticker(
    ticker: str, request: FetchRequest, output_dir: Path
) -> TickerFetchResult:
    short_history_exempt = ticker in request.allow_short_history
    inception = SHORT_HISTORY_INCEPTIONS.get(ticker)
    if short_history_exempt and inception is not None and inception > request.date_from:
        effective_from = inception
    else:
        effective_from = request.date_from
    if effective_from > request.date_to:
        raise YFinanceFetcherError(
            f"effective window for {ticker} is empty: "
            f"{effective_from.isoformat()} > {request.date_to.isoformat()}"
        )
    try:
        frame = _fetch_ticker_history(ticker, effective_from, request.date_to)
    except YFinanceFetcherError:
        raise
    except Exception as exc:  # noqa: BLE001 - yfinance can raise many error types
        raise YFinanceFetcherError(
            f"yfinance.Ticker({ticker!r}).history(...) raised "
            f"{type(exc).__name__}: {exc}"
        ) from exc
    rows = _parse_history_frame(
        ticker=ticker,
        frame=frame,
        effective_from=effective_from,
        effective_to=request.date_to,
    )
    expected = _expected_business_days(effective_from, request.date_to)
    coverage_ratio = (len(rows) / expected) if expected > 0 else 0.0
    if not short_history_exempt and coverage_ratio < COVERAGE_THRESHOLD:
        raise YFinanceFetcherError(
            f"insufficient coverage for {ticker}: {len(rows)}/{expected} business days "
            f"({coverage_ratio:.2%}) is below {COVERAGE_THRESHOLD:.0%} threshold"
        )
    if not rows:
        raise YFinanceFetcherError(
            f"yfinance returned no data rows for {ticker} between "
            f"{effective_from.isoformat()} and {request.date_to.isoformat()}"
        )
    output_file = _write_ticker_csv(output_dir, ticker, rows)
    return TickerFetchResult(
        ticker=ticker,
        row_count=len(rows),
        first_date=rows[0].date,
        last_date=rows[-1].date,
        expected_business_days=expected,
        coverage_ratio=coverage_ratio,
        output_file=output_file,
        short_history_exempt=short_history_exempt,
    )


def _parse_history_frame(
    *,
    ticker: str,
    frame: Any,
    effective_from: date,
    effective_to: date,
) -> list[_ParsedRow]:
    if frame is None:
        raise YFinanceFetcherError(
            f"yfinance returned no DataFrame for {ticker}"
        )
    columns = tuple(getattr(frame, "columns", ()))
    if not columns:
        raise YFinanceFetcherError(
            f"yfinance DataFrame for {ticker} has no columns; "
            f"expected at least {list(EXPECTED_YF_COLUMNS)}"
        )
    missing = [name for name in EXPECTED_YF_COLUMNS if name not in columns]
    if missing:
        raise YFinanceFetcherError(
            f"yfinance DataFrame for {ticker} is missing required columns "
            f"{missing} (got {list(columns)})"
        )
    if int(getattr(frame, "shape", (0, 0))[0]) == 0:
        raise YFinanceFetcherError(
            f"yfinance returned an empty DataFrame for {ticker} between "
            f"{effective_from.isoformat()} and {effective_to.isoformat()}"
        )
    rows: list[_ParsedRow] = []
    for index_value, row in frame.iterrows():
        row_date = _coerce_date(index_value, ticker=ticker)
        if row_date < effective_from or row_date > effective_to:
            raise YFinanceFetcherError(
                f"yfinance row for {ticker} outside requested window "
                f"[{effective_from.isoformat()}, {effective_to.isoformat()}]: "
                f"{row_date.isoformat()}"
            )
        try:
            open_value = float(row["Open"])
            high_value = float(row["High"])
            low_value = float(row["Low"])
            close_value = float(row["Close"])
            volume_value = int(float(row["Volume"]))
        except (TypeError, ValueError) as exc:
            raise YFinanceFetcherError(
                f"malformed numeric value in yfinance row for {ticker} on "
                f"{row_date.isoformat()}: {exc}"
            ) from exc
        rows.append(
            _ParsedRow(
                date=row_date,
                open=open_value,
                high=high_value,
                low=low_value,
                close=close_value,
                adjusted_close=close_value,
                volume=volume_value,
            )
        )
    if not rows:
        raise YFinanceFetcherError(
            f"yfinance DataFrame for {ticker} produced no usable rows"
        )
    rows.sort(key=lambda parsed: parsed.date)
    return rows


def _coerce_date(value: Any, *, ticker: str) -> date:
    # pandas.Timestamp inherits from datetime.datetime which inherits from
    # datetime.date, but Timestamp/datetime do NOT compare cleanly against pure
    # datetime.date instances. Reduce anything richer than a pure date to date()
    # before returning, so the caller can do date-only comparisons safely.
    to_pydatetime = getattr(value, "to_pydatetime", None)
    if callable(to_pydatetime):
        try:
            converted = to_pydatetime()
        except Exception as exc:  # noqa: BLE001 - defensive against vendor objects
            raise YFinanceFetcherError(
                f"could not coerce yfinance index value {value!r} to a date for "
                f"{ticker}: {exc}"
            ) from exc
        if isinstance(converted, datetime):
            return converted.date()
        if isinstance(converted, date):
            return converted
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    date_method = getattr(value, "date", None)
    if callable(date_method):
        try:
            result = date_method()
        except Exception as exc:  # noqa: BLE001 - defensive against vendor objects
            raise YFinanceFetcherError(
                f"could not coerce yfinance index value {value!r} to a date for "
                f"{ticker}: {exc}"
            ) from exc
        if isinstance(result, datetime):
            return result.date()
        if isinstance(result, date):
            return result
    raise YFinanceFetcherError(
        f"yfinance index value {value!r} for {ticker} is not a date-like object"
    )


def _expected_business_days(date_from: date, date_to: date) -> int:
    count = 0
    current = date_from
    while current <= date_to:
        if current.weekday() < 5:
            count += 1
        current += timedelta(days=1)
    return count


def _write_ticker_csv(
    output_dir: Path, ticker: str, rows: list[_ParsedRow]
) -> Path:
    destination = output_dir / f"{ticker}.csv"
    with destination.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(OUTPUT_CSV_HEADER)
        for row in rows:
            writer.writerow(
                [
                    row.date.isoformat(),
                    f"{row.open:.6f}",
                    f"{row.high:.6f}",
                    f"{row.low:.6f}",
                    f"{row.close:.6f}",
                    f"{row.adjusted_close:.6f}",
                    str(row.volume),
                ]
            )
    return destination


def _parse_iso_date(value: str) -> date:
    return date.fromisoformat(value)


def _parse_allow_short_history(value: str) -> frozenset[str]:
    if not value.strip():
        return frozenset()
    return frozenset(token.strip().upper() for token in value.split(",") if token.strip())


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Opt-in yfinance CSV fetcher for the Regime-Adaptive 9-asset universe. "
            "Research-only public-best-effort non-PIT data; never authorizes paper or "
            "live trading."
        )
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Destination directory for per-ticker '<SYMBOL>.csv' files (must be gitignored).",
    )
    parser.add_argument(
        "--from",
        dest="date_from",
        type=_parse_iso_date,
        default=DEFAULT_DATE_FROM,
        help="Earliest date to request from yfinance (default: 2018-01-01).",
    )
    parser.add_argument(
        "--to",
        dest="date_to",
        type=_parse_iso_date,
        default=DEFAULT_DATE_TO,
        help="Latest date to request from yfinance (default: 2025-12-31).",
    )
    parser.add_argument(
        "--allow-short-history",
        dest="allow_short_history",
        type=_parse_allow_short_history,
        default=DEFAULT_ALLOW_SHORT_HISTORY,
        help=(
            "Comma-separated tickers whose late inception (e.g. SGOV 2020-05-28) is "
            "tolerated below the 95%% coverage gate (default: 'SGOV')."
        ),
    )
    parser.add_argument(
        MANUAL_CONFIRM_FLAG,
        dest="manual_confirmation",
        action="store_true",
        help=(
            "Required acknowledgement that this performs a one-time real network "
            "fetch (via yfinance) for research-only public-best-effort non-PIT data "
            "and never authorizes paper or live trading."
        ),
    )
    return parser


def _format_summary(summary: FetchSummary) -> str:
    lines: list[str] = []
    lines.append(
        f"yfinance fetch summary "
        f"({summary.date_from.isoformat()}..{summary.date_to.isoformat()}) "
        f"into {summary.output_dir.as_posix()}:"
    )
    lines.append(RESEARCH_ONLY_DISCLAIMER)
    lines.append("ticker  rows  first         last          coverage  short_history")
    for result in summary.results:
        lines.append(
            f"{result.ticker:<6}  {result.row_count:>4}  "
            f"{result.first_date.isoformat()}  {result.last_date.isoformat()}  "
            f"{result.coverage_ratio:>7.2%}  "
            f"{'yes' if result.short_history_exempt else 'no'}"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    request = FetchRequest(
        output_dir=args.output_dir,
        date_from=args.date_from,
        date_to=args.date_to,
        manual_confirmation=args.manual_confirmation,
        allow_short_history=args.allow_short_history,
    )
    try:
        summary = fetch_yfinance_regime_adaptive_csvs(request)
    except YFinanceFetcherError as exc:
        print(f"fetch failed: {exc}", file=sys.stderr)
        return 2
    print(_format_summary(summary))
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    sys.exit(main())
