"""B082 F001 (part 2) — 红利低波 (dividend low-volatility) defensive-sleeve data.

Fetches the five series the B082 defensive sleeve needs (探针 GO, part 1 — see
``docs/test-reports/B082-F001-data-reality.md``) and writes one compact CSV per
series under ``<data_root>/snapshots/dividend_lowvol/`` (akshare 1.18.64, §23 host):

- ``etf_512890.csv``   ← ``fund_etf_hist_sina("sh512890")`` (sina)
  → ``date,open,high,low,close,volume``
- ``index_h30269.csv`` ← ``stock_zh_index_hist_csindex("H30269")`` (价格指数 / PR)
  → ``date,close``
- ``index_h20269.csv`` ← ``stock_zh_index_hist_csindex("H20269")`` (全收益指数 / TR)
  → ``date,close``
- ``cn_10y_yield.csv`` ← ``bond_zh_us_rate("20050101")`` (chinabond, 中国国债收益率10年)
  → ``date,yield``
- ``gxl_sh.csv``       ← ``stock_a_gxl_lg("上证A股")`` (legulegu, secondary)
  → ``date,dividend_yield``

Reality vs. the part-1 hand-off note: ``fund_etf_hist_sina`` returns **no**
``amount`` column (only ``date/open/high/low/close/volume`` — verified against the
installed akshare 1.18.64 source), so the ETF CSV drops ``amount`` rather than
emit a permanently-blank column. The sina ETF bars are UNADJUSTED (no dividend),
which is why F002 uses the H20269 TR index as the primary return口径 and the ETF
only as the implementability / cost layer.

§23 reachability + §12.10.2 boundary: every host here is a VM-reachable one
(sina / csindex / chinabond-via-eastmoney / legulegu), akshare lives only in this
workbench job (``trade`` never imports it — it reads the CSVs offline), and each
per-series fetch is bounded by ``call_with_timeout`` (B078 §38/39, 杜绝挂死) and
best-effort: one series failing (unreachable host / hang / write error) is logged,
counted, and skipped — it never aborts the wider daily refresh (不炸整轮).
"""

from __future__ import annotations

import csv
import importlib
import logging
import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Protocol

from workbench_api.data_refresh.call_timeout import call_with_timeout

logger = logging.getLogger(__name__)

# Written under the data root; ``trade`` reads these offline (never imports akshare).
DIVIDEND_LOWVOL_SUBDIR = ("snapshots", "dividend_lowvol")

ETF_HEADER = ["date", "open", "high", "low", "close", "volume"]
INDEX_HEADER = ["date", "close"]
YIELD_HEADER = ["date", "yield"]
DIVIDEND_YIELD_HEADER = ["date", "dividend_yield"]

# --- series parameters (焊死, spec §0 + part-1 探针 报告 §1) ---------------- #
ETF_SINA_SYMBOL = "sh512890"  # 华泰柏瑞中证红利低波动 ETF, sina host
INDEX_PRICE_CODE = "H30269"  # 中证红利低波动 价格指数 (PR)
INDEX_TOTALRETURN_CODE = "H20269"  # 中证红利低波动 全收益指数 (TR) — F002 primary
INDEX_START_DATE = "20050101"  # 21.5y depth (报告 §1)
BOND_START_DATE = "20050101"
BOND_10Y_COLUMN = "中国国债收益率10年"  # bond_zh_us_rate 列名 (报告 §1 / probe)
GXL_SYMBOL = "上证A股"  # legulegu 市场级股息率 (secondary / robustness)

# csindex / bond / gxl frames use Chinese column headers.
_CSINDEX_DATE_KEY = "日期"
_CSINDEX_CLOSE_KEY = "收盘"
_GXL_DATE_KEY = "日期"
_GXL_VALUE_KEY = "股息率"


class DividendLowvolLoader(Protocol):
    """Injected akshare-backed source (faked in tests). Each method returns
    already-parsed, CSV-ready rows (``list[list[str]]``) and never raises for a
    plain fetch failure — it degrades to ``[]`` so the caller counts + skips."""

    def fetch_etf_bars(self, symbol: str) -> list[list[str]]: ...

    def fetch_index_close(
        self, symbol: str, start_date: str, end_date: str
    ) -> list[list[str]]: ...

    def fetch_bond_yield(self, start_date: str, column: str) -> list[list[str]]: ...

    def fetch_market_dividend_yield(self, symbol: str) -> list[list[str]]: ...


class AkshareDividendLowvolLoader:
    """:class:`DividendLowvolLoader` over akshare (lazy import; injectable in tests)."""

    def __init__(self, akshare_module: Any | None = None) -> None:
        self._akshare = akshare_module

    def _load_akshare(self) -> Any | None:
        if self._akshare is not None:
            return self._akshare
        try:
            return importlib.import_module("akshare")
        except Exception:
            return None

    @staticmethod
    def _records(frame: Any) -> list[dict[str, Any]]:
        if frame is None:
            return []
        try:
            return list(frame.to_dict("records"))
        except Exception:
            return []

    def fetch_etf_bars(self, symbol: str) -> list[list[str]]:
        akshare = self._load_akshare()
        if akshare is None:
            return []
        fetch = getattr(akshare, "fund_etf_hist_sina", None)
        if fetch is None:
            return []
        try:
            frame = fetch(symbol=symbol)
        except Exception:
            return []
        return parse_etf_bars(self._records(frame))

    def fetch_index_close(
        self, symbol: str, start_date: str, end_date: str
    ) -> list[list[str]]:
        akshare = self._load_akshare()
        if akshare is None:
            return []
        fetch = getattr(akshare, "stock_zh_index_hist_csindex", None)
        if fetch is None:
            return []
        try:
            frame = fetch(symbol=symbol, start_date=start_date, end_date=end_date)
        except Exception:
            return []
        return parse_date_value(
            self._records(frame),
            date_key=_CSINDEX_DATE_KEY,
            value_key=_CSINDEX_CLOSE_KEY,
        )

    def fetch_bond_yield(self, start_date: str, column: str) -> list[list[str]]:
        akshare = self._load_akshare()
        if akshare is None:
            return []
        fetch = getattr(akshare, "bond_zh_us_rate", None)
        if fetch is None:
            return []
        try:
            frame = fetch(start_date=start_date)
        except Exception:
            return []
        return parse_date_value(
            self._records(frame), date_key="日期", value_key=column
        )

    def fetch_market_dividend_yield(self, symbol: str) -> list[list[str]]:
        akshare = self._load_akshare()
        if akshare is None:
            return []
        fetch = getattr(akshare, "stock_a_gxl_lg", None)
        if fetch is None:
            return []
        try:
            frame = fetch(symbol=symbol)
        except Exception:
            return []
        return parse_date_value(
            self._records(frame),
            date_key=_GXL_DATE_KEY,
            value_key=_GXL_VALUE_KEY,
        )


# --------------------------------------------------------------------------- #
# pure parsers (no akshare — unit-tested with plain dict rows)
# --------------------------------------------------------------------------- #


def parse_etf_bars(records: Sequence[Mapping[str, Any]]) -> list[list[str]]:
    """``[date, open, high, low, close, volume]`` string rows from sina ETF bars.

    A row is kept only when it has a valid date AND a positive finite close (the
    tradeable price); ``open/high/low/volume`` are optional (blank when
    missing/NaN). Malformed rows are skipped; the result is sorted ascending by
    date."""

    out: list[list[str]] = []
    for record in records:
        parsed = _coerce_date(record.get("date"))
        if parsed is None:
            continue
        close = _coerce_float(record.get("close"))
        if close is None or close <= 0:
            continue
        row = [parsed.isoformat()]
        for column in ("open", "high", "low", "close"):
            row.append(_fmt(_coerce_float(record.get(column))))
        row.append(_fmt(_coerce_float(record.get("volume"))))
        out.append(row)
    out.sort(key=lambda item: item[0])
    return out


def parse_date_value(
    records: Sequence[Mapping[str, Any]], *, date_key: str, value_key: str
) -> list[list[str]]:
    """``[date, value]`` string rows for a positive ``(date, value)`` series.

    Used for the index closes (PR / TR), the 10Y treasury yield and the market
    dividend yield — all strictly-positive series, so a row is kept only when the
    date parses and the value is positive + finite. Sorted ascending by date."""

    out: list[list[str]] = []
    for record in records:
        parsed = _coerce_date(record.get(date_key))
        if parsed is None:
            continue
        value = _coerce_float(record.get(value_key))
        if value is None or value <= 0:
            continue
        out.append([parsed.isoformat(), _fmt(value)])
    out.sort(key=lambda item: item[0])
    return out


def _fmt(value: float | None) -> str:
    return "" if value is None else repr(value)


def _coerce_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _coerce_date(value: object) -> date | None:
    if hasattr(value, "isoformat") and not isinstance(value, str):
        try:
            return date.fromisoformat(str(value.isoformat())[:10])
        except ValueError:
            return None
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


# --------------------------------------------------------------------------- #
# orchestrator
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class DividendLowvolRefreshSummary:
    """Per-series rows written + the count of series that produced no CSV."""

    rows_by_series: Mapping[str, int]
    errors: int


def run_dividend_lowvol_refresh(
    *,
    data_root: Path,
    loader: DividendLowvolLoader,
    fetch_timeout_seconds: float | None = None,
    today: date | None = None,
) -> DividendLowvolRefreshSummary:
    """Fetch the five 红利低波 series and write one CSV each under ``data_root``.

    Best-effort per series: every network fetch is bounded by
    ``fetch_timeout_seconds`` (0 / None = inline) and any failure — an unreachable
    host, a hang (:class:`FetchTimeoutError`), an empty result or a write error —
    is logged, counted in ``errors`` and skipped, never aborting the others
    (不炸整轮). ``today`` pins the csindex ``end_date`` window (the cli passes the
    refresh run date); omitted → now (UTC), so no ``date.today()`` TZ trap."""

    run_date = today or datetime.now(UTC).date()
    timeout = fetch_timeout_seconds or 0.0
    end_date = run_date.strftime("%Y%m%d")

    series: list[tuple[str, list[str], Callable[[], list[list[str]]]]] = [
        ("etf_512890", ETF_HEADER, lambda: loader.fetch_etf_bars(ETF_SINA_SYMBOL)),
        (
            "index_h30269",
            INDEX_HEADER,
            lambda: loader.fetch_index_close(
                INDEX_PRICE_CODE, INDEX_START_DATE, end_date
            ),
        ),
        (
            "index_h20269",
            INDEX_HEADER,
            lambda: loader.fetch_index_close(
                INDEX_TOTALRETURN_CODE, INDEX_START_DATE, end_date
            ),
        ),
        (
            "cn_10y_yield",
            YIELD_HEADER,
            lambda: loader.fetch_bond_yield(BOND_START_DATE, BOND_10Y_COLUMN),
        ),
        (
            "gxl_sh",
            DIVIDEND_YIELD_HEADER,
            lambda: loader.fetch_market_dividend_yield(GXL_SYMBOL),
        ),
    ]

    rows_by_series: dict[str, int] = {}
    errors = 0
    for name, header, fetch in series:
        written = _refresh_one_series(
            data_root=data_root,
            name=name,
            header=header,
            timeout=timeout,
            fetch=fetch,
        )
        rows_by_series[name] = written
        if written == 0:
            errors += 1

    logger.info(
        "dividend_lowvol_refresh_done",
        extra={"rows_by_series": dict(rows_by_series), "errors": errors},
    )
    return DividendLowvolRefreshSummary(rows_by_series=rows_by_series, errors=errors)


def _refresh_one_series(
    *,
    data_root: Path,
    name: str,
    header: list[str],
    timeout: float,
    fetch: Callable[[], list[list[str]]],
) -> int:
    """Fetch one series (timeout-bounded) and write its CSV. Returns rows written;
    0 on any best-effort failure (fetch error / hang / empty / write error)."""

    try:
        rows = call_with_timeout(timeout, fetch)
    except Exception:  # noqa: BLE001 — best-effort (incl. FetchTimeoutError)
        logger.exception("dividend_lowvol_fetch_failure", extra={"series": name})
        return 0
    if not rows:
        logger.warning("dividend_lowvol_no_rows", extra={"series": name})
        return 0

    path = data_root.joinpath(*DIVIDEND_LOWVOL_SUBDIR, f"{name}.csv")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(header)
            writer.writerows(rows)
    except OSError:
        logger.exception(
            "dividend_lowvol_write_failure", extra={"series": name, "path": str(path)}
        )
        return 0
    logger.info(
        "dividend_lowvol_series_done",
        extra={"series": name, "rows": len(rows), "path": str(path)},
    )
    return len(rows)


__all__ = [
    "AkshareDividendLowvolLoader",
    "DividendLowvolLoader",
    "DividendLowvolRefreshSummary",
    "ETF_SINA_SYMBOL",
    "parse_date_value",
    "parse_etf_bars",
    "run_dividend_lowvol_refresh",
]
