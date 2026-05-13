"""Committed fixture market data loader."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime
from importlib import resources
from pathlib import Path
from typing import Any

FIXTURE_FILE_NAME = "market_prices.json"
REQUIRED_PRICE_FIELDS = ("date", "symbol", "open", "close", "adjusted_close", "volume")


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
