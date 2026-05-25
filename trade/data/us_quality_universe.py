"""Repository for the B025 US Quality Momentum synthetic fixture.

Reads the committed CSV fixture at ``data/fixtures/us_quality_momentum/`` with
strict point-in-time semantics: every loader optionally filters to records
visible on or before ``as_of`` so factor calculations downstream cannot see
future data.

All data is synthetic. See ``data/fixtures/us_quality_momentum/README.md`` for
the lineage and hard boundaries.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import pandas as pd

_REPO_ROOT: Path = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURE_DIR: Path = _REPO_ROOT / "data" / "fixtures" / "us_quality_momentum"

UNIVERSE_FILE_NAME = "universe.csv"
PRICES_FILE_NAME = "prices_daily.csv"
FUNDAMENTALS_FILE_NAME = "fundamentals.csv"
EARNINGS_FILE_NAME = "earnings_calendar.csv"

UNIVERSE_REQUIRED_COLUMNS: tuple[str, ...] = (
    "ticker",
    "name",
    "exchange",
    "gics_sector",
    "gics_industry",
    "listing_date",
    "market_cap_initial",
)
PRICES_REQUIRED_COLUMNS: tuple[str, ...] = (
    "date",
    "ticker",
    "open",
    "high",
    "low",
    "close",
    "adj_close",
    "volume",
)
FUNDAMENTALS_REQUIRED_COLUMNS: tuple[str, ...] = (
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
)
EARNINGS_REQUIRED_COLUMNS: tuple[str, ...] = (
    "ticker",
    "earnings_date",
    "fiscal_quarter",
    "fiscal_quarter_end",
)


@dataclass(frozen=True, slots=True)
class UniverseEntry:
    """One ticker's metadata. Numerical fields are synthetic (see fixture README)."""

    ticker: str
    name: str
    exchange: str
    gics_sector: str
    gics_industry: str
    listing_date: date
    market_cap_initial: float


class UsQualityFixtureError(ValueError):
    """Raised when the fixture cannot be loaded or fails schema validation."""


def _parse_iso_date(value: object, field: str) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError as exc:
            raise UsQualityFixtureError(
                f"{field} must be YYYY-MM-DD; got {value!r}"
            ) from exc
    raise UsQualityFixtureError(f"{field} must be a date or ISO string; got {value!r}")


def _resolve_fixture_dir(fixture_dir: Path | None) -> Path:
    target = fixture_dir if fixture_dir is not None else DEFAULT_FIXTURE_DIR
    if not target.is_dir():
        raise UsQualityFixtureError(f"fixture directory does not exist: {target}")
    return target


def _read_csv(path: Path, required_columns: tuple[str, ...]) -> pd.DataFrame:
    if not path.is_file():
        raise UsQualityFixtureError(f"fixture file missing: {path}")
    frame = pd.read_csv(path)
    missing = [column for column in required_columns if column not in frame.columns]
    if missing:
        raise UsQualityFixtureError(
            f"{path.name} missing required columns: {missing}"
        )
    return frame


def load_universe(
    as_of: date | None = None,
    *,
    fixture_dir: Path | None = None,
) -> tuple[UniverseEntry, ...]:
    """Return the universe as visible on ``as_of`` (or full universe if ``None``).

    Tickers with ``listing_date`` strictly after ``as_of`` are excluded.
    """

    target_dir = _resolve_fixture_dir(fixture_dir)
    frame = _read_csv(target_dir / UNIVERSE_FILE_NAME, UNIVERSE_REQUIRED_COLUMNS)
    entries: list[UniverseEntry] = []
    seen: set[str] = set()
    for row in frame.itertuples(index=False):
        record = row._asdict()
        ticker = str(record["ticker"]).strip()
        if not ticker:
            raise UsQualityFixtureError("universe row has empty ticker")
        if ticker in seen:
            raise UsQualityFixtureError(f"duplicate ticker in universe: {ticker}")
        seen.add(ticker)
        listing_date = _parse_iso_date(record["listing_date"], "listing_date")
        if as_of is not None and listing_date > as_of:
            continue
        market_cap_initial = float(record["market_cap_initial"])
        if market_cap_initial <= 0:
            raise UsQualityFixtureError(
                f"market_cap_initial for {ticker} must be positive"
            )
        entries.append(
            UniverseEntry(
                ticker=ticker,
                name=str(record["name"]).strip(),
                exchange=str(record["exchange"]).strip(),
                gics_sector=str(record["gics_sector"]).strip(),
                gics_industry=str(record["gics_industry"]).strip(),
                listing_date=listing_date,
                market_cap_initial=market_cap_initial,
            )
        )
    return tuple(entries)


def load_prices(
    as_of: date | None = None,
    *,
    fixture_dir: Path | None = None,
) -> pd.DataFrame:
    """Long-format daily OHLCV. Filters to ``date <= as_of`` when provided.

    Returns columns: ``date`` (datetime64), ``ticker`` (object),
    ``open / high / low / close / adj_close`` (float64), ``volume`` (int64).
    """

    target_dir = _resolve_fixture_dir(fixture_dir)
    frame = _read_csv(target_dir / PRICES_FILE_NAME, PRICES_REQUIRED_COLUMNS)
    frame["date"] = pd.to_datetime(frame["date"], format="%Y-%m-%d")
    if as_of is not None:
        frame = frame[frame["date"] <= pd.Timestamp(as_of)]
    return frame.reset_index(drop=True)


def load_fundamentals(
    as_of: date | None = None,
    *,
    fixture_dir: Path | None = None,
) -> pd.DataFrame:
    """Long-format quarterly fundamentals. Filters to ``report_date <= as_of``.

    ``report_date`` is the date the filing is considered public (>= fiscal
    quarter end + 30 days). Factor calculations should not consume rows where
    ``report_date > as_of``.
    """

    target_dir = _resolve_fixture_dir(fixture_dir)
    frame = _read_csv(target_dir / FUNDAMENTALS_FILE_NAME, FUNDAMENTALS_REQUIRED_COLUMNS)
    frame["report_date"] = pd.to_datetime(frame["report_date"], format="%Y-%m-%d")
    frame["fiscal_quarter_end"] = pd.to_datetime(
        frame["fiscal_quarter_end"], format="%Y-%m-%d"
    )
    if as_of is not None:
        frame = frame[frame["report_date"] <= pd.Timestamp(as_of)]
    return frame.reset_index(drop=True)


def load_earnings_calendar(
    as_of: date | None = None,
    *,
    fixture_dir: Path | None = None,
) -> pd.DataFrame:
    """Earnings announcement dates. Filters to ``earnings_date <= as_of`` when provided.

    Unlike fundamentals, this loader returns past announcements only; consumers
    needing forward-looking earnings windows (e.g. F003 financial-results
    avoidance) should call without ``as_of`` and apply their own forward window.
    """

    target_dir = _resolve_fixture_dir(fixture_dir)
    frame = _read_csv(target_dir / EARNINGS_FILE_NAME, EARNINGS_REQUIRED_COLUMNS)
    frame["earnings_date"] = pd.to_datetime(frame["earnings_date"], format="%Y-%m-%d")
    frame["fiscal_quarter_end"] = pd.to_datetime(
        frame["fiscal_quarter_end"], format="%Y-%m-%d"
    )
    if as_of is not None:
        frame = frame[frame["earnings_date"] <= pd.Timestamp(as_of)]
    return frame.reset_index(drop=True)
