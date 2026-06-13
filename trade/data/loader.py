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

from trade.data.data_root import unified_fundamentals_path, unified_prices_path
from trade.data.trading_calendar import trading_calendar_gaps

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

# B029 F003 — paths the PIT fundamentals loader resolves to in priority
# order. Same shape convention as the prices pair above. The unified
# CSV is produced by ``scripts/backfill_fundamentals.py`` (B029 F002);
# the B025 fixture remains the deterministic backtest source-of-truth
# (B025 fixture row count > unified row count for the foreseeable
# future — see ``docs/test-reports/B029-pit-validation-2026-05-26.md``
# §3 for the sector-structural gap).
UNIFIED_FUNDAMENTALS_PATH: Path = (
    _REPO_ROOT / "data" / "snapshots" / "fundamentals" / "unified" / "fundamentals.csv"
)
"""Real-data unified CSV produced by ``scripts/backfill_fundamentals.py``.

Schema matches ``data/fixtures/us_quality_momentum/fundamentals.csv``
column-for-column (12 columns; Planner pre-impl adjudication 2026-05-26
decision #1). Filtered by ``effective_date`` before being returned so
strategy code never observes data that wasn't yet visible at
``as_of_date``.
"""

B025_FIXTURE_FUNDAMENTALS_PATH: Path = (
    _REPO_ROOT / "data" / "fixtures" / "us_quality_momentum" / "fundamentals.csv"
)
"""B025 synthetic fundamentals fixture used as the fallback source when
the unified file does not exist. Six tickers in the B025 universe
(BAC/JPM/V/LIN/NEE/PLD) produce zero rows in the unified file due to
sector-structural concept misalignment (see B029 PIT validation
report); F003's fall-back path means strategy code reading those
tickers still gets the B025 synthetic values, preserving B025 backtest
determinism (F003 acceptance §(4) hard invariant).
"""

UNIFIED_FUNDAMENTALS_REQUIRED_COLUMNS: tuple[str, ...] = (
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
"""Exact 12-column schema the fundamentals CSV must satisfy (per
:func:`load_fundamentals`). Order matches the B025 fixture header
1:1 (decision #1). A misshapen CSV raises :class:`FixtureDataError`
with a regen pointer.
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
class FundamentalsRow:
    """One fiscal quarter's eight ratios for one ticker, in the
    canonical B025 fixture column order.

    Schema matches ``data/fixtures/us_quality_momentum/fundamentals.csv``
    1:1 (12 columns; Planner pre-impl adjudication 2026-05-26 decision
    #1). Mirrors :class:`workbench_api.data.fundamentals_loader.FundamentalsRow`
    but lives in the ``trade`` package to keep the strategy / backtest
    layer free of any ``workbench_api`` import dependency. The two
    classes are intentionally structurally identical so a future
    refactor can swap one for the other without a downstream code
    change.

    PIT semantics: ``report_date`` is the SEC filing date (when the
    10-K/10-Q became publicly visible). ``effective_date = report_date +
    1 business day`` is what :func:`load_fundamentals` filters against
    so strategy code observes the row strictly **after** market hours
    on the filing day.
    """

    report_date: date
    ticker: str
    fiscal_quarter: str
    fiscal_quarter_end: date
    roe: float
    gross_margin: float
    fcf_yield: float
    debt_to_assets: float
    pe: float
    pb: float
    ev_ebitda: float
    earnings_yield: float


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
    """Pick the highest-priority on-disk source for :func:`load_prices`.

    The unified path honours the ``WORKBENCH_DATA_ROOT`` override (B045 F002):
    on the VM it resolves under the refresh job's data root; locally / in CI
    (env unset) it stays :data:`UNIFIED_PRICES_PATH` under the repo root. The
    B025 fixture fall-back is unchanged.
    """

    unified = unified_prices_path(UNIFIED_PRICES_PATH)
    if unified.exists():
        return unified
    if B025_FIXTURE_PRICES_PATH.exists():
        return B025_FIXTURE_PRICES_PATH
    return None


def load_fundamentals(
    tickers: list[str],
    as_of_date: date,
) -> dict[str, FundamentalsRow | None]:
    """Return the latest PIT-visible :class:`FundamentalsRow` per ticker.

    Reads from :data:`UNIFIED_FUNDAMENTALS_PATH` (real-data unified CSV
    produced by ``scripts/backfill_fundamentals.py``) when it exists,
    otherwise falls back to :data:`B025_FIXTURE_FUNDAMENTALS_PATH`
    (B025 synthetic fixture; row 1 of B025 universe fixture). Strategy
    code migrates to this function in the B030 cutover; F003 only adds
    the infrastructure.

    PIT enforcement:

    * ``effective_date = report_date + 1 business day`` (using
      ``pandas.tseries.offsets.BusinessDay(1)`` so weekends / US
      federal holidays slide forward to the next trading day).
    * The row is filtered ``effective_date <= as_of_date`` so a row
      filed on ``date(2015, 2, 4)`` (a Wednesday) becomes visible at
      ``date(2015, 2, 5)``; a row filed on a Friday becomes visible
      the next Monday.
    * For each ticker, the **latest** row by ``effective_date`` that
      passes the cutoff is returned. Tickers with no visible row
      (e.g. ``as_of_date`` precedes the first filing) map to ``None``.

    Args:
        tickers: ticker symbols to fetch; the output dict always
            contains every key, with ``None`` for any ticker either
            absent from the source CSV or whose earliest filing
            post-dates ``as_of_date``.
        as_of_date: PIT cutoff for visibility. If in the future, the
            cutoff is clamped to ``date.today()`` so the loader never
            surfaces unobservable data.

    Returns:
        ``{ticker: FundamentalsRow | None}``. The result dict mirrors
        the ``load_prices`` shape (always keyed by every requested
        ticker) so callers can branch on ``None`` without raising.

    Raises:
        FixtureDataError: if either the unified or fallback file is
            present but is missing one of the required schema columns.
            The error text includes a remediation pointer
            (``scripts/backfill_fundamentals.py`` regen).
    """

    if as_of_date > date.today():
        as_of_date = date.today()

    source_path = _resolve_fundamentals_source()
    if source_path is None:
        # Neither the unified file nor the B025 fixture is on disk.
        return {ticker: None for ticker in tickers}

    frame = _read_fundamentals_frame(source_path)
    # ``effective_date = report_date + 1 business day``. ``pandas``
    # offsets stack correctly on a Series of date objects when cast
    # via to_datetime first; the result is a Timestamp Series we drop
    # back to ``date`` for comparison with the ``as_of_date`` argument.
    frame["effective_date"] = (
        pd.to_datetime(frame["report_date"]) + pd.tseries.offsets.BusinessDay(1)
    ).dt.date
    # PIT enforcement happens BEFORE the ticker filter so the per-ticker
    # slice cannot include a row whose effective_date exceeds the cutoff
    # by accident.
    visible = frame[frame["effective_date"] <= as_of_date]

    out: dict[str, FundamentalsRow | None] = {ticker: None for ticker in tickers}
    if visible.empty:
        return out
    for ticker in tickers:
        ticker_slice = visible[visible["ticker"] == ticker].sort_values(
            "effective_date"
        )
        if ticker_slice.empty:
            continue
        out[ticker] = _row_to_fundamentals(ticker_slice.iloc[-1])
    return out


def _resolve_fundamentals_source() -> Path | None:
    """Pick the highest-priority on-disk source for :func:`load_fundamentals`.

    The unified path honours the ``WORKBENCH_DATA_ROOT`` override (B045 F002),
    mirroring :func:`_resolve_prices_source`; the B025 fixture fall-back is
    unchanged.
    """

    unified = unified_fundamentals_path(UNIFIED_FUNDAMENTALS_PATH)
    if unified.exists():
        return unified
    if B025_FIXTURE_FUNDAMENTALS_PATH.exists():
        return B025_FIXTURE_FUNDAMENTALS_PATH
    return None


def _read_fundamentals_frame(source_path: Path) -> pd.DataFrame:
    """Read a CSV in the unified-fundamentals schema and parse dates."""

    frame = pd.read_csv(source_path)
    required = set(UNIFIED_FUNDAMENTALS_REQUIRED_COLUMNS)
    missing = required - set(frame.columns)
    if missing:
        raise FixtureDataError(
            f"fundamentals source {source_path} missing required columns "
            f"{sorted(missing)}; expected at least "
            f"{sorted(UNIFIED_FUNDAMENTALS_REQUIRED_COLUMNS)}. "
            "Re-run scripts/backfill_fundamentals.py or restore the B025 "
            "fixture."
        )
    frame["report_date"] = pd.to_datetime(frame["report_date"]).dt.date
    frame["fiscal_quarter_end"] = pd.to_datetime(frame["fiscal_quarter_end"]).dt.date
    return frame


def _row_to_fundamentals(row: Any) -> FundamentalsRow:
    """Translate a unified-schema CSV row (after PIT filter) into the
    :class:`FundamentalsRow` shape used by the strategy layer.

    ``row`` is a single-row pandas Series (the ``iloc[-1]`` result of
    sort_values + tail). All numeric columns are cast through ``float``
    so a CSV that stored values as strings (the unified driver writes
    decimals as strings) still round-trips into typed floats.
    """

    return FundamentalsRow(
        report_date=row["report_date"],
        ticker=str(row["ticker"]),
        fiscal_quarter=str(row["fiscal_quarter"]),
        fiscal_quarter_end=row["fiscal_quarter_end"],
        roe=float(row["roe"]),
        gross_margin=float(row["gross_margin"]),
        fcf_yield=float(row["fcf_yield"]),
        debt_to_assets=float(row["debt_to_assets"]),
        pe=float(row["pe"]),
        pb=float(row["pb"]),
        ev_ebitda=float(row["ev_ebitda"]),
        earnings_yield=float(row["earnings_yield"]),
    )


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
        trading_calendar_gaps=trading_calendar_gaps(trading_dates),
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
