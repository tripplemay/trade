"""Repository for the BL-B011-S2 HK-China satellite data (price-only).

Mirrors :mod:`trade.data.us_quality_universe` (B025/B030) but is
**price-only** — the HK-China momentum strategy uses no fundamentals or
earnings calendar (design doc §6: momentum / trend / regional-risk are all
derivable from daily prices). Phase 1 trades only US-listed China/HK ETFs
(MCHI / FXI / KWEB / ASHR), so prices come from the same unified daily-OHLCV
CSV the B045 data-refresh pipeline writes (those four tickers were added to
``data_refresh.ETF_UNIVERSE`` in F001), with the synthetic fixture as the
deterministic fall-back.

Resolution priority for :func:`load_prices` (identical to us_quality):

1. Explicit ``fixture_dir`` argument (always wins; deterministic tests).
2. ``FORCE_FIXTURE_PATH=1`` env → default fixture dir.
3. Unified file if it exists on disk (VM ``WORKBENCH_DATA_ROOT`` aware).
4. Default fixture dir (synthetic; final fall-back).

The unified prices CSV carries every Master-universe symbol, so
:func:`load_prices` filters to the HK-China tickers — a caller asking for
HK-China prices never sees us_quality / risk-parity rows.

All data the **fixture** branch produces is synthetic; see
``data/fixtures/hk_china_momentum/README.md``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from trade.data.data_root import unified_prices_path

_REPO_ROOT: Path = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURE_DIR: Path = _REPO_ROOT / "data" / "fixtures" / "hk_china_momentum"

UNIFIED_PRICES_PATH: Path = (
    _REPO_ROOT / "data" / "snapshots" / "prices" / "unified" / "prices_daily.csv"
)

# Same env contract as us_quality (B030 F002): force the synthetic fixture
# even when the unified file exists, for deterministic backtests.
FORCE_FIXTURE_PATH_ENV: str = "FORCE_FIXTURE_PATH"

UNIVERSE_FILE_NAME = "universe.csv"
PRICES_FILE_NAME = "prices_daily.csv"

# Phase 1 universe — US-listed China/HK ETFs (design doc §4.3). HK-listed
# tickers (2800.HK etc.) are Phase 2. The constant is the price filter for
# the shared unified CSV.
HK_CHINA_TICKERS: tuple[str, ...] = ("MCHI", "FXI", "KWEB", "ASHR")

UNIVERSE_REQUIRED_COLUMNS: tuple[str, ...] = ("ticker", "name", "exposure", "listing_date")
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


@dataclass(frozen=True, slots=True)
class HkChinaUniverseEntry:
    """One HK-China ETF's minimal metadata (price-only strategy → no sector)."""

    ticker: str
    name: str
    exposure: str
    listing_date: date


class HkChinaFixtureError(ValueError):
    """Raised when the fixture cannot be loaded or fails schema validation."""


def _force_fixture_path() -> bool:
    return os.environ.get(FORCE_FIXTURE_PATH_ENV, "").strip() == "1"


def _parse_iso_date(value: object, field: str) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError as exc:
            raise HkChinaFixtureError(f"{field} must be YYYY-MM-DD; got {value!r}") from exc
    raise HkChinaFixtureError(f"{field} must be a date or ISO string; got {value!r}")


def _resolve_fixture_dir(fixture_dir: Path | None) -> Path:
    target = fixture_dir if fixture_dir is not None else DEFAULT_FIXTURE_DIR
    if not target.is_dir():
        raise HkChinaFixtureError(f"fixture directory does not exist: {target}")
    return target


def _resolve_prices_path(fixture_dir: Path | None) -> Path:
    """Pick the highest-priority on-disk source for :func:`load_prices`
    (see module docstring; same semantics as us_quality)."""

    if fixture_dir is not None:
        return _resolve_fixture_dir(fixture_dir) / PRICES_FILE_NAME
    if _force_fixture_path():
        return _resolve_fixture_dir(None) / PRICES_FILE_NAME
    unified = unified_prices_path(UNIFIED_PRICES_PATH)
    if unified.exists():
        return unified
    return _resolve_fixture_dir(None) / PRICES_FILE_NAME


def _read_csv(path: Path, required_columns: tuple[str, ...]) -> pd.DataFrame:
    if not path.is_file():
        raise HkChinaFixtureError(f"fixture file missing: {path}")
    frame = pd.read_csv(path)
    missing = [column for column in required_columns if column not in frame.columns]
    if missing:
        raise HkChinaFixtureError(f"{path.name} missing required columns: {missing}")
    return frame


def load_universe(
    as_of: date | None = None,
    *,
    fixture_dir: Path | None = None,
) -> tuple[HkChinaUniverseEntry, ...]:
    """Return the HK-China ETF universe visible on ``as_of`` (or all if None).

    Tickers with ``listing_date`` strictly after ``as_of`` are excluded."""

    target_dir = _resolve_fixture_dir(fixture_dir)
    frame = _read_csv(target_dir / UNIVERSE_FILE_NAME, UNIVERSE_REQUIRED_COLUMNS)
    entries: list[HkChinaUniverseEntry] = []
    seen: set[str] = set()
    for row in frame.itertuples(index=False):
        record = row._asdict()
        ticker = str(record["ticker"]).strip()
        if not ticker:
            raise HkChinaFixtureError("universe row has empty ticker")
        if ticker in seen:
            raise HkChinaFixtureError(f"duplicate ticker in universe: {ticker}")
        seen.add(ticker)
        listing_date = _parse_iso_date(record["listing_date"], "listing_date")
        if as_of is not None and listing_date > as_of:
            continue
        entries.append(
            HkChinaUniverseEntry(
                ticker=ticker,
                name=str(record["name"]).strip(),
                exposure=str(record["exposure"]).strip(),
                listing_date=listing_date,
            )
        )
    return tuple(entries)


def load_prices(
    as_of: date | None = None,
    *,
    fixture_dir: Path | None = None,
) -> pd.DataFrame:
    """Long-format daily OHLCV for the HK-China ETFs only.

    Reads the unified real-data CSV when present (and ``FORCE_FIXTURE_PATH``
    unset), else the synthetic fixture. Filters to :data:`HK_CHINA_TICKERS`
    (the shared unified CSV holds every Master symbol) and to ``date <=
    as_of`` when provided. Columns: ``date`` (datetime64), ``ticker``,
    ``open/high/low/close/adj_close`` (float), ``volume`` (int)."""

    source_path = _resolve_prices_path(fixture_dir)
    frame = _read_csv(source_path, PRICES_REQUIRED_COLUMNS)
    frame = frame[frame["ticker"].isin(HK_CHINA_TICKERS)]
    frame["date"] = pd.to_datetime(frame["date"], format="%Y-%m-%d")
    if as_of is not None:
        frame = frame[frame["date"] <= pd.Timestamp(as_of)]
    return frame.reset_index(drop=True)
