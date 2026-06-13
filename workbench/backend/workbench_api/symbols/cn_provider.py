"""B061 F002 — China A-share ``SymbolDataProvider`` (akshare main + baostock fallback).

The CN implementation of the B059 provider abstraction. akshare (东财 EOD
history) is primary — B060's P0 spike found it the most reachable from the
overseas prod VM; baostock is the cross-check / fallback when akshare is
unavailable or returns nothing. Both are **data** libraries (databases), never
broker SDKs — the no-broker guard's banlist is futu / tiger / ib / alpaca / …,
which this module never touches.

canonical ↔ native adaptation (path-doc §9.2) lives here: a ``600519.SH``
canonical becomes akshare's ``600519`` (6-digit code) or baostock's
``sh.600519``. The :class:`SymbolRef` value object (F001) is the single source
of truth for that mapping.

request-path safe: imports neither ``trade`` nor any broker SDK. akshare /
baostock are **lazy-imported** inside the fetch methods so the module loads
even where the heavy libs are absent (unit tests inject fakes; production
carries them via pyproject). Every external call is wrapped so a provider
failure degrades to the fallback / an honest ``SymbolNotFoundError`` rather
than a 500.

Full history (not a sample) is fetched per the §8 depth requirement — the
caller (service) passes the same ~13-month window it uses for US symbols, and
F005 verifies real ≥3–5y depth + akshare↔baostock cross-source agreement on
the VM.
"""

from __future__ import annotations

import importlib
from contextlib import suppress
from datetime import UTC, date, datetime, timedelta
from typing import Any

from workbench_api.data.snapshot_loader import PriceBar
from workbench_api.symbols.provider import (
    ProviderQuote,
    ProviderStats,
    SymbolDataProvider,
    SymbolNotFoundError,
)
from workbench_api.symbols.symbol_ref import SymbolRef

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

# A short recent window resolves the latest EOD close for a quote.
_QUOTE_WINDOW_DAYS = 10


def _to_ymd(day: date) -> str:
    return day.strftime("%Y%m%d")


def _to_iso(day: date) -> str:
    return day.strftime("%Y-%m-%d")


def _baostock_code(ref: SymbolRef) -> str:
    """canonical 600519.SH -> baostock sh.600519 (sz for .SZ)."""
    prefix = "sh" if ref.canonical.endswith(".SH") else "sz"
    return f"{prefix}.{ref.code}"


def _coerce_date(value: object) -> date | None:
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


def _coerce_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        result = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if result != result:  # NaN
        return None
    return result


def _resolve_columns(columns: list[str]) -> dict[str, str | None]:
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
    bar_date = _coerce_date(record.get(cols["date"]))
    open_ = _coerce_float(record.get(cols["open"]))
    high = _coerce_float(record.get(cols["high"]))
    low = _coerce_float(record.get(cols["low"]))
    close = _coerce_float(record.get(cols["close"]))
    volume = _coerce_float(record.get(cols["volume"]))
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


_REQUIRED_FIELDS = ("date", "open", "high", "low", "close", "volume")


def _bars_from_records(
    records: list[dict[str, Any]], columns: list[str], ticker: str
) -> list[PriceBar]:
    resolved = _resolve_columns(columns)
    cols: dict[str, str] = {
        field: name
        for field in _REQUIRED_FIELDS
        if (name := resolved[field]) is not None
    }
    if len(cols) != len(_REQUIRED_FIELDS):
        return []
    bars = [
        bar
        for record in records
        if (bar := _record_to_bar(record, cols, ticker)) is not None
    ]
    bars.sort(key=lambda b: b.bar_date)
    return bars


class CnSymbolProvider(SymbolDataProvider):
    """A-share EOD provider: akshare primary, baostock cross-check / fallback."""

    name = "akshare"

    def __init__(
        self,
        *,
        akshare_module: Any | None = None,
        baostock_module: Any | None = None,
    ) -> None:
        self._akshare = akshare_module
        self._baostock = baostock_module
        # The source that actually served the most recent fetch (akshare or
        # baostock) — the service records it for honest provenance.
        self.last_source: str = self.name

    # -- module loading (lazy; injectable for tests) --------------------- #

    def _load_akshare(self) -> Any | None:
        if self._akshare is not None:
            return self._akshare
        try:
            return importlib.import_module("akshare")
        except Exception:
            return None

    def _load_baostock(self) -> Any | None:
        if self._baostock is not None:
            return self._baostock
        try:
            return importlib.import_module("baostock")
        except Exception:
            return None

    # -- SymbolDataProvider surface -------------------------------------- #

    def get_price_history(
        self, symbol: str, from_date: date, to_date: date
    ) -> list[PriceBar]:
        ref = SymbolRef.parse(symbol)
        bars = self._fetch_akshare(ref, from_date, to_date)
        if bars:
            self.last_source = "akshare"
            return bars
        bars = self._fetch_baostock(ref, from_date, to_date)
        if bars:
            self.last_source = "baostock"
            return bars
        raise SymbolNotFoundError(symbol)

    def get_quote(self, symbol: str) -> ProviderQuote:
        today = datetime.now(UTC).date()
        bars = self.get_price_history(
            symbol, today - timedelta(days=_QUOTE_WINDOW_DAYS), today
        )
        if not bars:
            raise SymbolNotFoundError(symbol)
        latest = bars[-1]
        return ProviderQuote(
            symbol=symbol,
            as_of=latest.bar_date,
            close=latest.close,
            source=self.last_source,
        )

    def get_stats(self, symbol: str) -> ProviderStats:
        # P1 A-share scope is price/lookup only — CN fundamentals are out of
        # scope. Return minimal identity (CNY) so the US-gated fundamentals
        # surface degrades honestly to "non_us" rather than fabricating data.
        ref = SymbolRef.parse(symbol)
        return ProviderStats(
            symbol=symbol,
            source=self.name,
            currency=ref.currency,
            quote_type="EQUITY",
            country="China",
        )

    # -- per-source fetchers (never raise; empty list on any failure) ---- #

    def _fetch_akshare(
        self, ref: SymbolRef, from_date: date, to_date: date
    ) -> list[PriceBar]:
        akshare = self._load_akshare()
        if akshare is None:
            return []
        try:
            frame = akshare.stock_zh_a_hist(
                symbol=ref.code,
                period="daily",
                start_date=_to_ymd(from_date),
                end_date=_to_ymd(to_date),
                adjust="qfq",
            )
        except Exception:
            return []
        if frame is None:
            return []
        try:
            columns = [str(c) for c in frame.columns]
            records: list[dict[str, Any]] = frame.to_dict("records")
        except Exception:
            return []
        return _bars_from_records(records, columns, ref.canonical)

    def _fetch_baostock(
        self, ref: SymbolRef, from_date: date, to_date: date
    ) -> list[PriceBar]:
        baostock = self._load_baostock()
        if baostock is None:
            return []
        try:
            baostock.login()
        except Exception:
            return []
        try:
            result = baostock.query_history_k_data_plus(
                _baostock_code(ref),
                "date,open,high,low,close,volume",
                start_date=_to_iso(from_date),
                end_date=_to_iso(to_date),
                frequency="d",
                adjustflag="2",  # 2 = 前复权 (matches akshare qfq)
            )
            if getattr(result, "error_code", "0") != "0":
                return []
            columns = list(result.fields)
            records: list[dict[str, Any]] = []
            while result.next():
                records.append(dict(zip(columns, result.get_row_data(), strict=False)))
        except Exception:
            return []
        finally:
            with suppress(Exception):
                baostock.logout()
        return _bars_from_records(records, columns, ref.canonical)
