"""B074 F001 — sync A-share daily closes from the unified prices CSV into price_snapshot.

The daily ``workbench-prices`` timer fills ``price_snapshot`` via Tiingo over the
US/proxy target universe (B037 + B058 F002). A-shares are **not** Tiingo-reachable
and are **not** in ``data_refresh.price_universe()``, so the cn_attack paper books —
whose targets are A-share names (e.g. ``600519.SH``) — had NO mark in
``price_snapshot`` and could never build: the paper engine skipped every target for
want of a usable mark and the book stranded in cash (the §17.1 two-store split +
B058 F002 "target with no mark → paper stranded" family, this time for A-shares).

The A-share daily closes already exist on disk: the workbench data-refresh job
fetches them (akshare) and writes them into the unified prices CSV
(``<data_root>/snapshots/prices/unified/prices_daily.csv``) alongside the US rows.
This module reads that CSV (read-only — no akshare, no network) and persists the
recent A-share closes into ``price_snapshot`` (idempotent by ``(symbol, obs_date)``),
so the paper mark source covers the A-share targets from the SAME on-disk source the
cn_attack engine scores from (§17.1 single source). It deliberately does NOT extend
``price_universe()`` or add akshare to the Tiingo CLI: the Tiingo path stays US-only
(US-zero-regression) and this sync is a separate, additive CSV→DB step.

Boundary (r): read-only — composes ``CSV read → PriceSnapshotRepository``. It imports
no broker / order-ticket / execution surface and no akshare; A-share detection uses
``SymbolRef`` (``market == "CN"``). ``tests/safety/test_market_scheduler_scope.py``
greps the ``workbench_api.prices`` package to enforce that.
"""

from __future__ import annotations

import csv
import logging
import os
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from sqlalchemy.orm import Session

from workbench_api.db.repositories.price_snapshot import PriceSnapshotRepository
from workbench_api.symbols.provider import InvalidSymbolError
from workbench_api.symbols.symbol_ref import SymbolRef

logger = logging.getLogger(__name__)

# Provenance label distinguishing these rows from the Tiingo-sourced US closes in
# the same table. The immediate source is the unified CSV (the data-refresh job's
# akshare output), NOT a live fetch — honouring the "no new fetch" boundary.
CN_SNAPSHOT_SOURCE: str = "unified_csv"

# Default VM data root (mirrors price_history/cli.py + data_refresh/cli.py). The
# workbench-prices unit also sets WORKBENCH_DATA_ROOT explicitly (B074); the default
# matches where the data-refresh job writes, so a missing env var still resolves.
DEFAULT_DATA_ROOT: str = "/var/lib/workbench/data"
# Relative path of the unified prices CSV beneath a data root. Mirrors the writer
# (``data_refresh.refresh.PRICES_RELPATH``) + ``trade.data.data_root``; duplicated
# here (with this drift note) to keep the prices package's import surface minimal.
_PRICES_RELPATH: tuple[str, ...] = ("snapshots", "prices", "unified", "prices_daily.csv")

# Two closes make a symbol markable for the paper engine (latest + prior trading
# day); the daily-refreshed CSV's two most recent rows per A-share are exactly that.
DEFAULT_RECENT: int = 2


def default_prices_path() -> Path:
    """The unified prices CSV path from ``WORKBENCH_DATA_ROOT`` (else the VM default)."""

    root = os.environ.get("WORKBENCH_DATA_ROOT", "").strip() or DEFAULT_DATA_ROOT
    return Path(root).joinpath(*_PRICES_RELPATH)


def is_a_share(ticker: str) -> bool:
    """True for a mainland A-share canonical ticker (``.SH`` / ``.SZ`` → CNY).

    Uses :class:`SymbolRef` (``market == "CN"``); a bare US ticker, an HK ``.HK``
    name, or the ``CASH`` pseudo-symbol all return False, and unparseable input is
    not an A-share."""

    try:
        return SymbolRef.parse(ticker).market == "CN"
    except InvalidSymbolError:
        return False


@dataclass(frozen=True, slots=True)
class CnSnapshotSyncSummary:
    """Aggregate result of one A-share CSV→price_snapshot sync."""

    symbols: int  # distinct A-share symbols seen in the CSV
    saved: int  # new (symbol, obs_date) closes inserted
    rows_seen: int  # A-share (symbol, date) observations persisted (post-dedup)
    # A-share symbols written/seen — the caller checks which are still unmarkable
    # with the SAME ``_is_markable`` rule it applies to the US universe (loud gap).
    touched: tuple[str, ...]


def read_recent_cn_closes(
    prices_path: Path, *, recent: int = DEFAULT_RECENT
) -> dict[str, list[tuple[date, float]]]:
    """``{symbol: [(obs_date, close), ...]}`` for the ``recent`` newest dates per A-share.

    Reads the unified prices CSV (header ``date,ticker,...,close,...``; extra columns
    such as a trailing ``tradestatus`` are tolerated by ``DictReader``). Keeps only
    ``.SH`` / ``.SZ`` rows, parses ``date`` + ``close``, and returns the ``recent``
    most recent observations per symbol (newest first). A missing file → ``{}`` (local
    / CI, where the VM unified CSV does not exist — a graceful no-op). Malformed rows
    are skipped."""

    if not prices_path.is_file():
        return {}
    by_symbol: dict[str, list[tuple[date, float]]] = defaultdict(list)
    with prices_path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            ticker = (row.get("ticker") or "").strip()
            if not ticker or not is_a_share(ticker):
                continue
            try:
                obs_date = date.fromisoformat(row["date"].strip())
                close = float(row["close"])
            except (KeyError, ValueError, TypeError, AttributeError):
                continue
            by_symbol[ticker].append((obs_date, close))

    out: dict[str, list[tuple[date, float]]] = {}
    for symbol, observations in by_symbol.items():
        # Newest first, de-duplicating repeated dates (keep the first/newest seen),
        # then take the ``recent`` most recent — the minimal set that marks a symbol.
        observations.sort(key=lambda item: item[0], reverse=True)
        seen: set[date] = set()
        deduped: list[tuple[date, float]] = []
        for obs_date, close in observations:
            if obs_date in seen:
                continue
            seen.add(obs_date)
            deduped.append((obs_date, close))
        out[symbol] = deduped[: max(1, recent)]
    return out


def sync_cn_closes_from_csv(
    session: Session,
    *,
    prices_path: Path,
    recent: int = DEFAULT_RECENT,
    source: str = CN_SNAPSHOT_SOURCE,
) -> CnSnapshotSyncSummary:
    """Persist the recent A-share closes from the unified CSV into ``price_snapshot``.

    Idempotent (``save_if_new`` skips an existing ``(symbol, obs_date)``) and commits
    per symbol so one symbol's failure can't roll back earlier symbols' closes (mirrors
    the Tiingo CLI). Returns counts + the A-share symbols touched, so the caller surfaces
    a coverage gap with the SAME markable rule it uses for the US universe."""

    closes_by_symbol = read_recent_cn_closes(prices_path, recent=recent)
    repo = PriceSnapshotRepository(session)
    saved = 0
    rows_seen = 0
    for symbol in sorted(closes_by_symbol):
        for obs_date, close in closes_by_symbol[symbol]:
            rows_seen += 1
            row = repo.save_if_new(
                symbol=symbol, obs_date=obs_date, close=close, source=source
            )
            if row is not None:
                saved += 1
        # Commit per symbol so a later symbol's failure cannot discard earlier writes.
        session.commit()

    summary = CnSnapshotSyncSummary(
        symbols=len(closes_by_symbol),
        saved=saved,
        rows_seen=rows_seen,
        touched=tuple(sorted(closes_by_symbol)),
    )
    logger.info(
        "cn_snapshot_sync_done",
        extra={
            "prices_path": str(prices_path),
            "symbols": summary.symbols,
            "saved": summary.saved,
        },
    )
    return summary
