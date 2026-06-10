"""B037 F001 — schemas for ``GET /api/home``.

The daily-engagement Home page (B037) reads one payload:

* ``nav`` — net asset value (B051: latest ``account_snapshot`` cash +
  mark-to-market positions), reusing ``services.nav.aggregate_nav``.
* ``day_pnl`` — read-only mark-to-market Day P&L of the latest account
  positions (today's close vs the prior trading day's close), or
  ``null`` when no position can be marked / there is no snapshot — the
  UI renders "—" for the null case.
* ``sleeves`` — per-sleeve breakdown grouped by each position's ``sleeve``
  tag (``regime`` / ``risk_parity`` / ``satellite_us_quality`` +
  ``unclassified`` for legacy untagged holdings).

AI Advisor (B039) and market context (B038) are *not* part of this
payload — those Home sections render their own placeholders this batch.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class DayPnl(BaseModel):
    """Mark-to-market Day P&L. ``value`` is absolute (base currency);
    ``pct`` is the fraction vs the prior trading day's mark."""

    value: float
    pct: float


class SleeveBreakdown(BaseModel):
    sleeve: str
    nav_share: float | None = Field(
        default=None,
        description="Fraction of total marked value held in this sleeve, "
        "or null when nothing in the sleeve can be marked.",
    )
    day_pnl: DayPnl | None = Field(
        default=None,
        description="Per-sleeve mark-to-market Day P&L, or null when no "
        "position in the sleeve has both closes.",
    )
    positions_summary: str = Field(
        description="Short human summary, e.g. '3 positions' or '—'.",
    )


class HomeResponse(BaseModel):
    """GET /api/home payload — NAV + Day P&L + sleeve breakdown."""

    nav: float
    day_pnl: DayPnl | None = None
    sleeves: list[SleeveBreakdown] = Field(default_factory=list)
