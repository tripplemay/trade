"""B066 F003 — CSI 300 (沪深300) benchmark loader for the CN attack report.

Reads the ``cn_csi300.csv`` the refresh writes (akshare sina
``stock_zh_index_daily`` for ``sh000300``; header ``date,close``). The CN attack
comparison report (F003) uses it as the ``vs 沪深300`` benchmark. **Graceful
degradation**: an absent / empty file returns an empty series so the report shows
an honest "benchmark unavailable" rather than failing the whole backtest — the
6-variant comparison still stands on its own.

Pure stdlib + pandas; no akshare / broker import (``trade`` stays offline). The
index lives in its own CSV, deliberately NOT in the equity-prices file, so it can
never leak into the strategy's universe / factor cross-section.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from trade.data.data_root import unified_cn_benchmark_path

_REPO_ROOT: Path = Path(__file__).resolve().parents[2]
DEFAULT_CN_BENCHMARK_PATH: Path = (
    _REPO_ROOT / "data" / "snapshots" / "benchmark" / "cn_csi300.csv"
)

CN_BENCHMARK_REQUIRED_COLUMNS: tuple[str, ...] = ("date", "close")


def load_cn_benchmark(
    start: date | None = None,
    end: date | None = None,
    *,
    benchmark_path: Path | None = None,
) -> pd.Series:
    """CSI 300 daily close as a date-indexed ``pd.Series``, filtered to the window.

    Returns an **empty** series when the file is absent or malformed (honest
    degradation — the caller renders a "benchmark unavailable" note), never raises
    on a missing benchmark.
    """

    path = benchmark_path if benchmark_path is not None else _resolve_path()
    if not path.is_file():
        return pd.Series(dtype=float)
    frame = pd.read_csv(path)
    if any(column not in frame.columns for column in CN_BENCHMARK_REQUIRED_COLUMNS):
        return pd.Series(dtype=float)
    frame = frame[["date", "close"]].copy()
    # Coerce BOTH columns defensively (the loader's contract is "never raise on a
    # malformed file"): a non-numeric close must drop the row, not raise.
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
    frame = frame.dropna(subset=["date", "close"])
    if start is not None:
        frame = frame[frame["date"] >= pd.Timestamp(start)]
    if end is not None:
        frame = frame[frame["date"] <= pd.Timestamp(end)]
    series = frame.set_index("date")["close"].astype(float).sort_index()
    return series[series > 0]


def _resolve_path() -> Path:
    return unified_cn_benchmark_path(DEFAULT_CN_BENCHMARK_PATH)


__all__ = [
    "CN_BENCHMARK_REQUIRED_COLUMNS",
    "load_cn_benchmark",
]
