"""B048 F003 — mark-to-market NAV history reconstruction.

The safety / risk layer needs drawdown **over time**, not a single
point-in-time mark. This module rebuilds a NAV time series from the
``account_snapshot`` history: each historical snapshot (taken on date
``D``) is valued by marking every held position to the close
``price_history`` carries on-or-before ``D`` (B048 F001), reusing the
same valuation basis as the B046 ``mark_to_market`` helper.

Two series come out of one pass:

* **master** — ``cash + Σ (shares × close_on_or_before(symbol, D))`` per
  snapshot. The master drawdown is peak-to-latest on this series.
* **per-sleeve** — ``Σ (shares × close)`` grouped by each holding's
  ``sleeve`` tag (B048 F002). Cash is master-level and is intentionally
  excluded from sleeve values. Each sleeve's drawdown is peak-to-latest
  on its own series — this replaces the pre-F011 placeholder that
  mirrored the master drawdown onto every sleeve.

Degrade-don't-fabricate (v0.9.21): when a snapshot date predates the
price-history coverage for a symbol, ``close_on_or_before`` returns
``None``; we fall back to that holding's ``avg_cost`` for that point and
record the symbol in :attr:`NavHistory.degraded_symbols` so the caller
annotates the valuation rather than silently mixing bases unflagged.
When price history is absent entirely the whole series degrades to cost
basis — identical to the pre-F003 cost-based drawdown.

§12.10.2: read-only over the DB (``account_snapshot`` + ``price_history``);
imports no ``trade`` package, so it is safe on the request path.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from workbench_api.db.models.account_snapshot import AccountSnapshot
from workbench_api.db.repositories.price_history import PriceHistoryRepository

# The authoritative kill-switch threshold (B011 risk policy). B048 F003
# unifies the recommendations gate onto this value (was 0.20 there) so the
# kill-switch reads the same threshold everywhere.
KILL_SWITCH_THRESHOLD: float = 0.15

# Holdings written before B037 added the sleeve tag (or tagged outside the
# registry) group here — mirrors ``home.UNCLASSIFIED_SLEEVE``.
UNCLASSIFIED_SLEEVE: str = "unclassified"


@dataclass(frozen=True, slots=True)
class NavHistory:
    """A reconstructed mark-to-market NAV time series (master + per-sleeve)."""

    master_series: tuple[float, ...]
    per_sleeve_series: dict[str, tuple[float, ...]]
    degraded_symbols: tuple[str, ...]
    points: int

    @property
    def degraded(self) -> bool:
        return bool(self.degraded_symbols)


def drawdown(series: Sequence[float]) -> float:
    """Peak-to-latest drawdown as a positive fraction (0.07 = 7%).

    ``peak`` is the maximum of every point *before* the latest, so the
    result is "how far the latest value sits below its prior peak" — the
    current-drawdown semantics the kill switch acts on. Returns 0.0 with
    fewer than two points or a non-positive peak (no division by zero)."""

    if len(series) < 2:
        return 0.0
    peak = max(series[:-1])
    latest = series[-1]
    if peak <= 0:
        return 0.0
    return max(0.0, (peak - latest) / peak)


def reconstruct_nav_history(
    session: Session,
    *,
    repo: PriceHistoryRepository | None = None,
) -> NavHistory:
    """Rebuild the master + per-sleeve mark-to-market NAV series from the
    ``account_snapshot`` history (oldest first)."""

    repo = repo or PriceHistoryRepository(session)
    stmt = select(AccountSnapshot).order_by(AccountSnapshot.snapshot_at)
    snapshots = list(session.execute(stmt).scalars().all())

    master_series: list[float] = []
    snap_sleeve_maps: list[dict[str, float]] = []
    degraded: set[str] = set()

    for snap in snapshots:
        as_of = snap.snapshot_at.date()
        nav = float(snap.cash)
        sleeve_values: dict[str, float] = {}
        for entry in snap.positions or []:
            if not isinstance(entry, dict):
                continue
            symbol = str(entry.get("symbol", "")).upper()
            if not symbol:
                continue
            try:
                shares = float(entry.get("shares", 0.0))
                avg_cost = float(entry.get("avg_cost", 0.0))
            except (TypeError, ValueError):
                continue
            sleeve_raw = entry.get("sleeve")
            sleeve = str(sleeve_raw) if sleeve_raw else UNCLASSIFIED_SLEEVE
            close = repo.close_on_or_before(symbol, as_of)
            if close is None:
                # No price history at/before this date → degrade to cost
                # basis for this point and flag the symbol (don't fabricate).
                close = avg_cost
                degraded.add(symbol)
            value = shares * close
            nav += value
            sleeve_values[sleeve] = sleeve_values.get(sleeve, 0.0) + value
        master_series.append(nav)
        snap_sleeve_maps.append(sleeve_values)

    all_sleeves = sorted({s for m in snap_sleeve_maps for s in m})
    per_sleeve_series = {
        sleeve: tuple(m.get(sleeve, 0.0) for m in snap_sleeve_maps)
        for sleeve in all_sleeves
    }
    return NavHistory(
        master_series=tuple(master_series),
        per_sleeve_series=per_sleeve_series,
        degraded_symbols=tuple(sorted(degraded)),
        points=len(snapshots),
    )


def master_drawdown(nav: NavHistory) -> float:
    """Master drawdown = peak-to-latest on the mark-to-market NAV series."""

    return drawdown(nav.master_series)


def per_sleeve_drawdowns(nav: NavHistory) -> dict[str, float]:
    """Per-sleeve drawdown = peak-to-latest on each sleeve's NAV series."""

    return {
        sleeve: drawdown(series) for sleeve, series in nav.per_sleeve_series.items()
    }
