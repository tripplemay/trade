"""B066 F003 — CSI 300 (沪深300) benchmark refresh into the pipeline.

Fetches the CSI 300 index daily close via akshare's **sina** endpoint
``stock_zh_index_daily(symbol="sh000300")`` and writes a compact benchmark CSV
(``snapshots/benchmark/cn_csi300.csv``; columns ``date,close``) that the ``trade``
CN attack comparison report reads offline (:mod:`trade.data.cn_benchmark`) as the
``vs 沪深300`` benchmark.

§23 reachability: the **sina** index host is used (not the eastmoney push host),
matching the B062/B065 lesson that eastmoney push2his ConnectionErrors from the
prod VM while sina is reachable. akshare lives only here in the workbench job
(``trade`` never imports it). A fetch failure is logged + best-effort: the
benchmark CSV is simply not written, and the report degrades to "benchmark
unavailable" rather than failing the whole refresh.
"""

from __future__ import annotations

import csv
import importlib
import logging
from collections.abc import Sequence
from datetime import date
from pathlib import Path
from typing import Any, Protocol

logger = logging.getLogger(__name__)

# Mirrors trade.data.data_root.UNIFIED_CN_BENCHMARK_RELPATH (drift = trade reads a
# file this job never wrote). The writer joins it under the data root.
CN_BENCHMARK_RELPATH = ("snapshots", "benchmark", "cn_csi300.csv")
CN_BENCHMARK_HEADER = ["date", "close"]

# CSI 300 on sina: 上证-listed index → "sh000300".
CSI300_SINA_SYMBOL = "sh000300"


class IndexDailyLoader(Protocol):
    """Injected index-daily source (akshare-backed; faked in tests)."""

    def fetch_index_close(self, symbol: str) -> list[tuple[date, float]]: ...


class AkshareCsiLoader:
    """``IndexDailyLoader`` via akshare sina ``stock_zh_index_daily`` (lazy import)."""

    def __init__(self, akshare_module: Any | None = None) -> None:
        self._akshare = akshare_module

    def _load_akshare(self) -> Any | None:
        if self._akshare is not None:
            return self._akshare
        try:
            return importlib.import_module("akshare")
        except Exception:
            return None

    def fetch_index_close(self, symbol: str) -> list[tuple[date, float]]:
        akshare = self._load_akshare()
        if akshare is None:
            return []
        fetch = getattr(akshare, "stock_zh_index_daily", None)
        if fetch is None:
            return []
        try:
            frame = fetch(symbol=symbol)
        except Exception:
            return []
        if frame is None:
            return []
        try:
            records: list[dict[str, Any]] = frame.to_dict("records")
        except Exception:
            return []
        return parse_index_close(records)


def parse_index_close(records: Sequence[dict[str, Any]]) -> list[tuple[date, float]]:
    """``(date, close)`` pairs from sina index rows (columns ``date`` + ``close``).

    Malformed rows are skipped; the result is sorted ascending by date. Pure (no
    akshare) so it is unit-tested with plain dict rows."""

    out: list[tuple[date, float]] = []
    for record in records:
        parsed = _coerce_date(record.get("date"))
        if parsed is None:
            continue
        raw_close = record.get("close")
        if raw_close is None:
            continue
        try:
            close = float(raw_close)
        except (TypeError, ValueError):
            continue
        if close <= 0 or close != close:  # non-positive or NaN
            continue
        out.append((parsed, close))
    out.sort(key=lambda pair: pair[0])
    return out


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


def run_cn_benchmark_refresh(
    *,
    data_root: Path,
    loader: IndexDailyLoader,
    symbol: str = CSI300_SINA_SYMBOL,
) -> int:
    """Fetch the CSI 300 daily close and write ``cn_csi300.csv`` under ``data_root``.

    Best-effort: a fetch failure (logged) leaves the file unwritten (the report
    degrades). Returns the number of rows written (0 on failure)."""

    try:
        pairs = loader.fetch_index_close(symbol)
    except Exception:  # noqa: BLE001 — best-effort; never abort the refresh
        logger.exception("cn_benchmark_fetch_failure", extra={"symbol": symbol})
        return 0
    if not pairs:
        logger.warning("cn_benchmark_no_rows", extra={"symbol": symbol})
        return 0

    # The WRITE is best-effort too (mirrors _build_cn_universe): an OSError here
    # (disk full / read-only FS) must not abort the wider refresh — the benchmark
    # is optional (the report degrades) and downstream steps (CN universe build,
    # data-window DB persist) must still run.
    path = data_root.joinpath(*CN_BENCHMARK_RELPATH)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(CN_BENCHMARK_HEADER)
            writer.writerows([day.isoformat(), close] for day, close in pairs)
    except OSError:
        logger.exception("cn_benchmark_write_failure", extra={"path": str(path)})
        return 0
    logger.info(
        "cn_benchmark_refresh_done",
        extra={"rows": len(pairs), "symbol": symbol, "path": str(path)},
    )
    return len(pairs)


__all__ = [
    "CSI300_SINA_SYMBOL",
    "AkshareCsiLoader",
    "IndexDailyLoader",
    "parse_index_close",
    "run_cn_benchmark_refresh",
]
