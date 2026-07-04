"""B080 F003 — data-append: incremental baostock fetch → a fresh reverify snapshot.

Produces a **new** survivorship-free snapshot under ``data/research/reverify/<date>/``
(the frozen B070 universe copied verbatim + freshly-fetched prices) so the frozen
kernel re-validates on appended data without ever touching the original
``data/research/b070/`` snapshot. baostock is only reachable from the VM, so this
module is L2-verified (Codex runs it on the real VM); locally + in CI it is import-
safe (baostock is imported lazily inside :func:`append_reverify_snapshot`). Each
per-symbol fetch is wrapped in ``call_with_timeout`` and a ≤20 % failure floor
guards a systematically broken run — mirroring the data-refresh discipline.
"""

from __future__ import annotations

import csv
import logging
import shutil
from datetime import date
from pathlib import Path

from workbench_api.data_refresh.call_timeout import FetchTimeoutError, call_with_timeout

logger = logging.getLogger(__name__)

# Frozen B070 snapshot relpaths (source of the universe; target of the fresh prices).
_UNIVERSE_RELPATH = ("snapshots", "universe", "cn_pit_universe.csv")
_CONTROL_RELPATH = ("snapshots", "universe", "cn_pit_universe_current_control.csv")
_PRICES_RELPATH = ("snapshots", "prices", "unified", "prices_daily.csv")
_PRICES_HEADER = (
    "date", "ticker", "open", "high", "low", "close", "adj_close", "volume", "tradestatus"
)
_K_FIELDS = "date,open,high,low,close,volume,tradestatus"
_FROZEN_START = "2019-04-01"
_MAX_FAILURE_RATE = 0.2
_PER_SYMBOL_TIMEOUT = 60.0


def _to_baostock(canonical: str) -> str:
    """``600519.SH`` → ``sh.600519`` (baostock's code format)."""

    code, _, suffix = canonical.partition(".")
    return f"{suffix.lower()}.{code}"


def _union_tickers(universe_csv: Path) -> list[str]:
    if not universe_csv.is_file():
        raise FileNotFoundError(f"universe CSV not found: {universe_csv}")
    with universe_csv.open(encoding="utf-8", newline="") as handle:
        return sorted({row["ticker"].strip() for row in csv.DictReader(handle)})


def append_reverify_snapshot(
    *,
    b070_root: Path,
    reverify_root: Path,
    end: date,
    start: str = _FROZEN_START,
) -> dict[str, object]:
    """Build the reverify snapshot at ``reverify_root``; return a fetch summary.

    Copies the frozen universe CSVs from ``b070_root`` and re-fetches prices for
    their union of tickers over ``[start, end]`` via one baostock session. Raises
    ``RuntimeError`` if the per-symbol failure rate exceeds 20 % (a systematically
    broken fetch must not silently produce a thin snapshot the kernel then trusts).
    """

    b070_root, reverify_root = Path(b070_root), Path(reverify_root)
    # Copy the frozen universe verbatim (universe is frozen too — only prices append).
    for relpath in (_UNIVERSE_RELPATH, _CONTROL_RELPATH):
        src, dst = b070_root.joinpath(*relpath), reverify_root.joinpath(*relpath)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)

    tickers = _union_tickers(reverify_root.joinpath(*_UNIVERSE_RELPATH))
    prices_path = reverify_root.joinpath(*_PRICES_RELPATH)
    prices_path.parent.mkdir(parents=True, exist_ok=True)

    import baostock as bs  # lazy: VM-only dependency

    login = bs.login()
    logger.info("baostock login %s — appending %d names", login.error_code, len(tickers))
    priced = 0
    failed: list[str] = []
    total_rows = 0
    try:
        with prices_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(_PRICES_HEADER)
            for canonical in tickers:
                try:
                    rows = call_with_timeout(
                        _PER_SYMBOL_TIMEOUT, _fetch_one, bs, canonical, start, end.isoformat()
                    )
                except FetchTimeoutError:
                    failed.append(canonical)
                    continue
                if not rows:
                    failed.append(canonical)
                    continue
                priced += 1
                for r in rows:
                    d, o, h, lo, c, vol, ts = r
                    writer.writerow((d, canonical, o, h, lo, c, c, vol, ts))
                    total_rows += 1
    finally:
        bs.logout()

    failure_rate = len(failed) / len(tickers) if tickers else 1.0
    if failure_rate > _MAX_FAILURE_RATE:
        raise RuntimeError(
            f"reverify data-append failure rate {failure_rate:.0%} > "
            f"{_MAX_FAILURE_RATE:.0%} ({len(failed)}/{len(tickers)} names failed)"
        )
    return {
        "reverify_root": str(reverify_root),
        "tickers": len(tickers),
        "priced": priced,
        "failed": len(failed),
        "rows": total_rows,
        "failure_rate": round(failure_rate, 3),
    }


def _fetch_one(bs: object, canonical: str, start: str, end: str) -> list[list[str]]:
    rs = bs.query_history_k_data_plus(  # type: ignore[attr-defined]
        _to_baostock(canonical),
        _K_FIELDS,
        start_date=start,
        end_date=end,
        frequency="d",
        adjustflag="2",
    )
    rows: list[list[str]] = []
    while getattr(rs, "error_code", "0") == "0" and rs.next():
        rows.append(rs.get_row_data())
    return rows
