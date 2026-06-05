"""B037 F001 — assembles the ``GET /api/home`` payload.

The daily-engagement Home page needs three things, all read-only:

* **NAV** — reuses :func:`dashboard._aggregate_nav` (cash + equity).
* **Day P&L (mark-to-market)** — marks the latest ``AccountSnapshot``
  positions with the prices a :class:`PriceProvider` resolves (today's
  close vs the prior trading day's close) and sums ``shares * (latest -
  prior)``. Degrades to ``None`` when no position can be marked / there
  is no snapshot. **Read-only** — it never touches an execution surface.
* **Sleeve breakdown** — groups the same positions by their ``sleeve``
  tag (B037 added the tag to the positions JSON; legacy untagged
  holdings fall into ``unclassified``) and reports each sleeve's share of
  the marked NAV + its own Day P&L.

The price source is injected (``PriceProvider``) so tests assert an exact
Day P&L from known closes and the production wiring reads the
``price_snapshot`` table the daily timer fills — see
``services.prices_provider``.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from workbench_api.db.repositories.account_snapshot import AccountSnapshotRepository
from workbench_api.schemas.home import DayPnl, HomeResponse, SleeveBreakdown
from workbench_api.services.dashboard import _aggregate_nav
from workbench_api.services.prices_provider import (
    DbPriceProvider,
    PriceMark,
    PriceProvider,
)
from workbench_api.services.strategies import list_strategies
from workbench_api.settings import Settings

UNCLASSIFIED_SLEEVE = "unclassified"
"""Bucket for positions written before B037 added the ``sleeve`` tag
(or tagged with a sleeve outside the strategy registry)."""


@dataclass(frozen=True, slots=True)
class _Position:
    symbol: str
    shares: float
    sleeve: str


def _parse_positions(raw: object) -> list[_Position]:
    """Defensively parse the snapshot's positions JSON into typed rows.

    Malformed entries (non-dict, missing/garbage symbol or shares) are
    dropped — the same trust-nothing posture ``reconcile`` uses on the
    positions JSON. The optional ``sleeve`` tag defaults to
    ``unclassified`` so legacy snapshots still group cleanly.
    """

    positions: list[_Position] = []
    if not isinstance(raw, list):
        return positions
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        symbol = str(entry.get("symbol", "")).upper()
        if not symbol:
            continue
        try:
            shares = float(entry.get("shares", 0.0))
        except (TypeError, ValueError):
            continue
        sleeve_raw = entry.get("sleeve")
        sleeve = str(sleeve_raw) if sleeve_raw else UNCLASSIFIED_SLEEVE
        positions.append(_Position(symbol=symbol, shares=shares, sleeve=sleeve))
    return positions


def _registry_sleeves() -> list[str]:
    """Distinct sleeves from the strategy registry (stable order)."""

    return sorted({s.sleeve for s in list_strategies().strategies})


def _day_pnl(value: float, prior_value: float) -> DayPnl | None:
    """Build a DayPnl, or ``None`` when there is no prior mark to compare."""

    if prior_value <= 0:
        return None
    return DayPnl(value=round(value, 2), pct=round(value / prior_value, 6))


def build_home(
    session: Session,
    settings: Settings,
    provider: PriceProvider | None = None,
) -> HomeResponse:
    """Assemble the HomeResponse. Read-only; never writes or executes.

    ``provider`` defaults to the production :class:`DbPriceProvider`
    (reads ``price_snapshot``); tests inject a fake to pin the closes.
    """

    del settings  # reserved for future Home fields; NAV reads via _aggregate_nav
    if provider is None:
        provider = DbPriceProvider(session)

    nav = _aggregate_nav(session)

    snapshot = AccountSnapshotRepository(session).latest()
    positions = _parse_positions(snapshot.positions if snapshot else None)
    marks: dict[str, PriceMark] = (
        provider.get_marks([p.symbol for p in positions]) if positions else {}
    )

    # Accumulate marked latest/prior value + Day P&L per sleeve + overall.
    total_latest = 0.0
    total_prior = 0.0
    sleeve_latest: dict[str, float] = {}
    sleeve_prior: dict[str, float] = {}
    sleeve_count: dict[str, int] = {}
    for pos in positions:
        sleeve_count[pos.sleeve] = sleeve_count.get(pos.sleeve, 0) + 1
        mark = marks.get(pos.symbol)
        if mark is None:
            continue
        latest_value = pos.shares * mark.latest_close
        prior_value = pos.shares * mark.prior_close
        total_latest += latest_value
        total_prior += prior_value
        sleeve_latest[pos.sleeve] = sleeve_latest.get(pos.sleeve, 0.0) + latest_value
        sleeve_prior[pos.sleeve] = sleeve_prior.get(pos.sleeve, 0.0) + prior_value

    day_pnl = _day_pnl(total_latest - total_prior, total_prior)

    # List the registry sleeves (stable skeleton) plus any extra sleeve a
    # position is tagged with (e.g. unclassified) that the registry omits.
    sleeve_order = _registry_sleeves()
    extra = [s for s in sleeve_count if s not in sleeve_order]
    for s in sorted(extra):
        sleeve_order.append(s)

    sleeves: list[SleeveBreakdown] = []
    for sleeve in sleeve_order:
        latest = sleeve_latest.get(sleeve, 0.0)
        prior = sleeve_prior.get(sleeve, 0.0)
        count = sleeve_count.get(sleeve, 0)
        nav_share = (
            round(latest / total_latest, 6) if total_latest > 0 else None
        )
        sleeves.append(
            SleeveBreakdown(
                sleeve=sleeve,
                nav_share=nav_share,
                day_pnl=_day_pnl(latest - prior, prior),
                positions_summary=_positions_summary(count),
            )
        )

    return HomeResponse(nav=nav, day_pnl=day_pnl, sleeves=sleeves)


def _positions_summary(count: int) -> str:
    if count <= 0:
        return "—"
    if count == 1:
        return "1 position"
    return f"{count} positions"
