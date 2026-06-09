"""Risk-panel service (B023 F006; B048 F003 mark-to-market drawdown).

The workbench is research-only. The risk panel is informational — it
does not gate ticket generation; instead it tells the user "you may
want to pick the defensive ticket instead." When the kill switch
trips (master DD ≥ ``kill_switch_threshold``), the response carries
an ``alternative_defensive_ticket`` so the frontend can offer the
normal-vs-defensive radio choice.

Drawdown derivation (B048 F003): both master and per-sleeve drawdowns
are **mark-to-market over time** — :mod:`nav_history` rebuilds a NAV
series from the ``account_snapshot`` history, valuing each snapshot's
positions at the ``price_history`` close on-or-before its date, then
takes peak-to-latest. This replaces (a) the pre-F003 cost-basis master
series and (b) the pre-F011 placeholder that mirrored the master
drawdown onto a fixed sleeve list. When price history is missing for a
snapshot date the point degrades to cost basis and the symbol is flagged
in ``degraded_symbols`` (v0.9.21 — annotate, don't fabricate).
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from workbench_api.db.repositories.risk_explanation_snapshot import (
    RiskExplanationSnapshotRepository,
)
from workbench_api.schemas.risk_panel import (
    AlternativeDefensiveTicket,
    DefensivePosition,
    RiskPanelResponse,
    SleeveDrawdown,
)
from workbench_api.services.nav_history import (
    KILL_SWITCH_THRESHOLD,
    master_drawdown,
    per_sleeve_drawdowns,
    reconstruct_nav_history,
)
from workbench_api.services.reconcile import get_slippage_analytics

_logger = logging.getLogger("workbench.risk_panel")

# Defaults from B011's risk policy. The kill_switch is the hard gate
# (shared authority in nav_history); per_sleeve is the "yellow advisory".
DEFAULT_KILL_SWITCH_THRESHOLD: float = KILL_SWITCH_THRESHOLD
DEFAULT_PER_SLEEVE_THRESHOLD: float = 0.08

# The single defensive symbol the alternative ticket allocates to. SGOV
# is a 0-3 month Treasury bill ETF — used in B011's defensive sleeve as
# the canonical "rotate to safety" instrument. The 100% weight signals
# the user is fully out of risk assets; F011 may expand this to a
# multi-row defensive portfolio.
DEFENSIVE_SYMBOL: str = "SGOV"


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


def _build_per_sleeve(real_dd: dict[str, float]) -> list[SleeveDrawdown]:
    """Merge the strategy-registry sleeve skeleton with the real per-sleeve
    drawdowns (mirrors ``home._registry_sleeves`` + extras).

    Every registry sleeve renders (drawdown 0.0 when the account holds no
    position in it) so the UI's per-sleeve table keeps a stable skeleton —
    e.g. the B025 ``satellite_us_quality`` row stays visible regardless of
    holdings. Any extra sleeve a position is tagged with (``unclassified``,
    or a tag outside the registry) is appended after, so a real drawdown is
    never dropped."""

    from workbench_api.services.strategies import sleeve_strategies

    registry = sorted({s.sleeve for s in sleeve_strategies()})
    extras = sorted(s for s in real_dd if s not in registry)
    return [
        SleeveDrawdown(sleeve=sleeve, drawdown=real_dd.get(sleeve, 0.0))
        for sleeve in [*registry, *extras]
    ]


def get_risk_panel(
    session: Session,
    *,
    kill_switch_threshold: float = DEFAULT_KILL_SWITCH_THRESHOLD,
    per_sleeve_threshold: float = DEFAULT_PER_SLEEVE_THRESHOLD,
) -> RiskPanelResponse:
    # B048 F003: rebuild the mark-to-market NAV history once; master + every
    # sleeve drawdown read off the same series (one DB pass).
    nav = reconstruct_nav_history(session)
    master_dd = master_drawdown(nav)
    per_sleeve = _build_per_sleeve(per_sleeve_drawdowns(nav))
    state, kill_switch_triggered = _classify_state(
        master_dd,
        per_sleeve,
        kill_switch_threshold=kill_switch_threshold,
        per_sleeve_threshold=per_sleeve_threshold,
    )
    # Slippage trend reuses the F005 analytics service so the same
    # window calc is exercised from a second route — no duplication.
    analytics = get_slippage_analytics(session, window="3m")
    # B043 F003: surface the precomputed grounded explanation (read-only — the
    # request path NEVER calls the LLM; a daily job writes the snapshot). Absent
    # → None, the frontend renders no explanation block.
    risk_explanation = RiskExplanationSnapshotRepository(session).latest()
    return RiskPanelResponse(
        state=state,  # type: ignore[arg-type]
        master_dd=master_dd,
        kill_switch_threshold=kill_switch_threshold,
        per_sleeve_threshold=per_sleeve_threshold,
        kill_switch_triggered=kill_switch_triggered,
        per_sleeve_dd=per_sleeve,
        slippage_trend_3m_bps=analytics.rolling_avg_bps,
        valuation_basis=("cost_degraded" if nav.degraded else "mark_to_market"),
        degraded_symbols=list(nav.degraded_symbols),
        alternative_defensive_ticket=(
            _alternative_defensive_ticket(master_dd) if kill_switch_triggered else None
        ),
        explanation=risk_explanation.explanation if risk_explanation else None,
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
