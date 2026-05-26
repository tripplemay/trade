"""Committed fixture market data loader.

B028 F003 extends this module with :func:`load_prices`, a PIT-enforced
read path that prefers the unified real-data CSV produced by
``scripts/backfill_prices.py`` (B028 F002) and falls back to the B025
fixture (``data/fixtures/us_quality_momentum/prices_daily.csv``) when
the unified file is not on disk. The strategy code stays on the
existing fixture loaders for now; the B030 batch is responsible for
flipping the read paths to the unified source. The infrastructure
lives here so B030 only needs to import this function — no strategy
refactor.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime
from importlib import resources
from pathlib import Path
from typing import Any

import pandas as pd

FIXTURE_FILE_NAME = "market_prices.json"
REQUIRED_PRICE_FIELDS = ("date", "symbol", "open", "close", "adjusted_close", "volume")

# B028 F003 — paths the PIT loader resolves to in priority order.
# Both paths sit under the repo root (loader.py lives at
# ``trade/data/loader.py``; parents[2] is the repo root).
_REPO_ROOT: Path = Path(__file__).resolve().parents[2]
UNIFIED_PRICES_PATH: Path = (
    _REPO_ROOT / "data" / "snapshots" / "prices" / "unified" / "prices_daily.csv"
)
"""Real-data unified CSV produced by ``scripts/backfill_prices.py``.

Schema matches ``data/fixtures/us_quality_momentum/prices_daily.csv``
bit-for-bit: ``date / ticker / open / high / low / close / adj_close /
volume``. Filtered by ``as_of_date`` before being returned so strategy
code never observes future data.
"""

B025_FIXTURE_PRICES_PATH: Path = (
    _REPO_ROOT / "data" / "fixtures" / "us_quality_momentum" / "prices_daily.csv"
)
"""B025 synthetic fixture used as the fallback source when the unified
file does not exist (i.e. before the B028 backfill has been run on this
checkout). Tickers absent from the fixture map to an empty list.
"""

UNIFIED_REQUIRED_COLUMNS: frozenset[str] = frozenset(
    {"date", "ticker", "open", "close", "adj_close", "volume"}
)
"""Minimum schema the unified / fixture CSV must satisfy. ``high`` and
``low`` are accepted but unused — the legacy :class:`PriceBar` shape
doesn't include them. A future extension can widen the dataclass and
this set together.
"""


@dataclass(frozen=True, slots=True)
class PriceBar:
    """Single daily or representative trading-session price record."""

    date: date
    symbol: str
    open: float
    close: float
    adjusted_close: float
    volume: int


@dataclass(frozen=True, slots=True)
class DataSnapshot:
    """Validated fixture data plus deterministic lineage metadata."""

    records: tuple[PriceBar, ...]
    source: str
    adjusted_price_policy: str
    data_snapshot_id: str
    checksum: str
    start_date: date
    end_date: date
    symbols: tuple[str, ...]
    trading_calendar_gaps: tuple[str, ...]
    manifest_path: str | None = None
    manifest_snapshot_id: str | None = None


class FixtureDataError(ValueError):
    """Raised when committed or caller-provided fixture data is invalid."""


def load_fixture_prices(path: Path | None = None) -> DataSnapshot:
    """Load fixture prices from a local JSON file without network or environment access."""

    payload = _read_fixture_payload(path)
    return _snapshot_from_payload(payload)


def load_prices(
    tickers: list[str],
    as_of_date: date,
    from_date: date | None = None,
) -> dict[str, list[PriceBar]]:
    """Return PIT-filtered daily price bars per ticker.

    Reads from :data:`UNIFIED_PRICES_PATH` (real-data unified file
    produced by ``scripts/backfill_prices.py``) when it exists,
    otherwise falls back to :data:`B025_FIXTURE_PRICES_PATH` (B025
    synthetic). Strategy code is intended to migrate to this function
    in the B030 cutover; it does not yet replace the existing fixture
    loaders.

    Args:
        tickers: ticker symbols to fetch; the output dict always
            contains every key, with an empty list for any ticker
            absent from the source.
        as_of_date: PIT cutoff — rows with ``date > as_of_date`` are
            dropped before return. If ``as_of_date`` is in the future
            it is clamped to ``date.today()`` so the loader never
            tries to surface unobservable data.
        from_date: optional lower bound; rows with ``date < from_date``
            are dropped. Useful for windowed backtests that don't need
            the full history each call.

    Returns:
        ``{ticker: [PriceBar...]}`` sorted by date ascending per
        ticker. The :class:`PriceBar` shape uses ``adjusted_close`` /
        ``symbol`` (matching the rest of ``trade.data.loader``); the
        unified CSV's ``adj_close`` column maps onto it.

    Raises:
        FixtureDataError: if either the unified or fallback file is
            present but is missing one of the required schema columns.
            The error text includes a remediation pointer
            (``scripts/backfill_prices.py`` regen).
    """

    if as_of_date > date.today():
        as_of_date = date.today()

    source_path = _resolve_prices_source()
    if source_path is None:
        # Neither the unified file nor the B025 fixture is on disk.
        # Strategy callers asking for prices before either ships shouldn't
        # crash — return an explicitly empty result keyed by every
        # requested ticker.
        return {ticker: [] for ticker in tickers}

    frame = _read_prices_frame(source_path)
    # PIT enforcement happens BEFORE the ticker filter so the per-ticker
    # slice cannot include a row newer than as_of_date by accident.
    frame = frame[frame["date"] <= as_of_date]
    if from_date is not None:
        frame = frame[frame["date"] >= from_date]

    out: dict[str, list[PriceBar]] = {ticker: [] for ticker in tickers}
    if frame.empty:
        return out
    for ticker in tickers:
        ticker_slice = frame[frame["ticker"] == ticker].sort_values("date")
        if ticker_slice.empty:
            continue
        out[ticker] = [_row_to_pricebar(row) for row in ticker_slice.itertuples(index=False)]
    return out


def _resolve_prices_source() -> Path | None:
    """Pick the highest-priority on-disk source for :func:`load_prices`."""

    if UNIFIED_PRICES_PATH.exists():
        return UNIFIED_PRICES_PATH
    if B025_FIXTURE_PRICES_PATH.exists():
        return B025_FIXTURE_PRICES_PATH
    return None


def _read_prices_frame(source_path: Path) -> pd.DataFrame:
    """Read a CSV in the unified-schema shape + parse ``date`` to ``date``."""

    frame = pd.read_csv(source_path)
    missing = UNIFIED_REQUIRED_COLUMNS - set(frame.columns)
    if missing:
        raise FixtureDataError(
            f"prices source {source_path} missing required columns "
            f"{sorted(missing)}; expected at least {sorted(UNIFIED_REQUIRED_COLUMNS)}. "
            "Re-run scripts/backfill_prices.py or restore the B025 fixture."
        )
    frame["date"] = pd.to_datetime(frame["date"]).dt.date
    return frame


def _row_to_pricebar(row: Any) -> PriceBar:
    """Translate a unified-schema CSV row into the trade.data PriceBar shape.

    ``adj_close`` (CSV) → ``adjusted_close`` (PriceBar) and ``ticker``
    (CSV) → ``symbol`` (PriceBar) are the only renames; ``high`` and
    ``low`` are intentionally dropped because the legacy PriceBar
    schema doesn't carry them.
    """

    return PriceBar(
        date=row.date,
        symbol=row.ticker,
        open=float(row.open),
        close=float(row.close),
        adjusted_close=float(row.adj_close),
        volume=int(row.volume),
    )


def load_snapshot_prices(path: Path) -> DataSnapshot:
    """Load an explicitly configured local snapshot without fallback or external access."""

    if path.parts and path.parts[0] not in {"data", "tests"}:
        raise FixtureDataError("snapshot file must be an explicit local data/ or tests/ path")
    if not path.is_file():
        raise FixtureDataError(f"snapshot file does not exist: {path}")
    manifest = _read_manifest_for_snapshot(path)
    payload = _read_fixture_payload(path)
    snapshot = _snapshot_from_payload(payload)
    return DataSnapshot(
        records=snapshot.records,
        source=snapshot.source,
        adjusted_price_policy=snapshot.adjusted_price_policy,
        data_snapshot_id=f"snapshot:{snapshot.checksum[:16]}",
        checksum=snapshot.checksum,
        start_date=snapshot.start_date,
        end_date=snapshot.end_date,
        symbols=snapshot.symbols,
        trading_calendar_gaps=snapshot.trading_calendar_gaps,
        manifest_path=manifest["path"] if manifest else None,
        manifest_snapshot_id=manifest["snapshot_id"] if manifest else None,
    )


def _read_fixture_payload(path: Path | None) -> dict[str, Any]:
    if path is None:
        fixture = resources.files("trade.data.fixtures").joinpath(FIXTURE_FILE_NAME)
        with fixture.open("r", encoding="utf-8") as file:
            payload = json.load(file)
    else:
        with path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
    if not isinstance(payload, dict):
        raise FixtureDataError("fixture payload must be a JSON object")
    return payload


def _read_manifest_for_snapshot(path: Path) -> dict[str, str] | None:
    manifest_path = _find_manifest_for_snapshot(path)
    if manifest_path is None:
        return None
    with manifest_path.open("r", encoding="utf-8") as file:
        manifest = json.load(file)
    snapshot_id = manifest.get("snapshot_id")
    if not isinstance(snapshot_id, str) or not snapshot_id:
        raise FixtureDataError(f"snapshot manifest missing snapshot_id: {manifest_path}")
    return {"path": manifest_path.as_posix(), "snapshot_id": snapshot_id}


def _find_manifest_for_snapshot(path: Path) -> Path | None:
    adjacent_manifest = path.with_name(f"{path.stem}-manifest.json")
    if adjacent_manifest.is_file():
        return adjacent_manifest
    file_hash = _sha256_file(path)
    path_posix = path.as_posix()
    for candidate in sorted(path.parent.glob("*-manifest.json")):
        with candidate.open("r", encoding="utf-8") as file:
            manifest = json.load(file)
        if _manifest_references_file(manifest, path_posix, file_hash):
            return candidate
    return None


def _manifest_references_file(manifest: object, path_posix: str, file_hash: str) -> bool:
    if not isinstance(manifest, dict):
        return False
    files = manifest.get("files")
    if not isinstance(files, list):
        return False
    for file_entry in files:
        if not isinstance(file_entry, dict):
            continue
        manifest_path = file_entry.get("path")
        manifest_hash = file_entry.get("sha256")
        if manifest_path == path_posix and manifest_hash == file_hash:
            return True
    return False


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _snapshot_from_payload(payload: dict[str, Any]) -> DataSnapshot:
    source = _required_string(payload, "source")
    adjusted_price_policy = _required_string(payload, "adjusted_price_policy")
    raw_records = payload.get("records")
    if not isinstance(raw_records, list) or not raw_records:
        raise FixtureDataError("records must be a non-empty list")

    records = tuple(_parse_price_bar(record, index) for index, record in enumerate(raw_records))
    sorted_records = tuple(sorted(records, key=lambda item: (item.date, item.symbol)))

    symbols = tuple(sorted({record.symbol for record in sorted_records}))
    trading_dates = tuple(sorted({record.date for record in sorted_records}))
    _validate_symbol_coverage(sorted_records, trading_dates, symbols)
    checksum = _checksum(source, adjusted_price_policy, sorted_records)

    return DataSnapshot(
        records=sorted_records,
        source=source,
        adjusted_price_policy=adjusted_price_policy,
        data_snapshot_id=f"fixture:{checksum[:16]}",
        checksum=checksum,
        start_date=trading_dates[0],
        end_date=trading_dates[-1],
        symbols=symbols,
        trading_calendar_gaps=_calendar_gaps(trading_dates),
    )


def _parse_price_bar(raw: object, index: int) -> PriceBar:
    if not isinstance(raw, dict):
        raise FixtureDataError(f"record {index} must be a JSON object")
    missing_fields = [field for field in REQUIRED_PRICE_FIELDS if field not in raw]
    if missing_fields:
        raise FixtureDataError(f"record {index} missing fields: {', '.join(missing_fields)}")

    parsed_date = _parse_date(raw["date"], index)
    symbol = _non_empty_string(raw["symbol"], f"record {index} symbol")
    open_price = _positive_float(raw["open"], f"record {index} open")
    close = _positive_float(raw["close"], f"record {index} close")
    adjusted_close = _positive_float(raw["adjusted_close"], f"record {index} adjusted_close")
    volume = _non_negative_int(raw["volume"], f"record {index} volume")
    return PriceBar(
        date=parsed_date,
        symbol=symbol,
        open=open_price,
        close=close,
        adjusted_close=adjusted_close,
        volume=volume,
    )


def _required_string(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    return _non_empty_string(value, field)


def _non_empty_string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise FixtureDataError(f"{field} must be a non-empty string")
    return value.strip()


def _positive_float(value: object, field: str) -> float:
    if not isinstance(value, int | float) or isinstance(value, bool) or value <= 0:
        raise FixtureDataError(f"{field} must be a positive number")
    return float(value)


def _non_negative_int(value: object, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise FixtureDataError(f"{field} must be a non-negative integer")
    return value


def _parse_date(value: object, index: int) -> date:
    if not isinstance(value, str):
        raise FixtureDataError(f"record {index} date must be an ISO date string")
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise FixtureDataError(f"record {index} date must use YYYY-MM-DD") from exc


def _validate_symbol_coverage(
    records: tuple[PriceBar, ...], trading_dates: tuple[date, ...], symbols: tuple[str, ...]
) -> None:
    seen = {(record.date, record.symbol) for record in records}
    duplicate_count = len(records) - len(seen)
    if duplicate_count:
        raise FixtureDataError("records must not contain duplicate date/symbol entries")
    missing = [
        f"{trading_date.isoformat()}:{symbol}"
        for trading_date in trading_dates
        for symbol in symbols
        if (trading_date, symbol) not in seen
    ]
    if missing:
        raise FixtureDataError(f"records missing date/symbol coverage: {', '.join(missing)}")


def _checksum(source: str, adjusted_price_policy: str, records: tuple[PriceBar, ...]) -> str:
    canonical_records = [
        {
            "date": record.date.isoformat(),
            "symbol": record.symbol,
            "open": record.open,
            "close": record.close,
            "adjusted_close": record.adjusted_close,
            "volume": record.volume,
        }
        for record in records
    ]
    canonical = json.dumps(
        {
            "adjusted_price_policy": adjusted_price_policy,
            "records": canonical_records,
            "source": source,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _calendar_gaps(trading_dates: tuple[date, ...]) -> tuple[str, ...]:
    gaps: list[str] = []
    for earlier, later in zip(trading_dates, trading_dates[1:], strict=False):
        if _month_index(later) - _month_index(earlier) > 1:
            gaps.append(f"{earlier.isoformat()}..{later.isoformat()}")
    return tuple(gaps)


def _month_index(value: date) -> int:
    return value.year * 12 + value.month
