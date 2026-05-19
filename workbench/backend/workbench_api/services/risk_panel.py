"""Risk-panel service (B023 F006).

The workbench is research-only. The risk panel is informational — it
does not gate ticket generation; instead it tells the user "you may
want to pick the defensive ticket instead." When the kill switch
trips (master DD ≥ ``kill_switch_threshold``), the response carries
an ``alternative_defensive_ticket`` so the frontend can offer the
normal-vs-defensive radio choice.

Drawdown derivation: master DD is computed from the
``account_snapshot`` history as (peak − latest) / peak on the
``cash + Σ shares × avg_cost`` series. We do not currently track
per-sleeve nav independently (the recommendations service emits
synthetic B013/B014/B015/B016 sleeve symbols pre-F011), so
``per_sleeve_dd`` falls back to a single ``master`` entry mirroring
``master_dd``. F011 wires real per-sleeve drawdowns; this scaffolding
keeps the schema stable.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from workbench_api.db.models.account_snapshot import AccountSnapshot
from workbench_api.schemas.risk_panel import (
    AlternativeDefensiveTicket,
    DefensivePosition,
    RiskPanelResponse,
    SleeveDrawdown,
)
from workbench_api.services.reconcile import get_slippage_analytics

_logger = logging.getLogger("workbench.risk_panel")

# Defaults from B011's risk policy. The kill_switch is the hard gate;
# per_sleeve is the "yellow advisory" trigger.
DEFAULT_KILL_SWITCH_THRESHOLD: float = 0.15
DEFAULT_PER_SLEEVE_THRESHOLD: float = 0.08

# The single defensive symbol the alternative ticket allocates to. SGOV
# is a 0-3 month Treasury bill ETF — used in B011's defensive sleeve as
# the canonical "rotate to safety" instrument. The 100% weight signals
# the user is fully out of risk assets; F011 may expand this to a
# multi-row defensive portfolio.
DEFENSIVE_SYMBOL: str = "SGOV"


def _snapshot_equity(snapshot: AccountSnapshot) -> float:
    """Sum cash + Σ (shares × avg_cost) on a snapshot's positions JSON."""

    total = float(snapshot.cash)
    for entry in snapshot.positions or []:
        if not isinstance(entry, dict):
            continue
        try:
            shares = float(entry.get("shares", 0.0))
            avg_cost = float(entry.get("avg_cost", 0.0))
        except (TypeError, ValueError):
            continue
        total += shares * avg_cost
    return total


def _master_drawdown_from_history(session: Session) -> float:
    """Equity-peak-to-latest drawdown across all account_snapshot rows.

    Returns a positive fraction (0.07 = 7%). Returns 0.0 when fewer
    than 2 snapshots exist (no peak to measure against).
    """

    stmt = select(AccountSnapshot).order_by(AccountSnapshot.snapshot_at)
    snapshots = list(session.execute(stmt).scalars().all())
    if len(snapshots) < 2:
        return 0.0
    equities = [_snapshot_equity(snap) for snap in snapshots]
    if not equities:
        return 0.0
    peak = max(equities[:-1])  # exclude the very latest from peak comparison
    latest = equities[-1]
    if peak <= 0:
        return 0.0
    drawdown = (peak - latest) / peak
    return max(0.0, drawdown)


def _per_sleeve_drawdowns(master_dd: float) -> list[SleeveDrawdown]:
    """Placeholder until F011 wires real per-sleeve nav tracking.

    We surface a single ``master`` row so the schema stays well-defined
    + the frontend can render *something* without having to special-case
    an empty list.
    """

    return [SleeveDrawdown(sleeve="master", drawdown=master_dd)]


def _classify_state(
    master_dd: float,
    per_sleeve_dd: list[SleeveDrawdown],
    *,
    kill_switch_threshold: float,
    per_sleeve_threshold: float,
) -> tuple[str, bool]:
    kill_switch_triggered = master_dd >= kill_switch_threshold
    if kill_switch_triggered:
        return "red", True
    any_sleeve_yellow = any(
        sleeve.drawdown >= per_sleeve_threshold for sleeve in per_sleeve_dd
    )
    if any_sleeve_yellow:
        return "yellow", False
    return "green", False


def _alternative_defensive_ticket(master_dd: float) -> AlternativeDefensiveTicket:
    return AlternativeDefensiveTicket(
        target_positions=[
            DefensivePosition(
                symbol=DEFENSIVE_SYMBOL,
                target_weight=1.0,
                rationale=(
                    "Kill switch tripped — rotate fully into the defensive "
                    "sleeve until master drawdown recovers below threshold."
                ),
            )
        ],
        rationale=(
            f"Master drawdown {master_dd * 100:.1f}% ≥ kill-switch threshold "
            f"({DEFAULT_KILL_SWITCH_THRESHOLD * 100:.1f}%). The defensive "
            f"ticket allocates 100% to {DEFENSIVE_SYMBOL} as the B011 "
            f"defensive proxy."
        ),
    )


def get_risk_panel(
    session: Session,
    *,
    kill_switch_threshold: float = DEFAULT_KILL_SWITCH_THRESHOLD,
    per_sleeve_threshold: float = DEFAULT_PER_SLEEVE_THRESHOLD,
) -> RiskPanelResponse:
    master_dd = _master_drawdown_from_history(session)
    per_sleeve = _per_sleeve_drawdowns(master_dd)
    state, kill_switch_triggered = _classify_state(
        master_dd,
        per_sleeve,
        kill_switch_threshold=kill_switch_threshold,
        per_sleeve_threshold=per_sleeve_threshold,
    )
    # Slippage trend reuses the F005 analytics service so the same
    # window calc is exercised from a second route — no duplication.
    analytics = get_slippage_analytics(session, window="3m")
    return RiskPanelResponse(
        state=state,  # type: ignore[arg-type]
        master_dd=master_dd,
        kill_switch_threshold=kill_switch_threshold,
        per_sleeve_threshold=per_sleeve_threshold,
        kill_switch_triggered=kill_switch_triggered,
        per_sleeve_dd=per_sleeve,
        slippage_trend_3m_bps=analytics.rolling_avg_bps,
        alternative_defensive_ticket=(
            _alternative_defensive_ticket(master_dd) if kill_switch_triggered else None
        ),
    )


def defensive_target_positions() -> list[dict[str, Any]]:
    """Return the same defensive target_positions the risk panel would
    surface in its ``alternative_defensive_ticket``. The tickets service
    uses this when ``GenerateTicketRequest.defensive=True`` so the two
    UIs stay consistent."""

    return [
        {
            "symbol": DEFENSIVE_SYMBOL,
            "target_weight": 1.0,
            "current_weight": 0.0,
            "diff": 1.0,
            "rationale": (
                "Defensive ticket mode — rotate fully to the B011 "
                "defensive proxy."
            ),
        }
    ]
