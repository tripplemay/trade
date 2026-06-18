"""B066 F001 — point-in-time A-share universe loader for the CN attack engine.

Reads the ``cn_pit_universe.csv`` produced by the B065 refresh
(:mod:`workbench_api.data_refresh.cn_universe`). That file holds **point-in-time
membership**: one block of rows per quarterly rebalance ``as_of_date``, each row a
``(ticker, rank, market_cap, avg_turnover, composite_score)`` ranked by trailing
size + liquidity using only data dated ``<= as_of`` (structurally leakage-free,
B065 F001 / B063 survivorship discipline).

This loader's job is the read side of that point-in-time contract: given an
arbitrary ``as_of`` (any trading day the engine evaluates), return the membership
from the **latest rebalance block dated on or before** ``as_of`` — never a future
block. So an engine evaluating 2024-05-15 sees the 2024-03-31 universe, not the
not-yet-known 2024-06-30 one. Before the first rebalance the universe is empty.

Layering (§12.10.2): pure stdlib CSV reading; imports neither akshare nor a
broker SDK. The A-share daily prices / CAS fundamentals the engine scores live in
the **same unified CSVs** as the US data (B062 prices + B065 fundamentals), so the
engine reuses :func:`trade.data.us_quality_universe.load_prices` /
``load_fundamentals`` directly — only the *membership* needs a CN-specific schema.
"""

from __future__ import annotations

import csv
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from trade.data.data_root import unified_cn_universe_path

_REPO_ROOT: Path = Path(__file__).resolve().parents[2]
# Local / CI default; the VM override (WORKBENCH_DATA_ROOT) is applied by
# ``unified_cn_universe_path`` so the loader reads exactly what the refresh wrote.
DEFAULT_CN_UNIVERSE_PATH: Path = (
    _REPO_ROOT / "data" / "snapshots" / "universe" / "cn_pit_universe.csv"
)

CN_UNIVERSE_REQUIRED_COLUMNS: tuple[str, ...] = (
    "as_of_date",
    "ticker",
    "rank",
    "market_cap",
    "avg_turnover",
    "composite_score",
)


class CnUniverseError(ValueError):
    """Raised when the CN universe CSV is missing or fails schema validation."""


@dataclass(frozen=True, slots=True)
class CnUniverseMember:
    """One point-in-time universe membership row for a rebalance date."""

    as_of: date
    ticker: str
    rank: int
    market_cap: float
    avg_turnover: float
    composite_score: float


def _parse_iso_date(value: str, field: str) -> date:
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").date()
    except ValueError as exc:
        raise CnUniverseError(f"{field} must be YYYY-MM-DD; got {value!r}") from exc


def _resolve_path(universe_path: Path | None) -> Path:
    if universe_path is not None:
        return universe_path
    return unified_cn_universe_path(DEFAULT_CN_UNIVERSE_PATH)


def _read_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise CnUniverseError(f"CN universe file missing: {path}")
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        missing = [c for c in CN_UNIVERSE_REQUIRED_COLUMNS if c not in fieldnames]
        if missing:
            raise CnUniverseError(
                f"{path.name} missing required columns: {missing}"
            )
        return list(reader)


def load_cn_universe_members(
    as_of: date,
    *,
    universe_path: Path | None = None,
) -> tuple[CnUniverseMember, ...]:
    """Members of the latest rebalance block dated ``<= as_of`` (point-in-time).

    Returns the rows from the single most-recent rebalance ``as_of_date`` that is
    on or before ``as_of``, ordered by ``rank``. Rebalance blocks dated strictly
    after ``as_of`` are never consulted (no look-ahead). Empty when no rebalance
    has happened on or before ``as_of`` (the universe does not exist yet).
    """

    rows = _read_rows(_resolve_path(universe_path))

    # Group rows by rebalance date, keeping only blocks visible at ``as_of``.
    visible_dates: set[date] = set()
    parsed: list[tuple[date, dict[str, str]]] = []
    for row in rows:
        rebalance_date = _parse_iso_date(row["as_of_date"], "as_of_date")
        if rebalance_date <= as_of:
            visible_dates.add(rebalance_date)
            parsed.append((rebalance_date, row))
    if not visible_dates:
        return ()

    latest = max(visible_dates)
    members = [
        CnUniverseMember(
            as_of=rebalance_date,
            ticker=str(row["ticker"]).strip(),
            rank=int(row["rank"]),
            market_cap=float(row["market_cap"]),
            avg_turnover=float(row["avg_turnover"]),
            composite_score=float(row["composite_score"]),
        )
        for rebalance_date, row in parsed
        if rebalance_date == latest
    ]
    members.sort(key=lambda member: (member.rank, member.ticker))
    return tuple(members)


def load_cn_universe(
    as_of: date,
    *,
    universe_path: Path | None = None,
) -> tuple[str, ...]:
    """Point-in-time member tickers at ``as_of``, ordered by rank (convenience).

    Thin wrapper over :func:`load_cn_universe_members` returning just the tickers
    — the engine's eligible-set. See that function for the point-in-time
    semantics.
    """

    return tuple(
        member.ticker
        for member in load_cn_universe_members(as_of, universe_path=universe_path)
    )


def load_cn_universe_history(
    *,
    universe_path: Path | None = None,
) -> dict[date, tuple[str, ...]]:
    """All rebalance blocks: ``{rebalance_date: tickers ordered by rank}``.

    Reads the CSV **once** for a backtest's whole window so the daily driver can
    resolve point-in-time membership in memory (via :func:`resolve_pit_members`)
    instead of re-reading the file every trading day.
    """

    rows = _read_rows(_resolve_path(universe_path))
    ranked: dict[date, list[tuple[int, str]]] = {}
    for row in rows:
        rebalance_date = _parse_iso_date(row["as_of_date"], "as_of_date")
        ranked.setdefault(rebalance_date, []).append(
            (int(row["rank"]), str(row["ticker"]).strip())
        )
    return {
        rebalance_date: tuple(ticker for _, ticker in sorted(members))
        for rebalance_date, members in ranked.items()
    }


def resolve_pit_members(
    history: Mapping[date, tuple[str, ...]], as_of: date
) -> tuple[str, ...]:
    """Members of the latest rebalance block dated ``<= as_of`` (point-in-time).

    The in-memory twin of :func:`load_cn_universe`'s membership rule, over a
    history loaded once by :func:`load_cn_universe_history`. Empty before the
    first rebalance on or before ``as_of`` (no look-ahead).
    """

    visible = [rebalance_date for rebalance_date in history if rebalance_date <= as_of]
    if not visible:
        return ()
    return history[max(visible)]


__all__ = [
    "CN_UNIVERSE_REQUIRED_COLUMNS",
    "CnUniverseError",
    "CnUniverseMember",
    "load_cn_universe",
    "load_cn_universe_history",
    "load_cn_universe_members",
    "resolve_pit_members",
]
