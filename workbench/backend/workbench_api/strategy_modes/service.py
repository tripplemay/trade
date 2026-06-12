"""B057 F005 — strategy-mode read service (the selector's data source).

Builds the ``GET /api/strategy-modes`` response from the canonical registry, so
the frontend mode selector + honest research-state badges have a single source
and future modes appear automatically.
"""

from __future__ import annotations

from workbench_api.schemas.strategy_modes import StrategyModeInfo, StrategyModesResponse
from workbench_api.strategy_modes.registry import list_modes


def list_strategy_modes() -> StrategyModesResponse:
    """Return every registered mode in selector order (flagship first)."""

    return StrategyModesResponse(
        modes=[
            StrategyModeInfo(
                id=mode.id,
                strategy_id=mode.strategy_id,
                display_name=mode.display_name,
                funding_state=mode.funding_state,
                is_research_state=mode.is_research_state,
                cadence=mode.cadence,
                description=mode.description,
            )
            for mode in list_modes()
        ]
    )
