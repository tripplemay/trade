"""B057 F005 — schemas for ``GET /api/strategy-modes``.

The frontend mode selector reads this to enumerate the platform's strategy
modes (Master + regime + future modes auto-appear) and to mark research-state
modes honestly (``is_research_state`` → "研究态 / 前向验证中"). Read-only mirror
of the ``strategy_modes.registry`` enumeration.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class StrategyModeInfo(BaseModel):
    """One platform strategy mode (selector row)."""

    id: str = Field(description="Stable mode id, e.g. 'master' / 'regime'.")
    strategy_id: str = Field(
        description="Canonical strategy id (the API query param value), e.g. "
        "'master_portfolio' / 'regime_adaptive'."
    )
    display_name: str = Field(description="Chinese display name.")
    funding_state: str = Field(
        description="'live' (funded, real trading) or 'research' (forward-validation only)."
    )
    is_research_state: bool = Field(
        description="True when the mode is not funded — the surface marks it 研究态."
    )
    cadence: str = Field(description="Rebalance cadence, e.g. 'quarterly' / 'monthly'.")
    description: str = Field(description="One-line Chinese description.")


class StrategyModesResponse(BaseModel):
    """The full mode registry, in selector order (flagship first)."""

    modes: list[StrategyModeInfo]
