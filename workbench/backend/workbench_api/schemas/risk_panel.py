"""Schemas for ``/api/execution/risk-panel`` (B023 F006).

Three banner states ride on the response:

* ``green``  — master_dd < per_sleeve_threshold (0.08) AND every sleeve
  DD < per_sleeve_threshold. Workflow proceeds normally.
* ``yellow`` — any sleeve DD ≥ per_sleeve_threshold (8%). Advisory only
  — no UI gate, user still generates the normal ticket.
* ``red``    — kill_switch_triggered (master_dd ≥ kill_switch_threshold,
  default 0.15 per B011). The response then includes an
  ``alternative_defensive_ticket`` so the frontend can render the
  normal-vs-defensive radio choice.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class SleeveDrawdown(BaseModel):
    sleeve: str
    drawdown: float = Field(description="Per-sleeve drawdown as a positive fraction (0.08 = 8%).")


class DefensivePosition(BaseModel):
    """One row in the alternative defensive ticket's target portfolio."""

    symbol: str
    target_weight: float = Field(ge=0.0, le=1.0)
    rationale: str | None = None


class AlternativeDefensiveTicket(BaseModel):
    target_positions: list[DefensivePosition]
    rationale: str = Field(
        description=(
            "Plain-English justification surfaced under the radio "
            "choice — for example, 'kill-switch tripped at 15% master DD; "
            "rotate to 100% defensive sleeve.'"
        )
    )


class RiskPanelResponse(BaseModel):
    state: Literal["green", "yellow", "red"]
    master_dd: float = Field(description="Master drawdown as a positive fraction (0.07 = 7%).")
    kill_switch_threshold: float = Field(default=0.15)
    per_sleeve_threshold: float = Field(default=0.08)
    kill_switch_triggered: bool
    per_sleeve_dd: list[SleeveDrawdown]
    slippage_trend_3m_bps: float | None = Field(
        default=None,
        description="Rolling 3-month avg slippage bps from /slippage-analytics.",
    )
    alternative_defensive_ticket: AlternativeDefensiveTicket | None = Field(
        default=None,
        description=(
            "Populated only when state == 'red'. The defensive target "
            "portfolio the user can choose instead of the normal ticket."
        ),
    )
