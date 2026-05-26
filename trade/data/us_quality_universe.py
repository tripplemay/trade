"""Repository for the B025 US Quality Momentum data.

Reads point-in-time records from one of two CSV sources:

* The **unified** real-data CSVs produced by the B028/B029 backfill
  drivers under ``data/snapshots/{prices,fundamentals}/unified/`` —
  the default source as of B030 F002.
* The **B025 synthetic fixture** under
  ``data/fixtures/us_quality_momentum/`` — the deterministic fall-back
  used when the unified file does not exist (e.g. CI without backfill)
  and the only source consulted when the ``FORCE_FIXTURE_PATH=1``
  environment variable is set (B030 F002 acceptance §(8); honours
  B025 deterministic backtest reproducibility).

Every loader optionally filters to records visible on or before
``as_of`` so factor calculations downstream cannot see future data.

Resolution priority for :func:`load_prices` / :func:`load_fundamentals`:

1. Explicit ``fixture_dir`` argument (always wins; B025 tests use this
   to pin to a specific fixture checkout).
2. ``FORCE_FIXTURE_PATH=1`` env → default fixture dir.
3. Unified file if it exists on disk.
4. Default fixture dir (B025 synthetic; final fall-back).

The two sources share the same schema (12-column fundamentals, 8-
column daily prices) so the loader can swap between them without any
caller-side conversion (Planner pre-impl adjudication 2026-05-26
decision #1: unified schema column-for-column matches the fixture).

All data the **fixture** branch produces remains synthetic. See
``data/fixtures/us_quality_momentum/README.md`` for the lineage and
hard boundaries. Unified branch data is real SEC EDGAR + Tiingo
ingest (B027–B029).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import pandas as pd

_REPO_ROOT: Path = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURE_DIR: Path = _REPO_ROOT / "data" / "fixtures" / "us_quality_momentum"

# B030 F002 — unified-real-data source paths. Mirror the constants in
# ``trade.data.loader`` (B028 F003 + B029 F003) so a downstream caller
# can reason about both sources from a single import. Schema matches
# the fixture column-for-column (Planner pre-impl adjudication
# decision #1) so the loader can swap between them without any
# caller-side conversion.
UNIFIED_PRICES_PATH: Path = (
    _REPO_ROOT / "data" / "snapshots" / "prices" / "unified" / "prices_daily.csv"
)
UNIFIED_FUNDAMENTALS_PATH: Path = (
    _REPO_ROOT / "data" / "snapshots" / "fundamentals" / "unified" / "fundamentals.csv"
)

# B030 F002 — env var that forces the fixture path even when the
# unified file exists. Used by B025 deterministic backtests to pin
# numerical results (B025 F003 acceptance §(4) hard invariant; see
# also B030 spec §F002 §(8)). Any non-empty value other than ``"1"``
# is treated as unset to avoid accidental "true"/"yes"/etc. triggers.
FORCE_FIXTURE_PATH_ENV: str = "FORCE_FIXTURE_PATH"


def _force_fixture_path() -> bool:
    """Return True iff the caller asked to force the fixture branch.

    Reads :data:`FORCE_FIXTURE_PATH_ENV` from the process environment
    on every call (rather than caching at import) so tests can flip
    the env between test cases without re-importing the module.
    """

    return os.environ.get(FORCE_FIXTURE_PATH_ENV, "").strip() == "1"

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


def _resolve_prices_path(fixture_dir: Path | None) -> Path:
    """Pick the highest-priority on-disk source for :func:`load_prices`.

    See module docstring for the priority list. ``fixture_dir``
    overrides everything (B025 tests pin a specific fixture
    checkout). The unified file is preferred over the default
    fixture once the B028 backfill has been run on this checkout
    AND ``FORCE_FIXTURE_PATH`` is not set.
    """

    if fixture_dir is not None:
        return _resolve_fixture_dir(fixture_dir) / PRICES_FILE_NAME
    if _force_fixture_path():
        return _resolve_fixture_dir(None) / PRICES_FILE_NAME
    if UNIFIED_PRICES_PATH.exists():
        return UNIFIED_PRICES_PATH
    return _resolve_fixture_dir(None) / PRICES_FILE_NAME


def _resolve_fundamentals_path(fixture_dir: Path | None) -> Path:
    """Pick the highest-priority on-disk source for :func:`load_fundamentals`.

    Same priority semantics as :func:`_resolve_prices_path`; see the
    module docstring for the full list. Used by the F002 strategy
    cut-over so the B025 ``us_quality_momentum`` factor pipeline reads
    real SEC EDGAR ratios by default (with the synthetic fixture as a
    deterministic fall-back).
    """

    if fixture_dir is not None:
        return _resolve_fixture_dir(fixture_dir) / FUNDAMENTALS_FILE_NAME
    if _force_fixture_path():
        return _resolve_fixture_dir(None) / FUNDAMENTALS_FILE_NAME
    if UNIFIED_FUNDAMENTALS_PATH.exists():
        return UNIFIED_FUNDAMENTALS_PATH
    return _resolve_fixture_dir(None) / FUNDAMENTALS_FILE_NAME


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

    B030 F002: reads from the unified real-data CSV produced by
    ``scripts/backfill_prices.py`` (B028 F002) when it exists and
    ``FORCE_FIXTURE_PATH`` is unset. Otherwise falls back to the B025
    synthetic fixture. See module docstring for the full resolution
    priority. ``fixture_dir`` (if supplied) pins the source to that
    fixture checkout, bypassing both the env-var and the unified
    file — used by B025 deterministic backtests that need a specific
    pre-baked dataset.
    """

    source_path = _resolve_prices_path(fixture_dir)
    frame = _read_csv(source_path, PRICES_REQUIRED_COLUMNS)
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

    B030 F002: reads from the unified real-data CSV produced by
    ``scripts/backfill_fundamentals.py`` (B029 F002) when it exists
    and ``FORCE_FIXTURE_PATH`` is unset. Otherwise falls back to the
    B025 synthetic fixture. See module docstring for the full
    resolution priority. ``fixture_dir`` (if supplied) pins the
    source to that fixture checkout, bypassing both the env-var and
    the unified file — used by B025 deterministic tests.
    """

    source_path = _resolve_fundamentals_path(fixture_dir)
    frame = _read_csv(source_path, FUNDAMENTALS_REQUIRED_COLUMNS)
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
