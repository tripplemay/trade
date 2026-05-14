#!/usr/bin/env python3
"""Opt-in Stooq CSV fetcher for the Regime-Adaptive 9-asset universe.

This helper is the only B014 module that performs network I/O. It is research-only,
public-best-effort, and non-PIT. It fetches daily OHLCV records for SPY, QQQ, VEA, VWO,
IEF, TLT, GLD, DBC, and SGOV from the free Stooq direct CSV endpoint at
``https://stooq.com/q/d/l/`` and writes one ``<SYMBOL>.csv`` per ticker into a caller
supplied output directory. The script is gated behind the explicit
``--i-understand-this-is-manual-research-data`` flag, runs only on demand (never invoked
by default CI), targets ``stooq.com`` as the only authorized host, uses Python standard
library only (no third-party dependencies), and fails closed on HTTP errors, malformed
responses, or insufficient coverage for non-SGOV tickers. SGOV's documented inception on
2020-05-28 is treated as an allowed short-history case. The artifact never authorizes any
paper or live trading.
"""

from __future__ import annotations

import argparse
import csv
import io
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from trade.strategies.regime_adaptive.snapshot import REQUIRED_TICKERS

STOOQ_HOST = "stooq.com"
STOOQ_BASE_URL = "https://stooq.com/q/d/l/"
DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_USER_AGENT = "trade-regime-adaptive-stress-validation/0.1 (research-only)"
MANUAL_CONFIRM_FLAG = "--i-understand-this-is-manual-research-data"
EXPECTED_STOOQ_HEADER: tuple[str, ...] = ("Date", "Open", "High", "Low", "Close", "Volume")
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


class StooqFetcherError(RuntimeError):
    """Raised when the opt-in Stooq fetch cannot complete deterministically."""


@dataclass(frozen=True, slots=True)
class FetchRequest:
    output_dir: Path
    date_from: date = DEFAULT_DATE_FROM
    date_to: date = DEFAULT_DATE_TO
    manual_confirmation: bool = False
    allow_short_history: frozenset[str] = DEFAULT_ALLOW_SHORT_HISTORY
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    user_agent: str = DEFAULT_USER_AGENT


@dataclass(frozen=True, slots=True)
class TickerFetchResult:
    ticker: str
    http_status: int
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


def fetch_stooq_regime_adaptive_csvs(request: FetchRequest) -> FetchSummary:
    """Run the opt-in fetch and return a structured summary.

    The fetch is research-only and never authorizes paper or live trading.
    """

    if not request.manual_confirmation:
        raise StooqFetcherError(
            "manual confirmation flag required; Stooq fetcher is opt-in research-only"
        )
    if request.date_to < request.date_from:
        raise StooqFetcherError(
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
        raise StooqFetcherError(
            f"effective window for {ticker} is empty: "
            f"{effective_from.isoformat()} > {request.date_to.isoformat()}"
        )
    url = _build_stooq_url(ticker, effective_from, request.date_to)
    payload, http_status = _http_get(
        url=url,
        timeout_seconds=request.timeout_seconds,
        user_agent=request.user_agent,
    )
    rows = _parse_stooq_csv(
        ticker=ticker,
        payload=payload,
        effective_from=effective_from,
        effective_to=request.date_to,
    )
    expected = _expected_business_days(effective_from, request.date_to)
    coverage_ratio = (len(rows) / expected) if expected > 0 else 0.0
    if not short_history_exempt and coverage_ratio < COVERAGE_THRESHOLD:
        raise StooqFetcherError(
            f"insufficient coverage for {ticker}: {len(rows)}/{expected} business days "
            f"({coverage_ratio:.2%}) is below {COVERAGE_THRESHOLD:.0%} threshold"
        )
    if not rows:
        raise StooqFetcherError(
            f"Stooq returned no data rows for {ticker} between "
            f"{effective_from.isoformat()} and {request.date_to.isoformat()}"
        )
    output_file = _write_ticker_csv(output_dir, ticker, rows)
    return TickerFetchResult(
        ticker=ticker,
        http_status=http_status,
        row_count=len(rows),
        first_date=rows[0].date,
        last_date=rows[-1].date,
        expected_business_days=expected,
        coverage_ratio=coverage_ratio,
        output_file=output_file,
        short_history_exempt=short_history_exempt,
    )


def _build_stooq_url(symbol: str, date_from: date, date_to: date) -> str:
    return (
        f"{STOOQ_BASE_URL}?s={symbol.lower()}.us&i=d"
        f"&d1={date_from.strftime('%Y%m%d')}&d2={date_to.strftime('%Y%m%d')}"
    )


def _http_get(*, url: str, timeout_seconds: int, user_agent: str) -> tuple[bytes, int]:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != STOOQ_HOST:
        raise StooqFetcherError(
            f"refusing to fetch {url}: only https://{STOOQ_HOST}/q/d/l/ is authorized"
        )
    request_obj = Request(url, headers={"User-Agent": user_agent})
    try:
        with urlopen(request_obj, timeout=timeout_seconds) as response:
            status = int(getattr(response, "status", 200))
            body = response.read()
    except HTTPError as exc:
        raise StooqFetcherError(
            f"HTTP {exc.code} error fetching {url}: {exc.reason}"
        ) from exc
    except URLError as exc:
        raise StooqFetcherError(f"network error fetching {url}: {exc.reason}") from exc
    if status != 200:
        raise StooqFetcherError(f"non-200 HTTP status {status} fetching {url}")
    if not isinstance(body, (bytes, bytearray)):
        raise StooqFetcherError(
            f"unexpected non-bytes response body from {url}: {type(body).__name__}"
        )
    return bytes(body), status


def _parse_stooq_csv(
    *,
    ticker: str,
    payload: bytes,
    effective_from: date,
    effective_to: date,
) -> list[_ParsedRow]:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise StooqFetcherError(
            f"Stooq response for {ticker} is not valid UTF-8"
        ) from exc
    stripped = text.strip()
    if not stripped:
        raise StooqFetcherError(f"Stooq response for {ticker} is empty")
    handle = io.StringIO(text)
    reader = csv.reader(handle)
    try:
        header = next(reader)
    except StopIteration as exc:  # pragma: no cover - defended by empty-body check above
        raise StooqFetcherError(f"Stooq response for {ticker} has no header") from exc
    if len(header) < len(EXPECTED_STOOQ_HEADER) or tuple(
        header[: len(EXPECTED_STOOQ_HEADER)]
    ) != EXPECTED_STOOQ_HEADER:
        joined = ",".join(header).strip().lower()
        if joined.startswith("no data") or joined == "":
            raise StooqFetcherError(
                f"Stooq reports 'No data' for {ticker} between "
                f"{effective_from.isoformat()} and {effective_to.isoformat()}"
            )
        raise StooqFetcherError(
            f"unexpected Stooq header for {ticker}: {header!r}; "
            f"expected leading columns {list(EXPECTED_STOOQ_HEADER)}"
        )
    rows: list[_ParsedRow] = []
    for raw_row in reader:
        if not raw_row or all(cell == "" for cell in raw_row):
            continue
        if len(raw_row) < len(EXPECTED_STOOQ_HEADER):
            raise StooqFetcherError(
                f"malformed Stooq row for {ticker}: {raw_row!r} (too few columns)"
            )
        date_text, open_text, high_text, low_text, close_text, volume_text = (
            raw_row[0],
            raw_row[1],
            raw_row[2],
            raw_row[3],
            raw_row[4],
            raw_row[5],
        )
        try:
            row_date = date.fromisoformat(date_text)
        except ValueError as exc:
            raise StooqFetcherError(
                f"malformed date {date_text!r} in Stooq row for {ticker}"
            ) from exc
        if row_date < effective_from or row_date > effective_to:
            raise StooqFetcherError(
                f"Stooq row for {ticker} outside requested window "
                f"[{effective_from.isoformat()}, {effective_to.isoformat()}]: {date_text}"
            )
        try:
            open_value = float(open_text)
            high_value = float(high_text)
            low_value = float(low_text)
            close_value = float(close_text)
            volume_value = int(float(volume_text))
        except ValueError as exc:
            raise StooqFetcherError(
                f"malformed numeric value in Stooq row for {ticker}: {raw_row!r}"
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
        raise StooqFetcherError(
            f"Stooq response for {ticker} contained no data rows"
        )
    rows.sort(key=lambda parsed: parsed.date)
    return rows


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
            "Opt-in Stooq CSV fetcher for the Regime-Adaptive 9-asset universe. "
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
        help="Earliest date to request from Stooq (default: 2018-01-01).",
    )
    parser.add_argument(
        "--to",
        dest="date_to",
        type=_parse_iso_date,
        default=DEFAULT_DATE_TO,
        help="Latest date to request from Stooq (default: 2025-12-31).",
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
        "--timeout",
        dest="timeout_seconds",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="HTTP request timeout in seconds (default: 30).",
    )
    parser.add_argument(
        "--user-agent",
        dest="user_agent",
        default=DEFAULT_USER_AGENT,
        help="HTTP User-Agent header (default: research-only identifier).",
    )
    parser.add_argument(
        MANUAL_CONFIRM_FLAG,
        dest="manual_confirmation",
        action="store_true",
        help=(
            "Required acknowledgement that this performs a one-time real network "
            "fetch for research-only public-best-effort non-PIT data and never "
            "authorizes paper or live trading."
        ),
    )
    return parser


def _format_summary(summary: FetchSummary) -> str:
    lines: list[str] = []
    lines.append(
        f"Stooq fetch summary "
        f"({summary.date_from.isoformat()}..{summary.date_to.isoformat()}) "
        f"into {summary.output_dir.as_posix()}:"
    )
    lines.append(RESEARCH_ONLY_DISCLAIMER)
    lines.append(
        "ticker  status  rows  first         last          coverage  short_history"
    )
    for result in summary.results:
        lines.append(
            f"{result.ticker:<6}  {result.http_status:<6}  "
            f"{result.row_count:>4}  {result.first_date.isoformat()}  "
            f"{result.last_date.isoformat()}  "
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
        timeout_seconds=args.timeout_seconds,
        user_agent=args.user_agent,
    )
    try:
        summary = fetch_stooq_regime_adaptive_csvs(request)
    except StooqFetcherError as exc:
        print(f"fetch failed: {exc}", file=sys.stderr)
        return 2
    print(_format_summary(summary))
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    sys.exit(main())
