"""B062 F001 — shared akshare / baostock frame → PriceBar helpers.

Both the CN provider (akshare ``stock_zh_a_hist`` + baostock) and the HK provider
(akshare ``stock_hk_hist``) receive the same shapes — a pandas-style DataFrame
with Chinese headers (日期/开盘/收盘/最高/最低/成交量) from akshare, or
English-keyed row dicts from baostock — and must turn them into normalised OHLCV
:class:`PriceBar`. Centralising the column-normalisation + bar building here
keeps the per-market providers thin and the parsing identical across markets.

qfq (前复权) convention: the adjusted close IS the close (no separate adjusted
field from these sources), matching the engine's adjusted-close expectation.

request-path safe: stdlib + :class:`PriceBar` only — no akshare / trade /
broker import at module scope.
"""

from __future__ import annotations

from contextlib import suppress
from datetime import date, datetime
from typing import Any

from workbench_api.data.snapshot_loader import PriceBar

# Standard OHLCV field -> the column aliases each source uses (akshare emits
# Chinese headers; baostock English). Resolved case-insensitively.
_OHLCV_ALIASES: dict[str, tuple[str, ...]] = {
    "date": ("日期", "date", "trade_date"),
    "open": ("开盘", "open"),
    "high": ("最高", "high"),
    "low": ("最低", "low"),
    "close": ("收盘", "close"),
    "volume": ("成交量", "volume", "vol"),
}

REQUIRED_FIELDS: tuple[str, ...] = ("date", "open", "high", "low", "close", "volume")


def to_ymd(day: date) -> str:
    """akshare date format (e.g. 20240131)."""
    return day.strftime("%Y%m%d")


def to_iso(day: date) -> str:
    """baostock date format (e.g. 2024-01-31)."""
    return day.strftime("%Y-%m-%d")


def coerce_date(value: object) -> date | None:
    # pandas Timestamp subclasses datetime, so the datetime branch catches it.
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if value is None:
        return None
    text = str(value)[:10]
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        with suppress(ValueError):
            return datetime.strptime(text, fmt).date()
    return None


def coerce_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        result = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if result != result:  # NaN
        return None
    return result


def resolve_columns(columns: list[str]) -> dict[str, str | None]:
    lowered = {c.lower(): c for c in columns}
    resolved: dict[str, str | None] = {}
    for std, aliases in _OHLCV_ALIASES.items():
        match: str | None = None
        for alias in aliases:
            if alias in columns:
                match = alias
                break
            if alias.lower() in lowered:
                match = lowered[alias.lower()]
                break
        resolved[std] = match
    return resolved


def _record_to_bar(
    record: dict[str, Any], cols: dict[str, str], ticker: str
) -> PriceBar | None:
    bar_date = coerce_date(record.get(cols["date"]))
    open_ = coerce_float(record.get(cols["open"]))
    high = coerce_float(record.get(cols["high"]))
    low = coerce_float(record.get(cols["low"]))
    close = coerce_float(record.get(cols["close"]))
    volume = coerce_float(record.get(cols["volume"]))
    if (
        bar_date is None
        or open_ is None
        or high is None
        or low is None
        or close is None
        or volume is None
    ):
        return None
    # qfq (前复权) series: the adjusted close IS the close — no separate field.
    return PriceBar(
        ticker=ticker,
        bar_date=bar_date,
        open=open_,
        high=high,
        low=low,
        close=close,
        adj_close=close,
        volume=int(volume),
    )


def frame_records(
    module: Any, fn_name: str, **kwargs: Any
) -> tuple[list[dict[str, Any]], list[str]]:
    """Call ``module.<fn_name>(**kwargs)`` → ``(records, columns)``.

    Generic over any pandas-like frame (``.columns`` + ``.to_dict('records')``).
    Returns ``([], [])`` on **any** failure — a missing function, a network /
    host error, ``None``, or an unparseable frame — so the caller (a provider's
    fundamentals fetch) degrades honestly to a partial / empty result instead of
    raising. ``module`` is the lazily-imported akshare; no akshare import lives
    at this module's scope (B062 / §12.10.2)."""

    fn = getattr(module, fn_name, None)
    if fn is None:
        return [], []
    try:
        frame = fn(**kwargs)
    except Exception:
        return [], []
    if frame is None:
        return [], []
    try:
        columns = [str(c) for c in frame.columns]
        records: list[dict[str, Any]] = frame.to_dict("records")
    except Exception:
        return [], []
    return records, columns


def bars_from_records(
    records: list[dict[str, Any]], columns: list[str], ticker: str
) -> list[PriceBar]:
    """Normalise akshare / baostock rows into sorted OHLCV PriceBars.

    Returns ``[]`` when any required OHLCV column is missing (the caller treats
    an empty result as "no usable data" and falls back / 404s)."""
    resolved = resolve_columns(columns)
    cols: dict[str, str] = {
        field: name
        for field in REQUIRED_FIELDS
        if (name := resolved[field]) is not None
    }
    if len(cols) != len(REQUIRED_FIELDS):
        return []
    bars = [
        bar
        for record in records
        if (bar := _record_to_bar(record, cols, ticker)) is not None
    ]
    bars.sort(key=lambda b: b.bar_date)
    return bars
